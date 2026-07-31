"""
佰信 v7 — Alt 键盘精确导航到订舱管理
使用 Alt + 方向键 导航菜单栏
"""
import sys, time, subprocess, json, ctypes
from pathlib import Path
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BAIXIN_PATH = r"D:\Best-Hint\BestLOG\BestLOGFW.exe"
BAIXIN_CWD  = r"D:\Best-Hint\BestLOG"
USERNAME = "AI海运操作"
PASSWORD = "xu1264"
SCREENSHOT_DIR = Path(r"D:\OAIW\_baixin_screenshots")
SCREENSHOT_DIR.mkdir(exist_ok=True)

from pywinauto import Application
from pywinauto.keyboard import send_keys
import win32gui, win32api

def ss(win, name):
    try:
        win.capture_as_image().save(str(SCREENSHOT_DIR / name))
        print(f"  [截图] {name}")
    except Exception as e:
        print(f"  [截图失败] {name}: {e}")

def click_abs(x, y):
    sw = win32api.GetSystemMetrics(0)
    sh = win32api.GetSystemMetrics(1)
    ax = int(x * 65535 / sw)
    ay = int(y * 65535 / sh)
    class M(ctypes.Structure):
        _fields_ = [('dx', ctypes.c_long), ('dy', ctypes.c_long),
                    ('mouseData', ctypes.c_ulong), ('dwFlags', ctypes.c_ulong),
                    ('time', ctypes.c_ulong), ('dwExtraInfo', ctypes.POINTER(ctypes.c_ulong))]
    class I(ctypes.Structure):
        _fields_ = [('type', ctypes.c_ulong), ('mi', M)]
    def inp(f):
        i = I(); i.type = 0; i.mi = M(ax, ay, 0, f, 0, None); return i
    u = ctypes.windll.user32
    u.SendInput(1, ctypes.byref(inp(1|0x8000)), ctypes.sizeof(I()))
    time.sleep(0.03)
    u.SendInput(1, ctypes.byref(inp(2)), ctypes.sizeof(I()))
    time.sleep(0.05)
    u.SendInput(1, ctypes.byref(inp(4)), ctypes.sizeof(I()))

def focus(hwnd):
    try: win32gui.SetForegroundWindow(hwnd); time.sleep(0.3)
    except: pass

def find_mdi_children(win):
    """找出 MDI 区域内的子窗口"""
    res = []
    for ch in win.children():
        try:
            cls = ch.class_name()
            txt = (ch.window_text() or "")[:60]
            r = ch.rectangle()
            if ch.is_visible() and cls not in ('TPanel','TdxDockControl','TcxSplitter','TdxStatusBar','TcxTabControl','TdxBarControl','TdxBarDockControl','TdxDockSite','TfmFW_WallPaper','TcxButton','MDIClient','TApplication','SoPY_Status'):
                res.append((cls, txt, r))
        except: pass
    return res

# ===== 1. 启动 & 登录 =====
print("="*60)
print("佰信 v7 — Alt键盘导航 → 订舱管理")
print("="*60)

subprocess.run(["taskkill", "/f", "/im", "BestLOGFW.exe"], capture_output=True)
time.sleep(1.5)
subprocess.Popen([BAIXIN_PATH], cwd=BAIXIN_CWD)
time.sleep(5)

app = Application(backend="win32").connect(path=BAIXIN_PATH, timeout=30)
login_win = app.window(class_name="TfmLogin")
login_win.wait("visible", timeout=10)
uname = login_win.child_window(class_name="TcxTextEdit", found_index=0)
uname.click_input(); time.sleep(0.3)
uname.type_keys("^a{BACKSPACE}", with_spaces=True); time.sleep(0.2)
uname.type_keys(USERNAME, with_spaces=True)
pwd = login_win.child_window(class_name="TcxTextEdit", found_index=1)
pwd.click_input(); time.sleep(0.2)
pwd.type_keys(PASSWORD, with_spaces=True)
ok_btn = next((c for c in login_win.descendants(class_name="TcxButton") if "确定" in (c.window_text() or "")), None)
if ok_btn: ok_btn.click_input()
else: login_win.click_input(coords=(1020, 645))
for i in range(25):
    time.sleep(1)
    try:
        if not login_win.is_visible(): break
    except: break
time.sleep(3)

main_win = None
for w in app.windows():
    if w.is_visible() and w.class_name() == 'TfmMainD':
        main_win = w; break
if not main_win: print("主窗口失败"); sys.exit(1)
main_hwnd = main_win.handle
print(f"主窗口: 0x{main_hwnd:08x}")
focus(main_hwnd)
ss(main_win, "v7_01_main.png")

# ===== 2. 阶段一：点击底部提示面板 =====
print("\n[阶段一] 双击底部面板...")
for ch in main_win.children():
    if ch.class_name() == 'TPanel' and ch.is_visible():
        r = ch.rectangle()
        cx, cy = (r.left+r.right)//2, (r.top+r.bottom)//2
        click_abs(cx, cy); time.sleep(0.1)
        click_abs(cx, cy); time.sleep(3)
        ss(main_win, "v7_02_panel.png")
        break

# ===== 3. 阶段二：使用 Alt 导航到"海运操作"→"订舱管理" =====
print("\n[阶段二] Alt 菜单导航...")

# 方法1: 尝试直接用 Alt+特定键
# 标准 BestLOG 可能用 Alt+1, Alt+2,... 或 Alt+F, Alt+E 等
# 或者首字母：海运操作 → Alt+H
for alt_key in ['%h', '%H', '%1', '%s', '%y', '%{F1}']:
    print(f"  尝试 {alt_key}...")
    send_keys(alt_key)
    time.sleep(2)

    # 检查是否有菜单或界面变化
    mdi = find_mdi_children(main_win)
    menus = [w for w in app.windows() if w.is_visible() and 'Menu' in w.class_name() and w.rectangle().width() < 500]
    if menus or mdi:
        print(f"  {alt_key} 触发了反应! 菜单:{len(menus)} MDI子窗口:{len(mdi)}")
        ss(main_win, f"v7_alt_{alt_key[1:-1] if alt_key.startswith('%') and alt_key.endswith('}') else alt_key.replace('%','')}.png")
        if menus:
            print(f"    菜单: ({menus[0].class_name()}) {menus[0].rectangle()}")
        for m in mdi:
            print(f"    MDI: [{m[0]}] '{m[1]}' {m[2]}")

    # 关闭菜单
    send_keys('{ESC}')
    time.sleep(0.5)

# 方法2: Alt 激活菜单栏+方向键
print("\n  方法2: Alt → 方向键导航...")
for first_menu_idx in range(1, 7):
    print(f"    Alt激活 → {first_menu_idx}次RIGHT → DOWN...")
    focus(main_hwnd)
    time.sleep(0.2)
    send_keys('%')  # Alt
    time.sleep(1)
    for _ in range(first_menu_idx):
        send_keys('{RIGHT}')
        time.sleep(0.3)
    send_keys('{DOWN}')  # 打开菜单
    time.sleep(2)

    # 检查菜单
    menus_found = []
    for w in app.windows():
        if w.is_visible() and 'Menu' in w.class_name() and w.rectangle().width() < 500:
            menus_found.append(w)
            print(f"      菜单 {w.class_name()} {w.rectangle()}")
            ss(w, f"v7_menu_{first_menu_idx}.png")

    if menus_found:
        # 键盘↓选择菜单项
        for item_idx in range(8):  # 最多8个菜单项
            send_keys('{DOWN}')
            time.sleep(0.5)

            # 检查当前高亮项：尝试回车
            send_keys('{ENTER}')
            time.sleep(3)
            ss(main_win, f"v7_menuitem_{first_menu_idx}_{item_idx}.png")

            mdi_after = find_mdi_children(main_win)
            if mdi_after:
                print(f"      [成功] 菜单{first_menu_idx} 项{item_idx} 打开了MDI子窗口!")
                for m in mdi_after:
                    print(f"        [{m[0]}] '{m[1]}' {m[2]}")

            # 重新打开菜单继续
            send_keys('{ESC}'); time.sleep(0.5)
            send_keys('{ESC}'); time.sleep(0.5)
            focus(main_hwnd); time.sleep(0.2)
            send_keys('%'); time.sleep(0.5)
            for _ in range(first_menu_idx):
                send_keys('{RIGHT}'); time.sleep(0.3)
            send_keys('{DOWN}'); time.sleep(1.5)

    # 关闭菜单
    send_keys('{ESC}'); time.sleep(0.5)
    send_keys('{ESC}'); time.sleep(0.3)

# ===== 4. 阶段三：尝试双击模块加载提示 =====
print("\n[阶段三] 尝试各种方式加载模块...")

# 再次双击面板
for ch in main_win.children():
    if ch.class_name() == 'TPanel' and ch.is_visible():
        r = ch.rectangle()
        click_abs((r.left+r.right)//2, (r.top+r.bottom)//2)
        time.sleep(0.1)
        click_abs((r.left+r.right)//2, (r.top+r.bottom)//2)
        time.sleep(3)
        break

# 检查是否有模块加载的对话框
for w in app.windows():
    if w.is_visible() and w.class_name() not in ('TfmMainD','TApplication','SoPY_Status','TTrayIcon'):
        print(f"  其他窗口: '{w.window_text()[:60]}' ({w.class_name()}) {w.rectangle()}")

# ===== 5. 最终状态总览 =====
print("\n[最终] 扫描全部控件...")
all_items = []
def scan(ctl, d=0):
    if d > 5: return
    try:
        txt = (ctl.window_text() or "")[:100]
        if txt.strip() and ctl.is_visible():
            all_items.append((txt, ctl.class_name(), ctl.rectangle(), d))
        for ch in ctl.children(): scan(ch, d+1)
    except: pass
scan(main_win)

print(f"总可见控件(有文字): {len(all_items)}")
for item in all_items[:40]:
    print(f"  [{item[1]}] d={item[3]} '{item[0]}' {item[2]}")

print(f"\n所有窗口:")
for w in app.windows():
    if w.is_visible():
        print(f"  '{w.window_text()[:80]}' ({w.class_name()})")

print(f"\n截图: {SCREENSHOT_DIR}")
print("="*60)
