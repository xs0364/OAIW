# -*- coding: utf-8 -*-
"""
佰信 — 合并录入填值脚本
========================
读取 _merge_outputs 下的 {order_no}_{container_no}.json（字段级合并结果），
在佰信订舱编辑弹窗中按 _baixin_fill_template.json 坐标填入：
  - 表单 text/date 字段（button/combo 跳过；件数/毛重/体积等 autofill 字段主动覆盖）
  - 网格 7 列（可见列固定 x；滚动列 拖滑块 + header_ocr 动态定位 x）
不点保存 —— 填完待人工核对。

用法:
    python _baixin_merge_fill.py {order_no}_{container_no}.json

弹窗已开 → 复用；未开 → 调用 _baixin_rerun_flow.py {order_no} 打开。
"""
import sys, time, subprocess, json, pathlib, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import numpy as np
from pywinauto import Application
from pywinauto.keyboard import send_keys
import win32gui, win32con, ctypes
from _baixin_positions import ensure_popup_position
from _baixin_capture import capture_hwnd
import pyautogui
import easyocr, cv2

pyautogui.FAILSAFE = False
MERGE_DIR = r"D:\OAIW\_merge_outputs"
RERUN = r"D:\OAIW\_baixin_rerun_flow.py"
SHOT = r"D:\OAIW\_baixin_screenshots"
pathlib.Path(SHOT).mkdir(exist_ok=True)

GRID = (905, 594, 1277, 709)   # 网格视口（绝对坐标，弹窗在默认位）
ROW_Y_DEFAULT = 619            # 网格首行 y（fill3/gw 验证）
ROW_Y = ROW_Y_DEFAULT

# 表单可填字段：(中文label, template key, 合并source key, 绝对pos, 类型)
# 只含 text/date；button/combo 由人工处理（vessel/pol/dest/size_type 等）
FORM_FIELDS = [
    ("S/O NO",       "so_no",      "booking_no", (833, 311),  "text"),
    ("船东提单号",    "bl_no",      "bl_no",      (641, 335),  "text"),
    ("码头",         "terminal",   "terminal",   (999, 358),  "text"),
    ("ETD",          "etd",        "etd",        (833, 378),  "date"),
    ("ETA",          "eta",        "eta",        (1023, 378), "date"),
    ("货物简称",      "cargo_name", "cargo_name", (641, 493),  "text"),
    ("件数",         "pieces",     "pieces",     (799, 493),  "text"),
    ("毛重",         "gross",      "gross",      (1023, 493), "text"),
    ("体积",         "volume",     "volume",     (1180, 493), "text"),
]

# 网格可见列（滑块在左端，固定 x，来源 fill3 表头OCR: 尺寸923/集箱号1034/封铅1103）
GRID_VISIBLE = [
    ("尺寸",   "size_type",   923),
    ("集箱号", "container_no", 1034),
    ("封铅号", "seal",         1103),
]
# 网格滚动列（需横向滚动后 header_ocr 动态定位）
GRID_SCROLL = [
    ("件数", "pieces"),
    ("毛重", "gross"),
    ("体积", "volume"),
    ("订舱", "booking_no"),
]


# ====================================================================
# 连接 / 前台
# ====================================================================
def find_pid():
    """找佰信 UI 进程 PID（排除无窗口辅助进程，佰信是双进程）"""
    from _baixin_positions import find_ui_pid
    return find_ui_pid()


def foreground():
    """强前台切换（addrow2/fill_gw 验证版）"""
    win32gui.ShowWindow(pop.handle, win32con.SW_RESTORE); time.sleep(0.2)
    fg = u.GetForegroundWindow()
    try:
        fg_tid = u.GetWindowThreadProcessId(fg, None)
        pop_tid = u.GetWindowThreadProcessId(pop.handle, None)
        if fg_tid != pop_tid:
            u.AttachThreadInput(fg_tid, pop_tid, True)
            u.BringWindowToTop(pop.handle); time.sleep(0.1)
            u.SetForegroundWindow(pop.handle); time.sleep(0.2)
            u.AttachThreadInput(fg_tid, pop_tid, False)
        else:
            u.SetForegroundWindow(pop.handle)
    except Exception:
        u.SetForegroundWindow(pop.handle)
    u.keybd_event(0x12, 0, 0, 0); u.keybd_event(0x12, 0, 2, 0); time.sleep(0.1)
    u.SetForegroundWindow(pop.handle); time.sleep(0.3)


def wait_data_load(pop, timeout=60):
    """等弹窗数据加载：轮询 TcxTextEdit 有内容字段，>=5 视为已加载。"""
    t0 = time.time(); last = -1
    while time.time() - t0 < timeout:
        fields = []
        for c in pop.descendants():
            try:
                cn = c.class_name()
                if cn in ("TcxTextEdit", "TcxCustomInnerTextEdit", "TEdit"):
                    t = c.window_text() or ""
                    if t.strip():
                        fields.append(t.strip())
            except: pass
        if len(fields) > 0 and len(fields) != last:
            print(f"  [{time.time()-t0:.0f}s] 有内容字段 {len(fields)} 个")
            last = len(fields)
        if len(fields) >= 5:
            print(f"✅ 数据加载完成 ({time.time()-t0:.1f}s)")
            return True
        time.sleep(1)
    print("⚠️ 数据加载超时，继续（可能已有值）")
    return False


def verify_popup_order(pop, order_no, timeout=20):
    """强制校验弹窗就是目标工作号（防止填错单）。
    轮询弹窗全部控件文本，命中完整单号或纯数字段（如 26070007）即通过。"""
    target = (order_no or "").strip().upper()
    digits = "".join(ch for ch in target if ch.isdigit())
    t0 = time.time()
    while time.time() - t0 < timeout:
        texts = []
        for c in pop.descendants():
            try:
                t = c.window_text() or ""
                if t.strip():
                    texts.append(t.strip().upper())
            except: pass
        joined = " ".join(texts)
        if target and target in joined:
            return True
        if digits and len(digits) >= 6 and digits in joined:
            return True
        time.sleep(1)
    return False


# ====================================================================
# 捕获 / OCR / 滑块（从 _baixin_fill_gw.py / _baixin_fill3.py 拷贝）
# ====================================================================
reader = easyocr.Reader(['ch_sim', 'en'], gpu=False, verbose=False)


def capture_grid_region():
    """PrintWindow 捕获网格区，返回 (crop, bgr, w, h)（绝对坐标偏移保留）"""
    img, ok = capture_hwnd(pop.handle, 0)
    if img is None:
        return None, None, 0, 0
    pw, ph = img.size
    rel = (GRID[0] - pr.left, GRID[1] - pr.top, GRID[2] - GRID[0], GRID[3] - GRID[1])
    rel = (max(0, rel[0]), max(0, rel[1]), min(pw - rel[0], rel[2]), min(ph - rel[1], rel[3]))
    crop = img.crop((rel[0], rel[1], rel[0] + rel[2], rel[1] + rel[3]))
    bgr = cv2.cvtColor(np.array(crop), cv2.COLOR_RGB2BGR)
    h, w = bgr.shape[:2]
    return crop, bgr, w, h


def header_ocr(img):
    """表头行 OCR，返回 [(x, text)]（x 为绝对坐标，偏移以 GRID 左上为基准）"""
    pw, ph = img.size
    rel = (GRID[0] - pr.left, 590 - pr.top, 372, 22)
    rel = (max(0, rel[0]), max(0, rel[1]), min(pw - rel[0], rel[2]), min(ph - rel[1], rel[3]))
    crop = img.crop((rel[0], rel[1], rel[0] + rel[2], rel[1] + rel[3]))
    bgr = cv2.cvtColor(np.array(crop), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    _, bw = cv2.threshold(gray, 160, 255, cv2.THRESH_BINARY)
    h, w = bw.shape[:2]
    fx = 6
    big = cv2.resize(bw, (int(w * fx), int(h * fx)), interpolation=cv2.INTER_CUBIC)
    out = []
    for bbox, text, conf in reader.readtext(big):
        text = text.strip()
        if not text: continue
        x = int(bbox[0][0] / fx) + GRID[0]
        out.append((x, text))
    return out


def slider_center(img):
    """横向滑块中心 x（绝对坐标），找不到返回 None"""
    pw, ph = img.size
    rel = (GRID[0] - pr.left, 692 - pr.top, 372, 17)
    rel = (max(0, rel[0]), max(0, rel[1]), min(pw - rel[0], rel[2]), min(ph - rel[1], rel[3]))
    crop = img.crop((rel[0], rel[1], rel[0] + rel[2], rel[1] + rel[3]))
    arr = np.array(crop.convert("L"))
    colmean = arr.mean(axis=0)
    track = np.median(colmean)
    diff = np.abs(colmean - track)
    thresh = 12
    segs = []; in_seg = False
    for i in range(len(diff)):
        if diff[i] > thresh and not in_seg:
            start = i; in_seg = True
        elif diff[i] <= thresh and in_seg:
            segs.append((start, i - 1)); in_seg = False
    if in_seg: segs.append((start, len(diff) - 1))
    cands = [s for s in segs if s[0] > 925 or s[1] < 1255]
    best = None
    for s in cands:
        L = s[1] - s[0]
        if best is None or L > best[0]:
            best = (L, s)
    if best:
        return (best[1][0] + best[1][1]) // 2 + GRID[0]
    return None


def drag(from_c, to_c):
    Y = 700
    pyautogui.moveTo(from_c, Y, duration=0.3); time.sleep(0.3)
    pyautogui.mouseDown(); time.sleep(0.3)
    for i in range(1, 9):
        cx = from_c + (to_c - from_c) * i / 8
        pyautogui.moveTo(cx, Y, duration=0.15); time.sleep(0.05)
    pyautogui.mouseUp(); time.sleep(1.0)


def detect_row_y():
    """检测首数据行中心 y（绝对坐标）。网格无数据行返回 None。"""
    crop, bgr, w, h = capture_grid_region()
    if bgr is None or h < 10:
        return None
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    rows = []
    for ry in range(1, h - 1):
        if int((gray[ry] < 235).sum()) > w * 0.4:
            rows.append(ry)
    bands = []
    for ry in rows:
        if bands and ry - bands[-1][-1] <= 3:
            bands[-1].append(ry)
        else:
            bands.append([ry])
    if len(bands) >= 2:
        hdr_b, row_b = bands[0], bands[1]
        y = (int((hdr_b[0] + hdr_b[-1]) / 2) + int((row_b[0] + row_b[-1]) / 2)) // 2 + GRID[1]
        return y
    return None


def find_dialog(app):
    """找可见 #32770 询问框，返回 (dlg, {按钮文本:(x,y)}, 消息文本)"""
    for w in app.windows():
        try:
            if w.class_name() == "#32770" and w.is_visible():
                btns = {}; msgs = []
                for c in w.descendants():
                    try:
                        cn = c.class_name()
                        if not c.is_visible(): continue
                        r = c.rectangle()
                        t = (c.window_text() or "").strip()
                        if cn in ("Button", "TButton", "TcxButton"):
                            btns[t] = ((r.left + r.right) // 2, (r.top + r.bottom) // 2)
                        elif cn in ("Static", "TStaticText", "TcxLabel") and t:
                            msgs.append(t)
                    except: pass
                return w, btns, msgs
        except: pass
    return None, {}, []


def handle_dialog(app):
    """处理询问框：优先'是'，其次'确定'。返回描述。"""
    dlg, btns, msgs = find_dialog(app)
    if not dlg:
        return "无对话框"
    dr = dlg.rectangle()
    print(f"  对话框 @ ({dr.left},{dr.top})-({dr.right},{dr.bottom}) 消息={msgs} 按钮={list(btns)}")
    if not btns:
        return "无按钮可点"
    click_pos = None; which = None
    for key in ("是", "确定", "保存", "OK"):
        for t, pos in btns.items():
            if key in t:
                click_pos, which = pos, t; break
        if click_pos: break
    if not click_pos:
        first = list(btns.values())[0]
        click_pos, which = first, list(btns.keys())[0]
    print(f"  点击 '{which}' @ {click_pos}")
    pyautogui.click(*click_pos); time.sleep(1.2)
    return f"点击了 '{which}'"


def add_row():
    """右键网格空白 → OCR'新增一行' → 处理确认框。"""
    print("\n[加行] 右键 (1100,650)...")
    pyautogui.moveTo(1100, 650); time.sleep(0.3)
    pyautogui.click(button='right'); time.sleep(0.7)
    img = pyautogui.screenshot(region=(900, 640, 700, 330))
    bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    h, w = bgr.shape[:2]
    fx = 2.0
    big = cv2.resize(bgr, (int(w * fx), int(h * fx)), interpolation=cv2.INTER_CUBIC)
    target = None
    for bbox, text, conf in reader.readtext(big):
        text = text.strip()
        if "新增" in text or "新一行" in text:
            x = int(bbox[0][0] / fx) + 900
            y = int(bbox[0][1] / fx) + 640
            target = (x, y, text); break
    if not target:
        print("!! 未找到'新增一行'，跳过加行（若网格已有行则继续填值）")
        return False
    print(f"点击 '新增一行' @ ({target[0]},{target[1]})")
    pyautogui.moveTo(target[0], target[1]); time.sleep(0.3)
    pyautogui.click(); time.sleep(1.0)
    for attempt in range(4):
        result = handle_dialog(app)
        if result == "无对话框":
            break
        print(f"  → {result}")
        time.sleep(1.0)
    time.sleep(1.5)
    return True


# ====================================================================
# 填值
# ====================================================================
def fill_cell(x, value, tag):
    """网格单元格：单击→^a→输入→Tab（cxGrid 自动提交+横向滚动）"""
    pyautogui.moveTo(x, ROW_Y); time.sleep(0.4)
    pyautogui.click(); time.sleep(1.0)          # 慢速：点击后等系统聚焦输入框
    send_keys("^a"); time.sleep(0.2)
    send_keys(str(value)); time.sleep(0.8)
    send_keys("{TAB}"); time.sleep(1.3)
    print(f"  [{tag}] 已填 '{value}' @ x={x}")


def fmt_date(v):
    s = str(v).strip()
    s = s.split("T")[0]
    s = s.replace("/", "-")
    return s[:10]


def fill_form(x, y, value, tag, is_date=False):
    """表单字段：单击→^a→输入→Tab/Enter 提交"""
    v = fmt_date(value) if is_date else str(value)
    pyautogui.moveTo(x, y); time.sleep(0.4)
    pyautogui.click(); time.sleep(0.8)          # 慢速：点击后等系统聚焦输入框
    send_keys("^a"); time.sleep(0.2)
    send_keys(v); time.sleep(0.6)
    send_keys("{ENTER}" if is_date else "{TAB}"); time.sleep(0.8)
    print(f"  [{tag}] 已填 '{v}' @ ({x},{y})")


def find_col_x(targets, max_tries=8):
    """OCR 表头找目标列 x（绝对坐标）；找不到则向右拖滑块。返回 x 或 None。"""
    for i in range(max_tries):
        img, ok = capture_hwnd(pop.handle, 0)
        if img is None:
            break
        for x, t in header_ocr(img):
            t = t.strip()
            if any(k in t for k in targets) and 910 <= x <= 1280:
                return x
        sc = slider_center(img)
        if sc is None:
            sc = 1040
        drag(sc, min(sc + 60, 1255))
        time.sleep(0.6)
    return None


def has_value(v):
    if v is None:
        return False
    if isinstance(v, str):
        return bool(v.strip())
    if isinstance(v, (int, float)):
        return v not in (0, 0.0)
    return True


# ====================================================================
# 主流程
# ====================================================================
arg = sys.argv[1] if len(sys.argv) > 1 else ""
if not arg:
    print("用法: python _baixin_merge_fill.py {order_no}_{container_no}.json")
    sys.exit(1)
if not arg.endswith(".json"):
    arg += ".json"
path = arg if os.path.dirname(arg) else os.path.join(MERGE_DIR, arg)
if not os.path.exists(path):
    print(f"找不到合并结果: {path}")
    sys.exit(1)

data = json.load(open(path, encoding="utf-8"))
merged = data.get("merged", {})
order_no = data.get("order_no", "")
container_no = data.get("container_no", "")
print("=" * 60)
print(f"佰信合并填值: 工作号={order_no} 柜号={container_no}")
print("合并字段: " + ", ".join(f"{k}={v}" for k, v in merged.items()))
print("=" * 60)

pid = find_pid()
if not pid:
    print("未找到佰信进程"); sys.exit(1)
print(f"佰信 PID: {pid}")
app = Application(backend="win32").connect(process=pid)
pop, moved = ensure_popup_position(app)
if moved:
    print("⚠️ 弹窗位置偏移，已移回默认")
if not pop:
    print(f"\n弹窗未打开，调用 {RERUN} {order_no} 打开...")
    subprocess.run([sys.executable, RERUN, order_no], timeout=300)
    pid = find_pid()
    if not pid:
        print("佰信进程消失"); sys.exit(1)
    app = Application(backend="win32").connect(process=pid)
    pop, moved = ensure_popup_position(app)
    if moved:
        print("⚠️ 弹窗位置偏移，已移回默认")
if not pop:
    print("仍找不到订舱编辑弹窗"); sys.exit(1)

pr = pop.rectangle()
print(f"弹窗: ({pr.left},{pr.top})-({pr.right},{pr.bottom})  标题='{pop.window_text()}'")
u = ctypes.windll.user32

# ---- 先等数据加载完成，再强制校验单号（防止填错单）----
wait_data_load(pop)
print(f"\n[校验] 确认弹窗单号 = {order_no} ...")
if order_no and not verify_popup_order(pop, order_no):
    print("❌ 弹窗单号与目标不符，已中止（防止填错单）")
    sys.exit(1)
print("✅ 弹窗单号确认无误")

foreground()

ROW_Y = detect_row_y() or ROW_Y_DEFAULT
print(f"网格首行 y = {ROW_Y}")

# ---- 表单填值 ----
print("\n==== 表单字段 ====")
for label, _key, src, pos, ftype in FORM_FIELDS:
    v = merged.get(src)
    if not has_value(v):
        print(f"  [跳过] {label}: 无合并值")
        continue
    fill_form(pos[0], pos[1], v, f"表单-{label}", is_date=(ftype == "date"))

# ---- 网格填值 ----
print("\n==== 网格 ====")
if detect_row_y() is None:
    print("网格为空，先加行...")
    add_row()
    ROW_Y = detect_row_y() or ROW_Y_DEFAULT
    print(f"加行后首行 y = {ROW_Y}")
    time.sleep(0.5)

for label, src, x in GRID_VISIBLE:
    v = merged.get(src)
    if not has_value(v):
        print(f"  [跳过] {label}列: 无合并值")
        continue
    fill_cell(x, v, f"{label}列")

for label, src in GRID_SCROLL:
    v = merged.get(src)
    if not has_value(v):
        print(f"  [跳过] {label}列: 无合并值")
        continue
    x = find_col_x([label])
    if x is None:
        print(f"  [警告] 找不到 '{label}' 列，跳过")
        continue
    fill_cell(x, v, f"{label}列")

print("\n" + "=" * 60)
print("✅ 填值完成（未保存）。请人工核对弹窗内容后手动保存。")
print("=" * 60)
