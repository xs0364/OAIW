<template>
  <div class="documents-page">
    <!-- ===== 统计栏 ===== -->
    <div class="stats-row">
      <div class="stat-card">
        <div class="stat-icon" style="background:#ecf5ff">
          <el-icon :size="22" color="#409eff"><Document /></el-icon>
        </div>
        <div>
          <div class="stat-value">{{ docs.length }}</div>
          <div class="stat-label">文档</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon" style="background:#fdf6ec">
          <el-icon :size="22" color="#e6a23c"><FolderOpened /></el-icon>
        </div>
        <div>
          <div class="stat-value">{{ totalSize }}</div>
          <div class="stat-label">总大小</div>
        </div>
      </div>
      <div class="stat-card" style="flex:1;min-width:0">
        <div style="display:flex;align-items:center;gap:8px;width:100%">
          <el-icon :size="22" color="#909399"><InfoFilled /></el-icon>
          <span style="font-size:13px;color:#909399">上传、预览和合并业务文档（箱单、发票、保函、舱单等）</span>
        </div>
      </div>
    </div>

    <!-- ===== 主区域 ===== -->
    <div class="main-area">
      <!-- 左侧主区 -->
      <div class="main-content">
        <!-- 上传 -->
        <div class="section-card">
          <div class="section-title">
            <span>上传文档</span>
            <el-tag size="small" effect="plain" style="border-color:#d9ecff;color:#409eff;background:#ecf5ff">
              PDF / DOCX / XLSX / 图片 / TXT
            </el-tag>
          </div>
          <el-upload
            ref="uploadRef"
            drag
            multiple
            :auto-upload="false"
            :file-list="fileList"
            @change="onFileChange"
            class="upload-box"
          >
            <el-icon :size="40" color="#c0c4cc"><UploadFilled /></el-icon>
            <div style="margin-top:6px;font-size:13px;color:#606266">
              拖拽文件到此处，或<em style="color:#409eff">点击选择</em>
            </div>
          </el-upload>
          <div v-if="fileList.length > 0" class="file-tags">
            <el-tag v-for="(f, i) in fileList" :key="i" closable @close="removeFile(i)" size="small" style="margin:0 6px 6px 0">
              {{ f.name }}
            </el-tag>
          </div>
          <el-button type="primary" :loading="uploading" :disabled="fileList.length === 0" @click="uploadAll" style="margin-top:4px">
            {{ uploading ? '上传中...' : `开始上传 (${fileList.length} 个文件)` }}
          </el-button>
        </div>

        <!-- 合并箱单发票 -->
        <div class="section-card">
          <div class="section-title"><span>合并箱单发票</span></div>
          <p style="font-size:13px;color:#909399;margin-bottom:12px">
            选择已上传的文档，合并为一份完整箱单发票
          </p>
          <div style="display:flex;gap:10px;align-items:center">
            <el-select v-model="mergeIds" multiple placeholder="选择要合并的文档" style="flex:1">
              <el-option v-for="d in docs" :key="d.file_id" :label="d.filename" :value="d.file_id" />
            </el-select>
            <el-button type="success" :disabled="mergeIds.length < 2" @click="mergeDocs" :loading="merging">合并</el-button>
          </div>
        </div>
      </div>

      <!-- 右侧：文档列表 -->
      <div class="main-sidebar">
        <div class="sidebar-section">
          <div class="sidebar-section-title">
            <span>已上传文档</span>
            <el-button text size="small" @click="loadDocs" style="color:#909399">
              <el-icon><Refresh /></el-icon>
            </el-button>
          </div>

          <div v-if="loading" style="text-align:center;padding:24px">
            <el-icon class="is-loading" :size="20"><Loading /></el-icon>
          </div>
          <div v-else-if="docs.length === 0" class="sidebar-empty">暂无文档</div>
          <div v-else class="sidebar-doc-list">
            <div v-for="doc in docs" :key="doc.file_id" class="sidebar-doc-item">
              <div class="sidebar-doc-left">
                <el-icon color="#409eff"><Document /></el-icon>
                <div class="sidebar-doc-info">
                  <div class="sidebar-doc-name">{{ rawFilename(doc.filename) }}</div>
                  <div class="sidebar-doc-meta">{{ (doc.size / 1024).toFixed(1) }} KB</div>
                </div>
              </div>
              <div class="sidebar-doc-actions">
                <el-button text size="small" @click="previewDoc(doc)" style="color:#409eff">预览</el-button>
                <el-popconfirm title="确认删除？" @confirm="deleteDoc(doc)">
                  <template #reference>
                    <el-button text size="small" style="color:#c0c4cc;padding:0">
                      <el-icon><Close /></el-icon>
                    </el-button>
                  </template>
                </el-popconfirm>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 预览对话框 -->
    <el-dialog v-model="showPreview" :title="'预览 — ' + (previewDocData?.filename || '')" width="700px">
      <div v-if="previewLoading" style="text-align:center;padding:40px">
        <el-icon class="is-loading" :size="24"><Loading /></el-icon>
      </div>
      <div v-else class="preview-box">{{ previewText || '(无文本内容)' }}</div>
      <template #footer>
        <el-button @click="showPreview = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 合并结果 -->
    <el-dialog v-model="showMerge" title="合并结果" width="700px">
      <p style="margin-bottom:12px;color:#67c23a" v-if="mergeResult">
        ✅ 成功合并 {{ mergeResult.file_count }} 个文件
      </p>
      <div class="preview-box">{{ mergeResult?.merged_text || '' }}</div>
      <template #footer>
        <el-button @click="showMerge = false">关闭</el-button>
        <el-button type="primary" @click="copyMerge">复制内容</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  UploadFilled, Document, FolderOpened, InfoFilled,
  Refresh, Loading, Close,
} from '@element-plus/icons-vue'
import client from '../api/client'

const uploadRef = ref(null)
const fileList = ref([])
const uploading = ref(false)
const docs = ref([])
const loading = ref(false)
const mergeIds = ref([])
const merging = ref(false)
const showPreview = ref(false)
const showMerge = ref(false)
const previewDocData = ref(null)
const previewText = ref('')
const previewLoading = ref(false)
const mergeResult = ref(null)

const totalSize = computed(() => {
  const total = docs.value.reduce((s, d) => s + d.size, 0)
  if (total < 1024) return total + ' B'
  if (total < 1024 * 1024) return (total / 1024).toFixed(1) + ' KB'
  return (total / 1024 / 1024).toFixed(1) + ' MB'
})

function rawFilename(fname) {
  // strip UUID prefix: "uuid-ext" -> show original
  const parts = fname.split('-')
  if (parts.length > 1 && parts[0].length === 36) {
    return fname.substring(37) || fname
  }
  return fname
}

function onFileChange(file) {
  if (!fileList.value.find(f => f.name === file.name && f.size === file.size)) {
    fileList.value.push(file)
  }
}

function removeFile(index) {
  fileList.value.splice(index, 1)
}

async function uploadAll() {
  uploading.value = true
  for (const f of fileList.value) {
    try {
      const formData = new FormData()
      formData.append('file', f.raw || f)
      const res = await client.post('/docs/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 120000,
      })
      if (res.data.success) {
        ElMessage.success(`${res.data.filename} 上传成功`)
      }
    } catch (e) {
      ElMessage.error(`${f.name} 上传失败: ${e.message}`)
    }
  }
  fileList.value = []
  uploading.value = false
  loadDocs()
}

async function previewDoc(doc) {
  previewDocData.value = doc
  previewText.value = ''
  previewLoading.value = true
  showPreview.value = true
  try {
    const res = await client.get(`/docs/files/${doc.file_id}`)
    previewText.value = res.data.text_preview || '(文档内容不可预览)'
  } catch {
    previewText.value = '(预览加载失败)'
  } finally {
    previewLoading.value = false
  }
}

async function loadDocs() {
  loading.value = true
  try {
    const res = await client.get('/docs/files')
    docs.value = res.data.files || []
  } catch {
    docs.value = []
  } finally {
    loading.value = false
  }
}

async function deleteDoc(doc) {
  try {
    const res = await client.delete(`/docs/files/${doc.file_id}`)
    if (res.data.success) {
      ElMessage.success(`已删除 ${doc.filename}`)
      loadDocs()
    }
  } catch {
    ElMessage.error('删除失败')
  }
}

async function mergeDocs() {
  merging.value = true
  try {
    const res = await client.post('/docs/merge-invoices', { doc_ids: mergeIds.value })
    if (res.data.success) {
      mergeResult.value = res.data
      showMerge.value = true
    }
  } catch (e) {
    ElMessage.error('合并失败: ' + e.message)
  } finally {
    merging.value = false
  }
}

function copyMerge() {
  if (mergeResult.value?.merged_text) {
    navigator.clipboard.writeText(mergeResult.value.merged_text).then(() => {
      ElMessage.success('已复制到剪贴板')
    })
  }
}

onMounted(() => {
  loadDocs()
})
</script>

<style scoped>
.documents-page {
  height: calc(100vh - 100px);
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* ===== 统计栏 ===== */
.stats-row {
  display: flex;
  gap: 12px;
  flex-shrink: 0;
}
.stat-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 20px;
  border-radius: 10px;
  background: #fff;
  border: 1px solid #ebeef5;
}
.stat-card:first-child { min-width: 130px; }
.stat-card:nth-child(2) { min-width: 130px; }
.stat-icon {
  width: 44px; height: 44px;
  display: flex; align-items: center; justify-content: center;
  border-radius: 10px;
}
.stat-value { font-size: 24px; font-weight: 700; color: #303133; line-height: 1.2; }
.stat-label { font-size: 13px; color: #909399; margin-top: 2px; }

/* ===== 主区域 ===== */
.main-area {
  display: flex;
  gap: 16px;
  flex: 1;
  min-height: 0;
}
.main-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.main-sidebar {
  width: 300px;
  flex-shrink: 0;
}

/* ===== 区域卡片 ===== */
.section-card {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 10px;
  padding: 18px;
}
.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 14px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.upload-box {
  border: 1px dashed #dcdfe6;
  border-radius: 8px;
  padding: 24px 0;
  text-align: center;
}
.upload-box:hover { border-color: #409eff; }
.file-tags { margin-top: 12px; }

/* ===== 侧边栏 ===== */
.sidebar-section {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 10px;
  padding: 16px;
}
.sidebar-section-title {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.sidebar-empty {
  text-align: center;
  color: #c0c4cc;
  font-size: 13px;
  padding: 24px 0;
}
.sidebar-doc-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.sidebar-doc-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 10px;
  border-radius: 6px;
}
.sidebar-doc-item:hover { background: #f5f7fa; }
.sidebar-doc-left {
  display: flex;
  align-items: center;
  gap: 8px;
  overflow: hidden;
  flex: 1;
}
.sidebar-doc-info {
  overflow: hidden;
  flex: 1;
}
.sidebar-doc-name {
  font-size: 12px;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sidebar-doc-meta {
  font-size: 11px;
  color: #c0c4cc;
  margin-top: 1px;
}
.sidebar-doc-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
}

/* ===== 预览 ===== */
.preview-box {
  background: #f5f7fa;
  padding: 16px;
  border-radius: 6px;
  max-height: 500px;
  overflow-y: auto;
  white-space: pre-wrap;
  font-size: 13px;
  line-height: 1.7;
}
</style>
