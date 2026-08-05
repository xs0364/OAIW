# -*- coding: utf-8 -*-
"""集成验证：unified_mapper 输出 → merge_service.merge_fields（佰信录入链路）。

证明映射器输出的规范字段 dict 能被 merge.py / _baixin_merge_fill.py 直接消费：
1. key 对齐 FIELD_RULES（16规范字段）
2. 与 file_fields 合并优先级正确（query 字段映射器提供，件毛体以 file 为准）
3. 佰信填写脚本需要的 source key 全部有值来源"""
import sys
sys.path.insert(0, r"D:\OAIW")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from backend.rpa import unified_mapper as um
from backend.rpa import merge_service as ms

YT = """盐田港 - 集装箱 ECMU6262406 查询结果
--------------------------------------------------
订舱号: 272977891
提单号：WHL061G554006
集装箱号：ECMU6262406
箱主：MAEU
尺寸'类型：\t40'HQ(45/G1)\t街车入闸时间：\t2026-07-06 17:22\t街车出闸时间：\t2026-07-07 09:00
船舶名称：MAERSK SAIGON
航次：627E
封条号：ML7645744
总重(kgs)：30450
卸货港：PUSAN/BUSAN KOREA
当前场地：YICT
集装箱状态：在场
"""

print("== 1. 映射器输出（query_fields）==")
qf = um.map_port_to_fields("盐田港", YT, container_no="ECMU6262406", booking_no="SB-S26070007")
nonempty = {k: v for k, v in qf.items() if v or k in ("gross", "pieces", "volume")}
print(nonempty)

print("\n== 2. merge_fields 合并（件毛体以 file 为准）==")
ff = {"pieces": 120, "volume": 66.5, "cargo_name": "FROZEN FOOD"}
merged, prov = ms.merge_fields(qf, ff)
print("merged:", merged)
print("provenance:", prov)

print("\n== 3. 佰信填写脚本所需 source key 覆盖 ==")
# _baixin_merge_fill.py FORM_FIELDS + GRID 的 source key
need = ["booking_no", "bl_no", "terminal", "etd", "eta", "cargo_name",
        "pieces", "gross", "volume", "size_type", "container_no", "seal"]
missing = [k for k in need if not ms._has_value(merged.get(k))]
print("缺失:", missing if missing else "无 ✅")

assert "gross" in merged and merged["gross"] == 30450, "盐田总重应来自 query"
assert merged["cargo_name"] == "FROZEN FOOD", "品名以 file 为准"
assert prov["gross"] == "query", "gross provenance 应为 query"
assert merged["bl_no"] == "WHL061G554006", "盐田提单号应提取"
assert merged["etd"] == "2026-07-07", "盐田街车出闸时间应提取"
assert not missing, f"佰信字段缺失: {missing}"
print("\n✅ 集成链路打通：映射器输出 → merge_fields → 佰信填写")
