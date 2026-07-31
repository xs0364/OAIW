<template>
  <div>
    <h2>系统设置</h2>

    <el-tabs v-model="activeTab">
      <!-- AI模型配置 -->
      <el-tab-pane label="AI模型配置" name="llm">
        <el-card shadow="never">
          <el-form label-width="140px">
            <el-form-item label="主模型">
              <el-select v-model="mainModel" style="width: 300px">
                <el-option label="DeepSeek V4 (API)" value="deepseek" />
                <el-option label="Ollama 本地 (gemma4)" value="ollama" />
                <el-option label="LM Studio" value="lmstudio" />
              </el-select>
            </el-form-item>
            <el-form-item label="API Key">
              <el-input v-model="apiKey" type="password" show-password style="width: 300px" />
            </el-form-item>
            <el-form-item label="API 地址">
              <el-input v-model="apiUrl" style="width: 300px" placeholder="https://api.deepseek.com/v1" />
            </el-form-item>
            <el-form-item label="视觉模型">
              <el-select v-model="visionModel" style="width: 300px">
                <el-option label="NVIDIA Llama-3.2-90B-Vision (默认)" value="meta/llama-3.2-90b-vision-instruct" />
                <el-option label="NVIDIA Llama-3.2-11B-Vision" value="meta/llama-3.2-11b-vision-instruct" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="saveLLMConfig">保存配置</el-button>
              <el-button @click="testConnection">测试连接</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-tab-pane>

      <!-- 多Agent配置 -->
      <el-tab-pane label="多Agent配置" name="nim">
        <el-card shadow="never">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <b>多模型 Agent 引擎</b>
              <el-tag type="success">4 Agents</el-tag>
            </div>
          </template>
          <p style="color: #909399; font-size: 13px; margin-bottom: 20px">
            配置各Agent的API地址和Key。兼容任意 OpenAI 格式 API（英伟达NIM、DeepSeek、OpenAI、阿里百炼等）。
          </p>

          <div v-for="(agent, i) in nimAgents" :key="agent.name" style="margin-bottom: 20px; padding: 16px; border: 1px solid #e4e7ed; border-radius: 8px">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px">
              <el-tag :type="agent.status ? 'success' : 'danger'" size="small" effect="dark" round>
                {{ agent.status ? '已配置' : '未配置' }}
              </el-tag>
              <b style="font-size: 15px">{{ agent.display_name }}</b>
              <span style="font-size: 12px; color: #909399">{{ agent.model }}</span>
            </div>
            <el-form label-width="110px">
              <el-form-item :label="'URL ' + (i+1)">
                <el-input
                  v-model="agent.api_url"
                  placeholder="https://integrate.api.nvidia.com/v1"
                  style="width: 100%"
                />
              </el-form-item>
              <el-form-item :label="'API Key ' + (i+1)">
                <div style="display: flex; gap: 8px; width: 100%">
                  <el-input
                    v-model="agent.api_key"
                    :type="agent.showKey ? 'text' : 'password'"
                    placeholder="API Key"
                    style="width: 100%"
                  />
                  <el-button size="small" @click="toggleKeyVisibility(agent)">{{ agent.showKey ? '隐藏' : '显示' }}</el-button>
                </div>
              </el-form-item>
              <el-form-item label="用途">
                <span style="font-size: 13px; color: #606266">{{ agent.desc }}</span>
              </el-form-item>
            </el-form>
          </div>

          <el-divider />

          <!-- 自定义Agent -->
          <div style="margin-bottom: 16px">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px">
              <b>自定义Agent</b>
              <el-button size="small" type="primary" plain @click="showCustomDialog = true">+ 添加Agent</el-button>
            </div>
            <div v-if="customAgents.length === 0" style="color: #c0c4cc; font-size: 13px; padding: 12px 0">
              暂无自定义Agent
            </div>
            <div v-for="(agent, i) in customAgents" :key="agent._key" style="margin-bottom: 12px; padding: 12px; border: 1px dashed #e4e7ed; border-radius: 8px">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px">
                <div style="display: flex; align-items: center; gap: 8px">
                  <el-tag type="success" size="small" effect="dark" round>{{ agent.status ? '已配置' : '未配置' }}</el-tag>
                  <b style="font-size: 14px">{{ agent.display_name }}</b>
                  <span style="font-size: 12px; color: #909399">{{ agent.model }}</span>
                </div>
                <el-button text type="danger" size="small" @click="removeCustomAgent(i)">删除</el-button>
              </div>
              <el-form label-width="80px">
                <el-form-item label="URL">
                  <el-input v-model="agent.api_url" placeholder="https://integrate.api.nvidia.com/v1" />
                </el-form-item>
                <el-form-item label="API Key">
                  <div style="display: flex; gap: 8px; width: 100%">
                    <el-input v-model="agent.api_key" :type="agent.showKey ? 'text' : 'password'" placeholder="API Key" style="width: 100%" />
                    <el-button size="small" @click="agent.showKey = !agent.showKey">{{ agent.showKey ? '隐藏' : '显示' }}</el-button>
                  </div>
                </el-form-item>
              </el-form>
            </div>
          </div>

          <el-button type="primary" @click="saveNIMConfig" :loading="savingNIM">
            保存所有Agent配置
          </el-button>
          <el-button @click="testAllAgents" :loading="testingAgents">
            测试所有连接
          </el-button>

          <!-- 添加自定义Agent对话框 -->
          <el-dialog v-model="showCustomDialog" title="添加自定义Agent" width="500px">
            <el-form label-width="100px" :model="newCustomAgent">
              <el-form-item label="名称(英文)">
                <el-input v-model="newCustomAgent.name" placeholder="如 my_agent, 唯一标识" />
              </el-form-item>
              <el-form-item label="显示名称">
                <el-input v-model="newCustomAgent.display_name" placeholder="如 我的模型" />
              </el-form-item>
              <el-form-item label="模型名">
                <el-input v-model="newCustomAgent.model" placeholder="如 gpt-4o, deepseek-chat" />
              </el-form-item>
              <el-form-item label="API地址">
                <el-input v-model="newCustomAgent.api_url" placeholder="https://integrate.api.nvidia.com/v1" />
              </el-form-item>
              <el-form-item label="API Key">
                <el-input v-model="newCustomAgent.api_key" type="password" show-password placeholder="API Key" />
              </el-form-item>
              <el-form-item label="用途说明">
                <el-input v-model="newCustomAgent.desc" type="textarea" :rows="2" placeholder="描述这个Agent的用途" />
              </el-form-item>
            </el-form>
            <template #footer>
              <el-button @click="showCustomDialog = false">取消</el-button>
              <el-button type="primary" @click="addCustomAgent">添加</el-button>
            </template>
          </el-dialog>

          <el-divider />

          <div style="font-size: 13px; color: #606266">
            <b>使用说明：</b><br>
            1. 填入各Agent的API地址和Key（兼容任意OpenAI格式API）<br>
            2. 保存后在AI助手页面可选择使用哪个Agent<br>
            3. 支持自动路由、指定Agent、并行模式<br>
            4. 默认API地址为英伟达NIM：<code>https://integrate.api.nvidia.com/v1</code>
          </div>
        </el-card>
      </el-tab-pane>

      <!-- RPA配置 -->
      <el-tab-pane label="RPA配置" name="rpa">
        <el-card shadow="never">
          <el-form label-width="140px">
            <el-form-item label="浏览器模式">
              <el-radio-group v-model="headless">
                <el-radio :value="false">显示浏览器窗口</el-radio>
                <el-radio :value="true">无头模式 (后台)</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="超时时间(秒)">
              <el-input-number v-model="rpaTimeout" :min="10" :max="120" />
            </el-form-item>
            <el-form-item label="佰信系统地址">
              <el-input v-model="baixinUrl" style="width: 300px" placeholder="http://..." />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="saveRPAConfig">保存</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-tab-pane>

      <!-- 邮箱配置 -->
      <el-tab-pane label="邮箱配置" name="email">
        <el-card shadow="never">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <b>SMTP 邮件服务器</b>
              <el-tag :type="smtpConfigured ? 'success' : 'danger'" size="small">
                {{ smtpConfigured ? '已配置' : '未配置' }}
              </el-tag>
            </div>
          </template>
          <p style="color: #909399; font-size: 13px; margin-bottom: 20px">
            配置 SMTP 邮件服务器后，系统可在 RPA 任务完成等场景自动发送通知邮件。
            QQ邮箱使用 <code>smtp.qq.com</code>，密码处填写<strong>授权码</strong>（非登录密码）。
          </p>
          <el-form label-width="140px">
            <el-form-item label="SMTP 服务器">
              <el-input v-model="smtpHost" style="width: 300px" placeholder="smtp.qq.com" />
            </el-form-item>
            <el-form-item label="端口">
              <el-radio-group v-model="smtpPort">
                <el-radio :value="465">465 (SSL)</el-radio>
                <el-radio :value="587">587 (TLS)</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="邮箱账号">
              <el-input v-model="smtpUser" style="width: 300px" placeholder="your@qq.com" />
            </el-form-item>
            <el-form-item label="密码/授权码">
              <el-input v-model="smtpPassword" type="password" show-password style="width: 300px" placeholder="QQ邮箱请填写授权码" />
            </el-form-item>
            <el-form-item label="发件人地址">
              <el-input v-model="smtpFromEmail" style="width: 300px" placeholder="留空则使用邮箱账号" />
            </el-form-item>
            <el-form-item label="测试收件人">
              <el-input v-model="smtpTestTo" style="width: 300px" placeholder="留空则发送到自己邮箱" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="saveSmtpConfig" :loading="savingSmtp">保存配置</el-button>
              <el-button @click="testSmtpConfig" :loading="testingSmtp" :disabled="!smtpConfigured">发送测试邮件</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import client from '../api/client'

const activeTab = ref('llm')

// LLM配置
const mainModel = ref('deepseek')
const visionModel = ref('meta/llama-3.2-90b-vision-instruct')
const apiKey = ref('')
const apiUrl = ref('https://api.deepseek.com/v1')
const headless = ref(false)
const rpaTimeout = ref(30)
const baixinUrl = ref('')

// 多Agent配置
const savingNIM = ref(false)
const testingAgents = ref(false)
const nimAgents = ref([
  { name: 'nim_gpt', display_name: 'GPT-OSS 120B', model: 'openai/gpt-oss-120b', api_url: 'https://integrate.api.nvidia.com/v1', api_key: '', showKey: false, status: false, desc: '通用推理，适合复杂业务逻辑分析、合同审核、决策建议' },
  { name: 'nim_qwen', display_name: 'Llama 3.1 70B', model: 'meta/llama-3.1-70b-instruct', api_url: 'https://integrate.api.nvidia.com/v1', api_key: '', showKey: false, status: false, desc: '综合能力强，多语言翻译好，适合文档处理、翻译、摘要生成' },
  { name: 'nim_minimax', display_name: 'DeepSeek Chat', model: 'deepseek-chat', api_url: 'https://api.deepseek.com/v1', api_key: '', showKey: false, status: false, desc: 'DeepSeek官方API，适合快速问答、港口查询、货物跟踪' },
  { name: 'nim_deepseek', display_name: 'Nemotron Super 120B', model: 'nvidia/nemotron-3-super-120b-a12b', api_url: 'https://integrate.api.nvidia.com/v1', api_key: '', showKey: false, status: false, desc: '英伟达顶级推理模型，适合复杂分析、运价趋势、利润预测、业务决策' },
])

// 自定义Agent
const showCustomDialog = ref(false)
const customAgents = ref([])
const newCustomAgent = ref({
  name: '', display_name: '', model: '', api_url: 'https://integrate.api.nvidia.com/v1', api_key: '', desc: '',
})

// SMTP 邮箱配置
const smtpHost = ref('')
const smtpPort = ref(465)
const smtpUser = ref('')
const smtpPassword = ref('')
const smtpFromEmail = ref('')
const smtpTestTo = ref('')
const savingSmtp = ref(false)
const testingSmtp = ref(false)
const smtpConfigured = ref(false)

function addCustomAgent() {
  const a = newCustomAgent.value
  if (!a.name || !a.display_name || !a.model) {
    ElMessage.warning('请填写名称、显示名称和模型名')
    return
  }
  if (customAgents.value.find(c => c.name === a.name) || nimAgents.value.find(c => c.name === a.name)) {
    ElMessage.warning('名称已存在')
    return
  }
  customAgents.value.push({
    name: a.name,
    display_name: a.display_name,
    model: a.model,
    api_url: a.api_url,
    api_key: a.api_key,
    desc: a.desc || a.display_name,
    status: !!a.api_key,
    _key: 'custom_' + Date.now(),
  })
  showCustomDialog.value = false
  newCustomAgent.value = { name: '', display_name: '', model: '', api_url: 'https://integrate.api.nvidia.com/v1', api_key: '', desc: '' }
  ElMessage.success('自定义Agent已添加，点击"保存所有Agent配置"生效')
}

function removeCustomAgent(index) {
  customAgents.value.splice(index, 1)
  ElMessage.success('已删除，点击"保存所有Agent配置"生效')
}

// 加载所有配置
onMounted(async () => {
  try {
    // 读取LLM配置
    const loadSetting = async (key, target) => {
      const res = await client.get(`/settings/get/${key}`).catch(() => ({ data: { value: '' } }))
      if (res.data.value) target.value = res.data.value
    }
    await Promise.all([
      loadSetting('llm_provider', mainModel),
      loadSetting('llm_api_key', apiKey),
      loadSetting('llm_api_url', apiUrl),
      loadSetting('vision_model', visionModel),
      loadSetting('rpa_headless', headless),
      loadSetting('rpa_timeout', rpaTimeout),
      loadSetting('baixin_url', baixinUrl),
      // SMTP配置
      loadSetting('smtp_host', smtpHost),
      loadSetting('smtp_port', smtpPort),
      loadSetting('smtp_user', smtpUser),
      loadSetting('smtp_password', smtpPassword),
      loadSetting('smtp_from_email', smtpFromEmail),
    ])
    // 修复类型
    headless.value = headless.value === 'true' || headless.value === true
    rpaTimeout.value = parseInt(String(rpaTimeout.value)) || 30
    smtpPort.value = parseInt(String(smtpPort.value)) || 465
    smtpConfigured.value = !!(smtpHost.value && smtpUser.value && smtpPassword.value)

    // 读取Agent Key和URL
    for (const agent of nimAgents.value) {
      const [keyRes, urlRes] = await Promise.all([
        client.get(`/settings/get/agent_key_${agent.name}`).catch(() => ({ data: { value: '' } })),
        client.get(`/settings/get/agent_url_${agent.name}`).catch(() => ({ data: { value: '' } })),
      ])
      if (keyRes.data.value) {
        agent.api_key = keyRes.data.value
        agent.status = true
      }
      if (urlRes.data.value) {
        agent.api_url = urlRes.data.value
      }
    }

    // 读取自定义Agent
    const custRes = await client.get('/settings/get/agent_custom_list').catch(() => ({ data: { value: '' } }))
    if (custRes.data.value) {
      try {
        customAgents.value = JSON.parse(custRes.data.value).map(a => ({ ...a, status: !!a.api_key, _key: 'custom_' + a.name }))
      } catch { /* ignore */ }
    }
  } catch { /* 忽略 */ }
})

function toggleKeyVisibility(agent) {
  agent.showKey = !agent.showKey
}

// 保存LLM配置
async function saveLLMConfig() {
  try {
    await client.post('/settings/set-multi', [
      { key: 'llm_provider', value: mainModel.value, description: '主模型供应商' },
      { key: 'llm_api_key', value: apiKey.value, description: 'API Key' },
      { key: 'llm_api_url', value: apiUrl.value, description: 'API地址' },
      { key: 'vision_model', value: visionModel.value, description: '视觉模型' },
    ])
    ElMessage.success('LLM配置已保存')
  } catch (e) {
    ElMessage.error('保存失败: ' + (e.response?.data?.error || e.message))
  }
}

// 保存Agent配置
async function saveNIMConfig() {
  savingNIM.value = true
  try {
    for (const agent of nimAgents.value) {
      await Promise.all([
        agent.api_key ? client.post('/settings/set', {
          key: `agent_key_${agent.name}`,
          value: agent.api_key,
          description: `API Key for ${agent.display_name}`,
        }) : Promise.resolve(),
        agent.api_url ? client.post('/settings/set', {
          key: `agent_url_${agent.name}`,
          value: agent.api_url,
          description: `API URL for ${agent.display_name}`,
        }) : Promise.resolve(),
      ])
      agent.status = !!agent.api_key
    }
    // 保存自定义Agent
    const customData = customAgents.value.map(a => ({
      name: a.name,
      display_name: a.display_name,
      model: a.model,
      api_url: a.api_url,
      api_key: a.api_key,
      description: a.desc,
    }))
    await client.post('/settings/set', {
      key: 'agent_custom_list',
      value: JSON.stringify(customData),
      description: '自定义Agent列表',
    })
    ElMessage.success('所有Agent配置已保存')
  } catch (e) {
    ElMessage.error('保存失败: ' + (e.response?.data?.error || e.message))
  }
  savingNIM.value = false
}

// 测试主模型连接
async function testConnection() {
  try {
    const res = await client.post('/chat/send', {
      message: '回复"连接测试成功"四个字即可',
      stream: false,
    })
    if (res.data.reply) {
      ElMessage.success('主模型连接成功')
    }
  } catch (e) {
    ElMessage.error('连接失败: ' + (e.response?.data?.error || e.message))
  }
}

// 测试所有Agent连接
async function testAllAgents() {
  testingAgents.value = true
  for (const agent of nimAgents.value) {
    if (!agent.api_key) {
      ElMessage.warning(`${agent.display_name} 未配置API Key`)
      continue
    }
    try {
      const res = await client.post('/chat/multi-agent/send', {
        message: '回复"连接成功"即可',
        agent_name: agent.name,
      })
      if (res.data.success && res.data.content) {
        ElMessage.success(`${agent.display_name} 连接成功`)
        agent.status = true
      }
    } catch (e) {
      ElMessage.error(`${agent.display_name} 连接失败: ${e.message}`)
      agent.status = false
    }
  }
  testingAgents.value = false
}

// 保存RPA配置
async function saveRPAConfig() {
  try {
    await client.post('/settings/set-multi', [
      { key: 'rpa_headless', value: String(headless.value), description: '无头模式' },
      { key: 'rpa_timeout', value: String(rpaTimeout.value), description: '超时时间(秒)' },
      { key: 'baixin_url', value: baixinUrl.value, description: '佰信系统地址' },
    ])
    ElMessage.success('RPA配置已保存')
  } catch (e) {
    ElMessage.error('保存失败: ' + (e.response?.data?.error || e.message))
  }
}

// ===== SMTP 邮箱配置 =====

async function saveSmtpConfig() {
  savingSmtp.value = true
  try {
    await client.post('/settings/set-multi', [
      { key: 'smtp_host', value: smtpHost.value, description: 'SMTP服务器地址' },
      { key: 'smtp_port', value: String(smtpPort.value), description: 'SMTP端口' },
      { key: 'smtp_user', value: smtpUser.value, description: 'SMTP用户名' },
      { key: 'smtp_password', value: smtpPassword.value, description: 'SMTP密码/授权码' },
      { key: 'smtp_from_email', value: smtpFromEmail.value, description: '发件人邮箱' },
    ])
    smtpConfigured.value = !!(smtpHost.value && smtpUser.value && smtpPassword.value)
    ElMessage.success('SMTP配置已保存')
  } catch (e) {
    ElMessage.error('保存失败: ' + (e.response?.data?.error || e.message))
  }
  savingSmtp.value = false
}

async function testSmtpConfig() {
  testingSmtp.value = true
  try {
    const res = await client.post('/settings/test-email', {
      to_email: smtpTestTo.value || smtpUser.value,
      host: smtpHost.value,
      port: smtpPort.value,
      user: smtpUser.value,
      password: smtpPassword.value,
      from_email: smtpFromEmail.value,
    })
    if (res.data.success) {
      ElMessage.success(res.data.message)
    } else {
      ElMessage.error(res.data.error || '发送失败')
    }
  } catch (e) {
    ElMessage.error('测试失败: ' + (e.response?.data?.error || e.message))
  }
  testingSmtp.value = false
}
</script>

