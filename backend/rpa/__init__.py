"""
OAIW RPA 自动化引擎 — Playwright + Crawl4AI 浏览器自动化

操作部 RPA 场景：
1. 港口集装箱查询 — 查盐田/蛇口/上海/宁波/青岛等码头集装箱在场状态
2. 码头状态查询 — 访问码头首页获取公告信息
3. 保函自动生成 — 填充保函模板
4. 货物状态跟踪 — 查航班/船期状态

注意：Python 3.14 Windows 的 asyncio 事件循环不支持子进程。
因此使用 sync_playwright + asyncio.to_thread() 避免此问题。
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Optional

from backend.config import settings

from backend.rpa.log_queue import set_log_queue, rpa_log  # noqa: re-export

import asyncio
import queue as _queue

# 可选依赖：Crawl4AI — 码头状态查询优先使用
try:
    from crawl4ai import AsyncWebCrawler
    from crawl4ai.async_configs import BrowserConfig as C4BrowserConfig, CrawlerRunConfig
    _HAS_CRAWL4AI = True
except ImportError:
    _HAS_CRAWL4AI = False


async def run_browser_task(task_type: str, params: dict, log_queue: _queue.Queue | None = None) -> dict:
    """
    运行浏览器自动化任务。

    Args:
        task_type: 任务类型 (port_query | port_status | track_cargo | generate_letter | merge_docs)
        params: 任务参数
        log_queue: 日志队列，传入后 print 内容会实时推送到这个队列（SSE流用）

    Returns:
        {"success": bool, "data": str, "error": str}
    """
    try:
        set_log_queue(log_queue)
        return await asyncio.to_thread(_run_browser_sync, task_type, params)
    except Exception as e:
        return {"success": False, "data": "", "error": f"EXCEPTION: {type(e).__name__}: {e}"}
    finally:
        set_log_queue(None)


def _load_port_auth_state(context_kwargs: dict, port: str):
    """加载港口驱动的登录态文件（用于有验证码的码头）。"""
    port_files = {
        "蛇口": "sk_auth_state.json",
        "青岛": "qd_auth_state.json",
        "宁波": "npedi_auth_state.json",
    }
    file_name = None
    for key, fn in port_files.items():
        if key in port:
            file_name = fn
            break
    if not file_name:
        return
    auth_path = Path(__file__).parent / "ports" / file_name
    if auth_path.exists():
        context_kwargs["storage_state"] = str(auth_path)


def _run_browser_sync(task_type: str, params: dict) -> dict:
    """同步执行浏览器自动化任务（在 asyncio.to_thread 中运行）。"""

    # 码头状态查询优先使用 Crawl4AI（无需 Playwright，反检测更好）
    if task_type == "port_status" and _HAS_CRAWL4AI:
        rpa_log("使用 Crawl4AI 查询码头状态...")
        c4_result = _query_port_status_crawl4ai(params)
        if c4_result.get("success"):
            return c4_result
        rpa_log(f"Crawl4AI 失败，回退到 Playwright: {c4_result.get('error', '未知')[:100]}")
    elif task_type == "port_status" and not _HAS_CRAWL4AI:
        rpa_log("Crawl4AI 未安装，使用 Playwright...")

    rpa_log("启动浏览器...")
    from playwright.sync_api import sync_playwright

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=settings.HEADLESS,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-web-security",
                    "--disable-features=IsolateOrigins,site-per-process",
                    "--disable-infobars",
                    "--disable-dev-shm-usage",
                    "--no-first-run",
                    "--disable-blink-features=AutomationControlled",
                ],
            )

            # 港口驱动专用登录态（蛇口港有验证码，需持久化 auth state）
            context_kwargs = {
                "locale": "zh-CN",
                "timezone_id": "Asia/Shanghai",
                "viewport": {"width": 1920, "height": 1080},
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                "ignore_https_errors": True,
            }
            if task_type == "port_query":
                port = params.get("port_name", "")
                if "蛇口" in port or "青岛" in port or "宁波" in port:
                    _load_port_auth_state(context_kwargs, port)
            context = browser.new_context(**context_kwargs)
            page = context.new_page()
            page.set_default_timeout(settings.RPA_TIMEOUT)

            result: dict = {"success": False, "data": "", "error": ""}

            if task_type == "port_query":
                result = _query_port_container_sync(page, params)
                # RPA同步：查询结果同步到业务订单
                port = params.get("port_name", "")
                _rpa_sync_orders(port, params, result)
            elif task_type == "port_status":
                result = _query_port_status_sync(page, params)
            elif task_type == "track_cargo":
                result = _track_cargo_sync(page, params)
            else:
                result = {"success": False, "data": "", "error": f"未知任务类型: {task_type}"}

            browser.close()
    finally:
        pass

    return result


def _query_port_container_sync(page, params: dict) -> dict:
    """港口集装箱查询 — 使用对应港口的驱动模块查柜。"""
    port = params.get("port_name", "")
    container_no = params.get("container_no", "")
    booking_no = params.get("booking_no", "")

    if not port:
        return {"success": False, "data": "", "error": "未指定港口名称"}

    # 懒导入港口驱动
    from backend.rpa.ports import get_driver as _get_port_driver
    import backend.rpa.ports as _ports

    driver = _get_port_driver(port)
    if driver is None:
        return {
            "success": False,
            "data": "",
            "error": f"港口 '{port}' 尚未支持。已注册港口: {', '.join(_ports.list_ports()) or '无'}",
        }

    return driver.query_container(page, params)


def _rpa_sync_orders(port: str, params: dict, result: dict):
    """RPA 查询结果同步到业务订单（统一函数，支持所有港口）。"""
    if not result.get("success") or not result.get("data"):
        return
    # 目前支持：宁波港、盐田港、蛇口港、青岛港
    supported_ports = ["宁波", "盐田", "蛇口", "青岛"]
    if not any(p in port for p in supported_ports):
        return
    try:
        from backend.rpa.rpa_sync import sync_from_port
        from backend.database import SessionLocal
        _db = SessionLocal()
        try:
            sync_result = sync_from_port(
                _db,
                raw_text=result["data"],
                container_no=params.get("container_no", ""),
                booking_no=params.get("booking_no", ""),
                port_name=port,
                vessel_name=params.get("vessel_name", ""),
                voyage_no=params.get("voyage_no", ""),
            )
            if sync_result.get("synced"):
                from backend.rpa.log_queue import rpa_log
                action_text = "创建" if "created" in sync_result["action"] else "更新"
                rpa_log(f"[同步] {sync_result['module']} 单号 {sync_result['order_no']} — {action_text}")
                result["data"] += f"\n\n【自动同步】已{action_text} {sync_result['module']} 订单: {sync_result['order_no']}"
        except Exception as sync_err:
            from backend.rpa.log_queue import rpa_log
            rpa_log(f"[同步警告] {sync_err}")
        finally:
            _db.close()
    except Exception:
        pass  # 同步失败不影响主流程


def _query_port_status_sync(page, params: dict) -> dict:
    """查询码头公告/状态。

    各码头差异化查询：
    - 盐田: 访问通知公告页，提取公告列表
    - 蛇口: 访问 eport 门户首页，检查有无登录前可见的公告
    - 上海: 提取首页最新公告列表
    - 宁波: 访问门户首页，提取公开信息
    - 青岛: 访问云港通首页，提取公开信息
    """
    import re
    from datetime import datetime

    port = params.get("port_name", "")
    TIMEOUT = 30000

    def _match_port(keys: list[str]) -> bool:
        return any(k in port for k in keys)

    try:
        # ===== 盐田港 =====
        if _match_port(["盐田"]):
            # 盐田网站较慢，先快速连接再等待 body 加载
            page.goto("https://www.156yt.cn/", wait_until="commit", timeout=30000)
            try:
                page.wait_for_selector("body", timeout=15000)
                page.wait_for_timeout(2000)
            except Exception:
                page.wait_for_timeout(5000)
            lines = [
                f"🏭 盐田港 — 码头状态",
                f"{'─' * 50}",
                f"查询时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"网址: https://www.156yt.cn/",
                f"",
            ]
            body_text = page.evaluate("(document.body?.innerText || '').substring(0, 3000)") or ""
            lines.append(f"【页面内容】")
            lines.append(body_text[:2000] or "(页面加载中，请稍后重试)")

            # 尝试访问通知公告页
            try:
                page.goto("https://www.156yt.cn/info/news/notice.html",
                          wait_until="commit", timeout=20000)
                try:
                    page.wait_for_selector("body", timeout=10000)
                    page.wait_for_timeout(2000)
                except Exception:
                    page.wait_for_timeout(3000)
                notice_text = page.evaluate("(document.body?.innerText || '').substring(0, 2000)") or ""
                if notice_text.strip():
                    lines.append(f"")
                    lines.append(f"【通知公告】")
                    lines.append(notice_text[:2000])
            except Exception:
                lines.append(f"")
                lines.append(f"(公告页暂时无法访问)")

            lines.append(f"\n{'─' * 50}")
            lines.append(f"数据来源: 易物流盐田 (156yt.cn)")
            return {"success": True, "data": "\n".join(lines), "error": ""}

        # ===== 蛇口港 =====
        elif _match_port(["蛇口"]):
            page.goto("https://wk-eport.cmp1872.com/", wait_until="domcontentloaded", timeout=TIMEOUT)
            page.wait_for_timeout(3000)
            title = page.title()
            body = page.evaluate("document.body.innerText.substring(0, 2000)")
            lines = [
                f"🏭 蛇口港(SCCT) — 码头状态",
                f"{'─' * 50}",
                f"查询时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"网址: https://wk-eport.cmp1872.com/",
                f"页面标题: {title}",
                f"",
                f"【页面公开信息】",
                body[:1500],
                f"",
                f"💡 注: 蛇口港 eport 门户需登录才能查看详细公告。",
                f"   如需完整状态，请使用「集装箱查询」功能查具体柜号。",
                f"",
                f"{'─' * 50}",
                f"数据来源: 招商港口 eport (wk-eport.cmp1872.com)",
            ]
            return {"success": True, "data": "\n".join(lines), "error": ""}

        # ===== 上海港 =====
        elif _match_port(["上海"]):
            page.goto("https://www.hb56.com/", wait_until="domcontentloaded", timeout=TIMEOUT)
            page.wait_for_timeout(2000)
            lines = [
                f"🏭 上海港 — 码头状态",
                f"{'─' * 50}",
                f"查询时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"网址: https://www.hb56.com/",
                f"",
            ]
            # 提取最新公告列表
            notices = page.evaluate("""() => {
                const items = document.querySelectorAll('.hha, .hhb, .hhb a, .hha ~ ul li a, ' +
                    'ul li a[onclick*=\"Notice\"]');
                const results = [];
                // 找最新公告区域内的链接
                const allLinks = document.querySelectorAll('a[onclick*=\"openWindow\"], a[href*=\"Notice/NoticeInfo\"]');
                for (const a of allLinks) {
                    const t = (a.innerText || '').trim();
                    if (t) results.push(t);
                    if (results.length >= 15) break;
                }
                return results;
            }""")
            if notices and len(notices) > 0:
                lines.append(f"【最新公告】({len(notices)} 条)")
                for n in notices:
                    lines.append(f"  • {n}")
            else:
                # 兜底：直接抓页面可见文字
                visible = page.evaluate("""() => {
                    const all = document.body.innerText;
                    const idx = all.indexOf('最新公告');
                    return idx >= 0 ? all.substring(idx, idx + 800) : all.substring(0, 1500);
                }""")
                lines.append(f"【页面内容】")
                lines.append(visible[:1000])

            lines.append(f"\n{'─' * 50}")
            lines.append(f"数据来源: 港航纵横 (hb56.com)")
            return {"success": True, "data": "\n".join(lines), "error": ""}

        # ===== 宁波港 =====
        elif _match_port(["宁波"]):
            lines = [
                f"🏭 宁波港 — 码头状态",
                f"{'─' * 50}",
                f"查询时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"网址: https://www.npedi.com/",
                f"",
            ]
            # 尝试 Playwright 访问（wait_until="commit" 绕过部分 WAF 检测）
            try:
                page.goto("https://www.npedi.com/onesite/index",
                          wait_until="commit", timeout=TIMEOUT)
                try:
                    page.wait_for_selector("body", timeout=10000)
                    page.wait_for_timeout(3000)
                    title = page.title()
                    body = page.evaluate("(document.body?.innerText || '').substring(0, 3000)")
                    lines.append(f"页面标题: {title}")
                    lines.append(f"")
                    lines.append(f"【页面公开信息】")
                    lines.append(body[:2000] or "(页面加载中)")
                except Exception:
                    lines.append(f"(页面加载超时)")
            except Exception:
                # Playwright 失败，尝试 HTTP 直连
                lines.append("(Playwright 直连被拦截，尝试 HTTP 方式...)")
                try:
                    import urllib.request, ssl
                    ctx = ssl._create_unverified_context()
                    req = urllib.request.Request(
                        "https://www.npedi.com/",
                        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                    )
                    with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
                        html = resp.read().decode("utf-8", errors="replace")
                        # 提取页面标题和可见文字
                        import re
                        m = re.search(r'<title>(.*?)</title>', html, re.DOTALL)
                        title = m.group(1).strip() if m else "(无标题)"
                        # 去掉 HTML 标签取纯文本片段
                        text = re.sub(r'<[^>]+>', ' ', html)
                        text = re.sub(r'\s+', ' ', text).strip()[:2000]
                        lines.append(f"页面标题: {title}")
                        lines.append(f"")
                        lines.append(f"【页面公开信息】")
                        lines.append(text[:1500] or "(无内容)")
                except Exception as e2:
                    lines.append(f"(HTTP 方式也失败: {type(e2).__name__})")
                    lines.append(f"")
                    lines.append(f"💡 提示: npedi.com 有严格的 WAF 防护，自动化工具无法直接访问。")
                    lines.append(f"   如需查具体柜号，请使用「集装箱查询」功能（通过 API 方式查询）。")

            lines.append(f"\n{'─' * 50}")
            lines.append(f"数据来源: 宁波港口EDI中心 (npedi.com)")
            return {"success": True, "data": "\n".join(lines), "error": ""}

        # ===== 青岛港 =====
        elif _match_port(["青岛"]):
            lines = [
                f"🏭 青岛港 — 码头状态",
                f"{'─' * 50}",
                f"查询时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"网址: https://www.qingdao-port.net/",
                f"",
            ]
            # 尝试 Playwright 访问
            try:
                page.goto("https://www.qingdao-port.net/",
                          wait_until="commit", timeout=TIMEOUT)
                try:
                    page.wait_for_selector("body", timeout=10000)
                    page.wait_for_timeout(3000)
                    title = page.title()
                    body = page.evaluate("(document.body?.innerText || '').substring(0, 3000)")
                    lines.append(f"页面标题: {title}")
                    lines.append(f"")
                    lines.append(f"【页面公开信息】")
                    lines.append(body[:2000] or "(页面加载中)")
                except Exception:
                    lines.append(f"(页面加载超时)")
            except Exception:
                lines.append("(Playwright 直连被拦截，尝试 HTTP 方式...)")
                try:
                    import urllib.request, ssl
                    ctx = ssl._create_unverified_context()
                    req = urllib.request.Request(
                        "https://www.qingdao-port.net/",
                        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                    )
                    with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
                        html = resp.read().decode("utf-8", errors="replace")
                        import re
                        m = re.search(r'<title>(.*?)</title>', html, re.DOTALL)
                        title = m.group(1).strip() if m else "(无标题)"
                        text = re.sub(r'<[^>]+>', ' ', html)
                        text = re.sub(r'\s+', ' ', text).strip()[:2000]
                        lines.append(f"页面标题: {title}")
                        lines.append(f"")
                        lines.append(f"【页面公开信息】")
                        lines.append(text[:1500] or "(无内容)")
                except Exception as e2:
                    lines.append(f"(HTTP 方式也失败: {type(e2).__name__})")
                    lines.append(f"")
                    lines.append(f"💡 提示: 青岛港云港通网站有防护，自动化工具无法直接访问。")
                    lines.append(f"   如需查具体柜号，请使用「集装箱查询」功能（需登录）。")

            lines.append(f"\n{'─' * 50}")
            lines.append(f"数据来源: 青岛港云港通 (qingdao-port.net)")
            return {"success": True, "data": "\n".join(lines), "error": ""}

        else:
            return {"success": False, "data": "", "error": f"不支持的码头: {port}"}

    except Exception as e:
        import traceback
        return {
            "success": False,
            "data": "",
            "error": f"访问 {port} 码头状态失败: {type(e).__name__}: {e}\n{traceback.format_exc()}",
        }


def _query_port_status_crawl4ai(params: dict) -> dict:
    """Crawl4AI 版码头状态查询 — 反检测更好，无需单独 Playwright 浏览器。

    支持 盐田/蛇口/上海/宁波/青岛 五个码头。
    返回格式与 _query_port_status_sync 一致。
    """
    import asyncio
    import re
    from datetime import datetime

    port = params.get("port_name", "")

    def _match_port(keys: list[str]) -> bool:
        return any(k in port for k in keys)

    async def _crawl(url: str, timeout: int = 30000,
                     wait_until: str = "domcontentloaded",
                     delay: float = 1.0) -> str | None:
        """用 Crawl4AI 异步抓取页面，返回 Markdown 文本。

        Args:
            url: 目标 URL
            timeout: 超时毫秒
            wait_until: Playwright 等待策略（domcontentloaded/networkidle/commit）
            delay: 返回 HTML 前的额外等待时间（秒），用于 JS 渲染完成
        """
        browser_cfg = C4BrowserConfig(
            headless=True,
            enable_stealth=True,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
            viewport_width=1920,
            viewport_height=1080,
        )
        run_cfg = CrawlerRunConfig(
            page_timeout=timeout,
            wait_until=wait_until,
            magic=True,
            simulate_user=True,
            override_navigator=True,
            delay_before_return_html=delay,
            verbose=False,
        )
        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            result = await crawler.arun(url, config=run_cfg)
            async for r in result:
                if r.success and r.markdown:
                    return r.markdown
                if r.success and r.cleaned_html and not r.markdown:
                    return re.sub(r'<[^>]+>', ' ', r.cleaned_html)
            return None

    def _http_fallback(url: str) -> list[str]:
        """HTTP 直连回落 — 返回要追加到 lines 的列表。"""
        out = ["(Crawl4AI 直连被拦截，尝试 HTTP 方式...)"]
        try:
            import urllib.request, ssl
            ctx = ssl._create_unverified_context()
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            )
            with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
                html = resp.read().decode("utf-8", errors="replace")
                m = re.search(r'<title>(.*?)</title>', html, re.DOTALL)
                title = m.group(1).strip() if m else "(无标题)"
                text = re.sub(r'<[^>]+>', ' ', html)
                text = re.sub(r'\s+', ' ', text).strip()[:2000]
                out += [f"页面标题: {title}", "", "【页面公开信息】", text[:1500] or "(无内容)"]
        except Exception as e2:
            out += [f"(HTTP 方式也失败: {type(e2).__name__})"]
        return out

    try:
        if _match_port(["盐田"]):
            lines = [
                f"🏭 盐田港 — 码头状态", f"{'─' * 50}",
                f"查询时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"网址: https://www.156yt.cn/", "",
            ]
            body_md = asyncio.run(_crawl("https://www.156yt.cn/"))
            lines += ["【页面内容】", body_md[:2000] if body_md else "(页面加载失败)"]
            notice_md = asyncio.run(_crawl("https://www.156yt.cn/info/news/notice.html", timeout=20000))
            if notice_md and notice_md.strip():
                lines += ["", "【通知公告】", notice_md[:2000]]
            else:
                lines += ["", "(公告页暂时无法访问)"]
            lines += [f"\n{'─' * 50}", "数据来源: 易物流盐田 (156yt.cn)"]
            return {"success": True, "data": "\n".join(lines), "error": ""}

        elif _match_port(["蛇口"]):
            md = asyncio.run(_crawl(
                "https://eport.cmp1872.com/",
                wait_until="networkidle", delay=2.0,
            ))
            lines = [
                f"🏭 蛇口港(SCCT) — 码头状态", f"{'─' * 50}",
                f"查询时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"网址: https://eport.cmp1872.com/", "",
            ]
            if md:
                # 提取通知公告
                idx = md.find("通知公告")
                if idx >= 0:
                    lines += ["【通知公告】", md[idx:idx + 500]]
                # 提取公司新闻
                news_idx = md.find("公司新闻")
                if news_idx >= 0:
                    lines += ["", "【公司新闻】"]
                    lines += [md[news_idx:news_idx + 400]]
                # 提取核心服务
                biz_idx = md.find("一站式港口")
                if biz_idx >= 0:
                    lines += ["", "【服务介绍】", md[biz_idx:biz_idx + 500]]
                if idx < 0 and news_idx < 0 and biz_idx < 0:
                    lines += ["【页面公开信息】", md[:1200]]
            else:
                lines += ["【页面公开信息】(页面加载失败)"]
            lines += [
                "",
                f"{'─' * 50}",
                "数据来源: 招商港口 eport (eport.cmp1872.com)",
            ]
            return {"success": True, "data": "\n".join(lines), "error": ""}

        elif _match_port(["上海"]):
            md = asyncio.run(_crawl("https://www.hb56.com/"))
            lines = [
                f"🏭 上海港 — 码头状态", f"{'─' * 50}",
                f"查询时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"网址: https://www.hb56.com/", "",
            ]
            if md:
                idx = md.find("最新公告")
                if idx >= 0:
                    lines += ["【最新公告】", md[idx:idx + 1000]]
                else:
                    lines += ["【页面内容】", md[:1500]]
            else:
                lines += ["【页面内容】(页面加载失败)"]
            lines += [f"\n{'─' * 50}", "数据来源: 港航纵横 (hb56.com)"]
            return {"success": True, "data": "\n".join(lines), "error": ""}

        elif _match_port(["宁波"]):
            lines = [
                f"🏭 宁波港 — 码头状态", f"{'─' * 50}",
                f"查询时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"网址: https://www.npedi.com/", "",
            ]
            # 宁波 npedi.com 有严格 WAF，需 networkidle + 长等待让 JS 渲染完成
            md = asyncio.run(_crawl(
                "https://www.npedi.com/onesite/index",
                timeout=60000, wait_until="networkidle", delay=3.0,
            ))
            if md:
                # 尝试提取通知公告
                idx = md.find("通知公告")
                if idx >= 0:
                    lines += ["【通知公告】", md[idx:idx + 1500]]
                else:
                    lines += ["【页面公开信息】", md[:1500]]
            else:
                lines += _http_fallback("https://www.npedi.com/")
            lines += [f"\n{'─' * 50}", "数据来源: 宁波港口EDI中心 (npedi.com)"]
            return {"success": True, "data": "\n".join(lines), "error": ""}

        elif _match_port(["青岛"]):
            lines = [
                f"🏭 青岛港 — 码头状态", f"{'─' * 50}",
                f"查询时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"网址: https://www.qingdao-port.net/", "",
            ]
            # 青岛有时需要 JS 渲染，用 networkidle 保险
            md = asyncio.run(_crawl(
                "https://www.qingdao-port.net/",
                timeout=45000, wait_until="networkidle", delay=2.0,
            ))
            if md:
                lines += ["【页面公开信息】", md[:2000]]
            else:
                lines += _http_fallback("https://www.qingdao-port.net/")
            lines += [f"\n{'─' * 50}", "数据来源: 青岛港云港通 (qingdao-port.net)"]
            return {"success": True, "data": "\n".join(lines), "error": ""}

        else:
            return {"success": False, "data": "", "error": f"不支持的码头: {port}"}

    except Exception as e:
        import traceback
        return {
            "success": False,
            "data": "",
            "error": f"Crawl4AI 访问 {port} 失败: {type(e).__name__}: {e}\n{traceback.format_exc()}",
        }


def _track_cargo_sync(page, params: dict) -> dict:
    """跟踪货物状态。"""
    tracking_no = params.get("tracking_no", "")
    return {
        "success": True,
        "data": f"跟踪单号: {tracking_no}\n\n货物跟踪功能需要通过 Seabay 网站或航司官网查询。",
        "error": "",
    }
