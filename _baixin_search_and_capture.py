"""
佰信系统(BestLOG) — 登录 → 检索 → 打开记录 → 截图分析
全自动化版本（无 input() 暂停）
"""
import sys, time, subprocess, json, re
from pathlib import Path

# 解决 GBK 编码问题
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BAIXIN_PATH = r"D:\Best-Hint\BestLOG\BestLOGFW.exe"
BAIXIN_CWD  = r"D:\Best-Hint\BestLOG"
USERNAME = "AI海运操作"
PASSWORD = "xu1264"
SCREENSHOT_DIR = Path(r"D:\OAIW\_baixin_screenshots")
SCREENSHOT_DIR.mkdir(exist_ok=True)

from pywinauto import Application, Desktop
from pywinauto.keyboard import send_keys

def dump_controls_to_list(ctl, max_depth=10, depth=0):
    """递归采集控件信息"""
    results = []
    if depth > max_depth:
        return results
    try:
        txt = (ctl.window_text() or "")[:100]
        cls = ctl.class_name()
        rect = ctl.rectangle()
        vis = ctl.is_visible()
        en = ctl.is_enabled()
        cid = ctl.control_id()
        results.append({
            'class': cls, 'text': txt, 'rect': str(rect),
            'visible': vis, 'enabled': en, 'id': cid, 'depth': depth
        })
        for child in ctl.children():
            results.extend(dump_controls_to_list(child, max_depth, depth + 1))
    except:
        pass
    return results

def save_screenshot(win, name):
    """安全截图"""
    try:
        img = win.capture_as_image()
        path = SCREENSHOT_DIR / name
        img.save(str(path))
        print(f"  [截图] {name}")
        return path
    except Exception as e:
        print(f"  [截图失败] {name}: {e}")
        return None

def print_controls_summary(controls, title="控件"):
    """打印可见输入框、按钮、标签"""
    print(f"\n  --- {title} ---")

    # 输入框
    inputs = [c for c in controls if c['class'] in ('TcxTextEdit', 'TEdit', 'TMaskEdit', 'Edit', 'TcxMaskEdit', 'TDBEdit') and c['visible']]
    for c in inputs:
        print(f"    [输入] [{c['class']}] id={c['id']} text='{c['text']}' {c['rect']}")

    # 按钮（有文字的）
    btns = [c for c in controls if c['class'] in ('TcxButton', 'TButton', 'TBitBtn', 'TSpeedButton', 'Button') and c['visible'] and c['text'].strip()]
    for c in btns:
        print(f"    [按钮] [{c['class']}] '{c['text']}' {c['rect']}")

    # 下拉框
    combos = [c for c in controls if c['class'] in ('TcxComboBox', 'TComboBox', 'TcxLookupComboBox') and c['visible']]
    for c in combos:
        print(f"    [下拉] [{c['class']}] text='{c['text']}' {c['rect']}")

    # 复选框
    checks = [c for c in controls if c['class'] in ('TCheckBox', 'TcxCheckBox', 'TRadioButton', 'TcxRadioButton') and c['visible'] and c['text'].strip()]
    for c in checks:
        print(f"    [选择] [{c['class']}] '{c['text']}' {c['rect']}")

    # 标签
    labels = [c for c in controls if c['class'] in ('TcxLabel', 'TLabel', 'TcxDBLabel', 'TStaticText') and c['visible'] and c['text'].strip()]
    for c in labels[:30]:
        print(f"    [标签] [{c['class']}] '{c['text']}' {c['rect']}")

    print(f"    (输入:{len(inputs)} 按钮:{len(btns)} 下拉:{len(combos)} 选择:{len(checks)} 标签:{len(labels)})")

def try_find_edit_window(app):
    """尝试找编辑/录入弹窗"""
    for w in app.windows():
        if not w.is_visible():
            continue
        cls = w.class_name()
        txt = w.window_text() or ""
        rect = w.rectangle()
        # 排除主窗口和已知系统窗口
        if cls in ('TfmMainD', 'TfmLogin', '#32770', 'TTrayIcon', 'TApplication', 'SoPY_Status'):
            continue
        if cls.startswith(('Tfm', 'Tfrm')) and rect.width() > 100:
            return w
        # 也找非 Tfm 但中等大小的弹出窗口
        if 200 < rect.width() < 1800 and 200 < rect.height() < 1000:
            if txt and txt not in ('', '首页'):
                return w
    return None

# =====================================================================
print("=" * 60)
print("佰信系统 — 自动登录 → 检索 → 打开界面 → 分析")
print("=" * 60)

# 1. 清理 & 启动
print("\n[1/5] 清理旧进程并启动佰信...")
subprocess.run(["taskkill", "/f", "/im", "BestLOGFW.exe"], capture_output=True)
time.sleep(1.5)
proc = subprocess.Popen([BAIXIN_PATH], cwd=BAIXIN_CWD)
time.sleep(5)

# 2. 登录
print("\n[2/5] 登录佰信系统...")
app = Application(backend="win32").connect(path=BAIXIN_PATH, timeout=30)
login_win = app.window(class_name="TfmLogin")
login_win.wait("visible", timeout=10)
print(f"  登录窗口: rect={login_win.rectangle()}")

# 用户名
uname = login_win.child_window(class_name="TcxTextEdit", found_index=0)
uname.click_input(); time.sleep(0.3)
uname.type_keys("^a{BACKSPACE}", with_spaces=True); time.sleep(0.2)
uname.type_keys(USERNAME, with_spaces=True)
print(f"  用户名: {USERNAME}")

# 密码
pwd = login_win.child_window(class_name="TcxTextEdit", found_index=1)
pwd.click_input(); time.sleep(0.2)
pwd.type_keys(PASSWORD, with_spaces=True)
print(f"  密码: [已填]")

# 确定
ok_btn = next((c for c in login_win.descendants(class_name="TcxButton")
               if "确定" in (c.window_text() or "")), None)
if ok_btn:
    print(f"  确定按钮: {ok_btn.rectangle()}")
    ok_btn.click_input()
else:
    login_win.click_input(coords=(1020, 645))

# 等待登录
print("  等待登录...")
logged_in = False
for i in range(25):
    time.sleep(1)
    try:
        if not login_win.is_visible():
            print(f"  登录成功（{i+1}秒）")
            logged_in = True; break
    except:
        print(f"  登录成功"); logged_in = True; break

time.sleep(3)

# 3. 探查主窗口
print("\n[3/5] 探查主窗口结构...")
main_win = None
for w in app.windows():
    if w.is_visible() and w.class_name() == 'TfmMainD':
        main_win = w; break

if not main_win:
    for w in app.windows():
        if w.is_visible() and w.class_name() not in ('TfmLogin', '#32770', 'TTrayIcon', 'TApplication', 'SoPY_Status'):
            rect = w.rectangle()
            if rect.width() > 400 and rect.height() > 300:
                main_win = w; break

if not main_win:
    print("[失败] 找不到主窗口"); sys.exit(1)

print(f"  主窗口: class={main_win.class_name()} rect={main_win.rectangle()}")
main_win.set_focus()
time.sleep(1)
save_screenshot(main_win, "01_main_window.png")

# 采集主窗口控件
controls = dump_controls_to_list(main_win)
with open(SCREENSHOT_DIR / "control_tree.json", "w", encoding="utf-8") as f:
    json.dump(controls, f, ensure_ascii=False, indent=2)
print(f"  控件树: {len(controls)} 控件")
print_controls_summary(controls, "主窗口控件")

# 检查主窗口的直接子窗口（MDI 子窗口、面板等）
print("\n  --- 直接子窗口/面板 ---")
for c in controls:
    if c['depth'] <= 1 and c['visible']:
        print(f"    [{c['class']}] text='{c['text']}' {c['rect']}  id={c['id']}")

# 特别查找 TcxPageControl / TcxTabControl 等页签控件
print("\n  --- 页签/面板容器 ---")
for c in controls:
    if c['class'] in ('TcxPageControl', 'TcxTabControl', 'TPageControl', 'TPanel', 'TcxTabSheet') and c['visible']:
        print(f"    [{c['class']}] text='{c['text']}' {c['rect']}")

# 如果有首页页签，点击它（主窗口已显示首页）
# 在首页上找检索输入框 - 首页可能包含多个面板
# 查看所有含"检索""查询""搜索"的标签
print("\n  --- 含检索/查询/搜索/VLOOKUP 的标签或按钮 ---")
for c in controls:
    for kw in ['检索', '查询', '搜索', '查找', '过滤', 'Filter', 'Search', 'Find', 'VLOOK', '查看', '定位']:
        if kw in c['text'] and c['visible']:
            print(f"    [{c['class']}] '{c['text']}' {c['rect']}")
            break

# 尝试找到首页上的检索输入框 - 扫描所有无文字的小输入框
print("\n  --- 所有 TcxTextEdit（包括空文字）---")
edits = [c for c in controls if c['class'] in ('TcxTextEdit', 'TEdit') and c['visible']]
for c in edits:
    print(f"    [{c['class']}] id={c['id']} text='{c['text']}' {c['rect']}")

# 尝试用坐标方式定位：首页的检索框通常在左上区域
# 找到首页面板区域
print("\n  [尝试] 模拟键盘操作定位检索...")
# 按 F3 或 Ctrl+F 或 Alt+F 尝试打开检索
# 佰信系统常用 F3 或 Ctrl+F 进行全局检索
main_win.set_focus()
time.sleep(0.5)

# 尝试 F3（佰信常用检索快捷键）
print("  尝试 F3 打开检索...")
send_keys('{F3}')
time.sleep(2)

# 截图
save_screenshot(main_win, "02_after_f3.png")

# 检查是否有新窗口弹出
new_controls = dump_controls_to_list(main_win)
print_controls_summary(new_controls, "按F3后控件")

# 检查所有顶层窗口是否有弹窗
all_windows = app.windows()
edit_win = try_find_edit_window(app)
if edit_win:
    print(f"\n  弹出窗口: '{edit_win.window_text()}' ({edit_win.class_name()})")
    save_screenshot(edit_win, "03_f3_popup.png")
    # 探查弹窗控件
    popup_ctrls = dump_controls_to_list(edit_win)
    print_controls_summary(popup_ctrls, "弹窗控件")
    with open(SCREENSHOT_DIR / "f3_popup_controls.json", "w", encoding="utf-8") as f:
        json.dump(popup_ctrls, f, ensure_ascii=False, indent=2)

    # 在弹窗中找输入框 → 输入 SB-S26070007
    popup_inputs = [c for c in popup_ctrls if c['class'] in ('TcxTextEdit', 'TEdit', 'Edit') and c['visible']]
    if popup_inputs:
        inp = popup_inputs[0]
        print(f"\n  在弹窗输入框中输入 SB-S26070007...")
        try:
            input_ctrl = edit_win.child_window(class_name=inp['class'], found_index=0)
            input_ctrl.click_input(); time.sleep(0.3)
            input_ctrl.type_keys("^a{BACKSPACE}", with_spaces=True); time.sleep(0.2)
            input_ctrl.type_keys("SB-S26070007", with_spaces=True)
            print("  已输入")
            time.sleep(0.5)
            save_screenshot(edit_win, "04_input_search_term.png")

            # 按回车
            print("  按 Enter 检索...")
            send_keys('{ENTER}')
            time.sleep(3)
            save_screenshot(edit_win, "05_search_results.png")

            # 重新采集控件找结果
            results_ctrls = dump_controls_to_list(edit_win)
            with open(SCREENSHOT_DIR / "search_results_controls.json", "w", encoding="utf-8") as f:
                json.dump(results_ctrls, f, ensure_ascii=False, indent=2)

            # 找含 SB-S26070007 的控件
            found_cells = [c for c in results_ctrls if 'SB-S26070007' in c['text']]
            print(f"\n  找到 {len(found_cells)} 个含 SB-S26070007 的控件:")
            for fc in found_cells:
                print(f"    [{fc['class']}] '{fc['text']}' {fc['rect']}")

            if found_cells:
                # 双击第一个找到的单元格
                fc = found_cells[0]
                nums = re.findall(r'-?\d+', fc['rect'])
                if len(nums) >= 4:
                    left, top, right, bottom = map(int, nums[:4])
                    cx, cy = (left + right) // 2, (top + bottom) // 2
                    print(f"  双击坐标: ({cx}, {cy})")
                    edit_win.click_input(coords=(cx, cy), double=True)
                    time.sleep(3)

                    # 检查是否有编辑窗口打开
                    save_screenshot(main_win, "06_after_doubleclick.png")
                    time.sleep(1)

                    # 找新弹出的编辑窗口
                    edit_form = try_find_edit_window(app)
                    if edit_form:
                        print(f"\n  [发现] 编辑窗口: '{edit_form.window_text()}' ({edit_form.class_name()})")
                        save_screenshot(edit_form, "07_edit_form.png")

                        # 探查编辑窗口控件
                        edit_ctrls = dump_controls_to_list(edit_form)
                        with open(SCREENSHOT_DIR / "edit_form_controls.json", "w", encoding="utf-8") as f:
                            json.dump(edit_ctrls, f, ensure_ascii=False, indent=2)
                        print_controls_summary(edit_ctrls, "编辑窗口控件")
                    else:
                        print("  未检测到编辑弹窗，检查所有窗口...")
                        for w in app.windows():
                            if w.is_visible():
                                print(f"    '{w.window_text()[:60]}' ({w.class_name()})")
            else:
                print("  SB-S26070007 未在结果中找到，继续探查...")
                # 探查表格控件
                grids = [c for c in results_ctrls if 'Grid' in c['class'] and c['visible']]
                for g in grids:
                    print(f"    表格: [{g['class']}] {g['rect']}")
        except Exception as e:
            print(f"  操作出错: {e}")
    else:
        print("  弹窗中未找到输入框")

else:
    # F3 没弹窗，尝试其他方式找检索
    print("  F3 未弹出检索窗口，尝试其他方式...")

    # 检查首页上的工具栏
    all_controls = dump_controls_to_list(main_win, max_depth=3)
    tool_buttons = [c for c in all_controls if c['depth'] <= 2 and c['visible'] and c['text'].strip() and c['class'] in ('TcxButton', 'TBitBtn', 'TSpeedButton')]
    print(f"\n  首页工具栏按钮:")
    for tb in tool_buttons[:20]:
        print(f"    '{tb['text']}' {tb['rect']}")

    # 截图首页全貌
    save_screenshot(main_win, "02_homepage_detail.png")

    # 尝试 Alt+F 或 Ctrl+F 等快捷键
    for key, label in [('^f', 'Ctrl+F'), ('%f', 'Alt+F'), ('{F4}', 'F4'), ('{F2}', 'F2')]:
        print(f"\n  尝试 {label}...")
        send_keys(key)
        time.sleep(2)
        ew = try_find_edit_window(app)
        if ew:
            print(f"  {label} 触发了窗口: '{ew.window_text()}'")
            save_screenshot(ew, f"03_{label.replace('{','').replace('}','')}_popup.png")
            break

# 最终状态
print("\n" + "=" * 60)
print("当前所有可见窗口:")
for w in app.windows():
    if w.is_visible():
        print(f"  '{w.window_text()[:70]}' ({w.class_name()}) rect={w.rectangle()}")
print(f"截图目录: {SCREENSHOT_DIR}")
print("=" * 60)
