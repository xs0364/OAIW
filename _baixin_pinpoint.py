"""
佰信 — 精准点击海运操作菜单
已知：ToolBar @ y=23-45, 海运操作预测 x≈296 (窗口相对偏移)
菜单扫描 + 检索 SB-S26070007
"""
import sys, time, subprocess, ctypes, win32gui, win32api
sys.stdout.reconfigure(encoding='utf-8')

BAIXIN_PATH = r"D:\Best-Hint\BestLOG\BestLOGFW.exe"
USERNAME = "AI海运操作"; PASSWORD = "xu1264"
SCREENSHOT_DIR = r"D:\OAIW\_baixin_screenshots"

from pywinauto import Application
from pywinauto.keyboard import send_keys

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
        img=win.capture_as_image(); p=f"{SCREENSHOT_DIR}\\{name}"; img.save(p); print(f"  [截图] {name}")
    except Exception as e: print(f"  [截图失败] {e}")

def focus(hwnd):
    try: win32gui.SetForegroundWindow(hwnd); time.sleep(0.3)
    except: pass

def enum_windows():
    """安全地枚举所有顶层窗口"""
    wins = []
    def cb(h, _): wins.append(h); return True
    win32gui.EnumWindows(cb, None)
    return wins

def open_menu_at(hwnd, x, y):
    """在指定坐标点击打开菜单，返回菜单窗口"""
    focus(hwnd); time.sleep(0.15)
    clk(x, y); time.sleep(2)
    # 枚举全屏找菜单窗口
    wins = []
    def enum_cb(h, _): wins.append(h); return True
    win32gui.EnumWindows(enum_cb, None)
    for w in wins:
        try:
            cls = win32gui.GetClassName(w)
            if 'Menu' in cls and win32gui.IsWindowVisible(w):
                r = win32gui.GetWindowRect(w)
                if r[2]-r[0] < 500 and r[3]-r[1] > 50:
                    return w, r
        except: pass
    return None, None

# ===== 1. 启动 & 登录 =====
print("="*60)
print("佰信 — 精准导航到订舱管理")
print("="*60)

subprocess.run(["taskkill","/f","/im","BestLOGFW.exe"], capture_output=True)
time.sleep(1.5)
subprocess.Popen([BAIXIN_PATH], cwd=r"D:\Best-Hint\BestLOG")
time.sleep(5)

app = Application(backend="win32").connect(path=BAIXIN_PATH, timeout=30)
lw = app.window(class_name="TfmLogin")
lw.wait("visible", timeout=10)
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
hwnd = mw.handle
wr = mw.rectangle()
print(f"主窗口: 0x{hwnd:08x}  {wr}")

focus(hwnd)
for ch in mw.children():
    if ch.class_name()=="TPanel" and ch.is_visible() and ch.rectangle().top > 900:
        r=ch.rectangle(); dclk((r.left+r.right)//2,(r.top+r.bottom)//2); time.sleep(3); break

ss(mw, "t_01_main.png")
print(f"窗口: (-8,-8)-(1928,1040), ToolBar @ y=23-45")

# ===== 2. 定位海运操作菜单 =====
print("\n[1/3] 定位'海运操作'菜单...")
# ToolBar Y范围 = 窗口的y=23到45
toolbar_y = wr.top + 34  # ToolBar中间

# 从x_off=150到400步进5px找大的海运操作菜单
# 已知ToolBar项约在x_off=80,160,240,320,... (基于第一轮视觉结果)
# "海运操作"约在第三个位置，x_off≈240~320
haiyun_x = None
menu_hwnd = None
menu_r = None

for x_off in range(150, 420, 5):
    tx = wr.left + x_off
    mh, mr = open_menu_at(hwnd, tx, toolbar_y)
    if mh:
        h = mr[3] - mr[1]
        w = mr[2] - mr[0]
        print(f"  x_off={x_off} ({tx},{toolbar_y}) -> ({mr[0]},{mr[1]})-({mr[2]},{mr[3]}) {w}x{h}")
        if h > 350:
            huiyun_x = tx; menu_hwnd = mh; menu_r = mr
            print(f"  *** 海运操作菜单! 高{h}px ***")
            break
        send_keys('{ESC}'); time.sleep(0.2)
    else:
        pass  # 无弹出

if not menu_hwnd:
    print("  未找到海运操作菜单，尝试Alt键激活...")
    focus(hwnd); time.sleep(0.2)
    send_keys('%'); time.sleep(1.5)
    ss(mw, "t_alt.png")
    # 按→直到看到大的弹出菜单
    for step in range(8):
        send_keys('{DOWN}'); time.sleep(2)
        # 找菜单
        for w in enum_windows():
            try:
                cls = win32gui.GetClassName(w)
                if 'Menu' in cls and win32gui.IsWindowVisible(w):
                    r = win32gui.GetWindowRect(w)
                    if r[2]-r[0] < 500 and r[3]-r[1] > 350:
                        menu_hwnd = w; menu_r = r
                        print(f"  Alt菜单弹出: {r}")
                        break
            except: pass
        if menu_hwnd: break
        send_keys('{ESC}'); time.sleep(0.3)
        send_keys('{ESC}'); time.sleep(0.2)
        focus(hwnd); time.sleep(0.2)
        send_keys('%'); time.sleep(0.5)
        send_keys('{RIGHT}'); time.sleep(0.3)

    if not menu_hwnd:
        print("无法找到海运操作菜单"); sys.exit(1)

print(f"\n海运操作菜单: ({menu_r[0]},{menu_r[1]})-({menu_r[2]},{menu_r[3]})")
print(f"  宽{menu_r[2]-menu_r[0]} 高{menu_r[3]-menu_r[1]}")
ss(mw, "t_02_menu_open.png")

# ===== 3. 扫描菜单项找"订舱管理" =====
print("\n[2/3] 扫描菜单项找'订舱管理'...")
menu_cx = (menu_r[0] + menu_r[2]) // 2
item_found = False

for idx in range(1, 30):
    # 重新打开菜单
    mh2, mr2 = open_menu_at(hwnd, huiyun_x or (wr.left + 240), toolbar_y)
    if not mh2 or (mr2[3]-mr2[1]) < 350:
        # 如果菜单没打开，试试Alt方式
        focus(hwnd); time.sleep(0.2)
        send_keys('%'); time.sleep(1)
        for _ in range(2): send_keys('{RIGHT}'); time.sleep(0.2)
        send_keys('{DOWN}'); time.sleep(2)
        for w in enum_windows():
            try:
                if 'Menu' in win32gui.GetClassName(w) and win32gui.IsWindowVisible(w):
                    mr2 = win32gui.GetWindowRect(w)
                    if mr2[2]-mr2[0] < 500 and mr2[3]-mr2[1] > 350:
                        mh2 = w; break
            except: pass
        if not mh2:
            print("  菜单打开失败")
            break

    menu_r2 = win32gui.GetWindowRect(mh2)
    step = 22
    item_y = menu_r2[1] + step // 2 + (idx - 1) * step
    if item_y > menu_r2[3] - 5: break

    print(f"  项{idx}: y={item_y}...", end="")
    clk(menu_cx, item_y); time.sleep(2.5)

    # 检查界面变化
    new_items = []
    def scan(ctl, d=0):
        if d>5: return
        try:
            t=(ctl.window_text() or "")[:60]
            if t.strip() and ctl.is_visible(): new_items.append((t,ctl.class_name()))
            for ch in ctl.children(): scan(ch, d+1)
        except: pass
    scan(mw)

    has_input = any(c[1] in ('TcxTextEdit','TEdit','Edit') for c in new_items)
    has_mdi = False
    for ch in mw.children():
        try:
            if ch.is_visible() and ch.class_name() not in ('TPanel','TdxDockControl','TcxSplitter','TdxStatusBar','TcxTabControl','TdxBarControl','TdxBarDockControl','TdxDockSite','TfmFW_WallPaper','TcxButton','MDIClient','TApplication','SoPY_Status'):
                has_mdi = True; break
        except: pass

    print(f" 输入框:{has_input} MDI:{has_mdi}")

    if has_input:
        print(f"\n  *** 成功! 项{idx} 订舱管理已打开 ***")
        item_found = True
        ss(mw, f"t_success_item{idx}.png")

        # ===== 4. 检索 SB-S26070007 =====
        print("\n[3/3] 检索 SB-S26070007...")
        all_i = []
        def scan_a(ctl,d=0):
            if d>6: return
            try:
                t=(ctl.window_text() or "")[:80]
                if ctl.is_visible(): all_i.append((t,ctl.class_name(),ctl.rectangle()))
                for ch in ctl.children(): scan_a(ch,d+1)
            except: pass
        scan_a(mw)

        inputs = [c for c in all_i if c[1] in ('TcxTextEdit','TEdit','Edit')]
        print(f"  输入框: {len(inputs)}")
        for c in inputs: print(f"    [{c[1]}] '{c[0]}' @ {c[2]}")

        if inputs:
            r=inputs[0][2]
            cx,cy=(r.left+r.right)//2,(r.top+r.bottom)//2
            print(f"\n输入 '{input_str or 'SB-S26070007'}' @ ({cx},{cy})...")
            clk(cx,cy); time.sleep(0.3)
            send_keys("^a{BACKSPACE}"); time.sleep(0.2)
            send_keys("SB-S26070007"); time.sleep(0.5)
            ss(mw, "t_input.png")
            send_keys("{ENTER}"); time.sleep(3)
            ss(mw, "t_results.png")

            # 找结果
            res = []
            def scan_r(ctl,d=0):
                if d>6: return
                try:
                    t=(ctl.window_text() or "")[:80]
                    if ctl.is_visible(): res.append((t,ctl.class_name(),ctl.rectangle()))
                    for ch in ctl.children(): scan_r(ch,d+1)
                except: pass
            scan_r(mw)
            found=[c for c in res if "SB-S26070007" in c[0]]
            if found:
                r=found[0][2]
                cx,cy=(r.left+r.right)//2,(r.top+r.bottom)//2
                print(f"双击 ({cx},{cy})...")
                dclk(cx,cy); time.sleep(3)
                ss(mw, "t_edit.png")
                for w in app.windows():
                    if w.is_visible() and w.class_name() not in ("TfmMainD","TApplication","SoPY_Status","TTrayIcon"):
                        ss(w, "t_edit_form.png")
                        print(f"编辑窗口: '{w.window_text()[:60]}' ({w.class_name()})")
            else:
                print("未找到 SB-S26070007 记录")
                ss(mw, "t_no_result.png")
        break

    if has_mdi:
        print("    错误模块，关闭...")
        send_keys('{ESC}'); time.sleep(0.3); send_keys('{ESC}'); time.sleep(0.3)
        send_keys('^F4'); time.sleep(0.5)

    # 关闭菜单
    send_keys('{ESC}'); time.sleep(0.3)
    send_keys('{ESC}'); time.sleep(0.3)

if not item_found:
    print("未找到带输入框的菜单项")

print(f"\n截图: {SCREENSHOT_DIR}")
print("="*60)
