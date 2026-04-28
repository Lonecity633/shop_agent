<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getFavorites, removeFavorite } from '@/api/favorite'

const router = useRouter()
const loading = ref(false)
const items = ref([])

const hasItems = computed(() => items.value.length > 0)

function formatPrice(value) {
  const num = Number(value || 0)
  return Number.isFinite(num) ? num.toFixed(2) : '0.00'
}

function resolveImage(event) {
  event.target.src = 'data:image/svg+xml;utf8,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="460" height="460"><rect width="100%" height="100%" fill="#fff3e6"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="#ca5b2b" font-size="22">暂无图片</text></svg>')
}

async function fetchFavorites() {
  loading.value = true
  try {
    const res = await getFavorites()
    items.value = res.data || []
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '获取收藏失败')
  } finally {
    loading.value = false
  }
}

async function handleRemove(productId) {
  try {
    await removeFavorite(productId)
    ElMessage.success('已取消收藏')
    await fetchFavorites()
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '取消收藏失败')
  }
}

function goHome() {
  router.push('/products')
}

onMounted(fetchFavorites)
</script>

<template>
  <div class="page-wrap">
    <div class="page-head">
      <h2>我的收藏</h2>
      <el-button @click="goHome">返回首页</el-button>
    </div>

    <section v-loading="loading" class="goods-grid">
      <article v-for="item in items" :key="item.id" class="goods-card">
        <img :src="item.product.image_urls?.[0]" class="cover" alt="商品图" @error="resolveImage" />
        <div class="meta">
          <div class="title">{{ item.product.name }}</div>
          <div class="desc">{{ item.product.description || '暂无描述' }}</div>
          <div class="price">¥{{ formatPrice(item.product.price) }}</div>
          <el-button type="danger" plain @click="handleRemove(item.product_id)">取消收藏</el-button>
        </div>
      </article>
    </section>

    <el-empty v-if="!loading && !hasItems" description="你还没有收藏商品" />
  </div>
</template>

<style scoped>
.page-wrap {
  display: grid;
  gap: 16px;
}

.page-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.goods-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 14px;
}

.goods-card {
  border: 1px solid #ecd8d2;
  border-radius: 12px;
  overflow: hidden;
  background: #fff;
}

.cover {
  width: 100%;
  height: 180px;
  object-fit: cover;
  background: #fff7f3;
}

.meta {
  padding: 10px;
  display: grid;
  gap: 8px;
}

.title {
  font-weight: 700;
}

.desc {
  color: #666;
  font-size: 13px;
  min-height: 36px;
}

.price {
  color: #d5391c;
  font-weight: 700;
}
</style>
