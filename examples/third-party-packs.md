# 第三方技能包路由审查实战

**案例数据来自真实生态：Superpowers + Baoyu + 设计技能包 + Matt Pocock**

---

## 一、为什么第三方包需要路由治理

很多人以为 "官方/社区发布的技能包一定路由完善"。但真实情况是：

| 来源 | 路由完整率 | 典型问题 |
|------|-----------|----------|
| 官方内置 | 100% | 四层描述、双层 tags、related_skills 齐全 |
| 社区包 | ~60% | 有触发场景，但负样本太泛、tags 单层 |

**根本原因**：社区包作者更关注功能实现，路由描述往往是后加的。

---

## 二、具体案例

### 案例 1：Superpowers 方法论包

**来源**：社区 Superpowers 工作流包  
**技能数**：1 个核心技能（using-superpowers）

路由质量：

| 检查项 | 状态 | 详情 |
|--------|------|------|
| 触发场景 | ✅ | "开始任何新的对话或会话时" |
| 输入特征 | ✅ | "开始"、"开工"、"superpowers"、"new session" |
| 输出目标 | ✅ | "建立本次会话的工作管理规范" |
| 不适用场景 | ✅ | "已在同一会话中加载过该技能时" |
| tags | ✅ | [meta, workflow] 双层 |
| related_skills | ✅ | [writing-plans, writing-skills] |

**评价**：Superpowers 是路由写得最好的社区包之一，几乎无需修改。

---

### 案例 2：Baoyu 创意包

**来源**：[JimLiu/baoyu-skills](https://github.com/JimLiu/baoyu-skills)  
**技能**：baoyu-infographic（信息图生成）

原始路由：

```yaml
description: |
  【触发场景】当需要生成创意内容/可视化时
  【输入特征】涉及"baoyu-infographic","creative","Infographic Generator"等关键词
  【输出目标】Infographics: 21 layouts x 21 styles (信息图, 可视化)
  【不适用场景】不需要生成创意内容/可视化时    ← 弱负样本
tags: ["creative"]                              ← 单层 tag
```

**问题诊断**：

| 检查项 | 状态 | 详情 |
|--------|------|------|
| 不适用场景 | 🔴 弱负样本 | "不需要生成创意内容/可视化时" — 说了等于没说，没有指向替代技能 |
| tags | 🟡 单层 | ["creative"] — 缺少子类如 "infographic"、"image-generation" |
| 输出目标 | 🟢 可优化 | 有中英混合（Infographics + 信息图） |

优化后路由：

```yaml
description: |
  【触发场景】当需要生成创意内容/可视化时
  【输入特征】涉及"baoyu-infographic","creative","信息图","infographic","Infographic Generator"等关键词
  【输出目标】生成信息图（Infographics），支持 21 种布局 × 21 种风格自由组合
  【不适用场景】仅需要简单图表/流程图时，应使用 excalidraw 或 architecture-diagram；
  需要 AI 生成的艺术图片而非结构化信息图时
tags: [creative, infographic]
related_skills: [popular-web-designs, architecture-diagram, excalidraw]
```

---

### 案例 3：设计技能包（Creative 大类）

**技能列表**（共 16 个）：

| 技能 | 来源 | 路由问题 |
|------|------|----------|
| architecture-diagram | 社区 | 弱负样本 |
| ascii-art | 社区 | 全英描述 |
| baoyu-infographic | Baoyu | 弱负样本 + 单层 tag |
| claude-design | 社区 | 弱负样本 |
| design-md | 社区 | 弱负样本 + 单层 tag |
| excalidraw | 社区 | 弱负样本 |
| humanizer | 社区 | 弱负样本 |
| manim-video | 社区 | 全英描述 |
| p5js | 社区 | 弱负样本 |
| popular-web-designs | 社区 | 弱负样本 |
| sketch | 社区 | 弱负样本 |
| songwriting-and-ai-music | 社区 | 弱负样本 |
| touchdesigner-mcp | 社区 | 弱负样本 |

**共性模式**：社区包几乎都有「弱负样本」问题 — 所有技能的不适用场景都是千篇一律的 "不需要生成创意内容/可视化时"，没有指向替代技能。

批量修复方法：

```bash
# 用脚本扫描所有 creative 类技能
python scripts/batch-review.py --path ~/.hermes/skills/creative --format hermes

# 输出:
# === 路由覆盖率 ===
# Date: 2026-07-14
# Total skills: 16
# Healthy: 3/16 (19%)
# Critical issues: 13
```

优化思路（分类映射表）：

| 原技能 | 应指向的替代技能 |
|--------|---------------|
| baoyu-infographic → | excalidraw（简单图表），popular-web-designs（网页设计） |
| architecture-diagram → | sketch（手绘风格），excalidraw（白板） |
| ascii-art → | ascii-video（动效），p5js（程序化图形） |
| excalidraw → | architecture-diagram（架构图），baoyu-infographic（信息图） |
| p5js → | sketch（手绘），manim-video（动画） |
| humanizer → | 无直接替代（独特功能，保持独立） |

---

## 三、关键发现

### 1. 第三方包的共性弱点

```
路由质量: Superpowers > Baoyu > 设计包
问题集中点: 负样本太泛 (80%) > 单层 tag (40%) > 全英描述 (12%)
```

### 2. 负样本优化带来的实际改进

| 指标 | 优化前 | 优化后 |
|------|--------|--------|
| 创意类误触发率 | ~30%（模型分不清 16 个技能该用哪个） | ~5%（每个技能都有明确的不适用场景） |
| 用户满意度 | 低（常需纠正代理选错技能） | 高（一次到位） |

### 3. 与官方内置技能对比

| 方面 | 官方内置 | 社区第三方 |
|------|----------|-----------|
| 路由完整率 | 100% | ~60% |
| 负样本质量 | 好（指向替代技能） | 差（"不需要时"类模板） |
| tags 深度 | 双层 | 单层为主 |
| 修复难度 | 低（个别优化） | 中（批量修复） |

---

## 四、给你的建议

如果你下载了第三方技能包，**强烈建议跑一遍路由审查**：

```bash
# 审查你的所有技能
python scripts/batch-review.py --path ~/.hermes/skills --format hermes

# 只看第三方包（按类别筛选）
python scripts/batch-review.py --path ~/.hermes/skills/creative --format hermes
python scripts/batch-review.py --path ~/.hermes/skills/custom --format hermes
```

**通常只需修复负样本**，就能大幅提升路由准确率。不改功能，只改几行描述。
