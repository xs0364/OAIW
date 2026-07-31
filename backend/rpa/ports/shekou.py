# -*- coding: utf-8 -*-
"""
蛇口港 (wk-eport.cmp1872.com / SCCT码头) RPA 驱动 — 集装箱状态查询

正确流程：
1. 访问 eport.cmp1872.com 门户登录（验证码全图OCR + 按提示顺序点击）
2. 进入 wk-eport.cmp1872.com 工作台
3. 打开 container/ 应用 → 点击"单箱查询"快捷链接
4. 修复 iframe src 到 scct-query/danxiangsonumber
5. 填写柜号 → 点击查询
6. 拦截 API JSON 响应 → 返回结构化数据

验证码方案：Gemma4 视觉模型识别文字+坐标 → 按 wordlist 顺序点击（EasyOCR fallback）
"""

from __future__ import annotations

import builtins as _builtins
import json
import logging
import os
import re
import time
from pathlib import Path

from backend.rpa.log_queue import rpa_log as _rpa_log

_orig_print = _builtins.print

def _sanitize(text: str) -> str:
    """去掉GBK编码不支持的字符（emoji等），防止控制台UnicodeEncodeError。"""
    return text.encode('gbk', errors='replace').decode('gbk')

def _rpa_print(*args, **kwargs):
    text = " ".join(str(a) for a in args)
    clean = _sanitize(text)
    _orig_print(clean, **kwargs)
    if clean.strip():
        _rpa_log(clean)
_builtins.print = _rpa_print

import json
import os
import re
import time
from pathlib import Path

from backend.rpa.ports import register

# =============================================================================
# 账号配置
# =============================================================================
SHEKOU_USERNAME = "Seabayop"
SHEKOU_PASSWORD = "Seabayop3101"
AUTH_STATE_PATH = Path(__file__).parent / "sk_auth_state.json"


# =============================================================================
# 驱动主类
# =============================================================================

@register("蛇口港")
class ShekouPort:
    """蛇口港 (SCCT) 集装箱查询驱动。"""

    @staticmethod
    def query_container(page, params: dict) -> dict:
        container_no = params.get("container_no", "").strip().upper()
        booking_no = params.get("booking_no", "").strip()

        if not container_no:
            return {"success": False, "data": "", "error": "请输入集装箱号"}

        try:
            # ===== Step 1: 登录并导航到 container/ 应用 =====
            if not _navigate_to_container(page):
                return {
                    "success": False,
                    "data": "",
                    "error": "蛇口港登录失败（验证码无法通过或账号密码错误）",
                }

            # ===== Step 2: 点击"单箱查询" =====
            _click_quick_link(page)

            # ===== Step 3: 修复 iframe + 填柜查柜 =====
            api_data = _fix_iframe_and_query(page, container_no)

            # ===== Step 4: 解析结果 =====
            return _parse_result(api_data, container_no, booking_no)

        except Exception as e:
            import traceback
            return {
                "success": False,
                "data": "",
                "error": f"EXCEPTION: {type(e).__name__}: {e}\n{traceback.format_exc()}",
            }


# =============================================================================
# 登录 + 导航到 container/
# =============================================================================

def _is_logged_in(page) -> bool:
    """检查页面是否已登录（看页面内容，不看 URL）。"""
    try:
        url = page.url.lower()
        body = (page.evaluate("document.body.innerText.substring(0, 1000)") or "").strip()

        # 还在登录页 → 未登录
        is_login_page = "login" in url or "sso" in url

        # 已登录特征
        has_logged_in_text = any(kw in body for kw in ["退出", "工作台", "个人中心", "首页"])
        has_container_url = "container" in url or "home" in url

        return (not is_login_page) or has_logged_in_text or has_container_url
    except Exception:
        return False


def _navigate_to_container(page) -> bool:
    """
    恢复登录态并导航到 wk-eport container/ 应用。
    """
    context = page.context
    state = _load_auth_state()

    # 1. 先加 cookies
    if state:
        cookies = state.get("cookies", [])
        if cookies:
            print("  📦 加载已有登录态...", flush=True)
            context.add_cookies(cookies)

    # 2. 先访问 SSO 门户页面，恢复 localStorage（含 certificate 自动认证）
    print("  🌐 访问 SSO 门户...", flush=True)
    page.goto(
        "https://eport.cmp1872.com/login?targetSystem=e09311ed99e77617",
        wait_until="domcontentloaded",
        timeout=30000,
    )
    page.wait_for_timeout(2000)

    # 恢复门户页面的 localStorage（含 username + 自动认证信息）
    if state:
        _restore_local_storage(page, state)

    # 等待 SSO 自动认证（_ct cookie + localStorage certificate 可能自动登录）
    page.wait_for_timeout(3000)

    # 检查是否已 SSO 自动登录
    auto_logged_in = _is_logged_in(page)

    # 3. 导航到 container/ 并等待 SPA 渲染
    page.goto(
        "https://wk-eport.cmp1872.com/container/",
        wait_until="domcontentloaded",
        timeout=60000,
    )
    page.wait_for_timeout(3000)

    # 恢复工作台页面的 localStorage
    if state:
        _restore_local_storage(page, state)

    # 4. 检查是否在登录页
    if not _is_logged_in(page):
        if not auto_logged_in:
            # 需要完整登录
            print("  [KEY] 需要登录蛇口港...", flush=True)
            if not _do_login(page):
                return False
        else:
            # SSO 自动登录了但 container/ 没带上 → 等一会儿再检查
            page.wait_for_timeout(5000)
            if not _is_logged_in(page):
                print("  [KEY] cookie 已过期，需要重新登录...", flush=True)
                if not _do_login(page):
                    return False

        # 登录成功后重新导航到 container/
        print("  🚢 重新进入 container/ 应用...", flush=True)
        page.goto(
            "https://wk-eport.cmp1872.com/container/",
            wait_until="domcontentloaded",
            timeout=60000,
        )

    else:
        print("  ✅ 登录态有效，直接进入工作台", flush=True)

    # 等待 SPA 渲染（iframe 懒加载需要时间）
    print("  ⏳ 等待页面渲染...", flush=True)
    page.wait_for_timeout(10000)

    return True


def _restore_local_storage(page, state: dict):
    """恢复 localStorage 到当前页面。"""
    if not state:
        return
    for origin_entry in state.get("origins", []):
        origin = origin_entry.get("origin", "")
        if "wk-eport.cmp1872.com" not in origin and "eport.cmp1872.com" not in origin:
            continue
        for item in origin_entry.get("localStorage", []):
            key = item.get("name", "")
            value = item.get("value", "")
            try:
                page.evaluate(
                    f"localStorage.setItem({json.dumps(key)}, {json.dumps(value)})"
                )
            except Exception:
                pass


def _do_login(page) -> bool:
    """
    执行完整登录流程（含验证码识别）。
    委托 shekou_login.EportLogin 处理，使用 iframe 内验证码点击方案。
    """
    from backend.rpa.ports.shekou_login import EportLogin

    # 迁移到 shekou_login 的完整登录流程
    # shekou_login 走：iframe 内操作 → API 拦截验证码 → locator.click(force=True)
    # 这里需要复用现有的 browser context，不能用 shekou_login 新建浏览器
    # 因此只复用它的验证码识别核心逻辑，保持现有浏览器会话

    print("  [KEY] 开始蛇口港登录流程...", flush=True)

    # 注册 API 响应拦截
    captcha_api_data = {}
    def _on_captcha_response(response):
        url = response.url
        if "/api/v1/auth/captcha/get/v2" in url and response.status == 200:
            try:
                d = response.json()
                if d.get("repCode") == "0000":
                    captcha_api_data["image"] = d["repData"]["originalImageBase64"]
                    captcha_api_data["words"] = d["repData"]["wordList"]
                    print(f"  [API] 验证码捕获 wordList={d['repData']['wordList']}", flush=True)
            except Exception:
                pass
        if "/api/v1/auth/captcha/check" in url:
            try:
                r = response.json()
                print(f"  [API] 验证码检查结果: {r}", flush=True)
            except Exception:
                pass
    page.on("response", _on_captcha_response)

    # 导航到目标页
    page.goto(
        "https://wk-eport.cmp1872.com/#/main/home",
        wait_until="networkidle", timeout=30000,
    )
    page.wait_for_timeout(4000)

    # 找登录 iframe
    def _get_login_frame():
        for f in page.frames:
            if "eport.cmp1872.com/login" in f.url:
                return f
        return None

    f = _get_login_frame()
    if not f:
        print("  [X] 未找到登录 iframe", flush=True)
        return False

    # 填写登录信息
    try:
        f.fill("#username", SHEKOU_USERNAME)
        f.fill('input[type="password"]', SHEKOU_PASSWORD)
    except Exception:
        # 兜底：直接在主页面填
        page.fill('input[type="text"]', SHEKOU_USERNAME)
        page.fill('input[type="password"]', SHEKOU_PASSWORD)

    chk = f.query_selector(".tab-one .ivu-checkbox") if f else None
    if chk:
        chk.click()
    else:
        page.evaluate("""() => {
            for (const cb of document.querySelectorAll('input[type="checkbox"]'))
                if (!cb.checked) { cb.click(); return; }
        }""")

    print("  [OK] 登录信息已填写", flush=True)

    # 循环：触发验证码 → 识别 → 点击 → 校验
    from backend.rpa.clickword_solver import solve_clickword
    MAX_ATTEMPTS = 30

    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"  [{attempt}/{MAX_ATTEMPTS}] 尝试登录...", flush=True)

        f = _get_login_frame()

        # 检查验证码遮罩
        existing_mask = f.query_selector(".mask") if f else None
        if existing_mask:
            captcha_visible = existing_mask.evaluate("el => getComputedStyle(el).display") != "none"
        else:
            captcha_visible = False

        if not captcha_visible:
            # 点登录按钮触发验证码
            login_btn = f.query_selector("button.ivu-btn-primary") if f else None
            if login_btn:
                login_btn.click()
                page.wait_for_timeout(2000)
                mask = f.query_selector(".mask") if f else None
                shown = mask is not None
            else:
                shown = False

            if not shown:
                # 可能已经登录了
                page.wait_for_timeout(1500)
                url_lower = page.url.lower()
                body = page.evaluate("document.body.innerText.substring(0, 500)") or ""
                if "退出" in body or "工作台" in body or "container" in url_lower or "home" in url_lower:
                    print("  [OK] 检测到已登录", flush=True)
                    _save_auth_state(page)
                    return True
                continue

        # 获取验证码数据
        cd = {}
        if captcha_api_data:
            cd = dict(captcha_api_data)

        if "image" not in cd or not cd.get("image"):
            if f:
                src = f.evaluate("""
                    () => {
                        const el = document.querySelector('.verify-img-out img');
                        return el ? el.src : null;
                    }
                """)
            else:
                src = page.evaluate("""
                    () => {
                        const el = document.querySelector('.verify-img-out img');
                        return el ? el.src : null;
                    }
                """)
            if src:
                m = re.match(r"data:image/\w+;base64,(.+)", src)
                if m:
                    cd["image"] = m.group(1)

        if "words" not in cd or not cd.get("words"):
            # 首先从 API 拦截的 captcha_api_data 里再找
            if not cd.get("words"):
                cd["words"] = captcha_api_data.get("words", [])
            # 兜底：从页面提取
            if not cd.get("words"):
                prompt = (f or page).evaluate("""
                    () => {
                        const el = document.querySelector('.verifybox-bottom, .verify-tip, [class*=tip], [class*=prompt]');
                        if (!el) return '';
                        const m = el.textContent.match(/【(.+?)】/);
                        return m ? m[1] : el.textContent.trim();
                    }
                """)
                if "、" in prompt:
                    cd["words"] = [w.strip() for w in re.split(r"[、，,]", prompt) if w.strip()]

        # 清理已消费的 API 数据（避免下次重复使用旧的）
        captcha_api_data.clear()

        img_b64 = cd.get("image", "")
        words = cd.get("words", [])

        if not img_b64:
            print("  [X] 无验证码图片", flush=True)
            if f:
                refresh_btn = f.query_selector(".verifybox-refresh")
                if refresh_btn:
                    refresh_btn.click()
                    page.wait_for_timeout(3000)
            continue
        if not words:
            print("  [X] 无目标字", flush=True)
            continue

        print(f"  目标字: {words}", flush=True)

        pts = solve_clickword(img_b64, words)
        if not pts:
            print("  [X] OCR识别失败", flush=True)
            if f:
                refresh_btn = f.query_selector(".verifybox-refresh")
                if refresh_btn:
                    refresh_btn.click()
                    page.wait_for_timeout(3000)
            continue

        # 在验证码图片上按顺序点击
        frame_to_use = f if f else page
        img_info = frame_to_use.evaluate("""
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
            print("  [X] 未找到验证码图片元素", flush=True)
            continue

        scale_x = img_info["cssW"] / max(img_info["natW"], 1)
        scale_y = img_info["cssH"] / max(img_info["natH"], 1)
        img_locator = frame_to_use.locator(".verify-img-out img")

        for i, (px, py) in enumerate(pts):
            css_x = px * scale_x
            css_y = py * scale_y
            jx = css_x + (i * 7 + 3) % 5 - 2
            jy = css_y + (i * 11 + 1) % 5 - 2
            print(f"  点击{i+1}: ({px},{py}) → CSS({css_x:.0f},{css_y:.0f})", flush=True)
            img_locator.click(position={"x": jx, "y": jy}, delay=50 + 30 * i, force=True)
            page.wait_for_timeout(150 + 50 * i)

        page.wait_for_timeout(2000)

        # 校验结果
        try:
            mask = frame_to_use.query_selector(".mask")
        except Exception:
            print("  [OK] 页面已导航，验证通过!", flush=True)
            _save_auth_state(page)
            return True
        if not mask:
            print("  [OK] 遮罩消失，验证通过!", flush=True)
            _save_auth_state(page)
            return True
        disp = mask.evaluate("el => getComputedStyle(el).display")
        if disp == "none":
            print("  [OK] 验证通过 (mask hidden)!", flush=True)
            _save_auth_state(page)
            return True

        # 错误提示
        err = frame_to_use.evaluate("""
            () => {
                const m = document.querySelector('.ivu-message-notice');
                return m ? m.textContent.trim().slice(0, 80) : '';
            }
        """)
        if err:
            print(f"  [X] 验证失败: {err}", flush=True)
        else:
            print("  [?] 不确定，等待后重试", flush=True)
            page.wait_for_timeout(3000)
            try:
                mask2 = frame_to_use.query_selector(".mask")
            except Exception:
                print("  [OK] 延迟后页面导航，验证通过!", flush=True)
                _save_auth_state(page)
                return True
            if not mask2 or mask2.evaluate("el => getComputedStyle(el).display") == "none":
                print("  [OK] 延迟后验证通过!", flush=True)
                _save_auth_state(page)
                return True

        # 刷新验证码
        refresh_btn = frame_to_use.query_selector(".verifybox-refresh")
        if refresh_btn:
            refresh_btn.click()
            page.wait_for_timeout(3000)
            print("  🔄 验证码已刷新", flush=True)
        else:
            page.wait_for_timeout(2000)

    print("  [X] 登录失败：已达最大重试次数", flush=True)
    return False


# =============================================================================
# 验证码
# =============================================================================

# =============================================================================
# 验证码识别 — 视觉模型优先 (NVIDIA NIM Llama-3.2-90B-Vision) → EasyOCR fallback
# =============================================================================

_ocr_reader = None


def _get_ocr_reader():
    """延迟初始化的 EasyOCR reader（CPU 模式）。"""
    global _ocr_reader
    if _ocr_reader is None:
        import easyocr
        _ocr_reader = easyocr.Reader(["ch_sim", "en"], gpu=False)
    return _ocr_reader


# ---------------------------------------------------------------------------
# 通用工具
# ---------------------------------------------------------------------------

def _find_captcha_elements(page) -> dict | None:
    """动态查找页面上的验证码元素（图片 + 提示文字 + 面板位置）。"""
    result = page.evaluate("""() => {
        const out = { imgData: null, hintText: '', panelRect: null, naturalW: 500, naturalH: 300 };

        // 1. 找提示文字 — 包含【】且内容像验证码（2-3个汉字，含、或→分隔）
        const allEls = document.querySelectorAll('*');
        for (const el of allEls) {
            const t = (el.innerText || '').trim();
            if (!t.includes('【') || !t.includes('】')) continue;
            // 提取【】内的内容
            const m = t.match(/【([^】]+)】/);
            if (!m) continue;
            const inner = m[1];
            // 验证码特征：2-3个汉字，用、或空格或→分隔，且提示中包含"依次"关键词
            // 排除"用户协议"、"隐私政策"等非验证码弹窗
            const isCaptcha = (
                !t.includes('协议') && !t.includes('隐私')
                && !t.includes('政策') && !t.includes('同意')
                && (t.includes('依次') || t.includes('验证码') || t.includes('点击'))
                && inner.replace(/[、，, \\s→]/g, '').length >= 2
                && inner.replace(/[、，, \\s→]/g, '').length <= 4
            );
            if (isCaptcha) {
                out.hintText = t;
                break;
            }
        }
        if (!out.hintText) return out;

        // 2. 找验证码图片 — 取面积最大的 >200x200 图片（比一般图标大）
        let bestImg = null, bestArea = 0;
        for (const img of document.querySelectorAll('img')) {
            const r = img.getBoundingClientRect();
            if (r.width < 200 || r.height < 200) continue;
            const area = r.width * r.height;
            if (area > bestArea) {
                bestArea = area;
                bestImg = img;
            }
        }
        if (bestImg) {
            const r = bestImg.getBoundingClientRect();
            out.panelRect = { x: r.x, y: r.y, w: r.width, h: r.height };
            out.naturalW = bestImg.naturalWidth || r.width;
            out.naturalH = bestImg.naturalHeight || r.height;
            try {
                const c = document.createElement('canvas');
                c.width = out.naturalW;
                c.height = out.naturalH;
                const ctx = c.getContext('2d');
                ctx.drawImage(bestImg, 0, 0);
                out.imgData = c.toDataURL('image/png');
            } catch(e) {}
        }

        return out;
    }""")

    # 必须有验证码特征提示 + 图片位置
    if result.get("hintText") and result.get("panelRect"):
        return result
    return None


def _solve_captcha(page, api_data: dict = None) -> bool:
    """
    主入口：循环解验证码直到弹窗消失（多轮验证码）。
    优先使用 API 拦截数据，退化到页面截图。

    Args:
        page: Playwright page
        api_data: 从 captcha/get/v2 API 拦截的数据
                   {"image": "base64...", "words": ["甲","乙"]}
    """
    max_rounds = 8
    for rnd in range(1, max_rounds + 1):
        page.wait_for_timeout(1500)

        if _solve_clickword(page, api_data=api_data):
            # 验证码通过
            page.wait_for_timeout(2000)
            try:
                still = _find_captcha_elements(page)
            except Exception:
                still = None
            if not still or still is None:
                print(f"  [OK] 验证码弹窗消失 ({rnd} 轮)", flush=True)
                return True
            # 可能有多轮验证码，继续下一轮
            continue

        print(f"  [FALLBACK] 识别失败，刷新重试 (round {rnd}/{max_rounds})", flush=True)
        _click_refresh(page)
        api_data = None  # 刷新后 API 数据失效，退到截图模式

    print(f"  [!] 超过 {max_rounds} 轮验证码仍未通过", flush=True)
    return False


def _click_refresh(page):
    """点击验证码刷新按钮（右上角刷新图标）。"""
    try:
        page.evaluate("""() => {
            // 找刷新/换一换按钮
            for (const el of document.querySelectorAll('*')) {
                const t = el.innerText || '';
                if ((t.includes('刷新') || t.includes('换一换')) && el.offsetParent !== null) {
                    el.click(); return;
                }
            }
            // 兜底：找右上角的 icon 按钮
            const btns = document.querySelectorAll('i.ivu-icon-ios-refresh, i.ivu-icon-md-refresh, [class*=refresh]');
            for (const btn of btns) {
                if (btn.offsetParent !== null) { btn.click(); return; }
            }
        }""")
        page.wait_for_timeout(1500)
    except Exception:
        page.wait_for_timeout(2000)


# ---------------------------------------------------------------------------
# ClickWordSolver 接入：ddddocr(det=True) AI 检测 + 分类识别
# 彻底替代 OpenCV 轮廓法，复杂背景/多色文字/任意背景都兼容
# ---------------------------------------------------------------------------

def _solve_clickword(page, api_data: dict = None) -> bool:
    """
    使用 ClickWordSolver 识别验证码并点击。
    采用 img_locator.click(position=) 方式，自动处理 iframe 坐标映射。
    """
    from backend.rpa.clickword_solver import solve_clickword, extract_words_from_prompt, extract_base64_from_dataurl
    import base64

    image_b64 = None
    wordlist = None

    # ---------- 优先路径：API 拦截数据 ----------
    if api_data and api_data.get("image") and api_data.get("words"):
        image_b64 = api_data["image"]
        wordlist = api_data["words"]
        print(f"  [CWS] API数据: wordlist={wordlist}", flush=True)
    else:
        # 降级：截图 + 页面提取
        captcha = _find_captcha_elements(page)
        if not captcha:
            return False
        hint_text = captcha.get("hintText", "")
        match = re.search(r"【(.*?)】", hint_text)
        if not match:
            return False
        wordlist = [c.strip() for c in match.group(1).replace("、", ",").split(",") if c.strip()]
        if not wordlist:
            return False
        panel = captcha["panelRect"]
        clip = {"x": panel["x"], "y": panel["y"], "width": panel["w"], "height": panel["h"]}
        screenshot = page.screenshot(clip=clip)
        image_b64 = base64.b64encode(screenshot).decode()
        print(f"  [CWS] 截图模式: wordlist={wordlist}", flush=True)

    for attempt in range(3):
        page.wait_for_timeout(1500)

        points = solve_clickword(image_b64, wordlist)
        if not points:
            print(f"  [CWS] 识别失败 (attempt {attempt+1})", flush=True)
            continue

        print(f"  [CWS] resolved: {wordlist} → {points}", flush=True)

        # === 像 auto_login.py 那样用 img_locator.click(position=, force=True) ===
        # 1. 获取验证码图片的自然尺寸（点击原点在图片内部）
        img_info = page.evaluate("""() => {
            // 从 iframe 或主页面找验证码图片
            const allFrames = document.querySelectorAll('iframe');
            for (const f of allFrames) {
                try {
                    const doc = f.contentDocument || f.contentWindow?.document;
                    if (!doc) continue;
                    const img = doc.querySelector('.verify-img-out img, .verifybox-img img, img[src*="data:image"]');
                    if (img) {
                        const r = img.getBoundingClientRect();
                        return {
                            cssW: r.width, cssH: r.height,
                            natW: img.naturalWidth, natH: img.naturalHeight,
                            frame: 'iframe'
                        };
                    }
                } catch(e) {}
            }
            // 主页面直接找
            const img = document.querySelector('.verify-img-out img, .verifybox-img img, img[src*="data:image"]');
            if (img) {
                const r = img.getBoundingClientRect();
                return {
                    cssW: r.width, cssH: r.height,
                    natW: img.naturalWidth, natH: img.naturalHeight,
                    frame: 'main'
                };
            }
            return null;
        }""")

        if not img_info:
            print(f"  [CWS] 找不到验证码图片元素", flush=True)
            return False

        scale_x = img_info["cssW"] / max(img_info["natW"], 1)
        scale_y = img_info["cssH"] / max(img_info["natH"], 1)
        print(f"  [CWS] img: css={img_info['cssW']:.0f}x{img_info['cssH']:.0f} nat={img_info['natW']}x{img_info['natH']} scale={scale_x:.2f}x{scale_y:.2f}", flush=True)

        # 2. 在 iframe 或主页面找这个 img 元素
        frame_to_use = None
        if img_info.get("frame") == "iframe":
            iframes = page.query_selector_all("iframe")
            for ifr in iframes:
                try:
                    f = ifr.content_frame()
                    if f:
                        test = f.evaluate("document.querySelector('.verify-img-out img, .verifybox-img img') ? true : false")
                        if test:
                            frame_to_use = f
                            break
                except:
                    pass
        else:
            frame_to_use = page

        locator = frame_to_use.locator('.verify-img-out img, .verifybox-img img') if frame_to_use else None
        if not locator:
            # 兜底：直接 page.mouse.click
            panel = _find_captcha_elements(page)
            if not panel:
                return False
            p = panel["panelRect"]
            for (x, y) in points:
                cx = int(p["x"] + x * scale_x)
                cy = int(p["y"] + y * scale_y)
                page.mouse.click(cx, cy)
                page.wait_for_timeout(300)
        else:
            for i, (px, py) in enumerate(points):
                css_x = px * scale_x
                css_y = py * scale_y
                # 微抖动
                jx = css_x + (i * 7 + 3) % 5 - 2
                jy = css_y + (i * 11 + 1) % 5 - 2
                print(f"    click: img({jx:.0f},{jy:.0f})", flush=True)
                locator.click(position={"x": jx, "y": jy}, force=True)
                page.wait_for_timeout(200)

        page.wait_for_timeout(2000)

        # 3. 检查验证码是否通过
        try:
            still = _find_captcha_elements(page)
        except Exception:
            return True  # 导航了，肯定通过了
        if not still:
            return True

        # 验证码还在 — 说明点击失败或有多轮
        # 截图模式下尝试刷新
        print(f"  [CWS] 点击后弹窗仍在，刷新", flush=True)
        if not api_data:
            _click_refresh(page)

    return False


# ---------------------------------------------------------------------------
# 备用方案（保留旧的 OpenCV/EasyOCR fallback，但不再作为主力）
# ---------------------------------------------------------------------------


def _get_ddddocr():
    """全局单例 ddddocr 实例，惰性初始化。"""
    global _dddd_ocr
    if _dddd_ocr is None:
        _dddd_ocr = ddddocr.DdddOcr(show_ad=False)
    return _dddd_ocr


_dddd_ocr = None
_DEBUG_DIR = Path(__file__).parent.parent.parent.parent / "_debug_ports"
_DEBUG_CNT = 0


def _debug_save(name: str, data: bytes, ext: str = "png"):
    """保存调试文件到 _debug_ports 目录。"""
    global _DEBUG_CNT
    _DEBUG_CNT += 1
    d = Path(_DEBUG_DIR)
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"sk_debug_{_DEBUG_CNT:03d}_{name}.{ext}"
    if ext == "png":
        f.write_bytes(data)
    else:
        f.write_text(data, encoding="utf-8")
    print(f"  [DEBUG] saved {f.name} ({len(data)} bytes)", flush=True)


def _extract_hint_text(page, captcha) -> list[str] | None:
    """
    从底部提示栏识别白底黑字文本，提取目标字序列。

    截图策略：提示栏一般在验证码图片下方的 DOM 中，
    先尝试从 captcha['hintText'] 直接提取，失败才 OCR。
    """
    import base64 as _b64

    hint = captcha.get("hintText", "")
    # 先从页面 text 直接提取（最快）
    m = re.search(r"【(.*?)】", hint)
    if m:
        words = [c.strip() for c in m.group(1).replace("、", ",").split(",") if c.strip()]
        if len(words) >= 2:
            print(f"  [HINT] 直接从页面文本提取目标: {words}", flush=True)
            return words

    # 兜底：找到提示栏元素截图 OCR
    print(f"  [HINT] 页面文本提取失败，尝试 OCR 提示栏...", flush=True)
    try:
        hint_region = page.evaluate("""() => {
            // 找包含【】文本的可见元素，截图其区域
            for (const el of document.querySelectorAll('*')) {
                const t = el.innerText || '';
                if (t.includes('【') && t.includes('】') && el.offsetParent !== null) {
                    const r = el.getBoundingClientRect();
                    return { x: r.x, y: r.y, w: r.width, h: r.height };
                }
            }
            return null;
        }""")
        if hint_region and hint_region["w"] > 0:
            clip = {"x": hint_region["x"], "y": hint_region["y"], "width": hint_region["w"], "height": hint_region["h"]}
            hint_img = page.screenshot(clip=clip)
            _debug_save("hint_bar", hint_img)
            # ddddocr 识别白底黑字
            ocr = _get_ddddocr()
            hint_text = ocr.classification(hint_img)
            print(f"  [HINT] OCR 提示栏结果: {hint_text}", flush=True)
            m2 = re.search(r"【(.*?)】", hint_text)
            if m2:
                words = [c.strip() for c in m2.group(1).replace("、", ",").split(",") if c.strip()]
                if len(words) >= 2:
                    return words
    except Exception as e:
        print(f"  [HINT] OCR 提取失败: {e}", flush=True)

    return None


def _solve_captcha_opencv(page, captcha=None) -> bool:
    """
    自适应阈值分割 + ddddocr 识别 + 精确坐标点击。

    流程：
    1. Playwright 截图验证码区域
    2. 自适阈值二值化（兼容任意颜色文字）
    3. 形态学操作 + 汉字特征轮廓筛选
    4. 裁剪单字 → ddddocr 逐个识别
    5. 匹配目标字 → 按顺序点击
    """
    import base64 as _b64, io as _io
    import cv2, numpy as _np
    from PIL import Image as _PImage

    for attempt in range(3):
        page.wait_for_timeout(2000 if attempt == 0 else 1500)

        if captcha is None:
            captcha = _find_captcha_elements(page)
        if not captcha:
            print(f"  [OCV] attempt {attempt+1}: captcha not found", flush=True)
            continue

        # ---- Step 1: 提取目标字序列 ----
        wordlist = _extract_hint_text(page, captcha)
        if not wordlist:
            print(f"  [OCV] attempt {attempt+1}: cannot extract wordlist from hint", flush=True)
            continue
        print(f"  [OCV] wordlist: {wordlist}", flush=True)

        # ---- Step 2: 截图验证码区域（Playwright 直接截） ----
        panel = captcha["panelRect"]
        clip_rect = {"x": panel["x"], "y": panel["y"], "width": panel["w"], "height": panel["h"]}
        screenshot_bytes = page.screenshot(clip=clip_rect)
        _debug_save(f"captcha_raw_{attempt+1}", screenshot_bytes)
        snap_img = _PImage.open(_io.BytesIO(screenshot_bytes))
        snap_w, snap_h = snap_img.size
        print(f"  [OCV] screenshot: {snap_w}x{snap_h}", flush=True)

        nparr = _np.frombuffer(screenshot_bytes, _np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        # ---- Step 3: 标准化通用文字提取流水线 ----
        # 1. CLAHE 对比度增强（解决浅淡文字）
        # 2. 全色系 HSV 掩膜（捕获红/橙/黄/绿/浅蓝/深蓝/紫）
        # 3. 增强灰度自适应阈值兜底（捕获白色/浅灰文字）
        # 4. 双通道融合 + 形态学降噪
        # 5. 轮廓多重筛选（面积/宽高比/填充密度）
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        gray_enh = clahe.apply(gray)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        # 3a. 全色系 HSV 掩膜（7 大色系，覆盖所有验证码字体色）
        # 降低 S/V 下限到 40 以捕获低饱和度文字
        # 红色 (0-18)
        m_red1 = cv2.inRange(hsv, _np.array([0, 40, 40]), _np.array([18, 255, 255]))
        # 红色 (162-180)
        m_red2 = cv2.inRange(hsv, _np.array([162, 40, 40]), _np.array([180, 255, 255]))
        # 橙/土黄
        m_orange = cv2.inRange(hsv, _np.array([18, 40, 40]), _np.array([38, 255, 255]))
        # 绿色
        m_green = cv2.inRange(hsv, _np.array([35, 40, 40]), _np.array([88, 255, 255]))
        # 浅天蓝
        m_lblue = cv2.inRange(hsv, _np.array([90, 40, 40]), _np.array([115, 255, 255]))
        # 深蓝/紫
        m_dblue = cv2.inRange(hsv, _np.array([116, 40, 40]), _np.array([159, 255, 255]))
        # 玫红 (按需补充：色相 160~175，饱和度中高)
        m_pink = cv2.inRange(hsv, _np.array([155, 40, 40]), _np.array([170, 255, 255]))

        # 合并所有彩色掩膜
        color_mask = (m_red1 + m_red2 + m_orange + m_green + m_lblue + m_dblue + m_pink)
        color_mask = _np.where(color_mask > 0, 255, 0).astype(_np.uint8)

        # 3b. CLAHE 增强灰度自适应阈值（兜底白色/浅灰文字）
        bin_inv = cv2.adaptiveThreshold(gray_enh, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 15, 3)
        bin_norm = cv2.adaptiveThreshold(gray_enh, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 3)
        white_inv = _np.sum(bin_inv == 255)
        white_norm = _np.sum(bin_norm == 255)
        gray_binary = bin_inv if white_inv < white_norm else bin_norm
        print(f"  [OCV] gray threshold: {'INV' if white_inv < white_norm else 'NORM'} (inv_white={white_inv}, norm_white={white_norm})", flush=True)

        # 3c. 双通道融合
        combine = cv2.bitwise_or(color_mask, gray_binary)
        _debug_save(f"color_mask_{attempt+1}", cv2.imencode('.png', color_mask)[1].tobytes())
        _debug_save(f"combine_{attempt+1}", cv2.imencode('.png', combine)[1].tobytes())

        # 形态学降噪：闭运算连接笔画，开运算去噪点
        kernel = _np.ones((2, 3), _np.uint8)
        combine = cv2.morphologyEx(combine, cv2.MORPH_CLOSE, kernel)
        combine = cv2.morphologyEx(combine, cv2.MORPH_OPEN, kernel)
        _debug_save(f"morph_{attempt+1}", cv2.imencode('.png', combine)[1].tobytes())

        # ---- Step 4: 轮廓检测 + 汉字筛选（面积/宽高比/填充密度） ----
        contours, _ = cv2.findContours(combine, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        print(f"  [OCV] total contours after morph: {len(contours)}", flush=True)

        min_area = 70
        max_area = 3200  # 最多画面 12%

        char_regions = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            area = w * h
            if area < min_area or area > max_area:
                continue
            ratio = w / max(h, 1)
            if ratio < 0.45 or ratio > 1.7:
                continue
            if h < 10 or w < 10:
                continue

            roi = combine[y:y+h, x:x+w]
            fill_ratio = _np.count_nonzero(roi) / (w * h)
            if fill_ratio < 0.05:
                continue

            char_regions.append((x, y, w, h, area, fill_ratio))

        print(f"  [OCV] after char filtering: {len(char_regions)} regions", flush=True)

        if len(char_regions) < len(wordlist):
            print(f"  [OCV] only {len(char_regions)} char regions, need ≥{len(wordlist)}", flush=True)
            continue

        # 按面积取 top candidates（2×wordlist 防止漏）
        char_regions.sort(key=lambda b: b[4], reverse=True)
        char_regions = char_regions[:max(len(wordlist) * 2, 6)]

        # 画轮廓调试图
        img_boxes = img.copy()
        for (x, y, w, h, _, fr) in char_regions:
            cv2.rectangle(img_boxes, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(img_boxes, f"{fr:.2f}", (x, y-3), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
        _debug_save(f"boxes_{attempt+1}", cv2.imencode('.png', img_boxes)[1].tobytes())

        # ---- Step 5: 用 ddddocr + EasyOCR 双引擎识别文字 ----
        ocr_dddd = _get_ddddocr()
        ocr_easy = _get_ocr_reader()
        recognized = []

        PAD = 10
        for (x, y, w, h, _, _) in char_regions:
            x1 = max(0, x - PAD)
            y1 = max(0, y - PAD)
            x2 = min(snap_w, x + w + PAD)
            y2 = min(snap_h, y + h + PAD)
            crop = img[y1:y2, x1:x2]
            _, crop_buf = cv2.imencode('.png', crop)

            # 单字对比度增强（CLAHE） + 膨胀加粗笔画
            crop_gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            crop_clahe = cv2.createCLAHE(clipLimit=1.8, tileGridSize=(4, 4)).apply(crop_gray)
            crop_enhanced = cv2.dilate(crop_clahe, _np.ones((1, 1), _np.uint8), iterations=1)

            # 引擎1: EasyOCR（主力 — 对单字中文识别优于 ddddocr）
            easy_results = ocr_easy.readtext(crop_enhanced, detail=1, batch_size=1)
            char_text = ""
            for bbox, txt, conf in easy_results:
                t = txt.strip().replace(" ", "")
                if conf > 0.3 and len(t) <= 2 and len(t) >= 1:
                    char_text = t
                    print(f"    [EASY] '{t}' conf={conf:.2f}", flush=True)
                    break

            # 引擎2: ddddocr fallback（EasyOCR 置信度低或空白时）
            if not char_text:
                temp_text = ocr_dddd.classification(crop_buf.tobytes()).strip()
                if temp_text and len(temp_text) <= 2:
                    char_text = temp_text
                    print(f"    [DDDD] '{temp_text}'", flush=True)

            if char_text and 1 <= len(char_text) <= 2:
                cx = x + w // 2
                cy = y + h // 2
                recognized.append({"char": char_text, "x": cx, "y": cy, "w": w, "h": h})
                print(f"    [{char_text}] at ({cx},{cy})", flush=True)

        print(f"  [OCV] recognized {len(recognized)} chars", flush=True)

        if len(recognized) < len(wordlist):
            print(f"  [OCV] only recognized {len(recognized)} chars, need ≥{len(wordlist)}", flush=True)
            continue

        # ---- Step 6: 匹配目标字 ----
        click_queue = []
        used_indices = set()

        for target in wordlist:
            found = False
            for i, r in enumerate(recognized):
                if i in used_indices:
                    continue
                # 精确匹配或包含匹配
                if r["char"] == target or target in r["char"] or r["char"] in target:
                    click_queue.append({"char": target, "x": r["x"], "y": r["y"]})
                    used_indices.add(i)
                    found = True
                    break
            if not found:
                # 模糊匹配：相同首字
                for i, r in enumerate(recognized):
                    if i in used_indices:
                        continue
                    if r["char"] and r["char"][0] == target[0]:
                        click_queue.append({"char": target, "x": r["x"], "y": r["y"]})
                        used_indices.add(i)
                        found = True
                        break

            if not found:
                print(f"  [OCV] cannot find target '{target}' in recognized chars", flush=True)
                break

        if len(click_queue) != len(wordlist):
            print(f"  [OCV] only matched {len(click_queue)}/{len(wordlist)} targets", flush=True)
            continue

        print(f"  [OCV] matched: {[p['char'] for p in click_queue]}", flush=True)

        # ---- Step 7: 点击坐标映射并执行 ----
        scale_x = snap_w / panel["w"] if panel["w"] else 1.0
        scale_y = snap_h / panel["h"] if panel["h"] else 1.0
        # 注意：Playwright screenshot(clip=) 截出来的是 CSS 像素
        # click 坐标需要映射回页面坐标
        # 但 clip 截的图和页面坐标是一致的（同比例），直接用 panel + offset
        for pt in click_queue:
            click_x = int(panel["x"] + pt["x"])
            click_y = int(panel["y"] + pt["y"])
            print(f"    click: {pt['char']} at page({click_x},{click_y})", flush=True)
            page.mouse.click(click_x, click_y)
            page.wait_for_timeout(300)

        print(f"  [OCV] clicks done: {[p['char'] for p in click_queue]}", flush=True)
        page.wait_for_timeout(2000)

        # ---- Step 8: 验证是否通过（捕获可能发生的导航）----
        try:
            still_has = _find_captcha_elements(page)
        except Exception:
            # 页面导航了 → 说明验证成功
            print(f"  [OCV] 页面已导航，验证码通过 ✓", flush=True)
            return True

        if not still_has:
            print(f"  [OCV] 验证码弹窗消失 ✓", flush=True)
            return True

        print(f"  [OCV] 验证码依然存在，可能未通过", flush=True)
        _click_refresh(page)

    return False



# NVIDIA NIM 配置
_NVIDIA_KEY_KEYS = ["agent_key_nim_gpt", "agent_key_nim_qwen", "agent_key_nim_minimax", "agent_key_nim_deepseek"]
_NVIDIA_API_BASE = "https://integrate.api.nvidia.com/v1"
_NVIDIA_VISION_MODEL = "meta/llama-3.2-90b-vision-instruct"


def _get_vision_model() -> str:
    """从数据库读取用户配置的视觉模型，无配置则返回默认。"""
    try:
        import sqlite3
        db_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        db_path = os.path.join(db_dir, "oaiw.db")
        db = sqlite3.connect(db_path)
        cur = db.cursor()
        cur.execute("SELECT value FROM settings WHERE key=?", ("vision_model",))
        row = cur.fetchone()
        db.close()
        if row and row[0]:
            return row[0]
    except Exception:
        pass
    return _NVIDIA_VISION_MODEL


def _get_nvidia_key() -> str | None:
    """从 SQLite settings 表读取 NVIDIA NIM API Key。"""
    try:
        import sqlite3
        db_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        db_path = os.path.join(db_dir, "oaiw.db")
        db = sqlite3.connect(db_path)
        cur = db.cursor()
        for key_name in _NVIDIA_KEY_KEYS:
            cur.execute("SELECT value FROM settings WHERE key=?", (key_name,))
            row = cur.fetchone()
            if row and row[0]:
                db.close()
                return row[0]
        db.close()
    except Exception as e:
        print(f"  [VISION] DB读取失败: {e}", flush=True)
    return None


def _vision_ocr(img_data: str, wordlist: list[str], nat_w: int, nat_h: int) -> list[dict] | None:
    """
    调用 NVIDIA NIM 视觉模型 (Llama-3.2-90B-Vision) 分析验证码图片。

    Args:
        img_data: base64 data URL (data:image/png;base64,...)
        wordlist: 目标字符列表（需按此顺序点击）
        nat_w, nat_h: 图片原始尺寸

    Returns:
        [{"char": "工", "x": 123, "y": 456}, ...] 或 None
    """
    import httpx

    api_key = _get_nvidia_key()
    if not api_key:
        print("  [VISION] 未找到 NVIDIA API Key", flush=True)
        return None

    wordlist_str = " → ".join(wordlist)

    # 用新 model（如果数据库配了就把默认改掉）
    model_used = _get_vision_model()

    prompt = f"""You are analyzing an image with Chinese text.
The image is {nat_w}x{nat_h} pixels.

Find these exact characters: {wordlist_str}

For each character, output its center coordinates (x,y).
The coordinate origin (0,0) is the top-left corner. X goes right, Y goes down.

Return ONLY a JSON array, no other text:
[
  {{"char": "{wordlist[0]}", "x": <int>, "y": <int>}},
  {{"char": "{wordlist[1]}", "x": <int>, "y": <int>}}
]"""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model_used,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": img_data}},
            ],
        }],
        "max_tokens": 1024,
        "temperature": 0.1,
    }

    try:
        resp = httpx.post(
            f"{_NVIDIA_API_BASE}/chat/completions",
            json=payload,
            headers=headers,
            timeout=60,
        )

        if resp.status_code != 200:
            print(f"  [VISION] API错误 {resp.status_code}: {resp.text[:200]}", flush=True)
            return None

        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        print(f"  [VISION] raw response ({len(content)} chars):\n{content[:500]}", flush=True)

        # 提取 JSON（模型可能用 ```json 包裹或前置文字说明）
        json_str = content
        if "```json" in json_str:
            json_str = json_str.split("```json")[1]
        if "```" in json_str:
            json_str = json_str.split("```")[0]
        json_str = json_str.strip()
        # 如果还有前置文字（非 JSON 内容），找到第一个 [ 或 {
        start = json_str.find('[')
        if start < 0:
            start = json_str.find('{')
        if start > 0:
            json_str = json_str[start:]
        # 去掉末尾非 JSON 内容
        end = json_str.rfind(']')
        if end >= 0:
            json_str = json_str[:end+1]

        result = json.loads(json_str)

        if isinstance(result, list) and len(result) > 0:
            validated = []
            for item in result:
                if all(k in item for k in ("char", "x", "y")):
                    validated.append({
                        "char": str(item["char"]).strip(),
                        "x": int(round(float(item["x"]))),
                        "y": int(round(float(item["y"]))),
                    })
            if len(validated) == len(wordlist):
                return validated
            else:
                print(f"  [VISION] 数量不匹配: 期望{len(wordlist)} 得到{len(validated)}", flush=True)

        print(f"  [VISION] 响应格式异常: {content[:300]}", flush=True)
    except Exception as e:
        print(f"  [VISION] 调用失败: {type(e).__name__}: {e}", flush=True)

    return None


def _solve_captcha_vision_fallback(page, captcha=None) -> bool:
    """
    Vision API fallback — 当 OpenCV+OCR 失败时使用。
    全图直接送 Vision API 定位返回坐标 → 点击。
    """
    import base64 as _b64

    for attempt in range(2):
        page.wait_for_timeout(1500)
        if captcha is None:
            captcha = _find_captcha_elements(page)
        if not captcha:
            return False

        hint_text = captcha["hintText"]
        panel = captcha["panelRect"]
        match = re.search(r"【(.*?)】", hint_text)
        if not match:
            continue
        wordlist = [c.strip() for c in match.group(1).replace("、", ",").split(",") if c.strip()]
        if not wordlist:
            continue

        clip_rect = {"x": panel["x"], "y": panel["y"], "width": panel["w"], "height": panel["h"]}
        screenshot_bytes = page.screenshot(clip=clip_rect)
        img_b64 = _b64.b64encode(screenshot_bytes).decode()
        img_data_url = f"data:image/png;base64,{img_b64}"

        coords = _vision_ocr(img_data_url, wordlist, panel["w"], panel["h"])
        if not coords:
            continue

        for pt in coords:
            click_x = int(panel["x"] + pt["x"])
            click_y = int(panel["y"] + pt["y"])
            page.mouse.click(click_x, click_y)
            page.wait_for_timeout(200)

        page.wait_for_timeout(2000)
        try:
            still_has = _find_captcha_elements(page)
        except Exception:
            return True  # 导航了 => 验证通过
        if not still_has:
            return True

    return False


# ---------------------------------------------------------------------------
# 方案 B: EasyOCR fallback — 传统 OCR 识别所有文字 → 匹配 → 点击
# ---------------------------------------------------------------------------

def _preprocess_image(img, method=0):
    """
    验证码图像预处理，提高 OCR 识别率。

    method 0: CLAHE + 双边滤波
    method 1: 自适应阈值二值化 + 闭运算
    method 2: OTSU 二值化 + 膨胀
    """
    import cv2
    import numpy as np

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    if method == 0:
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        filtered = cv2.bilateralFilter(enhanced, 5, 50, 50)
        return cv2.cvtColor(filtered, cv2.COLOR_GRAY2BGR)

    elif method == 1:
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        binary = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 4
        )
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        morphed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        return cv2.cvtColor(morphed, cv2.COLOR_GRAY2BGR)

    elif method == 2:
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        dilated = cv2.dilate(binary, kernel, iterations=1)
        return cv2.cvtColor(dilated, cv2.COLOR_GRAY2BGR)

    return img


def _match_char_to_candidates(ch, candidates, used_indices):
    """多策略匹配一个字符到候选区域。"""
    best_idx = None
    best_score = 0

    for i, c in enumerate(candidates):
        if i in used_indices:
            continue
        ocr_text = c["ocr"]

        if ch == ocr_text:
            return i, 100
        if ch in ocr_text or ocr_text in ch:
            score = 80 - abs(len(ch) - len(ocr_text)) * 5
            if score > best_score:
                best_score = score
                best_idx = i
        if len(ocr_text) > 0 and ocr_text[0] == ch[0]:
            score = 60 - abs(len(ch) - len(ocr_text)) * 5
            if score > best_score:
                best_score = score
                best_idx = i

    return best_idx, best_score


def _filter_candidates(candidates):
    """去除距离过近的重复检测。"""
    filtered = []
    for c in candidates:
        is_dup = False
        for existing in filtered:
            dx = abs(c["x"] - existing["x"])
            dy = abs(c["y"] - existing["y"])
            if dx < 20 and dy < 15:
                is_dup = True
                if len(c["ocr"]) > len(existing["ocr"]):
                    existing["ocr"] = c["ocr"]
                break
        if not is_dup:
            filtered.append(c)
    return filtered


def _solve_captcha_easyocr(page, captcha=None) -> bool:
    """
    EasyOCR fallback：识别所有文字区域，匹配 wordlist，按顺序点击。
    """
    try:
        import cv2
        import numpy as np
    except ImportError as e:
        raise ImportError(
            "EasyOCR fallback 需要 opencv-python, easyocr, numpy。"
            f"pip install opencv-python easyocr numpy   ({e})"
        )

    reader = _get_ocr_reader()

    for attempt in range(3):
        page.wait_for_timeout(2000 if attempt == 0 else 1500)

        captcha = _find_captcha_elements(page)
        if not captcha:
            continue

        img_data = captcha["imgData"]
        hint_text = captcha["hintText"]
        panel = captcha["panelRect"]
        nat_w = captcha["naturalW"]
        nat_h = captcha["naturalH"]

        match = re.search(r"【(.*?)】", hint_text)
        if not match:
            continue
        chars_need = list(match.group(1).replace("、", "").replace(" ", ""))

        import base64
        try:
            base64_str = img_data.split(",")[1]
            img_bytes = base64.b64decode(base64_str)
            nparr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                continue
        except Exception:
            continue

        preprocess_method = (attempt % 3)
        processed_img = _preprocess_image(img, preprocess_method)

        full_results = reader.readtext(processed_img, detail=1, batch_size=1)

        candidates = []
        for bbox, text, conf in full_results:
            if conf < 0.2:
                continue
            xs = [p[0] for p in bbox]
            ys = [p[1] for p in bbox]
            cx = (min(xs) + max(xs)) / 2
            cy = (min(ys) + max(ys)) / 2
            text_clean = text.strip().replace(" ", "")
            if not text_clean:
                continue
            candidates.append({"x": cx, "y": cy, "ocr": text_clean, "conf": conf})

        candidates = _filter_candidates(candidates)
        if not candidates:
            continue

        scale_x = panel["w"] / nat_w if nat_w else 1.0
        scale_y = panel["h"] / nat_h if nat_h else 1.0

        pos_map = {}
        used_indices = set()
        unmatched_chars = []

        for ch in chars_need:
            idx, score = _match_char_to_candidates(ch, candidates, used_indices)
            if idx is not None:
                pos_map[ch] = (candidates[idx]["x"], candidates[idx]["y"])
                used_indices.add(idx)
            else:
                unmatched_chars.append(ch)

        remaining = [c for i, c in enumerate(candidates) if i not in used_indices]
        for ch, pos in zip(unmatched_chars, remaining):
            pos_map[ch] = (pos["x"], pos["y"])

        if len(pos_map) < len(chars_need):
            continue

        for ch in chars_need:
            if ch in pos_map:
                cx, cy = pos_map[ch]
                click_x = panel["x"] + cx * scale_x
                click_y = panel["y"] + cy * scale_y
                page.mouse.click(click_x, click_y)
                page.wait_for_timeout(400)

        page.wait_for_timeout(2000)
        return True

    return False


# =============================================================================
# 登录态管理
# =============================================================================

def _load_auth_state() -> dict | None:
    """从磁盘加载保存的登录态。"""
    if AUTH_STATE_PATH.exists():
        try:
            with open(AUTH_STATE_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def _save_auth_state(page):
    """保存当前登录态到磁盘。"""
    try:
        storage = page.context.storage_state()
        AUTH_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(AUTH_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(storage, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# =============================================================================
# 导航与查询
# =============================================================================

def _close_popups(page):
    """关闭平台公告弹窗（不含验证码弹窗）。"""
    print("  🔔 关闭弹窗...", flush=True)
    page.evaluate("""() => {
        // 只关 iView 类公告弹窗，不碰验证码弹窗
        const modals = document.querySelectorAll('.ivu-modal');
        for (const m of modals) {
            // 跳过验证码弹窗（包含依次点击文字）
            const text = (m.innerText || '');
            if (text.includes('【') && text.includes('】')) continue;
            const closeBtn = m.querySelector('.ivu-modal-close');
            if (closeBtn && closeBtn.offsetParent !== null) {
                closeBtn.scrollIntoView({block:'center'});
                closeBtn.click();
                console.log('closed notice modal');
            }
        }
    }""")
    page.wait_for_timeout(500)


def _click_quick_link(page):
    """点击主内容区 '单箱查询' 快捷链接。"""
    print("  🔗 点击「单箱查询」快捷链接...", flush=True)
    page.evaluate("""() => {
        const all = document.querySelectorAll('.menus_item_title');
        for (const el of all) {
            if (el.innerText.trim() === '单箱查询') {
                el.click(); return;
            }
        }
    }""")
    page.wait_for_timeout(2000)


def _fix_iframe_and_query(page, container_no: str) -> dict:
    """
    修复 iframe src 为正确的 scct-query 子应用 URL，
    填写柜号、点击查询，拦截 API JSON 响应。

    Returns:
        dict: API 响应数据的映射 {api_name: json_data}
    """
    api_resp_data = {}

    def _capture_api_response(response):
        url = response.url
        if "scct_query/sct/api" in url and response.status == 200:
            try:
                data = json.loads(response.text())
                # 从 URL 中提取 API 名称
                name = url.split("/scct_query/sct/api/")[-1].split("?")[0]
                api_resp_data[name] = data
            except Exception:
                pass

    page.on("response", _capture_api_response)

    # 等待 iframe 出现
    print("  📄 加载查询页面...", flush=True)
    iframes = page.query_selector_all("iframe")
    if not iframes:
        print("  ⚠️ 未找到 iframe", flush=True)
        return api_resp_data

    iframe = iframes[0]

    # 修复 iframe src 为正确的子应用 URL
    correct_url = "https://wk-eport.cmp1872.com/scct-query/danxiangsonumber"
    print(f"  🔧 修复 iframe src...", flush=True)
    page.evaluate("""() => {
        const ifr = document.querySelector('iframe');
        if (ifr) ifr.src = '""" + correct_url + """';
    }""")
    page.wait_for_timeout(5000)

    # 进入 iframe
    frame = iframe.content_frame()
    if not frame:
        return api_resp_data

    try:
        frame.wait_for_load_state("domcontentloaded", timeout=10000)
    except Exception:
        pass
    page.wait_for_timeout(2000)

    # 填写柜号
    print(f"  ✏️ 填写柜号: {container_no}", flush=True)
    input_els = frame.query_selector_all("input")
    for inp in input_els:
        try:
            rect = inp.bounding_box()
            if rect and rect["width"] > 0:
                inp.click()
                inp.fill(container_no)
                break
        except Exception:
            pass

    page.wait_for_timeout(500)

    # 点击"查询"按钮
    print("  🔍 点击查询按钮...", flush=True)
    query_btn = frame.query_selector("button:has-text('查询')")
    if query_btn:
        query_btn.click()
        page.wait_for_timeout(5000)
    else:
        # 兜底：找任意可见按钮
        for btn in frame.query_selector_all("button"):
            try:
                if btn.is_visible():
                    btn.click()
                    page.wait_for_timeout(5000)
                    break
            except Exception:
                pass

    return api_resp_data


# =============================================================================
# 结果解析
# =============================================================================

# 状态字段的友好映射
_STATUS_MAP = {"FULL": "重柜", "EMPTY": "吉柜", "LCL": "拼箱"}
_RELEASE_MAP = {"RELEASED": "已放行", "NOT_RELEASED": "未放行", "HOLD": "Hold"}


def _parse_result(api_data: dict, container_no: str, booking_no: str = "") -> dict:
    """
    将 API JSON 解析为友好的文本结果。
    """
    info = api_data.get("GContainerInfo", {})
    hist = api_data.get("GContainerHistoryInfo", {})
    inner = info.get("InnerList", [])

    if not inner:
        lines = [
            f"蛇口港(SCCT) - 集装箱 {container_no} 查询结果",
            f"{'─' * 50}",
            f"未查到该箱信息，可能当前不在蛇口港。",
        ]
        if booking_no:
            lines.append(f"订舱号: {booking_no}")
        # 补上原始数据
        raw = json.dumps(api_data, ensure_ascii=False, indent=2)[:500]
        lines.append(f"\n原始API: {raw}")

        return {"success": True, "data": "\n".join(lines), "error": ""}

    c = inner[0]
    lines = [
        f"蛇口港(SCCT) - 集装箱 {container_no} 查询结果",
        f"{'─' * 50}",
        f"",
        f"【基本信息】",
        f"柜号:     {c.get('ContainerNbr', '--')}",
        f"箱属:     {c.get('LineId', '--')}",
        f"尺寸/类型: {c.get('SzTpHt', '--')}  ISO: {c.get('IsoCode', '--')}",
        f"柜状态:   {_STATUS_MAP.get(c.get('Status', ''), c.get('Status', '--'))}",
        f"放行状态: {_RELEASE_MAP.get(c.get('ReleaseStatus', ''), c.get('ReleaseStatus', '--'))}",
        f"当前位置: {c.get('Location', '--')}",
        f"毛重(KG): {c.get('GrossWeight', '--')}",
        f"封条号:   {c.get('SealNbr1', '--')}",
        f"订舱单号: {c.get('BookingEdo', '--')}",
        f"IMO:      {c.get('IMO', '--')}",
        f"",
        f"【运输信息】",
        f"装货港:   {c.get('PolAlias', '--')}",
        f"卸货港:   {c.get('PodAlias', '--')}",
        f"目的港:   {c.get('Destination', '--')}",
        f"进场拖车: {c.get('InTruckNbr', '--') or '--'}",
        f"进场时间: {c.get('InTime', '--') or '--'}",
        f"出场时间: {c.get('OutTime', '--') or '--'}",
        f"",
        f"【船舶信息】",
        f"进港船名航次: {c.get('ArrVesselVoyage', '--') or '--'}",
        f"离港船名航次: {c.get('DepVesselVoyage', '--') or '--'}",
        f"出口商业航次: {c.get('OutBusinessVoy', '--') or '--'}",
        f"",
        f"【海关放行】",
        f"截放行条时间: {c.get('CIQ', '--') or '--'}",
        f"海关放行时间: {c.get('CUS', '--') or '--'}",
        f"激活放行时间: {c.get('Voucher', '--') or '--'}",
    ]

    # CIC 信息（如果有）
    cic = c.get("CicTime", "")
    if cic and cic != "N":
        lines.extend([
            f"",
            f"【CIC 信息】",
            f"CIC时间: {cic.replace('Y  ', '')}",
            f"CIC状态: {c.get('CicStatus', '--') or '--'}",
        ])

    # 操作历史（最近 5 条）
    hist_list = hist.get("InnerList", [])
    if hist_list:
        lines.extend([
            f"",
            f"【操作历史 - 最近 {min(5, len(hist_list))} 条】",
        ])
        for h in hist_list[:5]:
            time_str = h.get("OpTime", "")
            op = h.get("OpType", "")
            col = h.get("ColumnName", "")
            new_val = h.get("NewValue", "") or "--"
            lines.append(f"  {time_str}")
            lines.append(f"  {op} | {col}: {new_val}")
            lines.append("")

    lines.append(f"{'─' * 50}")
    lines.append(f"数据来源: 蛇口港 SCCT (wk-eport.cmp1872.com)")

    return {"success": True, "data": "\n".join(lines), "error": ""}
