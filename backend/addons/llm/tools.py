"""
MiniMax M3 工具调用 — RPA 集装箱查询 / 码头状态查询
"""
from __future__ import annotations

# ===== 工具定义（OpenAI Function Calling 格式） =====

RPA_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_container",
            "description": "查询集装箱在港口的在场状态、海关放行、进港时间、是否可提柜等信息。需要提供柜号，港口名称可选。",
            "parameters": {
                "type": "object",
                "properties": {
                    "container_no": {
                        "type": "string",
                        "description": "集装箱号/柜号，例如 TEMU1234567"
                    },
                    "port_name": {
                        "type": "string",
                        "description": "港口名称，可选。不提供则自动判断。可选值：盐田、蛇口、上海、宁波、青岛",
                        "enum": ["盐田", "蛇口", "上海", "宁波", "青岛"]
                    }
                },
                "required": ["container_no"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_port_status",
            "description": "查询码头的最新通知公告、运营状态、台风/拥堵/系统升级等异常公告。",
            "parameters": {
                "type": "object",
                "properties": {
                    "port_name": {
                        "type": "string",
                        "description": "港口名称。可选值：盐田、蛇口、上海、宁波、青岛",
                        "enum": ["盐田", "蛇口", "上海", "宁波", "青岛"]
                    }
                },
                "required": ["port_name"]
            }
        }
    },
]

# ===== 佰信订舱录入工具（字段对齐 → 待用户确认，不在服务端执行） =====

# 佰信待确认标记：execute 返回带此前缀时，调用方需转成前端确认卡（tool_confirm）
BAIXIN_PENDING_PREFIX = "__BAIXIN_PENDING__"

# LLM 字段对齐映射（key: 中文名），空运95字段/海运55字段的常用子集
BAIXIN_FIELD_MAP_TEXT = (
    "空运模板字段(key: 中文)：work_no:工作号, issue_date:开单日期, operator:业务/操作, doc_cs:单证/客服, "
    "carrier:航空公司, mawb_no:主单号, hawb_no:分单号, client_ref:委托号, consignor:委托人, "
    "consignor_contact:委托人-联系人, consignor_phone:委托人-电话, shipper:发货人, shipper_contact:发货人-联系人, "
    "shipper_phone:发货人-电话, consignee:收货人, notify:通知人, overseas_agent:国外代理, air_agent:空运代理, "
    "paid_shipper:排载发货人, paid_consignee:排载收货人, flight1:航班一, etd:ETD, eta:ETA, "
    "service_term:服务条款, origin:始发站, route:航线, dest:目的站, solicit_type:揽货类型, currency:币别, "
    "price_per:按约价, pieces:件数, package_unit:包装, weight:重量, charge_weight:计重, volume:体积, "
    "charge_volume:计体, cost:成本, rate:运价, pay_method:付款方式, main_hbl:主/分单, coload:Co-Load, "
    "import_export:进/出口, warehousing:进仓, normal_offload:正常/退载, insurance:保险, release:放货, "
    "contract_no:合约号, transship:转运, partial:分批, cargo_desc:物品描述, booking_remark:订舱备注, "
    "booking_confirm:订舱确认, handover:业务交接, etp:ETP, atd:ATD, ata:ATA\n"
    "海运模板字段(key: 中文)：client_ref:客户委托号, so_no:S/O NO, operator:操作员, bl_no:船东提单号, "
    "hbl_no:1st H/BL, scac:SCAC COD, vessel_en:英文船名, vessel_cn:中文船名, terminal:航次, route:航线, "
    "etd:ETD, eta:ETA, cutoff:截行条, consignor:委托人, shipper:发货人, consignee:收货人, notify:通知人, "
    "booking_consignor:排载发货人, booking_consignee:排载收货人, ship_agent:船代, owner:船东, pol:装运港, "
    "transit:中转港, dest_unload:卸货港, dest:目的港, overseas_agent:国外代理, solicit_type:揽货类型, "
    "pieces:件数, package_unit:包装, gross:毛重, volume:体积, truck_mode:拖车场装, customs_mode:报关方式, "
    "size_type:箱型箱重, cargo_name:货物简称, contract_no:合约号, remark:备注"
)

BAIXIN_FILL_TOOL = {
    "type": "function",
    "function": {
        "name": "baixin_merge_fill",
        "description": (
            "把用户提供的订舱字段内容对齐到佰信录入模板并准备自动填入。"
            "用户可能直接口述字段或粘贴订舱单/表格文本。"
            "步骤：①判断海运或空运（用户未明说时：工作号SB-A前缀或含航班号/始发站→空运；SB-S前缀或含船名/柜号/装运港→海运；"
            "否则根据航线、目的地等特征推理）；②按对应模板把每个字段映射到key，尽量用模板字段key；"
            "③只填用户提供或有把握推断的字段，不要臆造。\n"
            "可用字段key(merged里的key必须用这些)：\n" + BAIXIN_FIELD_MAP_TEXT
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["sea", "air"],
                    "description": "海运(sea)或空运(air)。用户未明说时自行推理",
                },
                "order_no": {
                    "type": "string",
                    "description": "佰信工作号/检索值，如 SB-A26080130(空运) / SB-S26080130(海运)。用户给到才填",
                },
                "container_no": {
                    "type": "string",
                    "description": "柜号（海运常用），用户给到才填",
                },
                "merged": {
                    "type": "object",
                    "description": "对齐后的字段字典，key必须用模板字段key，value为字段值。只填用户提供或可推断的字段",
                },
                "summary": {
                    "type": "string",
                    "description": "给用户看的字段对齐摘要，说明识别到了哪些字段（中文）",
                },
            },
            "required": ["mode", "merged", "summary"],
        },
    },
}

# ===== 佰信费用录入工具（应收应付登记） =====

# 费用字段对齐映射（key: 中文名）—— 海运/空运应收应付登记
BAIXIN_FEE_FIELD_MAP_TEXT = (
    "费用字段(key: 中文)：trader:往来单位(共用), recv_trader:应收-往来单位, "
    "recv_amount:应收, recv_qty:应收-数量, recv_price:应收-单价, "
    "pay_trader:应付-往来单位, pay_amount:应付, pay_qty:应付-数量, pay_price:应付-单价\n"
    "说明：recv_* 填应收网格、pay_* 填应付网格，只给一组也行；"
    "未给 recv_trader/pay_trader 时用 trader 作该网格往来单位"
)

BAIXIN_FEE_FILL_TOOL = {
    "type": "function",
    "function": {
        "name": "baixin_fee_fill",
        "description": (
            "把用户提供的海运/空运应收应付费用内容对齐到佰信费用录入模板并准备自动填入。"
            "用于「应收应付登记/费用录入/费用登记」，把费用往来单位、金额、数量、单价填入佰信的费用编辑弹窗。"
            "步骤：①判断海运或空运（工作号SB-A前缀→空运；SB-S前缀→海运；用户未给单号时按上下文判断）；"
            "②把字段映射到key：应收填 recv_*，应付填 pay_*，往来单位两者共用 trader；"
            "③只填用户提供或有把握推断的字段，不要臆造。\n"
            "可用字段key(merged里的key必须用这些)：\n" + BAIXIN_FEE_FIELD_MAP_TEXT
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["sea", "air"],
                    "description": "海运(sea)或空运(air)。用户未明说时按单号前缀推理",
                },
                "order_no": {
                    "type": "string",
                    "description": "佰信工作号/检索值，如 SB-A26080130(空运) / SB-S26080130(海运)",
                },
                "merged": {
                    "type": "object",
                    "description": "对齐后的费用字段字典，key必须用费用模板key，value为字段值。只填用户提供或可推断的字段",
                },
                "summary": {
                    "type": "string",
                    "description": "给用户看的费用字段摘要，说明识别到了应收/应付哪些内容（中文）",
                },
            },
            "required": ["mode", "merged", "summary"],
        },
    },
}


# ===== OAIW 业务工具（保函 / 箱单合并 / 账单） =====
# schema 与 workflow/tools.py 的 TOOLS 保持一致（workflow 从本文件单一来源导出）

OAIW_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "generate_dg_letter",
            "description": (
                "生成非危保函（危险品/化工品/电池货物）。用户说「非危保函」「电池保函」「化工品保函」时调用。"
                "若用户上传了非危保函 docx 模板，template_file 填该模板文件名（见消息中 ## 清单）；"
                "只填确为 .docx 的模板，提单/MSDS/鉴定书等参考文件不要填，缺失字段留空。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "carrier": {"type": "string", "description": "船公司或航司名称"},
                    "port_of_loading": {"type": "string", "description": "起运港"},
                    "goods_name": {"type": "string", "description": "货物名称（中英文）"},
                    "danger_class": {"type": "string", "description": "危险品类别 UN编号，如 UN3481"},
                    "container_no": {"type": "string", "description": "柜号（可选）"},
                    "vessel": {"type": "string", "description": "船名（可选）"},
                    "voyage": {"type": "string", "description": "航次（可选）"},
                    "bl_no": {"type": "string", "description": "提单号（可选）"},
                    "port_of_discharge": {"type": "string", "description": "卸货港（可选）"},
                    "中文品名": {"type": "string", "description": "中文品名（可选，用于模板填写）"},
                    "英文品名": {"type": "string", "description": "英文品名（可选，用于模板填写）"},
                    "CAS_NO": {"type": "string", "description": "CAS 号（可选，用于模板填写）"},
                    "外观与性状": {"type": "string", "description": "外观与性状（可选，用于模板填写）"},
                    "主要用途": {"type": "string", "description": "主要用途（可选，用于模板填写）"},
                    "shipper": {"type": "string", "description": "发货人（可选）"},
                    "consignee": {"type": "string", "description": "收货人（可选）"},
                    "template_file": {"type": "string", "description": "对话上传的非危保函 docx 模板文件名（可选）"},
                },
                "required": ["carrier", "port_of_loading", "goods_name", "danger_class"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_telex_letter",
            "description": (
                "生成电放保函。用户说「电放保函」「电放」「telex release」时调用。"
                "只要用户提供了船公司、提单号、柜号就立即生成；起运港/卸货港/发货人/收货人为可选字段，"
                "缺失时在保函中留空即可，不要向用户追问可选字段。"
                "若用户上传了电放 docx 模板，template_file 填该模板文件名（见消息中 ## 清单）；"
                "只填确为 .docx 的模板，提单等参考文件不要填。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "carrier": {"type": "string", "description": "船公司名称"},
                    "port_of_loading": {"type": "string", "description": "起运港"},
                    "port_of_discharge": {"type": "string", "description": "卸货港"},
                    "bill_of_lading_no": {"type": "string", "description": "提单号"},
                    "container_no": {"type": "string", "description": "柜号"},
                    "shipper": {"type": "string", "description": "发货人"},
                    "consignee": {"type": "string", "description": "收货人"},
                    "vessel": {"type": "string", "description": "船名（可选）"},
                    "voyage": {"type": "string", "description": "航次（可选）"},
                    "date": {"type": "string", "description": "开船日期（可选）"},
                    "shipper_address": {"type": "string", "description": "发货人地址（可选，用于模板填写）"},
                    "consignee_details": {"type": "string", "description": "收货人详细信息（可选，用于模板填写）"},
                    "cargo_description": {"type": "string", "description": "货物描述（可选，用于模板填写）"},
                    "template_file": {"type": "string", "description": "对话上传的电放 docx 模板文件名（可选）"},
                },
                "required": ["carrier", "bill_of_lading_no", "container_no"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "merge_invoice_packing",
            "description": "合并多家工厂的箱单发票为一份总文件。用户说「合并箱单」「拼柜箱单发票」时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_no": {"type": "string", "description": "业务单号"},
                    "factory_count": {"type": "integer", "description": "工厂数量"},
                },
                "required": ["order_no"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fill_baixin_bill",
            "description": (
                "录入账单到佰信系统。用户说「录账单」「录入佰信」「同行账单录入」时调用。"
                "注意：费用明细录入（应收/应付/往来单位/金额/数量/单价）请用 baixin_fee_fill；"
                "本工具仅用于账单类型为『同行账单/代理账单』的整体账单录入。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "bill_type": {
                        "type": "string",
                        "enum": ["同行账单", "代理账单"],
                        "description": "账单类型",
                    },
                    "order_no": {"type": "string", "description": "业务单号"},
                    "amount": {"type": "number", "description": "金额"},
                    "currency": {"type": "string", "description": "币种 USD/RMB/HKD"},
                },
                "required": ["bill_type", "order_no", "amount"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_email_to_user",
            "description": (
                "用当前用户自己的 SMTP 邮箱发送邮件。用户说「发送到我的邮箱」「发给我」「把…发邮件/发给客户」"
                "「把…发送到 xxx@xx.com」等意图时调用。"
                "收件人、主题、正文从用户对话中提取；内容较多时整理成简洁段落。"
                "用户说『我的邮箱』或没给具体收件地址时，to_email 留空（会自动发送到当前用户自己的邮箱）。"
                "若用户未配置邮箱，工具会返回提示引导其先到【邮箱设置】配置。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "to_email": {
                        "type": "string",
                        "description": "收件人邮箱地址。用户明确给出邮箱时填；说『我的邮箱/发给我』未给地址时留空（将发送到当前用户自己的邮箱）",
                    },
                    "subject": {"type": "string", "description": "邮件主题"},
                    "content": {"type": "string", "description": "邮件正文内容"},
                },
                "required": ["subject", "content"],
            },
        }
    },
]


async def _merge_invoice_packing(order_no: str, factory_count: int = 0) -> str:
    """按业务单号收集已上传的箱单/发票文件，合并文本并落盘到 _merge_outputs/。"""
    import os
    import asyncio
    from backend.parser import extract_text
    from backend.config import settings

    order_no = (order_no or "").strip()
    if not order_no:
        return "❌ 合并箱单发票：缺少业务单号（order_no），请提供工作号。"

    key = order_no.lower()
    docs_dir = os.path.join(settings.UPLOAD_DIR, "docs")
    ctx_root = os.path.join(settings.UPLOAD_DIR, "context_files")
    dirs = [docs_dir]
    if os.path.isdir(ctx_root):
        dirs.append(ctx_root)

    def _iter_paths():
        for d in dirs:
            if not os.path.isdir(d):
                continue
            if d == ctx_root:
                for root, _ds, fs in os.walk(ctx_root):
                    for f in fs:
                        yield os.path.join(root, f)
            else:
                for f in sorted(os.listdir(d)):
                    yield os.path.join(d, f)

    paths = list(_iter_paths())
    # 阶段1：文件名匹配（小写不敏感）
    matched = [p for p in paths if key in os.path.basename(p).lower()]
    # 阶段2：正文内容匹配（箱单/发票正文通常含工作号；限制扫描量防慢）
    if not matched and len(paths) <= 60:
        for p in paths:
            try:
                text = await asyncio.to_thread(extract_text, p)
            except Exception:
                continue
            if key in (text or "").lower():
                matched.append(p)

    if not matched:
        return (
            f"❌ 未在已上传文件中找到含工作号「{order_no}」的箱单/发票文件。\n"
            "请先在对话中上传含该工作号的箱单/发票文件（或到文档管理上传），再重新合并。"
        )

    out_dir = os.path.join(os.path.dirname(os.path.abspath(settings.UPLOAD_DIR)), "_merge_outputs")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{order_no}_invoice_packing.txt")

    parts = []
    for p in matched:
        try:
            t = await asyncio.to_thread(extract_text, p)
        except Exception as e:
            t = f"[提取失败: {e}]"
        parts.append(f"===== {os.path.basename(p)} =====\n{t}")
    merged = "\n\n".join(parts)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(merged)

    lines = [f"✅ 已合并 {len(matched)} 个文件（工作号 {order_no}）："]
    if factory_count:
        lines.append(f"你提到 {factory_count} 家工厂，实际找到 {len(matched)} 个文件。")
    lines += [f"• {os.path.basename(p)}" for p in matched]
    lines.append(f"合并结果已保存到 {out_path}")
    lines.append(f"\n--- 预览（前 500 字）---\n{merged[:500]}")
    return "\n".join(lines)


# ── 保函 docx 模板填写（对话上传模板 → 保留格式填写） ──────────────
_ctx_path_cache: dict[str, str] = {}  # 磁盘文件名 → 绝对路径（避免重复 os.walk）


def _find_context_template_path(file_contexts, hint):
    """从对话上传的 file_contexts 中找 .docx/.doc 模板文件。

    file_contexts 每项形如 {file_id, filename, ext, ...}（chat 层回传）。
    hint 是 LLM 填的 template_file，可能是原始文件名或带 "## " 前缀。
    返回 (绝对路径, 显示名) 或 None。
    """
    import os
    from backend.config import settings

    if not file_contexts:
        return None

    hint = (hint or "").strip()
    if hint.startswith("## "):
        hint = hint[3:].strip()
    hint_l = hint.lower()

    # 候选：仅 .docx/.doc 模板（提单/MSDS 等参考文件排除）
    candidates = []
    for fc in file_contexts:
        name = (fc.get("filename") or "").strip()
        if not name:
            continue
        ext = ((fc.get("ext") or "") or os.path.splitext(name)[1] or "").lower()
        if ext not in (".docx", ".doc"):
            continue
        candidates.append((name, fc, ext))

    if not candidates:
        return None

    chosen = None
    if hint_l:
        for name, fc, ext in candidates:
            if hint_l in name.lower():
                chosen = (name, fc, ext)
                break
    elif len(candidates) == 1:
        chosen = candidates[0]
    if chosen is None:
        return None

    name, fc, ext = chosen
    file_id = (fc.get("file_id") or "").strip()
    disk_name = f"{file_id}{ext}" if file_id else os.path.basename(name)

    cached = _ctx_path_cache.get(disk_name)
    if cached and os.path.exists(cached):
        return cached, name

    root = os.path.join(settings.UPLOAD_DIR, "context_files")
    if os.path.isdir(root):
        for base, _ds, fs in os.walk(root):
            if disk_name in fs:
                p = os.path.abspath(os.path.join(base, disk_name))
                _ctx_path_cache[disk_name] = p
                return p, name
    return None


def _build_extracted_telex(args: dict) -> dict:
    """工具参数 → _fill_telex_docx 需要的 extracted key。"""
    def _g(*keys):
        for k in keys:
            v = (args.get(k) or "").strip()
            if v:
                return v
        return ""
    return {
        "vessel": _g("vessel"),
        "voyage": _g("voyage"),
        "pol": _g("pol", "port_of_loading"),
        "pod": _g("pod", "port_of_discharge"),
        "bl_no": _g("bl_no", "bill_of_lading_no"),
        "date": _g("date"),
        "container_no": _g("container_no"),
        "shipper": _g("shipper"),
        "shipper_address": _g("shipper_address"),
        "consignee": _g("consignee"),
        "consignee_details": _g("consignee_details"),
        "notify_party": _g("notify_party", "notify"),
        "cargo_description": _g("cargo_description", "goods_name"),
    }


def _build_extracted_nonhazardous(args: dict) -> dict:
    """工具参数 → _fill_nonhazardous_docx 需要的 extracted key。"""
    def _g(*keys):
        for k in keys:
            v = (args.get(k) or "").strip()
            if v:
                return v
        return ""
    cn = _g("中文品名") or _g("goods_name")
    return {
        "vessel": _g("vessel"),
        "voyage": _g("voyage"),
        "vessel_voyage": _g("vessel_voyage"),
        "bl_no": _g("bl_no", "bill_of_lading_no"),
        "container_no": _g("container_no"),
        "pol": _g("pol", "port_of_loading"),
        "pod": _g("pod", "port_of_discharge"),
        "中文品名": cn,
        "英文品名": _g("英文品名"),
        "CAS_NO": _g("CAS_NO", "cas_no"),
        "外观与性状": _g("外观与性状"),
        "主要用途": _g("主要用途"),
        "shipper": _g("shipper"),
        "consignee": _g("consignee"),
    }


def _validate_filled(preview: str, extracted: dict) -> list[str]:
    """检查成品文本：残留占位符 + 用户提供的关键值是否真正填入。"""
    import re as _re
    warnings = []
    residuals = sorted(set(_re.findall(r"\[[^\]]+\]", preview or "")))
    if residuals:
        warnings.append(f"模板仍含未填充占位符：{'、'.join(residuals[:5])}")
    if preview:
        norm_p = _re.sub(r"\s+", "", preview)
        for key, val in extracted.items():
            val = (val or "").strip()
            if not val or len(val) < 2 or key == "date":
                continue
            if _re.sub(r"\s+", "", val) not in norm_p:
                warnings.append(f"「{key}」的值未出现在成品中，模板可能不含对应占位符")
    return warnings


async def _try_fill_telex_docx(args: dict, file_contexts, carrier: str):
    """有对话上传模板 → 按模板填写电放保函并生成下载链接；未命中模板返回 None。"""
    import asyncio
    import uuid as _uuid
    from backend.core.routers.rpa import _fill_telex_docx, _telex_download_store
    from backend.parser import extract_text

    tpl = _find_context_template_path(file_contexts, args.get("template_file"))
    if not tpl:
        return None
    template_path, display_name = tpl
    extracted = _build_extracted_telex(args)
    try:
        filled = await asyncio.to_thread(_fill_telex_docx, template_path, extracted, carrier)
        preview = await asyncio.to_thread(extract_text, filled) or ""
    except Exception as e:
        return f"❌ 按模板填写电放保函失败：{e}"

    download_id = str(_uuid.uuid4())
    _telex_download_store[download_id] = {"path": filled, "label": "电放保函"}

    md = f"✅ 已按模板「{display_name}」填写电放保函。\n\n[📥 下载填写好的保函](/api/rpa/letter/download/{download_id})"
    warns = _validate_filled(preview, extracted)
    if warns:
        md += "\n\n" + "\n".join(f"⚠️ {w}" for w in warns)
    md += f"\n\n--- 填写预览 ---\n{(preview or '（模板无可提取文本）')[:500]}"
    return md


async def _try_fill_nonhazardous_docx(args: dict, file_contexts, carrier: str):
    """有对话上传模板 → 按模板填写非危保函并生成下载链接；未命中模板返回 None。"""
    import asyncio
    import uuid as _uuid
    from backend.core.routers.rpa import _fill_nonhazardous_docx, _telex_download_store
    from backend.parser import extract_text

    tpl = _find_context_template_path(file_contexts, args.get("template_file"))
    if not tpl:
        return None
    template_path, display_name = tpl
    extracted = _build_extracted_nonhazardous(args)
    try:
        filled = await asyncio.to_thread(_fill_nonhazardous_docx, template_path, extracted, carrier)
        preview = await asyncio.to_thread(extract_text, filled) or ""
    except Exception as e:
        return f"❌ 按模板填写非危保函失败：{e}"

    download_id = str(_uuid.uuid4())
    _telex_download_store[download_id] = {"path": filled, "label": "非危保函"}

    md = f"✅ 已按模板「{display_name}」填写非危保函。\n\n[📥 下载填写好的保函](/api/rpa/letter/download/{download_id})"
    warns = _validate_filled(preview, extracted)
    if warns:
        md += "\n\n" + "\n".join(f"⚠️ {w}" for w in warns)
    md += f"\n\n--- 填写预览 ---\n{(preview or '（模板无可提取文本）')[:500]}"
    return md


async def execute_tool_call(
    tool_name: str,
    arguments: dict | str,
    file_contexts: list[dict] | None = None,
    user_id: int | None = None,
) -> str:
    """执行工具调用（带 Redis 缓存），返回人类可读的结果字符串。

    user_id: 当前用户 id，按用户配置执行的工具（如邮件）使用。
    """
    import json
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            return f"❌ 工具参数解析失败：{arguments}"

    from backend.rpa import run_browser_task
    from backend.addons.llm.redis_cache import get_rpa_cache, set_rpa_cache
    from backend.config import settings

    if tool_name == "baixin_merge_fill":
        # 佰信在浏览器本机操作，服务端不执行 —— 规范化参数后标记待确认，
        # 由 chat 层转成 SSE tool_confirm 事件，前端渲染确认卡后直连本地 agent
        import json as _json
        mode = (arguments.get("mode") or "").strip().lower()
        if mode not in ("sea", "air"):
            mode = "air" if str(arguments.get("order_no") or "").upper().startswith("SB-A") else "sea"
        order_no = (arguments.get("order_no") or "").strip().upper()
        merged = arguments.get("merged") or {}
        if not isinstance(merged, dict):
            try:
                merged = _json.loads(merged)
            except Exception:
                merged = {}
        if not merged:
            return "❌ 佰信填值：未识别到任何可填字段，请补充订舱字段内容"
        summary = (arguments.get("summary") or "").strip() or f"识别到 {len(merged)} 个字段"
        pending = {
            "mode": mode,
            "order_no": order_no,
            "container_no": (arguments.get("container_no") or "").strip().upper(),
            "merged": merged,
            "summary": summary,
        }
        return BAIXIN_PENDING_PREFIX + _json.dumps(pending, ensure_ascii=False)

    if tool_name == "baixin_fee_fill":
        # 佰信费用录入同样在浏览器本机操作，服务端不执行 —— 规范化参数后标记待确认
        import json as _json
        mode = (arguments.get("mode") or "").strip().lower()
        if mode not in ("sea", "air"):
            mode = "air" if str(arguments.get("order_no") or "").upper().startswith("SB-A") else "sea"
        order_no = (arguments.get("order_no") or "").strip().upper()
        merged = arguments.get("merged") or {}
        if not isinstance(merged, dict):
            try:
                merged = _json.loads(merged)
            except Exception:
                merged = {}
        if not merged:
            return "❌ 佰信费用录入：未识别到任何可填字段，请补充费用内容（往来单位/应收/应付/数量/单价）"
        summary = (arguments.get("summary") or "").strip() or f"识别到 {len(merged)} 个费用字段"
        pending = {
            "kind": "fee",
            "mode": mode,
            "order_no": order_no,
            "merged": merged,
            "summary": summary,
        }
        return BAIXIN_PENDING_PREFIX + _json.dumps(pending, ensure_ascii=False)

    if tool_name == "query_container":
        container_no = (arguments.get("container_no") or "").strip().upper()
        port_name = (arguments.get("port_name") or "").strip()
        if not container_no:
            return "❌ 错误：缺少柜号（container_no）"

        # Redis 缓存：同一柜号 5 分钟内不重复查
        cache_key = f"container:{container_no}"
        if settings.REDIS_ENABLED:
            cached = get_rpa_cache(cache_key)
            if cached:
                return f"📦 {container_no} 查询结果（缓存）:\n{cached}"

        params = {"container_no": container_no}
        if port_name:
            params["port_name"] = port_name
            cache_key += f":{port_name}"
        result = await run_browser_task("port_query", params)
        if result.get("success"):
            data = result.get("data", "查询完成，但无返回数据")
            # 写缓存
            if settings.REDIS_ENABLED:
                set_rpa_cache(cache_key, data, ttl=settings.REDIS_RPA_CACHE_TTL)
            return f"📦 {container_no} 查询结果:\n{data}"
        else:
            return f"❌ 查询失败：{result.get('error', '未知错误')}"

    elif tool_name == "query_port_status":
        port_name = (arguments.get("port_name") or "").strip()
        if not port_name:
            return "❌ 错误：请指定港口名称（port_name）"

        # Redis 缓存：同一港口公告 5 分钟缓存
        cache_key = f"port_status:{port_name}"
        if settings.REDIS_ENABLED:
            cached = get_rpa_cache(cache_key)
            if cached:
                return f"⏱️ {port_name} 港口状态（缓存）:\n{cached}"

        params = {"port_name": port_name}
        result = await run_browser_task("port_status", params)
        if result.get("success"):
            data = result.get("data", "查询完成，但无返回数据")
            if settings.REDIS_ENABLED:
                set_rpa_cache(cache_key, data, ttl=settings.REDIS_RPA_CACHE_TTL)
            return f"⏱️ {port_name} 港口状态:\n{data}"
        else:
            return f"❌ 查询失败：{result.get('error', '未知错误')}"

    if tool_name == "generate_dg_letter":
        from datetime import date
        from backend.core.routers.rpa import _generate_non_hazardous_letter
        carrier = (arguments.get("carrier") or "").strip()
        if not carrier:
            return "❌ 生成非危保函：缺少船公司/航司名称（carrier）"
        # 对话上传了 docx 模板 → 按模板填写（保留模板格式）；否则纯文本兜底
        docx_md = await _try_fill_nonhazardous_docx(arguments, file_contexts, carrier)
        if docx_md:
            return docx_md
        goods = (arguments.get("goods_name") or "").strip()
        dg = (arguments.get("danger_class") or "").strip()
        commodity = f"{goods}（危险品类别/UN编号: {dg}）" if (goods and dg) else (goods or dg)
        data = {
            "date": date.today().isoformat(),
            "pol": (arguments.get("port_of_loading") or "").strip(),
            "commodity": commodity,
            "container_no": (arguments.get("container_no") or "").strip(),
            "shipper": (arguments.get("shipper") or "").strip(),
            "consignee": (arguments.get("consignee") or "").strip(),
        }
        return f"📄 非危保函已生成：\n\n{_generate_non_hazardous_letter(carrier, data)}"

    if tool_name == "generate_telex_letter":
        from datetime import date
        from backend.core.routers.rpa import _generate_telex_letter
        carrier = (arguments.get("carrier") or "").strip()
        if not carrier:
            return "❌ 生成电放保函：缺少船公司名称（carrier）"
        # 对话上传了 docx 模板 → 按模板填写（保留模板格式）；否则纯文本兜底
        docx_md = await _try_fill_telex_docx(arguments, file_contexts, carrier)
        if docx_md:
            return docx_md
        data = {
            "date": date.today().isoformat(),
            "bl_no": (arguments.get("bill_of_lading_no") or "").strip(),
            "pol": (arguments.get("port_of_loading") or "").strip(),
            "pod": (arguments.get("port_of_discharge") or "").strip(),
            "container_no": (arguments.get("container_no") or "").strip(),
            "shipper": (arguments.get("shipper") or "").strip(),
            "consignee": (arguments.get("consignee") or "").strip(),
        }
        return f"📄 电放保函已生成：\n\n{_generate_telex_letter(carrier, data)}"

    if tool_name == "merge_invoice_packing":
        try:
            factory_count = int(arguments.get("factory_count") or 0)
        except (TypeError, ValueError):
            factory_count = 0
        return await _merge_invoice_packing(arguments.get("order_no") or "", factory_count)

    if tool_name == "fill_baixin_bill":
        # 佰信账单录入自动化未接入 —— 友好引导，不返回 PENDING
        return (
            "佰信账单录入（同行账单/代理账单）自动化暂未接入，未执行写入。\n"
            f"已收到待录入信息：账单类型={arguments.get('bill_type') or '—'}，"
            f"业务单号={arguments.get('order_no') or '—'}，"
            f"金额={arguments.get('amount') or '—'} {arguments.get('currency') or ''}\n"
            "当前可用的佰信能力：\n"
            "• 订舱录入（baixin_merge_fill）——空运/海运订舱字段对齐后在本机确认录入\n"
            "• 费用录入（baixin_fee_fill）——应收/应付费用登记对齐后在本机确认录入\n"
            "如需录入整体账单，请先用上述能力或联系管理员开通账单自动化。"
        )

    if tool_name == "send_email_to_user":
        # 用当前用户自己的 SMTP 配置发送邮件；未配置则返回提示（不自动回退全局）
        import html as _html
        from backend.database import SessionLocal
        from backend.utils.email import SmtpConfig, send_email_to_user

        if user_id is None:
            return "❌ 发送邮件失败：无法识别当前用户身份，请重新登录后再试"

        subject = (arguments.get("subject") or "").strip()
        content = (arguments.get("content") or "").strip()
        if not subject or not content:
            return "❌ 发送邮件失败：缺少邮件主题或正文"

        db = SessionLocal()
        try:
            # 用户给了具体收件地址用它；说"我的邮箱/发给我"未给地址 → 发送到用户自己的邮箱
            to_email = (arguments.get("to_email") or "").strip()
            if not to_email:
                to_email = SmtpConfig.from_user(db, user_id).user or ""
            if not to_email:
                return "❌ 发送邮件失败：未指定收件人，且您的账号未配置邮箱，请先到【邮箱设置】配置后再试"

            # 正文 → 简单 HTML（转义 + 换行）
            html_body = (
                "<div style='font-family:Microsoft YaHei,Arial,sans-serif;"
                "font-size:14px;line-height:1.7'>"
                + _html.escape(content).replace("\n", "<br/>")
                + "</div>"
            )

            success, err = send_email_to_user(
                db, user_id, to_email, subject, html_body, text_body=content
            )
        finally:
            db.close()

        if success:
            return f"📧 邮件已发送至 {to_email}，主题：{subject}"
        return f"📧 邮件发送失败：{err}"

    else:
        return f"❌ 未知工具: {tool_name}"
