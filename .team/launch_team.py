"""OAIW 7 Agent 启动器 v7 — 修复 --agent 类型问题"""
import json
import subprocess
import time
import os

ROOT = r"D:\OAIW"
CLAUDE_EXE = r"D:\download\reasonix\node_modules\@anthropic-ai\claude-code\bin\claude.exe"
AGENTS_FILE = os.path.join(ROOT, ".team", "agents.json")

with open(AGENTS_FILE, "r", encoding="utf-8") as f:
    agents = json.load(f)

ROLES = ["pm", "fe", "be", "rpa", "biz", "ai", "qa"]
LABELS = {"pm": "PM", "fe": "FE", "be": "BE", "rpa": "RPA", "biz": "Biz", "ai": "AI", "qa": "QA"}

# 清理旧进程
os.system("taskkill /f /im claude.exe 2>nul")
time.sleep(3)

for role in ROLES:
    label = LABELS[role]
    agent = agents[role]

    # agent JSON 文件
    single = {role: {"description": agent["description"], "prompt": agent["prompt"]}}
    with open(os.path.join(ROOT, ".team", f"agent_{role}.json"), "w", encoding="utf-8") as f:
        json.dump(single, f, ensure_ascii=False, indent=2)

    # Python runner — 关键修复：--agent general-purpose（用自定义prompt区分角色）
    runner_code = f'''import subprocess, json, os, sys
os.chdir(r"{ROOT}")
with open(r"{ROOT}\\.team\\agent_{role}.json", "r", encoding="utf-8") as f:
    agent_json = f.read().strip()
# --agent general-purpose: Claude Code内置类型
# --agents: 自定义角色prompt定义
cmd = [r"{CLAUDE_EXE}", "--agent", "general-purpose", "--agents", agent_json]
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
subprocess.run(cmd)
input("Agent exited. Press Enter to close...")
'''
    with open(os.path.join(ROOT, ".team", f"agent_{role}_runner.py"), "w", encoding="utf-8") as f:
        f.write(runner_code)

    # .bat 启动器
    bat = (
        '@echo off\r\n'
        f'cd /d {ROOT}\r\n'
        f'title OAIW-{label}\r\n'
        'chcp 65001 >nul\r\n'
        'cls\r\n'
        'echo ========================================\r\n'
        f'echo   OAIW Agent Team - {label}({role})\r\n'
        'echo ========================================\r\n'
        'echo.\r\n'
        'echo Tasks: .team\\tasks\\  Results: .team\\results\\\r\n'
        'echo.\r\n'
        f'python .team\\agent_{role}_runner.py\r\n'
        'pause\r\n'
    )
    with open(os.path.join(ROOT, ".team", f"launch_{role}.bat"), "w", encoding="utf-8") as f:
        f.write(bat)

    print(f"  [OK] {label} files ready")

# 启动所有窗口
print()
print("=" * 45)
print(" Launching 7 Agent windows...")
print("=" * 45)
print()

for role in ROLES:
    label = LABELS[role]
    bat_path = os.path.join(ROOT, ".team", f"launch_{role}.bat")
    subprocess.Popen(f'start "OAIW-{label}" cmd /c "{bat_path}"', shell=True)
    time.sleep(2)
    print(f"  [OK] {label} window launched")

print()
print("=" * 45)
print(" All 7 Agent windows launched!")
print(" All use --agent general-purpose + custom --agents prompt")
print("=" * 45)
print()
print("Try: python .team\\pm_dispatch.py board")
