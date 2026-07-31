import axios from 'axios'
import { ElMessage } from 'element-plus'

const client = axios.create({
  baseURL: '/api',
  timeout: 180000,
})

// 请求拦截器：自动带 Token
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('oaiw_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器：统一处理错误（只处理 401 跳转，具体业务错误由各调用方自己处理）
client.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status
    if (status === 401) {
      localStorage.removeItem('oaiw_token')
      localStorage.removeItem('oaiw_user')
      window.location.href = '/login'
    }
    // 不全局弹 ElMessage.error —— 各调用方自己的 catch 会处理
    return Promise.reject(error)
  }
)

export default client

// ===== Auth API =====
export const authAPI = {
  login(data) {
    return client.post('/auth/login', data)
  },
  register(data) {
    return client.post('/auth/register', data)
  },
  getMe() {
    return client.get('/auth/me')
  },
}

// ===== Health =====
export const systemAPI = {
  health() {
    return client.get('/health')
  },
}
