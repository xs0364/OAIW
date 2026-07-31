<template>
  <div>
    <h2>海运散货 (LCL)</h2>
    <p style="color: #909399; margin-bottom: 20px">
      拼箱出口全流程：放舱 → 安排提货 → 进仓 → 核对进仓数据 → 核对提单 → 补料 → 开船 → 发提单账单 → 收款 → 放单 → 到港 → 提货 → 结单
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
            {{ row.pieces }}件 / {{ row.gross_weight }}KGS / {{ row.volume }}CBM
          </template>
        </el-table-column>
        <el-table-column prop="carrier" label="船司/船名" width="140" />
        <el-table-column prop="etd" label="ETD" width="100" />
        <el-table-column label="截仓时间" width="110">
          <template #default="{ row }">
            <span v-if="row.cutoff_time" style="font-size: 13px; color: #e6a23c">
              <el-icon style="vertical-align: middle"><Clock /></el-icon> {{ row.cutoff_time }}
            </span>
            <span v-else style="color: #c0c4cc; font-size: 12px">未设置</span>
          </template>
        </el-table-column>
        <el-table-column label="当前状态" width="120">
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
        <el-table-column label="操作" width="120" fixed="right">
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
        <el-icon :size="48"><Ship /></el-icon>
        <p style="margin-top: 10px">暂无进行中的海运散货订单</p>
        <el-button type="primary" style="margin-top: 10px" @click="showNewOrder = true">创建第一票业务</el-button>
      </div>
    </el-card>

    <!-- 新建业务 -->
    <el-dialog v-model="showNewOrder" title="新建海运散货业务" width="600px">
      <el-form label-width="100px" :model="newOrder">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="起运港"><el-input v-model="newOrder.origin" placeholder="如 Yantian" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="目的港"><el-input v-model="newOrder.dest" placeholder="如 Hamburg" /></el-form-item>
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
        <el-form-item label="船司/船名"><el-input v-model="newOrder.carrier" placeholder="如 MSK MAERSK" /></el-form-item>
        <el-form-item label="ETD"><el-date-picker v-model="newOrder.etd" type="date" placeholder="预计开船日" style="width: 100%" /></el-form-item>
        <el-form-item label="截仓时间"><el-date-picker v-model="newOrder.cutoffTime" type="datetime" placeholder="截仓截止时间" style="width: 100%" /></el-form-item>
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
          <el-descriptions-item label="件/毛/体">{{ detailOrder.pieces }}件 / {{ detailOrder.gross_weight }}KGS / {{ detailOrder.volume }}CBM</el-descriptions-item>
          <el-descriptions-item label="船司/船名">{{ detailOrder.carrier }}</el-descriptions-item>
          <el-descriptions-item label="ETD">{{ detailOrder.etd }}</el-descriptions-item>
          <el-descriptions-item label="截仓时间">
            <span v-if="detailOrder.cutoff_time" style="color: #e6a23c">{{ detailOrder.cutoff_time }}</span>
            <span v-else style="color: #c0c4cc">未设置</span>
          </el-descriptions-item>
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
import { Ship, ArrowDown, Clock } from '@element-plus/icons-vue'

const searchText = ref('')
const statusFilter = ref('')
const showNewOrder = ref(false)
const showDetail = ref(false)
const detailOrder = ref(null)

const flowSteps = [
  { key: 'released', label: '放舱' },
  { key: 'pickup', label: '安排提货' },
  { key: 'warehoused', label: '进仓' },
  { key: 'wh_verify', label: '核对进仓数据' },
  { key: 'bl_verify', label: '核对提单' },
  { key: 'filing', label: '补料' },
  { key: 'sailing', label: '开船' },
  { key: 'bl_billed', label: '发提单账单' },
  { key: 'paid', label: '收款' },
  { key: 'release_docs', label: '放单' },
  { key: 'arrived', label: '到港' },
  { key: 'delivery', label: '提货' },
  { key: 'closed', label: '结单' },
]

const statusMap = {
  released: { label: '已放舱', type: 'primary' },
  pickup: { label: '安排提货中', type: 'warning' },
  warehoused: { label: '已进仓', type: '' },
  wh_verify: { label: '进仓数据已核对', type: '' },
  bl_verify: { label: '提单已核对', type: '' },
  filing: { label: '已补料', type: 'warning' },
  sailing: { label: '已开船', type: 'success' },
  bl_billed: { label: '提单账单已发', type: '' },
  paid: { label: '已收款', type: 'success' },
  release_docs: { label: '已放单', type: 'primary' },
  arrived: { label: '已到港', type: 'success' },
  delivery: { label: '提货中', type: 'warning' },
  closed: { label: '已结单', type: 'info' },
}

const statusOptions = Object.entries(statusMap).map(([value, s]) => ({
  value,
  label: s.label,
}))

const orders = ref([
  {
    id: 1, orderNo: 'LCL20260701', origin: 'Yantian', dest: 'Hamburg',
    route: 'Yantian → Hamburg', pieces: 55, gross_weight: 1280, volume: 8.5,
    carrier: 'MSK MAERSK', etd: '2026-07-10', cutoff_time: '2026-07-08 12:00',
    status: 'released', progress: 8,
    logs: [
      { action: '放舱', detail: '已收到SO，舱位确认', time: '2026-07-01 10:00' },
    ],
  },
  {
    id: 2, orderNo: 'LCL20260702', origin: 'Shekou', dest: 'Rotterdam',
    route: 'Shekou → Rotterdam', pieces: 120, gross_weight: 3650, volume: 22.0,
    carrier: 'CMA CGM', etd: '2026-07-12', cutoff_time: '2026-07-10 18:00',
    status: 'wh_verify', progress: 25,
    logs: [
      { action: '放舱', detail: 'CMA 放舱完成', time: '2026-06-28 14:00' },
      { action: '安排提货', detail: '已安排拖车提货', time: '2026-06-29 09:30' },
      { action: '进仓', detail: '货物已入仓，仓库编号 WH-03', time: '2026-06-30 16:00' },
      { action: '核对进仓数据', detail: '件毛体与进仓数据一致', time: '2026-07-02 11:00' },
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

function beijingTime(date) {
  const d = date ? new Date(date) : new Date()
  const pad = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const newOrder = ref({
  origin: '', dest: '', pieces: 1, grossWeight: 0.1, volume: 0.1,
  carrier: '', etd: null, cutoffTime: null, remark: '',
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
    orderNo: `LCL${dateStr}${String(id).padStart(2, '0')}`,
    origin: newOrder.value.origin,
    dest: newOrder.value.dest,
    route: `${newOrder.value.origin} → ${newOrder.value.dest}`,
    pieces: newOrder.value.pieces,
    gross_weight: newOrder.value.grossWeight,
    volume: newOrder.value.volume,
    carrier: newOrder.value.carrier || '待定',
    etd: newOrder.value.etd ? newOrder.value.etd.toISOString().slice(0, 10) : '待定',
    cutoff_time: newOrder.value.cutoffTime ? beijingTime(newOrder.value.cutoffTime) : '',
    status: 'released',
    progress: Math.round((0 / (flowSteps.length - 1)) * 100),
    logs: [{ action: '新建', detail: '业务已创建', time: beijingTime() }],
  })
  showNewOrder.value = false
  newOrder.value = { origin: '', dest: '', pieces: 1, grossWeight: 0.1, volume: 0.1, carrier: '', etd: null, cutoffTime: null, remark: '' }
  ElMessage.success('海运业务已创建')
}

function viewOrder(row) {
  detailOrder.value = row
  showDetail.value = true
}

function quickAction(command, row) {
  const idx = flowSteps.findIndex(s => s.key === command)
  if (idx <= flowSteps.findIndex(s => s.key === row.status)) {
    ElMessage.info('状态不能回退')
    return
  }
  row.status = command
  row.currentStep = idx
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
