#!/usr/bin/env python3
"""级联评估：laya 单独 vs laya + L2(AR) 协同。

流程（两阶段，中间由 L2 人工/模型填 picks）：
  阶段 A  --dump    ：跑 laya（词法 shortlist），对每条用例落 conf / top-1 / 候选集
  阶段 B  --report  ：读取 picks（conf < tau 的用例由 L2 从**同一候选集**里重选），出对比报告

为何分两段：L2 的"接管"必须只看 laya 看到的同一候选集（query + 候选 route_text），
不能偷看期望答案。picks 由 L2 依据 dump 里的候选信息填写。

用法：
  python cascade_eval.py --dump
  python cascade_eval.py --report --picks data/cascade_picks.json
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import laya_router as LR  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def cmd_dump(args):
    table = json.loads((ROOT / args.table).read_text(encoding="utf-8"))
    skills = table["skills"]
    cases = [json.loads(l) for l in (ROOT / args.cases).read_text(encoding="utf-8").splitlines() if l.strip()]
    L = LR.Laya(args.model_dir, args.threads)
    out = []
    for i, c in enumerate(cases):
        q = c["query"]
        if args.method == "vecshortlist":
            cand = LR.vector_shortlist(skills, q, args.k, model_dir=args.model_dir,
                                       abtt_k=args.vec_abtt, ft=args.ft)
        elif args.method == "hybrid":
            cand = LR.hybrid_shortlist(skills, q, args.k, model_dir=args.model_dir,
                                       abtt_k=args.vec_abtt, ft=args.ft)
        else:
            cand = LR.shortlist(skills, q, args.k)
        r = L.predict({"request": q}, LR.build_flat_question(skills, cand))
        a = r["answers"]["pick"]
        ranked = [k for k, _ in sorted(a["probabilities"].items(), key=lambda kv: -kv[1])]
        out.append({
            "i": i, "query": q, "expected": c["expected"],
            "accept": c.get("accept") or [c["expected"]],
            "conf": round(a["confidence"], 4), "laya_top1": ranked[0],
            "laya_top3": ranked[:3], "recall_ok": c["expected"] in cand,
            "cand": [{"name": n, "route_text": skills[n].get("route_text") or ""} for n in cand],
        })
        print(f"  {i:>2} conf={a['confidence']:.3f} {'✓' if ranked[0] in (c.get('accept') or [c['expected']]) else '✗'} exp={c['expected']}")
    p = ROOT / args.dump
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"落盘 {len(out)} 条 → {p}")


def cmd_report(args):
    dump = json.loads((ROOT / args.dump).read_text(encoding="utf-8"))
    tbl = json.loads((ROOT / args.table).read_text(encoding="utf-8"))
    skills = tbl["skills"]
    pool = tbl["count"]
    if args.l2 == "retriever":
        # 客观 L2：用（可微调的）向量检索器在**全库**上重选 top-1，无人工介入 → 无循环论证偏置
        picks = {}
        for d in dump:
            if d["conf"] < args.threshold:
                picks[str(d["i"])] = LR.vector_shortlist(skills, d["query"], 1,
                                                         model_dir=args.model_dir,
                                                         abtt_k=args.vec_abtt, ft=args.ft)[0]
    else:
        picks = json.loads((ROOT / args.picks).read_text(encoding="utf-8")) if (ROOT / args.picks).exists() else {}
    n = len(dump)
    tau = args.threshold

    solo = sum(d["laya_top1"] in d["accept"] for d in dump)
    solo3 = sum(any(x in d["accept"] for x in d["laya_top3"]) for d in dump)

    escalated = [d for d in dump if d["conf"] < tau]
    kept = [d for d in dump if d["conf"] >= tau]
    casc = sum(d["laya_top1"] in d["accept"] for d in kept)
    covered, miss_pick, no_cand = 0, [], []
    for d in escalated:
        pick = picks.get(str(d["i"]))
        if pick is None:
            no_cand.append(d["i"])
            continue
        if pick in d["accept"]:
            covered += 1
        else:
            miss_pick.append((d["i"], d["query"], d["expected"], pick))
        if pick not in [c["name"] for c in d["cand"]]:
            print(f"  ⚠️ pick {pick} 不在用例 {d['i']} 的候选集里")

    casc_total = casc + covered
    lines = [
        "# 级联评估：laya 单独 vs laya + L2(AR) 协同",
        "",
        f"生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"用例 **{n}** 条 · 技能池 **{pool}** 个 · "
        f"召回方法 {args.method} K={args.k} · 升级阈值 τ={tau} · L2={args.l2}"
        + (f"（ft={args.ft}）" if args.ft else ""),
        "",
        "> 口径：`laya 单独` = 全部用例都信 laya 的 top-1；`协同` = conf ≥ τ 信 laya，conf < τ 由 L2 从**同一候选集**重选。",
        "",
        "## 一、准确率对比",
        "",
        "| 方案 | top-1 可接受 | 提升 |",
        "|---|---|---|",
        f"| laya 单独 | **{solo/n:.1%}**（{solo}/{n}） | — |",
        f"| **协同（laya + L2，τ={tau}）** | **{casc_total/n:.1%}**（{casc_total}/{n}） | "
        f"+{casc_total-solo} 条（+{(casc_total-solo)/n:.1%}） |",
        "",
        f"- laya 单独 top-3 可接受：{solo3/n:.1%}（{solo3}/{n}）——协同的天花板",
        f"- 升级流量：{len(escalated)}/{n} = {len(escalated)/n:.0%}；其中 laya 原本已对 {sum(d['laya_top1'] in d['accept'] for d in escalated)} 条，"
        f"L2 救回 {covered} 条",
        f"- 未升级部分 laya 准确率：{casc/len(kept) if kept else 0:.1%}（{casc}/{len(kept)}）",
        "",
    ]
    if no_cand:
        lines += [f"⚠️ 尚未提供 picks 的用例：{no_cand}", ""]
    if miss_pick:
        lines += ["## 二、L2 仍选错的用例", "", "| # | 请求 | 期望 | L2 选择 |", "|---|---|---|---|"]
        lines += [f"| {i} | {q} | `{e}` | `{p}` |" for i, q, e, p in miss_pick]
        lines += [""]
    lines += ["## 三、升级用例明细", "", "| # | 请求 | laya conf | laya 选 | L2 选 | 期望 |", "|---|---|---|---|---|---|"]
    for d in escalated:
        pick = picks.get(str(d["i"]), "—")
        lines.append(f"| {d['i']} | {d['query']} | {d['conf']:.3f} | `{d['laya_top1']}` | `{pick}` | `{d['expected']}` |")
    lines.append("")
    p = ROOT / args.out
    p.write_text("\n".join(lines), encoding="utf-8")
    print(f"→ {p}")
    print(f"laya 单独 {solo/n:.1%} | 协同 {casc_total/n:.1%} | 升级 {len(escalated)} 条救回 {covered} 条")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", default="data/routing_table.json")
    ap.add_argument("--cases", default="data/cases_audit.jsonl")
    ap.add_argument("--model-dir", default=LR.MULTILINGUAL_MODEL)
    ap.add_argument("--dump", default="data/cascade_dump.json")
    ap.add_argument("--picks", default="data/cascade_picks.json")
    ap.add_argument("--out", default="data/route-audit-cascade.md")
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--method", choices=["shortlist", "vecshortlist", "hybrid"], default="shortlist",
                    help="前端召回方法（laya 看到的候选集来源）")
    ap.add_argument("--threshold", type=float, default=0.40)
    ap.add_argument("--l2", choices=["picks", "retriever"], default="picks",
                    help="L2 定义：picks=人工/AR 依据候选集重选；retriever=向量检索器全库重选（客观）")
    ap.add_argument("--ft", default=None, help="retriever 模式下使用的微调向量权重")
    ap.add_argument("--vec-abtt", type=int, default=LR.VEC_ABTT_K,
                    help="retriever 模式向量召回去主成分数（top-1 场景带 ABTT 更准）")
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--dump-only", action="store_true")
    ap.add_argument("--report-only", action="store_true")
    args = ap.parse_args()
    if not args.report_only:
        cmd_dump(args)
    if not args.dump_only:
        cmd_report(args)


if __name__ == "__main__":
    main()
