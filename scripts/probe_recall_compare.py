"""对比「词法 vs mmBERT向量」两路召回在给定路由表上的 recall@K。"""
import os
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import laya_router as LR

ROOT = Path(__file__).resolve().parents[1]
table_path = ROOT / (sys.argv[1] if len(sys.argv) > 1 else "data/routing_table.json")
MODEL = os.path.join(os.path.expanduser("~"), "laya-test", "models", "multilingual", "multilingual")
table = json.loads(table_path.read_text(encoding="utf-8"))
skills = table["skills"]
cases = [json.loads(l) for l in (ROOT / "data" / "cases_audit.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
n = len(cases)
zh = sum(1 for s in skills.values() if any("\u4e00" <= c <= "\u9fff" for c in (s.get("route_text") or "")))
print(f"表={table_path.name}  技能={len(skills)}  中文route_text={zh}")
for K in (5, 10, 15):
    hl = hv = hu = 0
    for c in cases:
        lex = set(LR.shortlist(skills, c["query"], K))
        vec = set(LR.vector_shortlist(skills, c["query"], K, MODEL))
        hl += c["expected"] in lex
        hv += c["expected"] in vec
        hu += c["expected"] in (lex | vec)
    print(f"  K={K:>2}: 词法={hl/n:5.0%}  向量={hv/n:5.0%}  并集={hu/n:5.0%}")
