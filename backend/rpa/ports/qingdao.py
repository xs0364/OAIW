"""
青岛港 (qingdao-port.net / 云港通) RPA 驱动

云港通是青岛港（山东港口）官方平台，使用 Nuxt.js SPA + iView 子应用 tycxtrack。

功能:
  1. 单箱查询 — 通过 wmdx 子系统查询集装箱物流状态
  2. 船期计划 — 通过 cbjh 子系统获取集装箱船舶计划

登录: 账号密码 + ddddocr 自动识别图形验证码
认证: JWT token (qdport-token) 保存在 cookies
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from backend.rpa.ports import register

# =============================================================================
# 全局 ddddocr 实例（只初始化一次，懒加载）
# =============================================================================
_ocr = None


def _get_ocr():
    global _ocr
    if _ocr is None:
        try:
            import ddddocr
            _ocr = ddddocr.DdddOcr(show_ad=False)
        except Exception as e:
            print(f"[QINGDAO] ddddocr 加载失败: {e}")
            _ocr = False
    return _ocr if _ocr else None


# =============================================================================
# 常量
# =============================================================================

BASE_URL = "https://www.qingdao-port.net"
API_BASE = f"{BASE_URL}/api/web/oceantally"
_AUTH_STATE_PATH = Path(__file__).parent / "qd_auth_state.json"
QD_USERNAME = os.environ.get("QD_PORT_USERNAME", "19972888366")
QD_PASSWORD = os.environ.get("QD_PORT_PASSWORD", "@Xs030604.")

# 船期计划可用的终端码头
TERMINALS = ["QQCT", "QQCTU", "QQCTN"]


# =============================================================================
# 登录态管理
# =============================================================================


def _load_auth_state() -> dict | None:
    """从磁盘加载保存的登录态。"""
    if _AUTH_STATE_PATH.exists():
        try:
            return json.loads(_AUTH_STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None


def _save_auth_state(page):
    """保存当前登录态到磁盘。"""
    try:
        storage = page.context.storage_state()
        _AUTH_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _AUTH_STATE_PATH.write_text(
            json.dumps(storage, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"  [OK] 青岛港登录态已保存")
    except Exception as e:
        print(f"  [!] 保存登录态失败: {e}")


def _is_logged_in(page) -> bool:
    """检查当前页面是否已登录（页面文字 + API 验证双重确认）。"""
    # 1. 页面文字快速检查
    try:
        text = page.inner_text("body")
        if "退出" not in text and "个人中心" not in text and "工作台" not in text:
            return False
    except Exception:
        return False

    # 2. API 验证：调一个轻量接口确认 token 有效
    try:
        resp = page.evaluate("""async () => {
            try {
                const r = await fetch('/api/web/user/member/getUserData.do', {
                    credentials: 'include',
                });
                return { status: r.status, ok: r.ok };
            } catch(e) { return { status: 0, ok: false, error: e.message }; }
        }""")
        if resp and (resp.get("status") == 200 or resp.get("ok")):
            return True
        api_status = resp.get("status", "?")
        print(f"  [!] API 验证失败 (status={api_status})，token 可能过期", flush=True)
        return False
    except Exception as e:
        print(f"  [!] API 验证异常: {e}", flush=True)
        return False


# =============================================================================
# 登录流程（账号密码 + ddddocr 验证码）
# =============================================================================


def _login_get_captcha(page) -> str | None:
    """从页面获取验证码图片，用 ddddocr 自动识别。"""
    import base64

    captcha_b64 = page.evaluate("""async () => {
        const img = document.querySelector('img.captcha');
        if (!img || !img.src || !img.src.startsWith('blob:')) return null;
        try {
            const resp = await fetch(img.src);
            const blob = await resp.blob();
            return new Promise((resolve) => {
                const reader = new FileReader();
                reader.onload = () => resolve(reader.result);
                reader.readAsDataURL(blob);
            });
        } catch(e) { return null; }
    }""")

    if not captcha_b64:
        print("  [X] 获取验证码失败")
        return None

    b64_data = captcha_b64.split(",")[1] if "," in captcha_b64 else captcha_b64
    img_bytes = base64.b64decode(b64_data)

    ocr = _get_ocr()
    captcha_text = ocr.classification(img_bytes).strip()

    if captcha_text and len(captcha_text) >= 3:
        print(f"  [LOCK] 验证码自动识别: [{captcha_text}]")
        return captcha_text

    # 自动识别失败 → API 模式跳过手动输入
    import tempfile
    captcha_file = Path(tempfile.gettempdir()) / "qdport_captcha.jpg"
    captcha_file.write_bytes(img_bytes)
    print(f"  [!] 自动识别失败，验证码已保存到 {captcha_file}")
    print(f"  [!] API 模式跳过手动输入验证码")
    return None


def _do_login(page) -> bool:
    """执行青岛港完整登录流程。"""
    print("\n[KEY] 青岛港登录流程...", flush=True)

    MAX_RETRIES = 5

    for attempt in range(1, MAX_RETRIES + 1):
        if attempt > 1:
            print(f"\n[RETRY] 第 {attempt} 次重试...")

        # 打开首页 → 点击登录
        page.goto(BASE_URL, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        page.evaluate("""() => {
            for (const el of document.querySelectorAll('span, a, div, button'))
                if (el.innerText.trim() === '登录') { el.click(); return; }
        }""")
        page.wait_for_timeout(3000)

        # 填入账号密码
        page.fill("#form_item_username", QD_USERNAME)
        page.fill("#form_item_password", QD_PASSWORD)
        print(f"  [OK] 账号已填入: {QD_USERNAME}")

        # 验证码识别
        page.wait_for_timeout(1000)
        captcha_text = _login_get_captcha(page)
        if not captcha_text:
            continue
        page.fill("#form_item_captcha", captcha_text)

        # 勾选自动登录 + 点击登录
        page.evaluate("""() => {
            const cb = document.querySelector('.ant-checkbox-input');
            if (cb && !cb.checked) cb.click();
        }""")
        page.wait_for_timeout(500)
        page.evaluate("""() => {
            const btn = document.querySelector('button.ant-btn-primary');
            if (btn) btn.click();
        }""")

        # 等待登录成功
        print("  [WAIT] 等待登录结果...")
        for _ in range(30):
            page.wait_for_timeout(1000)
            try:
                if _is_logged_in(page):
                    print("  [OK] 登录成功！")
                    _save_auth_state(page)
                    return True
            except Exception:
                pass

        print(f"  [X] 第 {attempt} 次登录失败")

    print("  [X] 登录失败，已达最大重试次数")
    return False


def _ensure_logged_in(page) -> bool:
    """确保已登录，未登录则执行登录流程。"""
    state = _load_auth_state()
    has_saved_cookies = False
    if state:
        cookies = state.get("cookies", [])
        if cookies:
            try:
                page.context.add_cookies(cookies)
                has_saved_cookies = True
            except Exception:
                pass

    if not has_saved_cookies:
        print("  [+] 无已保存的登录态，执行完整登录...", flush=True)
        if not _do_login(page):
            return False
    else:
        # 有 cookies，验证是否有效
        print("  [+] 验证登录态是否有效...", flush=True)
        page.goto(BASE_URL, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        try:
            logged_in = _is_logged_in(page)
        except Exception:
            logged_in = False

        if not logged_in:
            print("  [KEY] 登录态失效，重新登录...")
            if not _do_login(page):
                return False
        else:
            print("  [+] 登录态有效", flush=True)

    # 导航到 tycxtrack 子应用
    print("  [+] 导航到 tycxtrack 查询应用...", flush=True)
    try:
        page.goto(f"{BASE_URL}/web/tycxtrack/index.html?20240819", timeout=30000)
        page.wait_for_timeout(5000)
    except Exception as e:
        print(f"  [!] 导航到 tycxtrack 失败: {e}", flush=True)
        return False

    print("  [+] 青岛港登录态检查完成", flush=True)
    return True


# =============================================================================
# 单箱查询 — 通过 wmdx 子系统
# =============================================================================

_WMDX_SECTION_TITLES = {
    "mtxxListck": "出口-码头信息",
    "mtxxListcm": "进口-码头信息",
    "xgzList": "箱跟踪",
    "hgbgList": "海关报关单放行",
    "zcfxList": "装载放行",
    "zxdBgList": "装箱单信息",
    "zxdList": "装箱单信息",
    "bgtxList": "报关提醒",
    "ydbgList": "运抵报告",
    "wlshList": "外理审核放行",
    "qtList": "其他",
    "mxList": "明细",
}


def _query_container(page, container_no: str) -> dict:
    """
    执行单箱查询 — 导航到 wmdx 页面，输入柜号，拦截 API 响应。

    Returns:
        dict: {"success": bool, "data": str, "error": str}
    """
    query_url = f"{BASE_URL}/web/tycxtrack/index.html?20240819#/port/wmdx"
    print(f"  [+] 导航到单箱查询页面...", flush=True)
    try:
        page.goto(query_url, timeout=30000, wait_until="domcontentloaded")
        # 等待 SPA 渲染（hash 路由需要额外时间加载组件）
        page.wait_for_timeout(8000)
    except Exception as e:
        print(f"  [!] 导航到 wmdx 失败: {e}", flush=True)
        return {"success": False, "data": "", "error": f"导航到单箱查询页面失败: {e}"}

    # 确认页面已渲染，等待输入框出现
    print(f"  [+] 等待页面渲染完成...", flush=True)
    for _ in range(10):
        inp_count = page.evaluate("document.querySelectorAll('input.ivu-input').length")
        if inp_count > 0:
            print(f"  [OK] 页面已渲染（{inp_count} 个输入框）", flush=True)
            break
        page.wait_for_timeout(1000)
    else:
        print(f"  [!] 页面渲染超时，继续尝试...", flush=True)

    # 捕获所有相关 API 响应
    api_data = {}

    def _capture_api(resp):
        url = resp.url
        status = resp.status
        if "/api/" in url or ".do" in url:
            if status == 200:
                if "queryWmdx" in url or "wmdx" in url:
                    try:
                        api_data["raw"] = resp.json()
                        print(f"  [API] 捕获到 wmdx 响应 (200)", flush=True)
                    except Exception:
                        pass
                else:
                    # 记录其他 API 用于调试
                    if "debug_api" not in api_data:
                        api_data["debug_api"] = []
                    api_data["debug_api"].append({"url": url, "status": status})
                    print(f"  [API] {status} {url.split('/')[-1][:60]}", flush=True)
            elif status != 200:
                print(f"  [API!] 非200状态: {status} {url.split('/')[-1][:60]}", flush=True)
                api_data["last_error"] = {"url": url, "status": status}

    page.on("response", _capture_api)

    # 输入柜号
    print(f"  [+] 查询柜号: {container_no}", flush=True)
    try:
        inp = page.locator('input[placeholder="请输入箱号"]')
        inp.fill(container_no, timeout=5000)
        print(f"  [+] 柜号已填入（locator）", flush=True)
        page.wait_for_timeout(1000)
    except Exception as e:
        print(f"  [!] locator 填号失败，使用 evaluate fallback: {e}", flush=True)
        # fallback: 通过 evaluate 设值
        page.evaluate("""(val) => {
            for (const inp of document.querySelectorAll('input.ivu-input')) {
                if (inp.placeholder === '请输入箱号') {
                    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                    setter.call(inp, val);
                    inp.dispatchEvent(new Event('input', { bubbles: true }));
                    inp.dispatchEvent(new Event('change', { bubbles: true }));
                    return;
                }
            }
        }""", container_no)
        print(f"  [+] 柜号已填入（evaluate）", flush=True)
        page.wait_for_timeout(1000)

    # 点击查询
    print(f"  [+] 点击查询按钮...", flush=True)
    page.evaluate("""() => {
        for (const el of document.querySelectorAll('button'))
            if (el.innerText.trim() === '查询') { el.click(); return; }
    }""")
    page.wait_for_timeout(3000)

    # 等待 API 响应（最多 20 秒）
    print(f"  [+] 等待查询结果...", flush=True)
    for _ in range(20):
        if api_data.get("raw"):
            print(f"  [OK] 接收到 API 响应", flush=True)
            break
        page.wait_for_timeout(1000)

    # 解析结果
    raw = api_data.get("raw", {})
    if not raw or not raw.get("res"):
        # 兜底：直接从页面 body 抓文本
        print(f"  [!] 未捕获到 API 响应，尝试页面文本兜底...", flush=True)
        try:
            body_text = page.evaluate("document.body.innerText") or ""
            if container_no in body_text:
                return {"success": True, "data": f"青岛港 - 集装箱 {container_no} 查询结果\n\n{body_text[:2000]}", "error": ""}
            print(f"  [DEBUG] body text (200 chars): {body_text[:200]}", flush=True)
        except Exception as e:
            print(f"  [DEBUG] body text 读取失败: {e}", flush=True)
        return {"success": False, "data": "", "error": "单箱查询无返回数据"}

    sections = raw["res"]
    lines = [
        f"📦 青岛港 — 单箱查询结果",
        f"{'─' * 50}",
        f"柜号: {container_no}",
        f"查询时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"",
    ]

    for section in sections:
        sid = section.get("id", "")
        stitle = section.get("title", _WMDX_SECTION_TITLES.get(sid, sid))
        data = section.get("data", [])
        total = section.get("total", 0)

        if not data:
            continue

        lines.append(f"【{stitle}】({total} 条)")

        for row in data:
            # 每行数据是一个 dict，提取所有非空字段
            row_items = []
            if isinstance(row, dict):
                for k, v in row.items():
                    if v is not None and v != "" and v != 0:
                        row_items.append(f"{k}={v}")
            elif isinstance(row, str):
                row_items.append(row)
            if row_items:
                lines.append(f"  {' | '.join(row_items)}")
        lines.append("")

    lines.append(f"{'─' * 50}")
    lines.append(f"数据来源: 青岛港云港通 (qingdao-port.net)")

    return {"success": True, "data": "\n".join(lines), "error": ""}


# =============================================================================
# 船期计划 — 通过 cbjh 子系统
# =============================================================================

_AUTOCOMPLETE_LETTERS = (
    [chr(c) for c in range(ord("A"), ord("Z") + 1)]
    + [str(d) for d in range(10)]
    + ["中", "东"]  # 常用中文开头
)


def _fetch_page_autocomplete(page, term: str, mtmc: str) -> list:
    """通过页面 evaluate 调用 autocomplete API。"""
    data = page.evaluate(f"""async () => {{
        const r = await fetch('{API_BASE}/logistics/mtsearch/cbjhcmcx.do?term={term}&mtmc={mtmc}');
        const text = await r.text();
        try {{ return JSON.parse(text); }} catch(e) {{ return []; }}
    }}""")
    return data if isinstance(data, list) else []


def _fetch_vessel_details_batch(page, vessels: list) -> list:
    """
    批量并行获取船舶详情（分批并行请求，每批20艘）。

    Args:
        page: Playwright page
        vessels: list of dicts with ZWCM, CKHC, CMDM, KBDW fields

    Returns:
        list of detail dicts
    """
    api_url = f"{API_BASE}/logistics/mtsearch/cbjhcx.do"
    BATCH_SIZE = 20
    results = []

    for start in range(0, len(vessels), BATCH_SIZE):
        batch = vessels[start:start + BATCH_SIZE]
        # 构建 JS 代码：并行 fetch
        js_parts = []
        for i, v in enumerate(batch):
            zwcm = v.get("ZWCM", "")
            ckhc = v.get("CKHC", "")
            cmd = v.get("CMDM", "")
            mtmc = v.get("KBDW", "QQCT")
            if mtmc not in TERMINALS:
                mtmc = "QQCT"
            params = {
                "ZWCM": zwcm,
                "CKHC": ckhc,
                "CMDM": cmd,
                "MTMC": mtmc,
                "pageNum": "1",
                "pageSize": "10",
            }
            qs = "&".join(f"{k}={v.replace(' ', '%20')}" for k, v in params.items())
            fetch_url = api_url + "?" + qs
            js_parts.append(f"fetch('{fetch_url}').then(r=>r.json()).then(j=>j&&j.res&&j.res[0]?j.res[0].data||[]:[]).catch(()=>[])")

        js_code = "await Promise.all([" + ",".join(js_parts) + "])"
        batch_results = page.evaluate(f"""async () => {{ return {js_code}; }}""")

        for br in batch_results:
            if isinstance(br, list) and br:
                results.extend(br)

        print(f"     [WAIT] 批量获取详情: {min(start + BATCH_SIZE, len(vessels))}/{len(vessels)}", flush=True)

    return results


def _query_vessel_schedule(page, terminal: str = "") -> dict:
    """
    获取集装箱船舶计划数据。

    流程:
      1. 遍历 A-Z + 0-9 通过 autocomplete 获取所有船舶列表
      2. 按 CMDM (船名代码) 去重
      3. 批量并行获取 ETD 等详细信息

    Args:
        page: Playwright page
        terminal: 码头代码 (QQCT/QQCTU/QQCTN)，空则查询所有码头

    Returns:
        {"success": bool, "data": str, "error": str}
    """
    # 导航到船舶计划页面
    page.goto(f"{BASE_URL}/web/tycxtrack/index.html?20240819#/wlzz/cbjh", timeout=30000)
    page.wait_for_timeout(5000)
    print(f"  [PIN] 导航到船舶计划页面", flush=True)

    # autocomplete 的 mtmc 参数实际上不过滤，只扫一轮即可
    print(f"\n  [SHIP] 扫描所有码头...", flush=True)

    all_vessels = {}  # key=(CMDM, CKHC) → {vessel_info}
    seen_keys = set()
    for letter in _AUTOCOMPLETE_LETTERS:
        results = _fetch_page_autocomplete(page, letter, TERMINALS[0])
        for v in results:
            key = (v.get("CMDM", ""), v.get("CKHC", ""))
            if key not in seen_keys and key != ("", ""):
                seen_keys.add(key)
                all_vessels[key] = v

    print(f"  [DATA] 共获取 {len(all_vessels)} 艘唯一船舶", flush=True)

    # Step 2: 批量并行获取详细信息
    vessel_list = list(all_vessels.values())
    if not vessel_list:
        return {"success": True, "data": "暂无船舶计划数据", "error": ""}

    detailed = _fetch_vessel_details_batch(page, vessel_list)

    # fallback: 对未获取到详情的船舶用 autocomplete 数据
    detailed_cmdm = {(v.get("CMDM", ""), v.get("CKHC", "")) for v in detailed}
    for v in vessel_list:
        key = (v.get("CMDM", ""), v.get("CKHC", ""))
        if key not in detailed_cmdm:
            detailed.append(v)

    # 按 terminal 过滤
    if terminal:
        terminal_upper = terminal.upper()
        detailed = [v for v in detailed if terminal_upper in v.get("KBDW", "").upper()]
        if not detailed:
            print(f"  [!] {terminal} 无数据", flush=True)

    print(f"  [DATA] 最终记录: {len(detailed)} 条", flush=True)

    # Step 3: 格式化输出
    lines = [
        f"🚢 青岛港 — 集装箱船舶计划",
        f"{'─' * 100}",
    ]

    # 按 ETA 排序
    def _get_eta(v):
        eta = v.get("ETA", "")
        if isinstance(eta, (int, float)) and eta > 1000000000000:
            return eta  # 已经是 timestamp ms
        try:
            return datetime.strptime(str(eta)[:19], "%Y-%m-%d %H:%M:%S").timestamp() * 1000
        except Exception:
            return 0

    detailed.sort(key=_get_eta)

    headers = ["中文船名", "英文船名", "进口航次", "出口航次", "码头", "ETA", "ETD", "航线", "船名代码"]
    col_widths = [14, 20, 12, 12, 8, 20, 20, 28, 10]

    def fmt_row(values):
        return "  ".join(f"{v:{w}}" for v, w in zip(values, col_widths))

    lines.append(fmt_row(headers))
    lines.append(fmt_row(["─" * w for w in col_widths]))

    for v in detailed:
        eta = v.get("ETA", "")
        if isinstance(eta, (int, float)) and eta > 1000000000000:
            try:
                eta = datetime.fromtimestamp(eta / 1000).strftime("%m-%d %H:%M")
            except Exception:
                eta = str(eta)
        else:
            eta = str(eta)[:16] if eta else ""

        etd = v.get("ETD", "")
        if isinstance(etd, (int, float)) and etd > 1000000000000:
            try:
                etd = datetime.fromtimestamp(etd / 1000).strftime("%m-%d %H:%M")
            except Exception:
                etd = str(etd)
        else:
            etd = str(etd)[:16] if etd else ""

        row = [
            str(v.get("ZWCM", ""))[:14],
            str(v.get("YWCM", ""))[:20],
            str(v.get("JKHC", ""))[:12],
            str(v.get("CKHC", ""))[:12],
            str(v.get("KBDW", ""))[:8],
            str(eta)[:20],
            str(etd)[:20],
            str(v.get("HXZM", ""))[:28],
            str(v.get("CMDM", ""))[:10],
        ]
        lines.append(fmt_row(row))

    lines.append(f"\n{'─' * 100}")
    lines.append(f"共 {len(detailed)} 条记录")
    lines.append(f"数据来源: 青岛港云港通 (qingdao-port.net)")
    lines.append(f"查询时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    return {"success": True, "data": "\n".join(lines), "error": ""}


# =============================================================================
# 驱动主类
# =============================================================================


@register("青岛港")
class QingdaoPort:
    """青岛港 (云港通) 港口驱动 — 集装箱查询 + 船期计划。"""

    @staticmethod
    def query_container(page, params: dict) -> dict:
        """
        查询集装箱状态（单箱查询）。

        Args:
            page: Playwright page 对象
            params:
                - container_no: 集装箱号（必填）
                - booking_no: 提单号（可选，仅用于显示）

        Returns:
            {"success": bool, "data": str, "error": str}
        """
        container_no = params.get("container_no", "").strip().upper()
        if not container_no:
            return {"success": False, "data": "", "error": "请输入集装箱号"}

        try:
            if not _ensure_logged_in(page):
                return {"success": False, "data": "", "error": "青岛港登录失败"}

            result = _query_container(page, container_no)
            return result

        except Exception as e:
            import traceback
            return {
                "success": False,
                "data": "",
                "error": f"EXCEPTION: {type(e).__name__}: {e}\n{traceback.format_exc()}",
            }

    @staticmethod
    def query_vessel_schedule(page, params: dict) -> dict:
        """
        查询集装箱船舶计划。

        Args:
            page: Playwright page 对象
            params:
                - terminal: 可选，码头代码 (QQCT/QQCTU/QQCTN)，空则查全部

        Returns:
            {"success": bool, "data": str, "error": str}
        """
        terminal = params.get("terminal", "").strip().upper()

        try:
            if not _ensure_logged_in(page):
                return {"success": False, "data": "", "error": "青岛港登录失败"}

            result = _query_vessel_schedule(page, terminal)
            return result

        except Exception as e:
            import traceback
            return {
                "success": False,
                "data": "",
                "error": f"EXCEPTION: {type(e).__name__}: {e}\n{traceback.format_exc()}",
            }
