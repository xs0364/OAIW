# -*- coding: utf-8 -*-
"""方案B集成验证：sync_from_port 接入 unified_mapper 后，四港口文本 → FCLOrder 落库正确。

验证点：
1. 字段提取统一走 unified_mapper（盐田"总重(kgs)"修复在整链路生效）
2. 建单/查重/状态推进逻辑保留（重复同步 → updated，蛇口/青岛 VESSEL/已装船 → sailing）
3. 无柜号不同步
"""
import sys
sys.path.insert(0, r"D:\OAIW")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.core.models.fcl_order import FCLOrder
from backend.rpa.rpa_sync import sync_from_port

engine = create_engine("sqlite://")
FCLOrder.__table__.create(engine)
db = sessionmaker(bind=engine)()

passed = 0
def check(name, cond):
    global passed
    mark = "✅" if cond else "❌"
    print(f"  {mark} {name}")
    assert cond, f"失败: {name}"
    passed += 1

# ===== 各港独立柜号样例（照驱动格式化代码构造） =====
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

SK = """蛇口港(SCCT) - 集装箱 EGHU9622408 查询结果
────────────────────────────────────

【基本信息】
柜号:     EGHU9622408
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
柜号: CMAU1234567
查询时间: 2026-08-04 10:00:00

【出口-码头信息】(1 条)
  XH=SLEU2516841 | YWCM=OOCL ITALY | CKHC=155S | CC=40 | XX=HQ | MZ=30450 | QFH=ML7645744 | TDH=QGD3131565 | MTMC=QQCTU码头 | MDGM=BUSAN | SJRGSJ=2026-07-06 17:22:00 | XSGSM=CMA | DQZTMC=已装船 | ZHGYM=QINGDAO

──────────────────────────────────
数据来源: 青岛港云港通 (qingdao-port.net)
"""

NB = """MSKU7654321
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

[BL NBLG7654321]
  Pkgs: 120
  Wt: 30450 KG
  Vol: 66.5 CBM

--------------------------------------------------
Source: Ningbo Port EDI (api.npedi.com:8888)
"""

# ===== 盐田港（tab行 + 总重修复 + 提单号） =====
print("== 盐田港 ==")
r = sync_from_port(db, YT, "ECMU6262406", "SB-S26070007", port_name="盐田港")
check("创建订单", r["synced"] and r["action"].startswith("created"))
o = db.query(FCLOrder).filter(FCLOrder.container_no == "ECMU6262406").first()
check("order_no=业务单号", o.order_no == "SB-S26070007")
check("container_type tab行", o.container_type == "40'HQ(45/G1)")
check("gross_weight 总重(kgs)修复", o.gross_weight == 30450)
check("bl_no 提单号", o.bl_no == "WHL061G554006")
check("vessel 组合显示", o.vessel == "MAERSK SAIGON / 627E")
check("vessel_name", o.vessel_name == "MAERSK SAIGON")
check("voyage", o.voyage == "627E")
check("terminal", o.terminal == "YICT")
check("eta 街车入闸", o.eta == "2026-07-06")
check("etd 街车出闸", o.etd == "2026-07-07")
check("dest", o.dest == "PUSAN/BUSAN KOREA")
check("seal_no", o.seal_no == "ML7645744")
check("status 在场→received", o.status == "received")
r2 = sync_from_port(db, YT, "ECMU6262406", "SB-S26070007", port_name="盐田港")
check("重复同步→updated(查重保留)", r2["action"].startswith("updated"))
check("同一条单", r2["order_no"] == "SB-S26070007")

# ===== 蛇口港（ISO截断 + VESSEL→sailing） =====
print("== 蛇口港 ==")
r = sync_from_port(db, SK, "EGHU9622408", "SB-S26070008", port_name="蛇口港")
check("创建订单", r["synced"] and r["action"].startswith("created"))
o = db.query(FCLOrder).filter(FCLOrder.container_no == "EGHU9622408").first()
check("container_type ISO截断", o.container_type == "40'HQ")
check("gross_weight", o.gross_weight == 30450)
check("bl_no 订舱单号", o.bl_no == "ALK0574445")
check("vessel 拆分", o.vessel == "OOCL ITALY / 155S")
check("vessel_name", o.vessel_name == "OOCL ITALY")
check("voyage", o.voyage == "155S")
check("terminal VESSEL排除", o.terminal == "")
check("dest", o.dest == "BUSAN")
check("origin 装货港", o.origin == "YANTIAN")
check("eta", o.eta == "2026-07-06")
check("etd", o.etd == "2026-07-07")
check("status VESSEL→sailing", o.status == "sailing")

# ===== 青岛港（管道 + CC/XX组合 + 已装船→sailing） =====
print("== 青岛港 ==")
r = sync_from_port(db, QD, "CMAU1234567", "SB-S26070009", port_name="青岛港")
check("创建订单", r["synced"] and r["action"].startswith("created"))
o = db.query(FCLOrder).filter(FCLOrder.container_no == "CMAU1234567").first()
check("container_type CC+XX", o.container_type == "40HQ")
check("gross_weight MZ", o.gross_weight == 30450)
check("bl_no TDH", o.bl_no == "QGD3131565")
check("vessel YWCM", o.vessel == "OOCL ITALY / 155S")
check("terminal MTMC", o.terminal == "QQCTU码头")
check("origin ZHGYM", o.origin == "QINGDAO")
check("dest MDGM", o.dest == "BUSAN")
check("eta SJRGSJ", o.eta == "2026-07-06")
check("status 已装船→sailing", o.status == "sailing")

# ===== 宁波港（英文标签 + [BL]段 + Pkgs/Vol） =====
print("== 宁波港 ==")
r = sync_from_port(db, NB, "MSKU7654321", "NBLG7654321", port_name="宁波港")
check("创建订单", r["synced"] and r["action"].startswith("created"))
o = db.query(FCLOrder).filter(FCLOrder.container_no == "MSKU7654321").first()
check("container_type", o.container_type == "40'HQ")
check("gross_weight", o.gross_weight == 30450)
check("bl_no [BL]段", o.bl_no == "NBLG7654321")
check("vessel", o.vessel == "OOCL ITALY / 155S")
check("pieces Pkgs", o.pieces == 120)
check("volume Vol", o.volume == 66.5)
check("dest Port", o.dest == "BUSAN")
check("eta", o.eta == "2026-07-06")
check("etd", o.etd == "2026-07-08")
check("status Full→received", o.status == "received")

# ===== 边界：无柜号不同步 =====
print("== 边界 ==")
r = sync_from_port(db, NB, "", "WHL061G554006", port_name="宁波港")
check("无柜号不同步", not r["synced"])

print(f"\n全部通过 🎉 ({passed} 项断言)")
