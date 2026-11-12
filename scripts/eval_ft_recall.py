#!/usr/bin/env python3
"""评估微调后的 mmBERT 检索编码器：原始 vs 微调（raw / ABTT）在 35 条留出用例上的 recall。

用法：
  python eval_ft_recall.py [--ckpt data/finetuned/mmbert-retrieval.pt] [--out data/ft-recall.md]
"""
import argparse
import json
import sys
import time
from pathlib import Path

import torch
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).resolve().parent))
from finetune_mmbert import ROOT, build_encoder, tokenizer, embed  # noqa: E402

KS = (1, 3, 5, 10, 15)


@torch.no_grad()
def recall(model, tok, docs, cases, names, abtt_k=5):
    model.eval()
    D = F.normalize(embed(model, tok, docs), dim=-1)
    Q = F.normalize(embed(model, tok, [c["query"] for c in cases]), dim=-1)
    out = {}
    for label, cap in (("raw", None), (f"abtt{abtt_k}", abtt_k)):
        if cap is None:
            DD, QQ = D, Q
        else:
            mu = D.mean(0, keepdim=True)
            Dc, Qc = D - mu, Q - mu
            _, _, V = torch.pca_lowrank(Dc, q=min(16, Dc.shape[0] - 1))
            Vr = V[:, :cap]
            DD = F.normalize(Dc - (Dc @ Vr) @ Vr.T, dim=-1)
            QQ = F.normalize(Qc - (Qc @ Vr) @ Vr.T, dim=-1)
        sims = QQ @ DD.T
        for K in KS:
            hit = sum(c["expected"] in [names[j] for j in sims[i].topk(K).indices.tolist()]
                      for i, c in enumerate(cases))
            out[f"{label}@{K}"] = hit / len(cases)
    return out


def row(label, r):
    return "| " + label + " | " + " | ".join(f"{r.get(f'{p}@{K}', 0):.0%}" for p, K in
           [("raw", 1), ("raw", 3), ("raw", 10), ("abtt5", 1), ("abtt5", 3), ("abtt5", 10)] ) + " |"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", default="data/routing_table.json")
    ap.add_argument("--cases", default="data/cases_audit.jsonl")
    ap.add_argument("--ckpt", nargs="*", default=["data/finetuned/mmbert-retrieval.pt",
                                                  "data/finetuned/mmbert-retrieval-v2.pt"])
    ap.add_argument("--out", default="data/ft-recall.md")
    args = ap.parse_args()

    table = json.loads((ROOT / args.table).read_text(encoding="utf-8"))
    skills = table["skills"]
    names = list(skills)
    docs = [skills[n].get("route_text") or n for n in names]
    cases = [json.loads(l) for l in (ROOT / args.cases).read_text(encoding="utf-8").splitlines() if l.strip()]
    tok = tokenizer()

    t0 = time.time()
    model = build_encoder()
    base = recall(model, tok, docs, cases, names)
    print(f"baseline: {base}  ({time.time()-t0:.0f}s)")

    ft_rows = []
    for ck_name in args.ckpt:
        ck = ROOT / ck_name
        if not ck.exists():
            print(f"⚠️ 未找到微调权重 {ck}")
            continue
        obj = torch.load(ck, weights_only=False)
        model.load_state_dict(obj["state"], strict=False)
        r = recall(model, tok, docs, cases, names)
        print(f"{ck.name}: {r}")
        ft_rows.append((ck.name, r))

    n_pairs = len((ROOT / "data" / "ft_pairs.jsonl").read_text(encoding="utf-8").splitlines())
    md = [
        "# mmBERT 检索编码器：原始 vs 微调（35 条留出用例）",
        "",
        f"生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')} · 负样本池 {len(docs)} 篇 · "
        f"训练对 {n_pairs} 条",
        "",
        "| 编码器 | raw@1 | raw@3 | raw@10 | ABTT5@1 | ABTT5@3 | ABTT5@10 |",
        "|---|---|---|---|---|---|---|",
        row("原始 mmBERT", base),
    ]
    for name, r in ft_rows:
        md.append(row(f"微调 {name}", r))
    md.append("")
    (ROOT / args.out).write_text("\n".join(md), encoding="utf-8")
    print(f"→ {ROOT / args.out}")


if __name__ == "__main__":
    main()
