"""OAIW 7 Agent 多CLI窗口团队启动器"""
import json
import subprocess
import time
import os

ROOT = r"D:\OAIW"
AGENTS_FILE = os.path.join(ROOT, ".team", "agents.json")

with open(AGENTS_FILE, "r", encoding="utf-8") as f:
    agents = json.load(f)

ROLES = ["pm", "fe", "be", "rpa", "biz", "ai", "qa"]
ICONS = {"pm": "👔", "fe": "🎨", "be": "⚙️", "rpa": "🤖", "biz": "📊", "ai": "🧠", "qa": "🧪"}

print("=" * 45)
print(" OAIW 7 Agent 多CLI窗口团队 启动器")
print("=" * 45)
print()

for role in ROLES:
    icon = ICONS[role]
    agent = agents[role]

    single = json.dumps(
        {role: {"description": agent["description"], "prompt": agent["prompt"]}},
        ensure_ascii=False,
    )

    ps_script = f'''$env:CLAUDE_CODE_SIMPLE = "1"
Set-Location '{ROOT}'
Write-Host '╔════════════════════════════════════╗' -ForegroundColor Cyan
Write-Host '║   OAIW {icon} {role.upper()} ' -ForegroundColor Cyan
Write-Host '╚════════════════════════════════════╝' -ForegroundColor Cyan
Write-Host ''
Write-Host '等待PM分配任务中...' -ForegroundColor Yellow
Write-Host '任务: .team\\tasks\\ | 结果: .team\\results\\' -ForegroundColor DarkGray
claude --agent '{role}' --agents '{single}'
'''
    ps_path = os.path.join(ROOT, ".team", f"launch_{role}.ps1")
    with open(ps_path, "w", encoding="utf-8") as f:
        f.write(ps_script)

    subprocess.Popen(
        ["powershell", "-NoExit", "-ExecutionPolicy", "Bypass", "-File", ps_path],
        shell=True,
    )
    time.sleep(1.5)
    print(f"  ✅ {icon} {role} 窗口已启动")

print()
print("🎉 全部7个Agent窗口已启动！")
print("你在当前窗口以 PM 身份与团队协作。")
