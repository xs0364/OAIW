"""
佰信 — 修复菜单导航问题 v2
策略：截图菜单 → 视觉识别每个选项的精确坐标 → 点击对应位置
"""
import sys, time, subprocess, json, ctypes, base64, io as iomod, re
from pathlib import Path
sys.stdout = iomod.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BAIXIN_PATH = r"D:\Best-Hint\BestLOG\BestLOGFW.exe"
BAIXIN_CWD  = r"D:\Best-Hint\BestLOG"
USERNAME = "AI海运操作"
PASSWORD = "xu1264"
SCREENSHOT_DIR = Path(r"D:\OAIW\_baixin_screenshots")
SCREENSHOT_DIR.mkdir(exist_ok=True)

from pywinauto import Application
from pywinauto.keyboard import send_keys
import win32gui, win32api, httpx

API_KEY = "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"
API_URL = "https://integrate.api.nvidia.com/v1"

# === Win32 SendInput click ===
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
    u.SendInput(1, ctypes.byref(inp(1|0x8000)), ctypes.sizeof(I())); time.sleep(0.05)
    u.SendInput(1, ctypes.byref(inp(2)), ctypes.sizeof(I())); time.sleep(0.1)
    u.SendInput(1, ctypes.byref(inp(4)), ctypes.sizeof(I()))

def hover(x, y):
    """只移动鼠标到位置，不点击"""
    sw=win32api.GetSystemMetrics(0); sh=win32api.GetSystemMetrics(1)
    ax=int(x*65535/sw); ay=int(y*65535/sh)
    u=ctypes.windll.user32
    i=I(); i.type=0; i.mi=M(ax,ay,0,1|0x8000,0,None)  # MOVE | ABSOLUTE
    u.SendInput(1, ctypes.byref(i), ctypes.sizeof(I()))

def dclick(x, y): click(x,y); time.sleep(0.15); click(x,y)

def focus(hwnd):
    try: win32gui.SetForegroundWindow(hwnd); time.sleep(0.3)
    except: pass

def ss(win, name):
    try:
        img=win.capture_as_image(); p=SCREENSHOT_DIR/name; img.save(str(p))
        print(f"  [截图] {name}"); return p
    except: return None

def ask_vision(img_path, question):
    if not img_path or not Path(img_path).exists(): return None
    b64=base64.b64encode(open(img_path,"rb").read()).decode()
    payload={
        "model":"meta/llama-3.2-90b-vision-instruct",
        "messages":[{"role":"user","content":[
            {"type":"text","text":question},
            {"type":"image_url","image_url":{"url":f"data:image/png;base64,{b64}"}}
        ]}],
        "temperature":0.01,"max_tokens":1024
    }
    try:
        resp=httpx.post(f"{API_URL}/chat/completions",json=payload,
            headers={"Authorization":f"Bearer {API_KEY}","Content-Type":"application/json"},timeout=60)
        if resp.status_code==200:
            return resp.json()["choices"][0]["message"]["content"]
        else:
            print(f"  [API错误] {resp.status_code}: {resp.text[:100]}")
            return None
    except Exception as e:
        print(f"  [异常] {e}"); return None

# ===== 1. 启动 & 登录 =====
print("="*60)
print("佰信 — 菜单修复 v2（视觉定位+精确点击）")
print("="*60)

subprocess.run(["taskkill","/f","/im","BestLOGFW.exe"],capture_output=True)
time.sleep(1.5)
subprocess.Popen([BAIXIN_PATH],cwd=BAIXIN_CWD); time.sleep(5)

app=Application(backend="win32").connect(path=BAIXIN_PATH,timeout=30)
lw=app.window(class_name="TfmLogin"); lw.wait("visible",timeout=10)
lx=lw.child_window(class_name="TcxTextEdit",found_index=0)
lx.click_input(); time.sleep(0.3); lx.type_keys("^a{BACKSPACE}",with_spaces=True); time.sleep(0.2)
lx.type_keys(USERNAME,with_spaces=True)
lp=lw.child_window(class_name="TcxTextEdit",found_index=1)
lp.click_input(); time.sleep(0.2); lp.type_keys(PASSWORD,with_spaces=True)
ok=next((c for c in lw.descendants(class_name="TcxButton") if "确定" in (c.window_text() or "")),None)
if ok: ok.click_input()
else: lw.click_input(coords=(1020,645))
for i in range(25):
    time.sleep(1)
    try:
        if not lw.is_visible(): break
    except: break
time.sleep(3)

mw=None
for w in app.windows():
    if w.is_visible() and w.class_name()=="TfmMainD": mw=w; break
if not mw: print("主窗口失败"); sys.exit(1)
hwnd=mw.handle; print(f"主窗口: 0x{hwnd:08x}")
focus(hwnd)

# 双击底部面板
for ch in mw.children():
    if ch.class_name()=="TPanel" and ch.is_visible():
        r=ch.rectangle(); dclick((r.left+r.right)//2,(r.top+r.bottom)//2); time.sleep(3); break

# ===== 2. 截图全界面 + 视觉分析主菜单栏 =====
print("\n[1/4] 截图全界面，视觉分析主菜单布局...")
p1=ss(mw,"fix_01_main.png")
wr=mw.rectangle()

# 视觉分析主菜单栏的布局
vision_q=f"""屏幕分辨率: {win32api.GetSystemMetrics(0)}x{win32api.GetSystemMetrics(1)}
主窗口坐标: ({wr.left},{wr.top})-({wr.right},{wr.bottom})

这是佰信(BestLOG)货代管理系统的主界面。
请看最上方一行主菜单（通常在大约y={wr.top+40}到y={wr.top+70}之间，位于窗口顶部附近）。

**关键任务：** 请找出菜单栏中所有菜单项的文字和**精确屏幕坐标**。

回复格式（严格JSON）:
{{"menu_items": [
    {{"text":"海运操作", "x_center":N, "y_center":N}},
    {{"text":"CRM", "x_center":N, "y_center":N}},
    ...]
}}

要求:
- 精确到像素的屏幕坐标(x_center, y_center)
- 只列出最上方主菜单栏的项目（非工具栏图标）
- 特别注意包含"海运"文字的菜单项"""

vision_r=ask_vision(p1, vision_q)
print(f"\n视觉回复:\n{vision_r[:400] if vision_r else '无回复'}")

# 解析视觉回复中的JSON坐标
menu_items=[]
if vision_r:
    jm=re.search(r'\{.*"menu_items".*\}', vision_r, re.DOTALL)
    if jm:
        try:
            parsed=json.loads(jm.group())
            menu_items=parsed.get("menu_items",[])
            print(f"  解析到 {len(menu_items)} 个菜单项坐标")
        except: pass

# 找到"海运操作"的坐标
haiyun_coord=None
if menu_items:
    for item in menu_items:
        if '海运' in item.get('text','') or 'booking' in item.get('text','').lower():
            haiyun_coord=(item['x_center'],item['y_center'])
            print(f"  视觉定位: 海运操作 @ ({haiyun_coord[0]},{haiyun_coord[1]})")
            break

# ===== 3. 打开"海运操作"菜单 =====
print("\n[2/4] 打开'海运操作'下拉菜单...")

# 尝试多种方式找到正确的菜单项位置
menu_open_positions=[]

# 方式A: 视觉识别的坐标
if haiyun_coord:
    menu_open_positions.append(("视觉定位", haiyun_coord[0], haiyun_coord[1]))

# 方式B: 从主窗口相对坐标推算（菜单栏 y≈45-67）
menu_bar_y=wr.top+56  # 菜单栏中间
for x_offset in [50, 80, 110, 140, 170, 200, 230, 260, 290, 320, 350]:
    menu_open_positions.append((f"x+{x_offset}", wr.left+x_offset, menu_bar_y))

# 方式C: 直接从截图分析推算
# 主窗口宽度约1900，如果菜单项均匀分布，第2-3个可能是"海运操作"
for approx_idx in range(1, 10):
    x=wr.left+approx_idx*80  # 每项约80px
    menu_open_positions.append((f"idx{approx_idx}", x, menu_bar_y))

# 逐个尝试
menu_found=False
menu_win=None
for method, mx, my in menu_open_positions:
    focus(hwnd); time.sleep(0.2)
    click(mx, my); time.sleep(2.5)

    # 检查是否有菜单弹出
    for w in app.windows():
        if w.is_visible() and "Menu" in w.class_name():
            mr=w.rectangle()
            if mr.width()<500 and mr.height()>50:
                menu_found=True; menu_win=w
                print(f"  [菜单弹出] {method} -> ({mr.left},{mr.top})-({mr.right},{mr.bottom})")
                ss(menu_win, "fix_menu_popup.png")
                ss(mw, "fix_02_menu_open.png")
                break
    if menu_found: break
    send_keys('{ESC}'); time.sleep(0.3)  # 关闭可能误点的菜单

if not menu_win:
    print("无法弹出菜单"); sys.exit(1)

mr=menu_win.rectangle()
print(f"\n菜单窗口: ({mr.left},{mr.top})-({mr.right},{mr.bottom}) 宽{mr.width()} 高{mr.height()}")

# ===== 4. 截图菜单 + 视觉识别菜单项位置 =====
print("\n[3/4] 用视觉识别菜单项...")
menu_ss=ss(menu_win, "fix_menu_items.png")

menu_v=ask_vision(menu_ss, f"""这个下拉菜单位于屏幕坐标 ({mr.left},{mr.top})-({mr.right},{mr.bottom})。
请列出所有可见的菜单选项文本，以及每个选项的**屏幕Y坐标**（垂直位置）。

格式要求(JSON):
{{"items": [
    {{"text":"选项文本", "y_center":N, "index":N}},
    ...
]}}

特别注意有没有"订舱管理"、"订舱"、"海运操作"等选项。
其中y_center是选项文字中心位置的屏幕Y坐标值。""")

if menu_v:
    print(f"菜单内容:\n{menu_v[:500]}")

# 解析菜单项坐标
menu_items_coords=[]
if menu_v:
    jm2=re.search(r'\{.*"items".*\}', menu_v, re.DOTALL)
    if jm2:
        try:
            parsed2=json.loads(jm2.group())
            menu_items_coords=parsed2.get("items",[])
            print(f"  解析到 {len(menu_items_coords)} 个菜单项")
        except: pass

# ===== 5. 点击"订舱管理" =====
print("\n[4/4] 点击菜单项...")
target_item=None

# 优先从视觉结果找"订舱管理"
for item in menu_items_coords:
    if '订舱' in item.get('text',''):
        target_item=item
        print(f"  视觉目标: {item['text']} @ y={item['y_center']}")
        break

if target_item:
    # 有视觉坐标 → 直接点击
    item_y=target_item['y_center']
    item_x=(mr.left+mr.right)//2  # 水平居中

    print(f"  点击菜单项: ({item_x},{item_y})...")
    # hover一下再点击，给UI反应时间
    hover(item_x, item_y); time.sleep(0.5)
    click(item_x, item_y); time.sleep(3)
else:
    # 没有视觉坐标 → 逐个点击菜单项
    print("  没有视觉坐标，逐个扫描菜单项...")
    item_h=26
    n_items=max(1, mr.height()//item_h)
    print(f"  菜单高{mr.height()}px，每项~{item_h}px，约{n_items}项")

    for idx in range(n_items):
        item_cx=(mr.left+mr.right)//2
        item_cy=mr.top+item_h//2+idx*item_h
        if item_cy>mr.bottom-4: break

        print(f"  尝试项 {idx+1}: ({item_cx},{item_cy})...")
        hover(item_cx, item_cy); time.sleep(0.3)
        click(item_cx, item_cy); time.sleep(3)

        # 检查是否打开了功能模块
        new_items=[]
        def scan(ctl,d=0):
            if d>4: return
            try:
                t=(ctl.window_text() or "")[:60]
                if t.strip() and ctl.is_visible(): new_items.append((t,ctl.class_name()))
                for ch in ctl.children(): scan(ch,d+1)
            except: pass
        scan(mw)

        has_input=any(c[1] in ('TcxTextEdit','TEdit','Edit') for c in new_items)
        has_mdi=False
        for ch in mw.children():
            try:
                if ch.is_visible() and ch.class_name() not in ('TPanel','TdxDockControl','TcxSplitter','TdxStatusBar','TcxTabControl','TdxBarControl','TdxBarDockControl','TdxDockSite','TfmFW_WallPaper','TcxButton','MDIClient','TApplication','SoPY_Status'):
                    has_mdi=True; break
            except: pass

        print(f"    输入框:{has_input} MDI:{has_mdi}")

        if has_input or has_mdi:
            print(f"  [成功] 项 {idx+1} 打开了功能界面!")
            ss(mw, "fix_03_module_open.png")

            # 如果打开了，就检索
            if has_input:
                all_i=[]
                def scan_a(ctl,d=0):
                    if d>5: return
                    try:
                        t=(ctl.window_text() or "")[:80]
                        if ctl.is_visible(): all_i.append((t,ctl.class_name(),ctl.rectangle()))
                        for ch in ctl.children(): scan_a(ch,d+1)
                    except: pass
                scan_a(mw)
                inputs=[c for c in all_i if c[1] in ('TcxTextEdit','TEdit','Edit')]
                if inputs:
                    r=inputs[0][2]
                    cx,cy=(r.left+r.right)//2,(r.top+r.bottom)//2
                    print(f"\n[检索] 输入框 ({cx},{cy})...")
                    click(cx,cy); time.sleep(0.3)
                    send_keys("^a{BACKSPACE}"); time.sleep(0.2)
                    send_keys("SB-S26070007"); time.sleep(0.5)
                    ss(mw, "fix_04_input.png")
                    send_keys("{ENTER}"); time.sleep(3)
                    ss(mw, "fix_05_results.png")

                    # 找结果
                    res=[]
                    def scan_r(ctl,d=0):
                        if d>5: return
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
                        ss(mw, "fix_06_edit.png")
                        # 截图编辑窗口
                        for w in app.windows():
                            if w.is_visible() and w.class_name() not in ("TfmMainD","TApplication","SoPY_Status","TTrayIcon"):
                                ss(w, "fix_07_edit_form.png")
                                print(f"编辑窗口: '{w.window_text()[:60]}' ({w.class_name()})")
                    else:
                        print("未找到 SB-S26070007 文本")
                        ss(mw, "fix_05b_no_result.png")
            break

        # 重新打开菜单
        send_keys('{ESC}'); time.sleep(0.3); send_keys('{ESC}'); time.sleep(0.3)
        focus(hwnd); time.sleep(0.2)
        # 用之前成功的方法重新打开菜单
        if haiyun_coord:
            click(haiyun_coord[0],haiyun_coord[1]); time.sleep(2.5)
        else:
            for method, mx, my in menu_open_positions[:3]:
                click(mx,my); time.sleep(2)
                for w in app.windows():
                    if w.is_visible() and "Menu" in w.class_name() and w.rectangle().width()<500:
                        menu_win=w; mr=w.rectangle(); break
                if menu_win: break
                send_keys('{ESC}'); time.sleep(0.3)

# ===== 最终 =====
print(f"\n截图: {SCREENSHOT_DIR}")
print("="*60)
