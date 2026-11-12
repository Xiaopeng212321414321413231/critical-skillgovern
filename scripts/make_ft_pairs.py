#!/usr/bin/env python3
"""从 route_text 关键词模板化生成检索微调用的 (query → skill) 训练对。

设计：
  - 每个技能从它的 route_text 里抽中/英关键词，用一组"用户口吻"模板拼出查询；
  - **排除**审计用例（data/cases_audit.jsonl）—— 保证测试集留出，不发生泄漏；
  - 训练用 68 个技能文档做全库负样本（见 finetune_mmbert.py）。

用法：
  python make_ft_pairs.py [--table data/routing_table.json] [--out data/ft_pairs.jsonl] [--per-skill 6]
"""
import argparse
import json
import random
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CJK_RUN = re.compile(r"[\u4e00-\u9fff]{2,}")
EN_WORD = re.compile(r"[a-zA-Z][a-zA-Z0-9\-]{2,}")

ZH_T = ["帮我{kw}", "我想{kw}", "能不能{kw}", "{kw}怎么弄", "怎么{kw}", "帮我{kw1}和{kw2}", "{kw}一下"]
EN_T = ["help me {kw}", "how do I {kw}", "I need to {kw}", "can you {kw}", "{kw1} and {kw2} please"]

STOP_EN = {"the", "and", "for", "with", "you", "your", "this", "that", "use", "when", "user", "asks",
           "must", "any", "before", "from", "into", "out", "get", "set", "all", "not", "are", "its"}


def keywords(route_text):
    zh = []
    for m in CJK_RUN.findall(route_text):
        if m not in zh:
            zh.append(m)
    en = []
    for m in EN_WORD.findall(route_text.lower()):
        if m not in STOP_EN and m not in en:
            en.append(m)
    return zh, en


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", default="data/routing_table.json")
    ap.add_argument("--cases", default="data/cases_audit.jsonl")
    ap.add_argument("--out", default="data/ft_pairs.jsonl")
    ap.add_argument("--per-skill", type=int, default=6)
    ap.add_argument("--seed", type=int, default=20261010)
    args = ap.parse_args()

    table = json.loads((ROOT / args.table).read_text(encoding="utf-8"))
    skills = table["skills"]
    tests = [json.loads(l) for l in (ROOT / args.cases).read_text(encoding="utf-8").splitlines() if l.strip()]
    test_q = [c["query"].strip() for c in tests]

    def leaks(q):
        qs = q.strip()
        for t in test_q:
            if qs == t or (len(qs) >= 4 and qs in t) or (len(t) >= 4 and t in qs):
                return True
        return False

    rng = random.Random(args.seed)
    pairs, seen = [], set()
    for name in sorted(skills):
        rt = skills[name].get("route_text") or name
        zh, en = keywords(rt)
        cand = []
        if len(zh) >= 2:
            for i in range(len(zh)):
                cand.append(ZH_T[i % len(ZH_T)].format(kw=zh[i], kw1=zh[i],
                                                       kw2=zh[(i + 1) % len(zh)]))
        if len(zh) >= 1:
            for t in ZH_T:
                try:
                    cand.append(t.format(kw=zh[0], kw1=zh[0], kw2=zh[min(1, len(zh) - 1)]))
                except Exception:
                    pass
        if en:
            for i in range(min(len(en), 4)):
                cand.append(EN_T[i % len(EN_T)].format(kw=en[i], kw1=en[i],
                                                       kw2=en[(i + 1) % len(en)]))
        rng.shuffle(cand)
        picked = 0
        for q in cand:
            q = re.sub(r"\s+", " ", q).strip()
            if len(q) < 3 or q in seen or leaks(q):
                continue
            seen.add(q)
            pairs.append({"query": q, "skill": name})
            picked += 1
            if picked >= args.per_skill:
                break

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for p in pairs:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    n_sk = len({p["skill"] for p in pairs})
    print(f"生成训练对 {len(pairs)} 条，覆盖 {n_sk}/{len(skills)} 个技能 → {out}")
    leak = [p for p in pairs if leaks(p["query"])]
    print(f"泄漏检查：{len(leak)} 条与审计用例重叠（应为 0）")
    for p in pairs[:6]:
        print(f"  {p['skill']:<28} ← {p['query']}")


if __name__ == "__main__":
    main()
