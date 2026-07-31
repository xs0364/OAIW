"""
OAIW Tool Schemas — 操作部 AI Agent 工具定义

OpenAI 兼容 Function Calling 格式，供支持 tools 参数的 Provider 使用。
"""
from __future__ import annotations

# 操作部 AI Agent 可用工具
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_port_status",
            "description": "查询码头开港/进港/报关放行/装船状态。用户问「码头状态」「查码头」「开港了没」时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "port_name": {
                        "type": "string",
                        "description": "码头名称，如 盐田港、蛇口港、上海港、宁波港、青岛港"
                    },
                },
                "required": ["port_name"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_dg_letter",
            "description": "生成非危保函（危险品/化工品/电池货物）。用户说「非危保函」「电池保函」「化工品保函」时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "carrier": {"type": "string", "description": "船公司或航司名称"},
                    "port_of_loading": {"type": "string", "description": "起运港"},
                    "goods_name": {"type": "string", "description": "货物名称（中英文）"},
                    "danger_class": {"type": "string", "description": "危险品类别 UN编号，如 UN3481"},
                    "container_no": {"type": "string", "description": "柜号（可选）"},
                },
                "required": ["carrier", "port_of_loading", "goods_name", "danger_class"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_telex_letter",
            "description": "生成电放保函。用户说「电放保函」「电放」「telex release」时调用。",
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
            "description": "录入账单到佰信系统。用户说「录账单」「录入佰信」「同行账单录入」时调用。",
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
]
