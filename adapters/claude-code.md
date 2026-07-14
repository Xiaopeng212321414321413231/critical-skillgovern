# Claude Code 适配指南

Claude Code 使用 `.claude/skills/` 目录下的 Markdown 文件作为技能格式，通过自然语言匹配自动调用。

## 技能文件格式

```markdown
# .claude/skills/database-migration.md

When asked to create or modify database migrations:
1. Use Alembic for migration generation
2. Always create a rollback function
3. Test migrations against a local database copy
```

## 使用四层路由描述

在 Claude Code 中，技能文件的**首段（第一段话）** 充当路由描述。将四层结构转化为自然语言首段：

```markdown
# database-migration.md

【适用场景】当用户要求创建或修改数据库迁移脚本时。
【关键词】"迁移"、"migration"、"数据库变更"、"Alembic"。
【能力】生成 Alembic 迁移文件 + 回滚函数 + 本地测试验证。
【不适用】仅查询数据库结构时，应使用 database-query 技能。

1. Use Alembic for migration generation
2. Always create a rollback function
3. Test migrations against a local database copy
```

## 路由映射

| 通用路由 | Claude Code 实现 | 说明 |
|----------|-----------------|------|
| 触发场景 | 首段【适用场景】 | Claude 读取文件首段进行匹配 |
| 输入特征 | 首段【关键词】 | 自然语言关键词辅助匹配 |
| 输出目标 | 首段【能力】 | 明确技能能做什么 |
| 负样本 | 首段【不适用】 | 减少误触发 |
| 分类 | 目录结构 + 文件名 | skills/database/ 或 skills/testing/ |
| 关联 | CLAUDE.md 中的规则引用 | 通过命令行/规则引用其他技能 |

## 技能存放位置

```
# 项目级（团队共享，git-tracked）
<project>/.claude/skills/<skill-name>.md

# 用户级（个人全局）
~/.claude/skills/<skill-name>.md
```

## CLAUDE.md 引用技能

在 CLAUDE.md 中声明技能依赖关系：

```markdown
# Project Rules

## Skills
- When modifying the database, use `.claude/skills/database-migration.md`
- For testing, use `.claude/skills/test-patterns.md`
```

## 路由验证

Claude Code 的技能路由不提供内置验证功能。建议手动检查：

1. 技能文件首段是否有【适用场景】【关键词】【能力】【不适用】四段标记
2. 技能文件的文件名是否直观反映功能（如 database-migration.md）
3. 技能文件是否按功能目录分组（skills/database/, skills/testing/）

## 与 Hermes 的区别

| 特性 | Claude Code | Hermes Agent |
|------|-------------|-------------|
| 技能格式 | 纯 Markdown | YAML frontmatter + Markdown |
| 路由机制 | 自然语言匹配 | 四层描述 + tags + related_skills |
| 触发方式 | 自动（LLM 判断） | 自动（LLM 判断） |
| 分类 | 目录层级 | tags + 目录层级 |
| 验证 | 手动 | 可脚本化 |

## 优化检查清单

- [ ] 技能首段是否包含【适用场景】【关键词】【能力】【不适用】？
- [ ] 文件名是否直观反映功能？
- [ ] 是否按功能目录分组？
- [ ] CLAUDE.md 是否引用了该技能？
- [ ] 技能内容是否包含了具体步骤而非空泛描述？
- [ ] 是否与 Hermes 对应的技能保持了一致的路由描述？
