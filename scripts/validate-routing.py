#!/usr/bin/env python3
"""
Critical SkillGovern — Universal Routing Validation Script

路由验证脚本：把"硬编码的 Hermes 专属路由"升级为"人人可用的通用路由"。
自动检测任意平台的技能格式（Hermes / Claude Code / Codex / 通用 MD），
并用该平台对应的路由段落标准校验，输出健康报告。

Usage:
    python validate-routing.py --path ./skills [--format auto] [--strict] [--json]

--format: auto(默认，自动检测) | hermes | claude-code | codex | generic
--strict: 严格模式，把 🟡 警告也计为失败
--json:   输出 JSON 报告（便于 CI 集成）
"""

import argparse
import json
import os
import sys
import yaml
from pathlib import Path


# ============================================================
# 通用路由 Schema：每种平台对应一组"路由段落"检测标准
# 这就是"人人都可以用"的核心 —— 新增平台只需在下面加一条
# ============================================================
ROUTING_SCHEMAS = {
    # Hermes：YAML frontmatter + description 四层中文段落
    "hermes": {
        "desc": "YAML frontmatter + 四层路由描述",
        "required_sections": ["【触发场景】", "【输入特征】", "【输出目标】", "【不适用场景】"],
        "needs_frontmatter": True,
        "needs_tags": True,
        "desc_max_len": 500,
    },
    # Claude Code：一级标题 + When the user asks 英文描述
    "claude-code": {
        "desc": "Markdown 一级标题 + When 条件描述",
        "required_sections": ["When the user", "When the", "Use this skill"],
        "needs_frontmatter": False,
        "needs_tags": False,
        "desc_max_len": None,
    },
    # Codex：prompt 模板 + 系统指令式路由
    "codex": {
        "desc": "Codex prompt 模板（system/instruction 风格）",
        "required_sections": ["You are", "You are an", "Instructions", "When"],
        "needs_frontmatter": False,
        "needs_tags": False,
        "desc_max_len": None,
    },
    # 通用：宽松校验，任何格式只要有一级标题 + 一段描述即可
    "generic": {
        "desc": "任意 Markdown（宽松：仅校验标题+正文非空）",
        "required_sections": [],
        "needs_frontmatter": False,
        "needs_tags": False,
        "desc_max_len": None,
    },
}


def detect_format(content: str) -> str:
    """自动检测技能文件格式，返回 schema 名。"""
    # 1. 有 YAML frontmatter → hermes（或兼容 hermes 的生态）
    parts = content.split("---", 2)
    if len(parts) >= 3:
        try:
            fm = yaml.safe_load(parts[1])
            if isinstance(fm, dict) and fm.get("name"):
                return "hermes"
        except Exception:
            pass
    # 2. Claude Code 风格：When the user 开头
    if "When the user" in content or "When the" in content:
        return "claude-code"
    # 3. Codex 风格：You are / Instructions
    if "You are" in content or "Instructions" in content:
        return "codex"
    # 4. 兜底
    return "generic"


def extract_route_sections(content: str, fmt: str):
    """按格式抽取路由段落，返回 (frontmatter_dict, description_text)。"""
    schema = ROUTING_SCHEMAS[fmt]
    fm = {}
    desc = ""

    if schema["needs_frontmatter"]:
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                fm = yaml.safe_load(parts[1]) or {}
            except Exception:
                fm = {}
            desc = str(fm.get("description", "") or "")
    else:
        # 非 frontmatter 格式：取正文前 800 字符作为"描述"
        body = content
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                body = parts[2]
        desc = body.strip()[:800]

    return fm, desc


def validate_one(path: Path, fmt: str, content: str = None) -> dict:
    """校验单个技能文件，返回结果 dict。

    content 可选：由调用方传入已读取的内容时不再重复读文件（避免磁盘 IO 翻倍）。
    """
    if content is None:
        with open(path, encoding="utf-8") as f:
            content = f.read()

    schema = ROUTING_SCHEMAS[fmt]
    fm, desc = extract_route_sections(content, fmt)
    errors, warnings, notes = [], [], []

    # 1. 路由段落完整性
    missing = [s for s in schema["required_sections"] if s not in desc]
    if missing:
        errors.append(f"缺少路由段落: {', '.join(missing)}")

    # 2. frontmatter 校验（hermes 等）
    if schema["needs_frontmatter"]:
        if not fm:
            errors.append("frontmatter 解析失败或为空")
        else:
            if not fm.get("name"):
                errors.append("缺少 name 字段")
            if schema["needs_tags"] and not fm.get("tags"):
                errors.append("缺少 tags 字段")

    # 3. 描述长度
    if schema["desc_max_len"] and len(desc) > schema["desc_max_len"]:
        warnings.append(f"描述过长 ({len(desc)} > {schema['desc_max_len']} 字符)")

    # 4. 通用健康检查：中文触发词 / 负样本
    chinese_chars = sum(1 for c in desc if "\u4e00" <= c <= "\u9fff")
    if chinese_chars == 0 and len(desc.strip()) > 20 and fmt == "hermes":
        warnings.append("全英触发（hermes 生态建议中文路由）")
    if "【不适用场景】" in desc:
        neg = desc.split("【不适用场景】")[-1].split("\n")[0].strip()
        if len(neg) < 10:
            warnings.append(f"负样本过短: \"{neg[:30]}\"")

    # 5. 模板残余检测
    for residual in [".join", "kw[:", "+ ,", "', '"]:
        if residual in desc:
            errors.append(f"模板残余: \"{residual}\"")
            break

    return {
        "name": path.stem if fmt == "claude-code" else (fm.get("name") or path.stem),
        "path": str(path),
        "format": fmt,
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "notes": notes,
    }


def scan(base_path: Path, fmt: str) -> list:
    """扫描目录下所有技能文件。"""
    results = []
    # 辅助目录：不是技能本身，跳过（避免把 references/ 等误判为技能）
    SKIP_DIRS = {"references", "templates", "scripts", "assets", "examples",
                 "tests", "__pycache__", "node_modules", ".git"}
    for root, dirs, files in os.walk(base_path):
        # 跳过隐藏目录和辅助目录
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in SKIP_DIRS]
        for fn in files:
            if not fn.endswith((".md", ".markdown")):
                continue
            p = Path(root) / fn
            rel = os.path.relpath(root, base_path).replace(os.sep, "/")
            if any(part.startswith(".") for part in rel.split("/")):
                continue
            try:
                with open(p, encoding="utf-8") as f:
                    content = f.read()
                detected = detect_format(content) if fmt == "auto" else fmt
                results.append(validate_one(p, detected, content))
            except Exception as e:
                results.append({
                    "name": fn,
                    "path": str(p),
                    "format": fmt,
                    "ok": False,
                    "errors": [f"读取失败: {e}"],
                    "warnings": [],
                    "notes": [],
                })
    return results


def main():
    parser = argparse.ArgumentParser(description="通用技能路由验证")
    parser.add_argument("--path", required=True, help="技能目录路径")
    parser.add_argument("--format", default="auto",
                        choices=["auto", "hermes", "claude-code", "codex", "generic"],
                        help="技能格式（默认 auto 自动检测）")
    parser.add_argument("--strict", action="store_true", help="警告也计为失败")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    base = Path(args.path).expanduser()
    if not base.is_dir():
        print(f"错误: 目录不存在 {base}", file=sys.stderr)
        sys.exit(2)

    results = scan(base, args.format)
    total = len(results)
    passed = sum(1 for r in results if r["ok"])
    warned = sum(1 for r in results if r["ok"] and r["warnings"])
    failed = total - passed

    if args.json:
        print(json.dumps({
            "total": total, "passed": passed, "failed": failed,
            "results": results,
        }, ensure_ascii=False, indent=2))
    else:
        print(f"路由验证报告 (format={args.format})")
        print("=" * 56)
        print(f"总计 {total} | ✅ 通过 {passed} | ⚠️ 有警告 {warned} | ❌ 失败 {failed}")
        print()
        for r in results:
            status = "✅" if r["ok"] else "❌"
            print(f"  {status} [{r['format']:>11}] {r['path']}")
            for e in r["errors"]:
                print(f"         🔴 {e}")
            if args.strict:
                for w in r["warnings"]:
                    print(f"         🟡 {w}")

    sys.exit(1 if (failed > 0 or (args.strict and warned > 0)) else 0)


if __name__ == "__main__":
    main()
