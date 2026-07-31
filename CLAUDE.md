# OAIW 操作部AI工作台 — 多工程师协作规范

> **本工程体系仅适用于 D:\OAIW 项目**，不可混用于其他系统。

## 技术栈
- **后端**: Python 3.14 + FastAPI + SQLAlchemy + SQLite
- **前端**: Vue 3 (Composition API) + Vite (port 5175) + Element Plus + Pinia
- **AI**: NVIDIA NIM / DeepSeek / Ollama (Gemma4)
- **RPA**: Playwright + OpenCV + ddddocr + NVIDIA NIM Vision
- **Agent**: 手写 workflow（意图→拼 prompt→调 LLM→解析）
- **文档**: OCR + LLM 提取
- **向量**: ChromaDB

## 多工程师协作体系（7角色）

| 标记 | 角色 | 职责文件 |
|------|------|---------|
| `@pm` | PM 项目经理 | `.claude/agents/pm.md` |
| `@fe` | FE 前端工程师 | `.claude/agents/fe.md` |
| `@be` | BE 后端工程师 | `.claude/agents/be.md` |
| `@rpa` | RPA 自动化工程师 | `.claude/agents/rpa.md` |
| `@biz` | 业务专家 | `.claude/agents/biz.md` |
| `@ai` | AI 人工智能工程师 | `.claude/agents/ai.md` |
| `@qa` | QA 测试工程师 | `.claude/agents/qa.md` |

### 工作流
1. **PM 拆任务** — 确定涉及哪些角色
2. **并行执行** — `@fe` + `@be` + `@rpa` + `@ai` 可并行
3. **测试验收** — `@qa` 回归 → `@pm` 验收

### 角色调用方式
在对话中引用角色以激活其职责：
```
@pm 帮我拆一下这个需求
@fe RPA 页面的日志显示需要调整
@be 加一个查柜 API
@rpa 蛇口港验证码识别失败
@biz 这个运价规则怎么理解
@ai 侧边栏 AI 助手的意图分类需要优化
@qa 跑一下港口回归测试
```

## 启动
```bash
cd D:/OAIW
# 后端（port 7999）
python -m uvicorn backend.main:app --host 0.0.0.0 --port 7999

# 前端（port 5175）
cd frontend && npx vite --port 5175
```

## 项目结构
```
OAIW/
├── backend/
│   ├── main.py              # FastAPI 入口
│   ├── config.py            # 配置 (port 7999, HEADLESS=False)
│   ├── database.py          # 数据库
│   ├── core/routers/        # API 路由
│   │   ├── auth.py          # 登录认证
│   │   ├── rpa.py           # RPA 任务 (+ /run/stream SSE)
│   │   ├── users.py         # 用户管理
│   │   ├── settings.py      # 系统设置
│   │   ├── docs.py          # 文档上传/合并
│   │   └── air_freight.py   # 空运报价
│   ├── addons/llm/          # AI 助手
│   │   ├── multi_agent.py   # 4个NIM Agent编排
│   │   ├── llm_service.py   # LLM 调用封装
│   │   ├── providers/       # Provider 层
│   │   ├── workflow/        # 聊天工作流
│   │   └── routers/         # 聊天 API
│   ├── agent/               # Agent 节点/工具
│   ├── rpa/                 # RPA 引擎
│   │   ├── __init__.py      # run_browser_task()
│   │   ├── log_queue.py     # SSE 实时日志
│   │   └── ports/           # 港口驱动
│   │       ├── shekou.py    # 蛇口港 (文字点选验证码)
│   │       ├── yantian.py   # 盐田港
│   │       ├── qingdao.py   # 青岛港 (ddddocr)
│   │       └── npedi.py     # 宁波港 (API)
│   └── parser/              # 运价解析
├── frontend/src/
│   ├── views/               # 页面
│   │   ├── AgentChat.vue    # AI 助手侧边栏
│   │   ├── RpaTasks.vue     # RPA 任务 (SSE流式)
│   │   ├── Dashboard.vue    # 数据看板
│   │   └── ...
│   ├── store/               # Pinia
│   └── api/client.js        # Axios
└── .claude/agents/          # ⭐ 工程师角色定义
    ├── pm.md
    ├── fe.md
    ├── be.md
    ├── rpa.md
    ├── biz.md
    ├── ai.md
    └── qa.md
```

## 关键约束
- Python 3.14 Windows: RPA 用 `asyncio.to_thread()` + `sync_playwright`
- 修改 `rpa/__init__.py` 后需清 `__pycache__` 重启
- 后端 port 7999，前端 port 5175
- 每次编码前读 `coding-guidelines.md` 记忆
