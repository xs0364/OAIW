"""OAIW 7 Agent 启动器 — 写 .bat 文件并启动"""
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

for role in ROLES:
    label = LABELS[role]
    agent = agents[role]

    # 构建 agents JSON
    single = {role: {"description": agent["description"], "prompt": agent["prompt"]}}
    json_str = json.dumps(single, ensure_ascii=False)

    # BAT 中的引号转义：JSON 内的 " → """（三重引号在cmd中安全）
    safe_json = json_str.replace('"', '"""')

    bat = (
        '@echo off\r\n'
        f'cd /d {ROOT}\r\n'
        f'title OAIW-{label}\r\n'
        'chcp 65001 >nul\r\n'
        'cls\r\n'
        'echo ========================================\r\n'
        f'echo   OAIW Agent Team - {label}\r\n'
        'echo ========================================\r\n'
        'echo.\r\n'
        'echo Check tasks: dir .team\\tasks\\ /b\r\n'
        'echo Results in: .team\\results\\\r\n'
        'echo.\r\n'
        # claude.exe 直接启动，% 在bat里本身是特殊字符，但json里没有%所以安全
        f'start "OAIW-{label}" /wait "{CLAUDE_EXE}" --agent "{role}" --agents "{safe_json}"\r\n'
        'echo.\r\n'
        'pause\r\n'
    )

    bat_path = os.path.join(ROOT, ".team", f"launch_{role}.bat")
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write(bat)

    print(f"  [OK] launch_{role}.bat written")
