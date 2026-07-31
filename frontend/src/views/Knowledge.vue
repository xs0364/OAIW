<template>
  <div class="knowledge-page">
    <!-- ===== 顶部统计栏 ===== -->
    <div class="stats-row">
      <div class="stat-card stat-docs">
        <div class="stat-icon"><el-icon :size="22"><Document /></el-icon></div>
        <div>
          <div class="stat-value">{{ stats.documents }}</div>
          <div class="stat-label">文档</div>
        </div>
      </div>
      <div class="stat-card stat-chunks">
        <div class="stat-icon"><el-icon :size="22"><Reading /></el-icon></div>
        <div>
          <div class="stat-value">{{ stats.chunks }}</div>
          <div class="stat-label">知识片段</div>
        </div>
      </div>
      <div class="stat-card stat-sources" style="flex:1;min-width:0">
        <div style="display:flex;align-items:center;gap:8px;width:100%">
          <el-icon :size="22" color="#909399"><FolderOpened /></el-icon>
          <span class="stat-label" style="margin:0;white-space:nowrap">来源：</span>
          <div style="display:flex;gap:4px;flex-wrap:wrap;overflow:hidden">
            <el-tag v-for="s in stats.sources" :key="s" size="small" effect="plain" style="border-color:#d9ecff;color:#409eff;background:#ecf5ff">
              {{ s }}
            </el-tag>
            <span v-if="!stats.sources.length" style="font-size:13px;color:#999">暂无</span>
          </div>
        </div>
      </div>
    </div>

    <!-- ===== 主区域 ===== -->
    <div class="main-area">
      <!-- 左侧主区 -->
      <div class="main-content">
        <!-- 搜索栏 -->
        <div class="search-box">
          <el-input
            v-model="searchQuery"
            placeholder="搜索知识库内容，例如「空运操作流程」「码头网址」..."
            size="large"
            clearable
            @keydown.enter="doSearch"
          >
            <template #prefix>
              <el-icon color="#909399"><Search /></el-icon>
            </template>
            <template #append>
              <el-button @click="doSearch" :loading="searching" style="padding:0 24px">搜索</el-button>
            </template>
          </el-input>
          <div class="search-hints">
            <span v-for="hint in hints" :key="hint" class="hint-tag" @click="quickSearch(hint)">{{ hint }}</span>
          </div>
        </div>

        <!-- 搜索结果 -->
        <transition name="fade" mode="out-in">
          <!-- 有结果 -->
          <div v-if="searchResults.length > 0" key="results" class="results-area">
            <div class="results-header">
              <span class="results-count">共 {{ searchResults.length }} 个结果</span>
              <el-button text size="small" @click="searchResults = []; searched = false" style="color:#909399">清除</el-button>
            </div>
            <div class="results-list">
              <div v-for="(r, i) in searchResults" :key="i" class="result-card">
                <div class="result-source">
                  <el-icon color="#409eff" :size="15"><Document /></el-icon>
                  <span class="result-source-name">{{ r.source }}</span>
                  <el-tag size="small" effect="plain" style="border:none;background:#f0f9eb;color:#67c23a;padding:0 6px;font-size:11px">{{ r.chunk }}</el-tag>
                  <el-tag size="small" effect="plain" style="border:none;background:#fef0f0;color:#f56c6c;padding:0 6px;font-size:11px">{{ (r.score * 100).toFixed(0) }}%</el-tag>
                </div>
                <div class="result-text">{{ r.content }}</div>
              </div>
            </div>
          </div>

          <!-- 搜不到 -->
          <div v-else-if="searched && !searching" key="noresult" class="empty-area">
            <el-icon :size="48" color="#dcdfe6"><Search /></el-icon>
            <p>没有找到相关内容，换个关键词试试</p>
          </div>

          <!-- 初始状态：展示已有文档 -->
          <div v-else key="initial" class="empty-area">
            <div class="browse-title">知识库文档</div>
            <div class="doc-grid">
              <div v-for="doc in docs" :key="doc.filename" class="doc-card" @click="quickSearch(doc.filename)">
                <div class="doc-icon">
                  <el-icon :size="32" color="#409eff"><Document /></el-icon>
                </div>
                <div class="doc-card-name">{{ doc.filename }}</div>
                <div class="doc-card-meta">{{ doc.chunks }} 个片段</div>
              </div>
              <div v-if="docs.length === 0 && !loading" class="doc-card doc-card-empty">
                <el-icon :size="32" color="#c0c4cc"><UploadFilled /></el-icon>
                <div style="margin-top:8px;color:#909399;font-size:13px">上传文档到知识库</div>
              </div>
            </div>
          </div>
        </transition>
      </div>

      <!-- 右侧边栏 -->
      <div class="main-sidebar">
        <!-- 上传 -->
        <div class="sidebar-section">
          <div class="sidebar-section-title">上传文档</div>
          <el-upload
            drag
            :action="uploadUrl"
            :headers="uploadHeaders"
            :on-success="handleUploadSuccess"
            :on-error="handleUploadError"
            :before-upload="beforeUpload"
            multiple
            class="upload-area"
          >
            <el-icon class="el-icon--upload" :size="36" color="#c0c4cc"><UploadFilled /></el-icon>
            <div style="font-size:13px;color:#606266;margin-top:4px">拖拽或<em style="color:#409eff">点击上传</em></div>
          </el-upload>
          <div class="upload-tip">支持 PDF / DOCX / XLSX / 图片 / TXT</div>
        </div>

        <!-- 文档列表 -->
        <div class="sidebar-section">
          <div class="sidebar-section-title">
            <span>文档列表</span>
            <el-button text size="small" @click="loadDocs" :loading="loading" style="color:#909399">
              <el-icon><Refresh /></el-icon>
            </el-button>
          </div>
          <div v-if="loading" style="text-align:center;padding:24px">
            <el-icon class="is-loading" :size="20"><Loading /></el-icon>
          </div>
          <div v-else-if="docs.length === 0" class="sidebar-empty">暂无文档</div>
          <div v-else class="sidebar-doc-list">
            <div v-for="doc in docs" :key="doc.filename" class="sidebar-doc-item" @click="quickSearch(doc.filename)">
              <div class="sidebar-doc-left">
                <el-icon color="#409eff"><Document /></el-icon>
                <span class="sidebar-doc-name">{{ doc.filename }}</span>
              </div>
              <div class="sidebar-doc-right">
                <span class="sidebar-doc-chunks">{{ doc.chunks }}</span>
                <el-popconfirm title="确认删除？" @confirm="deleteDoc(doc)">
                  <template #reference>
                    <el-button text size="small" style="color:#c0c4cc;padding:0" @click.stop>
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
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  UploadFilled, Document, Search, Reading, FolderOpened,
  Refresh, Loading, Close,
} from '@element-plus/icons-vue'
import client from '../api/client'

const hints = ['空运操作流程', '码头网址', '整柜Flying', '非危保函', '海运散货']

const searchQuery = ref('')
const searchResults = ref([])
const searching = ref(false)
const searched = ref(false)

const stats = ref({ chunks: 0, documents: 0, sources: [] })
const docs = ref([])
const loading = ref(false)

const uploadUrl = '/api/knowledge/upload'
const uploadHeaders = { Authorization: `Bearer ${localStorage.getItem('oaiw_token') || ''}` }

// === 搜索 ===
async function doSearch() {
  if (!searchQuery.value.trim()) {
    ElMessage.warning('请输入搜索关键词')
    return
  }
  searching.value = true
  searched.value = true
  try {
    const res = await client.post('/knowledge/search', {
      query: searchQuery.value.trim(),
      top_k: 20,
    })
    searchResults.value = (res.data.results || []).sort((a, b) => b.score - a.score)
  } catch (e) {
    ElMessage.error('搜索失败: ' + (e.response?.data?.error || e.message))
    searchResults.value = []
  } finally {
    searching.value = false
  }
}

function quickSearch(text) {
  searchQuery.value = text
  doSearch()
}

// === 统计 ===
async function loadStats() {
  try {
    const res = await client.get('/knowledge/stats')
    if (res.data.success) stats.value = res.data
  } catch { /* ignore */ }
}

// === 上传 ===
function handleUploadSuccess(res) {
  if (res.success) {
    ElMessage.success(`「${res.filename}」已解析为 ${res.chunks} 个知识片段`)
    loadStats()
    loadDocs()
  } else {
    ElMessage.error(res.error || '上传失败')
  }
}

function handleUploadError() {
  ElMessage.error('上传请求失败')
}

function beforeUpload(file) {
  const ext = file.name.split('.').pop().toLowerCase()
  const allowed = ['pdf', 'docx', 'doc', 'xlsx', 'xls', 'png', 'jpg', 'jpeg', 'txt']
  if (!allowed.includes(ext)) {
    ElMessage.error(`不支持 ${ext} 格式`)
    return false
  }
  return true
}

// === 文档列表 ===
async function loadDocs() {
  loading.value = true
  try {
    const res = await client.post('/knowledge/search', { query: '', top_k: 50 })
    if (res.data.success && res.data.results) {
      const seen = {}
      res.data.results.forEach(item => {
        if (!seen[item.source]) {
          seen[item.source] = { filename: item.source, chunks: 1 }
        } else {
          seen[item.source].chunks++
        }
      })
      docs.value = Object.values(seen)
    } else {
      docs.value = []
    }
  } catch {
    docs.value = []
  } finally {
    loading.value = false
  }
}

async function deleteDoc(doc) {
  try {
    const r = await client.post('/knowledge/search', { query: doc.filename, top_k: 1 })
    if (!r.data.success || !r.data.results?.length) {
      ElMessage.warning('未找到该文档')
      return
    }
    const docId = r.data.results[0].doc_id
    const r2 = await client.delete(`/knowledge/${docId}`)
    if (r2.data.success) {
      ElMessage.success(`已删除 ${doc.filename}`)
      loadStats(); loadDocs()
      searchResults.value = searchResults.value.filter(s => s.source !== doc.filename)
    }
  } catch {
    ElMessage.error('删除失败')
  }
}

onMounted(() => {
  loadStats(); loadDocs()
})
</script>

<style scoped>
.knowledge-page {
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
.stat-docs { min-width: 130px; }
.stat-chunks { min-width: 130px; }
.stat-icon {
  width: 44px; height: 44px;
  display: flex; align-items: center; justify-content: center;
  border-radius: 10px;
}
.stat-docs .stat-icon { background: #ecf5ff; }
.stat-chunks .stat-icon { background: #f0f9eb; }
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
}
.main-sidebar {
  width: 280px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
}

/* ===== 搜索 ===== */
.search-box {
  flex-shrink: 0;
}
.search-hints {
  display: flex;
  gap: 8px;
  margin-top: 8px;
  flex-wrap: wrap;
}
.hint-tag {
  font-size: 12px;
  color: #909399;
  cursor: pointer;
  padding: 2px 10px;
  border-radius: 12px;
  background: #f5f7fa;
  transition: all .2s;
}
.hint-tag:hover {
  background: #ecf5ff;
  color: #409eff;
}

/* ===== 结果区域 ===== */
.results-area {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding-top: 12px;
}
.results-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
  margin-bottom: 10px;
}
.results-count {
  font-size: 13px;
  color: #606266;
}
.results-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-right: 4px;
}
.result-card {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 10px;
  padding: 16px;
  transition: box-shadow .2s, border-color .2s;
}
.result-card:hover {
  border-color: #d9ecff;
  box-shadow: 0 2px 8px rgba(64,158,255,.08);
}
.result-source {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}
.result-source-name {
  font-size: 13px;
  font-weight: 500;
  color: #409eff;
}
.result-text {
  font-size: 13px;
  line-height: 1.75;
  color: #303133;
  white-space: pre-wrap;
  word-break: break-word;
}

/* ===== 空状态 / 初始页 ===== */
.empty-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #909399;
  padding: 20px 0;
}
.empty-area p {
  margin-top: 12px;
  font-size: 14px;
}
.browse-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 16px;
  align-self: flex-start;
}
.doc-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
  width: 100%;
}
.doc-card {
  border: 1px solid #ebeef5;
  border-radius: 10px;
  padding: 20px 16px;
  text-align: center;
  cursor: pointer;
  transition: border-color .2s, box-shadow .2s;
  background: #fff;
}
.doc-card:hover {
  border-color: #409eff;
  box-shadow: 0 2px 8px rgba(64,158,255,.1);
}
.doc-card-empty {
  cursor: default;
  border-style: dashed;
}
.doc-card-empty:hover {
  border-color: #dcdfe6;
  box-shadow: none;
}
.doc-card-name {
  margin-top: 8px;
  font-size: 13px;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.doc-card-meta {
  font-size: 12px;
  color: #c0c4cc;
  margin-top: 4px;
}

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
.upload-area {
  border: 1px dashed #dcdfe6;
  border-radius: 8px;
  padding: 16px 0;
  text-align: center;
}
.upload-area:hover {
  border-color: #409eff;
}
.upload-tip {
  font-size: 11px;
  color: #c0c4cc;
  margin-top: 8px;
  text-align: center;
}
.sidebar-empty {
  text-align: center;
  color: #c0c4cc;
  font-size: 13px;
  padding: 16px 0;
}
.sidebar-doc-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.sidebar-doc-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
  transition: background .15s;
}
.sidebar-doc-item:hover {
  background: #f5f7fa;
}
.sidebar-doc-left {
  display: flex;
  align-items: center;
  gap: 6px;
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
.sidebar-doc-right {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}
.sidebar-doc-chunks {
  font-size: 11px;
  color: #c0c4cc;
  background: #f5f7fa;
  padding: 1px 6px;
  border-radius: 8px;
}

/* ===== 过渡动画 ===== */
.fade-enter-active, .fade-leave-active { transition: opacity .18s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

/* ===== 滚动条 ===== */
.results-list::-webkit-scrollbar { width: 4px; }
.results-list::-webkit-scrollbar-thumb { background: #dcdfe6; border-radius: 4px; }
.main-sidebar::-webkit-scrollbar { width: 4px; }
.main-sidebar::-webkit-scrollbar-thumb { background: #dcdfe6; border-radius: 4px; }
</style>
