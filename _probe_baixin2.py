"""
佰信系统(BestLOG)桌面客户端摸底脚本 v2
功能：探查 BestLOGFW.exe 窗口结构，识别所有可操作控件
"""
import sys
import time
import subprocess
from pathlib import Path

# 先杀掉已有进程，保证从登录窗口开始
subprocess.run(["taskkill", "/f", "/im", "BestLOGFW.exe"], capture_output=True)
time.sleep(1)

# 启动佰信
BAIXIN_PATH = r"D:\Best-Hint\BestLOG\BestLOGFW.exe"
print(f"[启动] 佰信: {BAIXIN_PATH}")
proc = subprocess.Popen([BAIXIN_PATH], cwd=r"D:\Best-Hint\BestLOG")

# 等待窗口出现
print("[等待] 窗口加载...")
time.sleep(5)

print("[DEBUG] sys.executable:", sys.executable)

# 分别导入，定位问题
print("[DEBUG] step1: import pywinauto...")
import pywinauto
print("[DEBUG] step2: from pywinauto import Application...")
from pywinauto import Application
print("[DEBUG] step3: 全部导入成功")

try:
    print("[连接] 连接到 BestLOG 进程...")
    app = Application(backend="win32").connect(path=BAIXIN_PATH, timeout=30)
    print("[OK] 已连接到 BestLOG 进程")

    # 列出所有顶级窗口
    print("\n" + "="*60)
    print("[所有顶级窗口]")
    print("="*60)
    for i, w in enumerate(app.windows()):
        print(f"  [{i}] handle=0x{w.handle:08x}  title='{w.window_text()}'  class='{w.class_name()}'  visible={w.is_visible()}")

    # 定位主登录窗口（通常是第一个可见的顶级窗口）
    main_win = None
    for w in app.windows():
        if w.is_visible() and w.window_text():
            main_win = w
            break

    if not main_win:
        windows = app.windows()
        if windows:
            main_win = windows[0]

    if main_win:
        print(f"\n{'='*60}")
        print("[主窗口详情]")
        print(f"  标题: '{main_win.window_text()}'")
        print(f"  类名: '{main_win.class_name()}'")
        print(f"  Rect: {main_win.rectangle()}")
        print(f"{'='*60}")

        # 深度遍历所有子控件
        print("\n[控件树 - 完整遍历]")
        print(f"{'='*60}")

        def dump_controls(ctl, depth=0):
            indent = "  " * depth
            try:
                text = ctl.window_text()[:60] if ctl.window_text() else ""
                class_name = ctl.class_name()
                rect = ctl.rectangle()
                is_vis = ctl.is_visible()
                is_en = ctl.is_enabled()
                ctrl_id = ctl.control_id()

                print(f"{indent}{class_name:30s} id={ctrl_id:5d}  '{text}'  "
                      f"({rect.left},{rect.top},{rect.right},{rect.bottom})  "
                      f"vis={is_vis} en={is_en}")

                try:
                    children = ctl.children()
                    for child in children:
                        dump_controls(child, depth + 1)
                except:
                    pass
            except Exception as e:
                print(f"{indent}[ERROR] {e}")

        dump_controls(main_win)

        # 通过类名搜索 Delphi 控件
        print(f"\n{'='*60}")
        print("[Delphi 控件扫描]")
        print(f"{'='*60}")
        for cls in ["TEdit", "TButton", "TLabel", "TComboBox", "TCheckBox", "TRadioButton",
                    "TPanel", "TForm", "TBitBtn", "TSpeedButton", "TMenuItem",
                    "TMaskEdit", "TDBEdit", "TDBGrid",
                    "Edit", "Button", "Static", "ComboBox", "CheckBox",
                    "WindowsForms10.EDIT", "WindowsForms10.BUTTON"]:
            try:
                ctrls = main_win.descendants(class_name=cls)
                if ctrls:
                    print(f"\n[类名 '{cls}'] ({len(ctrls)} 个):")
                    for c in ctrls[:30]:
                        txt = c.window_text()[:50] if c.window_text() else "(空)"
                        print(f"  - text='{txt}'  rect={c.rectangle()}  enabled={c.is_enabled()}")
            except Exception as e:
                pass

        # 用 Desktop 方式枚举所有顶层窗口
        print(f"\n{'='*60}")
        print("[Desktop 所有窗口]")
        print(f"{'='*60}")
        try:
            desktop = Desktop(backend="win32")
            for w in desktop.windows():
                if w.is_visible():
                    print(f"  title='{w.window_text()[:50]}'  class='{w.class_name()}'  rect={w.rectangle()}")
        except Exception as e:
            print(f"[Desktop 枚举失败] {e}")

    else:
        print("[失败] 未找到任何可见窗口")

except Exception as e:
    import traceback
    error_msg = str(e)
    print(f"[失败] 探查出错: {error_msg}")
    traceback.print_exc()

finally:
    print(f"\n{'='*60}")
    print("[提示] 探查完成，请手动关闭佰信窗口")
    print(f"{'='*60}")
