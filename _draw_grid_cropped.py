# -*- coding: utf-8 -*-
"""
截取佰信窗口区域 + 坐标网格叠加
让用户看着图片告诉我每个元素的坐标
"""
import sys, time, ctypes, win32gui, win32process, win32con
sys.stdout.reconfigure(encoding='utf-8')

import pyautogui, cv2, numpy as np
pyautogui.FAILSAFE = False

PID = 5804

# === 恢复窗口 ===
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
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    time.sleep(0.5)
    win32gui.SetForegroundWindow(hwnd)
    time.sleep(0.5)
    r = win32gui.GetWindowRect(hwnd)
    print(f"Window: ({r[0]},{r[1]})-({r[2]},{r[3]}) {r[2]-r[0]}x{r[3]-r[1]}")
else:
    print("Window not found!")
    sys.exit(1)

# === 只截窗口区域 ===
# 加一点 padding 确保完整
pad = 20
left = max(0, r[0] - pad)
top = max(0, r[1] - pad)
right = min(1920, r[2] + pad)
bottom = min(1080, r[3] + pad)

full = pyautogui.screenshot(region=(left, top, right-left, bottom-top))
img = cv2.cvtColor(np.array(full), cv2.COLOR_RGB2BGR)
h, w = img.shape[:2]

# === 绘制坐标网格 ===
GRID_MAIN = 50
GRID_SUB = 10

# 拷贝原图用于网格
grid = img.copy()

# 绘制子网格（淡灰色细线，0.5px opacity effect via thinner lines）
for x in range(0, w, GRID_SUB):
    if x % GRID_MAIN != 0:
        cv2.line(grid, (x, 0), (x, h), (180, 180, 180), 1)

for y in range(0, h, GRID_SUB):
    if y % GRID_MAIN != 0:
        cv2.line(grid, (0, y), (w, y), (180, 180, 180), 1)

# 绘制主网格线（深灰色粗线）
for x in range(0, w, GRID_MAIN):
    cv2.line(grid, (x, 0), (x, h), (80, 80, 80), 2)
    px = left + x
    cv2.putText(grid, str(px), (x+3, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 255), 1)

for y in range(0, h, GRID_MAIN):
    cv2.line(grid, (0, y), (w, y), (80, 80, 80), 2)
    py = top + y
    cv2.putText(grid, str(py), (3, y-3 if y>15 else y+14), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 255), 1)

# 方向箭头 X→ Y↓
cv2.putText(grid, "X\xe2\x86\x92", (w-50, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
cv2.putText(grid, "Y\xe2\x86\x93", (5, h-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

# 混合：60% 原图 + 40% 网格
result = cv2.addWeighted(img, 0.55, grid, 0.45, 0)

# 保存
out = r"D:\OAIW\_baixin_screenshots\coord_window_grid.png"
cv2.imwrite(out, result)
print(f"\nGrid overlay saved: {out}")
print(f"Grid origin: window top-left is at screen position ({left},{top})")
print(f"Coordinate numbers on the grid = screen absolute pixels")

# 也存一份窗口原图
raw_out = r"D:\OAIW\_baixin_screenshots\coord_window_raw.png"
cv2.imwrite(raw_out, img)
print(f"Raw window shot: {raw_out}")

# === 输出窗口区域坐标参考 ===
print(f"\n{'='*60}")
print("窗口坐标参考（屏幕绝对像素）")
print(f"{'='*60}")
print(f"窗口左上角: ({r[0]}, {r[1]})")
print(f"窗口右下角: ({r[2]}, {r[3]})")
print(f"窗口尺寸: {r[2]-r[0]} x {r[3]-r[1]}")
print(f"工具栏区域 y≈{r[1]+23} ~ {r[1]+45}")
print(f"主菜单按钮行 y≈{r[1]+56}")
print(f"\n截图文件: {out}")
print(f"请用图片查看器打开此文件，然后告诉我各按钮的坐标")
print(f"{'='*60}")
