import { ElMessage } from 'element-plus'
import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
  },
  {
    path: '/',
    component: () => import('../views/Layout.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('../views/Dashboard.vue'),
        meta: { title: '工作台', icon: 'Odometer' },
      },
      {
        path: 'air-freight',
        name: 'AirFreight',
        component: () => import('../views/AirFreight.vue'),
        meta: { title: '空运操作', icon: 'TakeawayBox' },
      },
      {
        path: 'sea-freight',
        name: 'SeaFreight',
        component: () => import('../views/SeaFreight.vue'),
        meta: { title: '海运操作', icon: 'Ship' },
      },
      {
        path: 'fcl',
        name: 'FCL',
        component: () => import('../views/FCL.vue'),
        meta: { title: '整柜FCL', icon: 'Box' },
      },
      {
        path: 'rpa-tasks',
        name: 'RpaTasks',
        component: () => import('../views/RpaTasks.vue'),
        meta: { title: 'RPA自动化', icon: 'Monitor' },
      },
      {
        path: 'merge-fill',
        name: 'MergeFill',
        component: () => import('../views/MergeFill.vue'),
        meta: { title: '佰信合并录入', icon: 'EditPen' },
      },
      {
        path: 'agent-chat',
        name: 'AgentChat',
        component: () => import('../views/AgentChat.vue'),
        meta: { title: 'AI助手', icon: 'ChatDotSquare' },
      },
      {
        path: 'documents',
        name: 'Documents',
        component: () => import('../views/Documents.vue'),
        meta: { title: '文档管理', icon: 'FolderOpened' },
      },
      {
        path: 'knowledge',
        name: 'Knowledge',
        component: () => import('../views/Knowledge.vue'),
        meta: { title: '知识库', icon: 'Reading' },
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('../views/Settings.vue'),
        meta: { title: '系统设置', icon: 'Setting', roles: ['admin'] },
      },
      {
        path: 'users',
        name: 'UserManagement',
        component: () => import('../views/UserManagement.vue'),
        meta: { title: '用户管理', icon: 'UserFilled', roles: ['admin'] },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 路由守卫：未登录跳转登录页；角色不足跳转工作台
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('oaiw_token')

  // 未登录 -> 登录页
  if (to.name !== 'Login' && !token) {
    return next({ name: 'Login' })
  }

  // 已登录 -> 检查角色权限
  const roles = to.meta?.roles
  if (roles && roles.length) {
    try {
      const user = JSON.parse(localStorage.getItem('oaiw_user') || '{}')
      if (!roles.includes(user.role)) {
        ElMessage?.warning?.('无权限访问该页面') || console.warn('无权限')
        return next({ name: 'Dashboard' })
      }
    } catch {
      return next({ name: 'Login' })
    }
  }

  next()
})

export default router
