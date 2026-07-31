# -*- coding: utf-8 -*-
"""
佰信动态坐标标尺 v5
====================
- 简化网格创建，去掉了可能导致不显示的复杂样式
- 网格用 tkinter 标准透明色（transparentcolor）而非 alpha
- 所有操作都有日志输出到文件 debug_coord.log
"""
import sys, time, os, ctypes, win32gui, win32process, win32con

# 日志
log_file = r"D:\OAIW\_debug_coord.log"
def log(msg):
    t = time.strftime("%H:%M:%S")
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write("[%s] %s\n" % (t, msg))
    print(msg)

try:
    import tkinter as tk
except ImportError:
    log("❌ 需要 tkinter"); sys.exit(1)

PID = 5804

class BaixinCoord:
    def __init__(self):
        log("="*50)
        log("佰信坐标标尺 v5 启动")
        log("="*50)

        self.root = tk.Tk()
        self.root.title("佰信坐标标尺")
        self.root.attributes('-topmost', True)
        self.root.configure(bg='#1a1a2e')

        self.baixin_hwnd = self._find_baixin()
        if not self.baixin_hwnd:
            log("❌ 未找到佰信主窗口")
            sys.exit(1)

        self._update_rect()
        log("✅ 佰信窗口: (%d,%d)-(%d,%d) %dx%d hwnd=0x%08x" % (
            self.wx, self.wy, self.wx2, self.wy2, self.ww, self.wh, self.baixin_hwnd))

        self.grid_visible = False
        self.grid_win = None

        self._build_ui()
        self.root.after(200, self._track_window)
        self.root.after(50, self._poll_mouse)
        self.root.protocol("WM_DELETE_WINDOW", self.quit)

        # Ctrl+G 快捷键
        self.root.bind('<Control-g>', lambda e: self._toggle_grid())
        self.root.bind('<Control-G>', lambda e: self._toggle_grid())

    def _find_baixin(self):
        hwnd = None
        def cb(h, _):
            nonlocal hwnd
            try:
                if win32gui.IsWindowVisible(h):
                    _, pid = win32process.GetWindowThreadProcessId(h)
                    if pid == PID and win32gui.GetClassName(h) == 'TfmMainD':
                        hwnd = h
            except: pass
            return True
        win32gui.EnumWindows(cb, None)
        return hwnd

    def _update_rect(self):
        try:
            r = win32gui.GetWindowRect(self.baixin_hwnd)
            self.wx, self.wy, self.wx2, self.wy2 = r
            self.ww, self.wh = r[2]-r[0], r[3]-r[1]
            return True
        except:
            return False

    def _build_ui(self):
        # 面板放在佰信窗口右侧，但如果超出屏幕则放在左侧
        screen_w = self.root.winfo_screenwidth()
        px = self.wx2 + 5
        if px + 320 > screen_w:
            px = self.wx - 325  # 放在窗口左侧
        if px < 0:
            px = 5  # 都不行就放左上角
        py = max(0, min(self.wy + 80, self.root.winfo_screenheight() - 300))
        self.root.geometry("320x280+%d+%d" % (px, py))
        self.root.resizable(False, False)
        self.root.minsize(300, 250)
        self.root.update()

        log("信息面板: +%d+%d 320x280" % (px, py))

        f = ('Consolas', 10)
        fb = ('Consolas', 10, 'bold')

        # 标题
        tf = tk.Frame(self.root, bg='#1a1a2e')
        tf.pack(fill='x', padx=10, pady=(8,2))
        tk.Label(tf, text="■ 佰信坐标标尺", fg='#00ff88', bg='#1a1a2e',
                font=('Consolas', 11, 'bold')).pack(side='left')
        tk.Label(tf, text="v5", fg='#555', bg='#1a1a2e',
                font=('Consolas', 8)).pack(side='right')

        tk.Frame(self.root, bg='#333', height=1).pack(fill='x', padx=10)

        # 窗口
        f1 = tk.Frame(self.root, bg='#1a1a2e')
        f1.pack(fill='x', padx=10, pady=2)
        tk.Label(f1, text="窗口:", fg='#888', bg='#1a1a2e', font=f).pack(side='left')
        self.v_winpos = tk.StringVar()
        tk.Label(f1, textvariable=self.v_winpos, fg='#ffcc00', bg='#1a1a2e',
                font=fb).pack(side='left', padx=5)
        f2 = tk.Frame(self.root, bg='#1a1a2e')
        f2.pack(fill='x', padx=10, pady=1)
        self.v_winsize = tk.StringVar()
        tk.Label(f2, textvariable=self.v_winsize, fg='#ffcc00', bg='#1a1a2e',
                font=fb).pack(anchor='w')
        tk.Frame(self.root, bg='#ff6600', height=1).pack(fill='x', padx=10, pady=4)

        # 坐标
        f3 = tk.Frame(self.root, bg='#1a1a2e')
        f3.pack(fill='x', padx=10, pady=2)
        tk.Label(f3, text="鼠标 → 绝对坐标:", fg='#888', bg='#1a1a2e', font=f).pack(anchor='w')
        self.v_abs = tk.StringVar(value="等待鼠标移动...")
        tk.Label(f3, textvariable=self.v_abs, fg='#00ff00', bg='#1a1a2e',
                font=('Consolas', 13, 'bold')).pack(anchor='w')

        f4 = tk.Frame(self.root, bg='#1a1a2e')
        f4.pack(fill='x', padx=10, pady=1)
        tk.Label(f4, text="相对偏移:", fg='#888', bg='#1a1a2e', font=f).pack(anchor='w')
        self.v_rel = tk.StringVar(value="等待鼠标移动...")
        tk.Label(f4, textvariable=self.v_rel, fg='#00ccff', bg='#1a1a2e',
                font=('Consolas', 13, 'bold')).pack(anchor='w')
        tk.Frame(self.root, bg='#ff6600', height=1).pack(fill='x', padx=10, pady=4)

        # 网格按钮
        self.btn_grid = tk.Button(self.root, text="🔲 显示网格",
                                  command=self._toggle_grid,
                                  bg='#0f3460', fg='#00ff88',
                                  activebackground='#1a5276',
                                  font=('Consolas', 11, 'bold'),
                                  relief='raised', bd=2, pady=5)
        self.btn_grid.pack(fill='x', padx=20, pady=6)

        tk.Label(self.root, text="Ctrl+G 开关网格 | 右键退出",
                fg='#555', bg='#1a1a2e', font=('Consolas', 8)).pack(side='bottom', pady=2)

        self._update_info()
        self.root.bind('<Button-3>', self._show_menu)

    def _show_menu(self, e):
        m = tk.Menu(self.root, tearoff=0, bg='#333', fg='white',
                   activebackground='#555', font=('Consolas', 9))
        if self.grid_visible:
            m.add_command(label="隐藏网格", command=self._toggle_grid)
        else:
            m.add_command(label="显示网格", command=self._toggle_grid)
        m.add_separator()
        m.add_command(label="退出", command=self.quit)
        m.tk_popup(e.x_root, e.y_root)

    def _update_info(self):
        self.v_winpos.set("(%d,%d)-(%d,%d)" % (self.wx, self.wy, self.wx2, self.wy2))
        self.v_winsize.set("尺寸: %d x %d" % (self.ww, self.wh))

    # ========== 网格 ==========
    def _toggle_grid(self):
        if self.grid_visible:
            self._hide_grid()
        else:
            self._show_grid()

    def _show_grid(self):
        log("显示网格...")
        if self.grid_win:
            try: self.grid_win.destroy()
            except: pass
        self.grid_win = self._create_grid()
        if self.grid_win:
            self.grid_visible = True
            self.btn_grid.config(text="✅ 隐藏网格 (Ctrl+G)", fg='#ff6600')
            log("✅ 网格已显示")
        else:
            log("❌ 网格创建失败")

    def _hide_grid(self):
        if self.grid_win:
            try: self.grid_win.withdraw()
            except: pass
        self.grid_visible = False
        self.btn_grid.config(text="🔲 显示网格 (Ctrl+G)", fg='#00ff88')
        log("网格已隐藏")

    def _create_grid(self):
        """创建网格覆盖窗口"""
        try:
            win = tk.Toplevel(self.root)
            win.title("BaixinGridOverlay")
            win.overrideredirect(True)
            win.attributes('-topmost', True)

            # 半透明网格 40% 可见度（之前太透明看不见）
            win.attributes('-alpha', 0.40)

            # 必须先设置 geometry 再获取 HWND
            win.geometry("%dx%d+%d+%d" % (self.ww, self.wh, self.wx, self.wy))
            win.configure(bg='#000000')

            # 强制更新窗口
            win.update_idletasks()
            win.update()

            # ===== 获取 HWND 并设置扩展样式 =====
            try:
                # 方法1: winfo_id()
                hwnd = win.winfo_id()
                log("  winfo_id() = 0x%08x" % hwnd)

                # 设置 WS_EX_TRANSPARENT 和 WS_EX_NOACTIVATE
                # 注意：不要重复设置 WS_EX_LAYERED（tkinter 已通过 -alpha 设置）
                ex = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                log("  当前 EX_STYLE: 0x%08x" % ex)

                # WS_EX_TRANSPARENT (0x20) — 鼠标穿透
                # WS_EX_NOACTIVATE (0x08000000) — 不激活
                # WS_EX_LAYERED (0x80000) — 透明层（tkinter 已设）
                new_ex = ex | win32con.WS_EX_TRANSPARENT | win32con.WS_EX_NOACTIVATE
                win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, new_ex)

                # 验证
                verify = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                log("  设置后 EX_STYLE: 0x%08x (TRANSPARENT=%s)" % (
                    verify, "✅" if (verify & 0x20) else "❌"))
            except Exception as e:
                log("  EX_STYLE 设置失败: %s" % e)

            # ===== 画网格 =====
            c = tk.Canvas(win, width=self.ww, height=self.wh,
                         bg='#000000', highlightthickness=0)
            c.pack()

            gs = 50
            gss = 10

            # 子格
            for x in range(0, self.ww, gss):
                if x % gs != 0:
                    c.create_line(x, 0, x, self.wh, fill='#666666', width=1)
            for y in range(0, self.wh, gss):
                if y % gs != 0:
                    c.create_line(0, y, self.ww, y, fill='#666666', width=1)

            # 主格 + 数字
            for x in range(0, self.ww, gs):
                c.create_line(x, 0, x, self.wh, fill='#00ff88', width=2)
                c.create_text(x+3, 12, text=str(self.wx+x), anchor='w',
                             fill='#ff4444', font=('Consolas', 8, 'bold'))
            for y in range(0, self.wh, gs):
                c.create_line(0, y, self.ww, y, fill='#00ff88', width=2)
                c.create_text(3, y+2, text=str(self.wy+y), anchor='w',
                             fill='#ff4444', font=('Consolas', 8, 'bold'))

            # 中心
            cx, cy = self.ww//2, self.wh//2
            c.create_line(cx-15, cy, cx+15, cy, fill='#ff00ff', width=2)
            c.create_line(cx, cy-15, cx, cy+15, fill='#ff00ff', width=2)
            c.create_text(cx, cy-20, text="(%d,%d)" % (self.wx+cx, self.wy+cy),
                         fill='#ffff00', font=('Consolas', 9, 'bold'))
            c.create_text(5, 3, text="左上(%d,%d)" % (self.wx, self.wy),
                         anchor='nw', fill='#ffff00', font=('Consolas', 8, 'bold'))
            c.create_text(self.ww-30, 15, text="X→", fill='#00ff88',
                         font=('Consolas', 11, 'bold'))
            c.create_text(15, self.wh-15, text="Y↓", fill='#00ff88',
                         font=('Consolas', 11, 'bold'))

            # Ctrl+G also works on grid
            win.bind('<Control-g>', lambda e: self._toggle_grid())
            win.bind('<Control-G>', lambda e: self._toggle_grid())

            # 强制置前
            win.lift()
            win.deiconify()

            log("  网格窗口已创建: %dx%d+%d+%d" % (self.ww, self.wh, self.wx, self.wy))
            return win

        except Exception as e:
            log("  ❌ 网格创建异常: %s" % e)
            import traceback
            log("  " + traceback.format_exc())
            return None

    # ========== 跟踪 ==========
    def _track_window(self):
        try:
            r = win32gui.GetWindowRect(self.baixin_hwnd)
            if (r[0], r[1], r[2], r[3]) != (self.wx, self.wy, self.wx2, self.wy2):
                self.wx, self.wy, self.wx2, self.wy2 = r
                self.ww, self.wh = r[2]-r[0], r[3]-r[1]
                self._update_info()
                if self.grid_win and self.grid_visible:
                    try:
                        self.grid_win.geometry("%dx%d+%d+%d" % (self.ww, self.wh, self.wx, self.wy))
                    except: pass
        except: pass
        self.root.after(200, self._track_window)

    def _poll_mouse(self):
        try:
            mx, my = win32gui.GetCursorPos()
            self.v_abs.set("x= %-4d   y= %-4d" % (mx, my))
            dx = mx - self.wx
            dy = my - self.wy
            self.v_rel.set("dx= %-4d   dy= %-4d" % (dx, dy))
        except: pass
        self.root.after(50, self._poll_mouse)

    def run(self):
        log("✅ 佰信坐标标尺 v5 启动完成")
        log("Ctrl+G = 开关网格 | 右键 = 退出")
        self.root.mainloop()

    def quit(self):
        try:
            if self.grid_win: self.grid_win.destroy()
        except: pass
        self.root.destroy()
        log("已退出")
        sys.exit(0)

if __name__ == '__main__':
    BaixinCoord().run()
