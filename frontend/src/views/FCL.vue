<template>
  <div>
    <h2>整柜 FCL</h2>
    <p style="color: #909399; margin-bottom: 20px">
      整柜出口全流程：接单审单 → 放舱 → 拖车报关 → 核对提单 → 补料/VGM → AMS/ISF → 开船 → 对账 → 收款 → 放单 → 确认到港 → 提柜 → 还空 → 结单
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
      <el-col :span="4">
        <el-select v-model="containerFilter" placeholder="箱型" clearable size="default" style="width: 100%">
          <el-option label="20GP" value="20GP" />
          <el-option label="40GP" value="40GP" />
          <el-option label="40HQ" value="40HQ" />
          <el-option label="20RF" value="20RF" />
          <el-option label="40RH" value="40RH" />
        </el-select>
      </el-col>
      <el-col :span="10" style="text-align: right">
        <el-button type="primary" @click="showNewOrder = true">+ 新建业务</el-button>
      </el-col>
    </el-row>

    <!-- 订单列表 -->
    <el-card shadow="never">
      <el-table :data="filteredOrders" style="width: 100%" v-if="filteredOrders.length > 0" stripe>
        <el-table-column prop="orderNo" label="业务单号" width="140" />
        <el-table-column prop="route" label="航线" width="160" />
        <el-table-column label="箱型/箱号" width="180">
          <template #default="{ row }">
            <el-tag size="small">{{ row.containerType }}</el-tag>
            <span style="margin-left: 6px; font-size: 12px; color: #606266">{{ row.containerNo || '待定' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="carrier" label="船司" width="110" />
        <el-table-column prop="vessel" label="船名航次" width="140" />
        <el-table-column prop="etd" label="ETD" width="95" />
        <el-table-column label="当前状态" width="105">
          <template #default="{ row }">
            <el-tag :type="statusMap[row.status]?.type || 'info'" size="small">
              {{ statusMap[row.status]?.label || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="流程进度" min-width="200">
          <template #default="{ row }">
            <el-progress :percentage="row.progress" :status="row.progress >= 100 ? 'success' : undefined" :stroke-width="14" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="viewOrder(row)">详情</el-button>
            <el-button text type="primary" size="small" @click="showAdvance(row)">推进</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div v-else style="text-align: center; padding: 60px 0; color: #c0c4cc">
        <el-icon :size="48"><Box /></el-icon>
        <p style="margin-top: 10px">暂无进行中的整柜业务</p>
        <el-button type="primary" style="margin-top: 10px" @click="showNewOrder = true">创建第一票业务</el-button>
      </div>
    </el-card>

    <!-- 新建业务 -->
    <el-dialog v-model="showNewOrder" title="新建整柜业务" width="650px">
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
            <el-form-item label="箱型">
              <el-select v-model="newOrder.containerType" style="width: 100%">
                <el-option label="20GP" value="20GP" />
                <el-option label="40GP" value="40GP" />
                <el-option label="40HQ" value="40HQ" />
                <el-option label="20RF" value="20RF" />
                <el-option label="40RH" value="40RH" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="箱号"><el-input v-model="newOrder.containerNo" placeholder="如 MSKU1234567" /></el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="毛重(KGS)"><el-input-number v-model="newOrder.grossWeight" :min="1" style="width: 100%" /></el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="船司"><el-input v-model="newOrder.carrier" placeholder="如 MSK" /></el-form-item>
        <el-form-item label="船名航次"><el-input v-model="newOrder.vessel" placeholder="如 MAERSK ECHO / 726W" /></el-form-item>
        <el-form-item label="ETD"><el-date-picker v-model="newOrder.etd" type="date" placeholder="预计开船日" style="width: 100%" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="newOrder.remark" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showNewOrder = false">取消</el-button>
        <el-button type="primary" @click="createOrder">创建</el-button>
      </template>
    </el-dialog>

    <!-- 推进状态对话框 -->
    <el-dialog v-model="showAdvanceDialog" title="推进业务状态" width="400px">
      <p style="color: #909399; margin-bottom: 12px; font-size: 13px">
        当前状态：<el-tag size="small">{{ statusMap[advanceOrder?.status]?.label }}</el-tag>
      </p>
      <el-select v-model="advanceTarget" placeholder="选择下一步状态" style="width: 100%">
        <el-option
          v-for="s in availableNextSteps"
          :key="s.value"
          :label="s.label"
          :value="s.value"
        />
      </el-select>
      <div style="margin-top: 12px">
        <el-input v-model="advanceNote" type="textarea" :rows="2" placeholder="操作备注（可选）" />
      </div>
      <template #footer>
        <el-button @click="showAdvanceDialog = false">取消</el-button>
        <el-button type="primary" @click="confirmAdvance">确认推进</el-button>
      </template>
    </el-dialog>

    <!-- 详情抽屉 -->
    <el-drawer v-model="showDetail" :title="'业务详情 — ' + (detailOrder?.orderNo || '')" size="500px">
      <template v-if="detailOrder">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="航线">{{ detailOrder.route }}</el-descriptions-item>
          <el-descriptions-item label="箱型/箱号">{{ detailOrder.containerType }} / {{ detailOrder.containerNo || '待定' }}</el-descriptions-item>
          <el-descriptions-item label="毛重">{{ detailOrder.gross_weight }} KGS</el-descriptions-item>
          <el-descriptions-item label="船司">{{ detailOrder.carrier }}</el-descriptions-item>
          <el-descriptions-item label="船名航次">{{ detailOrder.vessel }}</el-descriptions-item>
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

        <div style="margin-top: 12px">
          <b>操作记录</b>
          <div v-if="(detailOrder.logs?.length || 0) === 0" style="color: #c0c4cc; margin-top: 8px; font-size: 13px">暂无操作记录</div>
          <div v-for="(log, i) in detailOrder.logs" :key="i" style="padding: 8px 0; border-bottom: 1px solid #f0f0f0; font-size: 13px">
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
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Box } from '@element-plus/icons-vue'

const searchText = ref('')
const statusFilter = ref('')
const containerFilter = ref('')
const showNewOrder = ref(false)
const showDetail = ref(false)
const showAdvanceDialog = ref(false)
const detailOrder = ref(null)
const advanceOrder = ref(null)
const advanceTarget = ref('')
const advanceNote = ref('')
const orders = ref([])
const loading = ref(false)

// 字段映射：后端 snake_case → 前端 camelCase
const FIELD_MAP = {
  orderNo: 'orderNo', origin: 'origin', dest: 'dest', route: 'route',
  containerType: 'containerType', containerNo: 'containerNo',
  grossWeight: 'grossWeight', pieces: 'pieces', volume: 'volume',
  carrier: 'carrier', vessel: 'vessel', vesselName: 'vesselName',
  voyage: 'voyage', blNo: 'blNo', sealNo: 'sealNo', terminal: 'terminal',
  etd: 'etd', eta: 'eta', direction: 'direction',
  status: 'status', progress: 'progress', logs: 'logs',
}

async function fetchOrders() {
  loading.value = true
  try {
    const params = new URLSearchParams()
    if (searchText.value) params.set('search', searchText.value)
    if (statusFilter.value) params.set('status', statusFilter.value)
    if (containerFilter.value) params.set('container_type', containerFilter.value)
    const qs = params.toString()
    const res = await fetch(`/api/fcl/orders${qs ? '?' + qs : ''}`)
    const data = await res.json()
    if (data.success) {
      orders.value = data.orders.map(mapOrder)
    }
  } catch (e) {
    ElMessage.error('加载订单失败')
  } finally {
    loading.value = false
  }
}

function mapOrder(o) {
  return {
    id: o.id,
    orderNo: o.orderNo,
    origin: o.origin || '',
    dest: o.dest || '',
    route: o.route || (o.origin && o.dest ? `${o.origin} → ${o.dest}` : ''),
    containerType: o.containerType || '',
    containerNo: o.containerNo || '',
    gross_weight: o.grossWeight || 0,
    pieces: o.pieces || 0,
    volume: o.volume || 0,
    carrier: o.carrier || '',
    vessel: o.vessel || '',
    vesselName: o.vesselName || '',
    voyage: o.voyage || '',
    blNo: o.blNo || '',
    sealNo: o.sealNo || '',
    terminal: o.terminal || '',
    etd: o.etd || '',
    eta: o.eta || '',
    direction: o.direction || '',
    status: o.status || 'received',
    progress: o.progress || 0,
    logs: o.logs || [],
    createdAt: o.createdAt || '',
    updatedAt: o.updatedAt || '',
  }
}

const flowSteps = [
  { key: 'received', label: '接单审单' },
  { key: 'so_release', label: '放舱' },
  { key: 'trucking', label: '拖车报关' },
  { key: 'bl_draft', label: '核对提单' },
  { key: 'si_vgm', label: '补料/VGM' },
  { key: 'ams_isf', label: 'AMS/ISF' },
  { key: 'sailing', label: '开船' },
  { key: 'reconciled', label: '对账' },
  { key: 'payment', label: '收款' },
  { key: 'release', label: '放单' },
  { key: 'arrived', label: '确认到港' },
  { key: 'delivery', label: '提柜' },
  { key: 'empty_return', label: '还空' },
  { key: 'closed', label: '结单' },
]

const statusMap = {
  received: { label: '已接单', type: 'primary' },
  so_release: { label: '已放舱', type: 'primary' },
  trucking: { label: '拖车报关', type: 'warning' },
  bl_draft: { label: '对单中', type: '' },
  si_vgm: { label: '补料/VGM', type: '' },
  ams_isf: { label: 'AMS/ISF', type: 'warning' },
  sailing: { label: '已开船', type: 'success' },
  reconciled: { label: '已对账', type: '' },
  payment: { label: '待收款', type: 'danger' },
  release: { label: '已放单', type: 'success' },
  arrived: { label: '已到港', type: 'success' },
  delivery: { label: '提柜中', type: 'warning' },
  empty_return: { label: '已还空', type: '' },
  closed: { label: '已结单', type: 'info' },
}

const statusOptions = Object.entries(statusMap).map(([value, s]) => ({
  value,
  label: s.label,
}))

const filteredOrders = computed(() => {
  let list = orders.value
  if (searchText.value) {
    const q = searchText.value.toLowerCase()
    list = list.filter(o => o.orderNo.toLowerCase().includes(q) || (o.route || '').toLowerCase().includes(q) || (o.containerNo || '').toLowerCase().includes(q))
  }
  if (statusFilter.value) {
    list = list.filter(o => o.status === statusFilter.value)
  }
  if (containerFilter.value) {
    list = list.filter(o => o.containerType === containerFilter.value)
  }
  return list
})

onMounted(() => fetchOrders())


function beijingTime(date) {
  const d = date ? new Date(date) : new Date()
  const pad = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const newOrder = ref({
  origin: '', dest: '', containerType: '20GP', containerNo: '',
  grossWeight: 1000, carrier: '', vessel: '', etd: null, remark: '',
})

function createOrder() {
  if (!newOrder.value.origin || !newOrder.value.dest) {
    ElMessage.warning('请填写起运港和目的港')
    return
  }
  const body = {
    origin: newOrder.value.origin,
    dest: newOrder.value.dest,
    route: `${newOrder.value.origin} → ${newOrder.value.dest}`,
    containerType: newOrder.value.containerType,
    containerNo: newOrder.value.containerNo || '',
    grossWeight: newOrder.value.grossWeight,
    carrier: newOrder.value.carrier || '',
    vessel: newOrder.value.vessel || '',
    etd: newOrder.value.etd ? newOrder.value.etd.toISOString().slice(0, 10) : '',
  }
  fetch('/api/fcl/orders', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).then(r => r.json()).then(data => {
    if (data.success) {
      orders.value.unshift(mapOrder(data.order))
      showNewOrder.value = false
      newOrder.value = { origin: '', dest: '', containerType: '20GP', containerNo: '', grossWeight: 1000, carrier: '', vessel: '', etd: null, remark: '' }
      ElMessage.success('整柜业务已创建')
    } else {
      ElMessage.error(data.error || '创建失败')
    }
  }).catch(e => {
    ElMessage.error('网络错误')
  })
}

function viewOrder(row) {
  detailOrder.value = row
  showDetail.value = true
}

function showAdvance(row) {
  advanceOrder.value = row
  advanceTarget.value = ''
  advanceNote.value = ''
  showAdvanceDialog.value = true
}

const availableNextSteps = computed(() => {
  if (!advanceOrder.value) return []
  const curIdx = flowSteps.findIndex(s => s.key === advanceOrder.value.status)
  return flowSteps
    .filter((_, i) => i > curIdx)
    .map(s => ({ value: s.key, label: statusMap[s.key]?.label || s.label }))
})

function confirmAdvance() {
  if (!advanceTarget.value) {
    ElMessage.warning('请选择目标状态')
    return
  }
  const row = advanceOrder.value
  const targetIdx = flowSteps.findIndex(s => s.key === advanceTarget.value)

  // 调后端API推进
  fetch(`/api/fcl/orders/${row.id}/advance`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status: advanceTarget.value, note: advanceNote.value || '' }),
  }).then(r => r.json()).then(data => {
    if (data.success) {
      // 更新本地数据
      const idx = orders.value.findIndex(o => o.id === row.id)
      if (idx >= 0) orders.value[idx] = mapOrder(data.order)
      showAdvanceDialog.value = false
      ElMessage.success(`已推进到「${statusMap[advanceTarget.value]?.label}」`)
    } else {
      ElMessage.error(data.error || '推进失败')
    }
  }).catch(e => {
    ElMessage.error('网络错误')
  })
}

function getStepTagType(order, key) {
  const curIdx = flowSteps.findIndex(s => s.key === order.status)
  const stepIdx = flowSteps.findIndex(s => s.key === key)
  if (stepIdx < curIdx) return 'success'
  if (stepIdx === curIdx) return 'primary'
  return 'info'
}

function getStepStatus(order, key) {
  const curIdx = flowSteps.findIndex(s => s.key === order.status)
  const stepIdx = flowSteps.findIndex(s => s.key === key)
  if (stepIdx < curIdx) return 'success'
  if (stepIdx === curIdx) return 'process'
  return 'wait'
}
</script>
