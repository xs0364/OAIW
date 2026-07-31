# -*- coding: utf-8 -*-
"""Probe: navigate to 主菜单 mode, then probe row 2 buttons to find 海运操作"""
import sys, time, ctypes, win32gui, win32api
sys.stdout.reconfigure(encoding="utf-8")

from pywinauto import Application
from pywinauto.keyboard import send_keys
import pyautogui, easyocr, cv2
pyautogui.FAILSAFE = False

app = Application(backend="win32").connect(process=5804)
mw = None
for w in app.windows():
    try:
        if w.is_visible() and w.class_name() == "TfmMainD": mw = w; break
    except: pass
hwnd = mw.handle; wr = mw.rectangle()
print("Main window: %s" % wr)

class M(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]
class I(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("mi", M)]

def clk(x,y):
    sw=win32api.GetSystemMetrics(0); sh=win32api.GetSystemMetrics(1)
    ax=int(x*65535/sw); ay=int(y*65535/sh)
    u=ctypes.windll.user32
    def inp(f): i=I(); i.type=0; i.mi=M(ax,ay,0,f,0,None); return i
    u.SendInput(1, ctypes.byref(inp(1|0x8000)), ctypes.sizeof(I())); time.sleep(0.05)
    u.SendInput(1, ctypes.byref(inp(2)), ctypes.sizeof(I())); time.sleep(0.1)
    u.SendInput(1, ctypes.byref(inp(4)), ctypes.sizeof(I()))
    print("    click (%d,%d)" % (x,y))

def find_menus():
    wins = []
    def cb(h,_): wins.append(h); return True
    win32gui.EnumWindows(cb, None)
    menus = []
    for w in wins:
        try:
            if "Menu" in win32gui.GetClassName(w) and win32gui.IsWindowVisible(w):
                r = win32gui.GetWindowRect(w)
                if 60 < r[2]-r[0] < 500:
                    menus.append((w, r))
        except: pass
    return menus

def wait_menu(t=1.5):
    start = time.time()
    while time.time()-start < t:
        ms = find_menus()
        if ms:
            m = max(ms, key=lambda x: x[1][3]-x[1][1])
            if m[1][3]-m[1][1] > 80:
                return m
        time.sleep(0.2)
    return None

def close_all():
    for _ in range(3):
        send_keys("{ESC}"); time.sleep(0.2)

win32gui.SetForegroundWindow(hwnd); time.sleep(0.5)
close_all()

# Navigate to main menu mode
print("Step 1: click jbcz (x_off=40)...")
clk(32, wr.top+34); time.sleep(2)
print("Step 2: click zhu caidan at (73,55)...")
clk(73, 55); time.sleep(2.5)

# OCR the button row
print("\nLoading OCR...")
reader = easyocr.Reader(["ch_sim","en"], gpu=False, verbose=False)

print("\nStep 3: screenshot button row (y=40-65)...")
btn_row = pyautogui.screenshot(region=(40, 40, 500, 25))
btn_row.save(r"D:\OAIW\_baixin_screenshots\diag_row2.png")
btn_cv = cv2.imread(r"D:\OAIW\_baixin_screenshots\diag_row2.png")
results = reader.readtext(btn_cv)
print("Button row OCR:")
for bbox, text, conf in results:
    text = text.strip()
    if len(text) >= 2 and conf > 0.3:
        x1,y1 = int(bbox[0][0]), int(bbox[0][1])
        x2,y2 = int(bbox[2][0]), int(bbox[2][1])
        cx, cy = 40+(x1+x2)//2, 40+(y1+y2)//2
        print("  (%d,%d) conf=%.2f W=%d '%s'" % (cx, cy, conf, x2-x1, text))

# Probe buttons
print("\nStep 4: probe buttons at y=47...")
# Focus on x=80-170 range where 海运操作 might be between 业务管理 and 空运操作
for x in range(70, 200, 10):
    clk(x, 47)
    m = wait_menu(0.8)
    if m:
        mr = m[1]
        h = mr[3]-mr[1]
        print("  => x=%d MENU! h=%d %s" % (x, h, str(mr)))
        mi = pyautogui.screenshot(region=(mr[0], mr[1], mr[2]-mr[0], mr[3]-mr[1]))
        mi.save(r"D:\OAIW\_baixin_screenshots\diag_submenu_%d.png" % x)
        mi_cv = cv2.imread(r"D:\OAIW\_baixin_screenshots\diag_submenu_%d.png" % x)
        ri = reader.readtext(mi_cv)
        print("    Items:")
        for bbox, text, conf in ri:
            text = text.strip()
            if len(text)>=2 and conf>0.3:
                print("      '%s' conf=%.2f" % (text, conf))
        close_all()
        break
    else:
        print("  x=%d: no menu" % x, end="")

print("\nDone")
