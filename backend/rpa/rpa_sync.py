"""
RPA 查询结果 → 业务订单同步服务

统一处理所有港口的查询结果：
1. 解析输出文本，提取柜号/箱型/件毛体/船名航次/封条等字段
2. 有独立柜号+箱型尺寸 → 整柜 FCL
3. 只有件毛体无柜号 → 空运/海运暂留
4. 按柜号或提单号查重，同一业务单号只准存在一个
5. 已存在则推进状态，不存在则创建
"""
from __future__ import annotations

import json
import re
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from backend.core.models.fcl_order import FCLOrder
from backend.rpa import unified_mapper as um

logger = logging.getLogger(__name__)

# FCL 状态推进：每次 RPA 查到新数据 → 推进到"补料/VGM"
_FCL_ADVANCE_STATUS = "si_vgm"


def _extract_by_prefix(text: str, prefix: str) -> str:
    """从文本提取 '前缀: 值' 格式"""
    for line in text.split("\n"):
        line = line.strip()
        if "：" in line:
            parts = line.split("：", 1)
            if parts[0].strip() == prefix:
                return parts[1].strip()
        if ":" in line:
            parts = line.split(":", 1)
            if parts[0].strip().lower() == prefix.lower():
                return parts[1].strip()
    return ""


def _progress_for_status(fcl_status: str) -> int:
    """FCL 状态 → 进度百分比"""
    from backend.core.routers.fcl import STEP_KEYS
    idx = STEP_KEYS.index(fcl_status) if fcl_status in STEP_KEYS else -1
    if idx >= 0:
        return int((idx + 1) / len(STEP_KEYS) * 100)
    return 30


def _extract_colon(text: str, key: str) -> str:
    """提取 'key: val' 或 'key：val' 格式（仅匹配行首），去除多余tab内容"""
    pat = re.compile(r'(?:^|\n)\s*' + re.escape(key) + r'[：:]\s*([^\n]+)')
    m = pat.search(text)
    if m:
        val = m.group(1).strip()
        if '\t' in val:
            val = val.split('\t')[0].strip()
        return val
    return ""


def _extract_colon_any(text: str, key: str) -> str:
    """提取 'key: val' 格式，支持行首或行中（盐田 tab 行），取冒号后到行尾"""
    pat = re.compile(r'(?:^|\n|\t)\s*' + re.escape(key) + r'[：:]\s*([^\n]+)')
    m = pat.search(text)
    if m:
        val = m.group(1).strip()
        # 制表符分隔的多值行，取 tab 前的第一段
        if '\t' in val:
            val = val.split('\t')[0].strip()
        return val
    return ""


def sync_from_port(db: Session, raw_text: str, container_no: str, booking_no: str = "",
                   port_name: str = "", vessel_name: str = "", voyage_no: str = "") -> dict:
    """
    解析任意港口的查询结果文本，同步到业务订单。
    返回同步结果描述。

    字段映射：
      booking_no（前端传参）= 业务单号（如 SB-YWS26060136）→ order_no
      港口输出"订舱单号" = 船司订舱号/SO号（如 ALK0574445）→ bl_no
    """
    result = {"synced": False, "module": "", "order_no": "", "action": ""}

    # ===== 统一字段提取（方案B：走 unified_mapper 统一解析引擎） =====
    ctn = container_no.strip().upper()
    biz_order_no = booking_no.strip()  # 业务单号 → order_no

    canon = um.map_port_to_fields(port_name, raw_text, container_no=container_no, booking_no=booking_no)
    # 船司订舱号/提单号 → bl_no（盐田提单号/蛇口订舱单号/青岛TDH/宁波[BL]段）
    bl = canon["bl_no"] or canon["booking_no"] or booking_no.strip()  # 兜底: 宁波 blno 即提单号
    size_type = canon["size_type"]
    seal = canon["seal"]
    gross_float = canon["gross"]
    eng_name = canon["vessel"]
    voyage = canon["voyage"]
    vessel_field = f"{eng_name} / {voyage}" if voyage else eng_name  # 显示格式 "船名 / 航次"
    terminal = canon["terminal"]
    eta = canon["eta"]
    etd = canon["etd"]
    dest_port = canon["dest"]
    pol_port = canon["pol"]
    owner = canon["owner"]
    pieces = canon["pieces"]
    volume_float = canon["volume"]

    # ===== 判断业务类型 =====
    # 只要有RPA传过来的柜号，就视为有集装箱 → FCL 整柜
    has_container = bool(ctn)
    has_seal = bool(seal)

    # ===== 港口状态 → FCL 推进状态映射 =====
    # 统一 status（青岛已装船/盐田在场/蛇口柜状态/宁波Full）+ 蛇口"当前位置"(VESSEL=在船)
    # 收集所有状态信号，按最晚的工作流阶段推进
    port_status_texts = [
        canon["status"],
        _extract_colon(raw_text, "当前位置") or "",              # 蛇口: VESSEL 0600990
    ]

    def _port_status_to_step(port_st: str) -> int:
        """港口状态关键词 → FCL step index（越大越晚）"""
        from backend.core.routers.fcl import STEP_KEYS
        s = port_st.upper()
        if any(k in s for k in ("已装船", "ON VESSEL", "VESSEL", "已开船", "SAILING")):
            return STEP_KEYS.index("sailing")       # 开船
        if any(k in s for k in ("已到港", "ARRIVED", "ARRIVAL")):
            return STEP_KEYS.index("arrived")        # 到港
        if any(k in s for k in ("提柜", "DELIVERY")):
            return STEP_KEYS.index("delivery")       # 提柜
        if any(k in s for k in ("返空", "EMPTY RETURN", "已还空")):
            return STEP_KEYS.index("empty_return")   # 还空
        if any(k in s for k in ("已放行", "RELEASED", "放行")):
            return STEP_KEYS.index("si_vgm")         # 补料/VGM
        # 重柜/在场/重箱 → 接单
        return STEP_KEYS.index("received")
    # 取所有状态字段中 map 到的最大 step index（最晚流程阶段）
    from backend.core.routers.fcl import STEP_KEYS as _SK
    best_idx = -1
    best_status = _FCL_ADVANCE_STATUS
    for txt in port_status_texts:
        if txt:
            s = txt.strip()
            if s:
                idx = _port_status_to_step(s)
                if idx > best_idx:
                    best_idx = idx
                    best_status = _SK[idx] if 0 <= idx < len(_SK) else _FCL_ADVANCE_STATUS
    mapped_status = best_status

    if has_container:
        module = "FCL"
    else:
        return result  # 无柜号，暂不同步

    if module == "FCL":
        # 查重：按柜号或船司订舱号
        existing = db.query(FCLOrder).filter(
            (FCLOrder.container_no == ctn) | (FCLOrder.bl_no == bl)
        ).first()

        if existing:
            old_status = existing.status
            _advance_fcl_status(existing, mapped_status)

            # 刷新所有字段
            if size_type:
                existing.container_type = size_type
            if eng_name:
                existing.vessel_name = eng_name
                existing.voyage = voyage or voyage_no
                existing.vessel = vessel_field or f"{vessel_name} / {voyage_no}"
            if terminal:
                existing.terminal = terminal
            if eta:
                existing.eta = eta
            if etd:
                existing.etd = etd
            if dest_port:
                existing.dest = dest_port
            if pol_port:
                existing.origin = pol_port
            if gross_float > 0:
                existing.gross_weight = gross_float
            if pieces > 0:
                existing.pieces = pieces
            if volume_float > 0:
                existing.volume = volume_float
            if bl:
                existing.bl_no = bl
            if seal:
                existing.seal_no = seal
            if owner:
                existing.carrier = owner

            from backend.core.routers.fcl import _add_log
            _add_log(existing, f"RPA{port_name}更新", f"柜号 {ctn} 数据刷新，状态推进")
            db.commit()
            result.update({
                "synced": True, "module": "FCL",
                "order_no": existing.order_no,
                "action": f"updated ({old_status}→{existing.status})",
            })
        else:
            # 创建新订单
            import random
            # 优先使用业务单号（前端传入 booking_no = SB-YYYYMMDDNNN），否则自动生成
            order_no = biz_order_no if biz_order_no else f"FCL-{datetime.now().strftime('%y%m%d')}-{random.randint(100, 999)}"
            route = f"{pol_port or '?'} → {dest_port or '?'}" if dest_port else ""

            order = FCLOrder(
                order_no=order_no,
                container_no=ctn,
                container_type=size_type,
                bl_no=bl,
                seal_no=seal,
                gross_weight=gross_float,
                pieces=pieces,
                volume=volume_float,
                vessel_name=eng_name or vessel_name,
                voyage=voyage or voyage_no,
                vessel=vessel_field or f"{vessel_name} / {voyage_no}",
                terminal=terminal,
                direction=_extract_colon(raw_text, "航向") or "",
                origin=pol_port,
                dest=dest_port,
                eta=eta,
                etd=etd,
                carrier=owner,
                route=route,
                status=mapped_status,
                progress=_progress_for_status(mapped_status),
            )
            from backend.core.routers.fcl import _add_log
            _add_log(order, f"RPA{port_name}创建", f"来自{port_name}查询: {ctn}")
            db.add(order)
            db.commit()
            db.refresh(order)
            result.update({
                "synced": True, "module": "FCL",
                "order_no": order.order_no,
                "action": "created",
            })

    return result


def _advance_fcl_status(order: FCLOrder, target_status: str):
    """推进 FCL 订单到目标状态（只进不退）"""
    from backend.core.routers.fcl import STEP_KEYS

    cur_idx = STEP_KEYS.index(order.status) if order.status in STEP_KEYS else -1
    target_idx = STEP_KEYS.index(target_status) if target_status in STEP_KEYS else -1

    if target_idx > cur_idx:
        order.status = target_status
        order.progress = int((target_idx + 1) / len(STEP_KEYS) * 100)
