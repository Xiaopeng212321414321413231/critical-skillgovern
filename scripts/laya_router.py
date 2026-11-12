#!/usr/bin/env python3
"""
Critical SkillGovern — Laya Router (System-1 非自回归技能路由)

把"靠 AR 大模型读全部技能描述自己挑"的路由方式，升级为
**非自回归判决 + 自回归执行 + 定义回灌** 的三层结构：

    L0  laya（非自回归，0.3~2s，本地免费）   → 路由/分类（一次前向出全部候选概率）
    L1  本地 AR 模型（如 Gemma-26B）          → 执行被选中的技能（生成式产出）
    L2  云端 AR agent                         → 置信度不足时接管 / 复核

与 validate-routing.py 的分工：
    validate-routing.py  —— 静态校验"描述写得合不合规"
    laya_router.py       —— 动态测量"描述能不能真的路由对"（top-1 准确率）
    两者互补：前者管形，后者管效。

⚠️ 两个来自 laya 实现内部的硬约束（不是调参能绕开的）：
    1. 所有选项共享 head_max_len=192 token 预算，且 `opt_budget < 16` 时按
       per = max(4, (192-16)//N) 硬切 —— **技能越多，每个技能只剩 4~14 token**。
       所以喂给 laya 的必须是「压缩路由文本 route_text」（≤10 英文词），
       不是把四层描述整段塞进去。本脚本会实测并警告超标项。
    2. 选项 ≥11 时官方温度 0.1006 被 SDK 强制抬回 0.5 → confidence 不可信。
       所以默认走两级（大类 ≤7 → 子类 ≤10）。

Usage:
    python laya_router.py scan   --skills <dir> [<dir> ...] [--out data/routing_table.json]
    python laya_router.py route  --query "帮我合并两个 PDF" [--method tree|flat]
    python laya_router.py eval   --cases data/cases.jsonl [--sweep]
    python laya_router.py feedback --query "..." --expected pdf --got pdfkit-py
    python laya_router.py refine [--min-support 2] [--apply]

必须用装了 laya 的解释器运行（本机：%%USERPROFILE%%\\laya-test\\.venv\\Scripts\\python.exe）
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

# ------------------------------------------------------------------ 常量

LAYER_KEYS = ["【触发场景】", "【输入特征】", "【输出目标】", "【不适用场景】"]
NEG_KEY = "【不适用场景】"
TRIG_KEY = "【触发场景】"
IN_KEY = "【输入特征】"

HEAD_MAX_LEN = 192          # english 档的选项预算；multilingual 档是 256，运行时从配置读
HEAD_RESERVED = 16          # opt_budget < 16 时的保底切分阈值
MAX_SKILLS_PER_QUERY = 20   # 超过就先做 shortlist 粗筛（词法打分，不额外下 embedding 模型）

DEFAULT_MODEL = os.path.join(os.path.expanduser("~"), "laya-test", "models", "english")
MULTILINGUAL_MODEL = os.path.join(os.path.expanduser("~"), "laya-test", "models", "multilingual", "multilingual")

DEFAULT_TABLE = "data/routing_table.json"
DEFAULT_LOG = "data/routing_log.jsonl"
DEFAULT_CASES = "data/cases.jsonl"

CJK = re.compile(r"[\u4e00-\u9fff]")

# 大类中文名 → laya criteria 用的英文标签（laya english 档读不了中文）
MAJOR_EN = {
    "信息采集": "information-collection",
    "信息整理": "information-organization",
    "搜索与资源发现": "search-resource-discovery",
    "智能代理与自动化": "agent-automation",
    "开发与工具": "development-tools",
    "多媒体": "multimedia",
    "实用工具": "utilities",
}


def read_head_max_len(model_dir, default=HEAD_MAX_LEN):
    """从检查点的 rl_agent_config.json 读 head_max_len。

    english=192 / multilingual=256。硬编码 192 会把 multilingual 的预算算小，
    导致 cmd_scan 误报"超预算"并推荐不必要的分级。
    """
    try:
        cfg = json.loads((Path(model_dir) / "rl_agent_config.json").read_text(encoding="utf-8"))
        return int(cfg.get("head_max_len", default))
    except Exception:
        return default


def _lex_tokens(text):
    """把文本切成可比对的词元集合。

    - 英文/数字：按整词；
    - 中文：同时取 1-gram 与 2-gram（中文没空格，只取整串会漏；只取 2-gram 又会漏掉
      "浏览器 / 浏览" 这种切位错开的重叠）。1-gram 在打分时降权。
    """
    out = set()
    for m in re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", text.lower()):
        if re.fullmatch(r"[\u4e00-\u9fff]+", m):
            out |= set(m)                                   # 1-gram
            out |= {m[i:i + 2] for i in range(len(m) - 1)}  # 2-gram
        elif len(m) >= 2:
            out.add(m)
    return out


def shortlist(skills, query, k=10):
    """大库粗筛：IDF 加权的词法 overlap，把候选压到 k 个再交给 laya 精挑。

    ⚠️ 已知局限（2026-10-10 实测）：**纯词法对「中文查询 vs 英文 route_text」完全无效**
    （跨语言零重叠）。66 技能实测 recall@10 只有 41.7%，且漏掉的正好都是英文描述的技能。
    两条解法：① 给这些技能补**双语 route_text**（走 refine/overrides 回灌）；
    ② 换成 mmBERT 编码器算向量召回（跨语言）。
    本函数返回**恰好 k 个**（不足则按分数补位），保证下游 laya 总在固定预算内做选择。
    """
    import math
    qt = _lex_tokens(query)
    if not qt:
        return list(skills)[:k]
    doc = {n: _lex_tokens(s.get("route_text") or "") for n, s in skills.items()}
    df = {}
    for toks in doc.values():
        for t in toks:
            df[t] = df.get(t, 0) + 1
    N = max(1, len(skills))
    scored = []
    for n, toks in doc.items():
        sc = 0.0
        for t in (qt & toks):
            w = 0.35 if len(t) == 1 else 1.0          # 中文单字降权，避免"的/用/一"噪声
            sc += w * (math.log((N + 1) / (df.get(t, 1) + 1)) + 1.0)
        scored.append((sc, n))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [n for _, n in scored[:k]]


# ------------------------------------------------------------------ 向量粗筛（mmBERT）

# ⚠️ 实测教训（2026-10-10，68 技能库，35 用例）：
#   直接拿 laya 里那个 mmBERT-base 编码器做 mean-pool 句向量，**检索不可用**——
#   off-diagonal 余弦均值 0.713 / 最高 0.961，严重各向异性：中文查询对任意英文描述
#   都有 ~0.7 的"地板相似度"，recall@10 只有 34%（还不如词法）。
#   原因：它是被 laya 的 masked-choice 头微调过的 masked-LM，表征不是句向量。
#   解法：**All-but-the-top**（减均值 + 去掉前 k 个主成分）后余弦相似度。
#   k 扫描实测：k=5 时 recall@10 = 80%（k=2:69% / k=4:74% / k=8:69%），故默认 k=5。
VEC_ABTT_K = 5
VEC_MAX_TOKENS = 256
_ENC = {"key": None, "model": None, "tok": None}


def _load_encoder(model_dir, ft=None):
    """从 laya 检查点里抽出 mmBERT 编码器（`encoder.*` 前缀 → ModernBertModel 命名）。

    ft: 可选的微调权重（finetune_mmbert.py 产出）。给定时在其上叠加微调状态字典。
    """
    base = Path(model_dir)
    ft_key = ""
    if ft:
        fp = Path(ft)
        ft_key = f"||ft={fp.name}@{int(fp.stat().st_mtime)}" if fp.exists() else ""
    key = str(base) + ft_key
    if _ENC["key"] == key:
        return _ENC["model"], _ENC["tok"]
    try:
        import torch  # noqa: F401
        from transformers import ModernBertConfig, ModernBertModel
        from tokenizers import Tokenizer
        from safetensors.torch import load_file
    except ImportError as e:
        sys.exit(f"✗ vecshortlist 需要 torch/transformers/tokenizers/safetensors：{e}\n"
                 f"  请用 laya-test 的解释器运行。")
    enc_dir = base / "encoder"
    model = ModernBertModel(ModernBertConfig.from_pretrained(str(enc_dir)))
    sd = load_file(str(base / "model.safetensors"))
    model.load_state_dict({k[len("encoder."):]: v for k, v in sd.items() if k.startswith("encoder.")},
                          strict=False)
    if ft_key:
        ck = torch.load(str(ft), weights_only=False)
        model.load_state_dict(ck["state"], strict=False)
    model.eval()
    tok = Tokenizer.from_file(str(base / "tokenizer" / "tokenizer.json"))
    _ENC.update({"key": key, "model": model, "tok": tok})
    return model, tok


def embed_texts(texts, model_dir, ft=None):
    """mean-pool 句向量（L2 归一化前的原始向量）。"""
    import torch
    model, tok = _load_encoder(model_dir, ft)
    out = []
    with torch.no_grad():
        for t in texts:
            ids = tok.encode(t).ids[:VEC_MAX_TOKENS] or [0]
            x = torch.tensor([ids])
            h = model(input_ids=x, attention_mask=torch.ones_like(x)).last_hidden_state
            out.append(h.mean(1)[0])
    return torch.stack(out)


def _doc_space(skills, model_dir, ft=None):
    """技能描述向量空间：返回 (names, D_raw, mean, pcs)。按 route_text 内容哈希缓存。"""
    import hashlib
    import torch
    names = list(skills)
    texts = [skills[n].get("route_text") or n for n in names]
    cache_dir = Path(__file__).resolve().parents[1] / "data" / "emb_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    ft_tag = ""
    if ft and Path(ft).exists():
        ft_tag = "||ft:" + hashlib.md5(Path(ft).read_bytes()).hexdigest()[:10]
    h = hashlib.md5((str(model_dir) + "||" + "||".join(texts) + ft_tag).encode("utf-8")).hexdigest()[:16]
    cache = cache_dir / f"docs_{h}.pt"
    if cache.exists():
        obj = torch.load(cache, weights_only=False)
        return names, obj["D"], obj["mean"], obj["pcs"]
    D = embed_texts(texts, model_dir, ft)
    mu = D.mean(0, keepdim=True)
    q = min(16, max(1, len(names) - 1))
    _, _, V = torch.pca_lowrank(D - mu, q=q)
    torch.save({"D": D, "mean": mu, "pcs": V}, cache)
    return names, D, mu, V


def vector_shortlist(skills, query, k=10, model_dir=MULTILINGUAL_MODEL, abtt_k=VEC_ABTT_K, ft=None):
    """mmBERT 向量召回（跨语言）。

    abtt_k>0：去均值 + 去前 abtt_k 个主成分（ABTT）——原始 mmBERT 各向异性严重时必需。
    abtt_k=0：直接用原始向量余弦（微调后的编码器已对齐检索，ABTT 反而有害，见 §4.7）。
    """
    import torch
    import torch.nn.functional as F
    names, D, mu, V = _doc_space(skills, model_dir, ft)
    q = embed_texts([query], model_dir, ft)[0]
    if not abtt_k:
        sims = (F.normalize(D, dim=-1) @ F.normalize(q, dim=-1)).reshape(-1)
    else:
        Vr = V[:, :abtt_k]
        Dp = D - mu
        Dp = Dp - (Dp @ Vr) @ Vr.T
        qp = q - mu.squeeze(0)
        qp = qp - (qp @ Vr) @ Vr.T
        sims = (F.normalize(Dp, dim=-1) @ F.normalize(qp, dim=-1)).reshape(-1)
    idx = torch.topk(sims, min(k, len(names))).indices.tolist()
    return [names[i] for i in idx]


def hybrid_shortlist(skills, query, k=10, model_dir=MULTILINGUAL_MODEL, abtt_k=VEC_ABTT_K, ft=None):
    """词法 ∪ 向量：两路各取 k，去重后并集（跨语言 + 词面双保险，召回更高但候选更多）。"""
    out = []
    for n in shortlist(skills, query, k) + vector_shortlist(skills, query, k, model_dir, abtt_k, ft):
        if n not in out:
            out.append(n)
    return out


# ------------------------------------------------------------------ laya 接入

class Laya:
    """laya 的薄封装：延迟加载 + 单点调用 + 预算测量。

    单独包一层是为了让本脚本在没有 laya 的环境里也能跑 scan / refine
    （只有 route / eval 才真的需要模型）。
    """

    def __init__(self, model_dir, threads=8):
        os.environ.setdefault("LAYA_THREADS", str(threads))
        os.environ.setdefault("OMP_NUM_THREADS", str(threads))
        self.model_dir = model_dir
        self.head_max_len = read_head_max_len(model_dir)
        self._agent = None
        self.load_s = None

    @property
    def agent(self):
        if self._agent is None:
            try:
                import laya  # noqa: F401
            except ImportError as e:
                sys.exit(
                    "✗ 无法 import laya：%s\n"
                    "  请用装了 laya 的解释器运行，例如：\n"
                    "  %%USERPROFILE%%\\laya-test\\.venv\\Scripts\\python.exe %s"
                    % (e, Path(__file__).name)
                )
            import laya
            t0 = time.time()
            self._agent = laya.load(self.model_dir)
            self.load_s = time.time() - t0
        return self._agent

    def predict(self, state, questions):
        return self.agent.predict(state, questions)

    def is_english(self, text):
        try:
            import laya
            return bool(laya.is_english(text))
        except Exception:
            return not bool(CJK.search(text))

    def count_tokens(self, text):
        """按 laya 的分词器数 token（用于预算警告）。"""
        try:
            return len(self.agent.tok(text, add_special_tokens=False)["input_ids"])
        except Exception:
            return int(len(text.split()) * 1.4) + 1

    @staticmethod
    def per_option_budget(n_options, head_max_len=HEAD_MAX_LEN):
        """复刻 build_sequence 的选项预算逻辑，返回每个选项能活下来的 token 数。

        opt_budget = H - sum(len(o))。每项开头强制一个 [MASK]，
        所以 n 项至少要 n 个 token；放不下时 per = max(4, (H-16)//n)。
        H 由检查点决定：english=192、multilingual=256。
        """
        if n_options <= 0:
            return head_max_len
        room = head_max_len - n_options * 2          # 2 ≈ [MASK] + 至少 1 个内容 token
        if room >= HEAD_RESERVED:
            return max(1, head_max_len // n_options)
        return max(4, (head_max_len - HEAD_RESERVED) // n_options)


# ------------------------------------------------------------------ 技能解析

def parse_skill(path: Path):
    """解析一个技能文件，抽出四层路由描述。"""
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        return {"name": path.stem, "path": str(path), "error": f"读取失败: {e}"}

    fm, body = {}, content
    parts = content.split("---", 2)
    if len(parts) >= 3:
        if yaml is not None:
            try:
                fm = yaml.safe_load(parts[1]) or {}
            except Exception:
                fm = {}
        body = parts[2]

    desc = str(fm.get("description", "") or "")
    layers = {}
    for i, key in enumerate(LAYER_KEYS):
        if key not in desc:
            continue
        rest = desc.split(key, 1)[1]
        # 到下一个层级标记为止
        for nxt in LAYER_KEYS[i + 1:]:
            if nxt in rest:
                rest = rest.split(nxt, 1)[0]
        rest = rest.split("---")[0]
        layers[key] = rest.strip()

    name = fm.get("name") or path.parent.name or path.stem
    tags = fm.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    related = fm.get("related_skills") or []
    if isinstance(related, str):
        related = [related]

    # ⚠️ 不要把正文兜底塞进 layers：那会让 compress_route_text 误以为"有四层描述"，
    # 直接拿正文当前几个词用（实测准确率塌到 33%）。兜底只放 desc_head。
    if not desc:
        first = [ln.strip() for ln in body.splitlines() if ln.strip()]
        desc = " ".join(first[:6])[:400]

    return {
        "name": name,
        "path": str(path),
        "format": "hermes" if (TRIG_KEY in layers and fm) else "generic",
        "tags": [str(t) for t in tags],
        "related_skills": [str(r) for r in related],
        "layers": layers,
        "desc_len": len(desc),
        "desc_head": desc.strip()[:400],
    }


def compress_route_text(skill, max_words=9):
    """把技能描述压成 laya 能用的短路由文本（这是本脚本的核心产出）。

    ⚠️ 实测教训（2026-10-10，57 个真实技能库）：
    直接拿 description 的前几个词喂 laya 是**错的** —— 大多数技能的 description 是
    「功能说明」而不是「触发条件」，且常带 markdown 残留（`##`、`>`），
    实测顶-1 准确率只有 33.3%（10 选项随机基线 10%）。
    必须先定位**判别性从句**，再压缩。

    提取优先级：
      1. 显式四层描述【触发场景】/【输入特征】   ← 最优，给的是"什么时候用"
      2. "Use when …" / "should be used when …" / "当用户…时" / "用于…" 从句
      3. 首句（剥掉 markdown 与开场套话）
    负样本（【不适用场景】）不进 route_text —— 它在 refine 阶段回灌。
    """
    layers = skill.get("layers", {})
    trig = layers.get(TRIG_KEY, "")
    inp = layers.get(IN_KEY, "")
    out_goal = layers.get("【输出目标】", "")
    source = skill.get("desc_head", "") or ""

    def strip_md(s):
        s = re.sub(r"^[>#*\-\s]+", "", s, flags=re.M)
        s = re.sub(r"`([^`]*)`", r"\1", s)
        s = re.sub(r"\*\*([^*]*)\*\*", r"\1", s)
        s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
        return re.sub(r"\s+", " ", s).strip()

    def pick_clause(text):
        """从一句/一段描述里挖出判别性最强的那个从句。"""
        t = strip_md(text)
        # 1) 英文 Use when / should be used when
        for pat in (r"(?:should be used|is used|use this skill|use it|use)\s+(?:whenever|when|for)\s+(.+)",
                    r"\bwhenever\s+(.+)",
                    r"\buse when\s+(.+)",
                    r"\bused when\s+(.+)"):
            m = re.search(pat, t, re.I)
            if m:
                return m.group(1)
        # 2) 中文触发句
        m = re.search(r"当(.+?)时", t)
        if m:
            return m.group(1)
        m = re.search(r"用于([^。；]{4,60})", t)
        if m:
            return m.group(1)
        # 3) 退回首句，并去掉"这是一个/This skill provides"这类开场套话
        first = re.split(r"[。.;！!？?]", t)[0]
        first = re.sub(r"^(this skill|guide for|this is a|a skill for|provides?)\s*", "", first, flags=re.I)
        return first

    raw = " ".join(x for x in (trig, inp, out_goal) if x)
    if not raw:
        raw = pick_clause(source)
    else:
        raw = strip_md(raw)

    # 逗号/顿号/分号 归一化，然后按词数硬切（超预算会被 laya 静默截断）
    raw = re.sub(r"[，。；、]\s*", ", ", raw)
    raw = re.sub(r"\s*,\s*", ", ", raw)
    raw = re.sub(r"\s+", " ", raw).strip(" ,.-")
    parts = [p for p in re.split(r"\s+", raw) if p]
    if len(parts) > max_words:
        raw = " ".join(parts[:max_words])
    return raw.strip(", ")



# ------------------------------------------------------------------ scan

SKIP_DIRS = {"references", "templates", "scripts", "assets", "examples",
             "tests", "__pycache__", "node_modules", ".git", "experts"}


def cmd_scan(args):
    roots = [Path(p).expanduser() for p in args.skills]
    skills = {}
    for root in roots:
        if not root.exists():
            print(f"⚠️ 跳过不存在的路径: {root}")
            continue
        for dirpath, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in SKIP_DIRS]
            for fn in files:
                if fn not in ("SKILL.md", "skill.md"):
                    continue
                p = Path(dirpath) / fn
                s = parse_skill(p)
                if s.get("error"):
                    continue
                s["route_text"] = compress_route_text(s)
                s["route_text_source"] = "auto"
                s["source_root"] = str(root)
                skills[s["name"]] = s

    # 人工/回灌覆盖表：这是 refine 闭环唯一允许被改写的落点。
    # 之所以单独一个文件而不是直接改 SKILL.md：route_text 是"给 laya 的压缩表示"，
    # 与 SKILL.md 里给人和 AR 模型看的长描述是两种东西，混在一起会互相污染。
    ov_path = Path(args.overrides)
    if ov_path.exists():
        try:
            ov = json.loads(ov_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"⚠️ 覆盖表解析失败 {ov_path}: {e}")
            ov = {}
        n_ov = 0
        for name, text in ov.items():
            if name in skills and text:
                skills[name]["route_text"] = str(text).strip()
                skills[name]["route_text_source"] = "override"
                n_ov += 1
        print(f"已应用 {n_ov} 条 route_text 覆盖（来自 {ov_path.name}）")

    # 语料语言体检：laya english 档读不了中文
    zh = [n for n, s in skills.items() if CJK.search(s["route_text"])]
    hml = read_head_max_len(getattr(args, "model_dir", DEFAULT_MODEL))
    budget = Laya.per_option_budget(max(1, len(skills)), hml)
    over = []
    for n, s in skills.items():
        # 粗略估算：英文 ~4 字符/token，中文 ~1.5 字符/token
        t = s["route_text"]
        est = len(CJK.findall(t)) * 1.5 + (len(t) - len(CJK.findall(t))) / 4
        if est > budget:
            over.append((n, round(est, 1)))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "roots": [str(r) for r in roots],
        "count": len(skills),
        "per_option_token_budget": budget,
        "skills": skills,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"扫描完成：{len(skills)} 个技能 → {out}")
    print(f"laya 每个选项的 token 预算：约 {budget} token（head_max_len={hml}，技能越多越小）")
    if len(skills) > MAX_SKILLS_PER_QUERY:
        print(f"⚠️ 技能数 {len(skills)} > {MAX_SKILLS_PER_QUERY} → 单次 flat 路由超出建议上限，"
              f"请用 --method tree / shortlist 或先做 shortlist 粗筛")
    if zh:
        print(f"⚠️ {len(zh)}/{len(skills)} 个技能的 route_text 仍是中文 → english 检查点会崩，"
              f"必须换 laya-multilingual 或人工译成英文")
        print("   " + ", ".join(zh[:12]) + (" ..." if len(zh) > 12 else ""))
    if over:
        print(f"⚠️ {len(over)} 个技能 route_text 超出预算，会被 laya 静默截断：")
        for n, est in over[:12]:
            print(f"   {n}: 约 {est} token > {budget}")
    return skills


# ------------------------------------------------------------------ 路由

def build_flat_question(skills, names=None):
    names = names or list(skills)
    return {
        "pick": {
            "type": "choice",
            "instructions": "Which single skill should handle the user request? Choose the skill whose scope matches best.",
            "criteria": {n: skills[n]["route_text"] for n in names},
        }
    }


def build_major_question(skills):
    """一级：按 tags 第一层聚类成大类（≤7 项，confidence 可信区）。"""
    groups = {}
    for n, s in skills.items():
        major = (s.get("tags") or ["utilities"])[0]
        groups.setdefault(major, []).append(n)
    criteria = {}
    for major, members in groups.items():
        # 用该组技能名做描述，避免中文 tags 直接进 criteria
        criteria[major] = "skills about " + ", ".join(m.strip("skill-") for m in members[:6])
    return {"pick": {"type": "choice",
                     "instructions": "Which capability area does the user request belong to?",
                     "criteria": criteria}}, groups


def cmd_route(args):
    table = load_table(args.table)
    skills = table["skills"]
    L = Laya(args.model_dir, args.threads)

    query = args.query
    if not L.is_english(query):
        print("⚠️ 请求不是英文 → english 检查点在此类输入上不是退化而是崩塌"
              "（官方：MASSIVE 非英文意图 0.306 ≈ 随机）。请改用 --model multilingual 的检查点。")

    t0 = time.perf_counter()
    if args.method == "tree":
        q_major, groups = build_major_question(skills)
        r1 = L.predict({"request": query}, q_major)
        a1 = r1["answers"]["pick"]
        major = a1["choice"]
        members = groups.get(major, list(skills))
        r2 = L.predict({"request": query}, build_flat_question(skills, members))
        a2 = r2["answers"]["pick"]
        dt = (time.perf_counter() - t0) * 1000
        print(f"laya 加载 {L.load_s:.1f}s | 两级路由耗时 {dt:.0f} ms")
        print(f"① 大类: {major}  (conf {a1['confidence']:.3f})")
        print(f"② 技能: {a2['choice']}  (conf {a2['confidence']:.3f})")
        top = sorted(a2["probabilities"].items(), key=lambda kv: -kv[1])[:5]
        print("   候选分布: " + ", ".join(f"{k}={v:.3f}" for k, v in top))
        conf = a2["confidence"]
    elif args.method in ("shortlist", "vecshortlist", "hybrid"):
        if args.method == "vecshortlist":
            cand = vector_shortlist(skills, query, args.k, args.model_dir)
        elif args.method == "hybrid":
            cand = hybrid_shortlist(skills, query, args.k, args.model_dir)
        else:
            cand = shortlist(skills, query, args.k)
        r = L.predict({"request": query}, build_flat_question(skills, cand))
        a = r["answers"]["pick"]
        dt = (time.perf_counter() - t0) * 1000
        print(f"laya 加载 {L.load_s:.1f}s | {args.method}(K={len(cand)}) → 精挑 耗时 {dt:.0f} ms")
        print(f"   短名单: {', '.join(cand)}")
        print(f"→ {a['choice']}  (conf {a['confidence']:.3f})")
        top = sorted(a["probabilities"].items(), key=lambda kv: -kv[1])[:5]
        print("   候选分布: " + ", ".join(f"{k}={v:.3f}" for k, v in top))
        conf = a["confidence"]
    else:
        r = L.predict({"request": query}, build_flat_question(skills))
        a = r["answers"]["pick"]
        dt = (time.perf_counter() - t0) * 1000
        print(f"laya 加载 {L.load_s:.1f}s | 路由耗时 {dt:.0f} ms")
        print(f"→ {a['choice']}  (conf {a['confidence']:.3f})")
        top = sorted(a["probabilities"].items(), key=lambda kv: -kv[1])[:5]
        print("   候选分布: " + ", ".join(f"{k}={v:.3f}" for k, v in top))
        conf = a["confidence"]

    if args.threshold and conf < args.threshold:
        print(f"⚠️ conf {conf:.3f} < 阈值 {args.threshold} → 升级到自回归层（本地 26B / 云端 agent）")


# ------------------------------------------------------------------ eval

def cmd_eval(args):
    table = load_table(args.table)
    skills = table["skills"]
    cases = [json.loads(ln) for ln in Path(args.cases).read_text(encoding="utf-8").splitlines() if ln.strip()]
    L = Laya(args.model_dir, args.threads)

    ncand = {"shortlist": args.k, "vecshortlist": args.k, "hybrid": args.k * 2}.get(args.method, len(skills))
    print(f"用例 {len(cases)} 条 | 技能池 {len(skills)} 个 | 方法 {args.method} | "
          f"实际候选 {ncand} 个 | 每选项预算 ~{Laya.per_option_budget(ncand, L.head_max_len)} token")
    print("=" * 68)

    rows = []
    for c in cases:
        q = c["query"]
        state = {"request": q}
        t0 = time.perf_counter()
        if args.method == "vecshortlist":
            cand = vector_shortlist(skills, q, args.k, args.model_dir)
        elif args.method == "hybrid":
            cand = hybrid_shortlist(skills, q, args.k, args.model_dir)
        elif args.method == "shortlist":
            cand = shortlist(skills, q, args.k)
        else:
            cand = list(skills)
        recall = c["expected"] in cand
        r = L.predict(state, build_flat_question(skills, cand))
        ms = (time.perf_counter() - t0) * 1000
        a = r["answers"]["pick"]
        ranked = [k for k, _ in sorted(a["probabilities"].items(), key=lambda kv: -kv[1])]
        top1 = ranked[0]
        ok1 = top1 == c["expected"]
        ok3 = c["expected"] in ranked[:3]
        rows.append({"query": q, "expected": c["expected"], "top1": top1, "top3": ranked[:3],
                     "ok1": ok1, "ok3": ok3, "recall": recall, "cand": len(cand),
                     "conf": a["confidence"], "ms": ms})
        mark = "✅" if ok1 else ("🔸" if ok3 else "❌")
        print(f"{mark} exp={c['expected']:<28} got={top1:<28} conf={a['confidence']:.3f} {ms:.0f}ms")
        if not recall:
            print(f"      ⚠️ 粗筛漏掉（K={len(cand)}）")
        if not ok1:
            print(f"      top3: {', '.join(ranked[:3])}")

    n = len(rows)
    acc1 = sum(r["ok1"] for r in rows) / n
    acc3 = sum(r["ok3"] for r in rows) / n
    rec = sum(r["recall"] for r in rows) / n
    lat = sorted(r["ms"] for r in rows)[n // 2]
    print("=" * 68)
    print(f"top-1 准确率 {acc1:.1%}   top-3 {acc3:.1%}   延迟中位 {lat:.0f} ms")
    if args.method != "flat":
        print(f"粗筛召回@{args.k} {rec:.1%}（漏掉即不可救 → 这是大库路线的真实上限）")
    print(f"随机基线（{len(skills)} 选 1）= {1/len(skills):.1%}")

    if args.sweep:
        print("-" * 68)
        print("置信度阈值扫描（决定「什么时候升级到自回归层」的 tau）")
        print(f"{'tau':>6} {'覆盖率':>8} {'已判决中的正确率':>16}")
        best = None
        for tau in [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40]:
            sel = [r for r in rows if r["conf"] >= tau]
            cov = len(sel) / n
            prec = (sum(r["ok1"] for r in sel) / len(sel)) if sel else float("nan")
            print(f"{tau:>6.2f} {cov:>7.0%} {prec:>15.1%}")
            if sel and (best is None or prec > best[1]):
                best = (tau, prec, cov)
        if best:
            print(f"→ 建议 tau≈{best[0]:.2f}：覆盖 {best[2]:.0%} 的流量，这部分 top-1 达 {best[1]:.1%}，"
                  f"其余 {1-best[2]:.0%} 升级给自回归层")

    if args.log:
        p = Path(args.log)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps({"type": "eval", **r}, ensure_ascii=False) + "\n")
        print(f"已追加 {n} 条到 {p}")


# ------------------------------------------------------------------ feedback / refine

def cmd_feedback(args):
    p = Path(args.log)
    p.parent.mkdir(parents=True, exist_ok=True)
    rec = {"type": "feedback", "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
           "query": args.query, "expected": args.expected, "got": args.got,
           "note": args.note or ""}
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"已记录反馈 → {p}")


STOP = set("the a an and or of to for with in on at is are be do does my me you your it "
           "this that when how what which please help need want use using".split())

# 判别力过滤：这些词出现在一堆技能的 route_text 里，加进去只会污染描述
GENERIC = set("""skill skills file files data user users app apps create created creating
generate generated new add adding edit edited analyse analysis query queries tool tools
document documents page pages report reports make build support using work works""".split())


def keywords(text, limit=6, discriminative=None):
    """抽判别性关键词。

    实测教训：不过滤时 refine 会挖出 `two` / `into` / `can` / `add` 这类零判别力的词，
    补丁写进技能描述等于没写。判据：这个词必须**不出现在其他任何技能的 route_text 里**，
    （否则它无法把两个技能区分开），也不在通用词表里。
    """
    toks = re.findall(r"[a-zA-Z\u4e00-\u9fff]{2,}", text.lower())
    out = []
    for t in toks:
        if t in STOP or t in GENERIC or t.isdigit():
            continue
        if re.fullmatch(r"[\u4e00-\u9fff]+", t) and len(t) > 8:
            continue          # 中文整句当关键词没意义（应由 AR 层做中文分词）
        if discriminative is not None and t in discriminative:
            continue
        if t not in out:
            out.append(t)
        if len(out) >= limit:
            break
    return out


def cmd_refine(args):
    table = load_table(args.table)
    log = Path(args.log)
    if not log.exists():
        sys.exit(f"✗ 没有 {log}，先跑 eval 或 feedback 攒数据")

    recs = [json.loads(ln) for ln in log.read_text(encoding="utf-8").splitlines() if ln.strip()]
    mis = [r for r in recs if r.get("type") in ("eval", "feedback")
           and r.get("expected") and r.get("got", r.get("top1")) != r["expected"]]
    for r in mis:
        r["got"] = r.get("got") or r.get("top1")

    pairs = {}
    for r in mis:
        pairs.setdefault((r["got"], r["expected"]), []).append(r)

    if not pairs:
        print("✅ 反馈日志里没有误路由样本，无需调整")
        return

    patches = []
    for (got, expected), rows in sorted(pairs.items(), key=lambda kv: -len(kv[1])):
        if len(rows) < args.min_support:
            continue
        sk = table["skills"].get(expected, {})
        rt = sk.get("route_text", "").lower()
        # 判别力集合：出现在**其他任何技能** route_text 里的词，无法把两者区分开
        others = set()
        for n_other, s_other in table["skills"].items():
            if n_other == expected:
                continue
            others |= set(re.findall(r"[a-zA-Z\u4e00-\u9fff]{2,}",
                                     (s_other.get("route_text") or "").lower()))
        # 从误路由样本里挖"当前 route_text 没覆盖、且他处也没出现"的词
        cand = []
        for r in rows:
            for kw in keywords(r["query"], limit=8, discriminative=others):
                if kw not in rt and kw not in cand:
                    cand.append(kw)
        patches.append({
            "expected": expected, "false_positive": got, "support": len(rows),
            "missing_keywords": cand[:6],
            "samples": [r["query"] for r in rows[:3]],
            "patch": {
                "add_to_输入特征": "、".join(cand[:6]),
                "add_to_不适用场景": f"当用户要{cand[0] if cand else '该意图'}时，应使用 {expected}，不要用 {got}",
                "route_text_suggestion": (sk.get("route_text", "") + " " + " ".join(cand[:3])).strip(),
            },
        })

    if not patches:
        print(f"误路由样本不足以支持 >= {args.min_support} 条的证据，暂不产出补丁")
        return

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# 路由定义回灌补丁（由 laya 误路由反推）", "",
             f"生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}",
             f"误路由样本：{len(mis)} 条，聚成 {len(patches)} 组（min_support={args.min_support}）", "",
             "> ⚠️ 本文件只是**提案**。按框架方法论第 3 阶段，需你审批后才执行。",
             "", "| 误选 | 应该选 | 证据条数 | 当前 route_text 缺的词 |",
             "|---|---|---|---|"]
    for p in patches:
        lines.append(f"| {p['false_positive']} | **{p['expected']}** | {p['support']} | "
                     f"{', '.join(p['missing_keywords']) or '—'} |")
    lines += ["", "---", ""]
    for p in patches:
        lines += [f"## {p['false_positive']} ❌ → {p['expected']} ✅", "",
                  f"**证据（{p['support']} 条）**："]
        lines += [f"- {s}" for s in p["samples"]]
        lines += ["", "**建议补丁**：", "",
                  f"- `{IN_KEY}` 追加：{p['patch']['add_to_输入特征'] or '（无可提取词）'}",
                  f"- `{NEG_KEY}` 追加：{p['patch']['add_to_不适用场景']}",
                  f"- `route_text`（给 laya 的压缩文本）：`{p['patch']['route_text_suggestion']}`",
                  ""]
    out.write_text("\n".join(lines), encoding="utf-8")

    jout = out.with_suffix(".json")
    jout.write_text(json.dumps(patches, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"产出 {len(patches)} 组补丁提案 → {out}")
    print(f"                        → {jout}")
    print("按方法论第 3 阶段：先由你审批，再执行修复，最后跑 eval 复测 top-1 是否真的涨了。")
    if args.apply:
        print("⚠️ --apply 已忽略：本脚本默认只提案不落盘技能文件（防「改坏不回归」）。")


# ------------------------------------------------------------------ 工具

def load_table(path):
    p = Path(path)
    if not p.exists():
        sys.exit(f"✗ 找不到路由表 {p}，先跑：laya_router.py scan --skills <目录>")
    return json.loads(p.read_text(encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser(description="Critical SkillGovern × Laya 非自回归路由")
    sub = ap.add_subparsers(dest="cmd", required=True)

    common = dict()
    for name, fn, helptext in [
        ("scan", cmd_scan, "扫描技能目录，生成 laya 路由表"),
        ("route", cmd_route, "用 laya 路由一条请求"),
        ("eval", cmd_eval, "在标注用例上测 top-1 准确率"),
        ("feedback", cmd_feedback, "记录一次「应该选谁」的反馈"),
        ("refine", cmd_refine, "从误路由反推技能定义补丁"),
    ]:
        sp = sub.add_parser(name, help=helptext)
        if name == "scan":
            sp.add_argument("--skills", nargs="+", required=True)
            sp.add_argument("--out", default=DEFAULT_TABLE)
            sp.add_argument("--overrides", default="data/route_text_overrides.json")
            sp.add_argument("--model-dir", default=DEFAULT_MODEL,
                            help="仅用于读 head_max_len 估算预算（english=192 / multilingual=256）")
        else:
            sp.add_argument("--table", default=DEFAULT_TABLE)
        if name in ("route", "eval"):
            sp.add_argument("--model-dir", default=DEFAULT_MODEL,
                            help="english 或 multilingual 检查点目录")
            sp.add_argument("--threads", type=int, default=8)
        if name == "route":
            sp.add_argument("--query", required=True)
            sp.add_argument("--method", choices=["flat", "tree", "shortlist", "vecshortlist", "hybrid"], default="flat")
            sp.add_argument("--k", type=int, default=10, help="shortlist 短名单大小（建议 <=10）")
            sp.add_argument("--threshold", type=float, default=0.15)
        if name == "eval":
            sp.add_argument("--cases", default=DEFAULT_CASES)
            sp.add_argument("--method", choices=["flat", "shortlist", "vecshortlist", "hybrid"], default="flat")
            sp.add_argument("--k", type=int, default=10, help="shortlist 短名单大小")
            sp.add_argument("--sweep", action="store_true")
            sp.add_argument("--log", default=DEFAULT_LOG)
        if name == "feedback":
            sp.add_argument("--query", required=True)
            sp.add_argument("--expected", required=True)
            sp.add_argument("--got", default="")
            sp.add_argument("--note", default="")
            sp.add_argument("--log", default=DEFAULT_LOG)
        if name == "refine":
            sp.add_argument("--log", default=DEFAULT_LOG)
            sp.add_argument("--out", default="data/routing_patches.md")
            sp.add_argument("--min-support", type=int, default=2)
            sp.add_argument("--apply", action="store_true")
        sp.set_defaults(func=fn)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
