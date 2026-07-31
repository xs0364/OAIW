import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authAPI } from '../api/client'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(JSON.parse(localStorage.getItem('oaiw_user') || 'null'))
  const token = ref(localStorage.getItem('oaiw_token') || '')

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.role === 'admin')
  const displayName = computed(() => user.value?.display_name || user.value?.username || '')

  function setAuth(loginToken, loginUser) {
    token.value = loginToken
    user.value = loginUser
    localStorage.setItem('oaiw_token', loginToken)
    localStorage.setItem('oaiw_user', JSON.stringify(loginUser))
  }

  async function login(username, password) {
    const res = await authAPI.login({ username, password })
    setAuth(res.data.access_token, res.data.user)
    return res.data
  }

  async function register(data) {
    const res = await authAPI.register(data)
    setAuth(res.data.access_token, res.data.user)
    return res.data
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('oaiw_token')
    localStorage.removeItem('oaiw_user')
  }

  return { user, token, isLoggedIn, isAdmin, displayName, login, register, logout, setAuth }
})
