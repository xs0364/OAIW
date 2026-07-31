"""
佰信系统 — 基于视觉大模型的自动化导航
用大模型看截图 → 告诉坐标 → 自动操作
"""
import sys, time, subprocess, json, ctypes, base64, io, re
from pathlib import Path
import io as iomod
sys.stdout = iomod.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BAIXIN_PATH = r"D:\Best-Hint\BestLOG\BestLOGFW.exe"
BAIXIN_CWD  = r"D:\Best-Hint\BestLOG"
USERNAME = "AI海运操作"
PASSWORD = "xu1264"
SCREENSHOT_DIR = Path(r"D:\OAIW\_baixin_screenshots")
SCREENSHOT_DIR.mkdir(exist_ok=True)

from pywinauto import Application
from pywinauto.keyboard import send_keys
import win32gui, win32api

# === SendInput Click ===
class M(ctypes.Structure):
    _fields_ = [('dx', ctypes.c_long), ('dy', ctypes.c_long),
                ('mouseData', ctypes.c_ulong), ('dwFlags', ctypes.c_ulong),
                ('time', ctypes.c_ulong), ('dwExtraInfo', ctypes.POINTER(ctypes.c_ulong))]
class I(ctypes.Structure):
    _fields_ = [('type', ctypes.c_ulong), ('mi', M)]

def click_abs(x, y):
    sw = win32api.GetSystemMetrics(0); sh = win32api.GetSystemMetrics(1)
    ax = int(x * 65535 / sw); ay = int(y * 65535 / sh)
    u = ctypes.windll.user32
    def inp(f):
        i = I(); i.type = 0; i.mi = M(ax, ay, 0, f, 0, None)
        return i
    u.SendInput(1, ctypes.byref(inp(1|0x8000)), ctypes.sizeof(I()))
    time.sleep(0.03)
    u.SendInput(1, ctypes.byref(inp(2)), ctypes.sizeof(I()))
    time.sleep(0.05)
    u.SendInput(1, ctypes.byref(inp(4)), ctypes.sizeof(I()))

def double_click_abs(x, y):
    click_abs(x, y)
    time.sleep(0.1)
    click_abs(x, y)

def focus(hwnd):
    try: win32gui.SetForegroundWindow(hwnd); time.sleep(0.3)
    except: pass

def ss(win, name):
    try:
        img = win.capture_as_image()
        p = SCREENSHOT_DIR / name
        img.save(str(p))
        print(f"  [截图] {name} ({p})")
        return p
    except Exception as e:
        print(f"  [截图失败] {name}: {e}")
        return None

def image_to_base64(path):
    """把 PNG 图片转 base64"""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def enumerate_window_tree(main_win):
    """枚举所有控件，输出完整树结构"""
    lines = []
    def _rec(ctl, depth=0):
        if depth > 10: return
        try:
            txt = (ctl.window_text() or "")[:80]
            cls = ctl.class_name()
            r = ctl.rectangle()
            vis = ctl.is_visible()
            lines.append(f"{'  '*depth}[{cls}] '{txt}' {r} vis={vis}")
            for ch in ctl.children():
                _rec(ch, depth+1)
        except:
            pass
    _rec(main_win)
    return '\n'.join(lines)

# === 大模型视觉分析 ===
VISION_MODEL = "nvidia/llama-3.2-90b-vision"  # 先用这个
API_KEY = "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"
API_URL = "https://integrate.api.nvidia.com/v1"

def ask_vision(image_path, question):
    """用视觉大模型分析截图"""
    print(f"\n  [视觉分析] 问: {question}")
    b64 = image_to_base64(image_path)
    data_url = f"data:image/png;base64,{b64}"

    payload = {
        "model": VISION_MODEL,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": question},
                {"type": "image_url", "image_url": {"url": data_url}}
            ]
        }],
        "temperature": 0.1,
        "max_tokens": 2048
    }

    import httpx
    try:
        resp = httpx.post(
            f"{API_URL}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            timeout=30
        )
        if resp.status_code != 200:
            print(f"  API返回 {resp.status_code}: {resp.text[:200]}")
            return None

        result = resp.json()
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        print(f"  [视觉回答] {content[:500]}")
        return content

    except Exception as e:
        print(f"  API调用失败: {e}")
        return None

def ask_deepseek(question, context=""):
    """用DeepSeek做文本分析"""
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是一个桌面自动化专家。分析界面描述，输出精确的操作坐标。"},
            {"role": "user", "content": f"{context}\n\n{question}"}
        ],
        "temperature": 0.1,
        "max_tokens": 1024
    }

    import httpx
    try:
        resp = httpx.post(
            "https://api.deepseek.com/v1/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            timeout=30
        )
        if resp.status_code != 200:
            print(f"  DeepSeek返回 {resp.status_code}")
            return None
        return resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception as e:
        print(f"  DeepSeek调用失败: {e}")
        return None

# ===== 1. 启动 & 登录 =====
print("="*60)
print("佰信 视觉导航 v1 — 截图 → 视觉分析 → 自动操作")
print("="*60)

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
time.sleep(3)

main_win = None
for w in app.windows():
    if w.is_visible() and w.class_name() == 'TfmMainD':
        main_win = w; break
if not main_win: print("主窗口失败"); sys.exit(1)
main_hwnd = main_win.handle
print(f"主窗口: 0x{main_hwnd:08x}")
focus(main_hwnd)
ss(main_win, "vision_01_main.png")

# ===== 2. 双击底部面板 =====
print("\n[阶段1] 双击底部加载模块面板...")
for ch in main_win.children():
    if ch.class_name() == 'TPanel' and ch.is_visible():
        r = ch.rectangle()
        click_abs((r.left+r.right)//2, (r.top+r.bottom)//2)
        time.sleep(0.1)
        click_abs((r.left+r.right)//2, (r.top+r.bottom)//2)
        time.sleep(3)
        ss(main_win, "vision_02_after_panel.png")
        break

# ===== 3. 视觉分析：找"海运操作"位置 =====
print("\n[阶段2] 视觉分析：找顶部导航...")

# 先截取顶部区域
r = main_win.rectangle()
# 顶部导航在 y=20 到 y=90 区域
try:
    full_img = main_win.capture_as_image()
    top_area = full_img.crop((0, 20, r.width(), 90))
    top_path = SCREENSHOT_DIR / "vision_top_nav.png"
    top_area.save(str(top_path))
    print(f"  [顶部截图] {top_path}")
except Exception as e:
    print(f"  顶部截图失败: {e}")

# 用视觉模型分析顶部导航
vision_result = ask_vision(
    SCREENSHOT_DIR / "vision_02_after_panel.png",
    """这是佰信(BestLOG)货代管理系统的桌面客户端界面。
请分析：
1. 顶部菜单/工具栏中有哪些可点击的文字按钮？（如"海运操作""空运""报关"等）
2. 当前显示的是哪个页面？
3. "海运操作"菜单位于屏幕什么位置（估算X坐标）？
4. 最上方有哪些可见的元素？

回复格式：
- 可见菜单项: [名称1, 名称2, ...]
- 当前页面: ...
- 海运操作位于: 屏幕X≈...
- 顶部元素描述: ..."""
)

# ===== 4. 基于视觉结果自动操作 =====
print("\n[阶段3] 基于视觉分析结果自动操作...")

if vision_result:
    # 尝试从视觉结果提取"海运操作"的坐标
    # 保存到文件供后续分析
    with open(SCREENSHOT_DIR / "vision_analysis.txt", "w") as f:
        f.write(vision_result)

    # 查找菜单项坐标
    # 如果视觉说"海运操作"在某个位置，就点击那里
    # 否则采用备用方案

# 备用方案：Alt激活菜单+键盘导航
print("\n[备用] 尝试Alt+键盘导航...")
focus(main_hwnd)
send_keys('%')  # Alt
time.sleep(1)

# 截图Alt后的状态
ss(main_win, "vision_03_alt.png")

# 视觉：现在焦点在哪个菜单项？
vision_alt = ask_vision(
    SCREENSHOT_DIR / "vision_03_alt.png",
    """Alt键已按下，菜单栏被激活。
请分析当前哪个菜单项被高亮（通常有虚线框或反色背景），以及菜单项的名称和大致位置。

回复：
- 当前高亮菜单项: ...
- 所有可见菜单项（从左到右）: ...
- 每个菜单位置（X坐标范围）: ..."""
)

# 根据视觉结果按方向键
# 假设需要按→键2次到"海运操作"再按↓
send_keys('{RIGHT}')
send_keys('{RIGHT}')
send_keys('{DOWN}')
time.sleep(2)
ss(main_win, "vision_04_menu.png")

# 视觉：菜单打开了，里面有什么？
vision_items = ask_vision(
    SCREENSHOT_DIR / "vision_04_menu.png",
    """一个下拉菜单已打开。
请分析：
1. 菜单里有哪些选项？（文字列表）
2. "订舱管理"在第几个？
3. 当前哪个选项被高亮？
4. 整个菜单的屏幕位置（左上角Y坐标和右下角Y坐标）

回复列出所有可见的菜单项文字。"""
)

# ===== 5. 找"订舱管理"并点击 =====
print("\n[阶段4] 找到订舱管理并点击...")
if vision_items and '订舱' in vision_items:
    # 视觉模型已确认有"订舱管理"，按↓键导航到它
    # 假设"订舱管理"在第N项，按N-1次↓
    for _ in range(5):  # 最多试5次
        send_keys('{DOWN}')
        time.sleep(0.5)
        # 检查高亮变化
        send_keys('{ENTER}')
        time.sleep(3)

        # 检查是否有新界面
        new_items = []
        def scan(ctl, d=0):
            if d > 4: return
            try:
                txt = (ctl.window_text() or "")[:60]
                if txt.strip() and ctl.is_visible():
                    new_items.append((txt, ctl.class_name()))
                for ch in ctl.children(): scan(ch, d+1)
            except: pass
        scan(main_win)

        has_input = any(c[1] in ('TcxTextEdit','TEdit','Edit') for c in new_items)
        print(f"    试了{_+1}次, 输入框:{has_input}")

        if has_input:
            print("  [成功] 订舱管理已打开!")
            ss(main_win, "vision_05_booking_open.png")
            break

        # 重开菜单再试
        send_keys('{ESC}'); time.sleep(0.3)
        send_keys('{ESC}'); time.sleep(0.3)
        focus(main_hwnd); time.sleep(0.2)
        send_keys('%'); time.sleep(0.5)
        send_keys('{RIGHT}'); send_keys('{RIGHT}'); send_keys('{DOWN}')
        time.sleep(1.5)
else:
    print("  视觉未识别到订舱管理，尝试逐个菜单项...")
    # 暴力遍历全部菜单项
    for idx in range(8):
        send_keys('{DOWN}')
        time.sleep(0.3)
        send_keys('{ENTER}')
        time.sleep(2)
        new_items2 = []
        def scan2(ctl, d=0):
            if d > 4: return
            try:
                txt = (ctl.window_text() or "")[:60]
                if txt.strip() and ctl.is_visible():
                    new_items2.append((txt, ctl.class_name()))
                for ch in ctl.children(): scan2(ch, d+1)
            except: pass
        scan2(main_win)
        if any(c[1] in ('TcxTextEdit','TEdit','Edit') for c in new_items2):
            print(f"  [成功] 菜单项 {idx+1} 打开了功能界面!")
            ss(main_win, f"vision_05_menu_{idx+1}_opened.png")
            break

        send_keys('{ESC}'); time.sleep(0.3)
        send_keys('{ESC}'); time.sleep(0.3)
        focus(main_hwnd); time.sleep(0.2)
        send_keys('%'); time.sleep(0.5)
        send_keys('{RIGHT}'); send_keys('{RIGHT}'); send_keys('{DOWN}')
        time.sleep(1.5)

# ===== 6. 检索 SB-S26070007 =====
print("\n[阶段5] 检索 SB-S26070007...")
all_items = []
def scan_all(ctl, d=0):
    if d > 5: return
    try:
        txt = (ctl.window_text() or "")[:80]
        if ctl.is_visible():
            all_items.append((txt, ctl.class_name(), ctl.rectangle(), d))
        for ch in ctl.children(): scan_all(ch, d+1)
    except: pass
scan_all(main_win)

inputs = [c for c in all_items if c[1] in ('TcxTextEdit','TEdit','Edit')]
btns = [c for c in all_items if c[1] in ('TcxButton','TBitBtn','TSpeedButton') and c[0].strip()]

print(f"  可见输入框: {len(inputs)}")
for c in inputs: print(f"    [{c[1]}] '{c[0]}' {c[2]}")
print(f"  可见按钮: {len(btns)}")
for c in btns: print(f"    [{c[1]}] '{c[0]}' {c[2]}")

# 如果找到了输入框再输入
# 否则截图让视觉分析
if not inputs:
    ss(main_win, "vision_06_no_inputs.png")
    vision_retry = ask_vision(
        SCREENSHOT_DIR / "vision_06_no_inputs.png",
        """当前是佰信系统界面截图。
请分析：
1. 当前打开的是哪个功能模块？（看标题和界面布局）
2. 检索/查询输入框在哪里？（如果有，请描述位置）
3. 有哪些按钮可用？
4. 界面上有哪些可操作的区域？

请给出详细的界面分析。"""
    )

# 最终状态
print(f"\n截图目录: {SCREENSHOT_DIR}")
print("="*60)
