#!/usr/bin/env python3
"""laya 路由审计：**全程遵从 laya 的判断**（只记录、不打分改判、不人工干预）。

与 eval 的区别：
  - eval   只算准确率
  - audit  额外算 **token 消耗**（laya 读了多少 vs 一个"读全部描述"的 AR 路由要读多少）
           与 **路由质量**（exact / 可接受集合 / 错误），并落成一份可交付的 markdown 报告

用法：
  python laya_route_audit.py --cases data/cases_audit.jsonl --method shortlist --k 10 \
      --model-dir "%%USERPROFILE%%\\laya-test\\models\\multilingual\\multilingual" \
      --out data/route-audit.md
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import laya_router as LR  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="laya 路由审计（遵从 laya 判断）")
    ap.add_argument("--cases", required=True)
    ap.add_argument("--table", default="data/routing_table.json")
    ap.add_argument("--model-dir", default=LR.MULTILINGUAL_MODEL)
    ap.add_argument("--method", choices=["flat", "shortlist", "vecshortlist", "hybrid"], default="shortlist")
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--threshold", type=float, default=0.30)
    ap.add_argument("--ft", default=None, help="微调后的 mmBERT 检索权重（vecshortlist/hybrid 生效）")
    ap.add_argument("--vec-abtt", type=int, default=None,
                    help="向量召回去主成分数；0=原始余弦（微调后推荐），缺省=模块默认（原始 mmBERT 用 5）")
    ap.add_argument("--out", default="data/route-audit.md")
    args = ap.parse_args()

    table = json.loads(Path(args.table).read_text(encoding="utf-8"))
    skills = table["skills"]
    cases = [json.loads(ln) for ln in Path(args.cases).read_text(encoding="utf-8").splitlines() if ln.strip()]
    L = LR.Laya(args.model_dir, args.threads)

    # AR 路由基线：一个自回归模型要"读全部技能描述"才能选，这是本方案要替代的成本
    ar_router_tokens = sum(L.count_tokens(s.get("desc_head") or "") for s in skills.values())

    ncand = {"shortlist": args.k, "vecshortlist": args.k, "hybrid": args.k * 2}.get(args.method, len(skills))
    budget = LR.Laya.per_option_budget(ncand, L.head_max_len)
    vab = LR.VEC_ABTT_K if args.vec_abtt is None else args.vec_abtt

    rows = []
    for c in cases:
        q = c["query"]
        accept = c.get("accept") or [c["expected"]]
        t0 = time.perf_counter()
        if args.method == "vecshortlist":
            cand = LR.vector_shortlist(skills, q, args.k, args.model_dir, abtt_k=vab, ft=args.ft)
        elif args.method == "hybrid":
            cand = LR.hybrid_shortlist(skills, q, args.k, args.model_dir, abtt_k=vab, ft=args.ft)
        elif args.method == "shortlist":
            cand = LR.shortlist(skills, q, args.k)
        else:
            cand = list(skills)
        q_tok = L.count_tokens(q)
        cand_tok = sum(L.count_tokens(skills[n].get("route_text") or "") for n in cand)
        r = L.predict({"request": q}, LR.build_flat_question(skills, cand))
        ms = (time.perf_counter() - t0) * 1000
        a = r["answers"]["pick"]
        ranked = [k for k, _ in sorted(a["probabilities"].items(), key=lambda kv: -kv[1])]
        top1 = ranked[0]
        rows.append({
            "query": q, "expected": c["expected"], "accept": accept,
            "top1": top1, "top3": ranked[:3], "cand": cand,
            "conf": a["confidence"],
            "exact": top1 == c["expected"],
            "ok": top1 in accept,
            "ok3": any(x in ranked[:3] for x in accept),
            "recall": c["expected"] in cand,
            "q_tok": q_tok, "cand_tok": cand_tok,
            "laya_read_tok": q_tok + min(cand_tok, L.head_max_len),
            "ms": ms,
        })

    n = len(rows)
    exact = sum(r["exact"] for r in rows) / n
    ok = sum(r["ok"] for r in rows) / n
    ok3 = sum(r["ok3"] for r in rows) / n
    rec = sum(r["recall"] for r in rows) / n
    lat = sorted(r["ms"] for r in rows)[n // 2]
    mean_read = sum(r["laya_read_tok"] for r in rows) / n
    mean_cand = sum(r["cand_tok"] for r in rows) / n
    mean_q = sum(r["q_tok"] for r in rows) / n
    save = 1 - (mean_q + min(mean_cand, L.head_max_len)) / (ar_router_tokens + mean_q)

    # ---- 报告 ----
    L2 = []
    L2.append("# laya 路由审计报告（全程遵从 laya 判断）")
    L2.append("")
    L2.append(f"生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    mean_ncand = sum(len(r["cand"]) for r in rows) / n
    L2.append(f"用例 **{n}** 条 · 技能池 **{len(skills)}** 个 · 方法 **{args.method}"
              f"{'（K=' + str(args.k) + '）' if args.method != 'flat' else ''}** · "
              f"实际候选均 **{mean_ncand:.1f}** 个 · 每选项预算 ~{budget} token · head_max_len={L.head_max_len}")
    L2.append(f"模型：`{args.model_dir}`" + (f" ＋ 微调权重 `{args.ft}`" if args.ft else ""))
    if args.method in ("vecshortlist", "hybrid"):
        L2.append(f"向量召回去主成分 abtt_k={vab}" + ("（0=原始余弦，不做 ABTT）" if vab == 0 else ""))
    L2.append("")
    L2.append("> 说明：本审计**不修改、不覆盖 laya 的任何输出**，只记录它选了什么并打分；")
    L2.append("> `可接受集合` 仅用于少量天然歧义用例（如 md→docx 与写 Word），避免用单一答案误伤。")
    L2.append("")
    L2.append("## 一、路由准确率")
    L2.append("")
    L2.append("| 指标 | 数值 |")
    L2.append("|---|---|")
    L2.append(f"| top-1 完全命中 | **{exact:.1%}**（{sum(r['exact'] for r in rows)}/{n}） |")
    L2.append(f"| top-1 可接受 | **{ok:.1%}**（{sum(r['ok'] for r in rows)}/{n}） |")
    L2.append(f"| top-3 可接受 | **{ok3:.1%}**（{sum(r['ok3'] for r in rows)}/{n}） |")
    L2.append(f"| 粗筛召回 | {rec:.1%}（漏掉即不可救，链路上限） |")
    L2.append(f"| 判决延迟中位 | {lat:.0f} ms |")
    L2.append(f"| 随机基线（{len(skills)} 选 1） | {1/len(skills):.1%} |")
    L2.append("")
    L2.append("## 二、token 消耗")
    L2.append("")
    L2.append("| 项 | 数值 | 说明 |")
    L2.append("|---|---|---|")
    L2.append(f"| laya 每次判决读入 | **~{mean_q + min(mean_cand, L.head_max_len):.0f} token** | 查询 {mean_q:.0f} + 候选描述（截断至 {L.head_max_len}） |")
    L2.append(f"| 其中候选描述原始量 | {mean_cand:.0f} token | 未截断前的实际提供量 |")
    L2.append(f"| laya 生成 token | **0** | 非自回归，一次前向出全部候选概率，不逐 token 生成 |")
    L2.append(f"| 对照：AR 路由需读全部 {len(skills)} 条描述 | ~{ar_router_tokens} token | 这是本方案替代掉的成本 |")
    L2.append(f"| **路由阶段节省** | **~{save:.1%}** | 1 − laya读入 / AR读全量 |")
    L2.append("")
    L2.append("## 三、逐条结果")
    L2.append("")
    L2.append("| # | 请求 | 期望 | laya 实际选择 | conf | 判定 |")
    L2.append("|---|---|---|---|---|---|")
    for i, r in enumerate(rows, 1):
        mark = "✅" if r["exact"] else ("🔸" if r["ok"] else ("🔸top3" if r["ok3"] else "❌"))
        q = r["query"] if len(r["query"]) <= 34 else r["query"][:33] + "…"
        L2.append(f"| {i} | {q} | `{r['expected']}` | `{r['top1']}` | {r['conf']:.3f} | {mark} |")
    L2.append("")
    L2.append("## 四、误判明细（按需升级给自回归层）")
    L2.append("")
    bad = [r for r in rows if not r["ok"]]
    if not bad:
        L2.append("无（全部命中或落入可接受集合）。")
    else:
        L2.append("| 请求 | 期望 | laya 选择 | top-3 | conf | 粗筛是否漏 |")
        L2.append("|---|---|---|---|---|---|")
        for r in bad:
            L2.append(f"| {r['query']} | `{r['expected']}` | `{r['top1']}` | "
                      f"{', '.join('`'+x+'`' for x in r['top3'])} | {r['conf']:.3f} | "
                      f"{'❌漏' if not r['recall'] else '否'} |")
    L2.append("")
    L2.append("## 五、置信度阈值（该不该升级给 AR 层）")
    L2.append("")
    L2.append("| tau | 覆盖率 | 覆盖部分的 top-1 可接受率 |")
    L2.append("|---|---|---|")
    for tau in [0.10, 0.20, 0.30, 0.40, 0.50]:
        sel = [r for r in rows if r["conf"] >= tau]
        cov = len(sel) / n
        prec = (sum(r["ok"] for r in sel) / len(sel)) if sel else float("nan")
        L2.append(f"| {tau:.2f} | {cov:.0%} | {(prec if sel else 0):.0%} |")
    L2.append("")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L2), encoding="utf-8")
    print(f"审计完成 → {out}")
    print(f"top-1 完全命中 {exact:.1%} | 可接受 {ok:.1%} | top-3 {ok3:.1%} | 召回 {rec:.1%} | "
          f"laya读入 ~{mean_q + min(mean_cand, L.head_max_len):.0f} tok vs AR读全量 {ar_router_tokens} tok (省 {save:.1%})")


if __name__ == "__main__":
    main()
