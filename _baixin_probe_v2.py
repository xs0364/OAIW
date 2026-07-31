"""
佰信系统探查 v2 — 登录 → 加载模块 → 找检索框 → 打开记录
"""
import sys, time, subprocess, json, re
from pathlib import Path
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BAIXIN_PATH = r"D:\Best-Hint\BestLOG\BestLOGFW.exe"
BAIXIN_CWD  = r"D:\Best-Hint\BestLOG"
USERNAME = "AI海运操作"
PASSWORD = "xu1264"
SCREENSHOT_DIR = Path(r"D:\OAIW\_baixin_screenshots")
SCREENSHOT_DIR.mkdir(exist_ok=True)

from pywinauto import Application
from pywinauto.keyboard import send_keys

def save_screenshot(win, name):
    try:
        img = win.capture_as_image()
        path = SCREENSHOT_DIR / name
        img.save(str(path))
        print(f"  [截图] {name}")
        return path
    except Exception as e:
        print(f"  [截图失败] {name}: {e}")
        return None

def dump_all(ctl, depth=0, maxd=8):
    results = []
    if depth > maxd: return results
    try:
        txt = (ctl.window_text() or "")[:120]
        cls = ctl.class_name()
        r = ctl.rectangle()
        results.append({
            'class': cls, 'text': txt, 'rect': str(r),
            'vis': ctl.is_visible(), 'en': ctl.is_enabled(),
            'id': ctl.control_id(), 'depth': depth
        })
        for ch in ctl.children():
            results.extend(dump_all(ch, depth+1, maxd))
    except:
        pass
    return results

# ===== 1. 清理 & 登录 =====
print("="*60)
print("佰信探查 v2 — 加载模块 → 检索 → 打开界面")
print("="*60)

print("\n[1] 清理并启动...")
subprocess.run(["taskkill", "/f", "/im", "BestLOGFW.exe"], capture_output=True)
time.sleep(1.5)
subprocess.Popen([BAIXIN_PATH], cwd=BAIXIN_CWD)
time.sleep(5)

app = Application(backend="win32").connect(path=BAIXIN_PATH, timeout=30)

print("[2] 登录...")
login_win = app.window(class_name="TfmLogin")
login_win.wait("visible", timeout=10)
uname = login_win.child_window(class_name="TcxTextEdit", found_index=0)
uname.click_input(); time.sleep(0.3)
uname.type_keys("^a{BACKSPACE}", with_spaces=True); time.sleep(0.2)
uname.type_keys(USERNAME, with_spaces=True)
pwd = login_win.child_window(class_name="TcxTextEdit", found_index=1)
pwd.click_input(); time.sleep(0.2)
pwd.type_keys(PASSWORD, with_spaces=True)
ok_btn = next((c for c in login_win.descendants(class_name="TcxButton")
               if "确定" in (c.window_text() or "")), None)
if ok_btn: ok_btn.click_input()
else: login_win.click_input(coords=(1020, 645))

for i in range(25):
    time.sleep(1)
    try:
        if not login_win.is_visible(): break
    except: break
print("  登录完成")
time.sleep(3)

# ===== 2. 找主窗口 =====
main_win = None
for w in app.windows():
    if w.is_visible() and w.class_name() == 'TfmMainD':
        main_win = w; break
if not main_win:
    print("[失败] 找不到主窗口"); sys.exit(1)

main_win.set_focus()
time.sleep(1)
save_screenshot(main_win, "v2_01_main.png")

# ===== 3. 探查顶部页签 =====
print("\n[3] 探查顶部 TcxTabControl 和标签页...")
all_c = dump_all(main_win)

# 找 TabControl 和里面的 TabSheet
tab_ctrl_info = [c for c in all_c if c['class'] in ('TcxTabControl', 'TcxTabSheet') and c['vis']]
print(f"  页签控件: {len(tab_ctrl_info)} 个")
for tc in tab_ctrl_info:
    print(f"    [{tc['class']}] id={tc['id']} text='{tc['text']}' {tc['rect']} depth={tc['depth']}")

# 直接从 TcxTabControl 找子控件
try:
    tab_ctrl = main_win.child_window(class_name="TcxTabControl")
    print(f"\n  TcxTabControl children:")
    for ch in tab_ctrl.children():
        txt = ch.window_text()[:40]
        cls = ch.class_name()
        r = ch.rectangle()
        vis = ch.is_visible()
        print(f"    [{cls}] '{txt}' {r} vis={vis}")
except Exception as e:
    print(f"  TcxTabControl 遍历失败: {e}")

# 遍历工具栏按钮
print("\n  --- 工具栏按钮 ---")
try:
    tool_bar = main_win.child_window(class_name="TdxBarControl", found_index=0)
    print(f"  工具栏: rect={tool_bar.rectangle()}")
    for ch in tool_bar.children():
        txt = ch.window_text()[:40]
        cls = ch.class_name()
        r = ch.rectangle()
        vis = ch.is_visible()
        if vis:
            print(f"    [{cls}] '{txt}' {r}")
except Exception as e:
    print(f"  工具栏遍历失败: {e}")

# 找第二行工具栏（Tool Bar）
print("\n  --- 第二行工具栏 ---")
try:
    tool_bar2 = main_win.child_window(class_name="TdxBarControl", found_index=1)
    print(f"  工具栏2: rect={tool_bar2.rectangle()}")
    for ch in tool_bar2.children():
        txt = ch.window_text()[:40]
        cls = ch.class_name()
        r = ch.rectangle()
        vis = ch.is_visible()
        if vis:
            print(f"    [{cls}] '{txt}' {r}")
except Exception as e:
    print(f"  工具栏2遍历失败: {e}")

# ===== 4. 点击顶部页签进入功能模块 =====
print("\n[4] 尝试点击各个页签...")

# 获取所有可见的 TcxTabSheet
try:
    tab_sheets = tab_ctrl.children()
    for i, sheet in enumerate(tab_sheets):
        txt = sheet.window_text()[:40]
        cls = sheet.class_name()
        r = sheet.rectangle()
        if sheet.is_visible() and txt.strip():
            print(f"  [{i}] 页签: '{txt}' {r}")
except:
    pass

# 尝试点击"费用"相关模块
# 先截图顶部工具栏全貌
save_screenshot(main_win, "v2_02_top_bar.png")

# 如果找不到页签文字，就按坐标点击顶部标签中间区域
# TcxTabControl 矩形: L0, T67, R1920, B88 — 高度21像素
# 通常第一个标签在左边
tab_rect = tab_ctrl.rectangle()
print(f"\n  TabControl 区域: {tab_rect}")

# 点击顶部标签区域的几个关键位置
click_positions = [
    (100, 78, "标签1(左侧)"),
    (300, 78, "标签2"),
    (500, 78, "标签3(中间)"),
    (1000, 78, "标签4"),
    (1500, 78, "标签5(右侧)"),
]

for cx, cy, desc in click_positions:
    print(f"\n  点击 {desc} ({cx},{cy})...")
    main_win.click_input(coords=(cx, cy))
    time.sleep(2)

    # 检查界面是否变化 - 是否有新控件出现
    new_c = dump_all(main_win, maxd=3)
    new_inputs = [c for c in new_c if c['class'] in ('TcxTextEdit', 'TEdit', 'Edit') and c['vis']]
    new_btns = [c for c in new_c if c['class'] in ('TcxButton', 'TBitBtn') and c['vis'] and c['text'].strip()]

    if new_inputs or new_btns:
        print(f"  [发现] 点击 {desc} 后有新控件!")
        save_screenshot(main_win, f"v2_03_after_click_{desc.replace('(','').replace(')','')}.png")
        for inp in new_inputs[:5]:
            print(f"    输入框: [{inp['class']}] id={inp['id']} text='{inp['text']}' {inp['rect']}")
        for btn in new_btns[:10]:
            print(f"    按钮: [{btn['class']}] '{btn['text']}' {btn['rect']}")
        break

# ===== 5. 如果页签点击无效，尝试双击工具栏加载模块 =====
print("\n[5] 尝试双击底部提示面板（加载模块）...")
# 之前发现的提示面板: TPanel at (L0, T988, R1920, B1012)
panel = main_win.child_window(class_name="TPanel")
if panel and panel.is_visible():
    print(f"  底部面板: rect={panel.rectangle()}")
    panel.click_input(double=True)
    time.sleep(3)
    save_screenshot(main_win, "v2_04_after_doubleclick_panel.png")

    # 重新扫描
    after_panel = dump_all(main_win, maxd=3)
    new_inputs = [c for c in after_panel if c['class'] in ('TcxTextEdit', 'TEdit', 'Edit') and c['vis']]
    print(f"  新输入框: {len(new_inputs)}")
    for inp in new_inputs[:5]:
        print(f"    [{inp['class']}] '{inp['text']}' {inp['rect']}")

    # 再次探查全部
    if not new_inputs:
        # 尝试双击工具栏（第二行）
        print("  双击第二行工具栏...")
        tool_bar2 = main_win.child_window(class_name="TdxBarControl", found_index=1)
        tool_bar2.click_input(double=True)
        time.sleep(3)
        save_screenshot(main_win, "v2_05_after_doubleclick_toolbar.png")
        after_tb = dump_all(main_win, maxd=3)
        new_inputs2 = [c for c in after_tb if c['class'] in ('TcxTextEdit', 'TEdit', 'Edit') and c['vis']]
        print(f"  新输入框: {len(new_inputs2)}")
        for inp in new_inputs2[:5]:
            print(f"    [{inp['class']}] '{inp['text']}' {inp['rect']}")

# ===== 6. 如果已有控件或找到新控件，尝试检索 =====
print("\n[6] 扫描全局所有控件...")
all_visible = dump_all(main_win)
print(f"  总共 {len(all_visible)} 控件")

# 全面输出所有可见输入字段和按钮
print("\n  --- 全部可见输入框 ---")
inputs_found = [c for c in all_visible if c['class'] in ('TcxTextEdit', 'TEdit', 'Edit', 'TcxMaskEdit', 'TDBEdit') and c['vis']]
for c in inputs_found:
    print(f"    [{c['class']}] id={c['id']} text='{c['text']}' {c['rect']} depth={c['depth']}")

print(f"\n  --- 全部可见按钮(有文字) ---")
btns_found = [c for c in all_visible if c['class'] in ('TcxButton', 'TButton', 'TBitBtn', 'TSpeedButton') and c['vis'] and c['text'].strip()]
for c in btns_found:
    print(f"    [{c['class']}] '{c['text']}' {c['rect']} depth={c['depth']}")

# 标签（了解界面布局）
print(f"\n  --- 标签(有文字) ---")
labels_found = [c for c in all_visible if c['class'] in ('TcxLabel', 'TLabel', 'TcxDBLabel') and c['vis'] and c['text'].strip()]
for c in labels_found[:30]:
    print(f"    [{c['class']}] '{c['text']}' {c['rect']}")

# ===== 7. 尝试在 MDIClient 中加载子窗口 =====
print("\n[7] 检查 MDIClient 子窗口...")
try:
    mdi = main_win.child_window(class_name="MDIClient")
    print(f"  MDIClient: rect={mdi.rectangle()}")
    mdi_children = mdi.children()
    print(f"  MDI 子窗口数: {len(mdi_children)}")
    for i, ch in enumerate(mdi_children):
        txt = ch.window_text()[:60]
        cls = ch.class_name()
        r = ch.rectangle()
        if ch.is_visible():
            print(f"    [{i}] [{cls}] '{txt}' {r}")
except Exception as e:
    print(f"  MDI 遍历失败: {e}")

# ===== 8. 最终状态 =====
print("\n" + "="*60)
print("最终所有窗口:")
for w in app.windows():
    if w.is_visible():
        print(f"  '{w.window_text()[:80]}' ({w.class_name()})")
print(f"截图目录: {SCREENSHOT_DIR}")
print("="*60)
