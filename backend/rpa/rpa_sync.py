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


def _extract_qd_kv(text: str, key: str) -> str:
    """提取青岛港管道分隔格式的 key=value（如 XH=SLEU2516841 | YWCM=PRESIDENT REAGAN）"""
    pat = re.compile(r'(?:^|\|)\s*' + re.escape(key) + r'=([^|\n]+)')
    m = pat.search(text)
    return m.group(1).strip() if m else ""


def _qd_field(section: str, key: str, fallback: str = "") -> str:
    """从青岛港某个 section 提取字段值"""
    v = _extract_qd_kv(section, key)
    return v if v else fallback


def _yantian_kv(text: str, key: str) -> str:
    """从盐田港 tab 分隔的多字段行提取 key:value

    盐田输出每行多个 key:value 以 tab 分隔，key 在行中：
        L6: "尺寸’类型：\t40’HQ(45/G1)\t街车入闸时间：\t2026-07-06 17:22"

    只匹配包含 tab 的多字段行（排除单字段行首匹配）。
    """
    for line in text.split("\n"):
        if "\t" not in line:
            continue  # 跳过非 tab 行（单字段行首）
        sep = None
        for s in ("：", ":"):
            if key + s in line:
                sep = s
                break
        if sep is None:
            continue
        idx = line.find(key + sep)
        if idx < 0:
            continue
        after = line[idx + len(key) + len(sep):].strip()
        if "\t" in after:
            after = after.split("\t")[0].strip()
        return after
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

    # ===== 统一字段提取 =====
    ctn = container_no.strip().upper()
    biz_order_no = booking_no.strip()  # 业务单号 → order_no

    # ===== 青岛港专用解析（| 管道分隔的 key=value 格式） =====
    is_qingdao = "青岛" in port_name
    is_yantian = "盐田" in port_name
    qd_section = ""
    if is_qingdao:
        m = re.search(r'【出口-码头信息】\([^)]+\)\s*\n(.*?)(?:\n\n|\Z)', raw_text, re.DOTALL)
        if m:
            qd_section = m.group(1)

    # 从港口输出中提取真正的订舱单号/提单号
    booking_no_from_port = (
        _extract_colon(raw_text, "订舱单号") or  # 蛇口/盐田
        _extract_colon(raw_text, "提单号") or     # 宁波: 提单号：WHL061G554006
        _extract_colon(raw_text, "定舱号") or
        _extract_colon(raw_text, "BookingNo") or
        (_qd_field(qd_section, "TDH") if is_qingdao else "") or  # 青岛: TDH=QGD3131565
        _yantian_kv(raw_text, "订舱号") or  # 盐田 tab: 订舱号：\t272977891
        booking_no.strip() or  # fallback: 前端传入参数本身就是提单号（如宁波港）
        ""
    )
    bl = booking_no_from_port  # 真正的船司订舱号 → bl_no

    # 箱型（从各港口输出中提取）
    size_type = (  # 按优先级尝试
        _extract_colon(raw_text, "尺寸/类型") or     # 蛇口
        _extract_colon(raw_text, "箱型尺寸") or        # NPEDI
        _extract_colon(raw_text, "箱型") or            # 通用
        _extract_colon(raw_text, "尺寸") or            # 盐田: "尺寸：20GP"
        _extract_colon(raw_text, "尺寸’类型") or       # 盐田: "尺寸’类型(Unicode U+2019)：40'HQ(45/G1)"
        _yantian_kv(raw_text, "尺寸’类型") or          # 盐田 tab 分隔行
        _extract_colon(raw_text, "SzTpHt") or          # 蛇口英文
        (f"{_qd_field(qd_section, 'CC')}{_qd_field(qd_section, 'XX')}" if is_qingdao else "") or  # 青岛: CC=20 + XX=GP → 20GP
        ""
    )

    # 毛重
    gross_str = (
        _extract_colon(raw_text, "毛重(KG)") or
        _extract_colon(raw_text, "毛重(KGS)") or
        _extract_colon(raw_text, "箱重") or
        _extract_colon(raw_text, "GrossWeight") or
        _extract_colon(raw_text, "称重") or
        (_qd_field(qd_section, "MZ") if is_qingdao else "") or  # 青岛: MZ=15454
        ""
    )
    try:
        gross_float = float(re.sub(r'[^\d.]', '', gross_str))
    except (ValueError, TypeError):
        gross_float = 0

    # 封条号
    seal = (
        _extract_colon(raw_text, "封条号") or
        _extract_colon(raw_text, "铅封") or
        _extract_colon(raw_text, "SealNbr1") or
        _yantian_kv(raw_text, "封条号") or  # 盐田 tab 行
        (_extract_qd_kv(raw_text, "QFH") or _extract_qd_kv(raw_text, "QFH1") if is_qingdao else "") or  # 青岛: QFH=M/M7645744
        ""
    )

    # 船名/航次
    # 注意：蛇口港 "进港船名航次" 是拖车牌号/行程（粤BQL723/26061303298）
    #       "离港船名航次" 才是真船名（OOCL ITALY/155S）
    # 注意：盐田港 "船舶名称" 才是船名，"船舶" 是箱属缩写
    vessel_field = (
        _extract_colon(raw_text, "英文船名") or           # NPEDI
        _extract_colon(raw_text, "船舶名称") or            # 盐田: MAERSK SAIGON
        _yantian_kv(raw_text, "船舶名称") or               # 盐田 tab 行
        _extract_colon(raw_text, "船名航次") or           # 通用
        _extract_colon(raw_text, "离港船名航次") or       # 蛇口: "OOCL ITALY/155S"
        _extract_colon(raw_text, "船舶") or               # 盐田: "COSCO SHIPPING RHEIN / 224W"
        _extract_colon(raw_text, "船名") or               # 通用
        _extract_colon(raw_text, "进港船名航次") or       # 最低（蛇口此为拖车信息）
        (_qd_field(qd_section, "CKYWCM") or _qd_field(qd_section, "YWCM") if is_qingdao else "") or  # 青岛: CKYWCM=PRESIDENT REAGAN
        ""
    )
    # 单独的航次字段（盐田/青岛等单位字段）
    voyage_only = (
        _extract_colon(raw_text, "出口商业航次") or        # 蛇口: 155S
        _extract_colon(raw_text, "航次") or                # 盐田: GM/MSKSAI/627E
        _yantian_kv(raw_text, "航次") or                   # 盐田 tab 行
        ""
    )
    # 青岛航次
    qd_voyage = _qd_field(qd_section, "CKHC") or _qd_field(qd_section, "HCHC") if is_qingdao else ""
    eng_name = voyage = ""
    if vessel_field:
        parts = re.split(r'[/／]', vessel_field)
        eng_name = parts[0].strip()
        if len(parts) > 1:
            voyage = parts[1].strip()
        elif voyage_only:
            voyage = voyage_only  # 蛇口"出口商业航次"只有航次号
        elif qd_voyage:
            voyage = qd_voyage  # 青岛: CKHC=0DBORE

    # 码头（蛇口"当前位置: VESSEL 0600990"不是在码头，是已在船上）
    terminal = _extract_colon(raw_text, "当前场地") or ""  # 盐田: YICT
    if not terminal:
        t = _extract_colon(raw_text, "当前位置") or ""    # 蛇口
        if t and not t.upper().startswith("VESSEL"):
            terminal = t
    if not terminal:
        terminal = _extract_colon(raw_text, "码头") or ""  # NPEDI
    if not terminal and is_qingdao:
        terminal = _qd_field(qd_section, "MTMC") or ""    # 青岛: MTMC=QQCTU码头

    # ETA/ETD
    eta = _extract_colon(raw_text, "到港时间") or _extract_colon(raw_text, "进场时间") or ""
    etd = _extract_colon(raw_text, "离港时间") or _extract_colon(raw_text, "出场时间") or ""
    if not eta and is_qingdao:
        eta = _qd_field(qd_section, "SJCGSJ") or ""  # 青岛: 实际进场时间
        if not eta:
            for qkey in ("SJRGSJ", "INSERTSJ"):
                v = _qd_field(qd_section, qkey)
                if v and "1900" not in v:
                    eta = v
                    break
    if not eta:
        eta = _yantian_kv(raw_text, "街车入闸时间") or _extract_colon(raw_text, "街车入闸时间") or ""
        if not eta:
            eta = _yantian_kv(raw_text, "到达码头时间") or _extract_colon(raw_text, "到达码头时间") or ""
    if not etd:
        etd = _yantian_kv(raw_text, "街车出闸时间") or _extract_colon(raw_text, "街车出闸时间") or ""
    # 青岛 ETD：用入闸时间或入场时间（已装船的柜没有离港时间）
    if not etd and is_qingdao:
        for qkey in ("SJRGSJ", "SJRGSJ1", "INSERTSJ", "SJCGSJ"):
            v = _qd_field(qd_section, qkey)
            if v and "1900" not in v and v != eta:
                etd = v
                break

    # 目的港/卸货港
    dest_port = (
        _extract_colon(raw_text, "目的港") or
        _yantian_kv(raw_text, "卸货港") or               # 盐田 tab: 卸货港：PUSAN/BUSAN...
        _extract_colon(raw_text, "卸货港") or            # 盐田: 卸货港
        _extract_colon(raw_text, "装/卸货港口") or
        _extract_colon(raw_text, "当前动态") or          # 盐田: "返空"
        (_qd_field(qd_section, "MDGM") if is_qingdao else "") or  # 青岛: MDGM=USOAK
        ""
    )
    pol_port = _extract_colon(raw_text, "装货港") or ""
    if not pol_port and is_qingdao:
        pol_port = _qd_field(qd_section, "ZHGYM") or _qd_field(qd_section, "ZHGM") or ""  # 青岛: ZHGYM=QINGDAO

    # 箱属
    owner = (_extract_colon(raw_text, "箱属公司") or       # 盐田
             _extract_colon(raw_text, "箱属") or           # 蛇口
             _extract_colon(raw_text, "箱主") or           # NPEDI
             (_qd_field(qd_section, "XSGSM") if is_qingdao else "") or  # 青岛: XSGSM=CMA
             "")

    # 件数/体积（尝试从提单明细行提取）
    pieces = 0
    volume_str = ""
    bl_lines = re.findall(r'([A-Z0-9]{6,})\s+\d+\s+[\d.]+\s+[\d.]+', raw_text)
    if not bl_lines:
        bl_lines = re.findall(r'(\d+)[^\d]*件', raw_text)
    if bl_lines:
        try:
            pieces = int(bl_lines[-1]) if isinstance(bl_lines[-1], str) and bl_lines[-1].isdigit() else 0
        except (ValueError, IndexError):
            pieces = 0
    vol_match = re.search(r'体积[：:]\s*([\d.]+)', raw_text)
    if vol_match:
        volume_str = vol_match.group(1)
    try:
        volume_float = float(volume_str) if volume_str else 0
    except ValueError:
        volume_float = 0

    # ===== 判断业务类型 =====
    # 只要有RPA传过来的柜号，就视为有集装箱 → FCL 整柜
    has_container = bool(ctn)
    has_seal = bool(seal)

    # ===== 港口状态 → FCL 推进状态映射 =====
    # 收集所有港口状态字段，按最晚的工作流阶段推进
    port_status_texts = [
        _qd_field(qd_section, "DQZTMC") if is_qingdao else "",  # 青岛: 已装船
        _extract_colon(raw_text, "集装箱状态") or _yantian_kv(raw_text, "集装箱状态") or "",  # 盐田 tab 行中
        _extract_colon(raw_text, "当前位置") or "",              # 蛇口: VESSEL 0600990
        _extract_colon(raw_text, "当前动态") or "",              # 盐田: 返空
        _extract_colon(raw_text, "放行状态") or "",              # 蛇口: 已放行
        _extract_colon(raw_text, "柜状态") or "",                # 蛇口: 重柜
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
