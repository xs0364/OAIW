"""检查佰信当前状态"""
import sys, win32gui, time
sys.stdout.reconfigure(encoding='utf-8')

print("=== 所有可见窗口 ===")
def cb(h, _):
    if win32gui.IsWindowVisible(h):
        r = win32gui.GetWindowRect(h)
        w = r[2]-r[0]; hgt = r[3]-r[1]
        if w > 0 or hgt > 0:
            cls = win32gui.GetClassName(h)
            txt = win32gui.GetWindowText(h)[:60]
            print(f"  [{cls}] '{txt}' ({r[0]},{r[1]})-({r[2]},{r[3]}) {w}x{hgt}")
    return True
win32gui.EnumWindows(cb, None)

# Check all BestLOG windows
print("\n=== BestLOGFW进程窗口 ===")
import subprocess
r = subprocess.run(['tasklist', '/fi', 'imagename eq BestLOGFW.exe'], capture_output=True, text=True)
print(r.stdout)
