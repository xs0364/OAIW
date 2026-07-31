"""
启动佰信 → 登录 → 等待主窗口就绪 → 打印 PID
"""
import sys, time, subprocess, pyautogui
sys.stdout.reconfigure(encoding='utf-8')

BAIXIN_PATH = r"D:\Best-Hint\BestLOG\BestLOGFW.exe"
BAIXIN_CWD = r"D:\Best-Hint\BestLOG"
USERNAME = "AI海运操作"
PASSWORD = "xu1264"
pyautogui.FAILSAFE = False

print("=" * 60)
print("佰信 启动 + 登录")
print("=" * 60)

# 1. Kill old
subprocess.run(["taskkill", "/f", "/im", "BestLOGFW.exe"], capture_output=True)
time.sleep(2)

# 2. Start
proc = subprocess.Popen([BAIXIN_PATH], cwd=BAIXIN_CWD)
print(f"启动 PID={proc.pid}")
time.sleep(8)

# 3. Connect
from pywinauto import Application
app = Application(backend="win32").connect(path=BAIXIN_PATH, timeout=30)

# 4. Login
lw = app.window(class_name="TfmLogin")
lw.wait("visible", timeout=15)

lx = lw.child_window(class_name="TcxTextEdit", found_index=0)
lx.click_input(); lx.type_keys("^a{BACKSPACE}"); lx.type_keys(USERNAME)

lp = lw.child_window(class_name="TcxTextEdit", found_index=1)
lp.click_input(); lp.type_keys(PASSWORD)

ok = next((c for c in lw.descendants(class_name="TcxButton") if "确定" in (c.window_text() or "")), None)
if ok:
    ok.click_input()
else:
    lw.click_input(coords=(1020, 645))

# 5. Wait for login to complete
print("等待登录...")
time.sleep(3)
for i in range(30):
    time.sleep(1)
    try:
        if not lw.is_visible():
            print(f"登录完成 ({i+4}s)")
            break
    except:
        print(f"登录完成 (exception {i+4}s)")
        break

time.sleep(3)

# 6. Find main window
mw = None
for w in app.windows():
    try:
        if w.is_visible() and w.class_name() == "TfmMainD":
            mw = w
            break
    except:
        pass

if mw:
    print(f"主窗口就绪! PID={proc.pid} 0x{mw.handle:08x} {mw.rectangle()}")
    # 双击底部 Panel 加载模块
    for ch in mw.children():
        if ch.class_name() == "TPanel" and ch.is_visible() and ch.rectangle().top > 900:
            r = ch.rectangle()
            cx, cy = (r.left + r.right) // 2, (r.top + r.bottom) // 2
            import ctypes, win32api
            class M(ctypes.Structure):
                _fields_ = [('dx', ctypes.c_long), ('dy', ctypes.c_long),
                            ('mouseData', ctypes.c_ulong), ('dwFlags', ctypes.c_ulong),
                            ('time', ctypes.c_ulong), ('dwExtraInfo', ctypes.POINTER(ctypes.c_ulong))]
            class I(ctypes.Structure):
                _fields_ = [('type', ctypes.c_ulong), ('mi', M)]
            def clk(x, y):
                sw=win32api.GetSystemMetrics(0); sh=win32api.GetSystemMetrics(1)
                ax=int(x*65535/sw); ay=int(y*65535/sh)
                u=ctypes.windll.user32
                def inp(f): i=I(); i.type=0; i.mi=M(ax,ay,0,f,0,None); return i
                u.SendInput(1, ctypes.byref(inp(1|0x8000)), ctypes.sizeof(I())); time.sleep(0.05)
                u.SendInput(1, ctypes.byref(inp(2)), ctypes.sizeof(I())); time.sleep(0.1)
                u.SendInput(1, ctypes.byref(inp(4)), ctypes.sizeof(I()))
            def dclk(x,y): clk(x,y); time.sleep(0.1); clk(x,y)
            dclk(cx, cy)
            print(f"双击底部 Panel @ ({cx},{cy})")
            time.sleep(3)
            break

    print(f"\n主窗口已就绪，PID={proc.pid}")
    print(f"运行 _baixin_route.py 前请将 PID 设为 {proc.pid}")
    # 保持进程运行
    print("\n按 Ctrl+C 退出（进程会保持运行）")
    try:
        while True: time.sleep(10)
    except KeyboardInterrupt:
        print("退出监控，进程保持运行")
else:
    print("主窗口未找到!")
    sys.exit(1)
