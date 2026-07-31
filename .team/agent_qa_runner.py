import subprocess, json, os, sys
os.chdir(r"D:\OAIW")
with open(r"D:\OAIW\.team\agent_qa.json", "r", encoding="utf-8") as f:
    agent_json = f.read().strip()
# --agent general-purpose: Claude Code内置类型
# --agents: 自定义角色prompt定义
cmd = [r"D:\download\reasonix\node_modules\@anthropic-ai\claude-code\bin\claude.exe", "--agent", "general-purpose", "--agents", agent_json]
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
subprocess.run(cmd)
input("Agent exited. Press Enter to close...")
