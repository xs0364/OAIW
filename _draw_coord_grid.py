# -*- coding: utf-8 -*-
"""
在佰信截图上绘制高精度二维坐标系网格
方便用户肉眼读取每个交互元素的坐标
"""
import sys, time, ctypes, win32gui, win32process, win32con
sys.stdout.reconfigure(encoding='utf-8')

import pyautogui, cv2, numpy as np
pyautogui.FAILSAFE = False

PID = 5804

# === 恢复窗口到正常大小 ===
hwnd = None
def cb(h, _):
    global hwnd
    try:
        if win32gui.IsWindowVisible(h):
            _, pid = win32process.GetWindowThreadProcessId(h)
            if pid == PID and win32gui.GetClassName(h) == 'TfmMainD':
                hwnd = h
    except: pass
    return True
win32gui.EnumWindows(cb, None)

if hwnd:
    r = win32gui.GetWindowRect(hwnd)
    if r[0] < -100:  # minimized
        print("Restoring window...")
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        time.sleep(1)
    win32gui.SetForegroundWindow(hwnd)
    time.sleep(0.5)

# === 全屏截图 ===
print("Taking screenshot...")
full = pyautogui.screenshot()
img = cv2.cvtColor(np.array(full), cv2.COLOR_RGB2BGR)
h, w = img.shape[:2]
print(f"Screen: {w}x{h}")

# === 绘制坐标网格 ===
GRID_STEP = 50  # 50px 一格
GRID_SUB = 10   # 10px 子格

overlay = img.copy()

# 半透明浅灰背景绘制坐标文字
alpha = 0.85
overlay = cv2.addWeighted(overlay, alpha, np.zeros_like(overlay), 0, 0)

# 绘制子网格线（浅灰色细线）
for x in range(0, w, GRID_SUB):
    if x % GRID_STEP != 0:
        cv2.line(overlay, (x, 0), (x, h), (200, 200, 200), 1)

for y in range(0, h, GRID_SUB):
    if y % GRID_STEP != 0:
        cv2.line(overlay, (0, y), (w, y), (200, 200, 200), 1)

# 绘制主网格线（深灰色稍粗）
for x in range(0, w, GRID_STEP):
    cv2.line(overlay, (x, 0), (x, h), (100, 100, 100), 2)
    cv2.putText(overlay, str(x), (x+2, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)

for y in range(0, h, GRID_STEP):
    cv2.line(overlay, (0, y), (w, y), (100, 100, 100), 2)
    cv2.putText(overlay, str(y), (2, y-3 if y>15 else y+12), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)

# 坐标轴标注
cv2.putText(overlay, "X", (w-30, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
cv2.putText(overlay, "Y", (5, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

# 混合回原图
result = cv2.addWeighted(img, 0.4, overlay, 0.6, 0)

# 保存
path = r"D:\OAIW\_baixin_screenshots\coord_grid.png"
cv2.imwrite(path, result)
print(f"Saved: {path}")

# === 也截一张不带网格的原始图做对照 ===
raw_path = r"D:\OAIW\_baixin_screenshots\coord_raw.png"
cv2.imwrite(raw_path, cv2.cvtColor(np.array(full), cv2.COLOR_RGB2BGR))
print(f"Saved: {raw_path}")

print("\n================= 坐标网格已生成 =================")
print(f"网格精度: {GRID_STEP}px 主格 / {GRID_SUB}px 子格")
print(f"截图已保存到: {path}")
print(f"原始截图: {raw_path}")
print("================================================")
