<template>
  <el-container style="height: 100vh">
    <!-- 侧边栏 -->
    <el-aside :width="isCollapse ? '64px' : '220px'" class="oaiw-sidebar">
      <div class="logo-area">
        <span v-if="!isCollapse" class="logo-text">OAIW</span>
        <span v-else class="logo-mini">O</span>
      </div>
      <el-menu
        :default-active="route.path"
        :collapse="isCollapse"
        background-color="#1d1e1f"
        text-color="#bfcbd9"
        active-text-color="#409eff"
        router
      >
        <el-menu-item index="/dashboard">
          <el-icon><Odometer /></el-icon>
          <span>工作台</span>
        </el-menu-item>
        <el-menu-item index="/air-freight">
          <el-icon><TakeawayBox /></el-icon>
          <span>空运操作</span>
        </el-menu-item>
        <el-menu-item index="/sea-freight">
          <el-icon><Ship /></el-icon>
          <span>海运操作</span>
        </el-menu-item>
        <el-menu-item index="/fcl">
          <el-icon><Box /></el-icon>
          <span>整柜FCL</span>
        </el-menu-item>
        <el-menu-item index="/rpa-tasks">
          <el-icon><Monitor /></el-icon>
          <span>RPA自动化</span>
        </el-menu-item>
        <el-menu-item index="/agent-chat">
          <el-icon><ChatDotSquare /></el-icon>
          <span>AI助手</span>
        </el-menu-item>
        <el-menu-item index="/knowledge">
          <el-icon><Reading /></el-icon>
          <span>知识库</span>
        </el-menu-item>
        <el-menu-item index="/documents">
          <el-icon><FolderOpened /></el-icon>
          <span>文档管理</span>
        </el-menu-item>
        <el-menu-item v-if="auth.isAdmin" index="/users">
          <el-icon><UserFilled /></el-icon>
          <span>用户管理</span>
        </el-menu-item>
        <el-menu-item v-if="auth.isAdmin" index="/settings">
          <el-icon><Setting /></el-icon>
          <span>系统设置</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <!-- 主区域 -->
    <el-container>
      <!-- 顶部栏 -->
      <el-header class="oaiw-header">
        <div class="header-left">
          <el-button text @click="isCollapse = !isCollapse">
            <el-icon><Fold v-if="!isCollapse" /><Expand v-else /></el-icon>
          </el-button>
          <el-breadcrumb separator="/" style="margin-left: 16px">
            <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item v-if="route.meta.title">{{ route.meta.title }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="header-right">
          <el-dropdown trigger="click">
            <span class="user-info">
              <el-avatar :size="32" icon="UserFilled" />
              <span style="margin-left: 8px">{{ auth.displayName }}</span>
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-item @click="showNotify = true">
                <el-icon><Message /></el-icon>通知设置
              </el-dropdown-item>
              <el-dropdown-item @click="showChangePwd = true">
                <el-icon><Key /></el-icon>修改密码
              </el-dropdown-item>
              <el-dropdown-item divided @click="handleLogout">
                <el-icon><SwitchButton /></el-icon>退出登录
              </el-dropdown-item>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <!-- 内容 -->
      <el-main class="oaiw-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>

  <!-- 通知设置对话框 -->
  <el-dialog v-model="showNotify" title="通知设置" width="450px">
    <el-form :model="notifyForm" label-width="100px">
      <el-form-item label="通知邮箱">
        <el-input v-model="notifyForm.email" placeholder="接收通知的邮箱地址" />
      </el-form-item>
      <el-form-item label="通知类型">
        <div style="display:flex;flex-direction:column;gap:10px">
          <el-checkbox v-model="notifyForm.on_quote">收到新报价单时邮件通知</el-checkbox>
          <el-checkbox v-model="notifyForm.on_order">有新订单时邮件通知</el-checkbox>
          <el-checkbox v-model="notifyForm.on_rpa">RPA 任务完成时邮件通知</el-checkbox>
          <el-checkbox v-model="notifyForm.on_expiry">价格/合约即将到期时邮件通知</el-checkbox>
        </div>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="showNotify = false">取消</el-button>
      <el-button type="primary" :loading="notifySaving" @click="handleSaveNotify">保存</el-button>
    </template>
  </el-dialog>

  <!-- 修改密码对话框 -->
  <el-dialog v-model="showChangePwd" title="修改密码" width="400px">
    <el-form :model="pwdForm" label-width="80px">
      <el-form-item label="旧密码">
        <el-input v-model="pwdForm.old_password" type="password" show-password />
      </el-form-item>
      <el-form-item label="新密码">
        <el-input v-model="pwdForm.new_password" type="password" show-password />
      </el-form-item>
      <el-form-item label="确认密码">
        <el-input v-model="pwdForm.confirm" type="password" show-password />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="showChangePwd = false">取消</el-button>
      <el-button type="primary" :loading="pwdSaving" @click="handleChangePwd">确认修改</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../store/auth'
import { ElMessage } from 'element-plus'
import {
  Odometer, TakeawayBox, Ship, Box, Monitor,
  ChatDotSquare, Reading, FolderOpened, Setting, Fold, Expand,
  UserFilled, ArrowDown, SwitchButton, Key, Message,
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const isCollapse = ref(false)

// 通知设置
const showNotify = ref(false)
const notifyLoaded = ref(false)
watch(showNotify, async (v) => {
  if (v && !notifyLoaded.value) {
    try {
      const { default: client } = await import('../api/client')
      const r = await client.get('/auth/notify-settings')
      if (r.data.success) {
        notifyForm.value = { email: '', on_quote: false, on_order: false, on_rpa: false, on_expiry: false, ...r.data.data }
        notifyLoaded.value = true
      }
    } catch {}
  }
})
const notifySaving = ref(false)
const notifyForm = ref({ email: '', on_quote: false, on_order: false, on_rpa: false, on_expiry: false })

async function handleSaveNotify() {
  notifySaving.value = true
  try {
    const { default: client } = await import('../api/client')
    await client.put('/auth/notify-settings', notifyForm.value)
    ElMessage.success('通知设置已保存')
    showNotify.value = false
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally {
    notifySaving.value = false
  }
}

// 修改密码
const showChangePwd = ref(false)
const pwdSaving = ref(false)
const pwdForm = ref({ old_password: '', new_password: '', confirm: '' })

async function handleChangePwd() {
  if (!pwdForm.value.old_password || !pwdForm.value.new_password) {
    ElMessage.warning('请填写完整')
    return
  }
  if (pwdForm.value.new_password !== pwdForm.value.confirm) {
    ElMessage.warning('两次密码不一致')
    return
  }
  if (pwdForm.value.new_password.length < 4) {
    ElMessage.warning('新密码至少4位')
    return
  }
  pwdSaving.value = true
  try {
    const { default: client } = await import('../api/client')
    await client.post('/auth/change-password', {
      old_password: pwdForm.value.old_password,
      new_password: pwdForm.value.new_password,
    })
    ElMessage.success('密码修改成功')
    showChangePwd.value = false
    pwdForm.value = { old_password: '', new_password: '', confirm: '' }
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '修改失败')
  } finally {
    pwdSaving.value = false
  }
}

function handleLogout() {
  auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.logo-area {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}
.logo-text {
  font-size: 22px;
  font-weight: bold;
  color: #409eff;
  letter-spacing: 2px;
}
.logo-mini {
  font-size: 20px;
  font-weight: bold;
  color: #409eff;
}
.header-left {
  display: flex;
  align-items: center;
}
.header-right {
  display: flex;
  align-items: center;
}
.user-info {
  display: flex;
  align-items: center;
  cursor: pointer;
}
</style>
