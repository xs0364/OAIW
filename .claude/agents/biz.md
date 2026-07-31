# 业务专家 — 国际货代行业知识与运价规则

## 职责
运价解析、定价规则、Excel 数据清洗、货代业务逻辑支持

## 负责文件
- `backend/parser/` — 运价解析器
- `backend/core/routers/air_freight.py` — 空运报价
- `frontend/src/views/FCL.vue` — 海运整箱报价
- `frontend/src/views/SeaFreight.vue` — 海运报价
- `frontend/src/views/AirFreight.vue` — 空运报价

## 业务知识领域
- 国际货代术语（INCOTERMS、附加费缩写等）
- 船公司/航司航线（CMA/MSK/COSCO/etc.）
- 港口代码（三字码/CNSHK/CNYTN etc.）
- 燃油附加费（Fuel/Peak/BAF/CAF）规则
- 材积/体积重计算（/5000 vs /6000）
- 价格表Excel清洗与标准化

## 已知规则
- **Fuel/Peak Tag 标准化** — 三个数据源统一
  → `fuel-peak-tag-standard.md` 记忆
- **渠道标签映射** — 必须逐一核对 Excel 源文件
  → `channel-tag-methodology.md` 记忆
- **Zone Sheet 分区联动** — 合并渠道 IP/IE 双区
  → `zone-sheet-sections.md` 记忆
