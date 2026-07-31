"""
佰信最终版 — pyautogui截图 + easyocr识别"订舱管理" → 点击 → 检索
"""
import sys, time, subprocess, ctypes, win32gui, win32api
sys.stdout.reconfigure(encoding='utf-8')

BAIXIN_PATH = r"D:\Best-Hint\BestLOG\BestLOGFW.exe"
USERNAME = "AI海运操作"; PASSWORD = "xu1264"
SCREENSHOT_DIR = r"D:\OAIW\_baixin_screenshots"

import pathlib; pathlib.Path(SCREENSHOT_DIR).mkdir(exist_ok=True)
from pywinauto import Application
from pywinauto.keyboard import send_keys

# === Win32 SendInput ===
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

def dclk(x, y): clk(x,y); time.sleep(0.1); clk(x,y)

def focus(hwnd):
    try: win32gui.SetForegroundWindow(hwnd); time.sleep(0.3)
    except: pass

def enum_wins():
    wins = []; win32gui.EnumWindows(lambda h, _: (wins.append(h), True)[1], None); return wins

def find_large_menu():
    """找所有Menu窗口，返回最大的那个"""
    best = None; best_r = None; best_h = 0
    for w in enum_wins():
        try:
            if 'Menu' in win32gui.GetClassName(w) and win32gui.IsWindowVisible(w):
                r = win32gui.GetWindowRect(w)
                h = r[3]-r[1]
                if 60 < r[2]-r[0] < 500 and h > best_h:
                    best = w; best_r = r; best_h = h
        except: pass
    return best, best_r

# ===== 1. 启动 & 登录 =====
print("="*60)
print("佰信 — 图像识别导航（最终版）")
print("="*60)

subprocess.run(["taskkill","/f","/im","BestLOGFW.exe"], capture_output=True); time.sleep(1.5)
subprocess.Popen([BAIXIN_PATH], cwd=r"D:\Best-Hint\BestLOG"); time.sleep(6)

app = Application(backend="win32").connect(path=BAIXIN_PATH, timeout=30)
lw = app.window(class_name="TfmLogin"); lw.wait("visible", timeout=15)

lx = lw.child_window(class_name="TcxTextEdit", found_index=0)
lx.click_input(); lx.type_keys("^a{BACKSPACE}"); lx.type_keys(USERNAME)
lp = lw.child_window(class_name="TcxTextEdit", found_index=1)
lp.click_input(); lp.type_keys(PASSWORD)
ok = next((c for c in lw.descendants(class_name="TcxButton") if "确定" in (c.window_text() or "")), None)
if ok: ok.click_input()

# 等登录完成 → 主窗口出现
print("  等待登录...")
for i in range(40):
    time.sleep(1)
    try:
        if not lw.is_visible():
            print(f"  登录完成 ({i+1}s)")
            break
    except: break
time.sleep(3)

# 找主窗口
mw = None
for w in app.windows():
    try:
        if w.is_visible() and w.class_name() == "TfmMainD": mw = w; break
    except: pass
if not mw:
    print("主窗口未找到，重试..."); time.sleep(5)
    for w in app.windows():
        try:
            if w.is_visible() and w.class_name() == "TfmMainD": mw = w; break
        except: pass
if not mw: print("主窗口失败"); sys.exit(1)

hwnd = mw.handle; wr = mw.rectangle()
print(f"主窗口: 0x{hwnd:08x} {wr}")
focus(hwnd)

# 双击底部Panel
for ch in mw.children():
    if ch.class_name()=="TPanel" and ch.is_visible() and ch.rectangle().top > 900:
        r=ch.rectangle(); dclk((r.left+r.right)//2,(r.top+r.bottom)//2); time.sleep(3); break

print("  主界面已就绪")

# ===== 2. 找到"海运操作"菜单 =====
print("\n[1/4] 定位海运操作菜单...")
toolbar_y = wr.top + 34

# 扫描x_off=40到500找大海运菜单(h>350)
menu_r = None; click_x = None
for x_off in range(40, 500, 5):
    focus(hwnd); time.sleep(0.08)
    clk(wr.left + x_off, toolbar_y); time.sleep(1.2)
    mwnd, mr = find_large_menu()
    if mwnd and mr:
        h = mr[3]-mr[1]
        if h > 350:
            menu_r = mr; click_x = wr.left + x_off
            print(f"  海运操作菜单 @ x_off={x_off} ({mr[0]},{mr[1]})-({mr[2]},{mr[3]}) h={h}")
            break
        send_keys('{ESC}'); time.sleep(0.1)

# Alt备选
if not menu_r:
    print("  尝试Alt键...")
    focus(hwnd); time.sleep(0.2)
    send_keys('%'); time.sleep(1.5)
    for step in range(10):
        send_keys('{DOWN}'); time.sleep(1.5)
        mwnd, mr = find_large_menu()
        if mwnd and mr and mr[3]-mr[1] > 350:
            menu_r = mr; break
        send_keys('{ESC}'); time.sleep(0.3); send_keys('{ESC}'); time.sleep(0.2)
        focus(hwnd); time.sleep(0.2); send_keys('%'); time.sleep(0.5)
        send_keys('{RIGHT}'); time.sleep(0.3)

if not menu_r: print("无法找到菜单"); sys.exit(1)

# ===== 3. OCR找"订舱管理" =====
print(f"\n[2/4] 用OCR识别菜单项位置...")
print(f"  菜单: ({menu_r[0]},{menu_r[1]})-({menu_r[2]},{menu_r[3]})")

import pyautogui
pyautogui.FAILSAFE = False
menu_img = pyautogui.screenshot(region=(
    menu_r[0], menu_r[1], menu_r[2]-menu_r[0], menu_r[3]-menu_r[1]
))
menu_path = f"{SCREENSHOT_DIR}\\f_menu.png"
menu_img.save(menu_path)
print(f"  菜单截图已保存")

print("  加载EasyOCR...")
import easyocr, cv2
reader = easyocr.Reader(['ch_sim', 'en'], gpu=False, verbose=False)
menu_cv = cv2.imread(menu_path)
results = reader.readtext(menu_cv)

print("  OCR结果:")
target_y = None; target_text = ""
for bbox, text, conf in results:
    text = text.strip()
    print(f"    '{text}' conf={conf:.2f} @ y={bbox[0][1]:.0f}")
    if '订舱' in text:
        y_center = int((bbox[0][1] + bbox[2][1]) / 2)
        target_y = menu_r[1] + y_center
        target_text = text
        print(f"  *** 找到 '{text}'! 菜单内y={y_center} 屏幕y={target_y} ***")

# ===== 4. 点击+检索 =====
menu_cx = (menu_r[0] + menu_r[2]) // 2

if target_y:
    # 重新打开菜单再点
    print(f"\n[3/4] 点击'{target_text}' @ ({menu_cx},{target_y})...")
    focus(hwnd); time.sleep(0.15)
    clk(click_x, toolbar_y); time.sleep(2)
    clk(menu_cx, target_y); time.sleep(3)
else:
    print("\n[3/4] OCR未找到，逐项扫描...")
    for idx in range(1, 25):
        focus(hwnd); time.sleep(0.1)
        clk(click_x, toolbar_y); time.sleep(1.2)
        mwnd2, mr2 = find_large_menu()
        if not mwnd2: break
        menu_r = mr2
        step = 22
        item_y = menu_r[1] + step//2 + (idx-1)*step
        if item_y > menu_r[3] - 5: break
        clk(menu_cx, item_y); time.sleep(2.5)

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
        print(f"  项{idx}: y={item_y} 输入框:{has_input} MDI:{has_mdi}")
        if has_input:
            target_y = item_y
            break
        if has_mdi:
            send_keys('{ESC}'); time.sleep(0.3); send_keys('{ESC}'); time.sleep(0.3)
            send_keys('^F4'); time.sleep(0.5)
        send_keys('{ESC}'); time.sleep(0.3)

# ===== 检索 =====
if target_y:
    print(f"\n[4/4] 检索 SB-S26070007...")
    time.sleep(2)

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
    for c in inputs[:5]: print(f"    [{c[1]}] '{c[0]}' @ {c[2]}")

    if inputs:
        r=inputs[0][2]
        cx,cy=(r.left+r.right)//2,(r.top+r.bottom)//2
        print(f"  输入 SB-S26070007...")
        clk(cx,cy); time.sleep(0.3)
        send_keys("^a{BACKSPACE}"); time.sleep(0.2)
        send_keys("SB-S26070007"); time.sleep(0.5)
        send_keys("{ENTER}"); time.sleep(3)

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
            print(f"  双击 ({cx},{cy})...")
            dclk(cx,cy); time.sleep(3)
            for w in app.windows():
                try:
                    if w.is_visible() and w.class_name() not in ("TfmMainD","TApplication","SoPY_Status","TTrayIcon"):
                        print(f"  编辑窗口: '{w.window_text()[:60]}' ({w.class_name()}) {w.rectangle()}")
                except: pass
        else:
            print("  未找到 SB-S26070007 记录")
    else:
        print("  没有输入框")

print(f"\n截图: {SCREENSHOT_DIR}")
print("="*60)
