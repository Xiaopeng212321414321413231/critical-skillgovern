# Critical SkillGovern — 批判式技能治理方法论

> **核心洞察**：技能越多，路由复杂度指数级上升。系统不是能力不够，而是技能描述没有给模型足够的决策信号。
>
> 本方法论已在 **120+ 技能、40 个类别** 的实战中验证。

## 七阶段审查流水线

```
阶段 1: 路由诊断（Routing Diagnosis）      — 发现问题
阶段 2: 分类打标（Classification & Tagging）— 建立技能树
     ↓ 用户验证分类结果 ←— 关键！
阶段 3: 批判性质询（Critical Questioning）— 深度分析
阶段 4: 用户审批（User Approval）          — 决策拍板
阶段 5: 执行修复（Execution & Fix）        — 精确施治
阶段 6: 二次验证（Verification）          — 确保质量
阶段 7: 最终报告（Final Report）          — 交付成果
```

---

## 阶段 1：路由诊断

### 检查清单

对每个技能进行 **6 项路由健康检查**：

| # | 检查项 | 症状 | 严重度 |
|---|--------|------|--------|
| 1 | **模板残余** | 描述中有 `.join`、`kw[:`、`+ ,` 等 Python 字面量 | 🔴 |
| 2 | **中英混合** | 触发场景为英文（专有名词除外） | 🔴 |
| 3 | **重复描述** | 触发场景与输出目标几乎相同 | 🟡 |
| 4 | **弱负样本** | 负样本太泛，未指向替代技能 | 🟡 |
| 5 | **单层 tag** | tags 只有一层，缺少细粒度分类 | 🟢 |
| 6 | **缺关联** | related_skills 为空或缺少跨类链接 | 🟢 |

### 通用路由结构

```
【触发场景】什么情况下触发 — "当...时"
【输入特征】用户输入中的关键词/意图
【输出目标】最终产出什么
【不适用场景】什么情况不要用 — 指向替代技能
```

---

## 阶段 2：分类打标（⚠️ 之前漏掉的阶段）

在深入批判之前，**先把每个技能归到正确的类别里**。

### 做什么

```
每个技能分配：
  1. tags（双层：大类 + 小类）例如 [media, bilibili]
  2. 目录位置（属于哪个类别下）
  3. related_skills（上下游关联）
```

### Skill Tree 分类体系

```
研发类 (development)
├── planning       — brainstorming, writing-plans
├── implementation — tdd, subagent-driven, spike
├── debugging      — systematic-debugging, node-debugger
├── code-review    — requesting, receiving
└── completion     — verification, branch-finishing

协作类 (collaboration)
├── coordination   — parallel-agents, git-worktrees, kanban

GitHub (github)
├── devops         — auth, issues, pr-workflow
├── management     — repo-management, cleanup, polish
└── codebase       — inspection, code-review

创意类 (creative)
├── design         — architecture-diagram, excalidraw, p5js
├── visual         — ascii-art, sketch, touchdesigner
├── writing        — humanizer, songwriting
└── prototype      — claude-design, pretext

媒体类 (media)
├── video          — bilibili, youtube, songsee
├── audio          — transcription, music
└── image          — gif-search, vision-tagging

机器学习 (mlops)
├── models         — huggingface-hub, sam
├── inference      — llama-cpp
└── evaluation     — weights-and-biases

办公效率 (productivity) — pdf, notion, airtable, workspace
笔记知识库 (note-taking) — obsidian, pipeline
信息检索 (research)     — arxiv, blogwatcher, llm-wiki
网页提取 (web-extraction) — extraction, tools
Hermes 配置 (hermes)    — profile, plugin, gateway
```

### ➡️ 用户验证分类结果（🔑 关键环节）

```
分类完成后 → 列出所有技能的 tags + 分类 → 你过目 → 
✅ 确认 → 进入第 3 阶段
🔄 调整 → 你说改哪就改哪 → 再确认
```

这一步防止「我分的类不是你要的」，避免后面白批判。

---

## 阶段 3：批判性质询

分类确认了，现在挑战它。

### 5W1H 质问框架

```
What（是什么）：
├─ 这个技能的功能是什么？归类对不对？
├─ 如果不是这样会怎样？
├─ 有更好的分类方式吗？

Why（为什么）：
├─ 为什么分类在这里？为什么不放别的类别？
├─ 用户真的需要这个技能吗？

Who（谁）：
├─ 谁会使用这个技能？谁会误触发？

When（什么时候）：
├─ 什么时候触发正确？什么时候会误触发？

Where（在哪里）：
├─ 这个分类位置合理吗？有没有更适合的位置？

How（怎么做）：
├─ 怎么执行这个技能？怎么验证执行正确？
```

### 逆向思维

```
正常 → 异常
├─ 正常触发 → 边界触发（空输入、超长文本、特殊字符）
├─ 正常流程 → 异常流程（中断、超时、失败）
├─ 正常环境 → 异常环境（无网络、高并发、权限不足）

确定 → 假设
├─ 用户会正确表达 → 用户会模糊表达
├─ 关键词会匹配 → 关键词不会匹配
├─ 技能会正确执行 → 技能会错误执行
```

### 假设挖掘

| 假设类型 | 常见假设 | 反例思考 |
|----------|----------|----------|
| 用户行为假设 | 用户会按预期描述需求 | 用户描述模糊、不完整 |
| 环境假设 | 环境正常 | 网络异常、服务故障 |
| 依赖假设 | 相关技能都存在 | 依赖技能缺失或版本不匹配 |
| 时序假设 | 技能会按顺序触发 | 乱序触发、并发触发 |

### "那又怎样" 追问法

```
发现问题 → 那又怎样？
├─ 影响一个技能 → 那又怎样？还影响什么？
├─ 影响一个类别 → 那又怎样？还影响谁？
├─ 影响整个系统 → 那又怎样？影响多大？
```

---

## 阶段 4：用户审批

将阶段 1+2+3 的发现整理为 **决策清单**：

```
🔴 严重（bug，基本都批）:
  [ ] 模板残余 → 修复
  [ ] 全英触发 → 中文化
🟡 建议（你判断）:
  [ ] 弱负样本 → 指向替代技能
  [ ] 分类调整 → 从 media 移到 note-taking
🟢 可选（看心情）:
  [ ] 缺 related_skills → 补链接
```

---

## 阶段 5：执行修复

### 核心原则：只改路由，不碰本体

| 可修改 | 不可修改 |
|--------|----------|
| 描述 / 触发条件 | 功能代码、命令 |
| tags / 分类 | API 参数 |
| related_skills | 配置模板 |
| 负样本 | 文件结构 |

批量修复：50 个以上用自动化脚本按类别处理。

---

## 阶段 6：二次验证

重新运行阶段 1 的检查清单：

```
- [ ] 模板残余是否已清除？
- [ ] 触发场景是否已中文化？
- [ ] 输入特征是否覆盖自然语言变体？
- [ ] 负样本是否已指向替代技能？
- [ ] tags 是否已优化（双层）？
- [ ] related_skills 是否有跨类链接？
- [ ] YAML 语法是否正确？
```

---

## 阶段 7：最终报告

```
=== 技能治理审计报告 ===

技能总数: 128
初始覆盖率: 23/128 (18%)
最终覆盖率: 128/128 (100%)

修复项:
- 模板残余: 14 ✅
- 全英触发: 97 ✅
- 弱负样本: 54 ✅

跳过（用户选择）:
- tags 优化: 未处理
- related_skills: 未处理

第三方包误触率: ~30% → ~5%

最终状态: 健康
```

---

## 与旧流程的区别

| 旧流程（6阶段） | 新流程（7阶段） | 为什么改 |
|----------------|----------------|----------|
| 路由诊断 → 批判性质询 | 路由诊断 → **分类打标 → 用户验证分类 →** 批判性质询 | 分类是批判的前提，而且要你先确认才能往下走 |
| 用户审批在第3步 | **分类验证 + 修复审批 两次决策** | 一次决策管太多，拆成两次更清晰 |
| 批判在前 | 分类验证通过后才批判 | 避免白花力气管一个你都不认同的分类 |

---

## 什么时候做

1. 安装新技能后 → 自动走一遍 1-2（诊断+分类），等你确认
2. 批量导入后 → 全流程走一遍
3. 发现误触发后 → 从第 3 阶段起步（分类已经定了）
4. 定期维护 → 走 3-7（分类不动，只看路由质量）
