"""
佰信系统 v4 — 双击加载模块 → TdxBar菜单导航 → 订舱管理 → 检索
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

def ss(win, name):
    try:
        win.capture_as_image().save(str(SCREENSHOT_DIR / name))
        print(f"  [截图] {name}")
    except Exception as e:
        print(f"  [截图失败] {name}: {e}")

def dump_visible(ctl, maxd=5):
    """递归获取所有可见控件"""
    res = []
    def _rec(c, d=0):
        if d > maxd: return
        try:
            txt = (c.window_text() or "")[:120]
            cls = c.class_name()
            r = c.rectangle()
            res.append((cls, txt, r, c.is_visible(), c.is_enabled(), c.control_id(), d))
            for ch in c.children():
                _rec(ch, d+1)
        except:
            pass
    _rec(ctl)
    return res

def print_summary(items, title):
    print(f"\n  --- {title} ---")
    inputs = [c for c in items if c[3] and c[0] in ('TcxTextEdit','TEdit','Edit','TcxMaskEdit','TDBEdit')]
    btns = [c for c in items if c[3] and c[0] in ('TcxButton','TButton','TBitBtn','TSpeedButton') and c[1].strip()]
    labels = [c for c in items if c[3] and c[0] in ('TcxLabel','TLabel','TcxDBLabel') and c[1].strip()]
    for c in inputs: print(f"    [输入] [{c[0]}] '{c[1]}' {c[2]}")
    for c in btns: print(f"    [按钮] [{c[0]}] '{c[1]}' {c[2]}")
    for c in labels[:15]: print(f"    [标签] [{c[0]}] '{c[1]}' {c[2]}")
    print(f"    (输入:{len(inputs)} 按钮:{len(btns)} 标签:{len(labels)})")

# ===== 1. 启动 & 登录 =====
print("="*60)
print("佰信 v4 — 双击加载 → 菜单导航 → 检索 SB-S26070007")
print("="*60)

print("\n[1] 清理并启动...")
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
print("  登录完成")
time.sleep(3)

main_win = None
for w in app.windows():
    if w.is_visible() and w.class_name() == 'TfmMainD':
        main_win = w; break
if not main_win:
    print("[失败] 找不到主窗口"); sys.exit(1)
main_win.set_focus()
time.sleep(1)
ss(main_win, "v4_01_main.png")
print(f"  主窗口: rect={main_win.rectangle()}")

# ===== 2. 双击底部面板加载模块 =====
print("\n[2] 双击底部提示面板加载模块...")
panel = None
for ch in main_win.children():
    if ch.class_name() == 'TPanel' and ch.is_visible():
        panel = ch
        r = panel.rectangle()
        print(f"  底部面板: {r}")
        # 双击面板中央
        cx, cy = (r.left + r.right)//2, (r.top + r.bottom)//2
        print(f"  双击坐标 ({cx},{cy})...")
        panel.click_input(double=True)
        time.sleep(3)
        ss(main_win, "v4_02_after_doubleclick.png")
        break

# ===== 3. 探查界面变化 =====
print("\n[3] 双击后探查界面变化...")
items = dump_visible(main_win, 4)
print_summary(items, "双击后控件")

# 检查新出现的 MDI 窗口
mdi_children = []
for ch in main_win.children():
    if ch.class_name() not in ('TPanel','TdxDockControl','TcxSplitter','TdxStatusBar','TcxTabControl','TdxBarControl','TdxBarDockControl','TdxDockSite') and ch.is_visible():
        mdi_children.append(ch)
print(f"\n  MDI区可见子窗口: {len(mdi_children)}")
for ch in mdi_children:
    print(f"    [{ch.class_name()}] '{ch.window_text()[:60]}' {ch.rectangle()}")

# ===== 4. 尝试点击顶部标签 =====
print("\n[4] 点击顶部标签...")

# 方法1: 依次点击 Main Menu 区域 (TdxBarControl "Main Menu" L0,T45,R670,B67)
menu_y = 55  # Main Menu 垂直中间
print(f"  尝试点击 Main Menu 各位置 (y={menu_y})...")

for x_pos, guess in [
    (30, "系统菜单"),
    (100, "海运操作"),
    (200, "空运操作"),
    (300, "报关"),
    (400, "仓储"),
    (500, "财务"),
    (600, "管理"),
]:
    print(f"    -> 点击 x={x_pos} ({guess})...")
    main_win.click_input(coords=(x_pos, menu_y))
    time.sleep(1.5)

    # 检查是否有弹出菜单
    menu_found = False
    for w in app.windows():
        if w.is_visible() and w.class_name() in ('TPopupMenu','TdxBarPopupMenu','#32768','TMenu') and w.rectangle().width() < 500:
            txt = w.window_text()[:40]
            print(f"      [弹出菜单] '{txt}' ({w.class_name()}) {w.rectangle()}")
            menu_found = True
            ss(w, f"v4_popup_{guess}.png")

    # 用 ESC 关闭可能弹出的菜单
    send_keys('{ESC}')
    time.sleep(0.5)

# 方法2: 点击 TcxTabControl 区域 (L0,T67,R1920,B88)
tab_y = 76
print(f"\n  尝试点击 TabControl 各位置 (y={tab_y})...")

for x_pos, guess in [
    (80, "海运操作"),
    (220, "海运财务"),
    (360, "空运"),
    (500, "报关"),
    (640, "仓储管理"),
    (780, "车队管理"),
    (920, "费用结算"),
    (1060, "系统设置"),
]:
    print(f"    -> 点击 x={x_pos} ({guess})...")
    main_win.click_input(coords=(x_pos, tab_y))
    time.sleep(1.5)

    # 检查界面变化
    after = dump_visible(main_win, 3)
    new_inputs = [c for c in after if c[3] and c[0] in ('TcxTextEdit','TEdit','Edit')]
    if new_inputs:
        print(f"      [发现输入框!] 标签 '{guess}' 有输入控件!")
        for inp in new_inputs[:3]:
            print(f"        [{inp[0]}] '{inp[1]}' {inp[2]}")
        ss(main_win, f"v4_tab_{guess}_has_inputs.png")
        break

    # 检查 MDI 子窗口变化
    for ch in main_win.children():
        if ch.is_visible() and ch.class_name() not in ('TPanel','TdxDockControl','TcxSplitter','TdxStatusBar','TcxTabControl','TdxBarControl','TdxBarDockControl','TdxDockSite','TfmFW_WallPaper'):
            txt = ch.window_text()[:60]
            if txt.strip():
                print(f"      [MDI子窗口] '{txt}' ({ch.class_name()})")
                ss(ch, f"v4_mdi_{guess}.png")

# ===== 5. 尝试通过 TdxBar 工具栏按钮 =====
print("\n[5] 尝试点击工具栏 (Tool Bar) 按钮...")
# Tool Bar: L0, T23, R1920, B45
tool_y = 34
toolbar_positions = [
    (30, "系统"),
    (60, "首页"),
    (100, "海运操作"),
    (140, "海运操作2"),
    (180, "操作"),
    (220, "订舱"),
    (260, "单证"),
    (300, "费用"),
]
for x_pos, guess in toolbar_positions:
    print(f"    -> 点击 x={x_pos} ({guess})...")
    main_win.click_input(coords=(x_pos, tool_y))
    time.sleep(1.5)

    # 看是否有弹出菜单
    for w in app.windows():
        if w.is_visible() and w.class_name() in ('TPopupMenu','TdxBarPopupMenu','#32768','TMenu') and w.rectangle().width() < 500:
            txt = w.window_text()[:40]
            print(f"      [弹出菜单] '{txt}' ({w.class_name()}) {w.rectangle()}")
            ss(w, f"v4_toolbar_popup_{guess}.png")
            break

    # ESC 关闭
    send_keys('{ESC}'); time.sleep(0.3)

# ===== 6. 截图最终状态 + 保存全部控件 =====
print("\n[6] 最终汇总...")
final = dump_visible(main_win, 5)
with open(SCREENSHOT_DIR / "v4_final_controls.json", "w", encoding="utf-8") as f:
    json.dump([{
        'class': c[0], 'text': c[1], 'rect': str(c[2]),
        'visible': c[3], 'depth': c[6]
    } for c in final], f, ensure_ascii=False, indent=2)

print(f"  控件总数: {len(final)}")
print(f"  截图目录: {SCREENSHOT_DIR}")

# 列出所有含"订舱"文字的控件（区分大小写）
print("\n  含 '订舱' 文字的控件:")
for c in final:
    if '订舱' in c[1]:
        print(f"    [{c[0]}] depth={c[6]} '{c[1]}' {c[2]}")

# 列出所有当前可见的 MDI 子窗口
print("\n  当前所有可见窗口:")
for w in app.windows():
    if w.is_visible():
        print(f"    '{w.window_text()[:80]}' ({w.class_name()}) {w.rectangle()}")

print("="*60)
