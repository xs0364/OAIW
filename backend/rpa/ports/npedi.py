"""
Ningbo port (npedi.com) RPA driver - container logistics status query.

Semi-auto login flow:
1. Playwright opens npedi.com -> click login -> click phone-login tab
2. Fill phone -> auto-recognize image captcha (ddddocr) -> click send SMS
3. Frontend popup -> user enters SMS code received on phone
4. RPA fills SMS code -> submit login -> get Web-Token
5. Use Token to call EDI API for container query

API:
  GET http://api.npedi.com:8888/CtnStatusInfo/NewQueryNBGMultiCtnStatus
  Header: token=<Web-Token cookie>
  Param: arg0={...}
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import base64
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path

from backend.rpa.ports import register
from backend.rpa.log_queue import rpa_log as _log


# =============================================================================
# Paths
# =============================================================================

TOKEN_PATH = Path(__file__).parent / "npedi_token.txt"
AUTH_STATE_PATH = Path(__file__).parent / "npedi_auth_state.json"
MOBILE_STORE_PATH = Path(__file__).parent / "npedi_mobile.txt"


def _save_mobile(mobile: str):
    MOBILE_STORE_PATH.write_text(mobile.strip(), encoding="utf-8")


def _load_mobile() -> str | None:
    if MOBILE_STORE_PATH.exists():
        return MOBILE_STORE_PATH.read_text(encoding="utf-8").strip()
    return None


# =============================================================================
# Token management
# =============================================================================


def _load_token() -> str | None:
    if TOKEN_PATH.exists():
        try:
            return TOKEN_PATH.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    state = _load_auth_state()
    if state:
        for c in state.get("cookies", []):
            if c.get("name") == "Web-Token":
                return c.get("value")
    return None


def _save_token(token: str):
    TOKEN_PATH.write_text(token.strip(), encoding="utf-8")
    _log("  [TOKEN] Token saved")


def _save_auth_state(page):
    try:
        state = page.context.storage_state()
        AUTH_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(AUTH_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        _log("  [STATE] Auth state saved")
    except Exception as e:
        _log(f"  [STATE] Failed to save auth state: {e}")


def _load_auth_state() -> dict | None:
    if AUTH_STATE_PATH.exists():
        try:
            return json.loads(AUTH_STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None


# =============================================================================
# API
# =============================================================================

_API_BASE = "http://api.npedi.com:8888"
_QUERY_PATH = "/CtnStatusInfo/NewQueryNBGMultiCtnStatus"


def _call_api(params: dict, token: str) -> dict:
    arg0 = json.dumps(params, ensure_ascii=False, separators=(",", ":"))
    url = f"{_API_BASE}{_QUERY_PATH}?arg0={urllib.parse.quote(arg0)}"

    req = urllib.request.Request(url)
    req.add_header("token", token)

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8")
            return {"success": True, "data": body, "raw": body}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        if "Token is required" in err_body or "Permission denied" in err_body:
            return {
                "success": False,
                "data": "",
                "error": "Token expired, need re-login",
            }
        return {"success": False, "data": "", "error": f"API error ({e.code}): {err_body[:300]}"}
    except urllib.error.URLError as e:
        return {"success": False, "data": "", "error": f"Network error: {e.reason}"}
    except Exception as e:
        return {"success": False, "data": "", "error": f"API exception: {type(e).__name__}: {e}"}


# =============================================================================
# Constants
# =============================================================================

_TERMINAL_MAP = {
    "BLCT": "Erqi", "BLCT2": "Sanqi", "BLCT3": "Siqi",
    "BLCTZS": "Daxie Zhaoshang", "BLCTMS": "Meishan",
    "ZHCT": "Zhensi", "B2SCT": "Beilunshan", "ZIT": "Zhapu",
    "YZCT": "Yongzhou", "CNDTU": "Zhuangyuan'ao", "CNDMY": "Daimaiyu",
    "NDCC": "Dagang Xinshiji", "NCICL": "Dagang Xinshiji",
}
_DIRECT_MAP = {"I": "Import", "E": "Export"}
_STATUS_MAP = {"E": "Empty", "F": "Full", "L": "LCL"}
_CUSTPASS_MAP = {"EP": "Export released", "IP": "Import released", "RP": "Cancel"}
_NPP_STATUS_MAP = {"Y": "Released", "T": "Cancel release", "N": "Not released"}
_INGATE_STATUS_MAP = {"Y": "In gate", "N": "Not in gate"}
_OUTGATE_STATUS_MAP = {"Y": "Out gate", "N": "Not out gate"}
_LOAD_STATUS_MAP = {"Y": "Loaded", "N": "Not loaded"}
_DISCHARGE_STATUS_MAP = {"Y": "Discharged", "N": "Not discharged"}
_COSTCO_STATUS_MAP = {"Y": "Stuffed", "N": "Not stuffed"}
_CUSMOV_STATUS_MAP = {
    "C": "Inspection", "CM": "Can move", "OK": "Move done",
    "OT": "Return done", "UM": "Cannot move", "R": "Cancel",
    "CR": "Can cancel", "OR": "Cancel done", "UR": "Cannot cancel",
    "P": "LCL", "O": "Move order received", "E": "Move complete",
    "N": "Container not in yard", "Y": "Order exists", "Z": "Manual", "G": "Return done",
}
_CHECK986_MAP = {
    "1": "Manual", "2": "Machine", "3": "Manual+Machine", "4": "Machine->Manual",
    "5": "Machine->Manual(Manual)", "6": "Pre-hygiene",
    "Y": "Yes", "N": "No",
}


def _safe(val, default="--"):
    return val if val is not None and val != "" else default


def _fmt_time(t_str: str) -> str:
    if not t_str or len(t_str) < 8:
        return _safe(t_str)
    try:
        import datetime
        dt = datetime.datetime.strptime(t_str, "%Y%m%d%H%M%S")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return t_str


def _parse_result(raw_data: str, container_no: str, booking_no: str) -> dict:
    try:
        data = json.loads(raw_data)
    except json.JSONDecodeError:
        return {"success": True, "data": f"Raw:\n{raw_data[:3000]}", "error": ""}

    if data.get("msgID") == "01":
        result = data.get("result", "")
        return {
            "success": True,
            "data": (
                f"Ningbo Port - Result\n"
                f"{'-' * 50}\n"
                f"{result}"
            ),
            "error": "",
        }

    results = data.get("result", [])
    if not results:
        return {
            "success": True,
            "data": (
                f"Ningbo Port - {container_no}\n"
                f"{'-' * 50}\n"
                f"No data found"
            ),
            "error": "",
        }

    lines = []
    for i, r in enumerate(results):
        ctn = r.get("ctnNo", container_no)
        bl = r.get("blno", booking_no)
        direct = _DIRECT_MAP.get(r.get("direct", ""), r.get("direct", ""))
        terminal = _TERMINAL_MAP.get(r.get("terminal", ""), r.get("terminal", "--"))
        status = _STATUS_MAP.get(r.get("status", ""), r.get("status", "--"))

        if len(results) > 1:
            lines.append(f"\n{'=' * 50}")
            lines.append(f"Result #{i + 1}")

        lines.append(f"\n{ctn}")
        lines.append(f"{'-' * 50}")
        lines.append(f"Direction:  {direct or '--'}")
        lines.append(f"Terminal:   {terminal}")
        lines.append(f"Status:     {status}")
        lines.append(f"Size/Type:  {_safe(r.get('ctnSizeType'))}")
        lines.append(f"Owner:      {_safe(r.get('ctnOwner'))}")
        lines.append(f"Seal No:    {_safe(r.get('sealNo'))}")
        lines.append(f"Gross(KG):  {_safe(r.get('grossWeight'))}")
        lines.append(f"Vessel:     {_safe(r.get('vesselEname'))}")
        lines.append(f"Voyage:     {_safe(r.get('voyage'))}")
        lines.append(f"Port:       {_safe(r.get('dlPortCode'))}")

        lines.append(f"\n[Time]")
        lines.append(f"ETA:        {_fmt_time(r.get('etaArrivedTime'))}")
        lines.append(f"ETD:        {_fmt_time(r.get('etaSailingTime'))}")
        lines.append(f"ATA:        {_fmt_time(r.get('arrivalTime'))}")
        lines.append(f"ATD:        {_fmt_time(r.get('sailingTime'))}")

        bills = r.get("bills", [])
        if bills:
            for b in bills:
                lines.append(f"\n[BL {b.get('blno', '--')}]")
                lines.append(f"  Pkgs: {_safe(b.get('packageNum'))}")
                lines.append(f"  Wt: {_safe(b.get('weight'))} KG")
                lines.append(f"  Vol: {_safe(b.get('measure'))} CBM")

        costco = r.get("costco", {})
        if costco.get("status"):
            lines.append(f"\n[Stuffed]")
            lines.append(f"  Status: {_COSTCO_STATUS_MAP.get(costco['status'], costco['status'])}")
            lines.append(f"  Time: {_fmt_time(costco.get('operateTime'))}")

        discharge = r.get("discharge", {})
        if discharge.get("status"):
            lines.append(f"\n[Discharge]")
            lines.append(f"  Status: {_DISCHARGE_STATUS_MAP.get(discharge['status'], discharge['status'])}")
            lines.append(f"  Time: {_fmt_time(discharge.get('operateTime'))}")

        load_data = r.get("load", {})
        if load_data.get("status"):
            lines.append(f"\n[Load]")
            lines.append(f"  Status: {_LOAD_STATUS_MAP.get(load_data['status'], load_data['status'])}")
            lines.append(f"  Time: {_fmt_time(load_data.get('operateTime'))}")

        ingate = r.get("ingate", {})
        if ingate.get("status"):
            lines.append(f"\n[In-gate]")
            lines.append(f"  Status: {_INGATE_STATUS_MAP.get(ingate['status'], ingate['status'])}")
            lines.append(f"  Time: {_fmt_time(ingate.get('operateTime'))}")
            if ingate.get("truckNo"):
                lines.append(f"  Truck: {ingate['truckNo']}")

        outgate = r.get("outgate", {})
        if outgate.get("status"):
            lines.append(f"\n[Out-gate]")
            lines.append(f"  Status: {_OUTGATE_STATUS_MAP.get(outgate['status'], outgate['status'])}")
            lines.append(f"  Time: {_fmt_time(outgate.get('operateTime'))}")
            if outgate.get("truckNo"):
                lines.append(f"  Truck: {outgate['truckNo']}")

        custpass = r.get("custpass", {})
        if custpass.get("status"):
            lines.append(f"\n[Customs Release]")
            lines.append(f"  Status: {_CUSTPASS_MAP.get(custpass.get('remark', ''), custpass.get('remark', ''))}")
            lines.append(f"  Time: {_fmt_time(custpass.get('operateTime'))}")

        npp = r.get("npp", {})
        if npp.get("status"):
            lines.append(f"\n[Paperless]")
            lines.append(f"  Status: {_NPP_STATUS_MAP.get(npp['status'], npp['status'])}")
            lines.append(f"  OpTime: {_fmt_time(npp.get('operateTime'))}")
            lines.append(f"  CmpTime: {_fmt_time(npp.get('compareTime'))}")

        cusmov = r.get("cusmov", {})
        if cusmov.get("status") and cusmov["status"] not in ("N", ""):
            lines.append(f"\n[Customs Inspection]")
            stat = _CUSMOV_STATUS_MAP.get(cusmov["status"], cusmov["status"])
            lines.append(f"  Status: {stat}")
            lines.append(f"  Time: {_fmt_time(cusmov.get('operateTime'))}")
            if cusmov.get("isCheck986"):
                lines.append(f"  986 Status: {_CHECK986_MAP.get(cusmov['isCheck986'], cusmov['isCheck986'])}")

        cusret = r.get("cusretrec", {})
        if cusret.get("resultCode"):
            lines.append(f"\n[Arrival Receipt]")
            lines.append(f"  Time: {_fmt_time(cusret.get('receiveTime'))}")
            if cusret.get("resultDescripts"):
                lines.append(f"  Desc: {cusret['resultDescripts']}")

    lines.append(f"\n{'-' * 50}")
    lines.append(f"Source: Ningbo Port EDI (api.npedi.com:8888)")

    return {"success": True, "data": "\n".join(lines), "error": ""}


# =============================================================================
# Login helpers
# =============================================================================

_ocr = None
_ppll = None


def _get_ocr():
    global _ocr
    if _ocr is None:
        try:
            import ddddocr
            _ocr = ddddocr.DdddOcr(show_ad=False)
        except Exception as e:
            _log(f"[NPEDI] ddddocr 加载失败: {e}")
            _ocr = False  # sentinel: don't retry
    return _ocr if _ocr else None


def _get_pplocr():
    global _ppll
    if _ppll is None:
        try:
            import sys as _sys
            _ppll_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "_ppllocr")
            if _ppll_dir not in _sys.path:
                _sys.path.insert(0, _ppll_dir)
            from ppllocr import OCR as PpllOCR
            _ppll = PpllOCR()
        except Exception:
            _log("[NPEDI] ppllocr import failed, falling back to ddddocr")
            _ppll = None
    return _ppll


def _fill_input(page, keyword: str, value: str) -> bool:
    """Fill a visible input whose placeholder contains keyword."""
    return page.evaluate('(args) => { ' +
        'const kw = args.kw, val = args.val; ' +
        'const inputs = document.querySelectorAll("input"); ' +
        'for (const inp of inputs) { ' +
        'if (inp.offsetParent !== null && inp.type !== "hidden") { ' +
        'const p = (inp.placeholder || "").toLowerCase(); ' +
        'if (p.includes(kw.toLowerCase())) { ' +
        'const s = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set; ' +
        's.call(inp, val); ' +
        'inp.dispatchEvent(new Event("input", {bubbles: true})); ' +
        'inp.dispatchEvent(new Event("change", {bubbles: true})); ' +
        'return true; } } } return false; }',
        {"kw": keyword, "val": value})


def _npedi_login(page, mobile: str, sms_session_id: str) -> str | None:
    from backend.rpa.sms_bridge import wait_for_sms

    _log("[NPEDI] 开始登录流程...")
    _log(f"[NPEDI] 手机号: {mobile[:3]}****{mobile[-4:]}")

    # Step 1: go to login page, wait for JS to render
    page.goto("https://www.npedi.com/index", wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(8000)
    _log("[NPEDI] 页面已加载")

    # Debug: print visible buttons
    debug_btns = page.evaluate(
        '() => { const b = document.querySelectorAll("button"); '
        'return Array.from(b).filter(x => x.offsetParent !== null).map(x => (x.innerText||"").trim()).join(" | "); }'
    )
    _log(f"[NPEDI] 可见按钮: [{debug_btns}]")

    # Step 2: click login button with retry
    _log("[NPEDI] 正在点击登录按钮...")
    login_clicked = False
    for retry in range(3):
        # Debug: print all visible button text
        debug_btns = page.evaluate(
            '() => { const b = document.querySelectorAll("button"); '
            'return Array.from(b).filter(x => x.offsetParent !== null).map(x => (x.innerText||"").trim()).join(" | "); }'
        )
        _log(f"[NPEDI] 可见按钮: [{debug_btns}]")

        page.evaluate(
            '() => { const b = document.querySelectorAll("button"); '
            'for (const x of b) { if ((x.innerText||"").trim() === "登录" && x.offsetParent !== null) { x.click(); return true; } } return false; }'
        )
        page.wait_for_timeout(3000)
        # Check if login dialog appeared — look for any button containing "手机"
        has_dialog = page.evaluate(
            '() => { const b = document.querySelectorAll("button"); '
            'for (const x of b) { if ((x.innerText||"").includes("手机") && x.offsetParent !== null) { return true; } } return false; }'
        )
        if has_dialog:
            login_clicked = True
            _log("[NPEDI] 登录弹窗已打开")
            break
        _log(f"[NPEDI] 登录弹窗未出现，重试第{retry+1}次...")
    if not login_clicked:
        _log("[NPEDI] 登录弹窗打开失败")
        return None
    page.wait_for_timeout(3000)

    # Step 3: click phone login tab
    _log("[NPEDI] 正在切换到手机号登录...")
    for retry in range(3):
        page.evaluate(
            '() => { const b = document.querySelectorAll("button"); '
            'for (const x of b) { '
            'if ((x.innerText||"").includes("手机") && x.offsetParent !== null) '
            '{ x.click(); return true; } } return false; }'
        )
        page.wait_for_timeout(1500)
        # Check if phone input appeared (should be an input in the dialog)
        phone_inputs = page.evaluate(
            '() => { let n=0; for(const i of document.querySelectorAll("input")){if(i.offsetParent!==null&&i.type!=="hidden")n++} return n; }'
        )
        if phone_inputs >= 2:
            _log("[NPEDI] 已切换到手机号登录")
            break
    page.wait_for_timeout(1000)

    # Step 4: fill phone number by placeholder (same as demo)
    _log("[NPEDI] 填入手机号...")
    page.locator('input[placeholder*="请输入手机号"]').fill(mobile)
    page.wait_for_timeout(1000)
    _log("[NPEDI] 手机号已填入")

    # Step 5: get + recognize image captcha from page IMG element (NOT API)
    _log("[NPEDI] 获取页面验证码图片...")
    page.wait_for_timeout(1500)

    _log("[NPEDI] 开始识别图形验证码...")

    ocr = _get_ocr()
    if ocr is None:
        # OCR不可用（cv2/Python 3.14兼容性问题），提示用户手动输入
        _log("[NPEDI] OCR引擎不可用(CV2兼容性)，请手动输入验证码")
        from backend.rpa.sms_bridge import wait_for_sms
        captcha_text = ""
        return {"success": False, "data": "", "error": "图形验证码OCR不可用，请稍后重试或联系管理员升级CV2"}

    for attempt in range(10):
        # 点击验证码图片刷新（与演示脚本一致的定位方式）
        page.evaluate(
            '() => {const imgs=document.querySelectorAll("img");'
            'for(const img of imgs){'
            'const r=img.getBoundingClientRect();'
            'if(r.width>50&&r.width<200&&r.top>200){img.click();return;}}}'
        )
        page.wait_for_timeout(2000)

        # 截图验证码（与演示脚本一致）
        img_box = page.evaluate(
            '() => {const imgs=document.querySelectorAll("img");'
            'for(const img of imgs){'
            'const r=img.getBoundingClientRect();'
            'if(r.width>50&&r.width<200&&r.top>200){'
            'return{"x":r.x,"y":r.y,"w":r.width,"h":r.height}}}}'
        )
        if not img_box:
            _log(f"[NPEDI] 未找到验证码图片（第{attempt+1}次）")
            page.wait_for_timeout(2000)
            continue

        clip = {'x': img_box['x'], 'y': img_box['y'], 'width': img_box['w'], 'height': img_box['h']}
        ss = page.screenshot(clip=clip)

        # Use both OCR engines like demo: ppllocr preferred when 4 chars
        ppl = _get_pplocr()
        ddd_result = ocr.classification(ss).strip()
        ppl_result = ppl.classification(ss) if ppl else ""
        _log(f"[NPEDI] OCR ddd=[{ddd_result}] ppl=[{ppl_result}]")

        captcha_text = (ppl_result if len(ppl_result) == 4 else ddd_result[:4])
        if len(captcha_text) < 3:
            _log(f"[NPEDI] OCR结果太短: [{captcha_text}]，重试...")
            page.wait_for_timeout(1500)
            continue

        _log(f"[NPEDI] 使用验证码: [{captcha_text}]")

        # Fill into 2nd visible input (captcha field) - use locator.fill() like demo
        page.locator("input").nth(1).fill("")
        page.wait_for_timeout(200)
        page.locator("input").nth(1).fill(captcha_text)
        page.wait_for_timeout(500)
        _log(f"[NPEDI] 验证码已填入: [{captcha_text}]")

        # Step 6: click send SMS - exact match on "获取验证码"
        page.evaluate(
            '() => { const a = document.querySelectorAll("button"); ' +
            'for (const el of a) { ' +
            'if (el.innerText.trim() === "获取验证码" && ' +
            'el.offsetParent !== null) { el.click(); return; } } }'
        )
        page.wait_for_timeout(3000)

        # Check if SMS was actually sent (like demo does)
        body_text = page.evaluate("() => document.body.innerText")
        btn_text = page.evaluate(
            "() => { const a = document.querySelectorAll('button'); "
            "for (const el of a) { "
            "const t = el.innerText.trim(); "
            "if (t.includes('验证码') || t.includes('重新获取')) return t; "
            "} return ''; }"
        )
        _log(f"[NPEDI] 短信状态检测: 成功={'发送成功' in body_text} "
             f"错误={'验证码错误' in body_text} 按钮=[{btn_text}]")

        if "发送成功" in body_text:
            _log(f"[NPEDI] 短信发送成功（第{attempt+1}次尝试）")
            break
        elif "验证码错误" in body_text:
            _log(f"[NPEDI] 验证码错误，重试（第{attempt+1}次）...")
            page.wait_for_timeout(1500)
            continue
        else:
            # Button text after sending shows countdown like "58秒后重发"
            if any(kw in btn_text for kw in ("重新获取", "秒后", "秒")):
                _log(f"[NPEDI] 短信已发送！按钮: [{btn_text}]")
                break
            # Also check body for countdown pattern: digits + "秒" nearby
            import re
            countdown_match = re.search(r'\d{1,2}秒', body_text)
            if countdown_match:
                _log(f"[NPEDI] 短信已发送！找到倒计时: [{countdown_match.group()}]")
                break
            _log(f"[NPEDI] 短信状态未知，重试（第{attempt+1}次）...")
            page.wait_for_timeout(1500)
            continue

    else:
        _log("[NPEDI] 验证码识别失败，已达上限")
        return None

    # SMS sent successfully — now wait for user code
    _log("[NPEDI] 短信已发送，等待用户输入验证码...")

    # Step 7: wait for SMS code from user
    sms_code = wait_for_sms(sms_session_id, timeout=120)

    if not sms_code:
        _log("[NPEDI] 等待验证码超时")
        return None

    _log("[NPEDI] 获取到短信验证码，正在登录...")

    # Step 8: fill SMS code into 3rd visible input (id="smsCodeinp") - use locator.fill()
    page.locator("input").nth(2).fill(sms_code)
    page.wait_for_timeout(500)
    _log("[NPEDI] 短信验证码已填入，点击登录...")

    # Step 9: click login submit button（弹窗内最后一个可见的"登录"）
    page.evaluate(
        '() => { const b = document.querySelectorAll("button"); '
        'let last = null; '
        'for (const x of b) { '
        'if (x.innerText.trim() === "登录" && x.offsetParent !== null) { last = x; } '
        '} if (last) last.click(); }'
    )
    page.wait_for_timeout(3000)
    _log("[NPEDI] 正在登录...")

    # Step 10: wait for Web-Token cookie
    for i in range(30):
        page.wait_for_timeout(1000)
        cookies = page.context.cookies()
        for c in cookies:
            if c["name"] == "Web-Token":
                token = c["value"]
                _log("[NPEDI] 登录成功！")
                _save_token(token)
                _save_auth_state(page)
                _save_mobile(mobile)
                return token
        if i % 5 == 0:
            _log(f"[NPEDI] 等待登录中 {i+1}s...")

    _log("[NPEDI] 登录超时")
    page.wait_for_timeout(2000)
    cookies = page.context.cookies()
    for c in cookies:
        if c["name"] == "Web-Token":
            token = c["value"]
            _log("[NPEDI] Login successful!")
            _save_token(token)
            _save_auth_state(page)
            _save_mobile(mobile)
            return token
    return None


# =============================================================================
# Browser query — visit npedi.com directly to fetch container data
# =============================================================================


def _browser_query(page, container_no: str, booking_no: str = "",
                   vessel_name: str = "", voyage_no: str = "") -> dict:
    """通过浏览器直接访问 npedi.com 查询集装箱数据（不依赖 EDI API）。"""
    # Step A: Container tracking via direct URL
    _log("[NPEDI] 导航到容器物流跟踪...")
    page.goto("https://www.npedi.com/onesite/container/track", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(8000)

    # Fill container number (2nd visible visible input = 集装箱号)
    _log(f"[NPEDI] 填入柜号: {container_no}")
    page.evaluate("""(args) => {
        const inps = document.querySelectorAll('input:not([type=hidden])');
        let cnt = 0;
        for (const inp of inps) {
            if (inp.offsetParent !== null) {
                if (cnt === 0) { cnt++; continue; }  // skip Search bar
                const s = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
                s.call(inp, args);
                inp.dispatchEvent(new Event('input', {bubbles: true}));
                inp.dispatchEvent(new Event('change', {bubbles: true}));
                return;
            }
        }
    }""", container_no)

    # Fill booking number (3rd visible input = 提单号)
    if booking_no:
        _log(f"[NPEDI] 填入提单号: {booking_no}")
        page.evaluate("""(args) => {
            const inps = document.querySelectorAll('input:not([type=hidden])');
            let cnt = 0;
            for (const inp of inps) {
                if (inp.offsetParent !== null) {
                    cnt++;
                    if (cnt < 3) continue;  // wait for 3rd visible
                    const s = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
                    s.call(inp, args);
                    inp.dispatchEvent(new Event('input', {bubbles: true}));
                    inp.dispatchEvent(new Event('change', {bubbles: true}));
                    return;
                }
            }
        }""", booking_no)

    page.wait_for_timeout(1000)

    # Click 搜索 button
    _log("[NPEDI] 点击查询...")
    btn = page.locator('button:has-text("搜索")')
    if btn.is_visible():
        btn.click()
    else:
        page.evaluate("""()=>{
            const b = document.querySelectorAll('button');
            for (const el of b) {
                if ((el.innerText||'').trim()==='搜索' && el.offsetParent !== null) {
                    el.click(); return;
                }
            }
        }""")
    page.wait_for_timeout(8000)

    # Read tracking results
    track_content = page.evaluate("""() => {
        const text = document.body.innerText;
        const lines = text.split('\\n');
        let start = -1;
        for (let i = 0; i < lines.length; i++) {
            const t = (lines[i] || '').trim();
            if (t === '箱信息' || t === '箱号') { start = i; break; }
        }
        if (start > 0) return lines.slice(start).join('\\n');
        return text;
    }""")

    # Extract tables for the time line section
    track_tables = page.evaluate("""()=>{
        const t = document.querySelectorAll('table');
        let o = '';
        for (let i = 0; i < Math.min(t.length, 5); i++) {
            const rows = t[i].querySelectorAll('tr');
            const r = [];
            for (const row of rows) {
                const c = row.querySelectorAll('td,th');
                const txt = Array.from(c).map(x => (x.innerText || '').trim()).join(' | ');
                if (txt.replace(/[\\|\\s]/g, '').length > 0) r.push(txt);
            }
            if (r.length >= 1) { o += '\\nTable ' + (i + 1) + ':\\n'; o += r.join('\\n'); }
        }
        return o;
    }""")
    _log(f"[NPEDI] 物流跟踪结果: {len(track_content)} 字符，时间线: {len(track_tables)} 字符")

        # =========================================================================
    # Step B: 进箱公告 (失败不影响物流跟踪结果)
    # =========================================================================
    vessel_main = ""
    vessel_tables = ""
    has_vessel_filter = False
    try:
        _log("[NPEDI] 导航到进箱公告...")
        page.goto("https://www.npedi.com/onesite/vessel/dailyZyjh", wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(5000)

        current_url = page.url
        _log(f"[NPEDI] 进箱公告页面URL: {current_url}")
        if "login" in current_url.lower():
            _log("[NPEDI] 被重定向到登录页，跳过进箱公告")
        else:
            try:
                page.wait_for_selector('input', timeout=10000)
                _log("[NPEDI] 进箱公告页面已渲染")
            except Exception:
                _log("[NPEDI] 进箱公告页面未检测到输入框")
                page.wait_for_timeout(3000)

            if vessel_name:
                _log(f"[NPEDI] 填入船名: {vessel_name}")
                try:
                    page.locator('input[placeholder*="船名"]').fill(vessel_name, timeout=5000)
                except Exception:
                    _log("[NPEDI] 船名输入框未找到，使用备用方法")
                    inputs = page.locator('input').all()
                    if len(inputs) > 0:
                        inputs[0].fill(vessel_name)

            if voyage_no:
                _log(f"[NPEDI] 填入航次: {voyage_no}")
                try:
                    page.locator('input[placeholder*="航次"]').fill(voyage_no, timeout=5000)
                except Exception:
                    _log("[NPEDI] 航次输入框未找到，使用备用方法")
                    inputs = page.locator('input').all()
                    if len(inputs) > 1:
                        inputs[1].fill(voyage_no)
                    elif len(inputs) > 0:
                        inputs[0].fill(voyage_no)

            if vessel_name or voyage_no:
                _log("[NPEDI] 点击进箱公告查询...")
                try:
                    page.locator('button:has-text("查询")').click(timeout=5000)
                except Exception:
                    page.evaluate("""()=>{
                        const b = document.querySelectorAll('button.el-button--primary.el-button--mini');
                        for (const el of b) {
                            if ((el.innerText||'').trim()==='查询' && el.offsetParent !== null) {
                                el.click(); return;
                            }
                        }
                    }""")
                page.wait_for_timeout(8000)

            has_vessel_filter = bool(vessel_name or voyage_no)
            if has_vessel_filter:
                vessel_main = page.evaluate("""() => {
                    const text = document.body.innerText;
                    const lines = text.split('\\n');
                    let start = -1;
                    for (let i = 0; i < lines.length; i++) {
                        const t = (lines[i] || '').trim();
                        if (t.startsWith('首页') || t.includes('首页/')) { start = i; break; }
                    }
                    if (start <= 0) return text;
                    return lines.slice(start).join('\\n');
                }""")
                _log(f"[NPEDI] 进箱公告: {len(vessel_main)} 字符")
                vessel_tables = page.evaluate("""()=>{
                    const t = document.querySelectorAll('table');
                    let o = '';
                    for (let i = 0; i < Math.min(t.length, 5); i++) {
                        const rows = t[i].querySelectorAll('tr');
                        const r = [];
                        for (const row of rows) {
                            const c = row.querySelectorAll('td,th');
                            const txt = Array.from(c).map(x => (x.innerText || '').trim()).join(' | ');
                            if (txt.replace(/\\|/g, '').trim()) { r.push(txt); }
                        }
                        if (r.length >= 2) { o += '\\nTable ' + (i + 1) + ':\\n'; o += r.join('\\n'); }
                    }
                    return o;
                }""")
    except Exception as e:
        _log(f"[NPEDI] 进箱公告查询失败（物流跟踪结果已保存）: {e}")

# =========================================================================
    # Compile output
    # =========================================================================
    lines = [
        f"宁波港 - {container_no}",
        f"{'=' * 50}",
        "",
        "【容器物流跟踪】",
        f"{'-' * 50}",
    ]
    lines.append(track_content[:4000])
    if track_tables:
        lines.append("")
        lines.append("【时间线】")
        lines.append(track_tables[:2000])

    lines.append("")
    lines.append("【进箱公告】")
    lines.append(f"{'-' * 50}")
    if has_vessel_filter and vessel_tables:
        lines.append(vessel_tables[:5000])
    elif has_vessel_filter:
        lines.append(vessel_main[:3000])
    else:
        lines.append("（未填写船名/航次，跳过进箱公告）")

    lines.append("")
    lines.append(f"{'─' * 50}")
    lines.append("数据来源: 宁波港口EDI中心 (npedi.com)")

    return {"success": True, "data": "\n".join(lines), "error": ""}


# =============================================================================
# Main driver
# =============================================================================


@register("宁波港")
class NingboPort:
    """Ningbo port container status query - semi-auto login + EDI API."""

    @staticmethod
    def query_container(page, params: dict) -> dict:
        container_no = params.get("container_no", "").strip().upper()
        booking_no = params.get("booking_no", "").strip()
        mobile = params.get("npedi_mobile", "").strip()
        sms_session_id = params.get("sms_session_id", "")

        if not container_no:
            return {"success": False, "data": "", "error": "Please enter container number"}

        # Skip SMS re-login if we already have auth state to try browser path
        had_auth_state = _load_auth_state()
        if had_auth_state:
            _log("[NPEDI] 尝试使用已有浏览器登录态直接查询...")
            try:
                result = _browser_query(page, container_no, booking_no,
                                        vessel_name=params.get("vessel_name", ""),
                                        voyage_no=params.get("voyage_no", ""))
                if result.get("success"):
                    return result
                _log(f"[NPEDI] 浏览器查询失败，尝试登录: {result.get('error', '')}")
            except Exception as e:
                _log(f"[NPEDI] 浏览器查询异常: {e}")

        # 1. Try existing token via API
        token = _load_token()
        if token and not sms_session_id:
            api_params = {
                "ctnNo": container_no,
                "blno": booking_no,
                "vesselCode": "", "voyage": "",
                "vesselEname": "", "terminal": "", "direct": "",
            }
            result = _call_api(api_params, token)
            if result["success"]:
                return _parse_result(result["raw"], container_no, booking_no)
            _log(f"[NPEDI] API token expired ({result.get('error', 'unknown')})")

        # 2. Login needed — SMS flow
        if not mobile:
            mobile = _load_mobile()
        if not mobile:
            return {
                "success": False,
                "data": "",
                "error": "Please enter phone number (Ningbo port needs SMS login)",
            }

        if not sms_session_id:
            return {
                "success": False,
                "data": "",
                "error": "__SMS_REQUIRED__",
                "sms_session_created": True,
            }

        token = _npedi_login(page, mobile, sms_session_id)
        if not token:
            return {"success": False, "data": "", "error": "Ningbo port login failed"}

        # Now query via browser (after fresh login)
        return _browser_query(page, container_no, booking_no,
                              vessel_name=params.get("vessel_name", ""),
                              voyage_no=params.get("voyage_no", ""))

        # 2. Login needed
        if not mobile:
            mobile = _load_mobile()
        if not mobile:
            return {
                "success": False,
                "data": "",
                "error": "Please enter phone number (Ningbo port needs SMS login)",
            }

        if not sms_session_id:
            return {
                "success": False,
                "data": "",
                "error": "__SMS_REQUIRED__",
                "sms_session_created": True,
            }

        return _browser_query(page, container_no, booking_no,
                              vessel_name=params.get("vessel_name", ""),
                              voyage_no=params.get("voyage_no", ""))
