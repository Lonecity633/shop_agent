import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { getMe, login as loginApi, logout as logoutApi, register as registerApi, updateMe } from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))

  const isLoggedIn = computed(() => Boolean(token.value))
  const role = computed(() => user.value?.role || '')

  function setAuth(authToken, userInfo) {
    token.value = authToken
    user.value = userInfo
    localStorage.setItem('token', authToken)
    localStorage.setItem('user', JSON.stringify(userInfo))
  }

  function clearAuth() {
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }

  async function register(payload) {
    return registerApi(payload)
  }

  async function login(payload) {
    const res = await loginApi(payload)
    const accessToken = res.data?.access_token
    if (!accessToken) {
      throw new Error('登录返回缺少 access_token')
    }
    localStorage.setItem('token', accessToken)
    token.value = accessToken

    const meRes = await getMe()
    user.value = meRes.data
    localStorage.setItem('user', JSON.stringify(meRes.data))
    return { loginRes: res, meRes }
  }

  async function fetchMe() {
    if (!token.value) return null
    const res = await getMe()
    user.value = res.data
    localStorage.setItem('user', JSON.stringify(res.data))
    return res.data
  }

  async function logout() {
    try {
      if (token.value) {
        await logoutApi()
      }
    } finally {
      clearAuth()
    }
  }

  async function updateProfile(payload) {
    const res = await updateMe(payload)
    user.value = res.data
    localStorage.setItem('user', JSON.stringify(res.data))
    return res
  }

  return {
    token,
    user,
    role,
    isLoggedIn,
    setAuth,
    clearAuth,
    register,
    login,
    fetchMe,
    updateProfile,
    logout,
  }
})
