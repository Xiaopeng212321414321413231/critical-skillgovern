# 路由优化前后对比示例

## 示例 1：Hermes Agent 技能

### 优化前

```yaml
---
name: bilibili-content
description: |
  【触发场景】当提取B站视频字幕/转写内容，支持合集/多P批量处理，归档到Obsidian时
  【输入特征】涉及"B站", "bilibili", "哔哩哔哩", "Bilibili", "BV号"等关键词
  【输出目标】提取并即时呈现B站视频的文字摘要
  【不适用场景】不需要提取B站视频信息时
tags: [media, bilibili]
---
```

**问题诊断：**
- ✅ 触发场景完整
- ✅ 输入特征覆盖充分
- ✅ 输出目标明确
- ❌ 负样本太弱（"不需要提取B站视频信息时" — 说了等于没说）

### 优化后

```yaml
---
name: bilibili-content
description: |
  【触发场景】当提取B站视频字幕/转写内容，支持合集/多P批量处理，归档到Obsidian时
  【输入特征】涉及"B站", "bilibili", "哔哩哔哩", "Bilibili", "BV号"等关键词
  【输出目标】提取并即时呈现B站视频的文字摘要
  【不适用场景】需要下载B站视频文件时，应使用 bilibili-downloader；
  仅需视频元数据（播放量/点赞/评论）而非字幕内容时
tags: [media, bilibili]
related_skills: [obsidian, youtube-content]
---
```

**改善点：**
- ✅ 负样本指向了具体的替代技能（bilibili-downloader）
- ✅ 增加了第二个负样本场景（元数据查询）
- ✅ 补全了 related_skills（Obsidian 归档 + YouTube 对标）

---

## 示例 2：中英混合修复

### 优化前

```yaml
description: |
  【触发场景】When the user needs to configure, extend, or contribute to Hermes Agent
  【输入特征】涉及"hermes", "agent", "config"等关键词
  【输出目标】Help the user with Hermes Agent configuration
  【不适用场景】Not using Hermes Agent
```

### 优化后

```yaml
description: |
  【触发场景】当需要配置、扩展或参与 Hermes Agent 开发时
  【输入特征】涉及"hermes", "agent","Hermes 配置","Hermes 扩展","Hermes 开发"等关键词
  【输出目标】提供 Hermes Agent 的配置指南、扩展方法或开发帮助
  【不适用场景】不需要使用 Hermes Agent 时；或使用其他 AI 代理工具（如 Claude Code、Codex）时
```

---

## 示例 3：模板残余修复

### 优化前

```yaml
description: |
  【触发场景】当+ ,.join(kw[:5]) +    ← 模板残余！
  【输入特征】涉及"..."
  【输出目标】输出...
```

### 优化后

```yaml
description: |
  【触发场景】当需要进行代码审查时
  【输入特征】涉及"review", "code review", "审查代码", "检查代码"等关键词
  【输出目标】对代码进行全面的审查分析
  【不适用场景】需要自动化修复代码问题而非仅审查时
```
