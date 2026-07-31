# AI — 人工智能工程师

## 职责
侧边栏 AI 助手全部功能 + LLM 集成 + 智能体编排

## 负责文件
- `backend/addons/llm/multi_agent.py` — 4个NIM Agent编排
- `backend/addons/llm/llm_service.py` — LLM调用封装
- `backend/addons/llm/providers/` — Provider层
- `backend/addons/llm/workflow/` — 聊天工作流
- `backend/addons/llm/routers/chat.py` — 流式+非流式聊天端点
- `backend/agent/` — Agent节点和工具
- `frontend/src/views/AgentChat.vue` — 聊天界面

## 当前AI助手能力
| 能力 | 状态 |
|------|------|
| 自动路由 (多Agent) | ✅ |
| 手动切换Agent | ✅ |
| 并行Agent | ✅ |
| 意图识别 (查码头/运价/保函等) | ✅ |
| Tool Calling (prompt模拟) | ⚠️ 需升级 |
| 执行结果回传 | ❌ |
| Vision 多模态 | ⏳ Step 1完成，Step 2-5待完成 |

## 待完成项
1. **Tool Calling 升级** — 从 prompt 模拟到标准 Function Calling
2. **执行闭环** — 模型知道工具执行结果
3. **Vision 多模态** — Step 2-5
4. **行业知识增强** — 港口/船公司/航线知识库
5. **意图分类扩展** — 更多业务场景

## 注意
- `multi_agent.py` 需要 NVIDIA NIM API Key（从 settings 表读取）
- 4个预置Agent: GPT-OSS 120B / Qwen3-Next 80B / MiniMax M2.7 / Nemotron Super 120B
