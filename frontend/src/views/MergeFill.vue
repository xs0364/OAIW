<template>
  <div class="merge-fill">
    <!-- 首次使用提示：下载本机 agent 部署包 -->
    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="首次使用：请先在本机安装佰信代填助手"
      style="margin-bottom: 14px"
    >
      <template #default>
        <span>佰信自动填值由当前电脑上的本地 agent 完成，每台电脑各装一次。首次使用请下载部署包并双击 setup.bat 安装（约 5~20 分钟）：</span>
        <el-link type="primary" :href="pkgUrl" target="_blank">下载佰信 Agent 部署包</el-link>
        <span style="margin-left: 8px">安装完成后刷新本页即可正常使用。</span>
      </template>
    </el-alert>

    <!-- 初代版本横幅 -->
    <el-alert
      type="warning"
      :closable="false"
      show-icon
      title="初代版本（V1）· 自动填值"
      description="海运(SB-S)与空运(SB-A)订舱已打通：自动检索并填大部分字段。填完请务必人工逐项核对后再保存：① 业务操作/单证客服等【人名下拉】无法自动选，需在佰信弹窗下拉框人工选择；② 系统不自动保存，核对无误后请人工保存；③ 运行期间请勿操作本机鼠标键盘。"
      style="margin-bottom: 14px"
    />
    <el-card class="input-card">
      <template #header>
        <span>佰信合并录入 — 上传文件 + 柜号查询 → 字段级合并去重</span>
      </template>

      <el-form :inline="true" label-width="90px">
        <el-form-item label="柜号" required>
          <el-input v-model="form.container_no" placeholder="如 ECMU6262406" style="width: 180px" />
        </el-form-item>
        <el-form-item label="订舱号">
          <el-input v-model="form.booking_no" placeholder="SO号/订舱号" style="width: 160px" />
        </el-form-item>
        <el-form-item label="工作号">
          <el-input v-model="form.order_no" placeholder="佰信检索值 SB-S/SB-A…（自动填必填）" style="width: 190px" />
        </el-form-item>
      </el-form>

      <el-form :inline="true" label-width="90px">
        <el-form-item label="上传文件">
          <el-upload
            ref="uploadRef"
            drag
            multiple
            :auto-upload="false"
            accept=".xlsx,.xls,.pdf,.png,.jpg,.jpeg,.docx,.doc,.txt"
            :on-change="onFileChange"
            :on-remove="onFileRemove"
            :file-list="fileList"
          >
            <div class="el-upload__text">拖拽文件到此处或 <em>点击上传</em></div>
          </el-upload>
        </el-form-item>
        <el-form-item label="复用已上传">
          <el-select
            v-model="selectedDocIds"
            multiple
            clearable
            placeholder="从文档管理选择"
            style="width: 260px"
          >
            <el-option
              v-for="d in docOptions"
              :key="d.file_id"
              :label="d.filename"
              :value="d.file_id"
            />
          </el-select>
        </el-form-item>
      </el-form>

      <el-button type="primary" :loading="previewLoading" @click="doPreview">
        生成合并预览
      </el-button>
    </el-card>

    <!-- 合并预览 -->
    <el-card v-if="preview" class="preview-card">
      <template #header>
        <div style="display:flex;align-items:center;gap:12px">
          <span>合并预览</span>
          <el-tag v-if="preview.order_no" type="info" effect="plain">工作号 {{ preview.order_no }}</el-tag>
          <el-tag v-if="preview.warning" type="warning" effect="plain">{{ preview.warning }}</el-tag>
        </div>
      </template>

      <el-table :data="fieldsTable" border size="small" max-height="480">
        <el-table-column prop="label" label="字段" width="90" />
        <el-table-column label="柜号查询值" width="160">
          <template #default="{ row }">
            <span :class="{ 'cell-empty': !row.query_value }">{{ row.query_value ?? '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="上传文件值" width="160">
          <template #default="{ row }">
            <span :class="{ 'cell-empty': !row.file_value }">{{ row.file_value ?? '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="合并结果" width="180">
          <template #default="{ row }">
            <span class="merged-cell">{{ row.merged_value ?? '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="来源" width="130">
          <template #default="{ row }">
            <el-tag v-if="row.source" :type="sourceTagType(row.source)" size="small">
              {{ sourceLabel(row.source) }}
            </el-tag>
            <span v-else class="cell-empty">—</span>
          </template>
        </el-table-column>
      </el-table>

      <div style="margin-top: 14px; display:flex; gap: 10px">
        <el-button type="success" :loading="confirmLoading" @click="doConfirm">
          确认合并并同步 FCLOrder
        </el-button>
        <el-button @click="preview = null">重置</el-button>
      </div>
    </el-card>

    <!-- 确认结果 -->
    <el-card v-if="confirmResult" class="result-card">
      <template #header><span>已同步</span></template>
      <el-descriptions :column="1" border size="small">
        <el-descriptions-item label="工作号">{{ confirmResult.order_no || '—' }}</el-descriptions-item>
        <el-descriptions-item label="柜号">{{ confirmResult.container_no }}</el-descriptions-item>
        <el-descriptions-item label="FCLOrder">{{ confirmResult.fcl_order_no }}</el-descriptions-item>
        <el-descriptions-item label="合并JSON">{{ confirmResult.output_path }}</el-descriptions-item>
        <el-descriptions-item label="佰信填值">
          在佰信中打开该订舱弹窗后运行：
          <el-input :model-value="fillCommand" readonly size="small" style="margin-top:6px">
            <template #append>
              <el-button @click="copyCommand">复制</el-button>
            </template>
          </el-input>
        </el-descriptions-item>
      </el-descriptions>

      <!-- 一键自动录入本机佰信 -->
      <div style="margin-top: 14px">
        <el-button
          type="danger"
          :loading="baixinRunning"
          :disabled="baixinRunning || !!baixinDone?.success"
          @click="runBaixinAuto"
        >
          {{ baixinRunning ? '正在录入本机佰信...' : '一键自动填佰信（本机）' }}
        </el-button>
        <span v-if="baixinRunning" style="margin-left: 8px; color: #e6a23c; font-size: 12px">
          ⚠️ 约2-4分钟，期间请不要操作这台电脑的鼠标键盘
        </span>
      </div>
      <!-- 日志区 -->
      <div v-if="baixinLogs.length || baixinRunning" ref="logBoxRef" class="baixin-log-box">
        <div v-for="(line, i) in baixinLogs" :key="i">{{ line }}</div>
        <div v-if="!baixinLogs.length" style="color: #666">等待日志...</div>
      </div>
    </el-card>

    <!-- 费用录入：海运/空运应收应付登记 -->
    <el-card class="fee-card">
      <template #header>
        <span>佰信费用录入 — 海运/空运应收应付登记（一键填佰信）</span>
      </template>

      <el-form :inline="true" label-width="90px">
        <el-form-item label="运输方式" required>
          <el-radio-group v-model="feeForm.mode">
            <el-radio-button value="sea">海运</el-radio-button>
            <el-radio-button value="air">空运</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="工作号" required>
          <el-input
            v-model="feeForm.order_no"
            placeholder="佰信检索值 SB-A…(空运)/SB-S…(海运)"
            style="width: 230px"
          />
        </el-form-item>
      </el-form>

      <!-- 粘贴识别：粘贴邮件/Excel 费用块 → LLM 抽成多行费用表格 -->
      <el-form :inline="true" label-width="90px">
        <el-form-item label="粘贴费用">
          <el-input
            v-model="pasteText"
            type="textarea"
            :rows="3"
            placeholder="从邮件/Excel 复制费用内容粘贴到此，例如：&#10;上海远洋  应收 12500 10 1250&#10;中远报关  应付 500 1 500"
            style="width: 560px"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="parseLoading" @click="parseFee">粘贴识别</el-button>
        </el-form-item>
      </el-form>
      <div style="color: #909399; font-size: 12px; margin-bottom: 8px">
        支持邮件正文 / Excel 复制块；识别为多行费用后逐行核对、可手改，也可手动加行。
      </div>

      <el-table :data="feeRows" border size="small" max-height="320">
        <el-table-column label="应收往来单位" width="150">
          <template #default="{ row }">
            <el-input v-model="row.recv_trader" placeholder="应收往来单位" />
          </template>
        </el-table-column>
        <el-table-column label="应收金额" width="110">
          <template #default="{ row }">
            <el-input v-model="row.recv_amount" placeholder="金额" />
          </template>
        </el-table-column>
        <el-table-column label="应收数量" width="90">
          <template #default="{ row }">
            <el-input v-model="row.recv_qty" placeholder="数量" />
          </template>
        </el-table-column>
        <el-table-column label="应收单价" width="110">
          <template #default="{ row }">
            <el-input v-model="row.recv_price" placeholder="单价" />
          </template>
        </el-table-column>
        <el-table-column label="应付往来单位" width="150">
          <template #default="{ row }">
            <el-input v-model="row.pay_trader" placeholder="应付往来单位" />
          </template>
        </el-table-column>
        <el-table-column label="应付金额" width="110">
          <template #default="{ row }">
            <el-input v-model="row.pay_amount" placeholder="金额" />
          </template>
        </el-table-column>
        <el-table-column label="应付数量" width="90">
          <template #default="{ row }">
            <el-input v-model="row.pay_qty" placeholder="数量" />
          </template>
        </el-table-column>
        <el-table-column label="应付单价" width="110">
          <template #default="{ row }">
            <el-input v-model="row.pay_price" placeholder="单价" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="70">
          <template #default="{ $index }">
            <el-button link type="danger" @click="removeFeeRow($index)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div style="margin-top: 6px; display: flex; align-items: center; gap: 12px">
        <el-button size="small" @click="addFeeRow">＋ 添加一行</el-button>
        <span style="color: #909399; font-size: 12px">{{ feeRowCount }} 条费用（全空行自动忽略）</span>
      </div>
      <el-divider />

      <div style="margin-top: 8px; display: flex; gap: 10px; align-items: center">
        <el-button
          type="danger"
          :loading="feeRunning"
          :disabled="feeRunning || !!feeDone?.success"
          @click="runFeeFill"
        >
          {{ feeRunning ? '正在录入本机佰信...' : '一键填佰信（应收应付）' }}
        </el-button>
        <span v-if="feeRunning" style="color: #e6a23c; font-size: 12px">
          ⚠️ 约1-3分钟，期间请不要操作这台电脑的鼠标键盘；费用弹窗不自动保存，填完请人工核对
        </span>
      </div>
      <!-- 费用日志区 -->
      <div v-if="feeLogs.length || feeRunning" ref="feeLogBoxRef" class="baixin-log-box">
        <div v-for="(line, i) in feeLogs" :key="i">{{ line }}</div>
        <div v-if="!feeLogs.length" style="color: #666">等待日志...</div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import client from '../api/client'

const route = useRoute()
// 部署包下载地址：随当前页面来源动态拼接（局域网 IP / Tailscale 均自动适配）
const pkgUrl = `${window.location.origin}/baixin_agent_setup.zip`
const form = ref({ container_no: '', booking_no: '', order_no: '' })
const fileList = ref([])
const uploadRef = ref()
const selectedDocIds = ref([])
const docOptions = ref([])

const previewLoading = ref(false)
const confirmLoading = ref(false)
const preview = ref(null)
const confirmResult = ref(null)
const baixinRunning = ref(false)
const baixinLogs = ref([])
const baixinDone = ref(null)
const logBoxRef = ref()
const feeForm = ref({
  mode: 'sea',
  order_no: '',
})
const feeRows = ref([{}])
const pasteText = ref('')
const parseLoading = ref(false)
const feeRunning = ref(false)
const feeLogs = ref([])
const feeDone = ref(null)
const feeLogBoxRef = ref()

const fieldsTable = computed(() => (preview.value?.fields_table || []))
const fillCommand = computed(() => {
  if (!confirmResult.value?.output_path) return ''
  const fname = confirmResult.value.output_path.replace(/\\/g, '/').split('/').pop()
  return `python _baixin_merge_fill.py ${fname}`
})

function onFileChange(file, list) {
  const seen = new Set(fileList.value.map((f) => f.name + ':' + f.size))
  if (!seen.has(file.name + ':' + file.size)) {
    fileList.value = list
  }
}
function onFileRemove() {
  fileList.value = uploadRef.value?.uploadFiles || []
}

function sourceLabel(s) {
  return {
    query: '查询',
    file: '文件',
    file_fallback: '查询缺·文件补',
    query_fallback: '文件缺·查询补',
  }[s] || s
}
function sourceTagType(s) {
  return { query: 'primary', file: 'success', file_fallback: 'warning', query_fallback: 'info' }[s] || 'info'
}

async function doPreview() {
  if (!form.value.container_no?.trim()) {
    ElMessage.warning('请填写柜号')
    return
  }
  previewLoading.value = true
  try {
    const fd = new FormData()
    fd.append('container_no', form.value.container_no.trim())
    if (form.value.booking_no?.trim()) fd.append('booking_no', form.value.booking_no.trim())
    if (form.value.order_no?.trim()) fd.append('order_no', form.value.order_no.trim())
    fileList.value.forEach((f) => {
      if (f.raw) fd.append('files', f.raw)
      else if (f.file) fd.append('files', f.file)
    })
    if (selectedDocIds.value.length) fd.append('doc_ids', selectedDocIds.value.join(','))

    const r = await client.post('/merge/preview', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000,
    })
    if (!r.data?.success) {
      ElMessage.error(r.data?.error || '预览失败')
      return
    }
    preview.value = r.data
    confirmResult.value = null
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message || '预览失败')
  } finally {
    previewLoading.value = false
  }
}

async function doConfirm() {
  confirmLoading.value = true
  try {
    const r = await client.post('/merge/confirm', {
      container_no: preview.value.container_no,
      booking_no: preview.value.booking_no,
      order_no: preview.value.order_no,
      merged: preview.value.merged,
      provenance: preview.value.provenance,
    })
    if (!r.data?.success) {
      ElMessage.error(r.data?.error || '确认失败')
      return
    }
    confirmResult.value = r.data
    ElMessage.success('已同步 FCLOrder，请在佰信中运行填值脚本')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message || '确认失败')
  } finally {
    confirmLoading.value = false
  }
}

async function copyCommand() {
  try {
    await navigator.clipboard.writeText(fillCommand.value)
    ElMessage.success('已复制命令')
  } catch {
    ElMessage.warning('复制失败，请手动复制')
  }
}

const BAIXIN_AGENT_URL = 'http://127.0.0.1:7878'

// 日志自动滚到底
watch(baixinLogs, () => {
  nextTick(() => {
    if (logBoxRef.value) logBoxRef.value.scrollTop = logBoxRef.value.scrollHeight
  })
})
watch(feeLogs, () => {
  nextTick(() => {
    if (feeLogBoxRef.value) feeLogBoxRef.value.scrollTop = feeLogBoxRef.value.scrollHeight
  })
})

/**
 * 共享：检查本机 agent → POST /run → SSE 流式解析。
 * payload: POST /run 请求体；logs/done: 各自日志数组与结果 ref。
 */
async function runAgentSSE(payload, logs, done) {
  // 1. 检查本机 Agent 是否已启动
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), 3000)
  let healthy = false
  try {
    const h = await fetch(`${BAIXIN_AGENT_URL}/health`, { signal: ctrl.signal })
    healthy = h.ok && (await h.json())?.ok
  } catch {
    healthy = false
  }
  clearTimeout(timer)
  if (!healthy) {
    throw new Error('未检测到本机佰信Agent，请先运行 D:\\OAIW\\start_baixin_agent.bat 启动')
  }
  logs.value.push('[Agent 已连接，开始录入本机佰信...]')

  // 2. SSE 流式执行（在本机 agent 上操作本机佰信）
  const resp = await fetch(`${BAIXIN_AGENT_URL}/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!resp.ok) throw new Error(`Agent 返回 HTTP ${resp.status}`)

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let evtType = ''
  while (true) {
    const { done: streamDone, value } = await reader.read()
    if (streamDone) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''
    for (const line of lines) {
      if (line.startsWith('event: ')) {
        evtType = line.slice(7).trim()
      } else if (line.startsWith('data: ')) {
        const data = line.slice(6)
        if (evtType === 'done') {
          evtType = ''
          try {
            const result = JSON.parse(data)
            done.value = result
            if (result.success) ElMessage.success(result.message || '完成')
            else ElMessage.error(result.message || '失败')
          } catch {
            logs.value.push(data)
          }
        } else if (data !== '[SSE connected]') {
          logs.value.push(data)
        }
      }
    }
  }
}

async function runBaixinAuto() {
  if (!confirmResult.value) return
  // 安全校验：工作号为空时 rerun_flow 会检索默认单号，可能填错单
  if (!confirmResult.value.order_no) {
    ElMessage.warning('请先填写工作号（佰信检索值 SB-…）再预览/确认')
    return
  }
  baixinRunning.value = true
  baixinLogs.value = []
  baixinDone.value = null
  try {
    await runAgentSSE({
      order_no: confirmResult.value.order_no,
      container_no: confirmResult.value.container_no,
      merged: preview.value?.merged || {},
      provenance: preview.value?.provenance || {},
    }, baixinLogs, baixinDone)
  } catch (e) {
    baixinDone.value = { success: false, message: e.message }
    ElMessage.error(e.message)
  } finally {
    baixinRunning.value = false
  }
}

// 行内某侧（recv/pay）是否有任何值
function feeRowHasSide(row, side) {
  return ['trader', 'amount', 'qty', 'price'].some((k) => row[`${side}_${k}`]?.trim())
}

const feeRowCount = computed(
  () => feeRows.value.filter((r) => feeRowHasSide(r, 'recv') || feeRowHasSide(r, 'pay')).length,
)

function addFeeRow() {
  feeRows.value.push({})
}

function removeFeeRow(i) {
  feeRows.value.splice(i, 1)
  if (!feeRows.value.length) feeRows.value.push({})
}

async function parseFee() {
  const text = pasteText.value?.trim()
  if (!text) {
    ElMessage.warning('请先粘贴费用内容')
    return
  }
  parseLoading.value = true
  try {
    const r = await client.post('/fee/parse', { text })
    if (!r.data?.success) {
      ElMessage.error(r.data?.error || '识别失败')
      return
    }
    const d = r.data
    if (d.mode) feeForm.value.mode = d.mode
    if (d.order_no) feeForm.value.order_no = d.order_no
    feeRows.value = (d.rows && d.rows.length ? d.rows : [{}]).map((row) => ({
      recv_trader: row.recv_trader || '',
      recv_amount: row.recv_amount || '',
      recv_qty: row.recv_qty || '',
      recv_price: row.recv_price || '',
      pay_trader: row.pay_trader || '',
      pay_amount: row.pay_amount || '',
      pay_qty: row.pay_qty || '',
      pay_price: row.pay_price || '',
    }))
    ElMessage.success(d.summary ? `已识别 ${d.rows.length} 条：${d.summary}` : `已识别 ${d.rows.length} 条费用`)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message || '识别失败')
  } finally {
    parseLoading.value = false
  }
}

// 费用多行 → merged 契约（agent 逐行填佰信应收/应付网格）
function buildFeeMerged() {
  const rows = feeRows.value
    .map((r) => {
      const row = {}
      for (const k of ['recv_trader', 'recv_amount', 'recv_qty', 'recv_price', 'pay_trader', 'pay_amount', 'pay_qty', 'pay_price']) {
        const v = r[k]?.trim()
        if (v) row[k] = v
      }
      return row
    })
    .filter((r) => Object.keys(r).length > 0)
  return { rows }
}

async function runFeeFill() {
  const f = feeForm.value
  if (!f.order_no?.trim()) {
    ElMessage.warning('请填写工作号（佰信检索值 SB-…）')
    return
  }
  const no = f.order_no.trim()
  // 模式与单号前缀一致性：agent 端也按前缀推断模式，不一致会填错窗口
  if (f.mode === 'air' && !no.toUpperCase().startsWith('SB-A')) {
    ElMessage.warning('模式选了空运，但工作号不以 SB-A 开头，请核对（空运=SB-A…）')
    return
  }
  if (f.mode === 'sea' && no.toUpperCase().startsWith('SB-A')) {
    ElMessage.warning('模式选了海运，但工作号以 SB-A 开头（SB-A 是空运单号），请核对')
    return
  }
  if (!feeRowCount.value) {
    ElMessage.warning('请至少填写一行费用（应收或应付）')
    return
  }
  const merged = buildFeeMerged()
  feeRunning.value = true
  feeLogs.value = []
  feeDone.value = null
  try {
    await runAgentSSE({
      run_mode: 'fee',
      order_no: no,
      container_no: '',
      merged,
      provenance: { source: 'merge_fill_fee', mode: f.mode },
    }, feeLogs, feeDone)
  } catch (e) {
    feeDone.value = { success: false, message: e.message }
    ElMessage.error(e.message)
  } finally {
    feeRunning.value = false
  }
}

onMounted(async () => {
  // 从 RpaTasks 嵌入跳转预填
  if (route.query.container_no) form.value.container_no = route.query.container_no
  if (route.query.booking_no) form.value.booking_no = route.query.booking_no
  // 载入已上传文档供复用
  try {
    const r = await client.get('/docs/files')
    if (r.data?.success) docOptions.value = r.data.files
  } catch {}
})
</script>

<style scoped>
.merge-fill {
  padding: 4px;
}
.input-card,
.preview-card,
.result-card,
.fee-card {
  margin-bottom: 14px;
}
.cell-empty {
  color: #c0c4cc;
}
.merged-cell {
  font-weight: 600;
}
.baixin-log-box {
  margin-top: 8px;
  background: #1d1e1f;
  color: #00ff00;
  padding: 8px;
  border-radius: 4px;
  font-size: 12px;
  max-height: 250px;
  overflow-y: auto;
  font-family: 'Courier New', monospace;
  line-height: 1.6;
}
</style>
