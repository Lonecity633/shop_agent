<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getAddresses } from '@/api/address'
import { createOrder } from '@/api/order'
import { addCartItem } from '@/api/cart'
import { getCategories } from '@/api/category'
import { addFavorite, getFavorites, removeFavorite } from '@/api/favorite'
import { getProducts } from '@/api/product'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const loading = ref(false)
const products = ref([])
const categories = ref([])
const activeCategory = ref('all')
const keyword = ref('')

const creatingOrderId = ref(null)
const orderDialogVisible = ref(false)
const selectedProduct = ref(null)
const orderForm = reactive({ quantity: 1 })
const addresses = ref([])
const selectedAddressId = ref(null)
let stockRefreshTimer = null

const favoriteProductIds = ref(new Set())

const FALLBACK_IMAGE =
  'data:image/svg+xml;utf8,' +
  encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="640"><defs><linearGradient id="g" x1="0" x2="1" y1="0" y2="1"><stop stop-color="#fff0ec" offset="0"/><stop stop-color="#ffe2cb" offset="1"/></linearGradient></defs><rect fill="url(#g)" width="640" height="640" rx="28"/><text x="50%" y="49%" dominant-baseline="middle" text-anchor="middle" font-size="42" fill="#c14a33" font-family="Arial">京选商城</text><text x="50%" y="59%" dominant-baseline="middle" text-anchor="middle" font-size="24" fill="#9d5e49" font-family="Arial">暂无商品图</text></svg>'
  )

const hasProducts = computed(() => products.value.length > 0)

function normalizeImageUrl(rawUrl) {
  const input = String(rawUrl || '').trim()
  if (!input) return ''
  try {
    const parsed = new URL(input)
    const candidate = parsed.searchParams.get('mediaurl') || parsed.searchParams.get('murl')
    if (candidate) {
      const direct = new URL(candidate)
      if (['http:', 'https:'].includes(direct.protocol)) {
        return direct.toString()
      }
    }
    return parsed.toString()
  } catch {
    return input
  }
}

function normalizeProducts(list) {
  return (list || []).map((item) => {
    const imageUrls = Array.isArray(item.image_urls)
      ? item.image_urls.map((url) => normalizeImageUrl(url)).filter(Boolean)
      : []
    return {
      ...item,
      image_urls: imageUrls,
      cover: imageUrls[0] || FALLBACK_IMAGE,
    }
  })
}

function formatPrice(value) {
  const num = Number(value || 0)
  return Number.isFinite(num) ? num.toFixed(2) : '0.00'
}

function resolveImage(event) {
  event.target.src = FALLBACK_IMAGE
}

function stockText(stock) {
  if (stock <= 0) return '无货'
  if (stock <= 5) return `紧张 · 仅剩 ${stock}`
  return `有货 · 库存 ${stock}`
}

function stockTagType(stock) {
  if (stock <= 0) return 'danger'
  if (stock <= 5) return 'warning'
  return 'success'
}

function ensureLoginForAction() {
  if (!authStore.isLoggedIn) {
    router.push({ path: '/login', query: { redirect: '/products' } })
    return false
  }
  return true
}

async function fetchCategories() {
  try {
    const res = await getCategories()
    categories.value = res.data || []
  } catch {
    categories.value = []
  }
}

async function fetchProducts() {
  loading.value = true
  try {
    const params = {}
    const trimmed = keyword.value.trim()
    if (trimmed) params.keyword = trimmed
    if (activeCategory.value !== 'all') {
      params.category_id = Number(activeCategory.value)
    }
    if (!trimmed && activeCategory.value === 'all') {
      params.random = true
    }

    const res = await getProducts(params)
    products.value = normalizeProducts(res.data)
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '获取商品列表失败')
  } finally {
    loading.value = false
  }
}

async function fetchFavorites() {
  if (!authStore.isLoggedIn) {
    favoriteProductIds.value = new Set()
    return
  }
  try {
    const res = await getFavorites()
    const ids = new Set((res.data || []).map((item) => Number(item.product_id)))
    favoriteProductIds.value = ids
  } catch {
    favoriteProductIds.value = new Set()
  }
}

async function fetchAddressesForOrder() {
  if (!authStore.isLoggedIn) {
    addresses.value = []
    selectedAddressId.value = null
    return
  }
  try {
    const res = await getAddresses()
    const list = res.data || []
    addresses.value = list
    const defaultAddress = list.find((item) => item.is_default)
    selectedAddressId.value = (defaultAddress || list[0])?.id || null
  } catch (error) {
    addresses.value = []
    selectedAddressId.value = null
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '加载地址失败')
  }
}

function isFavorited(productId) {
  return favoriteProductIds.value.has(Number(productId))
}

async function toggleFavorite(product) {
  if (!ensureLoginForAction()) return

  try {
    if (isFavorited(product.id)) {
      await removeFavorite(product.id)
      favoriteProductIds.value.delete(Number(product.id))
      ElMessage.success('已取消收藏')
    } else {
      await addFavorite(product.id)
      favoriteProductIds.value.add(Number(product.id))
      ElMessage.success('已加入收藏')
    }
    favoriteProductIds.value = new Set(favoriteProductIds.value)
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '操作失败')
  }
}

async function addToCart(product) {
  if (!ensureLoginForAction()) return
  try {
    await addCartItem({ product_id: product.id, quantity: 1 })
    ElMessage.success('已加入购物车')
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '加入购物车失败')
  }
}

function chooseCategory(categoryId) {
  activeCategory.value = categoryId
  fetchProducts()
}

function handleSearch() {
  fetchProducts()
}

function handleReset() {
  keyword.value = ''
  activeCategory.value = 'all'
  fetchProducts()
}

async function openOrderDialog(product) {
  if (!ensureLoginForAction()) return
  await fetchAddressesForOrder()
  if (!addresses.value.length) {
    ElMessage.warning('请先在地址管理中创建收货地址后再下单')
    return
  }
  selectedProduct.value = product
  orderForm.quantity = 1
  orderDialogVisible.value = true
}

async function handleCreateOrder() {
  if (!selectedProduct.value) return
  if (!selectedAddressId.value) {
    ElMessage.warning('请选择收货地址')
    return
  }
  const product = selectedProduct.value
  creatingOrderId.value = product.id
  try {
    const res = await createOrder({
      product_id: product.id,
      quantity: orderForm.quantity,
      address_id: Number(selectedAddressId.value),
    })
    ElMessage.success(res.message || '下单成功')
    orderDialogVisible.value = false
    selectedProduct.value = null
    await fetchProducts()
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '下单失败')
  } finally {
    creatingOrderId.value = null
  }
}

async function refreshStorefrontOnVisible() {
  if (document.visibilityState !== 'visible') return
  await fetchProducts()
  await fetchFavorites()
}

async function refreshStorefrontOnFocus() {
  await fetchProducts()
}

function startStockRefreshTimer() {
  stopStockRefreshTimer()
  stockRefreshTimer = window.setInterval(() => {
    if (document.visibilityState === 'visible') {
      fetchProducts()
    }
  }, 15000)
}

function stopStockRefreshTimer() {
  if (stockRefreshTimer) {
    window.clearInterval(stockRefreshTimer)
    stockRefreshTimer = null
  }
}

onMounted(async () => {
  await fetchCategories()
  await fetchProducts()
  await fetchFavorites()
  document.addEventListener('visibilitychange', refreshStorefrontOnVisible)
  window.addEventListener('focus', refreshStorefrontOnFocus)
  startStockRefreshTimer()
})

onUnmounted(() => {
  document.removeEventListener('visibilitychange', refreshStorefrontOnVisible)
  window.removeEventListener('focus', refreshStorefrontOnFocus)
  stopStockRefreshTimer()
})
</script>

<template>
  <div class="market-page">
    <section class="market-head page-block">
      <div class="title-line">
        <h1 class="page-title">京选商城</h1>
        <p class="page-subtitle">品质好物，今日直达</p>
      </div>

      <div class="search-row">
        <el-input
          v-model="keyword"
          placeholder="搜索商品名称或描述"
          clearable
          class="search-input"
          @keyup.enter="handleSearch"
        />
        <el-button type="primary" @click="handleSearch">搜索</el-button>
        <el-button @click="handleReset">重置</el-button>
      </div>

      <div class="category-row">
        <el-tag
          class="category-tag"
          :effect="activeCategory === 'all' ? 'dark' : 'plain'"
          type="danger"
          @click="chooseCategory('all')"
        >
          全部
        </el-tag>
        <el-tag
          v-for="category in categories"
          :key="category.id"
          class="category-tag"
          :effect="String(activeCategory) === String(category.id) ? 'dark' : 'plain'"
          type="danger"
          @click="chooseCategory(String(category.id))"
        >
          {{ category.name }}
        </el-tag>
      </div>
    </section>

    <section v-loading="loading" class="goods-grid">
      <article v-for="product in products" :key="product.id" class="goods-card page-block">
        <div class="cover-wrap">
          <img :src="product.cover" class="cover" alt="商品图" @error="resolveImage" />
          <el-tag class="stock-tag" :type="stockTagType(product.stock)" size="small">
            {{ stockText(product.stock) }}
          </el-tag>
        </div>

        <div class="card-body">
          <h3 class="goods-title">{{ product.name }}</h3>
          <p class="goods-desc">{{ product.description || '暂无描述' }}</p>
          <div class="meta-row">分类：{{ product.category_name || '其他' }}</div>
          <div class="price-row">
            <span class="currency">¥</span>
            <span class="price">{{ formatPrice(product.price) }}</span>
          </div>

          <div class="btn-row">
            <el-button
              type="primary"
              class="buy-btn"
              :disabled="product.stock <= 0"
              @click="openOrderDialog(product)"
            >
              立即下单
            </el-button>
            <el-button plain @click="addToCart(product)">加入购物车</el-button>
            <el-button :type="isFavorited(product.id) ? 'danger' : 'default'" plain @click="toggleFavorite(product)">
              {{ isFavorited(product.id) ? '已收藏' : '收藏' }}
            </el-button>
          </div>
        </div>
      </article>
    </section>

    <el-empty v-if="!loading && !hasProducts" description="没有找到符合条件的商品" class="page-block" />

    <el-dialog v-model="orderDialogVisible" title="确认下单" width="520px">
      <div v-if="selectedProduct" class="confirm-panel">
        <img :src="selectedProduct.cover" class="confirm-image" alt="商品图" @error="resolveImage" />
        <div class="confirm-main">
          <h3>{{ selectedProduct.name }}</h3>
          <p>{{ selectedProduct.description || '暂无描述' }}</p>
          <div class="confirm-line">
            <span>单价</span>
            <strong>¥{{ formatPrice(selectedProduct.price) }}</strong>
          </div>
          <div class="confirm-line">
            <span>数量</span>
            <el-input-number v-model="orderForm.quantity" :min="1" :max="Math.max(selectedProduct.stock || 1, 1)" />
          </div>
          <div class="confirm-line">
            <span>收货地址</span>
            <el-select v-model="selectedAddressId" placeholder="请选择收货地址" style="width: 260px">
              <el-option
                v-for="addr in addresses"
                :key="addr.id"
                :label="`${addr.receiver_name} ${addr.receiver_phone} ${addr.province}${addr.city}${addr.district || ''}${addr.detail_address}`"
                :value="addr.id"
              />
            </el-select>
          </div>
          <div class="confirm-line total">
            <span>应付金额</span>
            <strong>¥{{ formatPrice(Number(selectedProduct.price) * orderForm.quantity) }}</strong>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="orderDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="creatingOrderId === selectedProduct?.id" @click="handleCreateOrder">
          确认下单
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.market-page {
  display: grid;
  gap: 18px;
}

.market-head {
  padding: 20px;
  display: grid;
  gap: 14px;
}

.title-line {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.page-title {
  margin: 0;
}

.page-subtitle {
  margin: 0;
  color: #666;
}

.search-row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.search-input {
  width: min(560px, 100%);
}

.category-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.category-tag {
  cursor: pointer;
}

.goods-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(245px, 1fr));
  gap: 16px;
  align-items: stretch;
}

.goods-card {
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.cover-wrap {
  position: relative;
  height: 210px;
  background: #fff7f3;
}

.cover {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.stock-tag {
  position: absolute;
  left: 10px;
  bottom: 10px;
}

.card-body {
  padding: 14px;
  display: grid;
  gap: 8px;
}

.goods-title {
  margin: 0;
  font-size: 17px;
}

.goods-desc {
  color: #666;
  margin: 0;
  min-height: 38px;
}

.meta-row {
  color: #6e6e6e;
  font-size: 13px;
}

.price-row {
  color: #d5391c;
}

.currency {
  font-size: 14px;
}

.price {
  font-size: 24px;
  font-weight: 700;
}

.btn-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.confirm-panel {
  display: grid;
  grid-template-columns: 140px 1fr;
  gap: 14px;
}

.confirm-image {
  width: 140px;
  height: 140px;
  object-fit: cover;
  border-radius: 8px;
}

.confirm-main {
  display: grid;
  gap: 10px;
}

.confirm-main h3,
.confirm-main p {
  margin: 0;
}

.confirm-line {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.confirm-line.total {
  color: #d5391c;
  font-weight: 700;
}

@media (max-width: 760px) {
  .confirm-panel {
    grid-template-columns: 1fr;
  }

  .confirm-image {
    width: 100%;
    height: 180px;
  }
}
</style>
