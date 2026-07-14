# 贡献指南

感谢你对 **Critical SkillGovern** 感兴趣！欢迎各种形式的贡献。

## 如何贡献

### 提交 Issue

- 🐛 **Bug 报告**：脚本报错、逻辑错误
- 💡 **功能建议**：新的检查项、适配新的平台
- 📚 **文档改进**：翻译、示例、格式优化
- ❓ **问题咨询**：使用中遇到困难

### 提交 PR

1. Fork 本仓库
2. 创建功能分支: `git checkout -b feature/my-feature`
3. 提交改动: `git commit -m 'feat: add support for xxx'`
4. 推送到分支: `git push origin feature/my-feature`
5. 创建 Pull Request

### 代码风格

- Python 脚本遵循 PEP 8
- Markdown 文档使用中文（专有名词除外）
- 提交信息使用 Conventional Commits 格式

## 开发指南

### 新增适配器

如果你想为新的 AI 代理平台编写适配器：

1. 在 `adapters/` 下创建 `<platform-name>.md`
2. 说明该平台的技能格式、存放位置、路由机制
3. 提供平台特有的检查清单
4. 更新 README.md 的支持平台表格

### 新增检查项

路由诊断的检查项在 `scripts/batch-review.py` 的 `check_skill_routing()` 函数中：

```python
def check_skill_routing(fm, desc):
    """Add your new check here"""
    issues = []
    
    # 示例：检查描述长度
    if len(desc) > 500:
        issues.append(('🟡', '描述过长', f'{len(desc)} 字符'))
    
    return issues
```

### 新增脚本

- 放在 `scripts/` 目录下
- 提供 argparse 参数支持
- 添加 `--help` 说明
- 支持 CSV 输出以便集成 CI/CD

## 发布流程

1. 更新版本号
2. 更新 CHANGELOG
3. 创建 GitHub Release
4. 发布到社区（可选）

## 社区准则

- 尊重所有贡献者
- 保持专业和友善
- 关注建设性反馈
- 欢迎新手贡献者
