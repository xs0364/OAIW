#!/usr/bin/env python3
"""
蛇口港ePort 自动化登录 - 同步版（sync_playwright）
直接集成进 shekou.py 作为登录 + 验证码识别标准流程

关键逻辑：
✔ 拦截API获取originalImageBase64 + wordList
✔ ddddocr检测文字位置 → 模糊匹配目标字
✔ 坐标映射：图片像素 → 页面坐标（处理缩放）
✔ 失败自动刷新重试
"""
from __future__ import annotations

import base64
import json
import logging
import re
import time

from playwright.sync_api import sync_playwright

from backend.rpa.clickword_solver import solve_clickword

log = logging.getLogger(__name__)

USERNAME = "Seabayop"
PASSWORD = "Seabayop3101"
TARGET_URL = "https://wk-eport.cmp1872.com/#/main/home"
MAX_RETRIES = 30


class EportLogin:
    """蛇口港ePort 自动化登录（同步版）"""

    def __init__(self, headless: bool = False):
        self._p = None
        self.browser = None
        self.context = None
        self.page = None
        self._captcha_api_data = None
        self._check_result = None
        self.headless = headless

    def start(self):
        self._p = sync_playwright().start()
        self.browser = self._p.chromium.launch(
            headless=self.headless, slow_mo=20,
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
        )
        self.context = self.browser.new_context(
            viewport={'width': 1400, 'height': 900},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        self.page = self.context.new_page()
        self.page.on('response', self._on_response)
        log.info("浏览器启动完成")
        return self

    def close(self):
        if self.browser:
            self.browser.close()
        if self._p:
            self._p.stop()

    # ---- 事件回调 ----
    def _on_response(self, response):
        url = response.url
        if '/api/v1/auth/captcha/get/v2' in url:
            try:
                d = response.json()
                if d.get('repCode') == '0000':
                    self._captcha_api_data = d['repData']
                    wl = d['repData'].get('wordList', [])
                    log.info(f"✓ 验证码API捕获 | wordList: {wl}")
            except Exception:
                pass
        if '/api/v1/auth/captcha/check' in url:
            try:
                self._check_result = response.json()
                log.info(f"✓ 验证码检查结果")
            except Exception:
                pass

    # ---- 工具方法 ----
    def _frame(self):
        for f in self.page.frames:
            if 'eport.cmp1872.com/login' in f.url:
                return f
        return None

    # ---- 登录流程 ----
    def fill_login(self):
        f = self._frame()
        f.fill('#username', USERNAME)
        f.fill('input[type="password"]', PASSWORD)
        chk = f.query_selector('.tab-one .ivu-checkbox')
        if chk:
            chk.click()
        log.info("✓ 登录信息已填写")
        return f

    def click_login_btn(self, f) -> bool:
        btn = f.query_selector('button.ivu-btn-primary')
        if not btn:
            return False
        btn.click()
        self.page.wait_for_timeout(2000)
        mask = f.query_selector('.mask')
        return mask is not None

    def refresh(self, f) -> bool:
        btn = f.query_selector('.verifybox-refresh')
        if btn:
            btn.click()
            self.page.wait_for_timeout(3000)
            log.info("🔄 验证码已刷新")
            return True
        return False

    def get_captcha(self, f) -> dict:
        """获取验证码数据，优先API拦截，退化到DOM截图"""
        data = {}

        # 从API拦截获取
        if self._captcha_api_data:
            data = dict(self._captcha_api_data)
            self._captcha_api_data = None

        # 图片兜底
        if 'originalImageBase64' not in data:
            src = f.evaluate("""
                () => {
                    const el = document.querySelector('.verify-img-out img');
                    return el ? el.src : null;
                }
            """)
            if src:
                m = re.match(r'data:image/\w+;base64,(.+)', src)
                if m:
                    data['originalImageBase64'] = m.group(1)

        # 目标字兜底
        if not data.get('wordList'):
            prompt = f.evaluate("""
                () => {
                    const el = document.querySelector('.verifybox-bottom');
                    if (!el) return '';
                    const m = el.textContent.match(/【(.+?)】/);
                    return m ? m[1] : el.textContent.trim();
                }
            """)
            if '、' in prompt:
                data['wordList'] = [w.strip() for w in re.split(r'[、，,]', prompt) if w.strip()]

        return data

    def click_words(self, f, positions_px) -> bool:
        """
        在验证码图片上按顺序点击坐标
        使用 locator.click(position={'x': px, 'y': py})
        """
        img_info = f.evaluate("""
            () => {
                const img = document.querySelector('.verify-img-out img');
                if (!img) return null;
                return {
                    cssW: img.getBoundingClientRect().width,
                    cssH: img.getBoundingClientRect().height,
                    natW: img.naturalWidth,
                    natH: img.naturalHeight
                };
            }
        """)
        if not img_info:
            log.error("✗ 未找到验证码图片元素")
            return False

        scale_x = img_info['cssW'] / max(img_info['natW'], 1)
        scale_y = img_info['cssH'] / max(img_info['natH'], 1)

        img_locator = f.locator('.verify-img-out img')

        for i, (px, py) in enumerate(positions_px):
            css_x = px * scale_x
            css_y = py * scale_y
            jx = css_x + (i * 7 + 3) % 5 - 2
            jy = css_y + (i * 11 + 1) % 5 - 2
            log.info(f"  点击{i+1}: ({px},{py}) → CSS({css_x:.0f},{css_y:.0f})")
            img_locator.click(
                position={'x': jx, 'y': jy},
                delay=50 + 30 * i,
                force=True
            )
            self.page.wait_for_timeout(150 + 50 * i)

        self.page.wait_for_timeout(2000)
        return True

    def check_result(self, f):
        """检查验证码是否通过，返回 True/False/None"""
        mask = f.query_selector('.mask')
        if not mask:
            return True
        disp = mask.evaluate('el => getComputedStyle(el).display')
        if disp == 'none':
            return True
        # 错误提示
        err = f.evaluate("""
            () => {
                const m = document.querySelector('.ivu-message-notice');
                return m ? m.textContent.trim().slice(0, 80) : '';
            }
        """)
        if err and ('失败' in err or '错误' in err):
            log.warning(f"  ! 提示: {err}")
            return False
        return None

    def run(self) -> bool:
        log.info("=" * 60)
        log.info("蛇口港ePort 自动化登录")
        log.info(f"账号: {USERNAME}")
        log.info("=" * 60)

        self.start()
        self.page.goto(TARGET_URL, wait_until='networkidle', timeout=30000)
        self.page.wait_for_timeout(4000)

        f = self._frame()
        if not f:
            log.error("✗ 未找到登录iframe")
            self.close()
            return False

        self.fill_login()

        for attempt in range(1, MAX_RETRIES + 1):
            log.info(f"\n{'─'*40}\n尝试 [{attempt}/{MAX_RETRIES}]\n{'─'*40}")

            f = self._frame()
            if not f:
                self.close()
                return False

            # 检查验证码遮罩
            existing_mask = f.query_selector('.mask')
            if existing_mask:
                captcha_visible = existing_mask.evaluate('el => getComputedStyle(el).display') != 'none'
            else:
                captcha_visible = False

            if not captcha_visible:
                shown = self.click_login_btn(f)
                if not shown:
                    r = self.check_result(f)
                    if r is True:
                        log.info("✓ 已登录！")
                        self.close()
                        return True
                    continue
            else:
                log.info("验证码遮罩已存在，直接处理")

            cd = self.get_captcha(f)
            img = cd.get('originalImageBase64', '')
            words = cd.get('wordList', [])

            if not img:
                log.warning("✗ 无图片")
                self.refresh(f)
                continue
            if not words:
                log.warning("✗ 无目标字")
                self.refresh(f)
                continue

            log.info(f"  目标: {words} | 图片: {len(img)//1024}KB")

            pts = solve_clickword(img, words)
            if not pts:
                log.warning("✗ OCR失败")
                self.refresh(f)
                continue

            self.click_words(f, pts)
            self.page.wait_for_timeout(1500)

            r = self.check_result(f)
            if r is True:
                log.info("\n" + "✓" * 50)
                log.info("✓✓✓ 验证通过！登录成功！✓✓✓")
                log.info("✓" * 50)
                self.page.wait_for_timeout(4000)
                self.close()
                return True
            elif r is False:
                log.warning("✗ 验证码错误，重试")
                self.refresh(f)
            else:
                self.page.wait_for_timeout(3000)
                r2 = self.check_result(f)
                if r2 is True:
                    log.info("✓✓✓ 登录成功！✓✓✓")
                    self.close()
                    return True
                log.warning("? 不确定，刷新重试")
                self.refresh(f)

        log.error("✗ 登录失败：已达最大重试次数")
        self.close()
        return False


def run_login(headless: bool = False) -> dict:
    """
    一键登录蛇口港，返回登录结果

    Returns:
        {"success": bool, "error": str, "page": page or None}
        成功时 page 可用（浏览器保持打开），失败时 page=None
    """
    bot = EportLogin(headless=headless)
    try:
        ok = bot.run()
        if ok:
            return {"success": True, "error": "", "page": bot.page, "browser": bot.browser}
        return {"success": False, "error": "登录失败：已达最大重试次数", "page": None, "browser": None}
    except Exception as e:
        import traceback
        return {"success": False, "error": f"{type(e).__name__}: {e}\n{traceback.format_exc()}", "page": None, "browser": None}
