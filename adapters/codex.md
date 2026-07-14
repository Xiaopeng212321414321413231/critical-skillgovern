# Codex 适配指南

Codex CLI（OpenAI 的自主编程代理）没有原生的技能/插件文件系统，但可以通过 prompt 模板 + CLI 包装器实现类似的路由优化效果。

## Codex 执行模式

Codex 通过以下方式执行任务：

```bash
# 一次性执行
codex exec "Your task description"

# 自动批准模式
codex exec --full-auto "Your task description"

# 无沙箱模式（最快但最危险）
codex exec --yolo "Your task description"
```

## 路由优化的两种方式

### 方式一：Prompt 模板文件

创建 prompt 模板目录：

```
~/.codex/templates/
├── database-migration.md      # 数据库迁移模板
├── code-review.md             # 代码审查模板
├── testing.md                 # 测试编写模板
└── refactoring.md             # 重构模板
```

模板文件示例（database-migration.md）：

```markdown
# Database Migration Task

When the user asks to create or modify database migrations, use this approach:

## Requirements
1. Use Alembic for migration generation
2. Always create a rollback function
3. Test migrations against a local database copy

## Style
- Generate both upgrade() and downgrade() functions
- Use descriptive revision messages
- Include foreign key constraints explicitly
```

使用方式：

```bash
# 通过模板执行
codex exec "$(cat ~/.codex/templates/database-migration.md) Create a users table migration"

# 或直接管道输入
cat ~/.codex/templates/code-review.md | codex exec "Review the current PR"
```

### 方式二：Shell 包装脚本

创建包装脚本目录：

```
~/.codex/scripts/
├── review-pr.sh        # 包装 code review 逻辑
├── create-migration.sh # 包装数据库迁移逻辑
└── run-tests.sh        # 包装测试执行逻辑
```

示例（review-pr.sh）：

```bash
#!/bin/bash
# Review a PR against main
PR_NUMBER=${1:-$(gh pr view --json number -q .number)}
REVIEW_DIR=$(mktemp -d)

git clone "$(gh repo view --json url -q .url)" "$REVIEW_DIR"
cd "$REVIEW_DIR"
gh pr checkout "$PR_NUMBER"
codex exec --full-auto "Review this PR. Check for bugs, security issues, 
and style problems. Focus on: business logic, error handling, edge cases."
rm -rf "$REVIEW_DIR"
```

## 路由映射

| 通用路由 | Codex 实现 |
|----------|-----------|
| 触发场景 | Prompt 模板文件名 + 首段描述 |
| 输入特征 | 模板中的关键词映射 |
| 输出目标 | 模板中的 Requirements 部分 |
| 负样本 | 模板中的 Exclusion 部分 |
| 分类 | 目录结构（按功能分组） |
| 关联 | Git 工作流整合 |

## 路由验证

Codex 无内置路由系统，验证通过以下方式：

1. Prompt 模板是否有清晰的触发场景描述？
2. 是否与 Hermes / Claude Code 的技能保持了一致的路由描述？
3. 包装脚本是否有明确的调用条件和输出预期？

## 与 Hermes / Claude Code 协同

建议将 Codex 的 prompt 模板与 Hermes 的 SKILL.md 保持同步：

```
# 同一个技能，跨平台适配
critical-skillgovern/skills/
├── database-migration/
│   ├── hermes.SKILL.md          # Hermes Agent 格式
│   ├── claude-code.skill.md     # Claude Code 格式
│   └── codex.prompt-template.md # Codex 格式
```

这样无论用户使用哪个平台，都能获得一致的技能治理体验。

## 优化检查清单

- [ ] Prompt 模板是否有清晰的任务描述？
- [ ] 是否有 Requirements 和 Exclusions 部分？
- [ ] 包装脚本是否有参数说明？
- [ ] 是否与其他平台保持了路由描述一致？
- [ ] 是否覆盖了常见的误触发场景？
