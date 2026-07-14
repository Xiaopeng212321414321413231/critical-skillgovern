# 技能路由优化（Skill Routing Optimization）

> 核心问题：当技能库超过 10 个时，AI 模型在众多技能中精准匹配用户意图的难度指数级上升。
> 本质是路由复杂度问题 —— 不是模型能力不足，而是技能描述没有给模型足够的决策信号。

## 四层路由描述

### 标准格式

每个技能的路由描述应拆分为 4 层结构化信息：

```yaml
description: |
  【触发场景】当需要编写新的 SKILL.md、编辑已有的技能文件时
  【输入特征】"写技能"、"创建技能"、"新建技能"、"edit skill"等表述
  【输出目标】输出一个符合规范的技能文件，含完整 YAML frontmatter 和 body
  【不适用场景】不需要创建或修改技能文件时；或仅使用现有技能时
```

| 层级 | 含义 | 给模型的价值 |
|------|------|-------------|
| 【触发场景】 | 什么情况下触发 | "这个技能适合我的情况吗？" |
| 【输入特征】 | 用户输入中的关键词/意图 | "用户的表述包含这些词吗？" |
| 【输出目标】 | 最终产出什么 | "这个产出是我要的吗？" |
| 【不适用场景】 | 什么情况不要用（负样本） | 减少误触发，最关键的一层 |

### 负样本设计原则

负样本是路由优化中**最重要也最容易被忽视**的一层。好的负样本：

1. **列出至少 2 种误触场景**
2. **指向应该用的替代技能**
3. **使用用户自然的表达方式**

```yaml
# ❌ 弱负样本（无效）
【不适用场景】不需要使用此技能时

# ✅ 强负样本（有效）
【不适用场景】需求仍模糊不清时，应先使用 brainstorming 细化；
已经有现有计划只需执行时，应使用 executing-plans
```

## 双层标签体系（Skill Tree）

不要让模型面对全部技能。先用 tags 缩小范围，再精确定位。

### tags 结构

```
tags: [大类, 小类]   # 第一层：功能域，第二层：具体类型
```

常见分类域：

| 大类 | 子类举例 |
|------|----------|
| `development` | `planning`, `implementation`, `debugging`, `code-review`, `completion` |
| `collaboration` | `coordination`, `communication` |
| `github` | `devops`, `management`, `pr-workflow` |
| `creative` | `design`, `art`, `music` |
| `media` | `video`, `audio`, `image` |
| `research` | `paper`, `monitor`, `search` |
| `note-taking` | `obsidian`, `knowledge-base` |
| `hermes` | `profile`, `plugin`, `gateway` |
| `productivity` | `documents`, `email`, `calendar` |

### related_skills 上下游链路

技能之间通过 related_skills 建立关联，形成一个导航网：

```yaml
# 单技能示例
related_skills: [brainstorming, executing-plans, subagent-driven-development]
```

**关键原则：**
- tags 负责**"召回"**（缩小范围）
- related_skills 负责**"精排"**（精确匹配）
- 两个机制缺一不可

**跨类别关联示例：**

| 技能 | 跨类关联到 |
|------|-----------|
| media/bilibili-content | note-taking/obsidian（内容归档） |
| research/arxiv | note-taking/obsidian（论文笔记） |
| github/code-review | requesting-code-review（审查流程） |
| creative/humanizer | custom/document（文本优化输出） |

## 路由健康指标

### 覆盖率（Coverage）

```python
good / total = 技能完整率
```

- < 60%：⚠️ 大部分技能路由不可靠
- 60-90%：🔶 需要针对性优化
- > 90%：✅ 路由体系健康

### 误触发率（False Trigger）

通过负样本质量评估：

- 每个技能至少 2 个负样本场景
- 每个负样本指向 1 个替代技能
- 负样本使用用户自然语言（非技术术语）

### 触发场景质量

- 中文触发 > 95%
- 触发场景以"当...时"开头
- 触发场景长度 < 80 字
- 关键词覆盖 3 种以上用户自然表达

## 与各平台的映射

### Hermes Agent

```
Hermes 技能格式     →  通用路由格式  →  标准四层描述
name: skill-name       【触发场景】     【触发场景】当...时
description: ...       【输入特征】     【输入特征】"..."
tags: [cat]            【输出目标】     【输出目标】输出...
related_skills: [...]  【不适用场景】   【不适用场景】...
```

### Claude Code

```
.claude/skills/skill-name.md          →  通用路由格式
# 技能名称（一级标题）                    【触发场景】
When the user asks about X...          【输入特征】
                                       【输出目标】
                                       【不适用场景】
```

### Codex

```
Codex 无原生技能系统                       →  通用路由格式
但可以通过 prompt 模板 + CLI 包装器实现      【触发场景】
                                           【输入特征】
                                           【输出目标】
                                           【不适用场景】
```

## Skill Tree 完整分类架构

```
研发类 (development)
├── planning          — brainstorming, writing-plans, decision-framework
├── implementation    — TDD, subagent-driven, spike, simplify-code
├── debugging         — systematic-debugging, node-debugger
├── code-review       — requesting, receiving
└── completion        — verification, branch-finishing

协作类 (collaboration)
├── coordination      — parallel-agents, git-worktrees, kanban
└── communication     — meeting, notification

GitHub 运维 (github)
├── devops            — auth, issues, pr-workflow
├── management        — repo-management, repo-cleanup, repo-polish
└── codebase          — inspection, code-review

创意类 (creative)
├── design            — architecture-diagram, excalidraw, p5js
├── visual            — ascii-art, sketch, touchdesigner
├── writing           — humanizer, songwriting
└── prototype         — claude-design, pretext

媒体类 (media)
├── video             — bilibili, youtube, songsee
├── audio             — transcription, music
└── image             — gif-search, vision-tagging

机器学习 (mlops)
├── models            — huggingface-hub, sam
├── inference         — llama-cpp
└── evaluation        — weights-and-biases

办公效率 (productivity)
├── documents         — pdf, ocr, ppt
├── collaboration     — notion, airtable, google-workspace
└── automation        — pipeline, workflow

笔记与知识库 (note-taking)
├── obsidian          — vault-management, ai-assistant
└── automation        — pipeline, workflow

信息检索 (research)
├── paper             — arxiv
├── monitor           — blogwatcher, rss
└── reference         — llm-wiki, web-search

网页提取 (web-extraction)
├── extraction        — web-extraction
└── tools             — setup, config
```

## 自动验证脚本

每次路由优化后运行：

```python
import os, yaml

required_sections = ['【触发场景】', '【输入特征】', '【输出目标】', '【不适用场景】']
good = 0
total = 0

for root, dirs, files in os.walk('skills/'):
    if 'SKILL.md' not in files:
        continue
    total += 1
    with open(os.path.join(root, 'SKILL.md')) as f:
        parts = f.read().split('---', 2)
    fm = yaml.safe_load(parts[1])
    desc = fm.get('description', '')
    has_all = all(s in desc for s in required_sections)
    has_tags = bool(fm.get('tags'))
    if has_all and has_tags:
        good += 1

print(f'{good}/{total} skills fully routed ({good/total*100:.0f}%)')
```
