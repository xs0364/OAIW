import subprocess, json, os, time
os.chdir(r"D:\OAIW")
# 读 agents.json 获取当前角色的 prompt
with open(".team/agents.json", "r", encoding="utf-8") as f:
    all_agents = json.load(f)
agent = all_agents["ai"]
# 启动 claude
cmd = ["claude", "--agent", "ai", "--agents", json.dumps({"ai": agent}, ensure_ascii=False)]
subprocess.run(cmd)
