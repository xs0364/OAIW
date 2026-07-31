"""
盐田港 (156yt.cn) RPA 驱动 — 集装箱状态查询

流程：
1. passport 登录 (j_username + j_password)
2. 访问 publicInfoService → 点"集装箱公众查询" → 新标签页
3. 在新标签页填柜号 → 点查询按钮 → 等待结果
"""

from __future__ import annotations

from backend.rpa.ports import register

YT_USERNAME = "shane"
YT_PASSWORD = "@xs19972888366"


@register("盐田港")
class YantianPort:
    """盐田港集装箱查询驱动。"""

    @staticmethod
    def query_container(page, params: dict) -> dict:
        container_no = params.get("container_no", "").strip().upper()
        booking_no = params.get("booking_no", "").strip()

        if not container_no:
            return {"success": False, "data": "", "error": "请输入集装箱号"}

        ctx = page.context

        try:
            # ===== Step 1: passport 登录 =====
            _login(page)

            # ===== Step 2: 导航到 publicInfoService =====
            page.goto(
                "https://www.156yt.cn/publicInfoService/index.action",
                wait_until="domcontentloaded",
                timeout=15000,
            )
            page.wait_for_timeout(2000)

            # ===== Step 3: 点击"集装箱公众查询"链接 → 新标签页 =====
            link = page.query_selector('a:has-text("集装箱公众查询")')
            if not link:
                return {"success": False, "data": "", "error": "找不到集装箱公众查询链接"}

            with ctx.expect_page() as new_tab_info:
                link.click()
            query_page = new_tab_info.value
            query_page.wait_for_load_state("domcontentloaded", timeout=15000)
            query_page.wait_for_timeout(2000)

            # ===== Step 4: 填写表单 =====
            _fill_form(query_page, container_no, booking_no)
            query_page.wait_for_timeout(500)

            # ===== Step 5: 提交查询（按钮点击，AJAX 提交不触发导航）=====
            query_btn = query_page.query_selector(
                'input[name="Submit12"], '
                'input[type="button"][value="查询"], '
                'button:has-text("查询"), '
                'input[type="submit"]'
            )

            if query_btn:
                query_btn.click()
                query_page.wait_for_timeout(3000)
            else:
                # 兜底：直接调用 queryCont()
                query_page.evaluate("queryCont()")
                query_page.wait_for_timeout(3000)

            # 等待结果加载（页面不跳转，靠 AJAX 刷新内容）
            try:
                query_page.wait_for_function(
                    '() => !document.querySelector(\'input[name="cont_id"]\') '
                    '|| document.body.innerText.includes("查询结果") '
                    '|| document.body.innerText.includes("不在场") '
                    '|| document.body.innerText.includes("没有找到")',
                    timeout=15000,
                )
            except Exception:
                pass
            query_page.wait_for_timeout(2000)

            # ===== Step 6: 解析结果 =====
            result = _parse_result(query_page, container_no, booking_no)
            return result

        except Exception as e:
            import traceback
            return {
                "success": False,
                "data": "",
                "error": f"EXCEPTION: {type(e).__name__}: {e}\n{traceback.format_exc()}",
            }


def _login(page):
    """盐田港 passport 登录。"""
    page.goto("https://www.156yt.cn/passport/", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(2000)
    page.fill('input[name="j_username"]', YT_USERNAME)
    page.fill('input[name="j_password"]', YT_PASSWORD)
    page.wait_for_timeout(500)
    login_btn = page.query_selector('input[type="button"][value="登录"]')
    if login_btn:
        login_btn.click()
    else:
        page.evaluate("doLoginTop()")
    page.wait_for_timeout(5000)
    try:
        page.wait_for_load_state("networkidle", timeout=20000)
    except Exception:
        pass


def _fill_form(page, container_no: str, booking_no: str):
    """填写 popuPublic.jsp 查询表单。"""
    cont_input = page.query_selector('input[name="cont_id"]')
    if cont_input:
        cont_input.fill("")
        cont_input.fill(container_no)
    else:
        page.evaluate(f'document.forms[0].cont_id.value = "{container_no}"')
    if booking_no:
        bk_input = page.query_selector('input[name="bookingno"]')
        if bk_input:
            bk_input.fill("")
            bk_input.fill(booking_no)


def _parse_result(page, container_no: str, booking_no: str) -> dict:
    """解析查询结果（适配 div 布局 + 表格兜底）。"""
    page.wait_for_timeout(2000)
    text = page.evaluate("document.body.innerText") or ""

    if "不在场" in text or "没有找到" in text:
        return {
            "success": True,
            "data": (
                f"盐田港 - 集装箱 {container_no} 查询结果\n"
                f"{'-' * 50}\n"
                + (f"订舱号: {booking_no}\n" if booking_no else "")
                + "\n该箱当前不在盐田港"
            ),
            "error": "",
        }

    result = {"success": True, "data": "", "error": ""}
    lines = [l.strip() for l in text.split('\n')]

    # 查询无结果：页面仍为表单页（inputs > 0），无有效内容
    try:
        remaining_inputs = page.evaluate("document.querySelectorAll('input').length")
    except Exception:
        remaining_inputs = 0
    if remaining_inputs > 0 and len(text) < 500:
        result["data"] = (
            f"盐田港 - 集装箱 {container_no} 查询结果\n"
            f"{'-' * 50}\n"
            + (f"订舱号: {booking_no}\n" if booking_no else "")
            + "\n该箱当前不在盐田港，或非 YICT 交/提柜。"
        )
        return result

    # --- 方法 A：提取「查询结果」到「友情链接」之间的内容（最准确）---
    start = end = -1
    for i, l in enumerate(lines):
        if '查询结果' in l:
            start = i
        if '友情链接' in l or i == len(lines) - 1:
            if start >= 0 and end < 0:
                end = i

    body_lines = []
    if start >= 0 and end > start:
        for l in lines[start + 1:end]:
            l = l.strip()
            if not l or l in ('返回', '打印预览', '下载app快速查阅'):
                continue
            if any(kw in l for kw in ('版权所有', '粤ICP备', '扫码下载', 'All Rights',
                                       '邮编', '电话', '传真', '友情链接')):
                continue
            body_lines.append(l)

    if body_lines:
        result["data"] = (
            f"盐田港 - 集装箱 {container_no} 查询结果\n"
            f"{'-' * 50}\n"
            + (f"订舱号: {booking_no}\n" if booking_no else "")
            + "\n" + "\n".join(body_lines)
        )
        return result

    # --- 方法 B：提取 table 数据（旧版）---
    table_lines = []
    try:
        tables = page.query_selector_all("table")
        for table in tables:
            rows = table.query_selector_all("tr")
            for row in rows:
                cells = row.query_selector_all("td, th")
                texts = [c.inner_text().strip() for c in cells if c.inner_text().strip()]
                if texts:
                    table_lines.append(" | ".join(texts))
    except Exception:
        pass

    if table_lines:
        result["data"] = (
            f"盐田港 - 集装箱 {container_no} 查询结果\n"
            f"{'-' * 50}\n"
            + (f"订舱号: {booking_no}\n" if booking_no else "")
            + "\n查询结果:\n" + "\n".join(table_lines)
        )
        return result

    # --- 方法 C：纯文本兜底 ---
    meaningful = [l for l in lines
                  if len(l) > 3
                  and not any(kw in l for kw in (
                      '版权所有', '粤ICP备', '邮编', '电话', '传真',
                      '扫码下载', 'All Rights', '平台热线', '码头热线',
                      '关于我们', '官方微信', '易物流',
                  ))]

    result["data"] = (
        f"盐田港 - 集装箱 {container_no}\n"
        f"{'-' * 50}\n"
        + (f"订舱号: {booking_no}\n" if booking_no else "")
        + "\n查询结果:\n" + ("\n".join(meaningful) if meaningful else text[:2000])
    )
    return result
