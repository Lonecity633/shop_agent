import axios from 'axios'

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1'

const request = axios.create({
  baseURL: apiBaseUrl,
  timeout: 10000,
})

request.interceptors.request.use(
  (config) => {
    // 预留 JWT 注入逻辑
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

request.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const status = error?.response?.status
    if (status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      const redirect = `${window.location.pathname}${window.location.search}`
      const query = redirect ? `?redirect=${encodeURIComponent(redirect)}` : ''
      if (!window.location.pathname.startsWith('/login')) {
        window.location.href = `/login${query}`
      }
    }
    return Promise.reject(error)
  }
)

export default request
