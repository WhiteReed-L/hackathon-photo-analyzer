# 贡献指南

欢迎参与 Hackathon Photo Analyzer 项目！

## 参与方式

### 方式 1：直接成为协作者

联系项目维护者，将你的 GitHub 用户名添加到仓库的 Collaborators 列表中，获得直接 push 权限。

### 方式 2：Fork + Pull Request

1. **Fork** — 点击仓库右上角 Fork 按钮，复制到你自己的 GitHub 账号下
2. **Clone** — `git clone https://github.com/你的用户名/hackathon-photo-analyzer.git`
3. **创建分支** — `git checkout -b feature/你的功能名`
4. **开发** — 修改代码并测试
5. **提交** — `git commit -m "描述你的改动"`
6. **推送** — `git push origin feature/你的功能名`
7. **提 PR** — 前往原仓库，点击 Pull Requests → New Pull Request

## 开发环境搭建

```bash
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 填入 OpenAI API Key（可选）
python -m uvicorn main:app --reload
```

## 代码规范

- Python: 遵循 PEP 8
- JavaScript: 使用 ES6+ 语法
- 提交信息: 使用中文或英文，描述清晰

## 报告问题

在 Issues 页面提交 Bug 报告或功能请求，请包含：
- 问题的详细描述
- 复现步骤
- 期望行为 vs 实际行为
- 浏览器和操作系统版本
