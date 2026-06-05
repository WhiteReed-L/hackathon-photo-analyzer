# 📸 Hackathon Photo Analyzer

一个基于 FastAPI 的 Web 应用，用户可以通过浏览器拍摄照片并上传，管理员可查看所有照片并使用 OpenAI 大模型进行 AI 分析。

## 功能

### 用户端
- 📷 浏览器访问设备相机，实时预览
- 📸 拍照 & 预览
- ☁️ 一键上传至服务器
- 📁 相机不可用时，支持文件选择/拖拽上传（JPEG / PNG）

### 管理端
- 🔒 密码认证登录
- 🖼️ 照片画廊（网格布局，按上传时间倒序）
- 🔍 点击照片查看大图和详情
- 🤖 调用 OpenAI GPT-4o-mini 对照片进行 AI 分析
- 📝 分析结果结构化展示（场景、人物、氛围、技术细节、观察）

## 快速开始

### 1. 安装依赖

```bash
cd Hackathon
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入真实的 OpenAI API Key：

```env
OPENAI_API_KEY=sk-your-real-key-here
ADMIN_PASSWORD=hackathon2026
```

> 如果暂时不需要 AI 分析功能，可以留空 API Key，其他功能不受影响。

### 3. 启动服务器

```bash
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. 访问

| 页面 | 地址 |
|------|------|
| 用户拍照页 | http://localhost:8000 |
| 管理后台 | http://localhost:8000/admin.html |
| API 文档 | http://localhost:8000/docs |

## 项目结构

```
Hackathon/
├── main.py                 # FastAPI 应用入口
├── config.py               # 配置管理
├── database.py             # SQLite 数据库操作
├── models.py               # Pydantic 数据模型
├── requirements.txt        # Python 依赖
├── .env.example            # 环境变量模板
├── .gitignore
├── routes/
│   ├── auth.py             # 管理员认证
│   ├── upload.py           # 照片上传
│   └── admin.py            # 管理后台 API
├── services/
│   └── llm.py              # OpenAI Vision API 集成
└── static/
    ├── index.html          # 用户拍照页面
    ├── admin.html          # 管理后台页面
    ├── css/style.css       # 样式
    └── js/
        ├── camera.js       # 相机 & 上传逻辑
        └── admin.js        # 管理面板逻辑
```

## API 端点

| 方法 | 路径 | 需要认证 | 说明 |
|------|------|----------|------|
| POST | `/api/upload` | 否 | 上传照片文件（multipart/form-data） |
| POST | `/api/admin/login` | 否 | 管理员登录 |
| POST | `/api/admin/logout` | 否 | 管理员登出 |
| GET | `/api/admin/check` | Cookie | 检查登录状态 |
| GET | `/api/photos` | Cookie | 照片列表（`?limit=50&offset=0`） |
| GET | `/api/photos/{id}` | Cookie | 单张照片详情 |
| POST | `/api/photos/{id}/analyze` | Cookie | 调用 OpenAI 分析照片 |
| GET | `/api/uploads/{filename}` | 否 | 访问图片文件 |

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python FastAPI + uvicorn |
| 数据库 | SQLite (aiosqlite) |
| AI 模型 | OpenAI GPT-4o-mini (Vision) |
| 前端 | 原生 HTML/CSS/JavaScript |
| 图片存储 | 本地文件系统 (UUID 命名) |

## 默认配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| 端口 | 8000 | uvicorn 监听端口 |
| 管理员密码 | hackathon2026 | 通过 `ADMIN_PASSWORD` 环境变量修改 |
| 上传大小限制 | 10 MB | 通过 `MAX_UPLOAD_SIZE_MB` 修改 |
| 允许的文件格式 | .jpg .jpeg .png | 通过 `ALLOWED_EXTENSIONS` 修改 |
| Session 有效期 | 24 小时 | 服务端自动清理过期 session |
