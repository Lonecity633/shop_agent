import { createRouter, createWebHistory } from 'vue-router'
import ProductList from '@/views/ProductList.vue'
import OrderList from '@/views/OrderList.vue'
import CheckoutView from '@/views/CheckoutView.vue'
import RefundCenter from '@/views/RefundCenter.vue'
import ProfileView from '@/views/ProfileView.vue'
import ForbiddenView from '@/views/ForbiddenView.vue'
import FavoritesView from '@/views/FavoritesView.vue'
import CartView from '@/views/CartView.vue'
import SupportChatView from '@/views/SupportChatView.vue'
import AdminDashboard from '@/views/admin/AdminDashboard.vue'
import KnowledgeManagement from '@/views/admin/KnowledgeManagement.vue'
import SellerCenter from '@/views/seller/SellerCenter.vue'
import MyProducts from '@/views/seller/MyProducts.vue'
import LoginView from '@/views/auth/LoginView.vue'
import RegisterView from '@/views/auth/RegisterView.vue'

const routes = [
  { path: '/', redirect: '/products' },
  { path: '/products', name: 'products', component: ProductList, meta: { disallowAdmin: true, disallowSeller: true } },
  { path: '/favorites', name: 'favorites', component: FavoritesView, meta: { requiresAuth: true, disallowAdmin: true, disallowSeller: true } },
  { path: '/cart', name: 'cart', component: CartView, meta: { requiresAuth: true, disallowAdmin: true, disallowSeller: true } },
  { path: '/orders', name: 'orders', component: OrderList, meta: { requiresAuth: true } },
  { path: '/checkout', name: 'checkout', component: CheckoutView, meta: { requiresAuth: true, disallowAdmin: true, disallowSeller: true } },
  { path: '/refunds', name: 'refunds', component: RefundCenter, meta: { requiresAuth: true, disallowAdmin: true } },
  { path: '/support/chat', name: 'support-chat', component: SupportChatView, meta: { requiresAuth: true, disallowAdmin: true } },
  { path: '/profile', name: 'profile', component: ProfileView, meta: { requiresAuth: true } },
  { path: '/admin/dashboard', name: 'admin-dashboard', component: AdminDashboard, meta: { requiresAuth: true, requiresAdmin: true } },
  { path: '/admin/knowledge', name: 'admin-knowledge', component: KnowledgeManagement, meta: { requiresAuth: true, requiresAdmin: true } },
  { path: '/seller/center', name: 'seller-center', component: SellerCenter, meta: { requiresAuth: true, requiresSeller: true } },
  { path: '/seller/products', name: 'seller-products', component: MyProducts, meta: { requiresAuth: true, requiresSeller: true } },
  { path: '/403', name: 'forbidden', component: ForbiddenView },
  { path: '/login', name: 'login', component: LoginView, meta: { guestOnly: true } },
  { path: '/register', name: 'register', component: RegisterView, meta: { guestOnly: true } },
]

const router = createRouter({ history: createWebHistory(), routes })

function roleHome(role) {
  if (role === 'admin') return '/admin/dashboard'
  if (role === 'seller') return '/seller/center'
  return '/products'
}

router.beforeEach((to) => {
  const token = localStorage.getItem('token')
  const userRaw = localStorage.getItem('user')
  let user = null
  try {
    user = userRaw ? JSON.parse(userRaw) : null
  } catch {
    user = null
  }
  const role = user?.role

  if (to.meta.requiresAuth && !token) return { path: '/login', query: { redirect: to.fullPath } }
  if (to.meta.requiresAdmin && role !== 'admin') return { path: '/403' }
  if (to.meta.requiresSeller && role !== 'seller') return { path: '/403' }
  if (to.meta.disallowAdmin && role === 'admin') return { path: roleHome(role) }
  if (to.meta.disallowSeller && role === 'seller') return { path: roleHome(role) }
  if (to.meta.guestOnly && token && user) return { path: roleHome(role) }

  return true
})

export default router
