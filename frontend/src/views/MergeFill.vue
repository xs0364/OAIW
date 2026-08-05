<template>
  <div class="merge-fill">
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
          <el-input v-model="form.order_no" placeholder="佰信检索值 SB-…（选填）" style="width: 190px" />
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
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import client from '../api/client'

const route = useRoute()
const form = ref({ container_no: '', booking_no: '', order_no: '' })
const fileList = ref([])
const uploadRef = ref()
const selectedDocIds = ref([])
const docOptions = ref([])

const previewLoading = ref(false)
const confirmLoading = ref(false)
const preview = ref(null)
const confirmResult = ref(null)

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
.result-card {
  margin-bottom: 14px;
}
.cell-empty {
  color: #c0c4cc;
}
.merged-cell {
  font-weight: 600;
}
</style>
