<template>
  <div>
    <el-card shadow="never">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <b>我的邮箱 (SMTP) 配置</b>
          <el-tag :type="configured ? 'success' : 'danger'" size="small">
            {{ configured ? '已配置' : '未配置' }}
          </el-tag>
        </div>
      </template>

      <p style="color: #909399; font-size: 13px; margin-bottom: 20px">
        这里配置的是<strong>您本人账号</strong>使用的发件邮箱，与其他同事互不影响。
        配置后，AI 助手在「发送邮件到我的邮箱 / 发邮件给客户」等场景使用您的邮箱发送。
        QQ邮箱使用 <code>smtp.qq.com</code>，密码处填写<strong>授权码</strong>（非登录密码）。
      </p>

      <el-form label-width="140px">
        <el-form-item label="SMTP 服务器">
          <el-input v-model="form.smtp_host" style="width: 300px" placeholder="smtp.qq.com" />
        </el-form-item>
        <el-form-item label="端口">
          <el-radio-group v-model="form.smtp_port">
            <el-radio :value="465">465 (SSL)</el-radio>
            <el-radio :value="587">587 (TLS)</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="邮箱账号">
          <el-input v-model="form.smtp_user" style="width: 300px" placeholder="your@qq.com" />
        </el-form-item>
        <el-form-item label="密码/授权码">
          <el-input v-model="form.smtp_password" type="password" show-password style="width: 300px" placeholder="QQ邮箱请填写授权码" />
        </el-form-item>
        <el-form-item label="发件人地址">
          <el-input v-model="form.smtp_from_email" style="width: 300px" placeholder="留空则使用邮箱账号" />
        </el-form-item>
        <el-form-item>
          <span style="font-size: 12px; color: #909399">测试邮件将发送到您的邮箱账号（smtp_user）</span>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSave" :loading="saving">保存配置</el-button>
          <el-button @click="handleTest" :loading="testing" :disabled="!configured">发送测试邮件</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import client from '../api/client'

const MASKED = '******'

const configured = ref(false)
const saving = ref(false)
const testing = ref(false)

const form = reactive({
  smtp_host: '',
  smtp_port: 465,
  smtp_user: '',
  smtp_password: '',
  smtp_from_email: '',
})

async function load() {
  try {
    const r = await client.get('/email-config')
    if (r.data.success) {
      const d = r.data
      form.smtp_host = d.smtp_host || ''
      form.smtp_port = d.smtp_port || 465
      form.smtp_user = d.smtp_user || ''
      form.smtp_password = d.smtp_password || '' // 已配置时为掩码 ******
      form.smtp_from_email = d.smtp_from_email || ''
      configured.value = !!d.configured
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '读取配置失败')
  }
}

async function handleSave() {
  if (!form.smtp_host || !form.smtp_user || !form.smtp_password) {
    ElMessage.warning('SMTP服务器、邮箱账号、密码/授权码为必填项')
    return
  }
  saving.value = true
  try {
    const r = await client.put('/email-config', { ...form })
    if (r.data.success) {
      configured.value = !!r.data.configured
      form.smtp_password = r.data.smtp_password || '' // 服务端返回掩码
      ElMessage.success('邮箱配置已保存')
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleTest() {
  testing.value = true
  try {
    const payload = { ...form }
    if (!payload.smtp_password || payload.smtp_password === MASKED) {
      payload.smtp_password = MASKED // 未改密码时带掩码，由后端解析为已存密码
    }
    const r = await client.post('/email-config/test', payload)
    if (r.data.success) {
      ElMessage.success(r.data.message || '测试邮件已发送')
    } else {
      ElMessage.error(r.data.error || '发送失败')
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '发送失败')
  } finally {
    testing.value = false
  }
}

onMounted(load)
</script>
