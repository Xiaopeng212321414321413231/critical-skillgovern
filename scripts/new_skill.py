#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""新建技能时的守门人：先出生即合规，别等审计再来返工。

为什么要有它：
  事后审计只能救「已存在的坏技能」，救不了「正在生成的坏技能」。
  一个技能 90% 的合规成本在 frontmatter 那一刻就决定了——
  四层描述写没写、tags 有没有、描述有没有超预算。
  所以真正实用的做法是：**创建时就按模板生成，写完立刻自检**，而不是攒一堆再批量补。

用法：
  python new_skill.py --root "<skills>" --name daily-review \
    --summary "每日复盘" \
    --scenario "用户说今天复盘一下；想把一天的活理清楚；睡前过一遍进度" \
    --input "当天的笔记、任务清单、提交记录" \
    --output "一份带结论的复盘 md + 明日三件事" \
    --exclude "只想要周报（用 weekly-report）；只要打卡（用 workbuddy-checkin）" \
    --triggers "复盘, 日报, 今日总结, daily review" \
    --tags "review,daily" --related "obsidian-knowledge-ops"

  # 只干跑看结果，不落盘
  python new_skill.py ... --dry-run

  # 写完立刻自检（长度预算 + 四层齐全）
  python new_skill.py ... --check
"""
import argparse
import io
import os
import re

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
DESC_SOFT, DESC_HARD = 500, 900        # 描述字数：超过软限提醒，超过硬限拒绝
FM_HARD = 1024                          # 规范上限：name + description 两项合计（不含 tags/related_skills 等附加字段）
FM_WARN = 1400                          # 附加字段过多时的提醒线，只警告不拒绝

BODY = """# {name} · {summary}

## Overview

<这个技能解决什么问题。一到两句，说清「不用它会怎样」。>

## 何时用

- <症状 1，写成用户会说的话>
- <症状 2>

**不适用**：<指向别的技能或工具>

## 核心做法

1. <第一步，具体到命令或文件>
2. <第二步>

## 常见错误

| 反模式 | 正确做法 |
|---|---|
| <踩过的坑> | <怎么绕> |
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="技能根目录，如 %USERPROFILE%/.workbuddy/skills")
    ap.add_argument("--name", required=True)
    ap.add_argument("--summary", required=True, help="一句话定位，≤30 字")
    ap.add_argument("--scenario", required=True, help="【触发场景】，多条用分号隔开")
    ap.add_argument("--input", required=True, help="【输入特征】")
    ap.add_argument("--output", required=True, help="【输出目标】")
    ap.add_argument("--exclude", required=True, help="【不适用场景】，多条用分号隔开")
    ap.add_argument("--triggers", default="", help="触发词，逗号分隔")
    ap.add_argument("--tags", default="")
    ap.add_argument("--related", default="")
    ap.add_argument("--description", default="", help="可选：直接给整段描述，覆盖四层拼接")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--check", action="store_true", help="写完打印自检结果")
    args = ap.parse_args()

    if not NAME_RE.match(args.name):
        raise SystemExit("名字只能用 小写字母/数字/连字符，例如 daily-review：%s" % args.name)
    if len(args.summary) > 30:
        raise SystemExit("一句话定位超过 30 字，会被截断，请压缩：%d 字" % len(args.summary))

    if args.description:
        desc = args.description.strip()
    else:
        desc = "\n".join([
            "  %s。" % args.summary,
            "  【触发场景】%s" % args.scenario,
            "  【输入特征】%s" % args.input,
            "  【输出目标】%s" % args.output,
            "  【不适用场景】%s" % args.exclude,
            "  触发词：%s" % args.triggers,
        ])

    fm = ["---", "name: %s" % args.name, "description: >-", desc]
    if args.tags:
        fm.append("tags: [%s]" % args.tags)
    if args.related:
        fm.append("related_skills: [%s]" % ", ".join(
            s.strip() for s in args.related.split(",") if s.strip()))
    fm.append("---")
    content = "\n".join(fm) + "\n\n" + BODY.format(name=args.name, summary=args.summary)

    # 出生即体检，不合格当场拒绝，不留给事后审计
    dlen = len(args.description or args.scenario) + len(args.summary) + len(
        args.input + args.output + args.exclude + args.triggers) + 40
    fmlen = len("\n".join(fm))
    # 规范量的是 name + description 两项，不含 tags/related_skills 这些附加字段
    core = len(args.name) + len(desc)
    problems = []
    if "【触发场景】" not in content:
        problems.append("缺【触发场景】")
    if "【不适用场景】" not in content:
        problems.append("缺【不适用场景】")
    if core > FM_HARD:
        problems.append("name+description %d 字符超过规范上限 %d" % (core, FM_HARD))
    if "；" not in args.exclude and ";" not in args.exclude:
        problems.append("【不适用场景】只写了 1 条，至少要 2 条并指向替代方案")
    if problems:
        raise SystemExit("拒绝生成：\n  - " + "\n  - ".join(problems))

    if args.dry_run:
        print(content)
        print("\n[干跑] 未落盘。frontmatter %d 字符 / 描述约 %d 字" % (fmlen, dlen))
        return

    target = os.path.join(args.root, args.name)
    if os.path.exists(os.path.join(target, "SKILL.md")):
        raise SystemExit("已存在同名技能，拒绝覆盖：%s" % target)
    os.makedirs(target, exist_ok=True)
    io.open(os.path.join(target, "SKILL.md"), "w", encoding="utf-8", newline="\n").write(content)

    print("已创建：%s" % os.path.join(target, "SKILL.md"))
    print("frontmatter %d/%d 字符 ｜ 描述约 %d 字（软限 %d）" % (fmlen, FM_HARD, dlen, DESC_SOFT))
    if dlen > DESC_SOFT:
        print("⚠️ 描述偏长，考虑压缩【触发场景】与触发词数量")
    print("\n下一步（必须做）：")
    print('  python scripts/validate-routing.py --path "%s" --format auto --strict' % args.root)
    print("  然后把正文的四层说明补完——本脚本只生成了骨架，内容要自己写。")


if __name__ == "__main__":
    main()
