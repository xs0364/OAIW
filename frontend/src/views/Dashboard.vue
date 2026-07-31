<template>
  <div class="dashboard">
    <h2>工作台</h2>
    <p class="welcome-text">欢迎回来，{{ auth.displayName }}！今天有 {{ pendingCount }} 个待处理任务</p>

    <!-- 快捷操作 -->
    <el-row :gutter="20" style="margin-bottom: 20px">
      <el-col :span="6" v-for="item in quickActions" :key="item.title">
        <el-card shadow="hover" class="action-card" @click="item.action">
          <el-icon :size="28" :color="item.color"><component :is="item.icon" /></el-icon>
          <div class="action-title">{{ item.title }}</div>
          <div class="action-desc">{{ item.desc }}</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 统计数据 -->
    <el-row :gutter="20" style="margin-bottom: 20px">
      <el-col :span="6" v-for="stat in stats" :key="stat.label">
        <el-card shadow="never">
          <div class="stat-value">{{ stat.value }}</div>
          <div class="stat-label">{{ stat.label }}</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 待办 + 动态 -->
    <el-row :gutter="20">
      <el-col :span="12">
        <el-card shadow="never">
          <template #header><b>待处理任务</b></template>
          <div v-if="tasks.length === 0" class="empty-state">暂无待处理任务</div>
          <div v-for="t in tasks" :key="t.id" class="task-item">
            <el-tag :type="t.priority === 'high' ? 'danger' : 'warning'" size="small">
              {{ t.type }}
            </el-tag>
            <span style="margin-left: 8px">{{ t.content }}</span>
          </div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never">
          <template #header><b>最近操作</b></template>
          <div v-if="recentOps.length === 0" class="empty-state">暂无操作记录</div>
          <div v-for="op in recentOps" :key="op.id" class="task-item">
            <el-tag size="small">{{ op.action }}</el-tag>
            <span style="margin-left: 8px; color: #606266">{{ op.detail }}</span>
            <span style="float: right; color: #c0c4cc; font-size: 12px">{{ op.time }}</span>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../store/auth'
import { Ship, TakeawayBox, Monitor, ChatDotSquare } from '@element-plus/icons-vue'

const router = useRouter()
const auth = useAuthStore()
const pendingCount = ref(3)

const quickActions = [
  { title: '空运操作', desc: '新建空运订单', icon: TakeawayBox, color: '#409eff', action: () => router.push('/air-freight') },
  { title: '海运操作', desc: '新建海运订单', icon: Ship, color: '#67c23a', action: () => router.push('/sea-freight') },
  { title: 'RPA任务', desc: '运行自动化', icon: Monitor, color: '#e6a23c', action: () => router.push('/rpa-tasks') },
  { title: 'AI助手', desc: '智能问答', icon: ChatDotSquare, color: '#9b59b6', action: () => router.push('/agent-chat') },
]

const stats = [
  { label: '进行中订单', value: '12' },
  { label: '待确认提单', value: '5' },
  { label: '待收款', value: '8' },
  { label: '已完成本月', value: '46' },
]

const tasks = ref([
  { id: 1, type: '空运', priority: 'high', content: 'SZX-SVO 航班确认 — 业务单号 O20240701' },
  { id: 2, type: '海运', priority: 'medium', content: '盐田-汉堡 补料待提交 — 截关 7/5' },
  { id: 3, type: '整柜', priority: 'high', content: 'AMS/ISF 需提交 — 船名 MSC ARIANE' },
])

const recentOps = ref([
  { id: 1, action: '提单确认', detail: 'O20240628-空运-达飞 提单已确认', time: '10:30' },
  { id: 2, action: 'RPA查价', detail: 'MSK 盐田-鹿特丹 运价已更新', time: '09:15' },
  { id: 3, action: '保函生成', detail: '非危保函已自动生成 — 电池货物', time: '昨天' },
])
</script>

<style scoped>
.welcome-text {
  color: #606266;
  margin-bottom: 20px;
}
.action-card {
  cursor: pointer;
  text-align: center;
  padding: 10px 0;
}
.action-card:hover {
  transform: translateY(-2px);
  transition: all 0.3s;
}
.action-title {
  font-size: 14px;
  font-weight: bold;
  margin-top: 8px;
}
.action-desc {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}
.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: #303133;
  text-align: center;
}
.stat-label {
  text-align: center;
  color: #909399;
  font-size: 13px;
  margin-top: 4px;
}
.task-item {
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
  font-size: 13px;
}
.empty-state {
  text-align: center;
  color: #c0c4cc;
  padding: 30px 0;
}
</style>
