"""
佰信系统 v6 — 键盘导航菜单 + 检索
流程：Login → 海运操作菜单(键盘) → 订舱管理 → 检索 SB-S26070007
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

# SendInput click
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [('dx', ctypes.c_long), ('dy', ctypes.c_long),
                ('mouseData', ctypes.c_ulong), ('dwFlags', ctypes.c_ulong),
                ('time', ctypes.c_ulong), ('dwExtraInfo', ctypes.POINTER(ctypes.c_ulong))]
class INPUT(ctypes.Structure):
    _fields_ = [('type', ctypes.c_ulong), ('mi', MOUSEINPUT)]

def send_click(screen_x, screen_y):
    sw = win32api.GetSystemMetrics(0)
    sh = win32api.GetSystemMetrics(1)
    abs_x = int(screen_x * 65535 / sw)
    abs_y = int(screen_y * 65535 / sh)
    def inp(flags):
        i = INPUT(); i.type = 0; i.mi = MOUSEINPUT(abs_x, abs_y, 0, flags, 0, None)
        return i
    move = 0x0001 | 0x8000
    down = 0x0002; up = 0x0004
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp(move)), ctypes.sizeof(INPUT))
    time.sleep(0.03)
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp(down)), ctypes.sizeof(INPUT))
    time.sleep(0.05)
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp(up)), ctypes.sizeof(INPUT))
    return True

def focus_window(hwnd):
    try:
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.3)
    except: pass

# ===== 1. 启动 & 登录 =====
print("="*60)
print("佰信 v6 — 键盘导航 → 订舱管理 → 检索")
print("="*60)

print("\n[1] 清理并启动...")
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
print("  登录完成")
time.sleep(3)

main_win = None
for w in app.windows():
    if w.is_visible() and w.class_name() == 'TfmMainD':
        main_win = w; break
if not main_win:
    for w in app.windows():
        if w.is_visible() and w.rectangle().width() > 400:
            main_win = w; break
if not main_win: print("[失败] 主窗口"); sys.exit(1)

main_hwnd = main_win.handle
print(f"  主窗口: 0x{main_hwnd:08x}")
ss(main_win, "v6_01_main.png")
focus_window(main_hwnd)

# ===== 2. 底部面板双击 =====
print("\n[2] 双击底部提示面板...")
for ch in main_win.children():
    if ch.class_name() == 'TPanel' and ch.is_visible():
        r = ch.rectangle()
        print(f"  面板: {r}")
        send_click((r.left+r.right)//2, (r.top+r.bottom)//2)
        time.sleep(0.1)
        send_click((r.left+r.right)//2, (r.top+r.bottom)//2)
        time.sleep(3)
        ss(main_win, "v6_02_after_panel.png")
        break

# ===== 3. 点击 Main Menu "海运操作" =====
print("\n[3] 点击 Main Menu '海运操作'...")
# Main Menu 区域: L0, T45, R670, B67
# 第一个菜单项"海运操作"大约在 x=80 左右
menu_x = 72  # 从 v5 得知屏幕坐标

# 用键盘方式：先 Alt 激活菜单栏
print("  方式A: Alt 激活菜单栏...")
focus_window(main_hwnd)
time.sleep(0.5)
send_keys('%')  # Alt 键
time.sleep(1)
ss(main_win, "v6_03_alt_menu.png")

# 再按 ← → 移动到"海运操作"
# 实际上按 Alt 后菜单栏第一个项目被选中
# 按 → 移动到"海运操作"
# 先试试直接 Alt+F (文件) 等标准快捷键
send_keys('{RIGHT}')
time.sleep(0.5)
send_keys('{RIGHT}')
time.sleep(0.5)
send_keys('{DOWN}')  # 打开菜单
time.sleep(2)
ss(main_win, "v6_04_alt_nav.png")

# 检查是否有菜单打开
menus_after_alt = []
for w in app.windows():
    if w.is_visible() and 'Menu' in w.class_name():
        r = w.rectangle()
        print(f"  菜单: '{w.window_text()[:40]}' ({w.class_name()}) {r}")
        menus_after_alt.append(w)

if menus_after_alt:
    print("  Alt 导航成功打开菜单!")
else:
    print("  Alt 导航未打开菜单，尝试直接点击...")

# 方式B: 直接点击"海运操作"
print("\n  方式B: 直接点击 '海运操作'...")
focus_window(main_hwnd)
time.sleep(0.3)
send_click(main_win.rectangle().left + 72, main_win.rectangle().top + 63)  # Main Menu Y=63
time.sleep(2)
ss(main_win, "v6_05_menu_open.png")

# ===== 4. 键盘导航菜单项 =====
print("\n[4] 键盘选择订舱管理...")

# 检查菜单
menu_wins = []
for w in app.windows():
    if w.is_visible() and 'Menu' in w.class_name():
        r = w.rectangle()
        cls = w.class_name()
        if r.width() < 500:
            print(f"  菜单: ({cls}) {r}")
            menu_wins.append(w)

if not menu_wins:
    print("  菜单未打开，再试一次点击...")
    focus_window(main_hwnd)
    time.sleep(0.3)
    send_click(main_win.rectangle().left + 72, main_win.rectangle().top + 63)
    time.sleep(2)
    for w in app.windows():
        if w.is_visible() and 'Menu' in w.class_name() and w.rectangle().width() < 500:
            print(f"  菜单: ({w.class_name()}) {w.rectangle()}")
            menu_wins.append(w)

# 菜单已打开，用键盘选择项
# 菜单尺寸 145x72，约2个项目
# 第1项自动高亮，按↓到第2项，或直接回车选第1项
print("  菜单位置已知，尝试各个菜单项...")

# 策略：依次尝试每个菜单项（用键盘↓+Enter）
for attempt in range(5):
    print(f"  尝试 {attempt+1}: 按 ↓ 然后 Enter...")
    time.sleep(0.5)
    send_keys('{DOWN}')
    time.sleep(0.5)
    send_keys('{ENTER}')
    time.sleep(3)
    ss(main_win, f"v6_06_menu_attempt_{attempt+1}.png")

    # 检查界面变化
    new_items = []
    def scan(ctl, d=0):
        if d > 3: return
        try:
            txt = (ctl.window_text() or "")[:80]
            if txt.strip() and ctl.is_visible():
                new_items.append((txt, ctl.class_name(), ctl.rectangle()))
            for ch in ctl.children(): scan(ch, d+1)
        except: pass
    scan(main_win)

    has_new_c = len([x for x in new_items if x[1] in ('TcxTextEdit','TEdit','Edit')])
    print(f"    输入框: {has_new_c}, 控件数: {len(new_items)}")

    if has_new_c > 0:
        print(f"  [成功] 菜单项 {attempt+1} 打开了功能界面!")
        break

    # 如果没变化，重新打开菜单再试
    if attempt < 4:
        print("  未变化，重新打开菜单...")
        focus_window(main_hwnd)
        time.sleep(0.2)
        send_click(main_win.rectangle().left + 72, main_win.rectangle().top + 63)
        time.sleep(2)

# ===== 5. 如果键盘没成功，尝试按坐标点击菜单 =====
print("\n[5] 按坐标点击菜单项...")
# 菜单位置: (L47, T65, R192, B137)
# 菜单高度 = 137-65 = 72px
# 每个菜单项约 25-30px 高
# 项目位置:

menu_left, menu_top = 47, 65
menu_h = 137 - 65  # 72
item_h = 28
n_items = menu_h // item_h  # ~2.5 → 约2-3个项目

print(f"  菜单高度 {menu_h}px, 每项 ~{item_h}px, 约 {n_items} 项")

# 先关闭菜单
send_keys('{ESC}'); time.sleep(0.5)

# 重新打开菜单
focus_window(main_hwnd)
time.sleep(0.3)
send_click(main_win.rectangle().left + 72, main_win.rectangle().top + 63)
time.sleep(1.5)

# 点击每个可能的菜单项位置
for idx in range(n_items):
    item_y = menu_top + item_h // 2 + idx * item_h
    item_center_x = (menu_left + 192) // 2  # 菜单中间
    print(f"  点击菜单项 {idx+1}: ({item_center_x}, {item_y})")
    send_click(item_center_x, item_y)
    time.sleep(3)
    ss(main_win, f"v6_07_menu_click_{idx+1}.png")

    # 检查是否有新控件出现
    new_items = []
    def scan2(ctl, d=0):
        if d > 3: return
        try:
            txt = (ctl.window_text() or "")[:80]
            if txt.strip() and ctl.is_visible():
                new_items.append((txt, ctl.class_name(), ctl.rectangle()))
            for ch in ctl.children(): scan2(ch, d+1)
        except: pass
    scan2(main_win)

    has_input = len([x for x in new_items if x[1] in ('TcxTextEdit','TEdit','Edit')])
    has_btn = len([x for x in new_items if x[1] in ('TcxButton','TBitBtn') and x[0].strip()])
    print(f"    输入框:{has_input} 按钮:{has_btn}")
    if has_input or has_btn:
        print(f"  [成功] 菜单项 {idx+1} 有效!")
        break

# ===== 6. 检索 =====
print("\n[6] 找检索框 → 输入 SB-S26070007...")
items = []
def scan3(ctl, d=0):
    if d > 5: return
    try:
        txt = (ctl.window_text() or "")[:100]
        if ctl.is_visible():
            items.append((txt, ctl.class_name(), ctl.rectangle(), d))
        for ch in ctl.children(): scan3(ch, d+1)
    except: pass
scan3(main_win)

print(f"\n  总控件: {len(items)}")
inputs = [c for c in items if c[1] in ('TcxTextEdit','TEdit','Edit')]
btns = [c for c in items if c[1] in ('TcxButton','TBitBtn','TSpeedButton') and c[0].strip()]
labels = [c for c in items if c[1] in ('TcxLabel','TLabel','TcxDBLabel') and c[0].strip()]

print(f"  输入框: {len(inputs)}")
for c in inputs: print(f"    [{c[1]}] '{c[0]}' {c[2]}")

print(f"\n  按钮: {len(btns)}")
for c in btns: print(f"    [{c[1]}] '{c[0]}' {c[2]}")

print(f"\n  标签: {len(labels)}")
for c in labels[:30]: print(f"    [{c[1]}] '{c[0]}' {c[2]}")

# 所有窗口
print("\n  所有可见窗口:")
for w in app.windows():
    if w.is_visible():
        print(f"    '{w.window_text()[:80]}' ({w.class_name()}) {w.rectangle()}")

print(f"\n截图: {SCREENSHOT_DIR}")
print("="*60)
