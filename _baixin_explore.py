"""快速启动佰信并截图分析界面"""
import sys, time, subprocess, ctypes, win32gui, win32api, base64, httpx
sys.stdout.reconfigure(encoding='utf-8')

BAIXIN_PATH = r"D:\Best-Hint\BestLOG\BestLOGFW.exe"
USERNAME = "AI海运操作"; PASSWORD = "xu1264"
SCREENSHOT_DIR = r"D:\OAIW\_baixin_screenshots"

from pywinauto import Application

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
    u.SendInput(1, ctypes.byref(inp(1|0x8000)), ctypes.sizeof(I()))
    time.sleep(0.05)
    u.SendInput(1, ctypes.byref(inp(2)), ctypes.sizeof(I()))
    time.sleep(0.1)
    u.SendInput(1, ctypes.byref(inp(4)), ctypes.sizeof(I()))

def dclk(x, y): clk(x,y); time.sleep(0.1); clk(x,y)
def ss(win, name):
    try:
        img=win.capture_as_image(); p=f"{SCREENSHOT_DIR}\\{name}"; img.save(p); print(f"  [截图] {name}"); return p
    except: return None
def focus(hwnd):
    try: win32gui.SetForegroundWindow(hwnd); time.sleep(0.3)
    except: pass
def enum_wins():
    wins = []
    def cb(h, _): wins.append(h); return True
    win32gui.EnumWindows(cb, None)
    return wins
def find_menu():
    """找所有Menu窗口"""
    menus = []
    for w in enum_wins():
        try:
            cls = win32gui.GetClassName(w)
            if 'Menu' in cls and win32gui.IsWindowVisible(w):
                r = win32gui.GetWindowRect(w)
                if r[2]-r[0] < 500 and r[3]-r[1] > 50:
                    menus.append((w, r))
        except: pass
    return menus

# 启动
subprocess.run(["taskkill","/f","/im","BestLOGFW.exe"], capture_output=True)
time.sleep(1.5)
subprocess.Popen([BAIXIN_PATH], cwd=r"D:\Best-Hint\BestLOG")
time.sleep(5)

app = Application(backend="win32").connect(path=BAIXIN_PATH, timeout=30)
lw = app.window(class_name="TfmLogin"); lw.wait("visible", timeout=10)
lx = lw.child_window(class_name="TcxTextEdit", found_index=0)
lx.click_input(); lx.type_keys("^a{BACKSPACE}"); lx.type_keys(USERNAME)
lp = lw.child_window(class_name="TcxTextEdit", found_index=1)
lp.click_input(); lp.type_keys(PASSWORD)
ok = next((c for c in lw.descendants(class_name="TcxButton") if "确定" in (c.window_text() or "")), None)
if ok: ok.click_input()
for i in range(25):
    time.sleep(1)
    try:
        if not lw.is_visible(): break
    except: break
time.sleep(3)

mw = None
for w in app.windows():
    if w.is_visible() and w.class_name() == "TfmMainD": mw = w; break
if not mw: print("主窗口失败"); sys.exit(1)
hwnd = mw.handle; wr = mw.rectangle()
print(f"主窗口: 0x{hwnd:08x} {wr}")
focus(hwnd)

# 双击底栏
for ch in mw.children():
    if ch.class_name()=="TPanel" and ch.is_visible() and ch.rectangle().top > 900:
        r=ch.rectangle(); dclk((r.left+r.right)//2,(r.top+r.bottom)//2); time.sleep(3); break

ss(mw, "nav_01_main.png")

# 枚举所有可见控件找"基本操作"和"主菜单"
print("\n=== 搜索包含的控件文字 ===")
found_texts = []
def scan(ctl, d=0):
    if d>4: return
    try:
        t = (ctl.window_text() or "").strip()
        if t and ctl.is_visible():
            found_texts.append((t, ctl.class_name(), ctl.rectangle()))
        for ch in ctl.children(): scan(ch, d+1)
    except: pass
scan(mw)

# 找关键文字
for t, cls, r in found_texts:
    print(f"  [{cls}] '{t}' @ {r}")
    if '基本操作' in t: print(f"    *** 找到'基本操作'! ***")
    if '主菜单' in t: print(f"    *** 找到'主菜单'! ***")

# 截图顶部区域
try:
    img = mw.capture_as_image()
    top = img.crop((0, 0, 1920, 120))
    top.save(f"{SCREENSHOT_DIR}\\nav_top_area.png")
    print(f"\n截图顶部区域")
except: pass

# 尝试找"基本操作"按钮 - 可能在Panel里
print("\n=== 检查所有可见Panel ===")
for ch in mw.children():
    try:
        if ch.class_name() == 'TPanel' and ch.is_visible():
            r = ch.rectangle()
            print(f"  TPanel @ {r} 宽{r.width()} 高{r.height()}")
            # 检查子控件
            for c2 in ch.children():
                try:
                    t2 = (c2.window_text() or "").strip()
                    if t2: print(f"    [{c2.class_name()}] '{t2}' @ {c2.rectangle()}")
                except: pass
    except: pass

print(f"\n截图: {SCREENSHOT_DIR}")
