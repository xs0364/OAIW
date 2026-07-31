# QA — 测试工程师

## 职责
全链路测试、回归测试、边界测试

## 测试范围

### API 测试
- `backend/core/routers/` 下所有端点
- 正常流程 + 错误参数 + 边界值
- Auth 验证（无token / 过期token）

### 港口驱动回归测试
| 港口 | 测试内容 |
|------|---------|
| 蛇口港 | 完整登录→验证码识别→查柜→结果解析 |
| 盐田港 | passport登录→查柜→结果正确 |
| 青岛港 | ddddocr验证码→单箱查询→API捕获 |
| 宁波港 | Token认证→API调用→结果解析 |

### RPA 引擎测试
- `backend/rpa/run` — 普通API
- `backend/rpa/run/stream` — SSE流式日志
- 登录态过期 → 自动重新登录
- 多轮验证码

### 前台功能测试（Playwright）
- RPA 页面 SSE 日志滚动渲染
- AI 助手多渠道切换/并行
- 运价页面显示

## 测试方法
- API: `pytest` + `httpx`
- 港口驱动: `timeout` + `json` 结果验证
- 前台: 手动或 Playwright 截图对比
