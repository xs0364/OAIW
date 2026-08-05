# -*- coding: utf-8 -*-
"""统一字段映射器 unified_mapper.py 测试。

用4港口驱动格式化代码的产物样例构造文本，验证每港都能映射出规范字段。
重点：盐田"总重(kgs)"修复、蛇口 ISO 截断/vessel拆分/VESSEL终端排除、
青岛 CC+XX 组合、宁波 [BL] 提单提取。不改任何真实数据。"""
import sys, importlib.util
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

spec = importlib.util.spec_from_file_location("unified_mapper", r"D:\OAIW\backend\rpa\unified_mapper.py")
um = importlib.util.module_from_spec(spec)
spec.loader.exec_module(um)

passed = 0

def check(name, cond):
    global passed
    mark = "✅" if cond else "❌"
    print(f"  {mark} {name}")
    assert cond, f"失败: {name}"
    passed += 1

# ===== 样例文本（照各驱动格式化代码构造） =====
YT = """盐田港 - 集装箱 ECMU6262406 查询结果
--------------------------------------------------
订舱号: 272977891
集装箱号：ECMU6262406
箱主：MAEU
尺寸'类型：\t40'HQ(45/G1)\t街车入闸时间：\t2026-07-06 17:22
船舶名称：MAERSK SAIGON
航次：627E
封条号：ML7645744
总重(kgs)：30450
卸货港：PUSAN/BUSAN KOREA
当前场地：YICT
集装箱状态：在场
"""

SK = """蛇口港(SCCT) - 集装箱 ECMU6262406 查询结果
────────────────────────────────────

【基本信息】
柜号:     ECMU6262406
箱属:     MAEU
尺寸/类型: 40'HQ  ISO: 22G1
柜状态:   重柜
放行状态: 已放行
当前位置: VESSEL 0600990
毛重(KG): 30450
封条号:   ML7645744
订舱单号: ALK0574445
IMO:      9407821

【运输信息】
装货港:   YANTIAN
卸货港:   BUSAN
目的港:   BUSAN
进场时间: 2026-07-06 17:22
出场时间: 2026-07-07 09:00

【船舶信息】
进港船名航次: OOCL ITALY/154N
离港船名航次: OOCL ITALY/155S
出口商业航次: 155S
"""

QD = """📦 青岛港 — 单箱查询结果
──────────────────────────────────
柜号: ECMU6262406
查询时间: 2026-08-04 10:00:00

【出口-码头信息】(1 条)
  XH=SLEU2516841 | YWCM=OOCL ITALY | CKHC=155S | CC=40 | XX=HQ | MZ=30450 | QFH=ML7645744 | TDH=ALK0574445 | MTMC=QQCTU码头 | MDGM=BUSAN | SJRGSJ=2026-07-06 17:22:00 | XSGSM=CMA | DQZTMC=已装船 | ZHGYM=QINGDAO

──────────────────────────────────
数据来源: 青岛港云港通 (qingdao-port.net)
"""

NB = """ECMU6262406
--------------------------------------------------
Direction:  Export
Terminal:   Beilunshan
Status:     Full
Size/Type:  40'HQ
Owner:      MAEU
Seal No:    ML7645744
Gross(KG):  30450
Vessel:     OOCL ITALY
Voyage:     155S
Port:       BUSAN

[Time]
ETA:        2026-07-06 17:22:00
ETD:        2026-07-08 12:00:00
ATA:        2026-07-10 09:00:00
ATD:        2026-07-11 18:00:00

[BL WHL061G554006]
  Pkgs: 120
  Wt: 30450 KG
  Vol: 66.5 CBM

--------------------------------------------------
Source: Ningbo Port EDI (api.npedi.com:8888)
"""

# ===== 场景1: 盐田港（tab 行 + 总重修复） =====
print("场景1: 盐田港")
r = um.map_port_to_fields("盐田港", YT)
check("container_no", r["container_no"] == "ECMU6262406")
check("size_type tab行", r["size_type"] == "40'HQ(45/G1)")
check("gross 总重(kgs)修复", r["gross"] == 30450)
check("gross 是数字", isinstance(r["gross"], int))
check("vessel", r["vessel"] == "MAERSK SAIGON")
check("voyage", r["voyage"] == "627E")
check("seal", r["seal"] == "ML7645744")
check("booking_no", r["booking_no"] == "272977891")
check("dest", r["dest"] == "PUSAN/BUSAN KOREA")
check("terminal", r["terminal"] == "YICT")
check("owner", r["owner"] == "MAEU")
check("status", r["status"] == "在场")

# ===== 场景2: 蛇口港（ISO截断 / vessel拆分 / VESSEL终端排除） =====
print("场景2: 蛇口港")
r = um.map_port_to_fields("蛇口港", SK)
check("container_no", r["container_no"] == "ECMU6262406")
check("size_type ISO截断", r["size_type"] == "40'HQ")
check("gross", r["gross"] == 30450)
check("booking_no", r["booking_no"] == "ALK0574445")
check("vessel 拆分", r["vessel"] == "OOCL ITALY")
check("voyage 独立航次", r["voyage"] == "155S")
check("terminal VESSEL排除", r["terminal"] == "")
check("pol", r["pol"] == "YANTIAN")
check("dest", r["dest"] == "BUSAN")
check("eta 日期", r["eta"] == "2026-07-06")
check("etd 日期", r["etd"] == "2026-07-07")
check("owner", r["owner"] == "MAEU")
check("status", r["status"] == "重柜")

# ===== 场景3: 青岛港（管道 + CC/XX 组合） =====
print("场景3: 青岛港")
r = um.map_port_to_fields("青岛港", QD, container_no="ECMU6262406")
check("container_no 参数优先", r["container_no"] == "ECMU6262406")
check("size_type 组合", r["size_type"] == "40HQ")
check("gross MZ", r["gross"] == 30450)
check("seal QFH", r["seal"] == "ML7645744")
check("bl_no TDH", r["bl_no"] == "ALK0574445")
check("vessel YWCM", r["vessel"] == "OOCL ITALY")
check("voyage CKHC", r["voyage"] == "155S")
check("terminal MTMC", r["terminal"] == "QQCTU码头")
check("pol ZHGYM", r["pol"] == "QINGDAO")
check("dest MDGM", r["dest"] == "BUSAN")
check("eta SJRGSJ", r["eta"] == "2026-07-06")
check("owner XSGSM", r["owner"] == "CMA")
check("status DQZTMC", r["status"] == "已装船")

# ===== 场景4: 宁波港（英文标签 + [BL] 段 + Pkgs/Vol） =====
print("场景4: 宁波港")
r = um.map_port_to_fields("宁波港", NB, container_no="ECMU6262406", booking_no="WHL061G554006")
check("container_no 参数兜底", r["container_no"] == "ECMU6262406")
check("size_type", r["size_type"] == "40'HQ")
check("seal", r["seal"] == "ML7645744")
check("gross", r["gross"] == 30450)
check("vessel", r["vessel"] == "OOCL ITALY")
check("voyage", r["voyage"] == "155S")
check("dest Port", r["dest"] == "BUSAN")
check("owner", r["owner"] == "MAEU")
check("bl_no [BL]段", r["bl_no"] == "WHL061G554006")
check("pieces Pkgs", r["pieces"] == 120)
check("volume Vol", r["volume"] == 66.5)
check("eta", r["eta"] == "2026-07-06")
check("etd", r["etd"] == "2026-07-08")
check("status", r["status"] == "Full")

# ===== 场景5: 未知港口 / 空文本 → 干净空字段 =====
print("场景5: 未知港口/空文本")
r = um.map_port_to_fields("未知港", "随便 文本")
check("未知港不崩", r["container_no"] == "" and r["gross"] == 0)
check("未知港全空", all(not v for k, v in r.items() if k not in ("pieces", "volume", "gross")))
r2 = um.map_port_to_fields("蛇口港", "毛重(KG): --\n封条号: N/A")
check("-- 置空", r2["gross"] == 0 and r2["seal"] == "")

print(f"\n全部通过 🎉 ({passed} 项断言)")
