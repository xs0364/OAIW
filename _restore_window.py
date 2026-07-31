# -*- coding: utf-8 -*-
"""Restore BestLOGFW main window from minimized state"""
import sys, time, ctypes, win32gui, win32process, win32con
sys.stdout.reconfigure(encoding='utf-8')

PID = 5804

# Find the main window
hwnd = None
def cb(h, _):
    global hwnd
    try:
        if win32gui.IsWindowVisible(h):
            _, pid = win32process.GetWindowThreadProcessId(h)
            if pid == PID and 'TfmMainD' == win32gui.GetClassName(h):
                hwnd = h
    except: pass
    return True

win32gui.EnumWindows(cb, None)

if not hwnd:
    print("TfmMainD not found!")
    sys.exit(1)

r = win32gui.GetWindowRect(hwnd)
print(f"Before: ({r[0]},{r[1]})-({r[2]},{r[3]}) {r[2]-r[0]}x{r[3]-r[1]}")

# Check window placement
wp = win32gui.GetWindowPlacement(hwnd)
print(f"Placement: showCmd={wp[3]}, flags={wp[2]}")
# showCmd: 1=normal, 2=minimized, 3=maximized

if wp[3] == 2:  # minimized
    print("Window is minimized. Restoring...")
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    time.sleep(1)
    win32gui.SetForegroundWindow(hwnd)
    time.sleep(1)
    r = win32gui.GetWindowRect(hwnd)
    print(f"After: ({r[0]},{r[1]})-({r[2]},{r[3]}) {r[2]-r[0]}x{r[3]-r[1]}")
    wp2 = win32gui.GetWindowPlacement(hwnd)
    print(f"Placement: showCmd={wp2[3]}")
else:
    print("Window is not minimized, trying SW_SHOWNORMAL anyway...")
    win32gui.ShowWindow(hwnd, win32con.SW_SHOWNORMAL)
    time.sleep(1)
    win32gui.SetForegroundWindow(hwnd)
    time.sleep(1)
    r = win32gui.GetWindowRect(hwnd)
    print(f"After: ({r[0]},{r[1]})-({r[2]},{r[3]}) {r[2]-r[0]}x{r[3]-r[1]}")

print(f"\nHandle: 0x{hwnd:08x}")
print("Done - window restored")
