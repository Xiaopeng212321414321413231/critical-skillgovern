#!/usr/bin/env python3
"""给 laya 检查点里的 mmBERT 编码器做**检索式对比学习微调**（全库负样本）。

背景（见 docs/laya-routing.md §4.6）：mmBERT-base 是被 laya 的 masked-choice 头微调过的
masked-LM，直接 mean-pool 当句向量检索严重各向异性（recall@10 仅 34%），ABTT 只能补到 80%。
本脚本用「68 个技能文档当负样本」的 cross-entropy 目标把它训成**检索对齐**的编码器，
期望在留出的 35 条审计用例上把 recall@10 顶上 90%+。

训练目标：对每个 query，与**全部 68 个技能文档**算余弦相似度，softmax 后取正确文档的 NLL。
    sim = normalize(q) @ normalize(docs).T / tau
    loss = CE(sim, target_index)

为在 CPU 上可跑：冻结前 16 层，只训最后 6 层 + final_norm。

用法：
  python finetune_mmbert.py [--epochs 3] [--batch 32] [--lr 2e-5] [--out data/finetuned/mmbert-retrieval.pt]
"""
import argparse
import json
import os
import time
from pathlib import Path

import torch
import torch.nn.functional as F
from safetensors.torch import load_file
from tokenizers import Tokenizer
from transformers import ModernBertConfig, ModernBertModel

ROOT = Path(__file__).resolve().parents[1]
BASE = os.path.join(os.path.expanduser("~"), "laya-test", "models", "multilingual", "multilingual")
UNFREEZE_FROM = 16          # 冻结 layers.0..15，训 layers.16..21 + final_norm
MAX_LEN = 64
TAU = 0.05


def build_encoder():
    model = ModernBertModel(ModernBertConfig.from_pretrained(str(Path(BASE) / "encoder")))
    sd = load_file(str(Path(BASE) / "model.safetensors"))
    model.load_state_dict({k[8:]: v for k, v in sd.items() if k.startswith("encoder.")}, strict=False)
    return model


def tokenizer():
    return Tokenizer.from_file(str(Path(BASE) / "tokenizer" / "tokenizer.json"))


def batch_encode(tok, texts):
    rows, masks = [], []
    for t in texts:
        ids = tok.encode(t).ids[:MAX_LEN] or [0]
        rows.append(ids)
    L = max(len(r) for r in rows)
    for r in rows:
        masks.append([1] * len(r) + [0] * (L - len(r)))
        r += [0] * (L - len(r))
    return torch.tensor(rows), torch.tensor(masks)


def mean_pool(h, am):
    """注意力掩码均值池化。h:(N,L,H) am:(N,L) -> (N,H)。

    注意：分母必须保持 2 维 (N,1)。若用 mask.unsqueeze(-1).sum(1,keepdim=True)
    会得到 (N,1,1)，与 (N,H) 相除时右对齐广播会错误地膨胀成 (N,N,H)。
    """
    m = am.unsqueeze(-1).float()                 # (N,L,1)
    return (h * m).sum(1) / am.sum(1, keepdim=True).float()   # (N,H)/(N,1)


def embed(model, tok, texts):
    x, am = batch_encode(tok, texts)
    h = model(input_ids=x, attention_mask=am).last_hidden_state
    return mean_pool(h, am)


@torch.no_grad()
def evaluate(model, tok, docs, cases, names, abtt_k=5):
    model.eval()
    D = F.normalize(embed(model, tok, docs), dim=-1)
    Q = F.normalize(embed(model, tok, [c["query"] for c in cases]), dim=-1)
    res = {}
    for label, cap in (("raw", None), ("abtt", abtt_k)):
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
        for K in (5, 10, 15):
            hit = sum(c["expected"] in [names[j] for j in sims[i].topk(K).indices.tolist()]
                      for i, c in enumerate(cases))
            res[f"{label}@{K}"] = hit / len(cases)
    model.train()
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", default="data/routing_table.json")
    ap.add_argument("--pairs", default="data/ft_pairs.jsonl")
    ap.add_argument("--cases", default="data/cases_audit.jsonl")
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--out", default="data/finetuned/mmbert-retrieval.pt")
    args = ap.parse_args()

    torch.set_num_threads(args.threads)
    table = json.loads((ROOT / args.table).read_text(encoding="utf-8"))
    skills = table["skills"]
    names = list(skills)
    docs = [skills[n].get("route_text") or n for n in names]
    idx = {n: i for i, n in enumerate(names)}
    pairs = [json.loads(l) for l in (ROOT / args.pairs).read_text(encoding="utf-8").splitlines() if l.strip()]
    cases = [json.loads(l) for l in (ROOT / args.cases).read_text(encoding="utf-8").splitlines() if l.strip()]

    t0 = time.time()
    model = build_encoder()
    for p in model.parameters():
        p.requires_grad = False
    trainable = []
    for n, p in model.named_parameters():
        if n.startswith("final_norm") or any(n.startswith(f"layers.{i}.") for i in range(UNFREEZE_FROM, 22)):
            p.requires_grad = True
            trainable.append(n)
    print(f"编码器加载 {time.time()-t0:.0f}s | 冻结 layers.0..{UNFREEZE_FROM-1}，"
          f"训练 {len(trainable)} 个张量 | 训练对 {len(pairs)} | 负样本 {len(docs)}")
    print("baseline(未微调):", evaluate(model, tokenizer(), docs, cases, names))
    model.train()
    tok = tokenizer()

    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=args.lr, weight_decay=0.01)
    doc_x, doc_m = batch_encode(tok, docs)
    n_step = (len(pairs) + args.batch - 1) // args.batch

    for ep in range(1, args.epochs + 1):
        perm = torch.randperm(len(pairs)).tolist()
        tot = 0.0
        te = time.time()
        for s in range(n_step):
            chunk = [pairs[i] for i in perm[s * args.batch:(s + 1) * args.batch]]
            qx, qm = batch_encode(tok, [c["query"] for c in chunk])
            target = torch.tensor([idx[c["skill"]] for c in chunk])
            # docs 每步都重算（负样本也要过梯度）
            dh = model(input_ids=doc_x, attention_mask=doc_m).last_hidden_state
            Dv = mean_pool(dh, doc_m)
            qh = model(input_ids=qx, attention_mask=qm).last_hidden_state
            Qv = mean_pool(qh, qm)
            sims = F.normalize(Qv, dim=-1) @ F.normalize(Dv, dim=-1).T / TAU
            loss = F.cross_entropy(sims, target)
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], 1.0)
            opt.step()
            tot += loss.item()
        print(f"[epoch {ep}/{args.epochs}] loss={tot/n_step:.4f}  {time.time()-te:.0f}s  "
              f"eval={evaluate(model, tok, docs, cases, names)}")

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    state = {n: p.detach().clone() for n, p in model.named_parameters() if p.requires_grad}
    torch.save({"state": state, "meta": {
        "base": BASE, "unfreeze_from": UNFREEZE_FROM, "max_len": MAX_LEN, "tau": TAU,
        "epochs": args.epochs, "lr": args.lr, "n_pairs": len(pairs),
    }}, out)
    print(f"已保存微调权重 {len(state)} 个张量（{out.stat().st_size/1e6:.0f} MB）→ {out}")


if __name__ == "__main__":
    main()
