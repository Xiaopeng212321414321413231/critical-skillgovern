# 🔍 Critical SkillGovern

> **批判式技能治理框架** — 跨平台技能质量审查方法论，**已在 120+ 技能实战验证**。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platforms](https://img.shields.io/badge/Platform-Hermes%20%7C%20Claude%20Code%20%7C%20Codex-blue)]()

---

## 这解决了什么问题？

当技能库超过 **10 个**时，AI 模型在众多技能中精准匹配的难度指数级上升。不是模型不够强，是技能描述没给足够的决策信号。

本框架专注一件事：**让你的技能路由精准、不误触**。

## 为什么你应该关心

你安装的第三方技能包（如 **Superpowers 方法论包、Baoyu 创意包、设计 Skill 包**）可能存在路由隐患：

| 包来源 | 路由完整率 | 典型问题 |
|--------|-----------|----------|
| 官方内置 | 100% ✅ | 标准四层描述，双层 tags |
| Superpowers | 优秀 ✅ | 社区包中最规范 |
| Baoyu | ⚠️ 60% | 负样本太泛，tags 单层 |
| 设计技能包（16个） | ⚠️ 19% | 13/16 有弱负样本问题 |

👉 详细案例 → [examples/third-party-packs.md](examples/third-party-packs.md)

治理前：

```yaml
【不适用场景】不需要生成创意内容/可视化时    ← 指向不清
```

治理后：

```yaml
【不适用场景】仅需要简单图表/流程图时，应使用 excalidraw；
需要 AI 艺术图而非结构化信息图时               ← 指向具体替代技能
```

**区别**：前者模型会猜错，后者模型一读就懂。

---

## 核心流程

```
路由诊断 → 批判性质询 → 用户审批 → 执行修复 → 二次验证 → 最终报告
```

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

```bash
# 1. 审查所有技能
python scripts/batch-review.py --path ~/.hermes/skills --format hermes

# 2. 只看第三方包（按类别）
python scripts/batch-review.py --path ~/.hermes/skills/creative --format hermes

# 3. 导出报告
python scripts/batch-review.py --path ~/.hermes/skills --format hermes --csv report.csv
```

---

## 目录结构

```
critical-skillgovern/
├── README.md                         # 项目概述
├── LICENSE                           # MIT 许可证
├── docs/
│   ├── methodology.md                # 核心方法论（六阶段流水线）
│   └── routing-optimization.md       # 路由优化 + 四层描述
├── adapters/
│   ├── hermes.md                     # Hermes Agent 适配
│   ├── claude-code.md                # Claude Code 适配
│   └── codex.md                      # Codex CLI 适配
├── templates/
│   ├── diagnostic-card.md            # 诊断卡模板
│   └── skill-audit-report.md         # 审计报告模板
├── scripts/
│   ├── batch-review.py               # 批量审查脚本
│   └── validate-routing.py           # 路由验证脚本
├── examples/
│   ├── before-after.md               # 优化前后对比
│   ├── full-audit-example.md         # 120 技能完整审计示例
│   └── third-party-packs.md          # 🌟 第三方包实战案例
└── CONTRIBUTING.md                   # 贡献指南
```

---

## 实战效果

在一套 **128 个技能、40 个类别**的 Hermes Agent 技能库上验证，包含 Superpowers、Baoyu、16 个设计技能等第三方包：

| 指标 | 治理前 | 治理后 |
|------|--------|--------|
| 路由覆盖率 | 23/128 (18%) | 128/128 (100%) |
| 模板残余（Python 字面量） | 14 个 | 0 个 |
| 全英触发场景 | 97 个 | 0 个 |
| 弱负样本（指向不清） | 54 个 | 全部指向替代技能 |
| 第三方包误触发率 | ~30% | ~5% |

---

## 为什么选这个方案

| 特性 | Critical SkillGovern | 传统路由优化 |
|------|---------------------|---------------|
| 跨平台 | Hermes / Claude Code / Codex | 仅锁定单一平台 |
| 批判性思维 | 逆向思维 + 假设挖掘 | 仅正向检查 |
| 第三方包适配 | 专门案例 + 批量脚本 | 无第三方考虑 |
| 实战验证 | 128 技能真实数据 | 理论设计 |
| 用户可控 | 严重度分级 + 选择性修复 | 全自动无人工 |
| 二次验证 | 修复后全量复检 | 无此步骤 |

---

## 贡献

欢迎提交 Issue 和 PR！详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 许可证

MIT License — 自由使用、修改、分发。
