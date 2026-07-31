"""
UIA backend 探针 v2 — 启动佰信 → 登录 → 探 UIA 控件支持情况
"""
import sys, time, subprocess, json, pathlib
sys.stdout.reconfigure(encoding='utf-8')

BAIXIN_PATH = r"D:\Best-Hint\BestLOG\BestLOGFW.exe"
BAIXIN_CWD = r"D:\Best-Hint\BestLOG"
USERNAME = "AI海运操作"
PASSWORD = "xu1264"
OUT_DIR = pathlib.Path(r"D:\OAIW\_baixin_screenshots")
OUT_DIR.mkdir(exist_ok=True)

import pyautogui
pyautogui.FAILSAFE = False

print("=" * 60)
print("佰信 UIA 探针 v2 — 启动 → 登录 → UIA 探测")
print("=" * 60)

# ===== 1. 启动佰信 =====
print("\n[1/5] 清理旧进程并启动佰信...")
subprocess.run(["taskkill", "/f", "/im", "BestLOGFW.exe"], capture_output=True)
time.sleep(1.5)
proc = subprocess.Popen([BAIXIN_PATH], cwd=BAIXIN_CWD)
print(f"  启动 PID={proc.pid}")
time.sleep(6)

from pywinauto import Application
from pywinauto.keyboard import send_keys

app = Application(backend="win32").connect(path=BAIXIN_PATH, timeout=30)

# ===== 2. 登录 =====
print("\n[2/5] 登录佰信...")
lw = app.window(class_name="TfmLogin")
lw.wait("visible", timeout=15)

lx = lw.child_window(class_name="TcxTextEdit", found_index=0)
lx.click_input()
lx.type_keys("^a{BACKSPACE}")
lx.type_keys(USERNAME)

lp = lw.child_window(class_name="TcxTextEdit", found_index=1)
lp.click_input()
lp.type_keys(PASSWORD)

ok = next((c for c in lw.descendants(class_name="TcxButton") if "确定" in (c.window_text() or "")), None)
if ok:
    ok.click_input()
else:
    lw.click_input(coords=(1020, 645))

# 等登录完成
print("  等待登录...")
for i in range(40):
    time.sleep(1)
    try:
        if not lw.is_visible():
            print(f"  登录完成 ({i+1}s)")
            break
    except:
        break
time.sleep(3)

# 找主窗口
mw = None
for w in app.windows():
    try:
        if w.is_visible() and w.class_name() == "TfmMainD":
            mw = w
            break
    except:
        pass
if not mw:
    print("  主窗口未找到!")
    sys.exit(1)
print(f"  主窗口: 0x{mw.handle:08x} {mw.rectangle()}")

# ===== 3. 用 UIA backend 连接 =====
print("\n[3/5] 用 UIA backend 连接...")

try:
    app_uia = Application(backend="uia").connect(process=proc.pid)
    mw_uia = None
    for w in app_uia.windows():
        try:
            if w.is_visible() and w.class_name() == "TfmMainD":
                mw_uia = w
                break
        except:
            pass

    if mw_uia:
        print(f"  ✅ UIA 连接成功! 主窗口 class={mw_uia.class_name()}")
    else:
        print("  ❌ UIA 能连进程但找不到主窗口 (class_name=TfmMainD)")
        mw_uia = None
except Exception as e:
    print(f"  ❌ UIA 连接失败: {e}")
    mw_uia = None

# ===== 4. 如果是 UIA 可用，遍历控件树 =====
if mw_uia:
    print("\n[4/5] UIA 控件树探测...")

    all_nodes = []
    def walk_tree(ctl, depth=0, max_depth=8):
        if depth > max_depth:
            return
        try:
            if not ctl.is_visible():
                return
            node = {
                "class": ctl.class_name(),
                "text": ctl.window_text()[:100] if ctl.window_text() else "",
                "ctrl_id": ctl.control_id(),
                "auto_id": ctl.automation_id(),
                "rect": str(ctl.rectangle()),
                "depth": depth,
            }
            all_nodes.append(node)
            for k in ctl.children():
                walk_tree(k, depth + 1, max_depth)
        except:
            pass

    walk_tree(mw_uia)
    print(f"  共找到 {len(all_nodes)} 个可见控件")

    # 搜索菜单/工具栏相关
    print("\n  --- 菜单/工具栏相关控件 ---")
    menu_keywords = ['bar', 'menu', 'tool', 'ribbon', 'tab']
    menu_nodes = [n for n in all_nodes if any(k in n['class'].lower() for k in menu_keywords)]
    for n in menu_nodes:
        print(f"    [{n['class']}] '{n['text']}' auto_id='{n['auto_id']}' rect={n['rect']}")

    print(f"\n  --- 所有控件文本（非空）---")
    for n in all_nodes:
        if n['text'].strip():
            print(f"    [{n['class']}] '{n['text'][:60]}' rect={n['rect']}")

    # 搜索 AutomationId（可能包含有意义的名称）
    print(f"\n  --- 有 AutomationId 的控件 ---")
    for n in all_nodes:
        if n['auto_id'] and n['auto_id'].strip():
            print(f"    [{n['class']}] auto_id='{n['auto_id']}'")

else:
    # ===== 4b. UIA 不可用，改用 win32 提代方案 =====
    print("\n[4/5] UIA 不可用，改用 win32 + OCR 方案...")
    print("  方案不变：pyautogui 截图 + EasyOCR 识别 + SendInput 点击")
    print("  不能依赖 UIA 获取菜单项文字")

# ===== 5. 总结 =====
print("\n" + "=" * 60)
print("结论:")
if mw_uia:
    # 检查有没有找到带文字的菜单项
    text_nodes = [n for n in all_nodes if n['text'].strip()] if mw_uia else []
    bar_nodes = [n for n in all_nodes if any(k in n['class'].lower() for k in ['bar','menu'])] if mw_uia else []
    if text_nodes:
        print("✅ UIA backend 可用，能找到控件")
        print(f"   文本控件: {len(text_nodes)} 个")
        print(f"   菜单栏控件: {len(bar_nodes)} 个")
        print("   → 可以用 UIA 替代部分 OCR 方案")
    else:
        print("⚠️ UIA 能用但找不到有效文本，效果有限")
else:
    print("❌ UIA backend 不可用（连接失败或找不到主窗口）")
    print("   → 坚持 OCR + SendInput 方案")

print("=" * 60)
