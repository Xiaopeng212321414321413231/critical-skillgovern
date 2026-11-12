#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""技能审计的「人工裁决」层：把「修不了」和「该不该修」分开。

为什么需要它：
  batch-review 只会给「红/黄/绿」。但技能库里有一类技能——上游框架同步来的——
  它的红不是缺陷，是**所有权问题**：改了会与上游分叉，不改就一直红。
  这种必须由人裁决，工具不许替人做决定，也不许把它算进健康率里假装不存在。

三桶模型：
  ① 自建技能        → 计入健康率，该修就修
  ② 待人工裁决      → 单列成队列，每条附「改的代价 / 不改的代价」，等人点头
  ③ 已裁决·保持上游 → 移出失败统计，但保留记录（不是删除，随时可翻案）

用法：
  # 看报告（三桶 + 待裁决队列）
  python audit_triage.py --path "<skills>" --decisions data/audit_decisions.json --report out.md

  # 裁决一条（人做的动作）
  python audit_triage.py --decide writing-skills keep --reason "上游框架，本地化会分叉"
  python audit_triage.py --decide opencli-setup localize --reason "自建，缺四段是硬伤"

  # 只看还没裁决的
  python audit_triage.py --path "<skills>" --decisions data/audit_decisions.json --pending-only
"""
import argparse
import csv
import io
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import date

CJK = re.compile(r"[\u4e00-\u9fff]")
DECISIONS = {"keep": "保持上游（不计入失败）", "localize": "本地化（计入失败，待修）", "pending": "待裁决"}


def load_json(path):
    if path and os.path.exists(path):
        try:
            return json.load(io.open(path, encoding="utf-8"))
        except Exception:
            pass
    return {"version": 1, "skills": {}}


def save_json(path, data):
    d = os.path.dirname(os.path.abspath(path))
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with io.open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def read_frontmatter(skill_dir):
    """轻量读 frontmatter：只为判断「像自建还是像上游」，不追求完整解析。"""
    p = os.path.join(skill_dir, "SKILL.md")
    if not os.path.exists(p):
        return {}
    t = io.open(p, encoding="utf-8").read()
    if not t.startswith("---"):
        return {"body_mentions_upstream": False}
    parts = t.split("---", 2)
    if len(parts) < 3:
        return {"body_mentions_upstream": False}
    fm, body = parts[1], parts[2]
    desc = ""
    m = re.search(r"^description:\s*(.+?)(?=^\w|\Z)", fm, re.S | re.M)
    if m:
        desc = m.group(1)
    return {
        "agent_created": bool(re.search(r"^agent_created:\s*true", fm, re.M)),
        "has_cjk_desc": bool(CJK.search(desc)),
        "has_tags": bool(re.search(r"^tags:", fm, re.M)),
        # 上游框架的技能正文里普遍引用了自己的命名空间，如 "superpowers:test-driven-development"
        "body_mentions_upstream": bool(re.search(r"superpowers[:/]", body, re.I)),
    }


def guess_owner(fm, manifest):
    """自建判定：出现在上游清单，或正文引用上游命名空间 → 疑似上游。

    不再用「有没有中文/tags」判断：上游技能被本地化过一轮后也有 tags，
    这个启发式会把它们误判成自建（实测踩过）。
    """
    if fm.get("in_manifest"):
        return "upstream_suspect"
    if fm.get("body_mentions_upstream"):
        return "upstream_suspect"
    return "self"


def run_review(skills_dir, fmt):
    tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
    tmp.close()
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "batch-review.py")
    cmd = [sys.executable, script, "--path", skills_dir, "--format", fmt, "--csv", tmp.name]
    subprocess.run(cmd, capture_output=True, text=True)
    rows = []
    if os.path.exists(tmp.name):
        with io.open(tmp.name, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        os.unlink(tmp.name)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", help="技能目录")
    ap.add_argument("--decisions", default="data/audit_decisions.json")
    ap.add_argument("--upstream-manifest", default="data/upstream_manifest.json",
                    help="已知上游技能清单（人工维护，可随时增删）")
    ap.add_argument("--format", default="hermes")
    ap.add_argument("--report", help="输出 markdown 报告")
    ap.add_argument("--pending-only", action="store_true", help="只列待裁决项")
    ap.add_argument("--decide", nargs="+", metavar="技能 [keep|localize|pending]",
                    help="裁决：--decide <技能目录名> <结果>")
    ap.add_argument("--to", choices=list(DECISIONS), help="裁决结果")
    ap.add_argument("--reason", default="", help="裁决理由")
    args = ap.parse_args()

    data = load_json(args.decisions)

    # 裁决模式：只落盘，不出报告
    if args.decide:
        name = args.decide[0]
        decision = args.to or (args.decide[1] if len(args.decide) > 1 else None)
        if decision not in DECISIONS:
            raise SystemExit("裁决结果必须是 keep / localize / pending，例如：--decide %s keep" % name)
        data["skills"][name] = {
            "decision": decision,
            "reason": args.reason,
            "at": date.today().isoformat(),
        }
        save_json(args.decisions, data)
        print("已记录：%s → %s（%s）" % (name, DECISIONS[decision], args.reason or "无理由"))
        return

    if not args.path:
        raise SystemExit("需要 --path（或用 --decide 记录裁决）")

    rows = run_review(args.path, args.format)
    byname = {}
    for r in rows:
        byname.setdefault(r["Name"], []).append(r)

    # 把健康技能也补进来（CSV 只记有问题的）
    scanned = []
    for d in sorted(os.listdir(args.path)):
        p = os.path.join(args.path, d)
        if os.path.isdir(p) and os.path.exists(os.path.join(p, "SKILL.md")):
            scanned.append(d)

    manifest_data = load_json(args.upstream_manifest)
    manifest = set()
    if isinstance(manifest_data, dict):
        manifest = set(manifest_data.get("skills", []))
    elif isinstance(manifest_data, list):
        manifest = set(manifest_data)

    buckets = {"ok": [], "self_fix": [], "pending": [], "kept": [], "localize_todo": []}
    for d in scanned:
        issues = byname.get(d, [])
        fm = read_frontmatter(os.path.join(args.path, d))
        fm["in_manifest"] = d in manifest
        owner = guess_owner(fm, manifest)
        rec = data["skills"].get(d, {})
        dec = rec.get("decision")
        item = {"dir": d, "owner": owner, "issues": issues,
                "critical": any("🔴" in i["Severity"] for i in issues),
                "reason": rec.get("reason", "")}
        if not issues:
            buckets["ok"].append(item)
        elif dec == "keep":
            buckets["kept"].append(item)
        elif dec == "localize":
            buckets["localize_todo"].append(item)
        elif dec == "pending":
            buckets["pending"].append(item)
        elif owner == "upstream_suspect":
            buckets["pending"].append(item)       # 没裁决 + 疑似上游 → 进队列，不判红
        else:
            buckets["self_fix"].append(item)      # 没裁决 + 自建 → 该修

    total = len(scanned)
    judged = len(buckets["ok"]) + len(buckets["self_fix"]) + len(buckets["localize_todo"])
    health = len(buckets["ok"]) * 100.0 / max(judged, 1)

    lines = []
    def out(s=""):
        lines.append(s)
        print(s)

    out("")
    out("=== 技能审计 · 三桶报告 ===")
    out("扫描 %d 个技能 ｜ 计入统计 %d 个（排除「保持上游」%d 个）"
        % (total, judged, len(buckets["kept"])))
    out("健康率：%d/%d = %.0f%%" % (len(buckets["ok"]), judged, health))
    out("  ① 待修（自建）      %2d" % len(buckets["self_fix"]))
    out("  ② 待人工裁决        %2d" % len(buckets["pending"]))
    out("  ③ 已裁决·保持上游    %2d" % len(buckets["kept"]))
    out("  ④ 已裁决·待本地化    %2d" % len(buckets["localize_todo"]))

    def dump(title, items, hint=""):
        if not items:
            return
        out("")
        out("--- %s（%d）---" % (title, len(items)))
        if hint:
            out(hint)
        for it in items:
            sev = "🔴" if it["critical"] else "🟡"
            issues = "；".join(sorted({i["Issue"] for i in it["issues"]}))
            out("  %s %-34s %s%s" % (sev, it["dir"], issues,
                                     ("  ← " + it["reason"]) if it["reason"] else ""))

    dump("① 待修（自建技能，无需裁决，直接修）", buckets["self_fix"])
    dump("② 待人工裁决", buckets["pending"],
         "  这些疑似上游同步来的技能。改 = 与上游分叉，要自己维护；不改 = 中文查询召回不到它。")
    dump("③ 已裁决·保持上游（不计入失败）", buckets["kept"])
    dump("④ 已裁决·待本地化（仍计入失败）", buckets["localize_todo"])

    if args.pending_only:
        pending = [it["dir"] for it in buckets["pending"]]
        print("\n待裁决清单：" + ("、".join(pending) if pending else "无"))

    if args.report:
        head = ["# 技能审计 · 三桶报告", "",
                "| 桶 | 数量 | 说明 |", "|---|---|---|",
                "| ① 待修（自建） | %d | 计入健康率，直接修 |" % len(buckets["self_fix"]),
                "| ② 待人工裁决 | %d | 疑似上游，等人点头 |" % len(buckets["pending"]),
                "| ③ 保持上游 | %d | 已裁决，不计入失败 |" % len(buckets["kept"]),
                "| ④ 待本地化 | %d | 已裁决要改，仍计失败 |" % len(buckets["localize_todo"]),
                "", "**健康率**：%d/%d = %.0f%%（分母不含「保持上游」）"
                % (len(buckets["ok"]), judged, health), ""]
        for title, items in [("① 待修", buckets["self_fix"]), ("② 待人工裁决", buckets["pending"]),
                             ("③ 保持上游", buckets["kept"]), ("④ 待本地化", buckets["localize_todo"])]:
            if not items:
                continue
            head += ["## " + title, "", "| 技能 | 问题 | 裁决理由 |", "|---|---|---|"]
            for it in items:
                head.append("| %s | %s | %s |" % (
                    it["dir"], "；".join(sorted({i["Issue"] for i in it["issues"]})),
                    it["reason"] or "—"))
            head.append("")
        io.open(args.report, "w", encoding="utf-8").write("\n".join(head) + "\n")
        print("\n报告已写入：" + args.report)


if __name__ == "__main__":
    main()
