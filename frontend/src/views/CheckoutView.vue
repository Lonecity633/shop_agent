<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createAddress, deleteAddress, getAddresses, updateAddress } from '@/api/address'
import { getCartItems, removeCartItem } from '@/api/cart'
import { createOrder } from '@/api/order'

const router = useRouter()

const loading = ref(false)
const submitLoading = ref(false)
const cartItems = ref([])
const addresses = ref([])
const selectedAddressId = ref(null)

const addressDialogVisible = ref(false)
const addressSubmitting = ref(false)
const editingAddressId = ref(null)

const addressForm = reactive({
  receiver_name: '',
  receiver_phone: '',
  province: '',
  city: '',
  district: '',
  detail_address: '',
  is_default: false,
})

const selectedItems = computed(() => (cartItems.value || []).filter((item) => item.selected))
const selectedCount = computed(() => selectedItems.value.length)
const hasSelectedItems = computed(() => selectedCount.value > 0)
const hasAddresses = computed(() => addresses.value.length > 0)

const totalAmount = computed(() => {
  return selectedItems.value.reduce((sum, item) => {
    const unitPrice = Number(item?.product?.price || 0)
    const qty = Number(item?.quantity || 0)
    return sum + unitPrice * qty
  }, 0)
})

function formatPrice(value) {
  const num = Number(value || 0)
  return Number.isFinite(num) ? num.toFixed(2) : '0.00'
}

function normalizeAddressLabel(address) {
  return `${address.province}${address.city}${address.district || ''}${address.detail_address}`
}

function resetAddressForm() {
  editingAddressId.value = null
  addressForm.receiver_name = ''
  addressForm.receiver_phone = ''
  addressForm.province = ''
  addressForm.city = ''
  addressForm.district = ''
  addressForm.detail_address = ''
  addressForm.is_default = false
}

function openCreateAddress() {
  resetAddressForm()
  addressDialogVisible.value = true
}

function openEditAddress(address) {
  editingAddressId.value = address.id
  addressForm.receiver_name = address.receiver_name || ''
  addressForm.receiver_phone = address.receiver_phone || ''
  addressForm.province = address.province || ''
  addressForm.city = address.city || ''
  addressForm.district = address.district || ''
  addressForm.detail_address = address.detail_address || ''
  addressForm.is_default = Boolean(address.is_default)
  addressDialogVisible.value = true
}

async function fetchCartItems() {
  const res = await getCartItems()
  cartItems.value = res.data || []
}

function applyAddressSelection() {
  const list = addresses.value || []
  if (!list.length) {
    selectedAddressId.value = null
    return
  }

  const current = Number(selectedAddressId.value)
  const stillExists = list.some((item) => item.id === current)
  if (stillExists) return

  const defaultAddress = list.find((item) => item.is_default)
  selectedAddressId.value = (defaultAddress || list[0]).id
}

async function fetchAddresses() {
  const res = await getAddresses()
  addresses.value = res.data || []
  applyAddressSelection()
}

async function refreshPageData() {
  loading.value = true
  try {
    await Promise.all([fetchCartItems(), fetchAddresses()])
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '加载结算数据失败')
  } finally {
    loading.value = false
  }
}

async function submitAddress() {
  if (!addressForm.receiver_name.trim()) {
    ElMessage.warning('收件人不能为空')
    return
  }
  if (!addressForm.receiver_phone.trim()) {
    ElMessage.warning('联系电话不能为空')
    return
  }
  if (!addressForm.province.trim() || !addressForm.city.trim()) {
    ElMessage.warning('省市不能为空')
    return
  }
  if (!addressForm.detail_address.trim()) {
    ElMessage.warning('详细地址不能为空')
    return
  }

  const payload = {
    receiver_name: addressForm.receiver_name.trim(),
    receiver_phone: addressForm.receiver_phone.trim(),
    province: addressForm.province.trim(),
    city: addressForm.city.trim(),
    district: addressForm.district.trim(),
    detail_address: addressForm.detail_address.trim(),
    is_default: Boolean(addressForm.is_default),
  }

  addressSubmitting.value = true
  try {
    if (editingAddressId.value) {
      const res = await updateAddress(editingAddressId.value, payload)
      ElMessage.success(res.message || '地址更新成功')
    } else {
      const res = await createAddress(payload)
      ElMessage.success(res.message || '地址新增成功')
    }
    addressDialogVisible.value = false
    await fetchAddresses()
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '地址提交失败')
  } finally {
    addressSubmitting.value = false
  }
}

async function handleDeleteAddress(address) {
  try {
    await ElMessageBox.confirm(`确认删除收货地址「${address.receiver_name}」吗？`, '删除地址', { type: 'warning' })
    const res = await deleteAddress(address.id)
    ElMessage.success(res.message || '地址删除成功')
    await fetchAddresses()
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '地址删除失败')
  }
}

async function handleSubmitOrders() {
  if (!hasSelectedItems.value) {
    ElMessage.warning('请先在购物车勾选需要结算的商品')
    return
  }
  if (!selectedAddressId.value) {
    ElMessage.warning('请先选择收货地址')
    return
  }

  submitLoading.value = true
  const succeeded = []
  const failed = []

  try {
    for (const item of selectedItems.value) {
      try {
        await createOrder({
          product_id: item.product_id,
          quantity: Number(item.quantity || 1),
          address_id: Number(selectedAddressId.value),
        })
        await removeCartItem(item.id)
        succeeded.push(item)
      } catch (err) {
        failed.push({
          item,
          message: err?.response?.data?.message || err?.response?.data?.detail || '下单失败',
        })
      }
    }

    if (succeeded.length) {
      ElMessage.success(`结算成功 ${succeeded.length} 项`)
    }
    if (failed.length) {
      ElMessage.warning(`有 ${failed.length} 项下单失败，请检查库存或状态后重试`)
    }

    await refreshPageData()

    if (succeeded.length && !failed.length) {
      router.push('/orders')
      return
    }

    if (failed.length) {
      const first = failed[0]
      ElMessage.error(`失败示例：${first.item?.product?.name || '商品'} - ${first.message}`)
    }
  } finally {
    submitLoading.value = false
  }
}

onMounted(refreshPageData)
</script>

<template>
  <div class="checkout-page" v-loading="loading">
    <section class="page-block checkout-head">
      <div>
        <h1 class="page-title">订单结算</h1>
        <p class="page-subtitle">从购物车勾选项创建订单，并绑定收货地址快照。</p>
      </div>
      <div class="head-actions">
        <el-button @click="refreshPageData">刷新</el-button>
        <el-button type="primary" @click="router.push('/cart')">返回购物车</el-button>
      </div>
    </section>

    <section class="page-block addresses">
      <div class="card-title-row">
        <strong>收货地址</strong>
        <el-button type="primary" plain @click="openCreateAddress">新增地址</el-button>
      </div>

      <el-empty v-if="!hasAddresses" description="暂无地址，请先新增" />

      <div v-else class="address-list">
        <label v-for="item in addresses" :key="item.id" class="address-item">
          <div class="address-main">
            <el-radio v-model="selectedAddressId" :value="item.id">使用该地址</el-radio>
            <el-tag v-if="item.is_default" type="success" size="small">默认</el-tag>
          </div>
          <div class="address-line">
            {{ item.receiver_name }} · {{ item.receiver_phone }}
          </div>
          <div class="address-line text-muted">{{ normalizeAddressLabel(item) }}</div>
          <div class="address-actions">
            <el-button size="small" @click="openEditAddress(item)">编辑</el-button>
            <el-button size="small" type="danger" plain @click="handleDeleteAddress(item)">删除</el-button>
          </div>
        </label>
      </div>
    </section>

    <section class="page-block">
      <div class="card-title-row">
        <strong>结算商品（来自购物车已勾选）</strong>
        <div class="summary">共 {{ selectedCount }} 项，合计 ¥{{ formatPrice(totalAmount) }}</div>
      </div>

      <el-empty v-if="!hasSelectedItems" description="购物车暂无勾选商品，请先去购物车勾选" />

      <el-table v-else :data="selectedItems" border stripe>
        <el-table-column label="商品" min-width="240">
          <template #default="scope">
            <div class="product-cell">
              <img :src="scope.row.product.image_urls?.[0]" class="thumb" alt="商品" />
              <div>{{ scope.row.product.name }}</div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="单价" width="120">
          <template #default="scope">¥{{ formatPrice(scope.row.product.price) }}</template>
        </el-table-column>
        <el-table-column prop="quantity" label="数量" width="100" />
        <el-table-column label="小计" width="120">
          <template #default="scope">¥{{ formatPrice(Number(scope.row.product.price) * Number(scope.row.quantity)) }}</template>
        </el-table-column>
      </el-table>

      <div class="submit-row">
        <el-button type="danger" :loading="submitLoading" :disabled="!hasSelectedItems || !selectedAddressId" @click="handleSubmitOrders">
          提交结算
        </el-button>
      </div>
    </section>

    <el-dialog v-model="addressDialogVisible" :title="editingAddressId ? '编辑地址' : '新增地址'" width="560px" @closed="resetAddressForm">
      <el-form label-position="top">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="收件人" required>
              <el-input v-model="addressForm.receiver_name" maxlength="60" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="联系电话" required>
              <el-input v-model="addressForm.receiver_phone" maxlength="30" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="省份" required>
              <el-input v-model="addressForm.province" maxlength="60" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="城市" required>
              <el-input v-model="addressForm.city" maxlength="60" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="区县">
          <el-input v-model="addressForm.district" maxlength="60" />
        </el-form-item>

        <el-form-item label="详细地址" required>
          <el-input v-model="addressForm.detail_address" maxlength="255" />
        </el-form-item>

        <el-form-item>
          <el-checkbox v-model="addressForm.is_default">设为默认地址</el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addressDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="addressSubmitting" @click="submitAddress">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.checkout-page {
  display: grid;
  gap: 16px;
}

.checkout-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.head-actions {
  display: flex;
  gap: 8px;
}

.card-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.summary {
  color: #d5391c;
  font-weight: 700;
}

.address-list {
  display: grid;
  gap: 10px;
}

.address-item {
  display: grid;
  gap: 6px;
  border: 1px solid #ecd8d2;
  border-radius: 10px;
  padding: 10px;
}

.address-main {
  display: flex;
  align-items: center;
  gap: 8px;
}

.address-line {
  line-height: 1.4;
}

.text-muted {
  color: #6d7481;
  font-size: 13px;
}

.address-actions {
  display: flex;
  gap: 8px;
}

.product-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}

.thumb {
  width: 44px;
  height: 44px;
  object-fit: cover;
  border-radius: 6px;
  background: #fff4eb;
}

.submit-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

@media (max-width: 900px) {
  .checkout-head {
    flex-direction: column;
    align-items: flex-start;
  }

  .card-title-row {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
