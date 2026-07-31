<template>
  <div class="chat-container">
    <!-- 侧边栏 -->
    <div class="chat-sidebar">
      <el-input v-model="searchText" placeholder="搜索对话..." size="small" clearable style="margin-bottom: 10px" />
      <el-button type="primary" style="width: 100%; margin-bottom: 10px" @click="newChat">+ 新对话</el-button>

      <div style="margin-bottom: 10px">
        <div style="font-size: 12px; color: #909399; margin-bottom: 4px">AI 引擎</div>
        <el-select v-model="agentMode" size="small" style="width: 100%" @change="onAgentModeChange">
          <el-option label="🤖 自动路由 (推荐)" value="auto" />
          <el-option v-for="a in agentOptions" :key="a.name" :label="a.emoji + ' ' + a.display_name" :value="a.name" />
          <el-option label="🔥 一呼百应 (协作模式)" value="collaborate" />
        </el-select>
      </div>

      <!-- Agent状态 -->
      <div style="margin-bottom: 10px; padding: 8px; background: #f5f7fa; border-radius: 6px; font-size: 12px">
        <div v-for="a in agentStatus" :key="a.name" style="display: flex; justify-content: space-between; padding: 2px 0">
          <span>{{ a.display }}</span>
          <el-tag :type="a.online ? 'success' : 'danger'" size="small" style="height: 20px">
            {{ a.online ? '在线' : '未配置' }}
          </el-tag>
        </div>
      </div>

      <div class="chat-list">
        <div v-for="c in conversations" :key="c.id" class="chat-item" :class="{ active: c.id === activeConvId }" @click="switchConv(c.id)">
          <div class="chat-item-title">{{ c.title }}</div>
          <div class="chat-item-info">
            <span class="chat-item-time">{{ formatTime(c.updated_at) }}</span>
            <el-button text size="small" style="color: #c0c4cc; padding: 0 4px" @click.stop="deleteConv(c.id)">×</el-button>
          </div>
        </div>
      </div>
      <div v-if="conversations.length === 0" style="text-align: center; color: #909399; padding: 20px; font-size: 13px">
        暂无对话记录
      </div>
    </div>

    <!-- 主聊天区 -->
    <div class="chat-main">
      <div class="chat-header" v-if="currentAgentLabel">
        <el-tag type="primary" size="small">
          {{ currentAgentLabel }}
        </el-tag>
        <span v-if="activeConvId" style="font-size: 12px; color: #909399; margin-left: 8px">
          {{ messageCount }} 条消息
        </span>
      </div>

      <div class="chat-messages" ref="msgRef">
        <div v-for="(msg, i) in messages" :key="i" class="msg-row" :class="msg.role">
          <div class="msg-bubble-wrap" :class="msg.role">
            <div class="msg-name-bar">
              <span class="msg-label" v-if="msg.role !== 'user'">{{ msg.agentLabel || 'AI助手' }}</span>
              <span class="msg-time">{{ formatTime(msg.created_at) || '' }}</span>
            </div>
            <div class="msg-bubble" :class="msg.role">
              <div v-if="editingMsgIndex !== i">
                <div v-if="thinking && msg.role === 'assistant' && !msg.content" class="thinking-indicator">
                  <span class="thinking-dots"><span class="dot">.</span><span class="dot">.</span><span class="dot">.</span></span>
                </div>
                <div v-else class="msg-text" v-html="renderMarkdown(msg.content)"></div>
              </div>
              <div v-else class="msg-edit-area">
                <el-input v-model="editingText" type="textarea" :rows="3" />
                <div class="msg-edit-actions" style="margin-top: 8px; display: flex; gap: 8px; justify-content: flex-end">
                  <el-button size="small" type="primary" @click="saveEdit(i)">保存</el-button>
                  <el-button size="small" @click="cancelEdit">取消</el-button>
                </div>
              </div>
            </div>
            <div v-if="editingMsgIndex !== i" class="msg-actions">
              <button class="msg-action-btn" @click="copyMsg(msg.content)" title="复制">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
              </button>
              <button v-if="msg.role === 'assistant'" class="msg-action-btn" @click="regenerateMsg(i)" title="重新生成">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
              </button>
              <button v-if="msg.role === 'user'" class="msg-action-btn" @click="startEdit(i)" title="编辑">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
              </button>
              <button class="msg-action-btn" @click="deleteMsg(i)" title="删除">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
              </button>
            </div>
          </div>
        </div>

        <!-- 一呼百应结果 -->
        <div v-if="collaborateResult" class="collaborate-section">
          <div class="collaborate-main">
            <div class="collaborate-title">📋 综合AI分析</div>
            <div class="collaborate-content" v-html="renderMarkdown(collaborateResult.synthesized)"></div>
            <div style="margin-top: 8px">
              <el-button text size="small" @click="showRawContributions = !showRawContributions" style="color: #909399">
                {{ showRawContributions ? '收起' : '展开' }}各Agent原始分析
              </el-button>
            </div>
          </div>
          <div v-if="showRawContributions" class="collaborate-detail">
            <div v-for="(contrib, name) in collaborateResult.contributions" :key="name" class="parallel-card">
              <div class="parallel-header">
                <el-tag :type="tagColorMap[name] || 'info'" size="small">{{ contrib.agent }}</el-tag>
                <span style="font-size: 11px; color: #909399; margin-left: 6px">{{ contrib.model }}</span>
              </div>
              <div class="parallel-content" v-html="renderMarkdown(contrib.content)"></div>
            </div>
          </div>
        </div>

        <!-- 流式生成中的状态提示（显示在消息流末尾） -->
        <div v-if="loading && messages.length === 0" class="msg-row assistant">
          <div class="msg-bubble-wrap assistant">
            <span class="thinking-dots"><span class="dot">.</span><span class="dot">.</span><span class="dot">.</span></span>
            <span v-if="streamingContent" style="font-size:12px;color:#909399;margin-top:4px">{{ streamingContent }}</span>
          </div>
        </div>
      </div>

      <!-- 文件上下文栏 -->
      <div class="file-context-bar" v-if="fileContexts.length > 0">
        <div class="file-context-tags">
          <div v-for="(fc, i) in fileContexts" :key="fc.file_id" class="file-context-tag" :title="fc.text_preview">
            <span class="file-icon">{{ getFileIcon(fc.ext) }}</span>
            <span class="file-name">{{ fc.filename }}</span>
            <span class="file-size">{{ formatFileSize(fc.file_size) }}</span>
            <el-button text size="small" class="file-remove-btn" @click.stop="removeFileContext(i)">×</el-button>
          </div>
        </div>
      </div>

      <div class="chat-input-area"
        @dragover.prevent="onDragOver"
        @dragleave.prevent="onDragLeave"
        @drop.prevent="onDrop"
        :class="{ 'drag-over': dragOver }">
        <div v-if="dragOver" class="drag-overlay">
          <span class="drag-overlay-text">释放以上传文件到对话上下文</span>
        </div>

        <div class="input-wrapper">
          <button class="input-file-btn" @click="openFilePicker" title="上传文件到上下文">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>
          </button>
          <input ref="fileInputRef" type="file" style="display:none"
            accept=".pdf,.docx,.xlsx,.txt,.png,.jpg,.jpeg"
            @change="handleFileSelect" />

          <textarea v-model="inputText" class="input-textarea"
            placeholder="输入您的问题..."
            rows="3"
            @keydown.enter.exact.prevent="sendMessage"></textarea>

          <button v-if="!loading" class="input-send-btn" @click="sendMessage" title="发送">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
          </button>
          <button v-else class="input-send-btn stop-btn-icon" @click="stopGeneration" title="停止生成">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>
          </button>
        </div>

        <div class="chat-actions">
          <div class="action-hints">
            <el-tag size="small" @click="quickAsk('查码头状态')" style="cursor:pointer">查码头状态</el-tag>
            <el-tag size="small" @click="quickAsk('查船司运价')" style="cursor:pointer">查船司运价</el-tag>
            <el-tag size="small" @click="quickAsk('生成非危保函')" style="cursor:pointer">生成非危保函</el-tag>
            <el-tag size="small" @click="quickAsk('合并箱单发票')" style="cursor:pointer">合并箱单</el-tag>
          </div>
          <div style="display:flex;gap:8px;align-items:center">
            <span v-if="agentMode === 'collaborate'" style="font-size:12px;color:#e6a23c">🔥 4 Agent 一呼百应</span>
            <span style="font-size:11px;color:#c0c4cc">Ctrl+Enter 发送</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted } from 'vue'
import hljs from 'highlight.js/lib/common'
import 'highlight.js/styles/github.css'
import { marked } from 'marked'
import { ElMessage } from 'element-plus'
import { DocumentCopy, RefreshRight, EditPen, Delete } from '@element-plus/icons-vue'
import client from '../api/client'
import axios from 'axios'

const searchText = ref('')
const inputText = ref('')
const loading = ref(false)
const activeConvId = ref(null)
const msgRef = ref(null)
const agentMode = ref('auto')
const agentStatus = ref([])
const collaborateResult = ref(null)
const showRawContributions = ref(false)
const messageCount = ref(0)
const streamingContent = ref('')
const thinking = ref(false)
const editingMsgIndex = ref(-1)
const editingText = ref('')
const abortController = ref(null)

const agentOptions = ref([])
const conversations = ref([])
const messages = ref([])

// ===== 文件上下文 =====
const fileContexts = ref([])
const fileInputRef = ref(null)
const dragOver = ref(false)

const currentAgentLabel = computed(() => {
  if (agentMode.value === 'auto') return '🤖 自动路由'
  if (agentMode.value === 'collaborate') return '🔥 一呼百应 (协作模式)'
  const a = agentOptions.value.find(o => o.name === agentMode.value)
  return a ? a.emoji + ' ' + a.display_name : agentMode.value
})

function getFileIcon(ext) {
  const icons = {
    '.pdf': '📄',
    '.docx': '📝',
    '.xlsx': '📊',
    '.txt': '📃',
    '.png': '🖼️',
    '.jpg': '🖼️',
    '.jpeg': '🖼️',
  }
  return icons[ext] || '📎'
}

function formatFileSize(bytes) {
  if (!bytes) return ''
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function openFilePicker() {
  fileInputRef.value?.click()
}

async function handleFileSelect(e) {
  const files = e.target.files
  if (!files || files.length === 0) return
  await uploadAndAddFiles(Array.from(files))
  e.target.value = ''
}

function onDragOver() {
  dragOver.value = true
}

function onDragLeave() {
  dragOver.value = false
}

async function onDrop(e) {
  dragOver.value = false
  const files = e.dataTransfer?.files
  if (!files || files.length === 0) return
  await uploadAndAddFiles(Array.from(files))
}

async function uploadAndAddFiles(files) {
  if (!activeConvId.value) {
    ElMessage.warning('请先创建或选择一个对话')
    return
  }

  for (const file of files) {
    if (fileContexts.value.some(fc => fc.filename === file.name)) {
      ElMessage.info(`文件 "${file.name}" 已在上下文中`)
      continue
    }

    const formData = new FormData()
    formData.append('file', file)
    formData.append('conversation_id', String(activeConvId.value))

    try {
      const res = await axios.post('/api/chat/upload-context-file', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      if (res.data.success) {
        fileContexts.value.push({
          file_id: res.data.file_id,
          filename: res.data.filename,
          file_size: res.data.file_size,
          ext: res.data.ext,
          text_preview: res.data.text_preview,
          text: res.data.text,
        })
        ElMessage.success(`已添加: ${res.data.filename}`)
      } else {
        ElMessage.error(res.data.error || '上传失败')
      }
    } catch (e) {
      ElMessage.error(`上传失败: ${e.response?.data?.error || e.message}`)
    }
  }
}

function removeFileContext(index) {
  fileContexts.value.splice(index, 1)
}

const tagColorMap = {
  nim_minimax: 'success',
  nim_gpt: 'primary',
  nim_qwen: 'warning',
  nim_deepseek: 'danger',
}

// ── Markdown renderer: code highlighting + enhanced rendering ──
let _mdCodeId = 0
function _esc(str) {
  return String(str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}

window._copyCode = function (id) {
  const el = document.getElementById(id)
  if (!el) return
  navigator.clipboard.writeText(el.textContent || '').catch(() => {})
  const btn = document.querySelector(`[data-copy="${id}"]`)
  if (btn) {
    btn.textContent = 'Copied!'
    setTimeout(() => { btn.textContent = 'Copy' }, 2000)
  }
}

marked.use({
  renderer: {
    code({ text, lang }) {
      const id = `cb-${++_mdCodeId}`
      const hasLang = lang && hljs.getLanguage(lang)
      let highlighted
      try {
        highlighted = hasLang
          ? hljs.highlight(text, { language: lang, ignoreIllegals: true }).value
          : hljs.highlightAuto(text).value
      } catch {
        highlighted = _esc(text)
      }
      const langLabel = hasLang ? `<span class="code-lang">${_esc(lang)}</span>` : ''
      return `<div class="code-block">
        <div class="code-header">
          ${langLabel}
          <button class="code-copy-btn" data-copy="${id}" onclick="window._copyCode('${id}')">Copy</button>
        </div>
        <pre><code id="${id}" class="hljs${hasLang ? ` language-${_esc(lang)}` : ''}">${highlighted}</code></pre>
      </div>`
    },
    link({ href, title, text }) {
      const isExternal = href && (href.startsWith('http://') || href.startsWith('https://'))
      const target = isExternal ? ' target="_blank" rel="noopener noreferrer"' : ''
      const titleAttr = title ? ` title="${_esc(title)}"` : ''
      return `<a href="${_esc(href)}"${titleAttr}${target}>${text}</a>`
    },
    image({ href, title, text }) {
      const titleAttr = title ? ` title="${_esc(title)}"` : ''
      return `<img src="${_esc(href)}" alt="${_esc(text || '')}"${titleAttr} style="max-width:100%;height:auto" />`
    },
    listitem(item) {
      if (item.task) {
        const checked = item.checked ? 'checked' : ''
        let content
        try {
          content = this.parser.parseInline(item.tokens)
        } catch {
          content = _esc(item.text || '')
        }
        return `<li class="task-list-item"><input type="checkbox" ${checked} disabled> ${content}</li>`
      }
      return false
    },
  },
})


function renderMarkdown(text) {
  if (!text) return ''
  try {
    let html = marked.parse(text, { async: false })
    // 纯单行文本去掉 <p> 包裹，避免气泡内文字偏上
    html = html.replace(/^<p>([\s\S]*?)<\/p>\n?$/s, '$1')
    return html
  } catch (e) {
    console.warn('[Markdown] Parse error:', e)
    return _esc(text)
  }
}

function formatTime(t) {
  if (!t) return ''
  const d = new Date(t)
  const now = new Date()
  if (d.toDateString() === now.toDateString()) {
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
  return `${d.getMonth() + 1}/${d.getDate()}`
}

// 加载Agent状态 + 对话列表
onMounted(async () => {
  // 从 localStorage 恢复对话列表（防止 HMR 丢失 / 刷新后 API 不返回数据）
  _restoreConversations()

  try {
    const [agentRes, convRes] = await Promise.all([
      client.get('/chat/multi-agent/list').catch(() => ({ data: { agents: [] } })),
      client.get('/chat/conversations').catch(() => ({ data: null })),
    ])
    const agentList = agentRes.data.agents || []
    const emojis = ['⚡', '🌐', '🔧', '🧠', '🤖', '🔥', '💡', '⭐', '🎯', '📡']
    agentOptions.value = agentList.map((a, i) => ({
      ...a, emoji: emojis[i] || '🤖',
    }))
    agentStatus.value = agentList.map(a => ({
      name: a.name, display: a.display_name, online: a.configured,
    }))
    // 只有后端返回有效数据时才覆盖，避免空响应冲掉 localStorage 里的本地数据
    if (convRes.data?.conversations && convRes.data.conversations.length > 0) {
      conversations.value = convRes.data.conversations
      _saveConversations()
    }
    // API 返回空/无效时不覆盖 localStorage 中的缓存数据
  } catch { console.warn('[AgentChat] Failed to load initial data') }

  // 自动恢复上次打开的对话（固定 key，不依赖登录状态）
  try {
    const lastId = localStorage.getItem('oaiw_active_conv')
    if (lastId && conversations.value.some(c => String(c.id) === lastId)) {
      switchConv(Number(lastId))
    }
  } catch { /* ignore */ }
})

function _saveConversations() {
  try {
    const data = JSON.stringify(conversations.value)
    // 固定 key（主要）：永不依赖登录状态
    localStorage.setItem('oaiw_convs_list', data)
    // 用户隔离 key（辅助写入）：已登录用户多账号隔离用
    localStorage.setItem(_lsKey('convs'), data)
  } catch { /* ignore */ }
}

function _restoreConversations() {
  // 读取顺序：固定 key → 用户隔离 key → 兜底
  let data = localStorage.getItem('oaiw_convs_list')
  if (!data) data = localStorage.getItem(_lsKey('convs'))
  if (!data) data = localStorage.getItem('oaiw_convs_cache')
  if (!data) data = localStorage.getItem('oaiw_convs_fallback')
  // 扫所有 oaiw_convs_* key 找数据最多的
  if (!data) {
    let best = '', bestLen = 0
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i)
      if (k && k.startsWith('oaiw_convs_') && k !== 'oaiw_convs_list') {
        try {
          const v = localStorage.getItem(k)
          if (v && v.length > bestLen) { best = v; bestLen = v.length }
        } catch {}
      }
    }
    data = best
  }
  if (!data) return
  try { conversations.value = JSON.parse(data) } catch {}
}

// ===== 每对话消息缓存（固定 key，不依赖登录状态） =====
function _cacheMessages(convId, msgs) {
  try {
    localStorage.setItem(`oaiw_msgs_${convId}`, JSON.stringify(msgs))
  } catch { /* ignore */ }
}

function _loadCachedMessages(convId) {
  try {
    const data = localStorage.getItem(`oaiw_msgs_${convId}`)
    return data ? JSON.parse(data) : null
  } catch { return null }
}

function _lsKey(name) {
  // 每个用户独立 localStorage 前缀，防止多账号串数据
  let uid = 'anon'
  try {
    const u = JSON.parse(localStorage.getItem('oaiw_user') || '{}')
    if (u.id) uid = String(u.id)
  } catch {}
  return `oaiw_${name}_${uid}`
}

// 创建新对话
async function newChat() {
  try {
    const res = await client.post('/chat/conversations', {
      title: '新对话',
      agent_mode: agentMode.value,
    })
    if (res.data.success) {
      const c = res.data.conversation
      conversations.value.unshift(c)
      activeConvId.value = c.id
      messages.value = []
      messageCount.value = 0
      fileContexts.value = []
      _saveConversations()
    } else {
      // API 返回 success=false（如未登录）→ 走离线模式
      throw new Error(res.data.error || 'API refused')
    }
  } catch {
    // 离线模式
    activeConvId.value = "offline_" + Date.now()
    conversations.value.unshift({ id: activeConvId.value, title: '新对话', updated_at: new Date().toISOString() })
    messages.value = []
    messageCount.value = 0
    fileContexts.value = []
    _saveConversations()
  }
}

// 切换对话
async function switchConv(id) {
  activeConvId.value = id
  try { localStorage.setItem('oaiw_active_conv', String(id)) } catch {}
  fileContexts.value = []
  try {
    const res = await client.get(`/chat/conversations/${id}/messages`)
    if (res.data.success) {
      messages.value = res.data.messages || []
      messageCount.value = messages.value.length
      _cacheMessages(id, messages.value)
    } else {
      throw new Error(res.data.error || 'API refused')
    }
  } catch {
    // API 失败时尝试从 localStorage 读取缓存的消息
    const cached = _loadCachedMessages(id)
    if (cached) {
      messages.value = cached
      messageCount.value = cached.length
    } else {
      messages.value = []
      messageCount.value = 0
    }
  }
  scrollToBottom()
}

// 删除对话
async function deleteConv(id) {
  try {
    await client.delete(`/chat/conversations/${id}`)
    conversations.value = conversations.value.filter(c => c.id !== id)
    _saveConversations()
    if (activeConvId.value === id) {
      activeConvId.value = null
      messages.value = []
      messageCount.value = 0
      fileContexts.value = []
    }
  } catch {
    conversations.value = conversations.value.filter(c => c.id !== id)
    _saveConversations()
  }
}

// 保存消息到后端
async function saveMsg(role, content, extra = {}) {
  if (!activeConvId.value || typeof activeConvId.value !== 'number') return
  try {
    const res = await client.post(`/chat/conversations/${activeConvId.value}/messages`, {
      role,
      content,
      agent_name: extra.agent_name || '',
      agent_label: extra.agent_label || '',
      model_name: extra.model_name || '',
    })
    if (res.data.success && res.data.message?.id) {
      const last = messages.value[messages.value.length - 1]
      if (last && last.role === role && last.content === content) {
        last.id = res.data.message.id
      }
    }
    messageCount.value++
  } catch { /* 离线模式忽略 */ }
  // 每次写入消息后同步更新消息缓存
  _cacheMessages(activeConvId.value, messages.value)
}

// 更新对话标题（首条消息）
async function updateConvTitle(firstMsg) {
  if (!activeConvId.value || typeof activeConvId.value !== 'number') return
  const title = firstMsg.length > 30 ? firstMsg.slice(0, 30) + '...' : firstMsg
  try {
    await client.patch(`/chat/conversations/${activeConvId.value}`, { title })
    const conv = conversations.value.find(c => c.id === activeConvId.value)
    if (conv) { conv.title = title; _saveConversations() }
  } catch { /* ignore */ }
}

function onAgentModeChange() {
  let msg = ''
  if (agentMode.value === 'auto') {
    msg = '已切换到自动路由模式 — 根据问题类型自动选择Agent'
  } else if (agentMode.value === 'collaborate') {
    msg = '已切换到一呼百应模式 — 4个Agent协作分析，统一回复 🔥'
  } else {
    const a = agentOptions.value.find(o => o.name === agentMode.value)
    if (a) msg = '已切换到 ' + a.display_name + ' — ' + (a.description || '自定义模型')
  }
  if (msg && activeConvId.value) {
    messages.value.push({ role: 'assistant', content: msg, agentLabel: '系统' })
    saveMsg('assistant', msg, { agent_label: '系统' })
  }
}

function quickAsk(text) {
  inputText.value = text
  sendMessage()
}

async function sendMessage() {
  if (!inputText.value.trim()) return
  const userMsg = inputText.value.trim()
  inputText.value = ''

  if (!activeConvId.value) await newChat()
  const isFirstMsg = messages.value.length === 0

  messages.value.push({ role: 'user', content: userMsg })
  await saveMsg('user', userMsg)
  if (isFirstMsg) await updateConvTitle(userMsg)

  loading.value = true
  collaborateResult.value = null
  streamingContent.value = ''

  try {
    if (agentMode.value === 'collaborate') {
      await _handleCollaborateStream(userMsg)
    } else {
      await _handleSingle(userMsg)
    }
  } catch (e) {
    if (e.name === 'CanceledError' || e.code === 'ERR_CANCELED' || e.name === 'AbortError') {
      // 用户手动停止，不报错
    } else {
      messages.value.push({
        role: 'assistant', content: `⚠️ 请求失败: ${e.response?.data?.error || e.message}`,
        agentLabel: '系统',
      })
    }
  }

  loading.value = false
  scrollToBottom()
}

/** 一呼百应 — 所有Agent协作分析，合成统一回复 */
async function _handleCollaborate(userMsg) {
  const res = await client.post('/chat/multi-agent/collaborate', {
    message: userMsg, history: [], file_contexts: fileContexts.value,
  })
  if (res.data.success) {
    const cr = res.data
    collaborateResult.value = cr
    messages.value.push({
      role: 'assistant', content: cr.synthesized || '',
      agentLabel: '🔥 一呼百应',
    })
    await saveMsg('assistant', cr.synthesized || '', {
      agent_label: '一呼百应', model_name: cr.synthesizer || '',
    })
  }
}

/** 一呼百应 — SSE streaming 协作分析 */
async function _handleCollaborateStream(userMsg) {
  const token = localStorage.getItem('oaiw_token')
  abortController.value = new AbortController()
  try {
    const response = await fetch('/api/chat/multi-agent/collaborate/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        message: userMsg,
        history: _buildHistory(),
        file_contexts: fileContexts.value,
      }),
      signal: abortController.value.signal,
    })
    if (!response.ok) {
      throw new Error(`Stream request failed: ${response.status}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let lastAssistantIdx = -1

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const dataText = line.slice(6)
          if (dataText === '[DONE]') break
          try {
            const data = JSON.parse(dataText)
            const evtType = data.type || ''

            if (evtType === 'status') {
              if (data.phase === 'collecting') {
                streamingContent.value = '正在收集各Agent分析结果...'
              } else if (data.phase === 'synthesizing') {
                streamingContent.value = '正在综合汇总...'
                const idx = messages.value.length
                messages.value.push({
                  role: 'assistant',
                  content: '',
                  agentLabel: '🔥 一呼百应',
                })
                lastAssistantIdx = idx
              }
            } else if (evtType === 'synth') {
              if (lastAssistantIdx >= 0) {
                messages.value[lastAssistantIdx].content += data.content || ''
              }
            } else if (evtType === 'done') {
              const fullText = data.synthesized || ''
              if (lastAssistantIdx >= 0) {
                messages.value[lastAssistantIdx].content = fullText
              }
              collaborateResult.value = {
                synthesized: fullText,
                contributions: data.contributions || null,
                synthesizer: data.synthesizer || '',
              }
              await saveMsg('assistant', fullText, {
                agent_label: '一呼百应',
                model_name: data.synthesizer || '',
              })
              streamingContent.value = ''
              return
            }
          } catch (e) {
            console.warn('[SSE] parse error:', e, dataText)
          }
        }
      }
    }
  } catch (e) {
    if (e.name === 'AbortError') return
    throw e
  } finally {
    abortController.value = null
    thinking.value = false
  }
}

/** 单Agent模式 — SSE流式输出，支持打字机效果和停止 */
async function _handleSingle(userMsg) {
  const agentName = agentMode.value === 'auto' ? '' : agentMode.value
  const history = _buildHistory()

  // Push placeholder assistant message
  const msgIdx = messages.value.length
  thinking.value = true
  messages.value.push({
    role: 'assistant',
    content: '',
    agentLabel: 'AI助手',
  })

  const token = localStorage.getItem('oaiw_token')
  abortController.value = new AbortController()

  let fullContent = ''
  let agentInfo = {}

  try {
    const response = await fetch('/api/chat/multi-agent/send/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        message: userMsg,
        history,
        agent_name: agentName,
        file_contexts: fileContexts.value,
      }),
      signal: abortController.value.signal,
    })
    if (!response.ok) {
      throw new Error(`Stream request failed: ${response.status}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      // Process complete SSE lines
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const dataText = line.slice(6)
          if (dataText === '[DONE]') break
          try {
            const data = JSON.parse(dataText)
            const evtType = data.type || ''

            if (evtType === 'text') {
              fullContent += data.content || ''
              thinking.value = false
              messages.value[msgIdx].content = fullContent
              scrollToBottom()
            } else if (evtType === 'status') {
              if (data.phase === 'tool_calling') {
                messages.value[msgIdx].content = '🔍 正在查询...'
              } else if (data.phase === 'streaming') {
                messages.value[msgIdx].content = ''
              }
            } else if (evtType === 'done') {
              thinking.value = false; agentInfo = data
              messages.value[msgIdx].agentLabel = data.agent || 'AI助手'
              messages.value[msgIdx].model_name = data.model || ''
            } else if (evtType === 'error') {
              messages.value[msgIdx].content = `⚠️ ${data.content || '请求失败'}`
            }
          } catch (e) {
            console.warn('[SSE] parse error:', e, dataText)
          }
        }
      }
    }

    // Save message after stream completes
    if (fullContent) {
      await saveMsg('assistant', fullContent, {
        agent_name: agentInfo.agent_name || agentName || agentInfo.intent || '',
        agent_label: agentInfo.agent || 'AI助手',
        model_name: agentInfo.model || '',
      })
    }
  } catch (e) {
    if (e.name === 'AbortError') {
      // User stopped - save partial content
      if (messages.value[msgIdx]?.content) {
        await saveMsg('assistant', messages.value[msgIdx].content + '\n\n[已停止生成]', {
          agent_label: messages.value[msgIdx].agentLabel || 'AI助手',
        })
      }
    } else {
      // Replace placeholder with error
      messages.value[msgIdx].content = `⚠️ 请求失败: ${e.message}`
    }
  } finally {
    abortController.value = null
    thinking.value = false
  }
}

// ===== 消息操作 =====

function _buildHistory() {
  return messages.value.slice(0, -1).map(m => ({
    role: m.role,
    content: m.content,
  }))
}

function copyMsg(content) {
  navigator.clipboard.writeText(content).then(() => {
    ElMessage.success('已复制到剪贴板')
  }).catch(() => {
    ElMessage.error('复制失败')
  })
}

function startEdit(index) {
  editingMsgIndex.value = index
  editingText.value = messages.value[index].content
}

function cancelEdit() {
  editingMsgIndex.value = -1
  editingText.value = ''
}

async function saveEdit(index) {
  const newContent = editingText.value.trim()
  if (!newContent) return

  messages.value[index].content = newContent

  const removed = messages.value.splice(index + 1)

  if (activeConvId.value && typeof activeConvId.value === 'number') {
    for (const m of removed) {
      if (m.id) {
        try {
          await client.delete(`/chat/conversations/${activeConvId.value}/messages/${m.id}`)
        } catch { /* ignore */ }
      }
    }
  }

  editingMsgIndex.value = -1
  editingText.value = ''

  inputText.value = newContent
  await sendMessage()
}

async function regenerateMsg(index) {
  let userIdx = -1
  for (let i = index - 1; i >= 0; i--) {
    if (messages.value[i].role === 'user') {
      userIdx = i
      break
    }
  }
  if (userIdx === -1) return

  const userMsg = messages.value[userIdx].content
  const removed = messages.value.splice(userIdx)

  if (activeConvId.value && typeof activeConvId.value === 'number') {
    for (const m of removed) {
      if (m.id) {
        try {
          await client.delete(`/chat/conversations/${activeConvId.value}/messages/${m.id}`)
        } catch { /* ignore */ }
      }
    }
  }

  inputText.value = userMsg
  await sendMessage()
}

async function deleteMsg(index) {
  const msg = messages.value[index]
  messages.value.splice(index, 1)
  messageCount.value = Math.max(0, messageCount.value - 1)

  if (msg.id && activeConvId.value && typeof activeConvId.value === 'number') {
    try {
      await client.delete(`/chat/conversations/${activeConvId.value}/messages/${msg.id}`)
    } catch { /* ignore */ }
  }
}

function stopGeneration() {
  if (abortController.value) {
    abortController.value.abort()
    abortController.value = null
    thinking.value = false
  }
  loading.value = false
}

function scrollToBottom() {
  nextTick(() => {
    if (msgRef.value) msgRef.value.scrollTop = msgRef.value.scrollHeight
  })
}
</script>

<style scoped>
.chat-container { display: flex; height: calc(100vh - 120px); gap: 16px; }
.chat-sidebar { width: 240px; flex-shrink: 0; display: flex; flex-direction: column; }
.chat-list { flex: 1; overflow-y: auto; }
.chat-item { padding: 8px 12px; border-radius: 8px; cursor: pointer; margin-bottom: 4px; }
.chat-item:hover, .chat-item.active { background: #ecf5ff; }
.chat-item-title { font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.chat-item-info { display: flex; justify-content: space-between; align-items: center; }
.chat-item-time { font-size: 11px; color: #c0c4cc; margin-top: 2px; }
.chat-main { flex: 1; display: flex; flex-direction: column; background: #fff; border-radius: 8px; border: 1px solid #e4e7ed; }
.chat-header { padding: 10px 20px; border-bottom: 1px solid #e4e7ed; display: flex; align-items: center; gap: 8px; }
.chat-messages { flex: 1; overflow-y: auto; padding: 8px 16px; }
.msg-row { display: flex; margin-bottom: 4px; }
.msg-row.user { justify-content: flex-end; }

/* ── 气泡容器 ── */
.msg-bubble-wrap {
  max-width: 75%;
  display: flex;
  flex-direction: column;
}
.msg-bubble-wrap.user { align-items: flex-end; }

/* ── 名称栏 ── */
.msg-name-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 2px;
}
.msg-bubble-wrap.user .msg-name-bar {
  flex-direction: row-reverse;
}
.msg-label {
  font-size: 12px;
  font-weight: 500;
  color: #606266;
}
.msg-time {
  font-size: 11px;
  color: #c0c4cc;
}

/* ── 气泡本体 ── */
.msg-bubble {
  padding: 4px 12px;
  border-radius: 12px;
  position: relative;
  font-size: 14px;
  line-height: 1.35;
  white-space: pre-wrap;
  word-break: break-word;
}
/* 清除Markdown渲染的<p>标签默认边距，确保气泡内文字上下间距一致 */
.msg-text {
  line-height: inherit;
}
.msg-text :deep(p) {
  margin: 0;
  padding: 0;
  line-height: inherit;
}
/* user 气泡 */
.msg-bubble.user {
  background: #409eff;
  color: #fff;
  border-bottom-right-radius: 4px;
}
/* assistant 气泡 */
.msg-bubble.assistant {
  background: #fff;
  color: #303133;
  border: 1px solid #ebeef5;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  border-bottom-left-radius: 4px;
}
.msg-bubble.assistant::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: -8px;
  width: 0;
  height: 0;
  border-bottom: 8px solid #fff;
  border-left: 8px solid transparent;
}
.msg-bubble.assistant::before {
  content: '';
  position: absolute;
  bottom: -1px;
  left: -9px;
  width: 0;
  height: 0;
  border-bottom: 9px solid #ebeef5;
  border-left: 9px solid transparent;
  z-index: -1;
}

/* ── 编辑模式 ── */
.msg-edit-area :deep(.el-textarea__inner) {
  font-size: 14px;
  line-height: 1.6;
}

/* ── 操作栏（常显示，不闪）── */
.msg-actions {
  display: flex;
  gap: 4px;
  padding: 4px 4px 0;
  margin-top: 4px;
  border-top: 1px solid rgba(0,0,0,0.06);
  flex-wrap: wrap;
}
.msg-row.user .msg-actions {
  border-top-color: rgba(255,255,255,0.15);
  justify-content: flex-end;
}
.msg-row.user .msg-actions :deep(.el-button) {
  color: rgba(255,255,255,0.75);
}
.msg-row.user .msg-actions :deep(.el-button:hover) {
  color: #fff;
}
.msg-action-btn {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #c0c4cc;
  cursor: pointer;
  transition: color 0.15s, background 0.15s;
}
.msg-action-btn:hover {
  color: #409eff;
  background: rgba(64, 158, 255, 0.08);
}
.msg-bubble-wrap.user .msg-action-btn:hover {
  background: rgba(255,255,255,0.12);
  color: #fff;
}

/* ── 文件上下文栏 ── */
.file-context-bar {
  border-top: 1px solid #e4e7ed;
  background: #fafafa;
  padding: 8px 16px;
  max-height: 120px;
  overflow-y: auto;
}
.file-context-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.file-context-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  background: #ecf5ff;
  border: 1px solid #d9ecff;
  border-radius: 6px;
  font-size: 12px;
  white-space: nowrap;
  max-width: 260px;
}
.file-icon { font-size: 14px; flex-shrink: 0; }
.file-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #303133;
}
.file-size { font-size: 11px; color: #909399; flex-shrink: 0; }
.file-remove-btn {
  padding: 0 2px !important;
  font-size: 14px !important;
  color: #c0c4cc !important;
  flex-shrink: 0;
}
.file-remove-btn:hover {
  color: #f56c6c !important;
}

/* ── 输入区域 ── */
.chat-input-area {
  border-top: 1px solid #e4e7ed;
  padding: 12px 16px 10px;
  position: relative;
  transition: background 0.2s;
}
.chat-input-area.drag-over {
  background: #ecf5ff;
  border-color: #409eff;
}
.drag-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(64, 158, 255, 0.06);
  border: 2px dashed #409eff;
  border-radius: 12px;
  z-index: 10;
}
.drag-overlay-text {
  font-size: 15px;
  color: #409eff;
  font-weight: 500;
}

/* ── 输入框容器（文件按钮 + textarea + 发送按钮一体）── */
.input-wrapper {
  position: relative;
  display: flex;
  align-items: flex-start;
  background: #f5f7fa;
  border: 1px solid #e4e7ed;
  border-radius: 12px;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.input-wrapper:focus-within {
  border-color: #409eff;
  box-shadow: 0 0 0 3px rgba(64, 158, 255, 0.12);
}
.input-file-btn {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  margin: 6px 0 0 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  color: #909399;
  cursor: pointer;
  border-radius: 8px;
  transition: color 0.15s, background 0.15s;
}
.input-file-btn:hover {
  color: #409eff;
  background: rgba(64, 158, 255, 0.08);
}
.input-textarea {
  flex: 1;
  border: none;
  background: transparent;
  resize: none;
  padding: 10px 8px 10px 2px;
  min-height: 52px;
  font-size: 14px;
  line-height: 1.6;
  font-family: inherit;
  color: #303133;
  outline: none;
}
.input-textarea::placeholder {
  color: #c0c4cc;
}
.input-send-btn {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  margin: 6px 6px 0 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 8px;
  background: #409eff;
  color: #fff;
  cursor: pointer;
  transition: background 0.15s, transform 0.1s;
}
.input-send-btn:hover {
  background: #337ecc;
}
.input-send-btn:active {
  transform: scale(0.95);
}
.input-send-btn.stop-btn-icon {
  background: #f56c6c;
}
.input-send-btn.stop-btn-icon:hover {
  background: #d9534f;
}

.chat-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
  padding: 0 2px;
}
.action-hints { display: flex; gap: 6px; flex-wrap: wrap; }
.parallel-card { border: 1px solid #e4e7ed; border-radius: 10px; overflow: hidden; }
.parallel-header { padding: 8px 14px; background: #f5f7fa; border-bottom: 1px solid #e4e7ed; display: flex; align-items: center; }
.parallel-content { padding: 12px 14px; font-size: 13px; line-height: 1.6; white-space: pre-wrap; }
.thinking-dots .dot { animation: blink 1.4s infinite; font-size: 24px; }
.thinking-dots .dot:nth-child(2) { animation-delay: 0.2s; }
.thinking-dots .dot:nth-child(3) { animation-delay: 0.4s; }
.thinking-indicator {
  padding: 4px 0;
  min-height: 24px;
  display: flex;
  align-items: center;
}
@keyframes blink { 0%, 80%, 100% { opacity: 0; } 40% { opacity: 1; } }

/* 一呼百应样式 */
.collaborate-section { margin-bottom: 20px; }
.collaborate-main { background: linear-gradient(135deg, #fdf6ec 0%, #fff 100%); border: 1px solid #e6a23c; border-radius: 10px; padding: 16px; }
.collaborate-title { font-size: 16px; font-weight: bold; color: #e6a23c; margin-bottom: 10px; }
.collaborate-content { font-size: 14px; line-height: 1.8; white-space: pre-wrap; color: #333; }
.collaborate-detail { margin-top: 12px; display: flex; flex-direction: column; gap: 10px; }

/* ── Markdown enhanced: code blocks ── */
.msg-text :deep(.code-block),
.collaborate-content :deep(.code-block),
.parallel-content :deep(.code-block) {
  margin: 8px 0;
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid #e4e7ed;
  background: #f8f9fa;
}
.msg-text :deep(.code-header),
.collaborate-content :deep(.code-header),
.parallel-content :deep(.code-header) {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 12px;
  background: #e9ecef;
  font-size: 12px;
}
.msg-text :deep(.code-lang),
.collaborate-content :deep(.code-lang),
.parallel-content :deep(.code-lang) {
  color: #606266;
  font-weight: 500;
  text-transform: uppercase;
  font-size: 11px;
}
.msg-text :deep(.code-copy-btn),
.collaborate-content :deep(.code-copy-btn),
.parallel-content :deep(.code-copy-btn) {
  background: transparent;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  padding: 2px 8px;
  font-size: 11px;
  cursor: pointer;
  color: #606266;
  line-height: 1.6;
}
.msg-text :deep(.code-copy-btn:hover),
.collaborate-content :deep(.code-copy-btn:hover),
.parallel-content :deep(.code-copy-btn:hover) {
  background: #409eff;
  color: #fff;
  border-color: #409eff;
}
.msg-text :deep(pre),
.collaborate-content :deep(pre),
.parallel-content :deep(pre) {
  margin: 0;
  padding: 12px 16px;
  overflow-x: auto;
  background: #f8f9fa;
}
.msg-text :deep(pre code),
.collaborate-content :deep(pre code),
.parallel-content :deep(pre code) {
  background: transparent;
  padding: 0;
  font-size: 13px;
  line-height: 1.5;
  font-family: "Cascadia Code", "Fira Code", "Consolas", "Courier New", monospace;
}

/* ── Markdown enhanced: tables (zebra + responsive) ── */
.msg-text :deep(table),
.collaborate-content :deep(table),
.parallel-content :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 8px 0;
}
.msg-text :deep(th),
.msg-text :deep(td),
.collaborate-content :deep(th),
.collaborate-content :deep(td),
.parallel-content :deep(th),
.parallel-content :deep(td) {
  border: 1px solid #dcdfe6;
  padding: 8px 12px;
  text-align: left;
  font-size: 13px;
}
.msg-text :deep(th),
.collaborate-content :deep(th),
.parallel-content :deep(th) {
  background: #f0f2f5;
  font-weight: 600;
  white-space: nowrap;
}
.msg-text :deep(tr:nth-child(even)),
.collaborate-content :deep(tr:nth-child(even)),
.parallel-content :deep(tr:nth-child(even)) {
  background: #f9f9f9;
}

/* ── Markdown enhanced: task list checkboxes ── */
.msg-text :deep(.task-list-item),
.collaborate-content :deep(.task-list-item),
.parallel-content :deep(.task-list-item) {
  list-style: none;
  margin-left: -1.2em;
}
.msg-text :deep(.task-list-item input[type="checkbox"]),
.collaborate-content :deep(.task-list-item input[type="checkbox"]),
.parallel-content :deep(.task-list-item input[type="checkbox"]) {
  margin-right: 6px;
  vertical-align: middle;
}

/* ── Markdown enhanced: images ── */
.msg-text :deep(img),
.collaborate-content :deep(img),
.parallel-content :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 4px;
  margin: 8px 0;
}

/* Responsive overflow for tables inside message bubble */
.msg-text,
.collaborate-content,
.parallel-content {
  overflow-x: auto;
  max-width: 100%;
}

/* 编辑模式 */
.msg-edit-area :deep(.el-textarea__inner) {
  font-size: 14px;
  line-height: 1.6;
}

/* 停止生成按钮 */
.stop-btn {
  font-size: 12px;
}

/* 消息操作按钮图标大小 */
.msg-actions :deep(.el-button) {
  font-size: 12px;
}
.msg-actions :deep(.el-icon) {
  font-size: 14px;
  vertical-align: middle;
}
</style>
