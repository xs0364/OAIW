#!/usr/bin/env python3
"""
OAIW PM 任务派发工具

用法:
  python .team/pm_dispatch.py <角色> <标题> [描述]

示例:
  python .team/pm_dispatch.py be "加一个查询港口状态的API端点"
  python .team/pm_dispatch.py fe "AgentChat.vue 加一呼百应协作模式" "在AI引擎选择器中添加collaborate选项"
  python .team/pm_dispatch.py rpa "修复蛇口港验证码识别" "当前识别率只有60%，需要优化"

角色列表:
  pm  - 项目经理 (PM)
  fe  - 前端工程师 (FE)
  be  - 后端工程师 (BE)
  rpa - RPA自动化 (RPA)
  biz - 业务专家 (Biz)
  ai  - AI工程师 (AI)
  qa  - 测试工程师 (QA)
"""
import json
import os
import sys
import glob
from datetime import datetime


ROOT = r"D:\OAIW"
TASKS_DIR = os.path.join(ROOT, ".team", "tasks")
RESULTS_DIR = os.path.join(ROOT, ".team", "results")
ROLES = {
    "pm": ("PM", "项目经理"),
    "fe": ("FE", "前端工程师"),
    "be": ("BE", "后端工程师"),
    "rpa": ("RPA", "RPA自动化"),
    "biz": ("Biz", "业务专家"),
    "ai": ("AI", "AI工程师"),
    "qa": ("QA", "测试工程师"),
}
NEXT_ID_FILE = os.path.join(ROOT, ".team", ".next_task_id")


def get_next_id():
    """获取下一个任务ID"""
    if os.path.exists(NEXT_ID_FILE):
        with open(NEXT_ID_FILE, "r") as f:
            try:
                return int(f.read().strip()) + 1
            except:
                return 1
    return 1


def save_next_id(task_id):
    with open(NEXT_ID_FILE, "w") as f:
        f.write(str(task_id))


def list_tasks(status_filter=None):
    """列出所有任务"""
    tasks = []
    for f in sorted(glob.glob(os.path.join(TASKS_DIR, "*.json"))):
        with open(f, "r", encoding="utf-8") as fh:
            try:
                task = json.load(fh)
                filename = os.path.basename(f)
                parts = filename.replace(".json", "").split("_", 1)
                task["_file"] = filename
                task["_id_display"] = parts[0]
                task["_role"] = parts[1] if len(parts) > 1 else "?"
                tasks.append(task)
            except:
                tasks.append({"_file": os.path.basename(f), "_error": True})

    results = []
    for f in sorted(glob.glob(os.path.join(RESULTS_DIR, "*.json"))):
        with open(f, "r", encoding="utf-8") as fh:
            try:
                r = json.load(fh)
                filename = os.path.basename(f)
                r["_file"] = filename
                results.append(r)
            except:
                pass

    return tasks, results


def display_board():
    """显示任务看板"""
    tasks, results = list_tasks()

    print()
    print("=" * 60)
    print("  OAIW 团队任务看板")
    print("=" * 60)

    if not tasks and not results:
        print("  (暂无任务)")
        print()
        return

    # 待办任务
    pending = [t for t in tasks if not any(r.get("id") == t.get("id") for r in results)]
    done_tasks = []
    done_ids = set()
    for r in results:
        done_ids.add(r.get("id"))
        done_tasks.append(r)

    if pending:
        print(f"\n  [待办] ({len(pending)}):")
        for t in pending:
            role_key = t.get("to", t.get("_role", "?"))
            r_info = ROLES.get(role_key, (role_key, role_key.upper()))
            rid = f"{r_info[1]}({r_info[0]})"
            print(f"    [{t.get('id', t.get('_id_display', '?'))}] -> {rid} | {t.get('title', '?')}")

    if results:
        print(f"\n  [已完成] ({len(results)}):")
        for r in results:
            role_key = r.get("from", "?")
            r_info = ROLES.get(role_key, (role_key, role_key.upper()))
            rid = f"{r_info[1]}({r_info[0]})"
            status_icon = "[OK]" if r.get("status") == "done" else "[!]"
            print(f"    {status_icon} [{r.get('id', '?')}] <- {rid} | {r.get('summary', '?')[:50]}")

    print()


def dispatch(role, title, description=""):
    """派发任务"""
    if role not in ROLES:
        print(f"❌ 未知角色: {role}")
        print(f"   可用角色: {', '.join(ROLES.keys())}")
        return

    task_id = get_next_id()

    task = {
        "id": f"TASK-{task_id:03d}",
        "from": "pm",
        "to": role,
        "title": title,
        "description": description,
        "priority": "normal",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    filename = f"TASK-{task_id:03d}_{role}.json"
    filepath = os.path.join(TASKS_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(task, f, ensure_ascii=False, indent=2)

    save_next_id(task_id)

    name_en, name_cn = ROLES[role]
    print(f"\n  [完成] 任务已派发: TASK-{task_id:03d} -> {name_cn}({name_en})")
    print(f"    标题: {title}")
    if description:
        print(f"    描述: {description}")
    print(f"    文件: .team\\tasks\\{filename}")
    print(f"\n    去 {name_cn}({name_en}) 窗口告诉它：新任务到了！")
    print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        display_board()
        sys.exit(0)

    if sys.argv[1] == "board":
        display_board()
        sys.exit(0)

    if sys.argv[1] == "clean":
        # 清理已完成任务的task文件
        _, results = list_tasks()
        done_ids = set(r.get("id") for r in results)
        for f in glob.glob(os.path.join(TASKS_DIR, "*.json")):
            with open(f, "r", encoding="utf-8") as fh:
                try:
                    t = json.load(fh)
                    if t.get("id") in done_ids:
                        os.remove(f)
                        print(f"  已清理: {os.path.basename(f)}")
                except:
                    pass
        sys.exit(0)

    role = sys.argv[1]
    title = sys.argv[2] if len(sys.argv) > 2 else ""
    description = " ".join(sys.argv[3:]) if len(sys.argv) > 3 else ""

    if not title:
        print("❌ 请提供任务标题")
        sys.exit(1)

    dispatch(role, title, description)
