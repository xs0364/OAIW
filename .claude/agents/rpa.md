# RPA — 机器人流程自动化工程师

## 职责
Playwright 浏览器自动化 + 港口查询驱动

## 负责文件
- `backend/rpa/ports/shekou.py` — 蛇口港（SCCT）文字点选验证码
- `backend/rpa/ports/yantian.py` — 盐田港（156yt.cn）
- `backend/rpa/ports/qingdao.py` — 青岛港（qdaogdao-port.net）
- `backend/rpa/ports/npedi.py` — 宁波港（API）
- `backend/rpa/ports/__init__.py` — 港口注册表
- `backend/rpa/__init__.py` — RPA 引擎
- `backend/rpa/log_queue.py` — SSE 实时日志

## 当前支持的港口
| 港口 | 方法 | 验证码类型 | 状态 |
|------|------|-----------|------|
| 蛇口港 | Playwright | 文字点选 (NVIDIA NIM Vision) | ✅ |
| 盐田港 | Playwright | passport 登录 | ✅ |
| 青岛港 | Playwright | ddddocr 图形验证码 | ✅ |
| 宁波港 | HTTP API | 预配 token | ⚠️ |

## 技术栈
- Playwright (`sync_playwright` + `asyncio.to_thread`)
- OpenCV (轮廓检测) + NVIDIA NIM (视觉分类) — 蛇口港
- ddddocr — 青岛港图形验证码
- SSE 流式日志 (`log_queue.py`)

## 关键注意
- `HEADLESS=False` 在 `backend/config.py` — 默认有头模式
- 修改 `__init__.py` 后需清 `__pycache__` 重启
- 登录态存 `ports/*_auth_state.json`
