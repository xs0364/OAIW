<template>
  <div class="container-standardize">
    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="集装箱查询结果 → 佰信海运订舱字段标准化"
      description="把 RPA 集装箱查询结果（盐田/蛇口/宁波/青岛）粘贴到下方，LLM 统一成佰信海运订舱 18 个标准字段，仅供展示核对、不会回填佰信。港口查不到的字段留空，可手改识别值。"
      style="margin-bottom: 14px"
    />

    <el-card class="input-card">
      <template #header>
        <span>输入 — 港口查询结果</span>
      </template>

      <el-form :inline="true" label-width="80px">
        <el-form-item label="港口">
          <el-select
            v-model="form.port_name"
            clearable
            placeholder="选择港口（可空）"
            style="width: 140px"
          >
            <el-option label="盐田港" value="盐田港" />
            <el-option label="蛇口港" value="蛇口港" />
            <el-option label="宁波港" value="宁波港" />
            <el-option label="青岛港" value="青岛港" />
          </el-select>
        </el-form-item>
        <el-form-item label="柜号">
          <el-input v-model="form.container_no" placeholder="如 TLLU4109819" style="width: 180px" />
        </el-form-item>
      </el-form>

      <el-input
        v-model="rawText"
        type="textarea"
        :rows="6"
        placeholder="粘贴港口集装箱查询结果文本（可从 RPA 集装箱查询结果复制，或本页右上「跳转带入」自动填充）"
      />
      <div style="margin-top: 10px">
        <el-button type="primary" :loading="standardizing" @click="runStandardize">
          标准化
        </el-button>
        <el-button v-if="summary" type="success" plain size="small" style="margin-left: 10px">
          {{ summary }}
        </el-button>
      </div>
    </el-card>

    <el-card v-if="rows.length" class="result-card" style="margin-top: 14px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>标准化结果 — 佰信海运订舱标准字段（{{ filledCount }}/18 有值，可手改）</span>
          <el-button v-if="currentId" type="primary" size="small" :loading="saving" @click="saveChanges">
            保存修改
          </el-button>
        </div>
      </template>
      <el-table :data="rows" border size="default" style="width: 100%">
        <el-table-column type="index" label="#" width="44" align="center" />
        <el-table-column label="佰信中文字段" width="140">
          <template #default="{ row }">
            <b>{{ row.label }}</b>
          </template>
        </el-table-column>
        <el-table-column label="识别值（可编辑）" min-width="220">
          <template #default="{ row }">
            <el-input v-model="row.value" placeholder="（该港查不到，留空）" />
          </template>
        </el-table-column>
        <el-table-column label="佰信对应字段" width="150">
          <template #default="{ row }">
            {{ row.baixin_label }}
          </template>
        </el-table-column>
        <el-table-column label="备注" min-width="180">
          <template #default="{ row }">
            <span style="color: #909399; font-size: 12px">{{ row.note }}</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card class="history-card" style="margin-top: 14px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>历史记录（已持久化，全员共享）</span>
          <el-input
            v-model="searchNo"
            placeholder="按柜号过滤"
            clearable
            style="width: 180px"
          />
        </div>
      </template>
      <el-table :data="filteredHistory" border size="default" style="width: 100%" :empty-text="historyLoading ? '加载中…' : '暂无历史记录'">
        <el-table-column label="时间" prop="created_at" width="160" />
        <el-table-column label="港口" prop="port_name" width="76" align="center" />
        <el-table-column label="柜号" prop="container_no" width="130" />
        <el-table-column label="摘要" prop="summary" min-width="150" show-overflow-tooltip />
        <el-table-column label="创建人" prop="created_by" width="90" align="center" />
        <el-table-column label="有值" prop="filled_count" width="56" align="center" />
        <el-table-column label="操作" width="130" align="center">
          <template #default="{ row }">
            <el-button size="small" @click="loadRecord(row)">加载</el-button>
            <el-button size="small" type="danger" @click="delRecord(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import client from '../api/client'

const route = useRoute()

// 与后端 backend/core/routers/standardize.py STANDARD_FIELDS 保持一致（key 对齐，仅展示用）
const STANDARD_FIELDS = [
  { key: 'container_no', label: '柜号',     baixin_label: '集装箱号',       note: '订舱网格第3列' },
  { key: 'size_type',    label: '箱型',     baixin_label: '箱型箱重',       note: '' },
  { key: 'seal',         label: '封条',     baixin_label: '封铅号',         note: '订舱网格第4列' },
  { key: 'gross',        label: '毛重',     baixin_label: '毛重',           note: '' },
  { key: 'booking_no',   label: '订舱单号', baixin_label: 'S/O NO',         note: '必填' },
  { key: 'bl_no',        label: '提单号',   baixin_label: '船东提单号',     note: '' },
  { key: 'vessel',       label: '船名',     baixin_label: '英文船名',       note: '必填；另有中文船名' },
  { key: 'voyage',       label: '航次',     baixin_label: '航次',           note: '模板内 key=terminal 实为航次' },
  { key: 'terminal',     label: '码头',     baixin_label: '码头/当前位置',  note: 'sources 层，无表单字段' },
  { key: 'pol',          label: '装货港',   baixin_label: '装运港',         note: '' },
  { key: 'dest',         label: '目的港',   baixin_label: '目的港+卸货港',  note: '映射 dest 与 dest_unload 两字段' },
  { key: 'eta',          label: 'ETA',      baixin_label: 'ETA',            note: '' },
  { key: 'etd',          label: 'ETD',      baixin_label: 'ETD',            note: '' },
  { key: 'owner',        label: '箱主',     baixin_label: '船东',           note: '' },
  { key: 'status',       label: '状态',     baixin_label: '状态',           note: 'sources 层，无表单字段' },
  { key: 'pieces',       label: '件数',     baixin_label: '件数',           note: '必填' },
  { key: 'volume',       label: '体积',     baixin_label: '体积',           note: '必填' },
  { key: 'cargo_name',   label: '品名',     baixin_label: '货物简称',       note: '' },
]

const form = ref({ port_name: '', container_no: '' })
const rawText = ref('')
const standardizing = ref(false)
const summary = ref('')
const rows = ref([])

// 历史记录（持久化）
const history = ref([])
const historyLoading = ref(false)
const searchNo = ref('')
const currentId = ref(null)
const saving = ref(false)

const filledCount = computed(() => rows.value.filter((r) => (r.value || '').trim()).length)

const filteredHistory = computed(() => {
  const q = (searchNo.value || '').trim().toUpperCase()
  if (!q) return history.value
  return history.value.filter((h) => (h.container_no || '').toUpperCase().includes(q))
})

function runStandardize() {
  const text = rawText.value?.trim()
  if (!text) {
    ElMessage.warning('请先粘贴港口查询结果')
    return
  }
  standardizing.value = true
  summary.value = ''
  client
    .post('/standardize/parse', {
      port_name: form.value.port_name,
      container_no: form.value.container_no,
      raw_text: text,
    })
    .then((r) => {
      const d = r.data
      if (!d?.success) {
        ElMessage.error(d?.error || '标准化失败')
        return
      }
      rows.value = STANDARD_FIELDS.map((f) => ({
        ...f,
        value: (d.fields && d.fields[f.key]) || '',
      }))
      summary.value = d.summary || `识别出 ${filledCount.value} 个字段`
      currentId.value = d.id || null
      loadHistory()
      ElMessage.success(`已标准化并保存，${filledCount.value} 个字段有值`)
    })
    .catch((e) => {
      ElMessage.error(e.response?.data?.detail || e.message || '标准化失败')
    })
    .finally(() => {
      standardizing.value = false
    })
}

function loadHistory() {
  historyLoading.value = true
  client
    .get('/standardize/history')
    .then((r) => {
      if (r.data?.success) history.value = r.data.items || []
    })
    .catch(() => {})
    .finally(() => {
      historyLoading.value = false
    })
}

function loadRecord(row) {
  currentId.value = row.id
  rows.value = STANDARD_FIELDS.map((f) => ({
    ...f,
    value: (row.fields && row.fields[f.key]) || '',
  }))
  summary.value = row.summary || ''
  form.value.port_name = row.port_name || ''
  form.value.container_no = row.container_no || ''
  ElMessage.success(`已加载历史 #${row.id}`)
}

function saveChanges() {
  if (!currentId.value) return
  const fields = {}
  rows.value.forEach((r) => {
    fields[r.key] = r.value || ''
  })
  saving.value = true
  client
    .put(`/standardize/history/${currentId.value}`, { fields })
    .then((r) => {
      if (r.data?.success) {
        ElMessage.success('已保存修改')
        loadHistory()
      } else {
        ElMessage.error(r.data?.error || '保存失败')
      }
    })
    .catch((e) => {
      ElMessage.error(e.response?.data?.detail || e.message || '保存失败')
    })
    .finally(() => {
      saving.value = false
    })
}

function delRecord(row) {
  ElMessageBox.confirm(`确认删除该条历史记录（柜号 ${row.container_no || '-'}）？`, '删除确认', {
    confirmButtonText: '删除',
    cancelButtonText: '取消',
    type: 'warning',
  })
    .then(() => {
      client.delete(`/standardize/history/${row.id}`).then((r) => {
        if (r.data?.success) {
          if (currentId.value === row.id) currentId.value = null
          loadHistory()
          ElMessage.success('已删除')
        } else {
          ElMessage.error(r.data?.error || '删除失败')
        }
      })
    })
    .catch(() => {})
}

onMounted(() => {
  if (route.query.container_no) form.value.container_no = route.query.container_no
  if (route.query.port_name) form.value.port_name = route.query.port_name
  const last = sessionStorage.getItem('last_container_query')
  if (last && !rawText.value) rawText.value = last
  loadHistory()
})
</script>
