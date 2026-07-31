# BE — 后端工程师

## 职责
所有 FastAPI 后端开发和维护

## 负责文件
- `backend/core/routers/*.py` — 所有 API 端点
- `backend/config.py` — 系统配置
- `backend/database.py` — 数据库连接
- `backend/main.py` — 应用入口
- `backend/rpa/__init__.py` — RPA 引擎层
- `backend/rpa/log_queue.py` — SSE 实时日志队列

## API 路由
| 路径 | 功能 |
|------|------|
| `/api/auth/*` | 用户认证 |
| `/api/users` | 用户管理 |
| `/api/rpa/run` | RPA 任务（普通） |
| `/api/rpa/run/stream` | RPA 任务（SSE流式） |
| `/api/settings/*` | 系统设置 |
| `/api/docs/*` | 文档上传/合并 |
| `/api/chat/*` | AI 助手聊天 |

## 关键约束
- Python 3.14 Windows 不支持 asyncio 子进程
  → RPA 用 `asyncio.to_thread()` + `sync_playwright`
- SSE 端点不能带 auth（SSE + Bearer 头有兼容问题）
  → 前端通过 Vite proxy 代理加头

## 启动
```bash
cd D:/OAIW
python -m uvicorn backend.main:app --host 0.0.0.0 --port 7999
```
