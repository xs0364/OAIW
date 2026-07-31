"""
佰信视觉导航 v2 — 用大模型理解界面，自动导航到订舱管理
"""
import sys, time, subprocess, json, ctypes, base64, io as iomod2, re
from pathlib import Path
sys.stdout = iomod2.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BAIXIN_PATH = r"D:\Best-Hint\BestLOG\BestLOGFW.exe"
BAIXIN_CWD  = r"D:\Best-Hint\BestLOG"
USERNAME = "AI海运操作"
PASSWORD = "xu1264"
SCREENSHOT_DIR = Path(r"D:\OAIW\_baixin_screenshots")
SCREENSHOT_DIR.mkdir(exist_ok=True)
VISION_MODEL = "meta/llama-3.2-90b-vision-instruct"
API_KEY = "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"
API_URL = "https://integrate.api.nvidia.com/v1"

from pywinauto import Application
from pywinauto.keyboard import send_keys
import win32gui, win32api, httpx

# === Win32 click ===
class M(ctypes.Structure):
    _fields_ = [('dx', ctypes.c_long), ('dy', ctypes.c_long),
                ('mouseData', ctypes.c_ulong), ('dwFlags', ctypes.c_ulong),
                ('time', ctypes.c_ulong), ('dwExtraInfo', ctypes.POINTER(ctypes.c_ulong))]
class I(ctypes.Structure):
    _fields_ = [('type', ctypes.c_ulong), ('mi', M)]

def click(x, y):
    sw=win32api.GetSystemMetrics(0); sh=win32api.GetSystemMetrics(1)
    ax=int(x*65535/sw); ay=int(y*65535/sh)
    u=ctypes.windll.user32
    def inp(f): i=I(); i.type=0; i.mi=M(ax,ay,0,f,0,None); return i
    u.SendInput(1, ctypes.byref(inp(1|0x8000)), ctypes.sizeof(I())); time.sleep(0.03)
    u.SendInput(1, ctypes.byref(inp(2)), ctypes.sizeof(I())); time.sleep(0.05)
    u.SendInput(1, ctypes.byref(inp(4)), ctypes.sizeof(I()))

def dclick(x, y): click(x,y); time.sleep(0.1); click(x,y)
def focus(hwnd):
    try: win32gui.SetForegroundWindow(hwnd); time.sleep(0.3)
    except: pass

def ss(win, name):
    try:
        img = win.capture_as_image(); p=SCREENSHOT_DIR/name; img.save(str(p))
        print(f"  [截图] {name}"); return p
    except: return None

def ask_vision(img_path, question):
    b64 = base64.b64encode(open(img_path,"rb").read()).decode()
    payload = {
        "model": VISION_MODEL,
        "messages": [{"role":"user","content":[
            {"type":"text","text":question},
            {"type":"image_url","image_url":{"url":f"data:image/png;base64,{b64}"}}
        ]}],
        "temperature":0.05,"max_tokens":1024
    }
    try:
        resp = httpx.post(f"{API_URL}/chat/completions", json=payload,
            headers={"Authorization":f"Bearer {API_KEY}","Content-Type":"application/json"}, timeout=60)
        if resp.status_code==200:
            c = resp.json()["choices"][0]["message"]["content"]
            print(f"  [视觉] {c[:300]}")
            return c
        else:
            print(f"  [视觉错误] {resp.status_code}: {resp.text[:200]}")
            return None
    except Exception as e:
        print(f"  [视觉异常] {e}")
        return None

# ===== 启动 & 登录 =====
print("="*60)
print("佰信 视觉导航 v2")
print("="*60)
subprocess.run(["taskkill","/f","/im","BestLOGFW.exe"],capture_output=True)
time.sleep(1.5)
subprocess.Popen([BAIXIN_PATH],cwd=BAIXIN_CWD); time.sleep(5)

app = Application(backend="win32").connect(path=BAIXIN_PATH,timeout=30)
lw = app.window(class_name="TfmLogin"); lw.wait("visible",timeout=10)
lx = lw.child_window(class_name="TcxTextEdit",found_index=0)
lx.click_input(); time.sleep(0.3); lx.type_keys("^a{BACKSPACE}",with_spaces=True); time.sleep(0.2)
lx.type_keys(USERNAME,with_spaces=True)
lp = lw.child_window(class_name="TcxTextEdit",found_index=1)
lp.click_input(); time.sleep(0.2); lp.type_keys(PASSWORD,with_spaces=True)
ok = next((c for c in lw.descendants(class_name="TcxButton") if "确定" in (c.window_text() or "")),None)
if ok: ok.click_input()
else: lw.click_input(coords=(1020,645))
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

# ===== 第一步：双击底部面板 =====
print("\n[1/5] 双击底部面板加载模块...")
for ch in mw.children():
    if ch.class_name()=="TPanel" and ch.is_visible():
        r=ch.rectangle(); dclick((r.left+r.right)//2,(r.top+r.bottom)//2)
        time.sleep(3); break
ss(mw,"v2_01_main.png")

# ===== 第二步：视觉分析全界面 =====
print("\n[2/5] 视觉分析全界面...")
full_img = mw.capture_as_image()
full_path = SCREENSHOT_DIR / "v2_02_full.png"
full_img.save(str(full_path))

vision_r = ask_vision(full_path, """这是佰信(BestLOG)货代管理系统的桌面客户端主界面。
请仔细分析整个界面，详细告诉我：

1. **顶部主菜单栏**（通常在窗口最上方、工具栏下方）：列出所有菜单项文字（从左到右）
2. **下方的标签页/模块栏**：列出所有标签文字
3. **左边导航树**（如果有）：列出可见的分组标题
4. **工作区域**：当前显示的是什么内容？
5. **底部状态栏**：有什么文字？

特别注意：中国货代系统中，海运相关功能可能叫"海运操作""海运业务""海运管理"等。
回复格式：
=== 主菜单栏 ===
- 项目1 | 项目2 | ...
=== 模块标签 ===
- 标签1 | 标签2 | ...
=== 左侧导航 ===
...
=== 工作区域 ===
...
=== 底部 ===
...""")

# ===== 第三步：导航到海运操作→订舱管理 =====
print("\n[3/5] 导航...")

# 从视觉回答提取导航信息
nav_found = False
if vision_r:
    # 找"海运"或"订舱"关键词
    has_haiyun = '海运' in vision_r
    has_booking = '订舱' in vision_r

    if has_haiyun or has_booking:
        print(f"  视觉识别到海运/订舱相关: YES")
        # 详细分析界面元素坐标
        coord_r = ask_vision(full_path, """你刚才已经分析了这个界面。
现在我需要精确知道"海运操作"或包含"海运"的菜单项/标签在屏幕上的位置。

请仔细看顶部菜单栏和标签栏，回答：
1. 最上方一行（工具栏下面的那一行文字菜单）有哪些项目？每个的左边缘X坐标大约是多少？
2. 再下面一行（如果有标签页）有哪些项目？每个的左边缘X坐标大约是多少？
3. "海运操作"或"海运XX"在第几行、第几个位置？
4. 如果点击"海运操作"后会出现下拉菜单，菜单里的选项可能有"订舱管理"吗？

请给出每个可点击元素的文字和估算的X坐标。""")

    if '订舱' not in vision_r:
        print("  视觉未直接看到订舱管理，尝试点击海运操作打开菜单再分析...")

# 备用：用Alt打开菜单栏
print("  用Alt激活菜单栏...")
focus(hwnd); time.sleep(0.2)
send_keys('%'); time.sleep(1.5)
ss(mw, "v2_03_alt.png")

# 视觉分析Alt后的状态
alt_r = ask_vision(SCREENSHOT_DIR / "v2_03_alt.png", """Alt键已按下，菜单栏已被激活（某个菜单项应被高亮）。

请回答：
1. 当前高亮的是哪个菜单项？（通常有虚线框或背景色变化）
2. 从左到右列出主菜单栏所有可见菜单项文字
3. 高亮菜单项在屏幕上的大概X坐标范围是多少？
4. 按键盘的 →（右箭头）会移动到哪个菜单项？""")

# 导航到"海运操作"
if alt_r and '海运' in alt_r:
    print("  Alt菜单中有'海运操作'!")
    # 导航到海运操作
    # 估算需要按→的次数
    send_keys('{RIGHT}'); time.sleep(0.5)
    ss(mw, "v2_04_right1.png")
    r2 = ask_vision(SCREENSHOT_DIR / "v2_04_right1.png", "当前高亮的是哪个菜单项？")
    if r2 and '海运' in r2:
        print("  已到'海运操作'!")
        send_keys('{DOWN}'); time.sleep(2)
        ss(mw, "v2_05_haixyun_menu.png")

        # 分析菜单内容
        menu_r = ask_vision(SCREENSHOT_DIR / "v2_05_haixyun_menu.png", """下拉菜单已打开。请列出菜单里所有可见的选项文字。
特别注意有没有"订舱管理"或"订舱"。
如果有，它在第几个位置？""")

        if menu_r and '订舱' in menu_r:
            print("  菜单中有'订舱管理'!")
            # 按↓找到订舱管理
            for attempt in range(6):
                send_keys('{DOWN}'); time.sleep(0.5)
                send_keys('{ENTER}'); time.sleep(3)
                ss(mw, f"v2_06_attempt_{attempt}.png")

                # 检查是否打开了功能界面
                items = []
                def s(ctl,d=0):
                    if d>4: return
                    try:
                        t=(ctl.window_text() or "")[:60]
                        if t.strip() and ctl.is_visible():
                            items.append((t,ctl.class_name()))
                        for ch in ctl.children(): s(ch,d+1)
                    except: pass
                s(mw)
                if any(c[1] in ('TcxTextEdit','TEdit','Edit') for c in items):
                    nav_found = True
                    print("  [成功] 订舱管理已打开!")
                    ss(mw, "v2_07_booking_open.png")
                    break

                # 重开菜单
                send_keys('{ESC}'); time.sleep(0.3)
                send_keys('{ESC}'); time.sleep(0.3)
                focus(hwnd); time.sleep(0.2)
                send_keys('%'); time.sleep(0.5)
                for _ in range(2): send_keys('{RIGHT}'); time.sleep(0.3)
                send_keys('{DOWN}'); time.sleep(1.5)

    else:
        # 继续按→直到找到海运操作
        for _ in range(5):
            send_keys('{RIGHT}'); time.sleep(0.5)
            ss(mw, f"v2_04_right_more.png")
            r3 = ask_vision(SCREENSHOT_DIR / "v2_04_right_more.png", "当前高亮的是哪个菜单项？有没有出现'海运'相关文字？")
            if r3 and '海运' in r3:
                send_keys('{DOWN}'); time.sleep(2)
                ss(mw, "v2_05_menu.png")
                break

        if not nav_found:
            # 尝试点开看到的每个菜单
            for menu_idx in range(3,8):
                focus(hwnd); time.sleep(0.2)
                send_keys('%'); time.sleep(1)
                for _ in range(menu_idx): send_keys('{RIGHT}'); time.sleep(0.3)
                send_keys('{DOWN}'); time.sleep(2)
                ss(mw, f"v2_05_menu_{menu_idx}.png")
                # 检查是否有订舱管理
                r4 = ask_vision(SCREENSHOT_DIR / f"v2_05_menu_{menu_idx}.png", "列出这个下拉菜单所有选项")
                if r4 and '订舱' in r4:
                    for attempt in range(6):
                        send_keys('{DOWN}'); time.sleep(0.3)
                        send_keys('{ENTER}'); time.sleep(2)
                        items2 = []
                        def s2(ctl,d=0):
                            if d>4: return
                            try:
                                t=(ctl.window_text() or "")[:60]
                                if t.strip() and ctl.is_visible(): items2.append((t,ctl.class_name()))
                                for ch in ctl.children(): s2(ch,d+1)
                            except: pass
                        s2(mw)
                        if any(c[1] in ('TcxTextEdit','TEdit','Edit') for c in items2):
                            nav_found = True; break
                        send_keys('{ESC}'); time.sleep(0.3); send_keys('{ESC}'); time.sleep(0.3)
                        focus(hwnd); time.sleep(0.2)
                        send_keys('%'); time.sleep(0.5)
                        for _ in range(menu_idx): send_keys('{RIGHT}'); time.sleep(0.3)
                        send_keys('{DOWN}'); time.sleep(1.5)

                send_keys('{ESC}'); time.sleep(0.3)

else:
    print("  Alt菜单中未找到'海运操作'，尝试逐个菜单...")
    # 尝试每个主菜单项
    for mi in range(3, 10):
        focus(hwnd); time.sleep(0.2)
        send_keys('%'); time.sleep(1)
        for _ in range(mi): send_keys('{RIGHT}'); time.sleep(0.3)
        send_keys('{DOWN}'); time.sleep(2)
        ss(mw, f"v2_05_menu_{mi}.png")
        r5 = ask_vision(SCREENSHOT_DIR / f"v2_05_menu_{mi}.png", "列出该菜单所有选项。特别注意有没有'订舱管理'或'海运操作'。")
        if r5 and ('订舱' in r5 or '海运' in r5):
            print(f"  菜单 {mi} 找到了目标!")
            for attempt in range(8):
                send_keys('{DOWN}'); time.sleep(0.3)
                send_keys('{ENTER}'); time.sleep(2)
                items3 = []
                def s3(ctl,d=0):
                    if d>4: return
                    try:
                        t=(ctl.window_text() or "")[:60]
                        if t.strip() and ctl.is_visible(): items3.append((t,ctl.class_name()))
                        for ch in ctl.children(): s3(ch,d+1)
                    except: pass
                s3(mw)
                if any(c[1] in ('TcxTextEdit','TEdit','Edit') for c in items3):
                    nav_found = True; break
                send_keys('{ESC}'); time.sleep(0.3); send_keys('{ESC}'); time.sleep(0.3)
                focus(hwnd); time.sleep(0.2)
                send_keys('%'); time.sleep(0.5)
                for _ in range(mi): send_keys('{RIGHT}'); time.sleep(0.3)
                send_keys('{DOWN}'); time.sleep(1.5)
            if nav_found: break
        send_keys('{ESC}'); time.sleep(0.3)

# ===== 第四步：检索 =====
print("\n[4/5] 检索 SB-S26070007...")
if nav_found:
    ss(mw, "v2_08_after_nav.png")
    all_i = []
    def scan_all(ctl,d=0):
        if d>5: return
        try:
            t=(ctl.window_text() or "")[:80]
            if ctl.is_visible(): all_i.append((t,ctl.class_name(),ctl.rectangle(),d))
            for ch in ctl.children(): scan_all(ch,d+1)
        except: pass
    scan_all(mw)
    inputs = [c for c in all_i if c[1] in ('TcxTextEdit','TEdit','Edit')]
    print(f"  输入框: {len(inputs)}")
    for c in inputs: print(f"    [{c[1]}] '{c[0]}' {c[2]}")

    if inputs:
        c=inputs[0]; r=c[2]
        cx,cy=(r.left+r.right)//2,(r.top+r.bottom)//2
        click(cx,cy); time.sleep(0.3)
        send_keys("^a{BACKSPACE}"); time.sleep(0.2)
        send_keys("SB-S26070007"); time.sleep(0.3)
        ss(mw, "v2_09_input.png")
        send_keys('{ENTER}'); time.sleep(3)
        ss(mw, "v2_10_results.png")

        # 找结果中 SB-S26070007
        res_i = []
        def scan_r(ctl,d=0):
            if d>5: return
            try:
                t=(ctl.window_text() or "")[:80]
                if ctl.is_visible(): res_i.append((t,ctl.class_name(),ctl.rectangle(),d))
                for ch in ctl.children(): scan_r(ch,d+1)
            except: pass
        scan_r(mw)
        found = [c for c in res_i if 'SB-S26070007' in c[0]]
        print(f"  结果中含 SB-S26070007: {len(found)}")
        for c in found:
            r=c[2]; cx=(r.left+r.right)//2; cy=(r.top+r.bottom)//2
            dclick(cx,cy); time.sleep(3)
            ss(mw, "v2_11_doubleclick.png")
            break

        # 截图打开的界面
        print("\n  打开的编辑界面:")
        for w in app.windows():
            if w.is_visible() and w.class_name() not in ('TfmMainD','TApplication','SoPY_Status','TTrayIcon'):
                print(f"    '{w.window_text()[:60]}' ({w.class_name()}) {w.rectangle()}")
                ss(w, "v2_12_edit_form.png")
    else:
        # 截图让视觉分析
        vm = ask_vision(SCREENSHOT_DIR / "v2_08_after_nav.png",
            "这个界面是佰信系统的功能模块。请分析：1)当前打开的是什么模块？2)检索/查询输入框在哪里？3)按钮有哪些？4)下一步应该怎么操作来查询工作号？")
        print(f"  视觉建议: {vm[:200] if vm else 'N/A'}")
else:
    print("  未能导航到订舱管理")
    ss(mw, "v2_08_failed.png")
    fail_v = ask_vision(SCREENSHOT_DIR / "v2_08_failed.png",
        """我们试图在佰信系统中打开"订舱管理"但失败了。
请分析当前界面：
1. 当前在哪个页面？
2. 顶部有哪些可点击的菜单或标签？
3. 要找到"海运操作"应该点哪里？
4. 请给出具体的导航步骤建议。""")
    print(f"  建议: {fail_v[:200] if fail_v else 'N/A'}")

# ===== 第五步：最终状态 =====
print(f"\n[5/5] 最终截图: {SCREENSHOT_DIR}")
print("="*60)
