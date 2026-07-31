# FE — 前端工程师

## 职责
所有 Vue 3 + Element Plus 前端开发和维护

## 负责文件
- `frontend/src/views/*.vue` — 所有页面组件
- `frontend/src/api/client.js` — API 调用层
- `frontend/src/router/` — 路由配置
- `frontend/src/store/` — Pinia 状态管理

## 关键页面
- **AgentChat.vue** — AI 助手聊天界面（侧边栏）
- **RpaTasks.vue** — RPA 任务页面（SSE流式日志渲染）
- **Dashboard.vue** — 数据看板
- **FCL.vue / SeaFreight.vue / AirFreight.vue** — 海运/空运报价
- **Settings.vue** — 系统设置
- **Login.vue** — 登录页
- **Layout.vue** — 主布局+侧边栏

## 技术栈
- Vue 3 Composition API (`<script setup>`)
- Element Plus 组件库
- Pinia 状态管理
- Axios（`client.js` 封装）
- Vite 构建（端口 5175）

## 注意事项
- 开发服务器: `http://localhost:5175`
- API 代理到 `http://127.0.0.1:7999`
- 修改后无需手动重启，Vite HMR 自动更新
