# 🔍 Critical SkillGovern

> **批判式技能治理框架** — 跨平台技能质量审查方法论，**已在 120+ 技能实战验证**。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platforms](https://img.shields.io/badge/Platform-Hermes%20%7C%20Codex%20%7C%20DeepSeek%20Harness-blue)]()

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

## ⚡ 非自回归路由（Laya）：把"描述"变成可测量的路由指标

四层描述解决的是"描述写得清不清楚"，但它没有回答**"这样写到底选不选得对"**。
`scripts/laya_router.py` 用 **Laya**（421M 非自回归判决器，一次前向并行出全部候选概率，
纯 CPU 单次约 0.9 s）做 L0 路由，把每一步都量出来：

```
L0 laya（非自回归 · 判决）  →  L1 本地 AR 模型（执行技能）  →  L2 云端 AR agent（低置信度接管）
                                      ↑ 执行结果 / 用户纠正 ↓
                              定义回灌 refine：反推 route_text 与负样本
```

**本机实测（真实技能库）：**

| 做法 | top-1 | 说明 |
|---|---|---|
| 直接拿 description 首句喂 laya | 33.3% | ❌ 走了弯路 |
| 从句提取 + 压到 ≤9 词 | **83.3%**（top-3 100%） | 10 候选、12 条英文用例、随机基线 10% |
| 中文查询（候选仍为英文） | 66.7% | ⇒ 中文库必须用 `laya-multilingual` |
| **大库 66 技能：flat 全量** | **25.0%**（top-3 66.7%） | 每项只剩 2~3 token，描述被砍光 |
| **大库 66 技能：shortlist K=10 + 双语 route_text** | **66.7%**（top-3 83.3%、召回 100%） | ✅ 端到端跑通「判决 + 回灌」 |

**三条硬约束**（来自 laya 实现内部，非调参可绕）：
1. 选项共享 `head_max_len` token 预算（english=192 / multilingual=256）→ **66 技能时每项只剩 2~3 token**，必须分级或先做 shortlist 粗筛；
2. english 档选项 ≥ 11 时官方温度被 SDK 强制抬回，**confidence 不可信** → 候选数控制在 ≤10（multilingual 档无此键，不受限）；
3. english 检查点读不了中文描述（官方 non-en 意图 0.306 ≈ 随机）→ 中文技能库必须换多语言档（本机已备好）。

**闭环**：`route/eval` 落日志 → `feedback` 记录纠正 → `refine` 挖判别性词生成补丁（只提案，需你审批）
→ 改 `data/route_text_overrides.json` → 重跑 `eval` 复测 top-1 是否真的涨。
**实测这轮闭环**：66 技能库首版 shortlist 只召回 41.7%（英文 route_text 撞中文查询），
补**双语 route_text** 后 → 召回 **100%**、top-1 **41.7% → 66.7%**，全程没改任何技能本体。
**技能定义从此像权重一样被路由误差"梯度下降"。**

📖 完整方案与全部实测数据 → [docs/laya-routing.md](docs/laya-routing.md)

---

## 支持的平台

| 平台 | 技能格式 | 适配指南 |
|------|----------|----------|
| 🏛️ **Hermes Agent** | SKILL.md (YAML frontmatter + Markdown) | [adapters/hermes.md](adapters/hermes.md) |
| 🔌 **DeepSeek Harness** | DSH 工具插件 (defineTool) | [dsh-plugin/](dsh-plugin/) |
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
│   ├── routing-optimization.md       # 路由优化 + 四层描述
│   └── prompts/
│       └── classify-skills-v2.txt    # 技能分类 Prompt v2.1
├── adapters/
│   ├── hermes.md                     # Hermes Agent 适配
│   └── codex.md                      # Codex CLI 适配
├── dsh-plugin/                       # DeepSeek Harness 插件
│   ├── package.json                  # DSH bundle 清单
│   ├── cordis.patch.yml              # Cordis 配置
│   └── index.js                      # 插件入口（3 个工具）
├── templates/
│   ├── diagnostic-card.md            # 诊断卡模板
│   └── skill-audit-report.md         # 审计报告模板
├── scripts/
│   ├── batch-review.py               # 批量审查脚本
│   ├── validate-routing.py           # 路由验证脚本（静态：描述合不合规）
│   └── laya_router.py                # 非自回归路由 + 定义回灌（动态：选不选得对）
├── data/                             # laya 路由工作区（路由表 / 日志 / 补丁 / route_text 覆盖）
├── docs/laya-routing.md              # Laya 非自回归路由方案与实测
├── examples/
│   ├── before-after.md               # 优化前后对比
│   ├── full-audit-example.md         # 120 技能完整审计示例
│   └── third-party-packs.md          # 第三方包实战案例
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
| 跨平台 | Hermes / Codex / DeepSeek Harness | 仅锁定单一平台 |
| 批判性思维 | 逆向思维 + 假设挖掘 | 仅正向检查 |
| 第三方包适配 | 专门案例 + 批量脚本 | 无第三方考虑 |
| 实战验证 | 128 技能真实数据 | 理论设计 |
| 用户可控 | 严重度分级 + 选择性修复 | 全自动无人工 |
| 二次验证 | 修复后全量复检 | 无此步骤 |

---

## DeepSeek Harness 插件

安装 DSH 插件，直接在 Agent 中获得 3 个技能治理工具：

```bash
# 从 GitHub 安装
dsh plugin --profile web add github:Xiaopeng212321414321413231/critical-skillgovern#path:dsh-plugin

# 从本地克隆安装
dsh plugin --profile web add ./dsh-plugin
```

| 工具 | 功能 |
|------|------|
| `skill-diagnose` | 诊断单个技能文件的路由健康度 |
| `skill-audit` | 批量审计整个技能目录 |
| `skill-classify` | 将技能分类到结构化类别（7 大类、19 子类） |

已收录于 [DSH 1024Store](https://deepseek1024.com)。

---

## 贡献

欢迎提交 Issue 和 PR！详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 许可证

MIT License — 自由使用、修改、分发。
