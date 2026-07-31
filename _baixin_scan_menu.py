"""
佰信 — 扫描海运操作下拉菜单（兼容窗口位置漂移）
"""
import sys, time, subprocess, ctypes, win32gui, win32api
sys.stdout.reconfigure(encoding='utf-8')

BAIXIN_PATH = r"D:\Best-Hint\BestLOG\BestLOGFW.exe"
USERNAME = "AI海运操作"
PASSWORD = "xu1264"
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

# ===== 1. 启动 & 登录 =====
print("="*60)
print("佰信 — 精确扫描海运操作菜单 v2")
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
print(f"主窗口: 0x{hwnd:08x}")
focus(hwnd)

for ch in mw.children():
    if ch.class_name()=="TPanel" and ch.is_visible():
        r=ch.rectangle(); dclk((r.left+r.right)//2, (r.top+r.bottom)//2); time.sleep(3); break

ss(mw, "s_01_main.png")
wr = mw.rectangle()
print(f"窗口: ({wr.left},{wr.top})-({wr.right},{wr.bottom})")

# ===== 2. 探测"海运操作"菜单位置 =====
# DevExpress条形菜单: 第一个项目在x=wr.left+45~55左右
# X坐标: 菜单项间隔约80-96px
# Y坐标: 菜单栏在窗口顶部偏下一点，约wr.top+40~55
print("\n[探测] 找海运操作菜单位置...")

HAIYUN_X = None
HAIYUN_Y = wr.top + 48  # 菜单栏Y坐标
menu_win = None
menu_r = None

# 方式A: 从x+50到x+350逐段点击找弹出菜单
for x_off in range(150, 500, 10):
    test_x = wr.left + x_off
    focus(hwnd); time.sleep(0.15)
    clk(test_x, HAIYUN_Y); time.sleep(1.5)

    try:
        for w in app.windows():
            if w.is_visible() and "Menu" in w.class_name():
                try:
                    mr = w.rectangle()
                    if mr.width() < 500 and mr.height() > 50:
                        if mr.height() > 150:
                            HAIYUN_X = test_x
                            menu_win = w
                            menu_r = mr
                            print(f"  菜单弹出 @ x_off={x_off} ({test_x},{HAIYUN_Y}) -> {mr} (高{mr.height()}px ✓)")
                            ss(w, "s_menu_found.png")
                            break
                        else:
                            print(f"  小菜单 @ x_off={x_off} 高{mr.height()}px，跳过")
                except: pass
    except: pass
    if menu_win: break
    send_keys('{ESC}'); time.sleep(0.2)

if not menu_win:
    print("  方式A失败，尝试方式B...")
    # 方式B: 菜单栏Y也可能不同
    for y_off in [38, 42, 46, 50, 54, 58, 62, 66]:
        test_y = wr.top + y_off
        for x_off in range(45, 400, 15):
            test_x = wr.left + x_off
            focus(hwnd); time.sleep(0.1)
            clk(test_x, test_y); time.sleep(1.2)
            for w in app.windows():
                if w.is_visible() and "Menu" in w.class_name():
                    mr = w.rectangle()
                    if mr.width() < 500 and mr.height() > 50:
                        HAIYUN_X = test_x; HAIYUN_Y = test_y
                        menu_win = w; menu_r = mr
                        print(f"  菜单弹出 @ x_off={x_off} y_off={y_off} -> {mr}")
                        break
            if menu_win: break
            send_keys('{ESC}'); time.sleep(0.15)
        if menu_win: break

if not menu_win:
    print("无法弹出菜单"); sys.exit(1)

print(f"\n海运操作: ({HAIYUN_X},{HAIYUN_Y})")
print(f"菜单区域: {menu_r} 宽{menu_r.width()} 高{menu_r.height()}")

# ===== 3. 扫描菜单项 =====
# 菜单由DevExpress TdxBarSubMenuControl渲染，子项HWND不可见
# 使用视觉分析或逐项点击
print("\n[扫描] 用视觉分析菜单内容...")

# 第一次: 截菜单图 + 视觉识别
menu_pic = ss(menu_win, "s_menu_items.png")

# 用API分析
import base64, httpx, json, re
def ask_vision(img_path, question):
    if not img_path: return None
    b64 = base64.b64encode(open(img_path, "rb").read()).decode()
    payload = {
        "model": "meta/llama-3.2-90b-vision-instruct",
        "messages": [{"role":"user","content":[
            {"type":"text","text":question},
            {"type":"image_url","image_url":{"url":f"data:image/png;base64,{b64}"}}
        ]}],
        "temperature":0.01,"max_tokens":512
    }
    try:
        resp = httpx.post("https://integrate.api.nvidia.com/v1/chat/completions",
            json=payload,
            headers={"Authorization":"Bearer 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","Content-Type":"application/json"},
            timeout=30)
        if resp.status_code==200:
            return resp.json()["choices"][0]["message"]["content"]
    except: return None

vision_r = ask_vision(menu_pic, """This is a vertical popup menu (DevExpress TdxBarSubMenuControl) from BestLOG logistics software.
The menu is the "海运操作" (Sea Freight Operations) dropdown.

List ALL menu item texts visible in this menu, in order from top to bottom.
Particularly look for "订舱管理" (Booking Management) or items containing "订舱" (booking).

Return format (JSON, no markdown):
{"items": [{"text":"...", "y_offset":N}, ...]}
where y_offset is the pixel distance from the top of this menu image.""")

if vision_r:
    print(f"  视觉回复: {vision_r[:400]}")
    jm = re.search(r'\{.*"items".*\}', vision_r, re.DOTALL)
    if jm:
        try:
            items = json.loads(jm.group()).get("items", [])
            print(f"  解析到 {len(items)} 个菜单项")
            for i, item in enumerate(items):
                print(f"    [{i+1}] '{item.get('text','')}' y_off={item.get('y_offset','?')}")
            # 找订舱管理
            booking = [item for item in items if '订舱' in item.get('text','')]
            if booking:
                target = booking[0]
                y_off = target.get('y_offset', 0)
                target_y = menu_r.top + y_off
                print(f"\n  *** 找到'{target['text']}' @ y_off={y_off} -> 屏幕y={target_y} ***")
                clk((menu_r.left+menu_r.right)//2, target_y); time.sleep(3)
                ss(mw, "s_booking_clicked.png")
        except: pass

# ===== 4. 如果视觉没找到/超时，退回到逐项点击 =====
print("\n[回退] 逐项点击扫描...")
menu_cx = (menu_r.left + menu_r.right) // 2

# 尝试多种步长
for step in [26, 22, 20]:
    print(f"  步长 {step}px...")
    for idx in range(1, 25):
        item_y = menu_r.top + step // 2 + (idx - 1) * step
        if item_y > menu_r.bottom - 5: break

        # 重新打开菜单
        focus(hwnd); time.sleep(0.15)
        clk(HAIYUN_X, HAIYUN_Y); time.sleep(2)

        # 验证菜单已打开
        menu_ok = False
        for w in app.windows():
            if w.is_visible() and "Menu" in w.class_name():
                mr = w.rectangle()
                if mr.width() < 500:
                    menu_ok = True
                    menu_r = mr
                    break
        if not menu_ok:
            print("    菜单未弹出")
            break

        print(f"    项 {idx}: y={item_y}...")
        clk(menu_cx, item_y); time.sleep(3)

        # 检查界面
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
                    has_mdi = True
                    print(f"      MDI: {ch.class_name()} '{ch.window_text()[:40]}'")
                    break
            except: pass
        print(f"      输入框:{has_input} MDI:{has_mdi}")

        if has_input:
            print(f"\n  *** 成功! 项{idx}带输入框 ***")
            ss(mw, f"s_success_item{idx}.png")

            # 检索
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
            if inputs:
                r=inputs[0][2]
                cx,cy=(r.left+r.right)//2,(r.top+r.bottom)//2
                print(f"\n[检索] ({cx},{cy})...")
                clk(cx,cy); time.sleep(0.3)
                send_keys("^a{BACKSPACE}"); time.sleep(0.2)
                send_keys("SB-S26070007"); time.sleep(0.5)
                ss(mw, "s_input.png")
                send_keys("{ENTER}"); time.sleep(3)
                ss(mw, "s_results.png")

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
                    dclk((r.left+r.right)//2,(r.top+r.bottom)//2); time.sleep(3)
                    ss(mw, "s_edit.png")
                    for w in app.windows():
                        if w.is_visible() and w.class_name() not in ("TfmMainD","TApplication","SoPY_Status","TTrayIcon"):
                            ss(w, "s_edit_form.png")
                            print(f"编辑窗口: '{w.window_text()[:60]}' ({w.class_name()})")
            sys.exit(0)

        if has_mdi:
            print("    错误模块，关闭...")
            send_keys('{ESC}'); time.sleep(0.3)
            send_keys('{ESC}'); time.sleep(0.3)
            send_keys('^F4'); time.sleep(0.5)

        # 关闭菜单
        send_keys('{ESC}'); time.sleep(0.3)

print("\n未找到目标")
print(f"截图: {SCREENSHOT_DIR}")
