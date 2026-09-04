"""
盐田港 (156yt.cn) RPA 驱动 — 集装箱状态查询 + 船期查询

集装箱查询流程：
1. passport 登录 (j_username + j_password)
2. 访问 publicInfoService → 点"集装箱公众查询" → 新标签页
3. 在新标签页填柜号 → 点查询按钮 → 等待结果

船期查询流程（query_vessel_schedule，登录复用同一账号）：
1. passport 登录后访问 publicInfoService → 点"船期公共查询(船名航次)" → 新标签页 voyQuery.jsp
2. 填船名(必填,≥3字符)/码头航次(可选)/起始日期(可选,默认当天) → 提交 → 解析靠泊计划表
3. 结果列: 码头航次 | 船名 | 闸口 | 预计停靠(ETB) | 预计离港(ETD) | 船代
"""

from __future__ import annotations

import re

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

    @staticmethod
    def query_vessel_schedule(page, params: dict) -> dict:
        """盐田港船期查询 — 按船名(必填)查靠泊计划 (voyQuery.jsp)。

        参数: vessel_name(船名,必填,≥3字符) / voyage_no(码头航次,可选)
              / etb_time(起始日期 yyyymmdd, 可选, 默认页面当天)
        """
        vessel = (params.get("vessel_name") or params.get("ship_name") or "").strip().upper()
        voyage = (params.get("voyage_no") or params.get("voyage_code") or "").strip()
        etb_date = (params.get("etb_time") or "").strip()
        # voyQuery 依赖显式提交 etb_time 才能稳定命中：页面 JS 默认当天在自动化下不可靠，
        # 留空会让服务端按空起始日期处理 → 0 记录（实测默认当天不填=0，显式填当天=命中）。
        # 未指定时显式填北京时间当天，与页面默认行为一致但可靠。
        if not etb_date:
            from datetime import datetime, timedelta, timezone
            etb_date = (datetime.now(timezone(timedelta(hours=8)))).strftime("%Y%m%d")

        if not vessel:
            return {"success": False, "data": "", "error": "请输入船名"}
        if len(vessel) < 3:
            return {"success": False, "data": "", "error": "船名需至少 3 个字符（英文船名）"}
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 .-]{2,79}", vessel):
            return {"success": False, "data": "", "error": "船名仅支持英文字母/数字/空格/句点/连字符"}
        if etb_date and not re.fullmatch(r"\d{8}", etb_date):
            return {"success": False, "data": "", "error": "起始日期需为 8 位数字，格式 yyyymmdd（如 20260903）"}

        try:
            qp = None
            result = None
            # 空窗容错: 156yt 多节点/定时同步下同一参数会间歇返回 0 记录（实证: 0 后等几秒重查常可命中）。
            # 最多 3 次: 首次 → 重试1(同页冷却后重填) → 重试2(换全新登录+新页，摆脱可能的节点粘滞)。
            for attempt in range(1, 4):
                if qp is None:
                    qp = _open_schedule_query(page)      # 登录 + 导航到 voyQuery 新标签页
                if not _submit_schedule_query(qp, vessel, voyage, etb_date):
                    # 复用页表单缺失(页面被重绘/踢回) → 换全新登录再查
                    try:
                        qp.close()
                    except Exception:
                        pass
                    qp = None
                    if attempt >= 3:
                        break
                    continue
                result = _parse_schedule(qp, vessel, voyage, etb_date)
                records = result.get("_records")
                if records not in (0, None) or attempt >= 3:
                    break
                if attempt == 2:
                    # 重试1 仍 0 → 下轮全新登录重开页
                    try:
                        qp.close()
                    except Exception:
                        pass
                    qp = None
                else:
                    # 首次 0 → 同页冷却几秒后重填（观察到的空窗多为秒级瞬态）
                    qp.wait_for_timeout(4000)
            if result is None:
                return {"success": False, "data": "", "error": "船期查询页面表单不可用，请重试"}
            return result

        except RuntimeError as e:
            # 结构性失败(找不到入口/导航超时等) — 干净报错不带 traceback
            return {"success": False, "data": "", "error": str(e)}
        except Exception as e:
            import traceback
            return {
                "success": False,
                "data": "",
                "error": f"EXCEPTION: {type(e).__name__}: {e}\n{traceback.format_exc()}",
            }


def _open_schedule_query(page):
    """登录并打开船期查询 voyQuery 新标签页，返回 qp。

    voyQuery 入口是 target=_blank 链接，直接 goto 会被拦回，必须 expect_page 等新标签。
    找不到入口等结构性失败抛 RuntimeError（由 query_vessel_schedule 干净报错）。
    """
    _login(page)
    page.goto(
        "https://www.156yt.cn/publicInfoService/index.action",
        wait_until="domcontentloaded",
        timeout=15000,
    )
    page.wait_for_timeout(2000)

    link = None
    for a in page.query_selector_all("a[href*='voyQuery']"):
        href = a.get_attribute("href") or ""
        if "voyQuery" in href:
            link = a
            break
    if link is None:
        raise RuntimeError("找不到「船期公共查询(船名航次)」入口")

    with page.context.expect_page() as tab_info:
        link.click()
    qp = tab_info.value
    qp.wait_for_load_state("domcontentloaded", timeout=20000)
    qp.wait_for_timeout(2000)
    return qp


def _submit_schedule_query(qp, vessel: str, voyage: str, etb_date: str) -> bool:
    """当前 voy 页填表并提交船期查询，等待 POST 导航完成。返回表单是否可用。

    关键坑（实证）:
    - voyQuery 初始页 body 就自带「总记录数:0」空结果表，绝不能用它当"结果已出"信号，
      否则在 POST 导航完成前解析会得到假阴性 0 记录 → 必须 wait_for_url 变 modify=query。
    - 提交后页面重绘瞬间表单控件可能短暂缺失 → 先重试查找 ship_name，找不到返回 False
      （调用方会换全新登录重来）。
    """
    inp = None
    for _ in range(10):
        inp = qp.query_selector('input[name="ship_name"]')
        if inp:
            break
        qp.wait_for_timeout(500)
    if not inp:
        return False

    _fill_schedule_form(qp, vessel, voyage, etb_date)
    qp.wait_for_timeout(300)
    sub = qp.query_selector('input[name="Submit1"], input[type="submit"]')
    if sub:
        sub.click()
    else:
        qp.evaluate("form1.submit()")
    # form action 提交 → 导航到 voyQuery.jsp?modify=query 才算这次查询真正完成
    qp.wait_for_url("**modify=query**", timeout=25000)
    try:
        qp.wait_for_load_state("domcontentloaded", timeout=20000)
    except Exception:
        pass
    qp.wait_for_timeout(2000)
    return True


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
            "success": False,
            "data": (
                f"盐田港 - 集装箱 {container_no} 查询结果\n"
                f"{'-' * 50}\n"
                + (f"订舱号: {booking_no}\n" if booking_no else "")
                + "\n该箱当前不在盐田港"
            ),
            "error": "该箱当前不在盐田港，未同步订单",
        }

    result = {"success": True, "data": "", "error": ""}
    lines = [l.strip() for l in text.split('\n')]

    # 查询无结果：页面仍为表单页（inputs > 0），无有效内容
    try:
        remaining_inputs = page.evaluate("document.querySelectorAll('input').length")
    except Exception:
        remaining_inputs = 0
    if remaining_inputs > 0 and len(text) < 500:
        result["success"] = False
        result["error"] = "查询无结果：该箱不在盐田港或非 YICT 交/提柜"
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


def _fill_schedule_form(qp, vessel: str, voyage: str, etb_date: str):
    """填写 voyQuery.jsp 船期查询表单：船名 / 码头航次 / 起始日期(可选)。"""
    inp = qp.query_selector('input[name="ship_name"]')
    if inp:
        inp.fill("")
        inp.fill(vessel)
    if voyage:
        vg = qp.query_selector('input[name="voyage_code"]')
        if vg:
            vg.fill("")
            vg.fill(voyage)
    if etb_date:
        dt = qp.query_selector('input[name="etb_time"]')
        if dt:
            dt.fill(etb_date)


def _parse_schedule(qp, vessel: str, voyage: str, etb_date: str) -> dict:
    """解析船期靠泊计划结果。

    表列: 码头航次 | 船名 | 闸口 | 预计停靠(ETB) | 预计离港(ETD) | 船代
    0 记录 = 查询本身成功，但该船在起始日期暂无公开靠泊计划。
    """
    try:
        text = qp.evaluate("document.body.innerText") or ""
    except Exception:
        text = ""

    def _cnt(label: str) -> int:
        m = re.search(rf"{label}[:：]\s*(\d+)", text)
        return int(m.group(1)) if m else 0

    total = _cnt("总记录数")
    total_pages = _cnt("总页数")

    # 抓结果表（含「码头航次」/「船名」表头的那张）
    header: list[str] = []
    data_rows: list[list[str]] = []
    try:
        for tb in qp.query_selector_all("table"):
            rows = tb.query_selector_all("tr")
            if len(rows) <= 1:
                continue
            hdr = [c.inner_text().strip() for c in rows[0].query_selector_all("td, th")]
            if not any(k in " ".join(hdr) for k in ("码头航次", "船名")):
                continue
            header = hdr
            for r in rows[1:]:
                cells = [c.inner_text().strip() for c in r.query_selector_all("td, th")]
                if any(cells):
                    data_rows.append(cells)
            break
    except Exception:
        pass

    date_lbl = ""
    if etb_date and len(etb_date) == 8:
        date_lbl = f"{etb_date[:4]}-{etb_date[4:6]}-{etb_date[6:]}"

    cond = f"船名 {vessel}"
    if voyage:
        cond += f" · 航次 {voyage}"
    if date_lbl:
        cond += f" · 起始 {date_lbl}"
    head = [f"盐田港 — 船期查询 · {cond}", f"{'─' * 44}"]

    if not data_rows:
        head.append(f"查询成功，但未查到该船在盐田的靠泊计划（总记录数: {total}）。")
        tip = "提示: ① 确认英文船名拼写准确；② 船期通常提前数日公布，可把起始日期向后调整几天重查。"
        if voyage:
            tip += "\n③ 已填航次时若未命中，可清空航次、仅用英文船名重查（网页按码头航次匹配，商业航次常与码头航次不一致）。"
        head.append(tip)
        return {"success": True, "data": "\n".join(head) + "\n", "error": "", "_records": total}

    head.append(f"查到 {total} 条靠泊计划：")
    std_hdr = [_std_label(h) for h in header]
    for i, cells in enumerate(data_rows):
        pairs = []
        for cidx, val in enumerate(cells):
            fld = std_hdr[cidx] if cidx < len(std_hdr) else f"字段{cidx + 1}"
            pairs.append((fld, val))
        head.append(_draw_field_box(pairs))
        if i < len(data_rows) - 1:
            head.append("")
    if total_pages > 1 and len(data_rows) < total:
        head.append(f"（当前显示第 1 页 {len(data_rows)} 条，共 {total} 条 / {total_pages} 页，可把起始日期调窄重查）")

    return {"success": True, "data": "\n".join(head) + "\n", "error": "", "_records": total}


def _disp_w(s: str) -> int:
    """字符串显示宽度：CJK/全角按 2，其余按 1（用于对齐 box 表）。"""
    import unicodedata
    return sum(2 if unicodedata.east_asian_width(ch) in ("F", "W") else 1 for ch in s)


def _cjk_pad(s: str, w: int) -> str:
    """按显示宽度右侧补齐到 w。"""
    return s + " " * max(0, w - _disp_w(s))


def _std_label(h: str) -> str:
    """网页表头 → 统一易读字段名。"""
    h = (h or "").strip()
    for kw, lab in (
        ("码头航次", "码头航次"),
        ("预计停靠", "预计停靠(ETB)"),
        ("ETB", "预计停靠(ETB)"),
        ("预计离港", "预计离港(ETD)"),
        ("ETD", "预计离港(ETD)"),
        ("船名", "船名"),
        ("闸口", "闸口"),
        ("船代", "船代"),
    ):
        if kw in h:
            return lab
    return h


def _draw_field_box(pairs: list[tuple[str, str]]) -> str:
    """「字段名 | 值」box 对照表，每行一个字段 + 网页查到的对应值。"""
    if not pairs:
        return ""
    wf = max(_disp_w(k) for k, _ in pairs)
    wv = max(_disp_w(v) for _, v in pairs)
    seg = "─"
    top = "┌" + seg * (wf + 2) + "┬" + seg * (wv + 2) + "┐"
    bot = "└" + seg * (wf + 2) + "┴" + seg * (wv + 2) + "┘"
    out = [top]
    for k, v in pairs:
        out.append(f"│ {_cjk_pad(k, wf)} │ {_cjk_pad(v, wv)} │")
    out.append(bot)
    return "\n".join(out)
