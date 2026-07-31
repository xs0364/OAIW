# -*- coding: utf-8 -*-
"""
佰信高精度二维坐标测绘系统 v1
================================
目标：绘制 BestLOGFW 窗口的全状态二维坐标图
  - 工具栏模式 1（初始）：基本操作 / 程序目录 / 窗口 / 帮助
  - 工具栏模式 2（主菜单模式）：业务管理 / 海运操作 / 空运操作 / 结算中心 / 报表中心 / 经理查询
  - 弹出子菜单：基本操作菜单、海运操作菜单、空运操作菜单等
  - 订舱管理界面：输入框、按钮、表格

工作原理：
  1. 全屏截图 → EasyOCR 识别所有文本 → 建立绝对坐标映射
  2. 联动 pywinauto win32 backend 读取控件树做交叉验证
  3. 输出结构化 JSON 坐标图

输出：D:\OAIW\_coord_map.json（程序可读）
      D:\OAIW\_baixin_screenshots\coord_map_*.png（可视化标注截图）
"""
import sys, time, ctypes, win32gui, win32api, json, pathlib
sys.stdout.reconfigure(encoding='utf-8')

PROC_ID = 5804
OUT_DIR = pathlib.Path(r"D:\OAIW\_baixin_screenshots")
OUT_DIR.mkdir(exist_ok=True)
MAP_FILE = pathlib.Path(r"D:\OAIW\_coord_map.json")

from pywinauto import Application
from pywinauto.keyboard import send_keys
import pyautogui, easyocr, cv2
import numpy as np
pyautogui.FAILSAFE = False

# ===== Win32 SendInput =====
class M(ctypes.Structure):
    _fields_ = [('dx', ctypes.c_long), ('dy', ctypes.c_long),
                ('mouseData', ctypes.c_ulong), ('dwFlags', ctypes.c_ulong),
                ('time', ctypes.c_ulong), ('dwExtraInfo', ctypes.POINTER(ctypes.c_ulong))]
class I(ctypes.Structure):
    _fields_ = [('type', ctypes.c_ulong), ('mi', M)]

def clk(x, y):
    sw=win32api.GetSystemMetrics(0); sh=win32api.GetSystemMetrics(1)
    ax=int(x*65535/sw); ay=int(y*65535/sh)
    u=ctypes.windll.user32
    def inp(f): i=I(); i.type=0; i.mi=M(ax,ay,0,f,0,None); return i
    u.SendInput(1, ctypes.byref(inp(1|0x8000)), ctypes.sizeof(I())); time.sleep(0.05)
    u.SendInput(1, ctypes.byref(inp(2)), ctypes.sizeof(I())); time.sleep(0.1)
    u.SendInput(1, ctypes.byref(inp(4)), ctypes.sizeof(I()))
    return (x, y)

# ===== Window helpers =====
def find_menus():
    wins = []
    def cb(h, _): wins.append(h); return True
    win32gui.EnumWindows(cb, None)
    menus = []
    for w in wins:
        try:
            if 'Menu' in win32gui.GetClassName(w) and win32gui.IsWindowVisible(w):
                r = win32gui.GetWindowRect(w)
                if 60 < r[2]-r[0] < 500:
                    menus.append((w, r))
        except: pass
    return menus

def wait_menu(timeout=2.5, min_h=60):
    start = time.time()
    while time.time() - start < timeout:
        ms = find_menus()
        if ms:
            m = max(ms, key=lambda x: x[1][3]-x[1][1])
            if m[1][3]-m[1][1] > min_h:
                return m
        time.sleep(0.15)
    return None

def wait_menu_gone(timeout=3):
    start = time.time()
    while time.time() - start < timeout:
        if not find_menus():
            return True
        time.sleep(0.15)
    return False

def close_all():
    for _ in range(4):
        send_keys('{ESC}'); time.sleep(0.2)

# ===== EasyOCR =====
print("Loading EasyOCR...")
reader = easyocr.Reader(['ch_sim', 'en'], gpu=False, verbose=False)
print("  OK")

# ===== Connect =====
app = Application(backend="win32").connect(process=PROC_ID)
mw = None
for w in app.windows():
    try:
        if w.is_visible() and w.class_name() == "TfmMainD": mw = w; break
    except: pass
if not mw: print("Main window not found"); sys.exit(1)
hwnd = mw.handle; wr = mw.rectangle()
print(f"\nMain window: {wr}")
print(f"  Handle: 0x{hwnd:08x}")
print(f"  Dimensions: {wr.width()} x {wr.height()}")

# ===== State definitions =====
# Each state: (name, description, setup_fn, screenshot_fn)
# We'll take a screenshot, OCR it, and record all text positions

states = {}
coord_map = {
    "window": {
        "handle": hwnd,
        "rect": {"left": wr.left, "top": wr.top, "right": wr.right, "bottom": wr.bottom,
                  "width": wr.width(), "height": wr.height()},
    },
    "states": {},
    "elements": {}  # aggregated by function
}

def ocr_screenshot(name):
    """Take screenshot, OCR it, return structured results"""
    img = pyautogui.screenshot()
    path = OUT_DIR / f"coord_{name}.png"
    img.save(str(path))
    cv_img = cv2.imread(str(path))
    results = reader.readtext(cv_img)
    items = []
    for bbox, text, conf in results:
        text = text.strip()
        if len(text) >= 2 and conf > 0.3:
            x1, y1 = int(bbox[0][0]), int(bbox[0][1])
            x2, y2 = int(bbox[2][0]), int(bbox[2][1])
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            w, h = x2 - x1, y2 - y1
            items.append({
                "text": text, "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                "cx": cx, "cy": cy, "w": w, "h": h, "conf": round(conf, 2)
            })
    return str(path), items

def annotate_coord_map(name, items, state_info):
    """Draw annotated coordinate marks on a screenshot"""
    img_path = OUT_DIR / f"coord_{name}.png"
    img = cv2.imread(str(img_path))
    if img is None:
        return
    for item in items:
        x1, y1, x2, y2 = item["x1"], item["y1"], item["x2"], item["y2"]
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 1)
        cv2.circle(img, (item["cx"], item["cy"]), 3, (0, 0, 255), -1)
        cv2.putText(img, f"({item['cx']},{item['cy']})", (x1, y1-5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 0, 0), 1)
    anno_path = OUT_DIR / f"coord_{name}_annotated.png"
    cv2.imwrite(str(anno_path), img)

def focus_main():
    try:
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.3)
    except: pass

# ============================================================
# STATE 0: Initial toolbar (normal mode)
# ============================================================
print("\n" + "="*60)
print("STATE 0: Normal toolbar (基本操作 visible)")
print("="*60)
focus_main()
close_all(); time.sleep(1)
focus_main()
time.sleep(0.5)

path0, items0 = ocr_screenshot("state0_normal")
coord_map["states"]["state0_normal"] = {
    "description": "Normal toolbar mode (just logged in / no menu open)",
    "screenshot": path0,
    "items": items0
}
annotate_coord_map("state0_normal", items0, None)
print(f"  Found {len(items0)} text elements")

# Filter to toolbar region (y = 20-60)
toolbar0 = [i for i in items0 if 20 <= i["cy"] <= 60]
print(f"  Toolbar region (y=20-60): {len(toolbar0)} items")
for i in toolbar0:
    print(f"    '{i['text']}' @ ({i['cx']},{i['cy']})  w={i['w']} conf={i['conf']}")

# ============================================================
# STATE 1: Click 基本操作 → show popup menu
# ============================================================
print("\n" + "="*60)
print("STATE 1: 基本操作 popup menu")
print("="*60)
focus_main()
clk(wr.left + 40, wr.top + 34)
time.sleep(0.8)
m1 = wait_menu(3)
if m1:
    mr1 = m1[1]
    path1, items1 = ocr_screenshot("state1_jbcz_menu")
    coord_map["states"]["state1_jbcz_menu"] = {
        "description": "基本操作 popup menu",
        "menu_rect": {"left": mr1[0], "top": mr1[1], "right": mr1[2], "bottom": mr1[3],
                       "w": mr1[2]-mr1[0], "h": mr1[3]-mr1[1]},
        "screenshot": path1,
        "items": items1
    }
    annotate_coord_map("state1_jbcz_menu", items1, None)
    print(f"  Menu rect: {mr1}")
    print(f"  Found {len(items1)} text elements")

    # Items within the menu
    menu_items1 = [i for i in items1 if mr1[0] <= i["cx"] <= mr1[2] and mr1[1] <= i["cy"] <= mr1[3]]
    for i in menu_items1:
        print(f"    '{i['text']}' @ ({i['cx']},{i['cy']})  w={i['w']} conf={i['conf']}")

    # Store menu items in elements
    coord_map["elements"]["jbcz_menu"] = {
        "trigger": {"x": wr.left + 40, "y": wr.top + 34, "name": "基本操作"},
        "menu_rect": {"left": mr1[0], "top": mr1[1], "right": mr1[2], "bottom": mr1[3]},
        "items": []
    }
    for i in menu_items1:
        coord_map["elements"]["jbcz_menu"]["items"].append({
            "name": i["text"], "x": i["cx"], "y": i["cy"],
            "w": i["w"], "h": i["h"], "conf": i["conf"]
        })

# ============================================================
# STATE 2: Click 主菜单 → switch to main menu toolbar mode
# ============================================================
print("\n" + "="*60)
print("STATE 2: Main menu toolbar mode")
print("="*60)

# Find 主菜单 in the menu
if m1:
    mr1 = m1[1]
    menu_items1 = [i for i in items1 if mr1[0] <= i["cx"] <= mr1[2] and mr1[1] <= i["cy"] <= mr1[3]]
    # Find 主菜单 or 主莱单
    zjcd_target = None
    for i in menu_items1:
        if any(t in i["text"] for t in ['主菜单', '主莱单']):
            zjcd_target = (i["cx"], i["cy"])
            print(f"  Clicking '主菜单' @ ({i['cx']},{i['cy']})")
            break
    if zjcd_target:
        clk(zjcd_target[0], zjcd_target[1])
        time.sleep(0.5)
        wait_menu_gone(2)
        time.sleep(1.5)
        focus_main()
        time.sleep(0.5)

        path2, items2 = ocr_screenshot("state2_main_menu")
        coord_map["states"]["state2_main_menu"] = {
            "description": "Main menu toolbar mode (主菜单 clicked)",
            "screenshot": path2,
            "items": items2
        }
        annotate_coord_map("state2_main_menu", items2, None)
        print(f"  Found {len(items2)} text elements")

        # Toolbar row 2 buttons (y=40-70)
        toolbar2 = [i for i in items2 if 40 <= i["cy"] <= 70]
        print(f"  Toolbar region (y=40-70): {len(toolbar2)} items")
        for i in toolbar2:
            print(f"    '{i['text']}' @ ({i['cx']},{i['cy']})  w={i['w']} conf={i['conf']}")

        # Store toolbar buttons
        coord_map["elements"]["main_toolbar"] = {"mode": "主菜单", "y_row": 56, "buttons": []}
        for i in toolbar2:
            coord_map["elements"]["main_toolbar"]["buttons"].append({
                "name": i["text"], "x": i["cx"], "y": i["cy"],
                "w": i["w"], "h": i["h"], "conf": i["conf"]
            })

        # ============================================================
        # STATE 3: Click 海运操作 → show submenu
        # ============================================================
        print("\n" + "="*60)
        print("STATE 3: 海运操作 submenu")
        print("="*60)

        # Find 海运操作 button
        hy_target = None
        for i in toolbar2:
            if any(t in i["text"] for t in ['海运操作', '海运操怍', '海运']):
                hy_target = (i["cx"], i["cy"])
                print(f"  Found '海运操作' @ ({i['cx']},{i['cy']})")
                break

        if not hy_target:
            # Try probe scan
            print("  OCR missed it, probing...")
            for x_off in range(100, 200, 5):
                clk(x_off, 56)
                m = wait_menu(0.6, 60)
                if m:
                    mr = m[1]
                    # OCR the submenu
                    sub_img = pyautogui.screenshot(region=(mr[0], mr[1], mr[2]-mr[0], mr[3]-mr[1]))
                    sub_path = OUT_DIR / "coord_submenu_probe.png"
                    sub_img.save(str(sub_path))
                    sub_cv = cv2.imread(str(sub_path))
                    sub_results = reader.readtext(sub_cv)
                    for bbox, text, conf in sub_results:
                        if any(t in text for t in ['订舱', '订仓', 'dingcang']):
                            hy_target = (x_off, 56)
                            print(f"  Found 海运操作 at x={x_off} via submenu probe")
                            break
                    close_all()
                    time.sleep(1)
                    if hy_target:
                        break

        if hy_target:
            # Navigate again: 基本操作 → 主菜单 → 海运操作
            focus_main()
            close_all(); time.sleep(0.5)
            focus_main()
            clk(wr.left + 40, wr.top + 34); time.sleep(0.8)
            m = wait_menu(2)
            if m:
                mr = m[1]
                # OCR menu1
                menu_img = pyautogui.screenshot(region=(mr[0], mr[1], mr[2]-mr[0], mr[3]-mr[1]))
                menu_cv = cv2.imread(str(OUT_DIR / "coord_menu1_refresh.png"))
                cv2.imwrite(str(OUT_DIR / "coord_menu1_refresh.png"), cv2.cvtColor(np.array(menu_img), cv2.COLOR_RGB2BGR))
                menu_res = reader.readtext(menu_cv)
                zjcd = None
                for bbox, text, conf in menu_res:
                    if any(t in text for t in ['主菜单', '主莱单']):
                        x1,y1 = int(bbox[0][0]), int(bbox[0][1])
                        x2,y2 = int(bbox[2][0]), int(bbox[2][1])
                        zjcd = (mr[0]+(x1+x2)//2, mr[1]+(y1+y2)//2)
                        break
                if zjcd:
                    clk(zjcd[0], zjcd[1]); time.sleep(1.5)
                    clk(hy_target[0], hy_target[1]); time.sleep(1.5)

                    m3 = wait_menu(3)
                    if m3:
                        mr3 = m3[1]
                        path3, items3 = ocr_screenshot("state3_hy_submenu")
                        coord_map["states"]["state3_hy_submenu"] = {
                            "description": "海运操作 submenu",
                            "menu_rect": {"left": mr3[0], "top": mr3[1], "right": mr3[2], "bottom": mr3[3],
                                           "w": mr3[2]-mr3[0], "h": mr3[3]-mr3[1]},
                            "screenshot": path3,
                            "items": items3
                        }
                        annotate_coord_map("state3_hy_submenu", items3, None)
                        print(f"  Submenu rect: {mr3}")

                        # Items within submenu
                        sub_items = [i for i in items3 if mr3[0] <= i["cx"] <= mr3[2] and mr3[1] <= i["cy"] <= mr3[3]]
                        coord_map["elements"]["hy_submenu"] = {
                            "trigger": {"x": hy_target[0], "y": hy_target[1], "name": "海运操作"},
                            "menu_rect": {"left": mr3[0], "top": mr3[1], "right": mr3[2], "bottom": mr3[3]},
                            "items": []
                        }
                        for i in sub_items:
                            print(f"    '{i['text']}' @ ({i['cx']},{i['cy']})  w={i['w']} conf={i['conf']}")
                            coord_map["elements"]["hy_submenu"]["items"].append({
                                "name": i["text"], "x": i["cx"], "y": i["cy"],
                                "w": i["w"], "h": i["h"], "conf": i["conf"]
                            })

                        # ============================================================
                        # STATE 4: Click 订舱管理 → open booking module
                        # ============================================================
                        print("\n" + "="*60)
                        print("STATE 4: 订舱管理 module")
                        print("="*60)

                        dc_target = None
                        for i in sub_items:
                            if any(t in i["text"] for t in ['订舱管理', '订舱', '订仓管理']):
                                dc_target = (i["cx"], i["cy"])
                                print(f"  Clicking '订舱管理' @ ({i['cx']},{i['cy']})")
                                break

                        if dc_target:
                            clk(dc_target[0], dc_target[1])
                            time.sleep(2)

                            # Wait for menu to close and module to load
                            wait_menu_gone(3)
                            time.sleep(3)

                            path4, items4 = ocr_screenshot("state4_booking_module")
                            coord_map["states"]["state4_booking_module"] = {
                                "description": "订舱管理 module (after clicking 订舱管理)",
                                "screenshot": path4,
                                "items": items4
                            }
                            annotate_coord_map("state4_booking_module", items4, None)
                            print(f"  Found {len(items4)} text elements")

                            # Look for input boxes and content area
                            # Check if module loaded - look for typical booking UI text
                            booking_keywords = ['订舱', 'SB-', '提单', '船期', '航次', 'VESSEL', 'VOYAGE', '装货港', '卸货港']
                            booking_text = [i for i in items4 if any(k in i["text"] for k in booking_keywords)]
                            print(f"  Booking-related text: {len(booking_text)} items")
                            for i in booking_text:
                                print(f"    '{i['text']}' @ ({i['cx']},{i['cy']})  conf={i['conf']}")

                            if booking_text:
                                coord_map["elements"]["booking_module"] = {
                                    "visible": True,
                                    "items": booking_text
                                }
                            else:
                                print("  ⚠️ Booking module UI not detected in OCR!")
                                print("  Possible: module loads in child window, or didn't open")
                                coord_map["elements"]["booking_module"] = {
                                    "visible": False,
                                    "note": "Booking module text not detected in main window OCR"
                                }

                            # Scan controls
                            def scan_ctrl(ctl, d=0, md=6):
                                items = []
                                if d > md: return items
                                try:
                                    if ctl.is_visible():
                                        txt = ctl.window_text()[:80]
                                        cls = ctl.class_name()
                                        r = ctl.rectangle()
                                        items.append({"text": txt, "class": cls, "rect": {"l":r.left,"t":r.top,"r":r.right,"b":r.bottom}})
                                        for ch in ctl.children():
                                            items.extend(scan_ctrl(ch, d+1, md))
                                except: pass
                                return items

                            all_ctrl = scan_ctrl(mw)
                            inputs = [c for c in all_ctrl if c["class"] in ('TcxTextEdit','TEdit','Edit')]
                            print(f"\n  Control scan: {len(all_ctrl)} total, {len(inputs)} input boxes")

                            # Also check child windows
                            def enum_child(h, _):
                                try:
                                    if win32gui.IsWindowVisible(h):
                                        cls = win32gui.GetClassName(h)
                                        txt = win32gui.GetWindowText(h)[:80]
                                        r = win32gui.GetWindowRect(h)
                                        print(f"    Child: [{cls}] '{txt}' ({r[0]},{r[1]})-({r[2]},{r[3]})")
                                except: pass
                                return True

                            print("\n  Visible child windows:")
                            win32gui.EnumChildWindows(hwnd, enum_child, None)

                            # Check for input boxes in child windows too
                            for c in all_ctrl[:20]:
                                print(f"    [{c['class']}] '{c['text'][:60]}' {c['rect']}")

                            coord_map["states"]["state4_booking_module"]["controls"] = {
                                "total": len(all_ctrl),
                                "inputs": len(inputs),
                                "input_classes": list(set(c["class"] for c in inputs))
                            }
                        else:
                            print("  ❌ 订舱管理 not found in submenu!")
                    else:
                        print("  ❌ No popup after clicking 海运操作!")
                else:
                    print("  ❌ 主菜单 not found in re-navigation!")
            else:
                print("  ❌ Failed to open 基本操作 menu!")
        else:
            print("  ❌ 海运操作 not found!")
    else:
        print("  ❌ 主菜单 not found!")
else:
    print("  ❌ No popup after clicking 基本操作!")

# ============================================================
# Save coordinate map
# ============================================================
print("\n" + "="*60)
print("Saving coordinate map...")

# Clean items from states (too verbose for JSON)
map_for_json = {
    "window": coord_map["window"],
    "states": {},
    "elements": coord_map["elements"]
}
for state_name, state_data in coord_map["states"].items():
    clean = {}
    for k, v in state_data.items():
        if k != "items":  # Skip raw OCR items in JSON
            clean[k] = v
    clean["item_count"] = len(state_data.get("items", []))
    map_for_json["states"][state_name] = clean

with open(str(MAP_FILE), 'w', encoding='utf-8') as f:
    json.dump(map_for_json, f, ensure_ascii=False, indent=2)

print(f"  Saved to {MAP_FILE}")
print(f"  States captured: {list(coord_map['states'].keys())}")
print(f"  Element groups: {list(coord_map['elements'].keys())}")

# ============================================================
# Summary
# ============================================================
print("\n" + "="*60)
print("COORDINATE MAP SUMMARY")
print("="*60)

for elem_name, elem_data in coord_map["elements"].items():
    print(f"\n  [{elem_name}]")
    if "trigger" in elem_data:
        t = elem_data["trigger"]
        print(f"    Trigger: '{t.get('name','')}' @ ({t['x']},{t['y']})")
    if "menu_rect" in elem_data:
        mr = elem_data["menu_rect"]
        print(f"    Menu rect: ({mr['left']},{mr['top']})-({mr['right']},{mr['bottom']}) = {mr.get('w',mr['right']-mr['left'])}x{mr.get('h',mr['bottom']-mr['top'])}")
    if "buttons" in elem_data:
        for b in elem_data["buttons"]:
            print(f"    Button: '{b['name']}' @ ({b['x']},{b['y']})  {b['w']}x{b['h']}  conf={b['conf']}")
    if "items" in elem_data:
        for it in elem_data["items"]:
            if "x" in it:
                print(f"    Item: '{it['name']}' @ ({it['x']},{it['y']})  {it.get('w','?')}x{it.get('h','?')}  conf={it.get('conf','?')}")
            else:
                print(f"    Item: '{it.get('text','')}' @ ({it.get('cx','?')},{it.get('cy','?')})")

print(f"\n{'='*60}")
print(f"Annotated screenshots saved to {OUT_DIR}")
print(f"coord_*.png = raw screenshots")
print(f"coord_*_annotated.png = with coordinate markers")
print(f"{'='*60}")

# Final: close any open menus
close_all()
time.sleep(0.5)
print("\nDone.")
