import axios from 'axios'

const authClient = axios.create({
  baseURL: 'http://127.0.0.1:8000/api/auth',
  timeout: 10000,
})

authClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

authClient.interceptors.response.use(
  (response) => response.data,
  (error) => Promise.reject(error)
)

export function register(payload) {
  return authClient.post('/register', payload)
}

export function login(payload) {
  return authClient.post('/login', payload)
}

export function logout() {
  return authClient.post('/logout')
}

export function getMe() {
  return authClient.get('/me')
}

export function updateMe(payload) {
  return authClient.patch('/me', payload)
}
