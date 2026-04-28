<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createOrder } from '@/api/order'
import { getCartItems, removeCartItem, updateCartItem } from '@/api/cart'

const router = useRouter()
const loading = ref(false)
const placingItemId = ref(null)
const items = ref([])

const hasItems = computed(() => items.value.length > 0)
const totalAmount = computed(() => {
  return items.value
    .filter((i) => i.selected)
    .reduce((sum, i) => sum + Number(i.product.price || 0) * Number(i.quantity || 0), 0)
})

function formatPrice(value) {
  const num = Number(value || 0)
  return Number.isFinite(num) ? num.toFixed(2) : '0.00'
}

async function fetchCart() {
  loading.value = true
  try {
    const res = await getCartItems()
    items.value = res.data || []
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '获取购物车失败')
  } finally {
    loading.value = false
  }
}

async function changeQuantity(item, quantity) {
  if (!quantity || quantity < 1) return
  try {
    await updateCartItem(item.id, { quantity })
    await fetchCart()
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '更新数量失败')
  }
}

async function toggleSelected(item, selected) {
  try {
    await updateCartItem(item.id, { selected })
    item.selected = selected
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '更新勾选状态失败')
  }
}

async function handleDelete(item) {
  try {
    await ElMessageBox.confirm(`确认删除「${item.product.name}」吗？`, '提示', { type: 'warning' })
    await removeCartItem(item.id)
    ElMessage.success('已删除')
    await fetchCart()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '删除失败')
    }
  }
}

async function handleOrder(item) {
  placingItemId.value = item.id
  try {
    await createOrder({ product_id: item.product_id, quantity: item.quantity })
    await removeCartItem(item.id)
    ElMessage.success('下单成功')
    await fetchCart()
    router.push('/orders')
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '下单失败')
  } finally {
    placingItemId.value = null
  }
}

onMounted(fetchCart)
</script>

<template>
  <div class="cart-page">
    <div class="cart-head">
      <h2>购物车</h2>
      <div class="summary">已选总额：<strong>¥{{ formatPrice(totalAmount) }}</strong></div>
    </div>

    <el-table v-loading="loading" :data="items" border stripe>
      <el-table-column label="选择" width="78">
        <template #default="scope">
          <el-checkbox :model-value="scope.row.selected" @change="(v) => toggleSelected(scope.row, Boolean(v))" />
        </template>
      </el-table-column>
      <el-table-column label="商品" min-width="250">
        <template #default="scope">
          <div class="product-cell">
            <img :src="scope.row.product.image_urls?.[0]" alt="商品" class="thumb" />
            <div class="title">{{ scope.row.product.name }}</div>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="单价" width="120">
        <template #default="scope">¥{{ formatPrice(scope.row.product.price) }}</template>
      </el-table-column>
      <el-table-column label="数量" width="180">
        <template #default="scope">
          <el-input-number
            :model-value="scope.row.quantity"
            :min="1"
            :max="Math.max(scope.row.product.stock || 1, 1)"
            @change="(v) => changeQuantity(scope.row, Number(v))"
          />
        </template>
      </el-table-column>
      <el-table-column label="小计" width="120">
        <template #default="scope">¥{{ formatPrice(Number(scope.row.product.price) * Number(scope.row.quantity)) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="scope">
          <div class="row-actions">
            <el-button
              type="primary"
              :disabled="!scope.row.selected"
              :loading="placingItemId === scope.row.id"
              @click="handleOrder(scope.row)"
            >
              下单
            </el-button>
            <el-button type="danger" plain @click="handleDelete(scope.row)">删除</el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!loading && !hasItems" description="购物车为空，去首页逛逛吧" />
  </div>
</template>

<style scoped>
.cart-page {
  display: grid;
  gap: 14px;
}

.cart-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.summary {
  color: #555;
}

.summary strong {
  color: #d5391c;
}

.product-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}

.thumb {
  width: 42px;
  height: 42px;
  object-fit: cover;
  border-radius: 6px;
  background: #fff4eb;
}

.title {
  font-weight: 600;
}

.row-actions {
  display: flex;
  gap: 8px;
}
</style>
