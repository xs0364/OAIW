"""检查当前运行中的 BestLOGFW 状态"""
import sys, win32gui, time, pyautogui
sys.stdout.reconfigure(encoding='utf-8')

pyautogui.FAILSAFE = False

# 枚举所有窗口找佰信相关
print("=== 佰信相关窗口 ===")
def cb(h, _):
    try:
        if win32gui.IsWindowVisible(h):
            cls = win32gui.GetClassName(h)
            txt = win32gui.GetWindowText(h)[:80]
            r = win32gui.GetWindowRect(h)
            w = r[2]-r[0]; hgt = r[3]-r[1]
            if any(x in cls for x in ['Tfm', 'Login', 'Main', 'Menu', 'TPanel', 'Tcx', 'Tdx']) and w > 10:
                print(f"  [{cls}] '{txt}' ({r[0]},{r[1]})-({r[2]},{r[3]}) {w}x{hgt}")
    except: pass
    return True
win32gui.EnumWindows(cb, None)

# 截全屏保存
pyautogui.screenshot(r"D:\OAIW\_baixin_screenshots\running_state.png")
print("\n截图已保存到 running_state.png")
