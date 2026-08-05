# -*- coding: utf-8 -*-
"""
统一字段映射器 (Unified Field Mapper) v1
========================================
各港口 RPA 查询结果（原始文本）→ 统一规范字段 dict。

职责边界（用户确认，2026-08-04）：
  - 展示层：前端直接显示各港原始文本，不经过本模块 —— 保持现状不动
  - 录入层：仅当需要往佰信系统录入时，用本模块把各港原始结果解析成统一字段

输出字段对齐 merge_service.FIELD_RULES（16 规范字段）+ owner/status：
    container_no, size_type, seal, gross, booking_no, bl_no, vessel,
    voyage, terminal, pol, dest, etd, eta, pieces, volume, cargo_name,
    owner, status

架构三层：
  1. 提取器  — 通用匹配函数（行首冒号 / 盐田 tab 行 / 青岛管道 key=value）
  2. PORT_MAP — 每港原始标签 → 规范字段（声明式；列表内按优先级回退；
               {"join": [k1, k2]} 表示组合字段，如青岛 CC+XX → 箱型尺寸）
  3. normalize — 类型清洗（数值 / 日期 / 尺寸 ISO 后缀 / '--' 空值 / 数字大小写）

纯函数、无 DB、无副作用 → 可直接单元测试。

接入说明：rpa_sync.py 的 sync_from_port 已统一走本模块（方案B，2026-08-04）。
     本模块修复了旧链路缺失的盐田 "总重(kgs)" 提取。
"""
from __future__ import annotations

import re

# =====================================================================
# 1. 通用提取器（逻辑沿用 rpa_sync.py 已验证版本）
# =====================================================================


def _extract_colon(text: str, key: str) -> str:
    """提取行首 'key: val' 或 'key：val'（含前导空白行），tab 截断。"""
    pat = re.compile(r'(?:^|\n)\s*' + re.escape(key) + r'[：:]\s*([^\n]+)')
    m = pat.search(text)
    if m:
        val = m.group(1).strip()
        if '\t' in val:
            val = val.split('\t')[0].strip()
        return val
    return ""


def _extract_colon_ci(text: str, key: str) -> str:
    """大小写不敏感版（宁波港英文标签：Size/Type / Gross(KG) / Seal No 等）。"""
    pat = re.compile(r'(?:^|\n)\s*' + re.escape(key) + r'[：:]\s*([^\n]+)', re.IGNORECASE)
    m = pat.search(text)
    if m:
        val = m.group(1).strip()
        if '\t' in val:
            val = val.split('\t')[0].strip()
        return val
    return ""


def _extract_colon_any(text: str, key: str) -> str:
    """行首或行中（盐田 tab 多字段行的后半段也含 key：value）。"""
    pat = re.compile(r'(?:^|\n|\t)\s*' + re.escape(key) + r'[：:]\s*([^\n]+)')
    m = pat.search(text)
    if m:
        val = m.group(1).strip()
        if '\t' in val:
            val = val.split('\t')[0].strip()
        return val
    return ""


def _yantian_kv(text: str, key: str) -> str:
    """盐田 tab 分隔的多字段行：'尺寸'类型：\t40'HQ(45/G1)\t街车入闸时间：\t...'。

    只匹配包含 tab 的多字段行（排除单字段行首匹配）。
    """
    for line in text.split("\n"):
        if "\t" not in line:
            continue
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


def _extract_qd_kv(text: str, key: str) -> str:
    """青岛港管道分隔格式的 key=value（如 XH=SLEU2516841 | YWCM=PRESIDENT REAGAN）。"""
    pat = re.compile(r'(?:^|\|)\s*' + re.escape(key) + r'=([^|\n]+)')
    m = pat.search(text)
    return m.group(1).strip() if m else ""


def _qd_field(section: str, key: str) -> str:
    """从青岛港某个 section 提取字段值。"""
    v = _extract_qd_kv(section, key)
    return v if v else ""


# =====================================================================
# 2. 每港字段映射表（声明式：规范key → 原始标签列表，按优先级回退）
# =====================================================================

PORT_MAP = {
    "盐田港": {
        "container_no": ["集装箱号"],
        "size_type": ["尺寸’类型", "尺寸'类型", "尺寸"],
        "seal": ["封条号"],
        "gross": ["总重(kgs)", "总重(KGS)", "总重", "毛重(KG)", "毛重"],
        "booking_no": ["订舱号"],
        "bl_no": ["提单号"],
        "vessel": ["船舶名称", "船名", "船舶"],
        "voyage": ["航次"],
        "terminal": ["当前场地", "码头"],
        "pol": ["装货港"],
        "dest": ["卸货港", "目的港"],
        "eta": ["到达码头时间", "街车入闸时间", "到港时间", "进场时间"],
        "etd": ["街车出闸时间", "离港时间", "出场时间"],
        "owner": ["箱主"],
        "status": ["集装箱状态", "当前动态"],
        "pieces": [],
        "volume": [],
    },
    "蛇口港": {
        "container_no": ["柜号"],
        "size_type": ["尺寸/类型"],
        "seal": ["封条号"],
        "gross": ["毛重(KG)", "毛重"],
        "booking_no": ["订舱单号"],
        "bl_no": ["提单号"],
        "vessel": ["离港船名航次", "进港船名航次"],
        "voyage": ["出口商业航次"],
        "terminal": ["当前位置"],
        "pol": ["装货港"],
        "dest": ["目的港", "卸货港"],
        "eta": ["进场时间", "到港时间"],
        "etd": ["出场时间", "离港时间"],
        "owner": ["箱属"],
        "status": ["柜状态", "放行状态"],
        "pieces": [],
        "volume": [],
    },
    "青岛港": {
        "container_no": ["XH", "XH1"],
        "size_type": {"join": ["CC", "XX"]},
        "seal": ["QFH", "QFH1"],
        "gross": ["MZ", "MZ1"],
        "booking_no": ["TDH"],
        "bl_no": ["TDH"],
        "vessel": ["YWCM", "CKYWCM"],
        "voyage": ["CKHC", "HCHC"],
        "terminal": ["MTMC"],
        "pol": ["ZHGYM", "ZHGM"],
        "dest": ["MDGM", "MDG"],
        "eta": ["SJRGSJ", "INSERTSJ", "SJCGSJ"],
        "etd": ["SJCGSJ1", "SJRGSJ1"],
        "owner": ["XSGSM"],
        "status": ["DQZTMC"],
        "pieces": [],
        "volume": [],
    },
    "宁波港": {
        "container_no": [],
        "size_type": ["Size/Type"],
        "seal": ["Seal No"],
        "gross": ["Gross(KG)", "GrossWeight", "Wt"],
        "booking_no": [],
        "bl_no": [],
        "vessel": ["Vessel"],
        "voyage": ["Voyage"],
        "terminal": ["Terminal"],
        "pol": [],
        "dest": ["Port", "Discharge Port"],
        "eta": ["ETA"],
        "etd": ["ETD"],
        "owner": ["Owner"],
        "status": ["Status"],
        "pieces": ["Pkgs", "PackageNum"],
        "volume": ["Vol", "Measure"],
    },
}


# 规范字段全集（保证任何输入都输出稳定结构，未知港口时全部为空）
CANONICAL_KEYS = [
    "container_no", "size_type", "seal", "gross", "booking_no", "bl_no",
    "vessel", "voyage", "terminal", "pol", "dest", "eta", "etd",
    "owner", "status", "pieces", "volume", "cargo_name",
]


def _make_extractor(port_name: str, text: str):
    """返回按港口选择的提取闭包 (key) -> str。青岛预定位出口码头 section。"""
    if "青岛" in port_name:
        m = re.search(r'【出口-码头信息】\([^)]*\)\s*\n(.*?)(?:\n\n|\Z)', text, re.DOTALL)
        section = m.group(1) if m else ""
        return lambda key: _qd_field(section, key) or _extract_qd_kv(text, key)
    if "盐田" in port_name:
        return lambda key: _yantian_kv(text, key) or _extract_colon_any(text, key)
    if "宁波" in port_name:
        return lambda key: _extract_colon_ci(text, key)
    # 蛇口及默认：行首中文标签
    return lambda key: _extract_colon(text, key)


def _resolve_entry(get, entry) -> str:
    """解析映射表条目：str = 单个标签；list = 优先级回退；{"join": [...]} = 组合拼接。"""
    if isinstance(entry, str):
        v = get(entry)
        return v if v and _clean(v) else ""
    if isinstance(entry, list):
        for label in entry:
            if not label:
                continue
            v = get(label)
            if v and _clean(v):
                return v
        return ""
    if isinstance(entry, dict) and "join" in entry:
        return "".join(_resolve_entry(get, sub) for sub in entry["join"])
    return ""


# =====================================================================
# 3. normalize — 类型清洗
# =====================================================================

_NUMERIC_FIELDS = {"gross", "pieces", "volume"}
_DATE_FIELDS = {"eta", "etd"}
_SIZE_FIELDS = {"size_type"}


def _clean(val) -> str:
    """去空值占位符（'--'/'N/A' 等）与首尾空白。"""
    if val is None:
        return ""
    v = str(val).strip()
    if v in ("--", "-", "N/A", "None", "null"):
        return ""
    return v


def _num(val):
    """提取数字 → int/float；无效返回 0（对齐 merge_service._has_value，0 视为缺失）。"""
    s = re.sub(r'[^\d.]', '', str(val))
    if not s:
        return 0
    try:
        f = float(s)
        return int(f) if f == int(f) else f
    except ValueError:
        return 0


def _date(val) -> str:
    """截断为 YYYY-MM-DD（对齐 _baixin_merge_fill.fmt_date）。"""
    s = _clean(val)
    if not s:
        return ""
    s = s.split("T")[0]
    s = s.replace("/", "-")
    return s[:10] if len(s) >= 10 else s


def _clean_size(val) -> str:
    """箱型清洗：截断蛇口 '40'HQ  ISO: 22G1' 中的 ISO 后缀。"""
    s = _clean(val)
    if "  ISO" in s:
        s = s.split("  ISO")[0].strip()
    return s


def normalize(canon: dict) -> dict:
    """按字段类型清洗。"""
    out = {}
    for k, v in canon.items():
        if k in _NUMERIC_FIELDS:
            out[k] = _num(v)
        elif k in _DATE_FIELDS:
            out[k] = _date(v)
        elif k in _SIZE_FIELDS:
            out[k] = _clean_size(v)
        else:
            out[k] = _clean(v)
    return out


# =====================================================================
# 后处理：跨字段逻辑（vessel/voyage 拆分、terminal VESSEL 排除、宁波 [BL] 提单）
# =====================================================================


def _post_process(port_name: str, text: str, canon: dict) -> dict:
    # 船名/航次拆分：'OOCL ITALY/155S' → vessel='OOCL ITALY'，voyage 用已有的或取后半
    v = canon.get("vessel", "")
    if v:
        parts = re.split(r'[/／]', v)
        if len(parts) > 1:
            canon["vessel"] = parts[0].strip()
            if not canon.get("voyage"):
                canon["voyage"] = parts[1].strip()

    # 蛇口 '当前位置: VESSEL 0600990' 表示已在船上，不是码头
    term = canon.get("terminal", "")
    if term.upper().startswith("VESSEL"):
        canon["terminal"] = ""

    # 宁波提单段 '[BL WHL061G554006]'
    if "宁波" in port_name and not canon.get("bl_no"):
        m = re.search(r'\[BL\s+([^\]]+)\]', text)
        if m:
            canon["bl_no"] = m.group(1).strip()
        if not canon.get("booking_no"):
            canon["booking_no"] = canon["bl_no"]

    return canon


# =====================================================================
# 主入口
# =====================================================================


def map_port_to_fields(port_name: str, raw_text: str,
                       container_no: str = "", booking_no: str = "") -> dict:
    """
    各港 RPA 查询原始文本 → 统一规范字段 dict。

    参数：
        port_name   港口名（'盐田港'/'蛇口港'/'青岛港'/'宁波港'，可含前缀）
        raw_text    driver.query_container 返回的原始 data 文本
        container_no 查询柜号（宁波无柜号标签时兜底）
        booking_no   查询订舱号/提单号（宁波 blno 即提单号时兜底）

    返回：
        规范字段 dict，key 对齐 merge_service.FIELD_RULES + owner/status；
        gross/pieces/volume 为数字（0=缺失），eta/etd 为 YYYY-MM-DD。
        可直接作为 merge preview 的 query_fields，或佰信填写 merged 的查询部分。
    """
    port_name = port_name or ""
    text = raw_text or ""
    get = _make_extractor(port_name, text)
    mapping = PORT_MAP.get(port_name, {})

    canon = {k: "" for k in CANONICAL_KEYS}
    for ckey, entry in mapping.items():
        canon[ckey] = _resolve_entry(get, entry)

    # 前端参数兜底（宁波 blno/柜号依赖参数）
    ctn = (container_no or "").strip().upper()
    if ctn:
        canon["container_no"] = ctn
    elif canon.get("container_no"):
        canon["container_no"] = canon["container_no"].strip().upper()
    if (booking_no or "").strip() and not canon.get("booking_no"):
        canon["booking_no"] = booking_no.strip()

    canon["cargo_name"] = ""
    canon = _post_process(port_name, text, canon)
    return normalize(canon)


# 单测快速入口
if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("map_port_to_fields(port_name, raw_text, container_no, booking_no) → dict")
