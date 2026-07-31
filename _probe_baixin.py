"""
佰信系统(BestLOG)桌面客户端摸底脚本
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

# 开始探查
print("[DEBUG] sys.executable:", sys.executable)
print("[DEBUG] sys.path:", sys.path)
try:
    print("[DEBUG] Attempting import pywinauto...")
    import pywinauto
    print("[DEBUG] pywinauto imported OK, version:", pywinauto.__version__ if hasattr(pywinauto, '__version__') else '?')
    from pywinauto import Desktop, Application
    from pywinauto.timing import wait_until
    print("[DEBUG] pywinauto imports all OK")

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
        # 如果没找到有标题的可见窗口，就用第一个窗口
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
                text = ctl.window_text()[:50] if ctl.window_text() else ""
                class_name = ctl.class_name()
                rect = ctl.rectangle()
                is_vis = ctl.is_visible()
                is_en = ctl.is_enabled()
                ctrl_id = ctl.control_id()

                print(f"{indent}{class_name:30s} id={ctrl_id:5d}  '{text}'  "
                      f"({rect.left},{rect.top},{rect.right},{rect.bottom})  "
                      f"vis={is_vis} en={is_en}")

                # 递归子控件
                try:
                    children = ctl.children()
                    for child in children:
                        dump_controls(child, depth + 1)
                except:
                    pass
            except Exception as e:
                print(f"{indent}[ERROR] {e}")

        dump_controls(main_win)

        # 特别搜索：定位可输入的 Edit 控件和 Button 控件
        print(f"\n{'='*60}")
        print("[关键控件汇总]")
        print(f"{'='*60}")

        try:
            edits = main_win.descendants(control_type="Edit")
            print(f"\n[Edit 输入框] ({len(edits)} 个):")
            for e in edits:
                print(f"  - class={e.class_name()}  text='{e.window_text()}'  rect={e.rectangle()}")
        except:
            pass

        try:
            buttons = main_win.descendants(control_type="Button")
            print(f"\n[Button 按钮] ({len(buttons)} 个):")
            for b in buttons:
                print(f"  - class={b.class_name()}  text='{b.window_text()}'  rect={b.rectangle()}")
        except:
            pass

        # 通过类名搜索常见的 Delphi 控件
        for cls in ["TEdit", "TButton", "TLabel", "TComboBox", "TCheckBox", "TRadioButton",
                    "TPanel", "TForm", "TBitBtn", "TSpeedButton", "TMenuItem",
                    "Edit", "Button", "Static", "ComboBox", "CheckBox"]:
            try:
                ctrls = main_win.descendants(class_name=cls)
                if ctrls:
                    print(f"\n[类名 '{cls}'] ({len(ctrls)} 个):")
                    for c in ctrls[:30]:  # 最多显示30个
                        print(f"  - text='{c.window_text()[:40]}'  rect={c.rectangle()}  enabled={c.is_enabled()}")
            except:
                pass
    else:
        print("[失败] 未找到任何可见窗口")

except ImportError:
    print("[失败] 需要先安装 pywinauto: pip install pywinauto")
except Exception as e:
    import traceback
    print(f"[失败] 探查出错: {e}")
    traceback.print_exc()
finally:
    print(f"\n{'='*60}")
    print("[提示] 探查完成后请手动关闭佰信窗口，或按 Ctrl+C 退出")
    print(f"{'='*60}")
