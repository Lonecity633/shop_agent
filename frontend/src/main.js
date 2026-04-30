import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import './style.css'
import App from './App.vue'
import router from './router'
import { useAuthStore } from '@/stores/auth'

async function bootstrap() {
  const app = createApp(App)
  const pinia = createPinia()

  app.use(pinia)

  const authStore = useAuthStore(pinia)
  if (authStore.token) {
    try {
      await authStore.fetchMe()
    } catch {
      authStore.clearAuth()
    }
  }

  app.use(router).use(ElementPlus).mount('#app')
}

bootstrap()
