# -*- coding: utf-8 -*-
"""
佰信 v4 — 完整导航：基本操作→主菜单(模式切换)→海运操作→订舱管理→检索
v4 关键发现: "主菜单"切换后第二行按钮在 y=56, 海运操作在 x=146
"""
import sys, time, ctypes, win32gui, win32api
sys.stdout.reconfigure(encoding='utf-8')

PID = 5804
SCREENSHOT_DIR = r"D:\OAIW\_baixin_screenshots"
import pathlib; pathlib.Path(SCREENSHOT_DIR).mkdir(exist_ok=True)

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
    u.SendInput(1, ctypes.byref(inp(1|0x8000)), ctypes.sizeof(I())); time.sleep(0.05)
    u.SendInput(1, ctypes.byref(inp(2)), ctypes.sizeof(I())); time.sleep(0.1)
    u.SendInput(1, ctypes.byref(inp(4)), ctypes.sizeof(I()))
    print("    click (%d,%d)" % (x,y))

def dclk(x,y): clk(x,y); time.sleep(0.1); clk(x,y)

def focus(hwnd):
    try: win32gui.SetForegroundWindow(hwnd); time.sleep(0.3)
    except: pass

def find_menus():
    wins = []
    def cb(h, _):
        wins.append(h); return True
    win32gui.EnumWindows(cb, None)
    menus = []
    for w in wins:
        try:
            if 'Menu' in win32gui.GetClassName(w) and win32gui.IsWindowVisible(w):
                r = win32gui.GetWindowRect(w)
                if 60 < r[2]-r[0] < 500:
                    menus.append((w, r))
        except: pass
    return menus

def wait_for_menu(timeout=3, min_h=80):
    start = time.time()
    while time.time() - start < timeout:
        menus = find_menus()
        if menus:
            mr = max(menus, key=lambda x: x[1][3]-x[1][1])
            h = mr[1][3]-mr[1][1]
            if h > min_h:
                return mr
        time.sleep(0.2)
    return None

def close_menus():
    for _ in range(3):
        send_keys('{ESC}'); time.sleep(0.2)

def wait_menu_gone(timeout=3):
    start = time.time()
    while time.time() - start < timeout:
        if not find_menus():
            return True
        time.sleep(0.2)
    return False

# ===== 1. Connect =====
print("="*60)
print("Baixin v4 - jbcz -> zjcd -> hycz -> dcgl -> search")
print("="*60)

app = Application(backend="win32").connect(process=PID)
mw = None
for w in app.windows():
    try:
        if w.is_visible() and w.class_name() == "TfmMainD": mw = w; break
    except: pass
if not mw: print("main window not found"); sys.exit(1)

hwnd = mw.handle; wr = mw.rectangle()
print("main window: 0x%08x %s" % (hwnd, wr))
focus(hwnd); time.sleep(1)

import pyautogui, easyocr, cv2
pyautogui.FAILSAFE = False
print("loading EasyOCR...")
reader = easyocr.Reader(['ch_sim', 'en'], gpu=False, verbose=False)

# ===== Step 1: Click "基本操作" (first toolbar button) =====
print("\n" + "="*50)
print("Step 1: click jbcz (toolbar x_off=40)")
print("="*50)

close_menus(); time.sleep(0.5)
pyautogui.screenshot(SCREENSHOT_DIR + "\\v4_step0.png")

# Click at toolbar position (x=32 is x_off=40 from window left=-8)
toolbar_y = wr.top + 34
focus(hwnd)
clk(wr.left + 40, toolbar_y)
time.sleep(0.5)

# Check if menu popped up
m1 = wait_for_menu(3)
if not m1:
    print("No menu after first click, trying nearby positions...")
    for x_off in range(30, 100, 5):
        clk(wr.left + x_off, toolbar_y)
        m1 = wait_for_menu(1.5)
        if m1:
            print("  Found at x_off=%d" % x_off)
            break
    if not m1:
        print("FAIL: cannot open first menu"); sys.exit(1)

print("Menu 1: %s" % (str(m1[1]),))
pyautogui.screenshot(SCREENSHOT_DIR + "\\v4_menu1.png")

# ===== Step 2: Click "主菜单" in menu =====
print("\n" + "="*50)
print("Step 2: click 'zhu caidan' in menu 1")
print("="*50)

mr1 = m1[1]
menu1_img = pyautogui.screenshot(region=(mr1[0], mr1[1], mr1[2]-mr1[0], mr1[3]-mr1[1]))
menu1_img.save(SCREENSHOT_DIR + "\\v4_menu1_content.png")
menu1_cv = cv2.imread(SCREENSHOT_DIR + "\\v4_menu1_content.png")

# check OCR for zhu caidan
items1 = []
for bbox, text, conf in reader.readtext(menu1_cv):
    text = text.strip()
    if len(text) >= 2 and conf > 0.3:
        x1,y1 = int(bbox[0][0]), int(bbox[0][1])
        x2,y2 = int(bbox[2][0]), int(bbox[2][1])
        cx = mr1[0] + (x1+x2)//2
        cy = mr1[1] + (y1+y2)//2
        items1.append((cx, cy, text, conf))

zjcd_pos = None
for cx, cy, txt, conf in items1:
    if any(t in txt for t in ['主菜单', '主莱单']):
        zjcd_pos = (cx, cy)
        print("  Found '%s' @ (%d,%d) conf=%.2f" % (txt, cx, cy, conf))
        break

if not zjcd_pos:
    print("  'zhu caidan' not found. Menu items:")
    for cx, cy, txt, conf in items1:
        print("    '%s' @ (%d,%d) conf=%.2f" % (txt, cx, cy, conf))
    close_menus(); sys.exit(1)

clk(zjcd_pos[0], zjcd_pos[1])
print("  Waiting for menu 1 to close...")
wait_menu_gone(3)
time.sleep(1)
pyautogui.screenshot(SCREENSHOT_DIR + "\\v4_after_zjcd.png")

# ===== Step 3: Click "海运操作" at x=146, y=56 =====
print("\n" + "="*50)
print("Step 3: click 'haiyun caozuo' @ (146,56)")
print("="*50)

# The second row of buttons is at y=56 after 主菜单 mode switch
# 海运操作 is at x=146 (OCR verified)
# Note: 海运操作 likely opens a module directly (not a popup menu)
clk(146, 56)
time.sleep(3)

# Take a screenshot to see what changed
pyautogui.screenshot(SCREENSHOT_DIR + "\\v4_after_hy.png")
print("  Screenshot saved. Scanning for 'dingcang' in main window...")

# ===== Step 4: Find "订舱管理" in the opened module interface =====
print("\n" + "="*50)
print("Step 4: find 'dingcang guanli' in UI")
print("="*50)

# Scan the full screen for 订舱管理 text
full = pyautogui.screenshot()
full.save(SCREENSHOT_DIR + "\\v4_full_after_hy.png")
full_cv = cv2.imread(SCREENSHOT_DIR + "\\v4_full_after_hy.png")

# Also check for popup menus (海运操作 might open a submenu after all)
m3 = wait_for_menu(2)
dcgl_pos = None

if m3:
    print("  Popup menu found: %s" % (str(m3[1]),))
    mr3 = m3[1]
    menu3_img = pyautogui.screenshot(region=(mr3[0], mr3[1], mr3[2]-mr3[0], mr3[3]-mr3[1]))
    menu3_img.save(SCREENSHOT_DIR + "\\v4_menu_hy_content.png")
    menu3_cv = cv2.imread(SCREENSHOT_DIR + "\\v4_menu_hy_content.png")
    for bbox, text, conf in reader.readtext(menu3_cv):
        text = text.strip()
        if len(text) >= 2 and conf > 0.3:
            x1,y1 = int(bbox[0][0]), int(bbox[0][1])
            x2,y2 = int(bbox[2][0]), int(bbox[2][1])
            cx = mr3[0] + (x1+x2)//2
            cy = mr3[1] + (y1+y2)//2
            print("    '%s' @ (%d,%d) conf=%.2f" % (text, cx, cy, conf))
            if any(t in text for t in ['订舱管理', '订舱', '订仓管理']):
                dcgl_pos = (cx, cy)
else:
    print("  No popup menu. 海运操作 likely opened module directly.")
    print("  Scanning full screen for 'dingcang'...")
    # Scan the full screen for 订舱管理
    for bbox, text, conf in reader.readtext(full_cv):
        text = text.strip()
        if any(t in text for t in ['订舱管理', '订舱', '订仓管理']):
            x1,y1 = int(bbox[0][0]), int(bbox[0][1])
            x2,y2 = int(bbox[2][0]), int(bbox[2][1])
            cx = (x1+x2)//2; cy = (y1+y2)//2
            print("    Found '%s' @ (%d,%d) conf=%.2f" % (text, cx, cy, conf))
            dcgl_pos = (cx, cy)
            break

if not dcgl_pos:
    # Last resort: scan the main window controls for 订舱
    print("  Checking window controls for tabs/buttons labeled dingcang...")
    def scan_ctl(ctl, d=0, md=5):
        if d>md: return
        try:
            if ctl.is_visible():
                t = (ctl.window_text() or "")[:60]
                if t.strip():
                    print("    [%s] '%s' %s" % (ctl.class_name(), t, ctl.rectangle()))
                for ch in ctl.children(): scan_ctl(ch, d+1, md)
        except: pass
    scan_ctl(mw)

    print("\n  Full screen text dump:")
    for bbox, text, conf in reader.readtext(full_cv):
        text = text.strip()
        if len(text) >= 2 and conf > 0.4:
            x1,y1 = int(bbox[0][0]), int(bbox[0][1])
            print("    (%d,%d) conf=%.2f '%s'" % (x1, y1, conf, text))

if not dcgl_pos:
    print("FAIL: cannot find dingcang guanli")
    sys.exit(1)

print("  Clicking 'dingcang' @ (%d,%d)..." % (dcgl_pos[0], dcgl_pos[1]))
clk(dcgl_pos[0], dcgl_pos[1])
time.sleep(3)
pyautogui.screenshot(SCREENSHOT_DIR + "\\v4_booking.png")
print("\n*** DINGCANG GUANLI OPENED (hopefully)! ***")

# ===== Step 5: Search for SB-S26070007 =====
print("\n" + "="*50)
print("Step 5: search SB-S26070007")
print("="*50)
time.sleep(2)

def scan_ctrl(ctl, d=0, md=6):
    items = []
    if d > md: return items
    try:
        if ctl.is_visible():
            items.append((ctl.window_text()[:80], ctl.class_name(), ctl.rectangle()))
            for ch in ctl.children(): items.extend(scan_ctrl(ch, d+1, md))
    except: pass
    return items

all_i = scan_ctrl(mw)
inputs = [c for c in all_i if c[1] in ('TcxTextEdit','TEdit','Edit')]
print("  input boxes: %d" % len(inputs))
for c in inputs[:5]:
    print("    [%s] '%s' @ %s" % (c[1], c[0], c[2]))

if inputs:
    r = inputs[0][2]
    cx, cy = (r.left+r.right)//2, (r.top+r.bottom)//2
    print("  type SB-S26070007 @ (%d,%d)..." % (cx, cy))
    clk(cx, cy); time.sleep(0.3)
    send_keys("^a{BACKSPACE}"); time.sleep(0.2)
    send_keys("SB-S26070007"); time.sleep(0.5)
    send_keys("{ENTER}"); time.sleep(3)

    res = scan_ctrl(mw)
    found = [c for c in res if "SB-S26070007" in c[0]]
    if found:
        r = found[0][2]
        cx2, cy2 = (r.left+r.right)//2, (r.top+r.bottom)//2
        print("  Found! double click (%d,%d)..." % (cx2, cy2))
        dclk(cx2, cy2); time.sleep(3)
        for w in app.windows():
            try:
                if w.is_visible() and w.class_name() not in ("TfmMainD","TApplication","SoPY_Status","TTrayIcon"):
                    print("  Edit window: '%s' (%s) %s" % (w.window_text()[:60], w.class_name(), w.rectangle()))
            except: pass
    else:
        print("  SB-S26070007 not found")
        pyautogui.screenshot(SCREENSHOT_DIR + "\\v4_no_result.png")
else:
    print("  no input boxes")
    pyautogui.screenshot(SCREENSHOT_DIR + "\\v4_no_input.png")

print("\nDone. Screenshots: %s" % SCREENSHOT_DIR)
print("="*60)
