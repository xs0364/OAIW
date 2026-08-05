<template>
  <div>
    <h2>RPA 自动化任务</h2>
    <p style="color: #909399; margin-bottom: 20px">浏览器自动化工具，自动执行码头查询、保函填写、箱单合并等重复性操作</p>

    <el-row :gutter="20">
      <el-col :span="8" v-for="task in rpaTasks" :key="task.name">
        <el-card shadow="hover" style="margin-bottom: 16px">
          <template #header>
            <div style="display: flex; align-items: center; gap: 8px">
              <el-icon :size="20" :color="task.color"><component :is="task.icon" /></el-icon>
              <b>{{ task.name }}</b>
            </div>
          </template>
          <p style="font-size: 13px; color: #606266; min-height: 36px">{{ task.desc }}</p>

          <!-- 码头选择（仅 port_status 显示） -->
          <div v-if="task.name === '码头状态查询'" style="margin-bottom: 10px">
            <el-select v-model="task.params.port_name" placeholder="选择码头" size="small" style="width: 100%">
              <el-option label="盐田港" value="盐田" />
              <el-option label="蛇口港" value="蛇口" />
              <el-option label="上海港" value="上海" />
              <el-option label="宁波港" value="宁波" />
              <el-option label="青岛港" value="青岛" />
            </el-select>
          </div>

          <!-- 集装箱查询输入 -->
          <div v-if="task.name === '集装箱查询'" style="margin-bottom: 10px">
            <el-select v-model="task.params.port_name" placeholder="选择港口" size="small" style="width: 100%; margin-bottom: 8px"
              @change="onPortChange(task)">
              <el-option label="盐田港" value="盐田港" />
              <el-option label="蛇口港" value="蛇口港" />
              <el-option label="上海港" value="上海港" />
              <el-option label="宁波港" value="宁波港" />
              <el-option label="青岛港" value="青岛港" />
            </el-select>
            <!-- 宁波港：手机号输入 -->
            <div v-if="task.params.port_name === '宁波港'" style="margin-bottom: 6px">
              <el-input v-model="task.params.npedi_mobile" placeholder="手机号（用于宁波港短信登录）" size="small">
                <template #prepend>📱</template>
              </el-input>
            </div>
            <el-input v-model="task.params.container_no" placeholder="集装箱号 (必填) eg. TLLU4109819" size="small" style="margin-bottom: 6px" />
            <el-input v-model="task.params.booking_no" placeholder="订舱号 (可选) eg. 149604151004" size="small" />
            <!-- 宁波港：进箱公告查询条件 -->
            <div v-if="task.params.port_name === '宁波港'" style="margin-bottom: 6px">
              <el-input v-model="task.params.vessel_name" placeholder="船名（进箱公告筛选，可选）" size="small" style="margin-bottom: 4px" />
              <el-input v-model="task.params.voyage_no" placeholder="航次（进箱公告筛选，可选）" size="small" />
            </div>
            <div style="font-size: 12px; color: #909399; margin-top: 4px">⚡ 宁波港需短信验证码登录，填写手机号后首次运行会弹出验证码输入框</div>
          </div>

          <!-- 箱单合并文件上传 -->
          <div v-if="task.name === '拼柜箱单合并'" style="margin-bottom: 10px">
            <el-upload
              ref="uploadRef"
              :auto-upload="false"
              multiple
              :file-list="task.files"
              :on-change="(f) => task.files.push(f)"
              list-type="text"
            >
              <el-button size="small" type="primary">选择文件</el-button>
            </el-upload>
          </div>
          <!-- AI自动填写模式 -->
          <div v-if="task.name === '非危保函填写'" style="margin-bottom:12px">
            <el-button size="small" :type="task.autoMode ? 'primary' : 'default'"
              @click="toggleAutoFill(task)" style="margin-bottom:10px;width:100%">
              {{ task.autoMode ? '🤖 AI自动填写模式' : '📋 手动填写模式' }}
            </el-button>

            <div v-if="task.autoMode" class="auto-fill-section">
              <!-- 拖放上传区 -->
              <div class="auto-drop-zone"
                @dragover.prevent="fileDragOver = true"
                @dragleave.prevent="fileDragOver = false"
                @drop.prevent="(e) => onFileDrop(e, task)"
                :class="{ 'drag-over': fileDragOver }">
                <div class="drop-hint">
                  <el-icon :size="32" color="#c0c4cc"><UploadFilled /></el-icon>
                  <span>拖拽文件到此处</span>
                </div>
                <div class="drop-files">
                  <div class="drop-file-item" :class="{ filled: task.msdsFile }">
                    <span class="drop-label">MSDS</span>
                    <span class="drop-value">{{ task.msdsFile ? task.msdsFile.name : '等待文件' }}</span>
                    <el-button v-if="task.msdsFile" text size="small" style="color:#c0c4cc;padding:0" @click.stop="task.msdsFile = null">×</el-button>
                  </div>
                  <div class="drop-file-item" :class="{ filled: task.certFile }">
                    <span class="drop-label">鉴定书</span>
                    <span class="drop-value">{{ task.certFile ? task.certFile.name : '等待文件' }}</span>
                    <el-button v-if="task.certFile" text size="small" style="color:#c0c4cc;padding:0" @click.stop="task.certFile = null">×</el-button>
                  </div>
                  <div class="drop-file-item" :class="{ filled: task.templateFile }">
                    <span class="drop-label">保函模板</span>
                    <span class="drop-value">{{ task.templateFile ? task.templateFile.name : '（可选）' }}</span>
                    <el-button v-if="task.templateFile" text size="small" style="color:#c0c4cc;padding:0" @click.stop="task.templateFile = null">×</el-button>
                  </div>
                </div>
                <div class="drop-footer">
                  <span>支持 PDF / DOCX / XLSX / 图片</span>
                  <span style="color:#409eff;cursor:pointer" @click.stop="triggerFilePick(task)">或点击选择</span>
                </div>
              </div>
              <div class="upload-row" style="margin-top:8px">
                <span class="upload-label">船公司</span>
                <el-input v-model="task.carrierInput" placeholder="如 MSK / CMA / COSCO" size="small" style="flex:1" />
              </div>
            </div>

            <div v-else>
              <el-input v-model="task.carrierInput" placeholder="船公司代码，如 MSK" size="small" style="margin-bottom:6px" />
              <el-input v-model="task.params.data.shipper" placeholder="Shipper（发货人）" size="small" style="margin-bottom:4px" />
              <el-input v-model="task.params.data.consignee" placeholder="Consignee（收货人）" size="small" style="margin-bottom:4px" />
              <el-input v-model="task.params.data.commodity" placeholder="Commodity（品名）" size="small" style="margin-bottom:4px" />
              <el-input v-model="task.params.data.container_no" placeholder="Container No（柜号）" size="small" style="margin-bottom:4px" />
              <el-input v-model="task.params.data.pol" placeholder="Port of Loading（起运港）" size="small" style="margin-bottom:4px" />
              <el-input v-model="task.params.data.pod" placeholder="Port of Discharge（目的港）" size="small" />
            </div>
          </div>

          <!-- AI自动填写模式（电放保函） -->
          <div v-if="task.name === '电放保函生成'" style="margin-bottom:12px">
            <el-button size="small" :type="task.autoMode ? 'primary' : 'default'"
              @click="toggleAutoFill(task)" style="margin-bottom:10px;width:100%">
              {{ task.autoMode ? '🤖 AI自动填写模式' : '📋 手动填写模式' }}
            </el-button>

            <div v-if="task.autoMode" class="auto-fill-section">
              <div class="auto-drop-zone"
                @dragover.prevent="fileDragOver = true"
                @dragleave.prevent="fileDragOver = false"
                @drop.prevent="(e) => onTelexFileDrop(e, task)"
                :class="{ 'drag-over': fileDragOver }">
                <div class="drop-hint">
                  <el-icon :size="32" color="#c0c4cc"><UploadFilled /></el-icon>
                  <span>拖拽文件到此处</span>
                </div>
                <div class="drop-files">
                  <div class="drop-file-item" :class="{ filled: task.blFile }">
                    <span class="drop-label">📄 提单</span>
                    <span class="drop-value">{{ task.blFile ? task.blFile.name : '等待文件（必填）' }}</span>
                    <el-button v-if="task.blFile" text size="small" style="color:#c0c4cc;padding:0" @click.stop="task.blFile = null">×</el-button>
                  </div>
                  <div class="drop-file-item" :class="{ filled: task.templateFile }">
                    <span class="drop-label">📋 模板</span>
                    <span class="drop-value">{{ task.templateFile ? task.templateFile.name : '等待文件（可选）' }}</span>
                    <el-button v-if="task.templateFile" text size="small" style="color:#c0c4cc;padding:0" @click.stop="task.templateFile = null">×</el-button>
                  </div>
                </div>
                <div class="drop-footer">
                  <span>支持 PDF / DOCX / DOC / 图片</span>
                  <span style="color:#409eff;cursor:pointer" @click.stop="triggerTelexFilePick(task)">或点击选择</span>
                </div>
              </div>
              <div class="upload-row" style="margin-top:8px">
                <span class="upload-label">船公司</span>
                <el-input v-model="task.carrierInput" placeholder="如 MSC / CMA / COSCO" size="small" style="flex:1" />
              </div>
            </div>

            <div v-else>
              <el-input v-model="task.carrierInput" placeholder="船公司代码，如 MSC" size="small" style="margin-bottom:6px" />
              <el-input v-model="task.params.data.shipper" placeholder="Shipper（发货人）" size="small" style="margin-bottom:4px" />
              <el-input v-model="task.params.data.consignee" placeholder="Consignee（收货人）" size="small" style="margin-bottom:4px" />
              <el-input v-model="task.params.data.bl_no" placeholder="B/L No（提单号）" size="small" style="margin-bottom:4px" />
              <el-input v-model="task.params.data.container_no" placeholder="Container No（柜号）" size="small" style="margin-bottom:4px" />
              <el-input v-model="task.params.data.vessel" placeholder="Vessel（船名）" size="small" style="margin-bottom:4px" />
              <el-input v-model="task.params.data.pol" placeholder="Port of Loading（起运港）" size="small" style="margin-bottom:4px" />
              <el-input v-model="task.params.data.pod" placeholder="Port of Discharge（目的港）" size="small" />
            </div>
          </div>
          <div style="margin-top: 12px; display: flex; gap: 8px; align-items: center">
            <el-tag size="small" :type="task.status === '运行中' ? 'warning' : task.status === '失败' ? 'danger' : task.status === '完成' ? 'success' : 'info'">
              {{ task.status }}
            </el-tag>
            <el-button type="primary" size="small" :loading="task.status === '运行中'" @click="runTask(task)">
              {{ task.status === '运行中' ? '运行中...' : '运行' }}
            </el-button>
            <el-button v-if="task.name === '集装箱查询' && task.queryDone" type="success" size="small" @click="goMergeFill(task)">
              合并录入佰信
            </el-button>
            <el-button size="small" @click="task.showLogs = !task.showLogs">
              {{ task.showLogs ? '隐藏日志' : '日志' }}
            </el-button>
            <el-button size="small" @click="clearLogs(task)" v-if="task.logLines.length > 1">清空</el-button>
          </div>

          <!-- 填写结果预览面板 -->
          <div v-if="task.filledLetter" class="result-panel">
            <div class="result-header">
              <span style="font-weight:600">填充结果</span>
              <div style="display:flex;gap:6px">
                <el-button size="small" @click="copyLetter(task)" :type="task.copied ? 'success' : 'default'">
                  {{ task.copied ? '已复制' : '复制' }}
                </el-button>
                <el-button size="small" type="primary" @click="downloadLetter(task)">下载 TXT</el-button>
                <el-button v-if="task.downloadId" size="small" type="success" @click="downloadDocx(task)">下载 DOCX</el-button>
              </div>
            </div>
            <pre class="result-content">{{ task.filledLetter }}</pre>
            <!-- 提取的字段摘要 -->
            <div v-if="task.extractedFields && Object.keys(task.extractedFields).length" class="extracted-summary">
              <div style="font-weight:600;margin-bottom:4px;font-size:13px">提取字段</div>
              <div v-for="(v,k) in task.extractedFields" :key="k" class="extracted-item" v-if="v">
                <span class="extracted-key">{{ k }}</span>
                <span class="extracted-val">{{ v }}</span>
              </div>
            </div>
          </div>

          <!-- 日志区域 -->
          <div v-if="task.showLogs" style="margin-top: 8px; background: #1d1e1f; color: #00ff00; padding: 8px; border-radius: 4px; font-size: 12px; max-height: 250px; overflow-y: auto; font-family: 'Courier New', monospace">
            <div v-for="(line, i) in task.logLines" :key="i" style="line-height: 1.6">
              <span style="color: #888">[{{ line.time }}]</span>
              <span :style="{ color: line.color || '#00ff00' }"> {{ line.text }}</span>
            </div>
            <div v-if="task.logLines.length === 0" style="color: #666">无日志</div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Ship, Ticket, Search, Files, CreditCard, UploadFilled } from '@element-plus/icons-vue'
import client from '../api/client'

const router = useRouter()

function goMergeFill(task) {
  router.push({
    name: 'MergeFill',
    query: {
      container_no: task.params.container_no || '',
      booking_no: task.params.booking_no || '',
    },
  })
}

const fileDragOver = ref(false)

function ts() {
  return new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function log(task, text, color = '') {
  task.logLines.push({ time: ts(), text, color })
}

const rpaTasks = ref([
  {
    name: '集装箱查询', icon: Search, color: '#409eff',
    desc: '输入柜号查询盐田/蛇口/上海/宁波/青岛等港口的集装箱在场状态',
    status: '就绪', showLogs: false, logLines: [], queryDone: false,
    params: { port_name: '盐田港', container_no: '', booking_no: '', npedi_mobile: localStorage.getItem('npedi_mobile') || '', vessel_name: '', voyage_no: '' }, files: [],
  },
  {
    name: '码头状态查询', icon: Ship, color: '#67c23a',
    desc: '自动查盐田/蛇口/上海/宁波/青岛码头开港、进港、放行状态',
    status: '就绪', showLogs: false, logLines: [], params: { port_name: '盐田' }, files: [],
  },
  {
    name: '非危保函填写', icon: Ticket, color: '#9b59b6',
    desc: '上传MSDS和鉴定书，AI自动提取信息填入非危保函',
    status: '就绪', showLogs: false, logLines: [],
    params: { type: 'non_hazardous', carrier: '', data: {} },
    files: [],
    msdsFile: null,
    certFile: null,
    templateFile: null,
    carrierInput: '',
    autoMode: false,
  },
  {
    name: '电放保函生成', icon: Files, color: '#f56c6c',
    desc: '上传提单(B/L)和电放保函模板，AI自动填充电放保函',
    status: '就绪', showLogs: false, logLines: [], params: { type: 'telex', carrier: 'MSK', data: {} }, files: [],
    autoMode: false, blFile: null, templateFile: null, carrierInput: '',
    filledLetter: '', extractedFields: {}, copied: false, downloadId: '',
  },
  {
    name: '拼柜箱单合并', icon: CreditCard, color: '#909399',
    desc: '将多家工厂不同格式的箱单发票合并为一份',
    status: '就绪', showLogs: false, logLines: [], params: {}, files: [],
  },
  {
    name: '账单录入佰信', icon: CreditCard, color: '#e74c3c',
    desc: '自动登录佰信系统，录入同行账单和代理账单',
    status: '就绪', showLogs: false, logLines: [], params: {}, files: [],
  },
])

function onPortChange(task) {
  task.logLines = []
}

function toggleAutoFill(task) {
  task.autoMode = !task.autoMode
  task.logLines = []
}

function triggerFilePick(task) {
  // Create a temp input for each click
  const input = document.createElement('input')
  input.type = 'file'
  input.multiple = false
  input.accept = '.pdf,.docx,.doc,.xls,.xlsx,.png,.jpg,.jpeg,.txt'
  input.onchange = (e) => {
    onFilePick(e, task)
  }
  input.click()
}

function onFilePick(e, task) {
  const files = Array.from(e.target.files || [])
  assignFilesToSlots(files, task)
  e.target.value = ''
}

function onFileDrop(e, task) {
  fileDragOver.value = false
  const files = Array.from(e.dataTransfer.files || [])
  if (files.length === 0) return
  assignFilesToSlots(files, task)
  task.logLines = []
}

function assignFilesToSlots(files, task) {
  for (const file of files) {
    const ext = file.name.split('.').pop().toLowerCase()
    const name = file.name.toLowerCase()
    // Try to detect file type by name
    if (!task.msdsFile && (name.includes('msds') || name.includes('msd') || name.includes('safety') || name.includes('material'))) {
      task.msdsFile = file
    } else if (!task.certFile && (name.includes('鉴定') || name.includes('certificate') || name.includes('非危') || name.includes('appraisal') || name.includes('classification'))) {
      task.certFile = file
    } else if (!task.templateFile && (name.includes('模板') || name.includes('保函') || name.includes('template') || name.includes('letter') || name.includes('declaration'))) {
      task.templateFile = file
    } else if (!task.msdsFile) {
      task.msdsFile = file
    } else if (!task.certFile) {
      task.certFile = file
    } else if (!task.templateFile) {
      task.templateFile = file
    }
  }
}

function triggerTelexFilePick(task) {
  const input = document.createElement('input')
  input.type = 'file'
  input.multiple = false
  input.accept = '.pdf,.docx,.doc,.xls,.xlsx,.png,.jpg,.jpeg,.txt'
  input.onchange = (e) => {
    const file = e.target.files?.[0]
    if (file) {
      if (!task.blFile) {
        task.blFile = file
      } else if (!task.templateFile) {
        task.templateFile = file
      }
    }
    e.target.value = ''
  }
  input.click()
}

function onTelexFileDrop(e, task) {
  fileDragOver.value = false
  const files = Array.from(e.dataTransfer.files || [])
  if (files.length === 0) return
  for (const file of files) {
    const name = file.name.toLowerCase()
    if (!task.blFile) {
      task.blFile = file
    } else if (!task.templateFile && (name.includes('模板') || name.includes('模板') || name.includes('保函') || name.includes('格式') || name.includes('letter') || name.includes('format') || name.includes('template') || name.includes('tlx'))) {
      task.templateFile = file
    } else if (!task.templateFile) {
      task.templateFile = file
    }
  }
  task.logLines = []
}

async function runTask(task) {
  task.status = '运行中'
  task.showLogs = true
  task.logLines = []
  log(task, '[任务启动]')

  try {
    const token = localStorage.getItem('oaiw_token')
    const params = task.params

    if (task.name === '集装箱查询') {
      if (!params.container_no) {
        log(task, '[请先输入集装箱号]', '#ff6b6b')
        task.status = '失败'
        return
      }
      log(task, `[查询] ${params.port_name}`, '#ffd700')
      log(task, `柜号: ${params.container_no.toUpperCase()}${params.booking_no ? ` | 订舱号: ${params.booking_no}` : ''}`, '#87ceeb')

      if (params.port_name === '宁波港') {
        log(task, '[宁波港] 准备登录查询...', '#87ceeb')

        const savedMobile = localStorage.getItem('npedi_mobile') || ''
        if (!params.npedi_mobile && !savedMobile) {
          log(task, '[宁波港] 请先输入手机号', '#ffd700')
          task.status = '就绪'
          return
        }
        const mobile = params.npedi_mobile || savedMobile
        log(task, `[宁波港] 手机号: ${mobile.slice(0,3)}****${mobile.slice(-4)}`, '#87ceeb')
        localStorage.setItem('npedi_mobile', mobile)

        const sessionResp = await fetch('/api/rpa/sms/session', { method: 'POST' })
        const { session_id: smsSessionId } = await sessionResp.json()

        log(task, '[宁波港] 正在启动浏览器...', '#87ceeb')
        const loginResp = await fetch('/api/rpa/run/stream', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            task_type: 'port_query',
            params: {
              port_name: '宁波港',
              container_no: params.container_no,
              booking_no: params.booking_no || '',
              npedi_mobile: mobile,
              sms_session_id: smsSessionId,
              vessel_name: params.vessel_name || '',
              voyage_no: params.voyage_no || '',
            },
          }),
        })

        if (!loginResp.ok) {
          const errBody = await loginResp.text().catch(() => '')
          log(task, `[错误] 后端请求失败 (HTTP ${loginResp.status}): ${errBody.slice(0, 200)}`, '#ff6b6b')
          task.status = '就绪'
          return
        }

        let smsTaskResolved = false

        const readSSE = async () => {
          const reader = loginResp.body.getReader()
          const decoder = new TextDecoder()
          let buf = ''
          let evtType = ''
          while (true) {
            const { done, value } = await reader.read()
            if (done) break
            buf += decoder.decode(value, { stream: true })
            const lines = buf.split('\n')
            buf = lines.pop() || ''
            for (const line of lines) {
              if (line.startsWith('event: ')) {
                evtType = line.slice(7).trim()
              } else if (line.startsWith('data: ')) {
                const msg = line.slice(6)
                if (msg === '[SSE connected]') continue
                if (evtType === 'done') {
                  evtType = ''
                  smsTaskResolved = true
                  try {
                    const result = JSON.parse(msg)
                    if (result.data) {
                      result.data.split('\n').forEach(l => {
                        const c = l.replace(/\t/g, ' ').replace(/ +/g, ' ').trim()
                        if (c) log(task, c)
                      })
                    }
                    log(task, result.success ? '[查询成功]' : ('[查询失败] ' + (result.error || '')), result.success ? '#00ff00' : '#ff6b6b')
                    if (result.success) task.queryDone = true
                  } catch (e) { /* ignore */ }
                  continue
                }
                log(task, msg)
                if (!smsTaskResolved && (msg.includes('waiting for user input') || msg.includes('等待用户输入'))) {
                  smsTaskResolved = true
                  log(task, '[宁波港] 短信已发送到手机，请输入验证码', '#ffd700')
                  await new Promise(r => setTimeout(r, 200))
                  try {
                    const { value: smsCode } = await ElMessageBox.prompt(
                      '短信验证码已发送到您的手机，请输入：',
                      '宁波港短信验证码',
                      {
                        confirmButtonText: '提交',
                        cancelButtonText: '取消',
                        inputPattern: /^\d{4,8}$/,
                        inputErrorMessage: '请输入收到的短信验证码',
                      }
                    )
                    log(task, '[宁波港] 已拿到验证码，正在进入系统...', '#00ff00')
                    await fetch('/api/rpa/sms/submit', {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ session_id: smsSessionId, code: smsCode }),
                    })
                  } catch {
                    log(task, '[宁波港] 用户取消验证码输入', '#ff6b6b')
                  }
                }
              }
            }
          }
        }
        const ssePromise = readSSE()
        await ssePromise
        task.status = '就绪'
        log(task, '--- 任务完成 ---', '#888')
        return
      }

      // 非宁波港：常规 SSE 流
      const resp = await fetch('/api/rpa/run/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ task_type: 'port_query', params: task.params }),
      })

      if (!resp.ok) {
        const errText = await resp.text().catch(() => '')
        log(task, `[错误] 后端请求失败 (HTTP ${resp.status}): ${errText.slice(0, 300)}`, '#ff6b6b')
        task.status = '就绪'
        log(task, '--- 任务完成 ---', '#888')
        return
      }

      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let evtType = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
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
                if (result.data) {
                  result.data.split('\n').forEach(l => {
                    const cleaned = l.replace(/\t/g, ' ').replace(/ +/g, ' ').trim()
                    if (cleaned) log(task, cleaned)
                  })
                }
                if (result.success) {
                  task.queryDone = true
                  log(task, '[查询成功]', '#00ff00')
                }
                else log(task, '[查询失败] ' + (result.error || '未知错误'), '#ff6b6b')
              } catch (e) { log(task, data) }
            } else {
              if (data !== '[SSE connected]') {
                log(task, data)
              }
            }
          }
        }
      }

    } else if (task.name === '码头状态查询') {
      log(task, '正在执行: 码头状态查询', '#ffd700')
      const res = await client.post('/rpa/run', { task_type: 'port_status', params: task.params })
      if (res.data.success) {
        log(task, '[执行成功]')
        res.data.data.split('\n').forEach(line => log(task, line.trim()))
      } else { throw new Error(res.data.error || '执行失败') }
    } else if (task.name === '电放保函生成') {
      if (task.autoMode) {
        if (!task.blFile) { log(task, '[请先选择提单文件(B/L)]', '#ff6b6b'); task.status = '失败'; return }
        log(task, '[AI自动填写模式] 正在上传提单并提取信息...', '#ffd700')
        const formData = new FormData()
        formData.append('bill_of_lading', task.blFile)
        if (task.templateFile) formData.append('template', task.templateFile)
        if (task.carrierInput) formData.append('carrier', task.carrierInput)
        const res = await client.post('/rpa/letter/auto-fill-telex', formData, { headers: { 'Content-Type': 'multipart/form-data' } })
        if (res.data.success) {
          log(task, '[AI填写成功]', '#00ff00')
          task.filledLetter = res.data.filled_letter || ''
          task.extractedFields = res.data.extracted || {}
          task.downloadId = res.data.download_id || ''
          task.copied = false
        } else { throw new Error(res.data.error || 'AI填写失败') }
      } else {
        log(task, `正在生成: ${task.name}`, '#ffd700')
        const payload = {
          type: 'telex',
          carrier: task.carrierInput || task.params.carrier || 'MSK',
          data: {
            shipper: task.params.data.shipper || '',
            consignee: task.params.data.consignee || '',
            bl_no: task.params.data.bl_no || '',
            container_no: task.params.data.container_no || '',
            vessel: task.params.data.vessel || '',
            pol: task.params.data.pol || '',
            pod: task.params.data.pod || '',
          },
        }
        const res = await client.post('/rpa/letter/generate', payload)
        if (res.data.success) {
          log(task, '[保函生成成功]')
          res.data.content.split('\n').forEach(line => log(task, line.trim()))
        } else { throw new Error(res.data.error || '生成失败') }
      }
    } else if (task.name === '非危保函填写') {
      if (task.autoMode) {
        if (!task.msdsFile) { log(task, '[请先选择MSDS文件]', '#ff6b6b'); task.status = '失败'; return }
        if (!task.certFile) { log(task, '[请先选择鉴定书文件]', '#ff6b6b'); task.status = '失败'; return }
        log(task, '[AI自动填写模式] 正在上传文件并提取信息...', '#ffd700')
        const formData = new FormData()
        formData.append('msds', task.msdsFile)
        formData.append('certificate', task.certFile)
        if (task.templateFile) formData.append('template', task.templateFile)
        if (task.carrierInput) formData.append('carrier', task.carrierInput)
        const res = await client.post('/rpa/letter/auto-fill', formData, { headers: { 'Content-Type': 'multipart/form-data' } })
        if (res.data.success) {
          log(task, '[AI填写成功]', '#00ff00')
          task.filledLetter = res.data.filled_letter || ''
          task.extractedFields = res.data.extracted || {}
          task.copied = false
        } else { throw new Error(res.data.error || 'AI填写失败') }
      } else {
        log(task, `正在生成: ${task.name}`, '#ffd700')
        const payload = {
          type: 'non_hazardous',
          carrier: task.carrierInput || '',
          data: {
            shipper: task.params.data.shipper || '',
            consignee: task.params.data.consignee || '',
            commodity: task.params.data.commodity || '',
            container_no: task.params.data.container_no || '',
            pol: task.params.data.pol || '',
            pod: task.params.data.pod || '',
          },
        }
        const res = await client.post('/rpa/letter/generate', payload)
        if (res.data.success) {
          log(task, '[保函生成成功]')
          res.data.content.split('\n').forEach(line => log(task, line.trim()))
        } else { throw new Error(res.data.error || '生成失败') }
      }
    } else if (task.name === '拼柜箱单合并') {
      if (task.files.length < 2) { log(task, '[请至少选择2个文件进行合并]', '#ff6b6b'); task.status = '失败'; return }
      log(task, `正在合并 ${task.files.length} 个文件...`, '#ffd700')
      const docIds = []
      for (const f of task.files) {
        const formData = new FormData(); formData.append('file', f.raw || f)
        const uploadRes = await client.post('/docs/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } })
        if (uploadRes.data.success) { docIds.push(uploadRes.data.file_id); log(task, `已上传: ${uploadRes.data.filename}`, '#87ceeb') }
      }
      const mergeRes = await client.post('/docs/merge-invoices', { doc_ids: docIds })
      if (mergeRes.data.success) { log(task, `[合并完成] 共 ${mergeRes.data.file_count} 个文件`, '#00ff00'); mergeRes.data.merged_text.split('\n').slice(0, 50).forEach(line => log(task, line)) }
    } else if (task.name === '账单录入佰信') {
      log(task, '[打开佰信合并录入]', '#ffd700')
      router.push({ name: 'MergeFill' })
    }

    task.status = task.filledLetter ? '完成' : '就绪'
    log(task, '--- 任务完成 ---', '#888')
  } catch (e) {
    task.status = '失败'
    log(task, `[错误] ${e.response?.data?.error || e.message}`, '#ff6b6b')
  }
}

function clearLogs(task) {
  task.logLines = []
}

function copyLetter(task) {
  if (!task.filledLetter) return
  navigator.clipboard.writeText(task.filledLetter).then(() => {
    task.copied = true
    setTimeout(() => task.copied = false, 2000)
  })
}

function downloadLetter(task) {
  if (!task.filledLetter) return
  const label = task.name === '电放保函生成' ? '电放保函' : '非危保函'
  const name = task.extractedFields?.['bl_no'] || task.extractedFields?.['中文品名'] || label
  const blob = new Blob([task.filledLetter], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${name}_${label}.txt`
  a.click()
  URL.revokeObjectURL(url)
}

function downloadDocx(task) {
  if (!task.downloadId) return
  window.open(`/api/rpa/letter/download/${task.downloadId}`, '_blank')
}
</script>

<style scoped>
.auto-fill-section {
  background: #f5f7fa;
  border-radius: 8px;
  padding: 12px;
}
.auto-drop-zone {
  border: 2px dashed #dcdfe6;
  border-radius: 8px;
  padding: 16px;
  text-align: center;
  transition: all .2s;
  background: #fff;
}
.auto-drop-zone.drag-over {
  border-color: #409eff;
  background: #ecf5ff;
}
.drop-hint {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  color: #909399;
  font-size: 13px;
  margin-bottom: 12px;
}
.drop-files {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 10px;
}
.drop-file-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: 6px;
  background: #f5f7fa;
  font-size: 12px;
}
.drop-file-item.filled {
  background: #ecf5ff;
}
.drop-label {
  color: #909399;
  font-weight: 500;
  flex-shrink: 0;
  width: 56px;
}
.drop-value {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #303133;
  text-align: left;
}
.drop-footer {
  font-size: 12px;
  color: #c0c4cc;
}
.drop-footer a {
  color: #409eff;
  cursor: pointer;
}
.upload-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.upload-row:last-child { margin-bottom: 0; }
.upload-label {
  font-size: 12px;
  color: #606266;
  width: 56px;
  flex-shrink: 0;
}
.result-panel {
  margin-top: 12px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
}
.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  background: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
  font-size: 14px;
}
.result-content {
  margin: 0;
  padding: 14px;
  background: #fff;
  font-size: 13px;
  line-height: 1.7;
  max-height: 400px;
  overflow-y: auto;
  white-space: pre-wrap;
  font-family: 'Microsoft YaHei', 'SimSun', monospace;
}
.extracted-summary {
  padding: 10px 14px;
  background: #fafafa;
  border-top: 1px solid #e4e7ed;
}
.extracted-item {
  display: inline-block;
  margin: 2px 6px 2px 0;
  padding: 2px 8px;
  background: #ecf5ff;
  border-radius: 4px;
  font-size: 12px;
}
.extracted-key {
  color: #909399;
  margin-right: 4px;
}
.extracted-val {
  color: #303133;
}
</style>
