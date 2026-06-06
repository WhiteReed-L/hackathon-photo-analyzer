# 👗 穿搭 AI 助手

基于 FastAPI 的 Web 应用，用户输入身体数据和穿搭偏好，AI 生成服装搭配效果图。

## 功能

- 🔐 用户注册/登录（必填：昵称、身高、体重；选填：三维）
- 🧭 两条搭配路径：
  - **我知道想穿什么** — 上传自己照片 + 服装参考图 + 文字描述
  - **我有一些想法** — 选择风格标签（20个）+ 场景标签（20个）+ 文字补充 + 参考图
- 📸 点击拍照按钮调用设备原生相机，或从相册选择文件
- ✨ OpenAI 图像模型生成服装搭配效果图，可通过 `OPENAI_MODEL` 配置
- 🖼️ 生成图自动下载保存到服务器，前端展示压缩预览，保存时下载原图
- 💬 结果页可继续对话调整需求
- 💾 对话历史当前保存在浏览器 localStorage，并可同步到服务端 conversations 表
- 🔒 上传和图片访问需要登录，图片会登记为用户资产

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

编辑 `.env`，填入 OpenAI API Key：

```env
OPENAI_API_KEY=sk-your-real-key-here
OPENAI_MODEL=gpt-image-2
```

### 3. 启动

```bash
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. 访问

| 页面 | 地址 |
|------|------|
| 前端 | http://localhost:8000 |
| API 文档 | http://localhost:8000/docs |

## 项目结构

```
Hackathon/
├── main.py                   # FastAPI 应用入口
├── config.py                 # 配置管理
├── database.py               # SQLite 数据库（WAL + 连接池 + 资产/任务记录）
├── models.py                 # Pydantic 数据模型
├── limiter.py                # API 速率限制
├── requirements.txt
├── .env.example
├── .gitignore
├── routes/
│   ├── user.py               # 用户注册/登录/登出/个人信息
│   ├── upload.py             # 图片上传
│   ├── generate.py           # Vision + Style Parser + 图像生成
│   ├── chat.py               # 对话意图判断
│   └── conversations.py      # 对话历史读写
├── services/
│   ├── image_gen.py          # 图像生成 + 缩略图压缩
│   ├── vision_service.py     # 用户/参考图视觉分析
│   ├── style_parser.py       # 风格解析
│   └── prompt_engine.py      # Prompt 模板
└── static/
    ├── index.html            # 单页前端（多视图状态机）
    ├── css/style.css
    └── js/
        └── app.js            # 状态管理 + 视图切换 + localStorage
```

## API 端点

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| POST | `/api/user/register` | 无 | 注册 |
| POST | `/api/user/login` | 无 | 登录 |
| POST | `/api/user/logout` | Cookie | 登出 |
| GET | `/api/user/me` | Cookie | 获取当前用户信息 |
| POST | `/api/upload` | Cookie | 上传图片（速率限制 30/min） |
| POST | `/api/generate` | Cookie | 调用 DALL-E 生图 |
| GET | `/api/conversations` | Cookie | 获取对话历史 |
| POST | `/api/conversations/sync` | Cookie | 同步 localStorage 对话到服务端 |
| GET | `/api/uploads/{filename}` | Cookie | 访问自己的图片文件 |

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python FastAPI + uvicorn |
| 数据库 | SQLite WAL 模式 + aiosqlite 连接池 |
| AI | OpenAI Chat/Vision/Image APIs |
| 前端 | 原生 HTML/CSS/JavaScript（无框架） |
| 图片压缩 | Pillow（600px JPEG 预览 + 原图保留） |

## 配置项

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `OPENAI_API_KEY` | — | OpenAI API Key（必填） |
| `OPENAI_MODEL` | `dall-e-3` | AI 生图模型 |
| `UPLOAD_DIR` | `uploads` | 图片存储目录 |
| `MAX_UPLOAD_SIZE_MB` | `10` | 上传大小限制 |
| `UPLOAD_RATE_LIMIT` | `30/minute` | 上传速率限制 |
| `AUTH_RATE_LIMIT` | `10/minute` | 登录/注册速率限制 |
| `GENERATE_RATE_LIMIT` | `5/minute` | 生图速率限制 |
| `CHAT_RATE_LIMIT` | `30/minute` | 聊天速率限制 |
| `COOKIE_SECURE` | `false` | 生产 HTTPS 环境建议设为 true |
| `MAX_IMAGE_PIXELS` | `25000000` | 上传图片最大像素数 |
| `DATABASE_PATH` | `photos.db` | 数据库文件路径 |
| `DB_POOL_SIZE` | `5` | 数据库连接池大小 |
| `DB_BUSY_TIMEOUT_MS` | `5000` | 数据库写锁等待超时（ms） |

## Prompt 自定义

生图 prompt 在 `services/prompt_engine.py` 中集中管理：

- 身份提取 prompt
- 风格解析 prompt
- 换装生成 prompt

修改后重启服务器即可生效，无需改动前端代码。
