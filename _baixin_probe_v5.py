"""
佰信系统 v5 — 使用 Win32 SendMessage 模拟点击（不依赖物理鼠标）
流程：海运操作 → 订舱管理 → 检索 SB-S26070007
"""
import sys, time, subprocess, json, re, ctypes
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
import win32gui, win32api, win32con, win32process

# Win32 message constants
WM_LBUTTONDOWN = 0x201
WM_LBUTTONUP = 0x202
WM_LBUTTONDBLCLK = 0x203
MK_LBUTTON = 0x0001

def send_click(hwnd, x, y):
    """通过 SendMessage 模拟点击（注意：部分 Delphi 程序不响应）"""
    lparam = (y << 16) | x
    win32gui.SendMessage(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lparam)
    time.sleep(0.05)
    win32gui.SendMessage(hwnd, WM_LBUTTONUP, 0, lparam)

def send_doubleclick(hwnd, x, y):
    """通过 SendMessage 模拟双击"""
    lparam = (y << 16) | x
    win32gui.SendMessage(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lparam)
    win32gui.SendMessage(hwnd, WM_LBUTTONUP, 0, lparam)
    time.sleep(0.05)
    win32gui.SendMessage(hwnd, WM_LBUTTONDBLCLK, MK_LBUTTON, lparam)
    win32gui.SendMessage(hwnd, WM_LBUTTONUP, 0, lparam)

def send_input_click(hwnd, x, y):
    """使用 SendInput API 模拟真实鼠标点击（更可靠）"""
    # 先获取窗口客户区位置
    rect = win32gui.GetWindowRect(hwnd)
    screen_x, screen_y = rect[0] + x, rect[1] + y

    # SendInput structure via ctypes
    # MOUSEINPUT structure
    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ('dx', ctypes.c_long),
            ('dy', ctypes.c_long),
            ('mouseData', ctypes.c_ulong),
            ('dwFlags', ctypes.c_ulong),
            ('time', ctypes.c_ulong),
            ('dwExtraInfo', ctypes.POINTER(ctypes.c_ulong)),
        ]

    class INPUT(ctypes.Structure):
        _fields_ = [
            ('type', ctypes.c_ulong),
            ('mi', MOUSEINPUT),
        ]

    INPUT_MOUSE = 0
    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_ABSOLUTE = 0x8000
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004

    # 获取屏幕分辨率
    screen_w = win32api.GetSystemMetrics(0)
    screen_h = win32api.GetSystemMetrics(1)

    # 归一化坐标到 0-65535
    abs_x = int(screen_x * 65535 / screen_w)
    abs_y = int(screen_y * 65535 / screen_h)

    def _input(flags):
        inp = INPUT()
        inp.type = INPUT_MOUSE
        inp.mi = MOUSEINPUT(abs_x, abs_y, 0, flags, 0, None)
        return inp

    try:
        ctypes.windll.user32.SendInput(1, ctypes.byref(_input(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE)), ctypes.sizeof(INPUT))
        time.sleep(0.05)
        ctypes.windll.user32.SendInput(1, ctypes.byref(_input(MOUSEEVENTF_LEFTDOWN)), ctypes.sizeof(INPUT))
        time.sleep(0.05)
        ctypes.windll.user32.SendInput(1, ctypes.byref(_input(MOUSEEVENTF_LEFTUP)), ctypes.sizeof(INPUT))
        return True
    except Exception as e:
        print(f"    SendInput 失败: {e}")
        return False

def focused_click(hwnd, x, y):
    """将窗口置前 + 真实鼠标点击"""
    try:
        # 用 SetForegroundWindow 激活窗口
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.3)
    except:
        pass
    # 用 SendInput 点击
    return send_input_click(hwnd, x, y)

def ss(win, name):
    try:
        img = win.capture_as_image()
        img.save(str(SCREENSHOT_DIR / name))
        print(f"  [截图] {name}")
    except Exception as e:
        print(f"  [截图失败] {name}: {e}")

def dump_visible(ctl, maxd=5):
    res = []
    def _rec(c, d=0):
        if d > maxd: return
        try:
            txt = (c.window_text() or "")[:120]
            cls = c.class_name()
            r = c.rectangle()
            res.append((cls, txt, r, c.is_visible(), c.is_enabled(), ctl.control_id(), d))
            for ch in c.children():
                _rec(ch, d+1)
        except:
            pass
    _rec(ctl)
    return res

def print_summary(items, title):
    print(f"\n  --- {title} ---")
    inputs = [c for c in items if c[3] and c[0] in ('TcxTextEdit','TEdit','Edit','TcxMaskEdit','TDBEdit')]
    btns = [c for c in items if c[3] and c[0] in ('TcxButton','TButton','TBitBtn','TSpeedButton') and c[1].strip()]
    labels = [c for c in items if c[3] and c[0] in ('TcxLabel','TLabel','TcxDBLabel') and c[1].strip()]
    for c in inputs: print(f"    [输入] [{c[0]}] '{c[1]}' {c[2]}")
    for c in btns: print(f"    [按钮] [{c[0]}] '{c[1]}' {c[2]}")
    for c in labels[:15]: print(f"    [标签] [{c[0]}] '{c[1]}' {c[2]}")
    print(f"    (输入:{len(inputs)} 按钮:{len(btns)} 标签:{len(labels)})")

# ===== 1. 清理 & 登录 =====
print("="*60)
print("佰信 v5 — 海运操作 > 订舱管理 > 检索 SB-S26070007")
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

# 主窗口
main_win = None
for w in app.windows():
    if w.is_visible() and w.class_name() == 'TfmMainD':
        main_win = w; break
if not main_win:
    for w in app.windows():
        if w.is_visible() and w.rectangle().width() > 400:
            main_win = w; break
if not main_win:
    print("[失败] 找不到主窗口"); sys.exit(1)

main_hwnd = main_win.handle
print(f"  主窗口: handle=0x{main_hwnd:08x} rect={main_win.rectangle()}")
ss(main_win, "v5_01_main.png")

# 激活窗口
try:
    win32gui.SetForegroundWindow(main_hwnd)
    time.sleep(0.5)
except:
    print("  SetForegroundWindow 失败，继续...")

# ===== 2. 点击顶部 TcxTabControl 找到"海运操作" =====
print("\n[2] 定位并点击顶部标签...")

# 已知界面结构（从之前探查）:
# TabControl 区域屏幕坐标: L0, T67, R1920, B88 (在 1920x1080 分辨率下)
# Main Menu 屏幕坐标: L0, T45, R670, B67
# 主窗口: L-8, T-8, R1928, B1040
# 注意：main_win 是 DialogWrapper，不能使用 child_window，直接使用屏幕坐标

main_r = main_win.rectangle()
# 标题栏高度 ≈ 标题文字到客户区顶部的距离
title_bar_h = 67 - 8  # 从之前得 TcxTabControl top=67, main top=-8 → 标题栏约 59px?
# 实际上 TcxTabControl 的 top 是相对于屏幕的，主窗口 top=-8
# 所以标签栏相对主窗口客户区的 Y = 67 - (client_area_top相对于0的偏移)
# 简单点：屏幕坐标Y = main_r.top + 偏移
# TcxTabControl 上边缘屏幕Y=67, 主窗口顶部屏幕Y=-8
# 所以标签栏在主窗口内的偏移 = 67 - (-8) = 75
tab_y_offset = 67 - main_r.top  # 75
menu_y_offset = 55 - main_r.top  # Main Menu 的 Y 偏移

print(f"  主窗口: {main_r}")
print(f"  TabControl 在主窗口内偏移 Y={tab_y_offset}, Main Menu Y={menu_y_offset}")

# 用屏幕坐标点击
def screen_click(main_hwnd, win_rect, rel_x, rel_y, desc=""):
    """基于主窗口的偏移坐标点击"""
    sx = win_rect.left + rel_x
    sy = win_rect.top + rel_y
    print(f"    -> 点击 {desc} 屏幕({sx},{sy})...")
    return focused_click(main_hwnd, sx, sy)

# 点击 TabControl 区域的不同位置
tab_y = main_r.top + tab_y_offset + 10  # 标签垂直居中
tab_x_positions = [
    (main_r.left + 60, tab_y, "海运操作(左侧)"),
    (main_r.left + 200, tab_y, "标签2"),
    (main_r.left + 350, tab_y, "标签3"),
    (main_r.left + 500, tab_y, "标签4"),
    (main_r.left + 650, tab_y, "标签5"),
    (main_r.left + 800, tab_y, "标签6"),
    (main_r.left + 950, tab_y, "标签7"),
    (main_r.left + 1100, tab_y, "标签8"),
]

for sx, sy, desc in tab_x_positions:
    print(f"\n  点击标签 {desc} ({sx},{sy})...")
    ok = focused_click(main_hwnd, sx, sy)
    print(f"    点击结果: {'OK' if ok else '失败'}")
    time.sleep(2)
    ss(main_win, f"v5_tab_{desc[:4]}.png")

    # 检查是否有 MDI 子窗口打开
    for ch in main_win.children():
        if ch.is_visible():
            cls = ch.class_name()
            txt = ch.window_text()[:50]
            if cls not in ('TPanel','TdxDockControl','TcxSplitter','TdxStatusBar','TcxTabControl','TdxBarControl','TdxBarDockControl','TdxDockSite','TfmFW_WallPaper','TcxButton','MDIClient') and txt.strip():
                print(f"    [MDI子窗口] '{txt}' ({cls})")
                ss(ch, f"v5_mdi_{desc[:4]}.png")

    # 扫描
    items = dump_visible(main_win, 3)
    has_inputs = len([c for c in items if c[3] and c[0] in ('TcxTextEdit','TEdit','Edit')])
    print(f"    输入框数: {has_inputs}")

# ===== 3. 尝试 Main Menu 点击 =====
print("\n[3] 点击 Main Menu...")
# Main Menu 屏幕坐标: L0, T45, R670, B67 → 主窗口偏移
menu_y = main_r.top + menu_y_offset + 10
menu_positions = [
    (main_r.left + 80, menu_y, "海运操作"),
    (main_r.left + 180, menu_y, "空运"),
    (main_r.left + 260, menu_y, "报关"),
    (main_r.left + 340, menu_y, "仓储"),
]
for sx, sy, desc in menu_positions:
    print(f"  点击菜单 '{desc}' ({sx},{sy})...")
    focused_click(main_hwnd, sx, sy)
    time.sleep(2)

    # 检查是否有弹出菜单
    menus = []
    for w in app.windows():
        if w.is_visible():
            cls = w.class_name()
            r = w.rectangle()
            txt = w.window_text()[:40]
            if r.width() < 400 and r.height() < 800 and cls not in ('TfmMainD','TApplication','SoPY_Status','TTrayIcon') or 'Menu' in cls or 'Popup' in cls:
                menus.append((txt, cls, r))
                print(f"    [菜单] '{txt}' ({cls}) {r}")
                ss(w, f"v5_menu_{desc}.png")

    if not menus:
        # 没有菜单出现
        send_keys('{ESC}'); time.sleep(0.3)
        continue

    # 有菜单弹出！在菜单中找"订舱管理"
    print("    菜单已弹出，查找'订舱管理'...")
    # TdxBarSubMenuControl 是弹出菜单
    menu_win = None
    for w in app.windows():
        if w.is_visible() and w.class_name() == 'TdxBarSubMenuControl' and w.rectangle().width() < 500:
            menu_win = w
            break
    if not menu_win:
        for w in app.windows():
            if w.is_visible() and ('Menu' in w.class_name() or 'Popup' in w.class_name()) and w.rectangle().width() < 500:
                menu_win = w
                break

    if menu_win:
        menu_r = menu_win.rectangle()
        print(f"    菜单窗口: {menu_r}")

        # 方法1: 枚举子控件
        menu_childs = menu_win.children()
        print(f"    子控件数: {len(menu_childs)}")
        for i, mc in enumerate(menu_childs):
            try:
                mc_txt = (mc.window_text() or "")[:50]
                mc_cls = mc.class_name()
                mc_r = mc.rectangle()
                mc_vis = mc.is_visible()
                print(f"      [{i}] [{mc_cls}] '{mc_txt}' {mc_r} vis={mc_vis}")
            except Exception as e:
                print(f"      [{i}] ERROR: {e}")

        # 方法2: 递归枚举菜单窗口所有控件
        print(f"    --- 菜单窗口所有可见控件 ---")
        menu_all = dump_visible(menu_win, 4)
        for mc in menu_all:
            if mc[3] and mc[1].strip():
                print(f"      [{mc[0]}] depth={mc[6]} '{mc[1]}' {mc[2]}")

        # 方法3: 获取包含"订舱"文字的控件
        menu_texts = [(c[1], c[2]) for c in menu_all if mc[3] and '订舱' in c[1]]
        if menu_texts:
            for mt, mr in menu_texts:
                print(f"      [点击] '{mt}' {mr}")
                cx = (mr.left + mr.right)//2
                cy = (mr.top + mr.bottom)//2
                focused_click(main_hwnd, cx, cy)
                time.sleep(3)
                ss(main_win, "v5_after_booking.png")

        # 方法4: 如果以上都找不到，把菜单保存为截图分析
        ss(menu_win, f"v5_menu_{desc}_detail.png")

        # 关闭菜单（ESC）
        send_keys('{ESC}')
        time.sleep(0.5)
    else:
        print("    未找到菜单窗口")
        send_keys('{ESC}'); time.sleep(0.3)

# ===== 4. 如果还没进入模块，尝试双击 MDIClient =====
print("\n[4] 尝试双击 MDI 区域...")
# MDIClient 屏幕坐标: L0, T88, R1912, B988
mdi_rel_x = 100  # 从左边偏移
mdi_rel_y = 100  # 从上边偏移
mdi_sx = main_r.left + mdi_rel_x
mdi_sy = main_r.top + 88 - main_r.top + 100  # MDI 客户区 Y 偏移
print(f"  点击 MDI 区域 ({mdi_sx},{mdi_sy})...")
focused_click(main_hwnd, mdi_sx, mdi_sy)
time.sleep(2)
ss(main_win, "v5_mdi_click.png")
items = dump_visible(main_win, 3)
print_summary(items, "点击 MDI 后")

# ===== 5. 最终 =====
print("\n[5] 最终状态...")
print("\n所有可见窗口:")
for w in app.windows():
    if w.is_visible():
        print(f"  '{w.window_text()[:80]}' ({w.class_name()}) {w.rectangle()}")

# 保存控件树
final = dump_visible(main_win, 6)
with open(SCREENSHOT_DIR / "v5_final.json", "w", encoding="utf-8") as f:
    json.dump([{'class':c[0],'text':c[1],'rect':str(c[2])} for c in final], f, ensure_ascii=False, indent=2)

# 找所有含'订舱'的控件
print("\n  含 '订舱' 的控件:")
for c in final:
    if '订舱' in c[1]:
        print(f"    [{c[0]}] depth={c[6]} '{c[1]}' {c[2]}")

print(f"\n截图目录: {SCREENSHOT_DIR}")
print("="*60)
