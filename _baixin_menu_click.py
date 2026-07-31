"""
佰信 — 打开菜单 → 逐个点击菜单项 → 找到订舱管理 → 检索 SB-S26070007
"""
import sys, time, subprocess, ctypes, win32gui, win32api
sys.stdout.reconfigure(encoding='utf-8')

BAIXIN_PATH = r"D:\Best-Hint\BestLOG\BestLOGFW.exe"
USERNAME = "AI海运操作"
PASSWORD = "xu1264"
SCREENSHOT_DIR = r"D:\OAIW\_baixin_screenshots"

from pywinauto import Application
from pywinauto.keyboard import send_keys

# === Win32 click via SendInput ===
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

# ===== 1. 启动 & 登录 =====
print("="*60)
print("佰信 — 菜单点击 → 订舱管理 → 检索")
print("="*60)

subprocess.run(["taskkill","/f","/im","BestLOGFW.exe"], capture_output=True)
time.sleep(1.5)
subprocess.Popen([BAIXIN_PATH], cwd=r"D:\Best-Hint\BestLOG")
time.sleep(4)

app = Application(backend="win32").connect(path=BAIXIN_PATH, timeout=30)
lw = app.window(class_name="TfmLogin")
lw.wait("visible", timeout=10)
lx = lw.child_window(class_name="TcxTextEdit", found_index=0)
lx.click_input(); lx.type_keys("^a{BACKSPACE}"); lx.type_keys(USERNAME)
lp = lw.child_window(class_name="TcxTextEdit", found_index=1)
lp.click_input(); lp.type_keys(PASSWORD)
ok = next((c for c in lw.descendants(class_name="TcxButton") if "确定" in (c.window_text() or "")), None)
if ok: ok.click_input()
for i in range(20):
    time.sleep(1)
    try:
        if not lw.is_visible(): break
    except: break
time.sleep(2)

mw = None
for w in app.windows():
    if w.is_visible() and w.class_name() == "TfmMainD": mw = w; break
if not mw: print("主窗口失败"); sys.exit(1)
hwnd = mw.handle
print(f"主窗口: 0x{hwnd:08x}")
try: win32gui.SetForegroundWindow(hwnd)
except: pass

# 双击面板
for ch in mw.children():
    if ch.class_name()=="TPanel" and ch.is_visible():
        r=ch.rectangle()
        dclk((r.left+r.right)//2, (r.top+r.bottom)//2)
        time.sleep(3); break

ss(mw, "m_01_main.png")
wr = mw.rectangle()

# ===== 2. 打开菜单 =====
print("\n[打开主菜单]...")
try: win32gui.SetForegroundWindow(hwnd); time.sleep(0.3)
except: pass

# 点击主菜单第一个项目
menu_x = wr.left + 50
menu_y = wr.top + 48  # Main Menu y大约在45-55之间
print(f"点击菜单 ({menu_x},{menu_y})...")
clk(menu_x, menu_y)
time.sleep(2.5)

# 找菜单窗口
menu_r = None
for w in app.windows():
    if w.is_visible() and "Menu" in w.class_name():
        mr = w.rectangle()
        if mr.width() < 500:
            menu_r = mr
            print(f"菜单: {mr}")
            ss(w, "m_02_menu.png")
            break

if not menu_r:
    print("菜单未弹出")
    # 尝试其他坐标
    for offset in [60, 70, 80, 90, 100, 110, 120, 140]:
        clk(wr.left + offset, menu_y)
        time.sleep(2)
        for w in app.windows():
            if w.is_visible() and "Menu" in w.class_name():
                mr = w.rectangle()
                if mr.width() < 500:
                    menu_r = mr
                    print(f"菜单位置 (x+{offset}): {mr}")
                    ss(w, f"m_menu_x{offset}.png")
                    break
        if menu_r: break

if not menu_r:
    print("无法弹出菜单"); sys.exit(1)

# ===== 3. 逐个点击菜单项 =====
print(f"\n[点击菜单项] 菜单范围: {menu_r}")
item_h = 26  # 每项约26px
n_items = max(1, menu_r.height() // item_h)
print(f"菜单项数(估): {n_items}")

for idx in range(n_items):
    item_cx = (menu_r.left + menu_r.right) // 2
    item_cy = menu_r.top + item_h // 2 + idx * item_h

    # 确保不超出菜单底部
    if item_cy > menu_r.bottom - 4: break

    print(f"\n  菜单项 {idx+1}: ({item_cx},{item_cy})...")
    clk(item_cx, item_cy)
    time.sleep(3)

    # 检查界面变化
    new_items=[]
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
            if ch.is_visible() and ch.class_name() not in ('TPanel','TdxDockControl','TcxSplitter','TdxStatusBar','TcxTabControl','TdxBarControl','TdxBarDockControl','TdxDockSite','TfmFW_WallPaper','TcxButton','MDIClient'):
                has_mdi = True; break
        except: pass

    print(f"  输入框:{has_input} MDI:{has_mdi}")

    if has_input or has_mdi:
        print(f"  [成功] 菜单项 {idx+1} 打开了功能界面!")
        ss(mw, f"m_03_item{idx+1}_opened.png")

        # ===== 4. 检索 =====
        if has_input:
            items_all=[]
            def scan_a(ctl,d=0):
                if d>6: return
                try:
                    t=(ctl.window_text() or "")[:80]
                    if ctl.is_visible(): items_all.append((t,ctl.class_name(),ctl.rectangle()))
                    for ch in ctl.children(): scan_a(ch,d+1)
                except: pass
            scan_a(mw)
            inputs=[c for c in items_all if c[1] in ('TcxTextEdit','TEdit','Edit')]
            if inputs:
                r=inputs[0][2]
                cx,cy=(r.left+r.right)//2,(r.top+r.bottom)//2
                print(f"\n[检索] 输入框 ({cx},{cy})...")
                clk(cx,cy); time.sleep(0.3)
                send_keys("^a{BACKSPACE}"); time.sleep(0.2)
                send_keys("SB-S26070007"); time.sleep(0.5)
                ss(mw, "m_04_input.png")
                send_keys("{ENTER}"); time.sleep(3)
                ss(mw, "m_05_results.png")

                # 找结果
                res=[]
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
                    print(f"双击 SB-S26070007 ({cx},{cy})...")
                    dclk(cx,cy); time.sleep(3)
                    ss(mw, "m_06_edit.png")
                    # 检查编辑窗口
                    for w in app.windows():
                        if w.is_visible() and w.class_name() not in ("TfmMainD","TApplication","SoPY_Status","TTrayIcon"):
                            ss(w, "m_07_edit_form.png")
                            print(f"编辑窗口: '{w.window_text()[:60]}' ({w.class_name()})")
                else:
                    print("未在控件中找到 SB-S26070007（可能在表格中不可枚举）")
                    ss(mw, "m_05_results_vis.png")
        break

    # 重新打开菜单
    try: win32gui.SetForegroundWindow(hwnd); time.sleep(0.2)
    except: pass
    clk(menu_x, menu_y); time.sleep(2)

# ===== 5. 最终状态 =====
print(f"\n截图: {SCREENSHOT_DIR}")
print("="*60)
