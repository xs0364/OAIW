"""
佰信系统 — 海运操作 → 订舱管理 → 检索 SB-S26070007 → 打开
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

def dump_visible(ctl, depth=0, maxd=6):
    """递归获取所有可见控件的类名/文字/坐标"""
    res = []
    if depth > maxd: return res
    try:
        txt = (ctl.window_text() or "")[:100]
        cls = ctl.class_name()
        r = ctl.rectangle()
        res.append((cls, txt, r, ctl.is_visible(), ctl.is_enabled(), ctl.control_id(), depth))
        for ch in ctl.children():
            res.extend(dump_visible(ch, depth+1, maxd))
    except:
        pass
    return res

def print_ctrls(ctrls, title="控件"):
    print(f"\n  --- {title} ---")
    inputs = [c for c in ctrls if c[0] in ('TcxTextEdit','TEdit','Edit','TcxMaskEdit','TDBEdit') and c[3]]
    btns = [c for c in ctrls if c[0] in ('TcxButton','TButton','TBitBtn','TSpeedButton') and c[3] and c[1].strip()]
    labels = [c for c in ctrls if c[0] in ('TcxLabel','TLabel','TcxDBLabel') and c[3] and c[1].strip()]
    for c in inputs:
        print(f"    [输入] [{c[0]}] id={c[5]} '{c[1]}' {c[2]}")
    for c in btns:
        print(f"    [按钮] [{c[0]}] '{c[1]}' {c[2]}")
    for c in labels[:20]:
        print(f"    [标签] [{c[0]}] '{c[1]}' {c[2]}")
    print(f"    (输入:{len(inputs)} 按钮:{len(btns)} 标签:{len(labels)})")

# ===== 1. 清理 & 登录 =====
print("="*60)
print("佰信 — 海运操作 → 订舱管理 → 检索 SB-S26070007")
print("="*60)

print("\n[1/6] 清理并启动佰信...")
subprocess.run(["taskkill", "/f", "/im", "BestLOGFW.exe"], capture_output=True)
time.sleep(1.5)
subprocess.Popen([BAIXIN_PATH], cwd=BAIXIN_CWD)
time.sleep(5)

app = Application(backend="win32").connect(path=BAIXIN_PATH, timeout=30)

print("[2/6] 登录...")
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
print("  登录完成 ✓")
time.sleep(3)

# ===== 2. 找主窗口 =====
main_win = None
for w in app.windows():
    if w.is_visible() and w.class_name() == 'TfmMainD':
        main_win = w; break
if not main_win:
    for w in app.windows():
        if w.is_visible() and w.rectangle().width() > 400:
            main_win = w; break
if not main_win:
    print("[失败] 找不到主窗口"); sys.exit(1)

main_win.set_focus()
time.sleep(1)
ss(main_win, "v3_01_main.png")
print(f"  主窗口: rect={main_win.rectangle()}")

# ===== 3. 获取主窗口所有直接子控件 =====
print("\n[3/6] 探查主窗口子控件...")
children = main_win.children()
print(f"  顶级子控件: {len(children)} 个")
for i, ch in enumerate(children):
    txt = (ch.window_text() or "")[:60]
    cls = ch.class_name()
    r = ch.rectangle()
    vis = ch.is_visible()
    print(f"    [{i}] [{cls}] '{txt}' {r} vis={vis}")

# ===== 4. 点击顶部导航标签 =====
print("\n[4/6] 通过坐标点击顶部导航...")

# 从之前探查已知顶部结构：
# TcxTabControl 区域: L0, T67, R1920, B88
# TdxBarControl "Main Menu": L0, T45, R670, B67
# TdxBarControl "Tool Bar": L0, T23, R1920, B45

# 导航标签在 TcxTabControl 区域 (L0, T67, R1920, B88)
# 标签高度约 21px，第一个标签"海运操作"应该在左侧
# 遍历标签区域，逐个点击

# 先尝试点击"海运操作"标签（通常在第一个位置）
# 使用屏幕坐标点击标签区域
nav_y = 76  # TcxTabControl 的垂直中间位置

# 方法：从左到右依次点击各个位置，检测界面变化
# 先找出每个标签的边界
print("  扫描标签区域...")
# 获取 TcxTabControl 的子控件
tab_zones = []
for ch in main_win.children():
    r = ch.rectangle()
    if abs(r.top - 67) < 5 and abs(r.bottom - 88) < 5:  # 近似 TcxTabControl 高度
        txt = (ch.window_text() or "")[:40]
        tab_zones.append((txt, ch, r))

if tab_zones:
    print(f"  找到标签控件: {len(tab_zones)}")
    for t, ch, r in tab_zones:
        print(f"    '{t}' {r} class={ch.class_name()}")
        ch.click_input()
        time.sleep(2)
else:
    print("  未直接找到标签控件，按坐标探测...")

    # 在标签栏区域从左到右依次点击
    # 假设标签大致等宽分布，1920宽度 / 假设6个标签 ≈ 320px每个
    for x_pos, label_guess in [
        (80, "海运操作"),
        (250, "海运财务"),
        (450, "空运"),
        (650, "报关"),
        (900, "仓储"),
        (1200, "系统管理"),
    ]:
        print(f"  点击 '{label_guess}' x={x_pos}...")
        main_win.click_input(coords=(x_pos, nav_y))
        time.sleep(1.5)
        ss(main_win, f"v3_tab_{label_guess}.png")

        # 检查是否有新控件出现
        items = dump_visible(main_win, 0, 3)
        new_inputs = [c for c in items if c[0] in ('TcxTextEdit','TEdit','Edit') and c[3]]
        new_btns = [c for c in items if c[0] in ('TcxButton','TBitBtn') and c[3] and c[1].strip()]

        if new_inputs or new_btns:
            print(f"    [发现] '{label_guess}' 有输入框/按钮!")
            for inp in new_inputs[:5]:
                print(f"      [输入] [{inp[0]}] '{inp[1]}' {inp[2]}")
            for btn in new_btns[:10]:
                print(f"      [按钮] [{btn[0]}] '{btn[1]}' {btn[2]}")
            break

# ===== 5. 如果点击标签后出现二级菜单/模块，点击"订舱管理" =====
print("\n[5/6] 在上方次导航找'订舱管理'...")

# 重新全面扫描控件
all_items = dump_visible(main_win)
print(f"  当前总控件: {len(all_items)}")

# 找所有标签/按钮文字
print("\n  所有有文字的可见控件:")
for c in all_items:
    if c[3] and c[1].strip():
        print(f"    [{c[0]}] depth={c[6]} '{c[1]}' {c[2]}")

# 找"订舱管理"按钮
book_btns = [c for c in all_items if c[3] and '订舱' in c[1]]
if book_btns:
    print(f"\n  找到 '订舱管理':")
    for c in book_btns:
        print(f"    [{c[0]}] '{c[1]}' {c[2]}")
        # 点击
        try:
            # 根据坐标点击
            r = c[2]
            cx = (r.left + r.right) // 2
            cy = (r.top + r.bottom) // 2
            print(f"    点击 ({cx},{cy})...")
            main_win.click_input(coords=(cx, cy))
            time.sleep(2)
            ss(main_win, "v3_04_booking.png")
            print("  已点击订舱管理")
        except Exception as e:
            print(f"    点击失败: {e}")
else:
    print("\n  未找到'订舱管理'，检查是否有二级菜单弹出...")
    # 可能"海运操作"点击后展开了下拉菜单
    # 检查是否有弹出菜单
    for w in app.windows():
        if w.is_visible():
            cls = w.class_name()
            txt = w.window_text()[:60]
            r = w.rectangle()
            if cls not in ('TfmMainD','TApplication','SoPY_Status','TTrayIcon') and r.width() < 500:
                print(f"  弹窗/菜单: '{txt}' ({cls}) {r}")
                ss(w, "v3_popup_menu.png")

# ===== 6. 进入模块后找检索框 =====
print("\n[6/6] 找检索输入框 → 输入 SB-S26070007...")

# 全面扫描
final_items = dump_visible(main_win)
print_ctrls(final_items, "当前界面控件")

# 如果还没找到，等待一下再试
if not [c for c in final_items if c[0] in ('TcxTextEdit','TEdit','Edit') and c[3]]:
    print("\n  等待界面加载（5秒）...")
    time.sleep(5)
    final_items = dump_visible(main_win)
    print_ctrls(final_items, "等待后控件")

# 在所有控件中找检索框 + 检索按钮
search_btn = [c for c in final_items if c[3] and any(kw in c[1] for kw in ['检索','查询','搜索','查找','过滤','Filter','Search'])]
print(f"\n  检索按钮: {len(search_btn)}")
for c in search_btn:
    print(f"    [{c[0]}] '{c[1]}' {c[2]}")

# 取第一个输入框输入
all_inputs = [c for c in final_items if c[0] in ('TcxTextEdit','TEdit','Edit') and c[3]]
if all_inputs:
    inp = all_inputs[0]
    r = inp[2]
    cx = (r.left + r.right) // 2
    cy = (r.top + r.bottom) // 2
    print(f"\n  在输入框 ({cx},{cy}) 输入 SB-S26070007...")
    main_win.click_input(coords=(cx, cy))
    time.sleep(0.5)
    send_keys("^a{BACKSPACE}")
    time.sleep(0.2)
    send_keys("SB-S26070007")
    time.sleep(0.5)
    ss(main_win, "v3_05_input_done.png")
    print("  已输入 SB-S26070007")

    # 按回车
    print("  按 Enter 检索...")
    send_keys('{ENTER}')
    time.sleep(3)
    ss(main_win, "v3_06_results.png")
    print("  检索完成")

    # 检查结果
    result_items = dump_visible(main_win)
    found = [c for c in result_items if 'SB-S26070007' in c[1]]
    print(f"  结果中含 'SB-S26070007' 的控件: {len(found)}")
    for c in found:
        print(f"    [{c[0]}] '{c[1]}' {c[2]}")
        # 双击
        r = c[2]
        cx = (r.left + r.right) // 2
        cy = (r.top + r.bottom) // 2
        print(f"  双击 ({cx},{cy})...")
        main_win.click_input(coords=(cx, cy), double=True)
        time.sleep(3)
        ss(main_win, "v3_07_after_doubleclick.png")
        break
else:
    print("\n  未找到任何输入框！！！")

# ===== 最终报告 =====
print("\n" + "="*60)
print("最终状态:")
for w in app.windows():
    if w.is_visible():
        print(f"  '{w.window_text()[:80]}' ({w.class_name()})")
print(f"截图: {SCREENSHOT_DIR}")
print("="*60)
