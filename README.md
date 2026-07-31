# OAIW — 操作部AI工作台

> *国际货代行业的智能操作平台 · 多Agent协作 · RPA自动化 · AI知识库*

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.14-blue?logo=python" alt="Python 3.14"/>
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/Vue-3.5-4FC08D?logo=vue.js" alt="Vue 3"/>
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License"/>
</p>

---

## 📖 概述

**OAIW (Operations AI Workstation)** 是一套面向国际货运代理行业的智能化操作平台。它整合了 **多Agent AI助手**、**RPA港口自动化**、**运价解析引擎** 和 **知识库管理** 四大核心能力，旨在将货代操作人员从重复性的系统录入、港口查询、运价对比等工作中解放出来。

> 本项目诞生于真实的货代业务场景，所有功能模块均经过实际业务验证。

---

## ✨ 功能特性

### 🤖 多智能体 AI 助手

| Agent | 职责 | 技术栈 |
|-------|------|--------|
| **业务专家 (Biz)** | 运价规则解读、业务术语查询 | LLM + RAG |
| **RPA 工程师** | 港口自动化任务编排 | Playwright + OCR |
| **AI 工程师** | 意图分类、工具调用 | LangGraph Workflow |
| **后端工程师 (BE)** | 数据查询、报表生成 | FastAPI + SQLAlchemy |

- 基于 **LangGraph** 的多Agent编排引擎
- 支持 **OpenAI 兼容 API**（NVIDIA NIM / DeepSeek / Ollama）
- 向量知识库（ChromaDB）驱动的 RAG 问答
- SSE 流式输出，实时展示 Agent 思考过程

### 🏭 RPA 港口自动化

| 港口 | 验证码类型 | 方案 | 状态 |
|------|-----------|------|------|
| **蛇口港** | 文字点选验证码 | OpenCV + OCR + Vision | ✅ 生产可用 |
| **盐田港** | 滑块验证码 | Playwright + 轨迹模拟 | ✅ 生产可用 |
| **青岛港** | 数字验证码 | ddddocr | ✅ 生产可用 |
| **宁波港** | API Token | 直接 API 调用 | ✅ 生产可用 |
| **佰信系统** | 桌面客户端 | Win32 API + EasyOCR | 🚧 开发中 |

- Playwright 浏览器自动化
- 多种验证码识别方案（传统 CV + AI Vision）
- SSE 实时推送 RPA 执行日志
- 支持 Web 端远程触发和监控

### 📊 数据看板 & 管理

- 海运 / 空运 / 整柜运价管理
- 操作部数据看板（开发中）
- 用户权限管理（JWT 认证）
- 文档上传与知识库投喂

---

## 🧱 技术栈

```
后端框架     FastAPI + Uvicorn
数据库       SQLAlchemy + SQLite / MySQL
AI 引擎      LangGraph + OpenAI Compatible API
向量存储     ChromaDB + Sentence-Transformers
RPA 引擎     Playwright + OpenCV + ddddocr
前端框架     Vue 3 (Composition API) + Vite
UI 组件      Element Plus
状态管理     Pinia
路由         Vue Router 4
缓存         Redis
文档解析     PyMuPDF + python-docx + docling
```

---

## 🚀 快速开始

### 前置要求

- Python 3.11+
- Node.js 18+
- 依赖安装见下方

### 1. 克隆

```bash
git clone https://github.com/xs0364/OAIW.git
cd OAIW
```

### 2. 后端

```bash
# 创建虚拟环境
python -m venv venv
venv\Scripts\activate

# 安装依赖
pip install -r backend/requirements.txt

# 初始化数据库
python backend/seed.py

# 启动后端（端口 7999）
python -m uvicorn backend.main:app --host 0.0.0.0 --port 7999 --reload
```

### 3. 前端

```bash
cd frontend
npm install
npx vite --port 5175
```

浏览器打开 `http://localhost:5175` 即可访问。

### 4. 环境变量

复制 `.env.example` 为 `.env` 并配置：

```env
# LLM API
OPENAI_API_KEY=your_api_key_here
OPENAI_API_BASE=https://api.your-provider.com/v1

# 数据库（默认 SQLite）
DATABASE_URL=sqlite:///./oaiw.db

# JWT 密钥
SECRET_KEY=your-secret-key
```

---

## 📁 项目结构

```
OAIW/
│
├── backend/                        # FastAPI 后端
│   ├── main.py                     # 应用入口
│   ├── config.py                   # 配置管理
│   ├── database.py                 # 数据库引擎
│   ├── seed.py                     # 初始数据
│   ├── requirements.txt            # Python 依赖
│   │
│   ├── core/                       # 核心业务
│   │   ├── routers/                # API 路由
│   │   │   ├── auth.py             # 登录认证
│   │   │   ├── users.py            # 用户管理
│   │   │   ├── rpa.py              # RPA 任务 (+ SSE 流式)
│   │   │   ├── settings.py         # 系统设置
│   │   │   ├── docs.py             # 文档上传
│   │   │   ├── air_freight.py      # 空运报价
│   │   │   ├── sea_freight.py      # 海运报价
│   │   │   └── fcl.py              # 整柜报价
│   │   ├── models/                 # SQLAlchemy 模型
│   │   ├── schemas/                # Pydantic 模型
│   │   └── services/               # 业务逻辑
│   │
│   ├── addons/                     # 扩展模块
│   │   ├── llm/                    # AI 助手
│   │   │   ├── llm_service.py      # LLM 调用封装
│   │   │   ├── multi_agent.py      # 多 Agent 编排
│   │   │   ├── tools.py            # Agent 工具
│   │   │   ├── providers/          # Provider 层
│   │   │   │   ├── base.py         # 抽象基类
│   │   │   │   └── openai_compat.py # OpenAI 兼容 API
│   │   │   ├── workflow/           # LangGraph 工作流
│   │   │   │   ├── workflow.py     # 主流程
│   │   │   │   ├── state.py        # 状态定义
│   │   │   │   ├── tools.py        # 工作流工具
│   │   │   │   └── nodes/          # 工作流节点
│   │   │   └── routers/            # 聊天 API
│   │   │       ├── chat.py         # 对话接口
│   │   │       └── chat_history.py # 对话历史
│   │   ├── rag/                    # RAG 知识库
│   │   └── memory/                 # 对话记忆
│   │
│   ├── rpa/                        # RPA 引擎
│   │   ├── __init__.py             # run_browser_task() 入口
│   │   ├── clickword_solver.py     # 点选验证码求解器
│   │   ├── log_queue.py            # SSE 实时日志队列
│   │   ├── rpa_sync.py             # 任务同步管理
│   │   ├── sms_bridge.py           # 短信验证码桥接
│   │   └── ports/                  # 港口驱动
│   │       ├── shekou.py           # 🚢 蛇口港
│   │       ├── shekou_login.py     #   登录逻辑
│   │       ├── yantian.py          # 🚢 盐田港
│   │       ├── qingdao.py          # 🚢 青岛港
│   │       └── npedi.py            # 🚢 宁波港
│   │
│   ├── parser/                     # 运价解析引擎
│   └── utils/                      # 工具函数
│       └── email.py                # 邮件发送
│
├── frontend/                       # Vue 3 前端
│   ├── index.html
│   ├── vite.config.js
│   ├── package.json
│   └── src/
│       ├── main.js                 # 入口
│       ├── App.vue                 # 根组件
│       ├── api/client.js           # Axios 封装
│       ├── router/index.js         # 路由
│       ├── store/auth.js           # 认证状态
│       ├── assets/theme.css        # 主题样式
│       └── views/
│           ├── Login.vue           # 登录页
│           ├── Layout.vue          # 主布局
│           ├── Dashboard.vue       # 数据看板
│           ├── AgentChat.vue       # AI 助手
│           ├── RpaTasks.vue        # RPA 任务
│           ├── SeaFreight.vue      # 海运报价
│           ├── AirFreight.vue      # 空运报价
│           ├── FCL.vue             # 整柜报价
│           ├── Documents.vue       # 文档管理
│           ├── Knowledge.vue       # 知识库
│           ├── Settings.vue        # 系统设置
│           └── UserManagement.vue  # 用户管理
│
├── knowledge/                      # 📚 货代业务知识库
│   ├── 海运散货操作流程图.pdf
│   ├── 空运操作流程.docx
│   ├── 整柜 Flying.pdf
│   └── ...
│
├── .claude/agents/                 # 🤖 多工程师角色定义
│   ├── pm.md                       # 项目经理
│   ├── be.md                       # 后端工程师
│   ├── fe.md                       # 前端工程师
│   ├── rpa.md                      # RPA 工程师
│   ├── biz.md                      # 业务专家
│   ├── ai.md                       # AI 工程师
│   └── qa.md                       # 测试工程师
│
├── _coord_overlay.py               # 佰信桌面坐标标尺工具
├── _baixin_route.py                # 佰信自动化导航脚本
├── _start_baixin.py                # 佰信启动+登录
├── CLAUDE.md                       # 协作规范
├── AGENTS.md                       # Agent 配置
└── start.bat                       # 一键启动
```

---

## 🔄 从 0 到 200 Fork 的旅程

> **Fork 数，是别人 Fork 你仓库的次数。**
>
> 每一次 Fork，都意味着有人对你的代码产生了兴趣，愿意花时间去阅读、去修改、去尝试。它不是点赞——它是有成本的行动。

这个项目从第一天起就开源在 GitHub 上。从 0 到 1 是第一步，从 1 到 200 不是一天两天的事——它意味着：

1. **项目对别人有用** — 有人在真实场景中使用你的代码
2. **代码靠得住** — 别人 Fork 回去修改，说明他们信任你的基础
3. **社区在生长** — 每一个 Fork 背后，都是一个潜在的贡献者、一个真实的用户、一个和你解决类似问题的人

这条路很长。但每多一个 Fork，就多一个人在和这个项目一起成长。

**OAIW 的目标** — 成为货代行业最实用的开源 AI 操作平台。无论你是货代公司的 IT 团队、物流 SaaS 开发者、还是对这个行业感兴趣的 AI 工程师，这里都有一块你可以参与的地方。

如果你觉得这个项目对你有帮助——**Start 一下，Fork 一下**。让更多人看到，让这个项目活起来。

---

## 🤝 参与贡献

欢迎各种形式的贡献：

- 🐛 **提 Issue** — 发现 Bug 或建议新功能
- 🔀 **提交 PR** — Fork 仓库，修改后提交 Pull Request
- 📖 **完善文档** — 修正错别字、补充使用说明
- 💬 **分享反馈** — 告诉我们你的使用场景

### 开发流程

```bash
# 1. Fork 本仓库
# 2. Clone 你的 Fork
git clone https://github.com/你的用户名/OAIW.git

# 3. 创建特性分支
git checkout -b feat/your-feature

# 4. 修改后提交
git commit -m "feat: add your feature"

# 5. 推送到你的 Fork
git push origin feat/your-feature

# 6. 提交 Pull Request
```

> 本项目使用 7 角色多工程师协作体系（PM / FE / BE / RPA / Biz / AI / QA），详见 `.claude/agents/` 目录。如果你想了解 Agent 协作的工作方式，可以查看 `AGENTS.md`。

---

## 📄 License

[MIT License](LICENSE) © 2024-2026 OAIW Contributors

---

<p align="center">
  <sub>
    用 ❤️ 和 🐍 构建 · 
    <a href="https://github.com/xs0364/OAIW">GitHub</a> ·
    <a href="https://github.com/xs0364/OAIW/issues">Issues</a> ·
    <a href="https://github.com/xs0364/OAIW/fork">Fork</a>
  </sub>
</p>
