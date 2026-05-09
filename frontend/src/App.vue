<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const isAuthPage = computed(() => ['/login', '/register'].includes(route.path))
const userRole = computed(() => authStore.user?.role || '')
const isLoggedIn = computed(() => authStore.isLoggedIn)

const isAdmin = computed(() => userRole.value === 'admin')
const isSeller = computed(() => userRole.value === 'seller')

const displayName = computed(() => authStore.user?.display_name || authStore.user?.email || '用户')

function toLogin(redirect = '/products') {
  router.push({ path: '/login', query: { redirect } })
}

function ensureLogin(path) {
  if (!isLoggedIn.value) {
    toLogin(path)
    return false
  }
  return true
}

function goHome() {
  if (isAdmin.value) {
    router.push('/admin/dashboard')
    return
  }
  if (isSeller.value) {
    router.push('/seller/center')
    return
  }
  router.push('/products')
}

function goFavorites() {
  if (!ensureLogin('/favorites')) return
  router.push('/favorites')
}

function goOrders() {
  if (!ensureLogin('/orders')) return
  router.push('/orders')
}

function goCart() {
  if (!ensureLogin('/cart')) return
  router.push('/cart')
}

function goCheckout() {
  if (!ensureLogin('/checkout')) return
  router.push('/checkout')
}

function goRefunds() {
  if (!ensureLogin('/refunds')) return
  router.push('/refunds')
}

function goRegister() {
  router.push('/register')
}

function goProfile() {
  if (!ensureLogin('/profile')) return
  router.push('/profile')
}

async function handleLogout() {
  await authStore.logout()
  router.push('/products')
}

function contactService() {
  if (!ensureLogin('/support/chat')) return
  router.push('/support/chat')
}
</script>

<template>
  <div class="layout">
    <header v-if="!isAuthPage" class="top-header">
      <div class="header-inner">
        <div class="brand" @click="goHome">京选商城</div>

        <template v-if="isAdmin">
          <nav class="left-nav">
            <button class="nav-btn" @click="router.push('/admin/dashboard')">管理后台</button>
            <button class="nav-btn" @click="router.push('/orders')">订单监控</button>
          </nav>
          <nav class="right-nav">
            <button class="nav-btn" @click="goProfile">{{ displayName }}</button>
            <button class="nav-btn" @click="handleLogout">退出</button>
          </nav>
        </template>

        <template v-else-if="isSeller">
          <nav class="left-nav">
            <button class="nav-btn" @click="router.push('/seller/center')">店铺资料</button>
            <button class="nav-btn" @click="router.push('/seller/products')">我的商品</button>
            <button class="nav-btn" @click="router.push('/orders')">订单列表</button>
            <button class="nav-btn" @click="goRefunds">退款工单</button>
            <button class="nav-btn" @click="contactService">客服</button>
          </nav>
          <nav class="right-nav">
            <button class="nav-btn" @click="goProfile">{{ displayName }}</button>
            <button class="nav-btn" @click="handleLogout">退出</button>
          </nav>
        </template>

        <template v-else>
          <nav class="left-nav">
            <button class="nav-btn" @click="goHome">商城首页</button>
            <button class="nav-btn" @click="goFavorites">我的收藏</button>
            <button class="nav-btn" @click="goOrders">我的订单</button>
            <button class="nav-btn" @click="goRefunds">退款中心</button>
          </nav>

          <nav class="right-nav">
            <button class="nav-btn" @click="contactService">客服</button>
            <button v-if="!isLoggedIn" class="nav-btn" @click="toLogin('/products')">你好请登录</button>
            <button v-else class="nav-btn" @click="goProfile">你好，{{ displayName }}</button>
            <button v-if="!isLoggedIn" class="nav-btn" @click="goRegister">注册</button>
            <button v-else class="nav-btn" @click="handleLogout">退出</button>
            <button class="nav-btn" @click="goCheckout">去结算</button>
            <button class="nav-btn cart-btn" @click="goCart">购物车</button>
          </nav>
        </template>
      </div>
    </header>

    <main class="content" :class="{ 'content-auth': isAuthPage }">
      <router-view />
    </main>
  </div>
</template>

<style scoped>
.layout {
  min-height: 100vh;
  background: var(--jd-bg);
}

.top-header {
  position: sticky;
  top: 0;
  z-index: 30;
  border-bottom: 1px solid #f0d8cf;
  background: linear-gradient(180deg, #fff 0%, #fff9f5 100%);
}

.header-inner {
  width: min(1280px, calc(100vw - 30px));
  margin: 0 auto;
  min-height: 62px;
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 14px;
}

.brand {
  color: #d73a1f;
  font-weight: 800;
  font-size: 21px;
  cursor: pointer;
}

.left-nav,
.right-nav {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.right-nav {
  justify-content: flex-end;
}

.nav-btn {
  border: 0;
  background: transparent;
  color: #333;
  cursor: pointer;
  padding: 6px 8px;
  border-radius: 6px;
}

.nav-btn:hover {
  color: #d73a1f;
  background: #fff1eb;
}

.cart-btn {
  color: #fff;
  background: #d73a1f;
}

.cart-btn:hover {
  color: #fff;
  background: #bf2f16;
}

.content {
  width: min(1280px, calc(100vw - 30px));
  margin: 0 auto;
  padding: 18px 0 30px;
}

.content-auth {
  width: 100%;
  padding: 0;
}

@media (max-width: 980px) {
  .header-inner {
    grid-template-columns: 1fr;
    gap: 8px;
    padding: 10px 0;
  }

  .right-nav {
    justify-content: flex-start;
  }

  .content {
    width: min(1280px, calc(100vw - 18px));
  }
}
</style>
