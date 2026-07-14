# 🔍 Critical SkillGovern

> **批判式技能治理框架** — 一套跨平台、经验证的技能质量审查方法论。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platforms](https://img.shields.io/badge/Platform-Hermes%20%7C%20Claude%20Code%20%7C%20Codex-blue)]()

**护你的技能库不乱长，让每个技能都精准命中用户意图。**

---

## 这解决了什么问题？

当技能库超过 **10 个** 时，AI 模型在众多技能中精准匹配用户意图的难度指数级上升。这不是模型能力不足，而是技能描述没有给模型足够的决策信号。

| 技能数 | 路由问题 | 影响 |
|--------|----------|------|
| 1-10 | 几乎无 | 模型能轻松区分 |
| 10-50 | 误触发开始出现 | 技能描述不够准确 |
| 50-100 | 频繁误触发 | 需要结构化路由 |
| 100+ | 系统不可靠 | 必须治理 |

**Critical SkillGovern** 提供了一套实战验证的流程，让你的技能库在任何规模下都保持可靠。

---

## 核心流程

```
路由诊断 → 批判性质询 → 用户审批 → 执行修复 → 二次验证 → 最终报告
```

### 六阶段审查流水线

| 阶段 | 做什么 | 产出 |
|------|--------|------|
| 1️⃣ **路由诊断** | 扫描技能描述，发现模板残余/中英混合/弱负样本 | 问题清单 |
| 2️⃣ **批判性质询** | 5W1H 质问 + 逆向思维 + 假设挖掘 | 深度分析 |
| 3️⃣ **用户审批** | 按严重度分级，让用户决策 | 批准/拒绝清单 |
| 4️⃣ **执行修复** | 只改路由不改本体，批量或单技能 | 修复后的文件 |
| 5️⃣ **二次验证** | 重新检查修复是否彻底 | 验证报告 |
| 6️⃣ **最终报告** | 输出审计结果 | 完整报告 |

---

## 支持的平台

| 平台 | 技能格式 | 适配指南 |
|------|----------|----------|
| 🏛️ **Hermes Agent** | SKILL.md (YAML frontmatter + Markdown) | [adapters/hermes.md](adapters/hermes.md) |
| 🌀 **Claude Code** | .claude/skills/*.md (Markdown) | [adapters/claude-code.md](adapters/claude-code.md) |
| 🤖 **Codex CLI** | Prompt 模板 / Shell 包装器 | [adapters/codex.md](adapters/codex.md) |

---

## 快速开始

### 1. 审查单个技能

```bash
# 查看技能文件
cat ~/.hermes/skills/your-skill/SKILL.md

# 对照检查清单检查
# - 是否有四层描述（触发场景/输入特征/输出目标/不适用场景）？
# - 是否是中文？
# - 负样本是否指向替代技能？
```

### 2. 批量审查

```bash
# 安装依赖
pip install pyyaml

# 跑批量审查
python scripts/batch-review.py --path ~/.hermes/skills --format hermes
```

### 3. 生成报告

```bash
python scripts/batch-review.py --path ~/.hermes/skills --format hermes --csv report.csv
```

---

## 目录结构

```
critical-skillgovern/
├── README.md                      # 本项目概述
├── LICENSE                        # MIT 许可证
├── docs/
│   ├── methodology.md             # 核心方法论（六阶段流水线）
│   └── routing-optimization.md    # 路由优化指南
├── adapters/
│   ├── hermes.md                  # Hermes Agent 适配
│   ├── claude-code.md             # Claude Code 适配
│   └── codex.md                   # Codex CLI 适配
├── templates/
│   ├── diagnostic-card.md         # 诊断卡模板
│   └── skill-audit-report.md      # 审计报告模板
├── scripts/
│   ├── batch-review.py            # 批量审查脚本
│   └── validate-routing.py        # 路由验证脚本
├── examples/
│   ├── before-after.md            # 优化前后对比
│   └── full-audit-example.md      # 完整审计示例
└── CONTRIBUTING.md                # 贡献指南
```

---

## 与同类方案的区别

| 特性 | Critical SkillGovern | 传统的路由优化 |
|------|---------------------|---------------|
| 跨平台 | Hermes / Claude Code / Codex | 仅限单一平台 |
| 批判性思维 | 深度质疑 + 逆向思维 | 仅正面检查 |
| 用户审批 | 严重度分级 + 选择性修复 | 全自动无人工 |
| 二次验证 | 修复后再次全量检查 | 无此步骤 |
| 模板化 | 诊断卡 + 报告模板 | 无标准化输出 |
| 实战验证 | 120+ 技能经验 | 理论设计 |

---

## 实战效果

在一套 **120 个技能、40 个类别** 的 Hermes Agent 技能库上验证：

| 指标 | 治理前 | 治理后 |
|------|--------|--------|
| 路由覆盖率 | 23/120 (19%) | 120/120 (100%) |
| 模板残余 | 14 个 | 0 个 |
| 全英触发 | 97 个 | 0 个 |
| 弱负样本 | 54 个 | 全部指向替代技能 |

---

## 贡献

欢迎提交 Issue 和 PR！详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 许可证

MIT License — 自由使用、修改、分发。
