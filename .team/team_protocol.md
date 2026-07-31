# OAIW 7 Agent 多CLI窗口团队协议

## 架构

每个角色在独立 CLI 窗口运行 `claude --agent <角色名>`，通过 `D:\OAIW\.team\` 文件系统共享上下文。

```
┌─ 👔 PM (本窗口) ──────────────────────┐
│  你在这里跟PM对话，PM负责拆任务分配      │
│  所有Agent的状态实时可见                │
└────────────────────────────────────────┘

独立CLI窗口（各司其职）:
  🎨 FE  → claude --agent fe    ⚙️ BE  → claude --agent be
  🤖 RPA → claude --agent rpa   📊 Biz → claude --agent biz
  🧠 AI  → claude --agent ai    🧪 QA  → claude --agent qa
```

## 文件通信协议

### 📥 任务文件 (`.team/tasks/<ID>_<角色>.json`)
PM 写入，Agent 读取：
```json
{
  "id": "TASK-001",
  "from": "pm",
  "to": "fe",
  "title": "开发登录页面",
  "description": "具体任务描述",
  "priority": "high",
  "context_refs": ["context.json#current_sprint"],
  "depends_on": ["TASK-000"],
  "created_at": "2026-07-09T12:00:00"
}
```

### 📤 结果文件 (`.team/results/<ID>_<角色>_done.json`)
Agent 完成写入，PM 读取验收：
```json
{
  "id": "TASK-001",
  "from": "fe",
  "status": "done",
  "summary": "完成了xxx",
  "files_changed": ["frontend/src/views/Login.vue"],
  "notes": "需要留意xxx",
  "completed_at": "2026-07-09T14:00:00"
}
```

### 📋 共享上下文 (`.team/context.json`)
所有角色读写，记录项目全局状态：
```json
{
  "project": "OAIW",
  "current_sprint": "Sprint 5",
  "active_tasks": ["TASK-001", "TASK-002"],
  "decisions": [
    {"date": "2026-07-09", "decision": "使用Vite作为构建工具", "reasoner": "pm"}
  ]
}
```

## 工作流

1. **PM 拆任务** → 写 `.team/tasks/<ID>_<角色>.json`
2. **Agent 看到任务** → 读文件，开始工作
3. **Agent 完成** → 写 `.team/results/<ID>_<角色>_done.json`
4. **PM 验收** → 读结果，通知用户
5. **QA 介入** → PM 分配 QA 任务，QA 测试后回报

## Agent 行为准则

1. 启动时先读 `context.json` 了解项目状态
2. 定期扫描 `tasks/` 目录看是否有新任务
3. 任务完成后立即写结果文件
4. 发现共享上下文过期时更新 `context.json`
