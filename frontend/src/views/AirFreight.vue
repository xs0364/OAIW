<template>
  <div>
    <h2>空运操作</h2>
    <p style="color: #909399; margin-bottom: 20px">
      空运出口全流程：订舱 → 面单 → 放SO → 对单 → 补料 → 报关 → 保险 → 提单 → 跟踪 → 应付录入 → 到港 → 提货 → 结单
    </p>

    <!-- 工具条 -->
    <el-row :gutter="16" style="margin-bottom: 16px">
      <el-col :span="6">
        <el-input v-model="searchText" placeholder="搜索业务单号/航线..." clearable size="default" />
      </el-col>
      <el-col :span="4">
        <el-select v-model="statusFilter" placeholder="状态筛选" clearable size="default" style="width: 100%">
          <el-option v-for="s in statusOptions" :key="s.value" :label="s.label" :value="s.value" />
        </el-select>
      </el-col>
      <el-col :span="14" style="text-align: right">
        <el-button type="primary" @click="showNewOrder = true">+ 新建业务</el-button>
      </el-col>
    </el-row>

    <!-- 订单列表 -->
    <el-card shadow="never">
      <el-table :data="filteredOrders" style="width: 100%" v-if="filteredOrders.length > 0" stripe>
        <el-table-column prop="orderNo" label="业务单号" width="140" />
        <el-table-column prop="route" label="航线" width="160" />
        <el-table-column label="件/毛/体" width="180">
          <template #default="{ row }">
            {{ row.pieces }}件 / {{ row.grossWeight }}KGS / {{ row.volume }}CBM
          </template>
        </el-table-column>
        <el-table-column prop="carrier" label="航司/航班" width="140" />
        <el-table-column prop="etd" label="ETD" width="100" />
        <el-table-column label="当前状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusMap[row.status]?.type || 'info'" size="small">
              {{ statusMap[row.status]?.label || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="流程进度" min-width="260">
          <template #default="{ row }">
            <div style="display: flex; align-items: center; gap: 8px">
              <el-progress :percentage="row.progress" :status="row.progress >= 100 ? 'success' : undefined" style="flex: 1" />
              <span style="font-size: 12px; color: #909399; white-space: nowrap">{{ row.progress }}%</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="viewOrder(row)">详情</el-button>
            <el-dropdown trigger="click" @command="(cmd) => quickAction(cmd, row)">
              <el-button text type="primary" size="small">推进 <el-icon><ArrowDown /></el-icon></el-button>
              <template #dropdown>
                <el-dropdown-item v-for="s in statusOptions" :key="s.value" :command="s.value" :disabled="s.disabled?.(row)">
                  {{ s.label }}
                </el-dropdown-item>
              </template>
            </el-dropdown>
          </template>
        </el-table-column>
      </el-table>

      <div v-else style="text-align: center; padding: 60px 0; color: #c0c4cc">
        <el-icon :size="48"><TakeawayBox /></el-icon>
        <p style="margin-top: 10px">暂无进行中的空运订单</p>
        <el-button type="primary" style="margin-top: 10px" @click="showNewOrder = true">创建第一票业务</el-button>
      </div>
    </el-card>

    <!-- 新建订单 -->
    <el-dialog v-model="showNewOrder" title="新建空运订单" width="600px">
      <el-form label-width="100px" :model="newOrder">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="起运港"><el-input v-model="newOrder.origin" placeholder="如 SZX" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="目的港"><el-input v-model="newOrder.dest" placeholder="如 SVO" /></el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="件数"><el-input-number v-model="newOrder.pieces" :min="1" style="width: 100%" /></el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="毛重(KGS)"><el-input-number v-model="newOrder.grossWeight" :min="0.1" style="width: 100%" /></el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="体积(CBM)"><el-input-number v-model="newOrder.volume" :min="0.1" style="width: 100%" /></el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="航司/航班"><el-input v-model="newOrder.carrier" placeholder="如 CZ CZ8371" /></el-form-item>
        <el-form-item label="ETD"><el-date-picker v-model="newOrder.etd" type="date" placeholder="预计出运日" style="width: 100%" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="newOrder.remark" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showNewOrder = false">取消</el-button>
        <el-button type="primary" @click="createOrder">创建</el-button>
      </template>
    </el-dialog>

    <!-- 详情抽屉 -->
    <el-drawer v-model="showDetail" :title="'业务详情 — ' + (detailOrder?.orderNo || '')" size="500px">
      <template v-if="detailOrder">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="航线">{{ detailOrder.route }}</el-descriptions-item>
          <el-descriptions-item label="件/毛/体">{{ detailOrder.pieces }}件 / {{ detailOrder.grossWeight }}KGS / {{ detailOrder.volume }}CBM</el-descriptions-item>
          <el-descriptions-item label="航司/航班">{{ detailOrder.carrier }}</el-descriptions-item>
          <el-descriptions-item label="ETD">{{ detailOrder.etd }}</el-descriptions-item>
        </el-descriptions>

        <div style="margin-top: 20px">
          <b>流程状态</b>
          <div style="display: flex; flex-wrap: wrap; gap: 4px; margin-top: 16px; align-items: center">
            <template v-for="(s, i) in flowSteps" :key="s.key">
              <el-tag
                :type="getStepTagType(detailOrder, s.key)"
                size="small"
                effect="plain"
                :style="{ fontWeight: detailOrder.status === s.key ? 'bold' : 'normal' }"
              >
                {{ s.label }}
              </el-tag>
              <span v-if="i < flowSteps.length - 1" style="color: #dcdfe6; font-size: 12px">›</span>
            </template>
          </div>
        </div>

        <div style="margin-top: 20px">
          <b>操作记录</b>
          <div v-if="(detailOrder.logs?.length || 0) === 0" style="color: #c0c4cc; margin-top: 8px; font-size: 13px">暂无操作记录</div>
          <div v-for="(log, i) in detailOrder.logs" :key="i" style="padding: 6px 0; border-bottom: 1px solid #f0f0f0; font-size: 13px">
            <el-tag size="small">{{ log.action }}</el-tag>
            <span style="margin-left: 8px">{{ log.detail }}</span>
            <span style="float: right; color: #c0c4cc; font-size: 12px">{{ log.time }}</span>
          </div>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { TakeawayBox, ArrowDown } from '@element-plus/icons-vue'

const searchText = ref('')
const statusFilter = ref('')
const showNewOrder = ref(false)
const showDetail = ref(false)
const detailOrder = ref(null)

// ===== 13步流程定义 =====
const flowSteps = [
  { key: 'booking', label: '订舱' },
  { key: 'waybill', label: '面单' },
  { key: 'so_release', label: '放SO' },
  { key: 'docs_confirm', label: '对单' },
  { key: 'filing', label: '补料' },
  { key: 'customs', label: '报关' },
  { key: 'insurance', label: '保险' },
  { key: 'bl', label: '提单' },
  { key: 'tracking', label: '跟踪' },
  { key: 'ap_entry', label: '应付录入' },
  { key: 'arrived', label: '到港' },
  { key: 'delivery', label: '提货' },
  { key: 'closed', label: '结单' },
]

const statusMap = {
  booking: { label: '已订舱', type: 'primary' },
  waybill: { label: '面单已出', type: '' },
  so_release: { label: '已放SO', type: 'primary' },
  docs_confirm: { label: '对单中', type: 'warning' },
  filing: { label: '已补料', type: 'warning' },
  customs: { label: '报关中', type: 'warning' },
  insurance: { label: '已投保', type: '' },
  bl: { label: '提单确认', type: 'primary' },
  tracking: { label: '跟踪中', type: '' },
  ap_entry: { label: '应付录入', type: 'warning' },
  arrived: { label: '已到港', type: 'success' },
  delivery: { label: '提货中', type: 'warning' },
  closed: { label: '已结单', type: 'info' },
}

const statusOptions = Object.entries(statusMap).map(([value, s]) => ({
  value,
  label: s.label,
}))

function beijingTime(date) {
  const d = date ? new Date(date) : new Date()
  const pad = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

// ===== 模拟数据 =====
const orders = ref([
  {
    id: 1, orderNo: 'AE20260701', origin: 'SZX', dest: 'SVO',
    route: 'SZX → SVO', pieces: 55, grossWeight: 565, volume: 3.5,
    carrier: 'CZ CZ8371', etd: '2026-07-10',
    status: 'filing', progress: 33,
    logs: [
      { action: '订舱', detail: '已向航司订舱，舱位确认', time: '2026-07-01 10:00' },
      { action: '面单', detail: '面单已打印，编号 MAWB-001', time: '2026-07-02 09:30' },
      { action: '放SO', detail: 'SO已释放，通知客户', time: '2026-07-03 14:00' },
      { action: '对单', detail: '提单草稿已核对，确认件毛体', time: '2026-07-04 11:20' },
      { action: '补料', detail: '已向航司发送补料，VGM已提交', time: '2026-07-05 16:00' },
    ],
  },
  {
    id: 2, orderNo: 'AE20260702', origin: 'CAN', dest: 'LAX',
    route: 'CAN → LAX', pieces: 220, grossWeight: 2800, volume: 12.0,
    carrier: 'CA CA983', etd: '2026-07-12',
    status: 'docs_confirm', progress: 25,
    logs: [
      { action: '订舱', detail: 'CA 订舱确认', time: '2026-07-02 09:00' },
      { action: '面单', detail: '面单已出', time: '2026-07-03 10:30' },
      { action: '放SO', detail: 'SO已释放', time: '2026-07-04 14:00' },
    ],
  },
  {
    id: 3, orderNo: 'AE20260703', origin: 'SZX', dest: 'NRT',
    route: 'SZX → NRT', pieces: 30, grossWeight: 180, volume: 1.2,
    carrier: 'NH NH9640', etd: '2026-07-15',
    status: 'closed', progress: 100,
    logs: [
      { action: '订舱', detail: 'NH 确认', time: '2026-06-28 09:00' },
      { action: '面单', detail: '面单已出', time: '2026-06-29 10:30' },
      { action: '放SO', detail: 'SO已释放', time: '2026-06-30 14:00' },
      { action: '对单', detail: '对单完成', time: '2026-07-01 11:00' },
      { action: '补料', detail: '已补料', time: '2026-07-02 16:30' },
      { action: '报关', detail: '报关放行', time: '2026-07-03 10:00' },
      { action: '保险', detail: '已投保', time: '2026-07-03 15:00' },
      { action: '提单', detail: '正本提单已签发', time: '2026-07-04 17:00' },
      { action: '跟踪', detail: '货物跟踪中，预计抵达', time: '2026-07-10 08:00' },
      { action: '应付录入', detail: '应付费用已录入系统', time: '2026-07-11 14:00' },
      { action: '到港', detail: '货物已到港', time: '2026-07-12 06:30' },
      { action: '提货', detail: '已提货离港', time: '2026-07-13 09:00' },
      { action: '结单', detail: '订单关闭', time: '2026-07-14 17:00' },
    ],
  },
])

const filteredOrders = computed(() => {
  let list = orders.value
  if (searchText.value) {
    const q = searchText.value.toLowerCase()
    list = list.filter(o => o.orderNo.toLowerCase().includes(q) || o.route.toLowerCase().includes(q))
  }
  if (statusFilter.value) {
    list = list.filter(o => o.status === statusFilter.value)
  }
  return list
})

const newOrder = ref({
  origin: '', dest: '', pieces: 1, grossWeight: 0.1, volume: 0.1,
  carrier: '', etd: null, remark: '',
})

function createOrder() {
  if (!newOrder.value.origin || !newOrder.value.dest) {
    ElMessage.warning('请填写起运港和目的港')
    return
  }
  const id = orders.value.length + 1
  const now = new Date()
  const dateStr = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}`
  orders.value.unshift({
    id,
    orderNo: `AE${dateStr}${String(id).padStart(2, '0')}`,
    origin: newOrder.value.origin,
    dest: newOrder.value.dest,
    route: `${newOrder.value.origin} → ${newOrder.value.dest}`,
    pieces: newOrder.value.pieces,
    grossWeight: newOrder.value.grossWeight,
    volume: newOrder.value.volume,
    carrier: newOrder.value.carrier || '待定',
    etd: newOrder.value.etd ? newOrder.value.etd.toISOString().slice(0, 10) : '待定',
    status: 'booking',
    progress: 8,
    logs: [{ action: '新建', detail: '业务已创建', time: beijingTime() }],
  })
  showNewOrder.value = false
  newOrder.value = { origin: '', dest: '', pieces: 1, grossWeight: 0.1, volume: 0.1, carrier: '', etd: null, remark: '' }
  ElMessage.success('空运业务已创建')
}

function viewOrder(row) {
  detailOrder.value = row
  showDetail.value = true
}

function quickAction(command, row) {
  const idx = flowSteps.findIndex(s => s.key === command)
  const cur = flowSteps.findIndex(s => s.key === row.status)
  if (idx <= cur) {
    ElMessage.info('状态不能回退')
    return
  }
  row.status = command
  row.progress = Math.round((idx / (flowSteps.length - 1)) * 100)
  if (!row.logs) row.logs = []
  row.logs.push({
    action: statusMap[command]?.label || command,
    detail: `状态更新为「${statusMap[command]?.label || command}」`,
    time: beijingTime(),
  })
  ElMessage.success(`已推进到「${statusMap[command]?.label || command}」`)
}

function getStepTagType(order, key) {
  const idx = flowSteps.findIndex(s => s.key === key)
  const cur = flowSteps.findIndex(s => s.key === order.status)
  if (idx < cur) return 'success'
  if (idx === cur) return 'primary'
  return 'info'
}
</script>
