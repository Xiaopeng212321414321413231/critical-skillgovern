# Hermes Agent 适配指南

Hermes Agent 使用 SKILL.md 文件作为技能格式，采用 YAML frontmatter + Markdown body 的结构。

## 技能文件格式

```yaml
---
name: skill-name
description: |
  【触发场景】当...
  【输入特征】"...", "..."等关键词
  【输出目标】输出一个...
  【不适用场景】不需要...时
tags: [category, subcategory]
related_skills: [other-skill-1, other-skill-2]
---
# Skill Title

Skill body content...
```

## 路由映射

| 通用路由 | Hermes 字段 | 示例 |
|----------|-------------|------|
| 触发场景 | description → 【触发场景】 | 当需要编写技能时 |
| 输入特征 | description → 【输入特征】 | "写技能"、"创建技能" |
| 输出目标 | description → 【输出目标】 | 输出 SKILL.md 文件 |
| 负样本 | description → 【不适用场景】 | 不需要创建技能时 |
| 分类 | tags | [development, planning] |
| 关联 | related_skills | [brainstorming, writing-plans] |

## 技能存放位置

```
# 默认路径
~/.hermes/skills/<category>/<skill-name>/SKILL.md

# Windows
%USERPROFILE%\AppData\Local\hermes\skills\<category>\<skill-name>\SKILL.md
```

## 优化检查清单

- [ ] description 是否包含四层结构？
- [ ] 【触发场景】是否以"当...时"开头？
- [ ] 【输入特征】是否覆盖了 3 种以上用户自然表达？
- [ ] 【输出目标】是否明确了最终产出？
- [ ] 【不适用场景】是否列出了 2 种以上误触情况？是否指向替代技能？
- [ ] tags 是否使用了双层结构（大类+小类）？
- [ ] related_skills 是否连接了上下游或同级别技能？

## 验证命令

```bash
# 统计路由覆盖率
python -c "
import os, yaml
base = os.path.join(os.environ['USERPROFILE'], 'AppData', 'Local', 'hermes', 'skills')
good = 0
total = 0
for root, dirs, files in os.walk(base):
    rel = os.path.relpath(root, base).replace(os.sep, '/')
    if any(p in rel.split('/') for p in ['.archive', '.hub', 'scripts', 'references', 'templates']):
        continue
    if 'SKILL.md' not in files:
        continue
    total += 1
    with open(os.path.join(root, 'SKILL.md')) as fh:
        parts = fh.read().split('---', 2)
    fm = yaml.safe_load(parts[1])
    desc = fm.get('description', '')
    checks = all(s in desc for s in ['【触发场景】', '【输入特征】', '【输出目标】', '【不适用场景】'])
    if checks and bool(fm.get('tags')):
        good += 1
print(f'{good}/{total} skills fully routed ({good/total*100:.0f}%)')
"
```
