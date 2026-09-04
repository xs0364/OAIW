# OAIW — 操作部AI工作台

> *国际货代行业的智能操作平台 · 多Agent协作 · RPA港口自动化与船期查询 · 佰信桌面合并录入 · AI知识库*

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.14-blue?logo=python" alt="Python 3.14"/>
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/Vue-3.5-4FC08D?logo=vue.js" alt="Vue 3"/>
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License"/>
</p>

---

## 📖 概述

**OAIW (Operations AI Workstation)** 是一套面向国际货运代理行业的智能化操作平台。它整合了 **多Agent AI助手**、**RPA 港口自动化（含四港船期直查）**、**佰信桌面系统合并录入**、**运价解析引擎** 与 **知识库管理** 等能力，旨在将货代操作人员从重复性的系统录入、港口查询、运价对比等工作中解放出来。

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

- 基于 **LangGraph** 的多Agent编排引擎（Workflow 状态机 + 工具调用）
- 支持 **OpenAI 兼容 API**（NVIDIA NIM / DeepSeek / Ollama）
- 向量知识库（ChromaDB）驱动的 RAG 问答
- 多轮对话历史持久化，可回溯复盘
- Agent 工具链：docx 模板填写（电放/非危保函）、代发邮件到用户指定邮箱（独立 SMTP）、知识库检索
- SSE 流式输出，实时展示 Agent 思考过程

### 🏭 RPA 港口自动化

| 港口 | 验证码类型 | 方案 | 状态 |
|------|-----------|------|------|
| **蛇口港** | 文字点选验证码 | OpenCV + OCR + Vision | ✅ 生产可用 |
| **盐田港** | 滑块验证码 | Playwright + 轨迹模拟 | ✅ 生产可用 |
| **青岛港** | 数字验证码 | ddddocr | ✅ 生产可用 |
| **宁波港** | API Token | 直接 API 调用 | ✅ 生产可用 |
| **佰信系统** | 桌面客户端 | Win32/UIA + 坐标模板 | ✅ 订舱/合并录入（海运） |

- Playwright 浏览器自动化
- 多种验证码识别方案（传统 CV + AI Vision）
- SSE 实时推送 RPA 执行日志，任务页支持「仅显示结果」精简回显
- 支持 Web 端远程触发和监控

**🚢 港口船期查询**（RPA 任务页「船期查询」卡片，按船名/航次直查港口系统）

| 港口 | 登录方式 | 说明 |
|------|---------|------|
| 盐田港 | 滑块验证码 | 按船名查询，0 记录自动重试 |
| 蛇口港 | 反自动化防护 | 工作台子应用，双字段过滤 |
| 宁波港 | API Token / SMS | 短信登录态桥接 |

### 📊 数据看板 & 管理

- 海运 / 空运 / 整柜 FCL 运价管理 + 费用模块
- 箱号标准化查询（容器箱号识别/校验）
- 用户管理：角色权限（JWT 认证）、**实时在线状态**（前端心跳保活 + 在线/离线列）、通知设置、修改密码
- 邮件设置：每个账号独立 SMTP 配置，支持 AI 助手代发到指定邮箱
- 佰信合并录入工作台（服务器编排 + 本机 Agent 驱动桌面端）
- 操作部数据看板
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
│   │   │   ├── auth.py             # 登录认证 / 心跳保活 / 通知设置
│   │   │   ├── users.py            # 用户管理
│   │   │   ├── rpa.py              # RPA 任务 (+ SSE 流式)
│   │   │   ├── settings.py         # 系统设置
│   │   │   ├── docs.py             # 文档上传
│   │   │   ├── air_freight.py      # 空运报价
│   │   │   ├── sea_freight.py      # 海运报价
│   │   │   ├── fcl.py              # 整柜报价
│   │   │   ├── merge.py            # 佰信合并录入
│   │   │   ├── standardize.py      # 箱号标准化
│   │   │   ├── fee.py              # 运费/费用
│   │   │   └── email_config.py     # 用户独立 SMTP 配置
│   │   ├── models/                 # SQLAlchemy 模型
│   │   │   ├── air_freight.py      # 空运
│   │   │   ├── fcl_order.py        # 整柜订单
│   │   │   ├── container_standardize.py  # 箱号标准化
│   │   │   ├── user_smtp_config.py       # 用户 SMTP 配置
│   │   │   └── setting.py          # 系统设置键值
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
│   │       ├── shekou.py           # 🚢 蛇口港（船期查询）
│   │       ├── shekou_login.py     #   登录逻辑
│   │       ├── yantian.py          # 🚢 盐田港（船期查询）
│   │       ├── qingdao.py          # 🚢 青岛港
│   │       └── npedi.py            # 🚢 宁波港（SMS 桥接 + 船期查询）
│   │       # 注：各港 *_auth_state.json / *_token.txt 登录凭据不入库
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
│           ├── Layout.vue          # 主布局（60s 心跳保活）
│           ├── Dashboard.vue       # 数据看板
│           ├── AgentChat.vue       # AI 助手
│           ├── RpaTasks.vue        # RPA 任务 / 船期查询
│           ├── MergeFill.vue       # 佰信合并录入
│           ├── ContainerStandardize.vue  # 箱号标准化
│           ├── EmailConfig.vue     # 邮箱设置
│           ├── SeaFreight.vue      # 海运报价
│           ├── AirFreight.vue      # 空运报价
│           ├── FCL.vue             # 整柜报价
│           ├── Documents.vue       # 文档管理
│           ├── Knowledge.vue       # 知识库
│           ├── Settings.vue        # 系统设置
│           └── UserManagement.vue  # 用户管理（在线状态）
│
├── knowledge/                      # 📚 货代业务知识库（内部资料，不随公开仓库分发）
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
├── .team/                          # 🤖 7 角色多Agent 团队运行时
├── .claude/agents/                 # 角色定义
├── _baixin_fill_template.json      # 佰信坐标录入模板（本地 Agent 配套）
├── CLAUDE.md                       # 协作规范
├── AGENTS.md                       # Agent 配置
└── start.bat                       # 一键启动
```


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
