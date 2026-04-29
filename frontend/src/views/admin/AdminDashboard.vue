<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  arbitrateRefund,
  auditProduct,
  auditSellerProfile,
  createAdminCategory,
  deleteAdminCategory,
  executeRefund,
  getAdminCategories,
  getAdminOrdersPaged,
  getAdminOverview,
  getAdminRefundsPaged,
  getPendingProducts,
  getPendingSellerProfiles,
  getSellers,
  updateAdminCategory,
  updateAdminCategoryStatus,
} from '@/api/admin'

const overviewLoading = ref(false)
const sellersLoading = ref(false)
const pendingProductsLoading = ref(false)
const pendingProfilesLoading = ref(false)
const recentOrdersLoading = ref(false)
const refundsLoading = ref(false)
const categoriesLoading = ref(false)

const overview = reactive({
  total_users: 0,
  total_buyers: 0,
  total_sellers: 0,
  total_admins: 0,
  today_new_users: 0,
  pending_seller_profiles: 0,
  pending_products: 0,
  total_orders: 0,
  pending_paid_orders: 0,
  paid_orders: 0,
  shipped_orders: 0,
  completed_orders: 0,
  closed_or_cancelled_orders: 0,
  refunded_orders: 0,
  today_new_orders: 0,
  gmv_paid_total: 0,
  gmv_refunded_total: 0,
  today_paid_amount: 0,
  refund_requested_count: 0,
  refund_seller_rejected_count: 0,
  refund_refunded_count: 0,
})

const sellers = ref([])
const pendingProducts = ref([])
const pendingSellerProfiles = ref([])
const categories = ref([])
const recentOrders = ref([])
const refundCases = ref([])

const productAuditLoadingId = ref(null)
const profileAuditLoadingId = ref(null)
const refundAuditLoadingId = ref(null)

const productAuditDialogVisible = ref(false)
const productAuditForm = reactive({
  productId: null,
  approval_status: 'approved',
  review_note: '',
})

const refundDialogVisible = ref(false)
const refundAuditForm = reactive({
  refundId: null,
  action: 'approve',
  admin_note: '',
})

const imagePreviewVisible = ref(false)
const previewImageUrl = ref('')
const categoryDialogVisible = ref(false)
const categorySubmitLoading = ref(false)
const categoryLoadingId = ref(null)
const editingCategoryId = ref(null)
const editingCategoryOriginalStatus = ref(true)
const editingCategoryIsFallback = ref(false)
const categoryForm = reactive({
  name: '',
  sort_order: 100,
  is_active: true,
})

const refundFilter = reactive({
  status: 'all',
  keyword: '',
})
const orderFilter = reactive({
  status: '',
  pay_status: '',
  keyword: '',
})
const orderPage = reactive({ page: 1, page_size: 20, total: 0 })
const refundPage = reactive({ page: 1, page_size: 20, total: 0 })

const FALLBACK_IMAGE =
  'data:image/svg+xml;utf8,' +
  encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="160" height="120"><defs><linearGradient id="g" x1="0" x2="1" y1="0" y2="1"><stop stop-color="#fff0ec" offset="0"/><stop stop-color="#ffe2cb" offset="1"/></linearGradient></defs><rect fill="url(#g)" width="160" height="120" rx="12"/><text x="50%" y="47%" dominant-baseline="middle" text-anchor="middle" font-size="14" fill="#c14a33" font-family="Arial">商品图</text><text x="50%" y="60%" dominant-baseline="middle" text-anchor="middle" font-size="11" fill="#9d5e49" font-family="Arial">未提供</text></svg>'
  )

const overviewCards = computed(() => [
  { label: '总用户数', value: overview.total_users, desc: `买家 ${overview.total_buyers} · 卖家 ${overview.total_sellers}` },
  { label: '今日新增用户', value: overview.today_new_users, desc: `管理员 ${overview.total_admins}` },
  {
    label: '待审核队列',
    value: overview.pending_seller_profiles + overview.pending_products,
    desc: `店铺 ${overview.pending_seller_profiles} · 商品 ${overview.pending_products}`,
  },
  { label: '订单总量', value: overview.total_orders, desc: `今日新增 ${overview.today_new_orders}` },
  {
    label: '支付 GMV',
    value: `¥${Number(overview.gmv_paid_total || 0).toFixed(2)}`,
    desc: `今日支付 ¥${Number(overview.today_paid_amount || 0).toFixed(2)}`,
  },
  {
    label: '退款风险池',
    value: overview.refund_requested_count + overview.refund_seller_rejected_count,
    desc: `申请中 ${overview.refund_requested_count} · 卖家拒绝 ${overview.refund_seller_rejected_count}`,
  },
])

function formatTime(value) {
  if (!value) return '-'
  const dt = new Date(value)
  if (Number.isNaN(dt.getTime())) return value
  return dt.toLocaleString()
}

function statusType(status) {
  if (status === 'pending_paid') return 'warning'
  if (status === 'paid' || status === 'shipped') return 'primary'
  if (status === 'completed') return 'success'
  if (status === 'cancelled' || status === 'closed') return 'info'
  return 'danger'
}

function statusLabel(status) {
  const map = {
    pending_paid: '待支付',
    paid: '已支付',
    shipped: '已发货',
    completed: '已完成',
    cancelled: '已取消',
    closed: '已关闭',
  }
  return map[status] || status
}

function refundStatusType(status) {
  if (status === 'requested') return 'warning'
  if (status === 'seller_rejected') return 'danger'
  if (status === 'refunded') return 'success'
  if (status === 'closed') return 'info'
  return 'primary'
}

function refundStatusLabel(status) {
  const map = {
    requested: '买家申请中',
    approved_pending_refund: '待执行退款',
    seller_approved: '卖家已同意',
    seller_rejected: '卖家已拒绝',
    refunded: '已退款',
    refund_failed: '退款失败',
    closed: '已关闭',
  }
  return map[status] || status
}

function normalizeImageUrls(value) {
  if (Array.isArray(value)) return value.filter(Boolean)
  if (typeof value === 'string') {
    try {
      const parsed = JSON.parse(value)
      return Array.isArray(parsed) ? parsed.filter(Boolean) : []
    } catch {
      return []
    }
  }
  return []
}

function toPendingProductViewModel(item) {
  const imageUrls = normalizeImageUrls(item.image_urls)
  return {
    ...item,
    image_urls: imageUrls,
    cover: imageUrls[0] || FALLBACK_IMAGE,
  }
}

function resolveImage(event) {
  event.target.src = FALLBACK_IMAGE
}

function openImagePreview(url) {
  previewImageUrl.value = url || FALLBACK_IMAGE
  imagePreviewVisible.value = true
}

async function loadOverview() {
  overviewLoading.value = true
  try {
    const res = await getAdminOverview()
    Object.assign(overview, res.data || {})
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '加载运营总览失败')
  } finally {
    overviewLoading.value = false
  }
}

async function loadSellers() {
  sellersLoading.value = true
  try {
    const res = await getSellers()
    sellers.value = res.data || []
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '加载卖家列表失败')
  } finally {
    sellersLoading.value = false
  }
}

async function loadPendingProducts() {
  pendingProductsLoading.value = true
  try {
    const res = await getPendingProducts()
    pendingProducts.value = (res.data || []).map(toPendingProductViewModel)
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '加载待审核商品失败')
  } finally {
    pendingProductsLoading.value = false
  }
}

async function loadPendingSellerProfiles() {
  pendingProfilesLoading.value = true
  try {
    const res = await getPendingSellerProfiles()
    pendingSellerProfiles.value = res.data || []
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '加载待审核店铺失败')
  } finally {
    pendingProfilesLoading.value = false
  }
}

async function loadRecentOrders() {
  recentOrdersLoading.value = true
  try {
    const res = await getAdminOrdersPaged({
      page: orderPage.page,
      page_size: orderPage.page_size,
      status: orderFilter.status || undefined,
      pay_status: orderFilter.pay_status || undefined,
      keyword: orderFilter.keyword || undefined,
    })
    const data = res.data || {}
    recentOrders.value = data.items || []
    orderPage.total = data.total || 0
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '加载最近订单失败')
  } finally {
    recentOrdersLoading.value = false
  }
}

async function loadRefundCases() {
  refundsLoading.value = true
  try {
    const res = await getAdminRefundsPaged({
      status: refundFilter.status,
      keyword: refundFilter.keyword || undefined,
      page: refundPage.page,
      page_size: refundPage.page_size,
    })
    const data = res.data || {}
    refundCases.value = data.items || []
    refundPage.total = data.total || 0
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '加载退款工单失败')
  } finally {
    refundsLoading.value = false
  }
}

async function loadCategories() {
  categoriesLoading.value = true
  try {
    const res = await getAdminCategories()
    categories.value = res.data || []
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '加载分类失败')
  } finally {
    categoriesLoading.value = false
  }
}

function resetCategoryForm() {
  editingCategoryId.value = null
  editingCategoryOriginalStatus.value = true
  editingCategoryIsFallback.value = false
  categoryForm.name = ''
  categoryForm.sort_order = 100
  categoryForm.is_active = true
}

function openCreateCategoryDialog() {
  resetCategoryForm()
  categoryDialogVisible.value = true
}

function openEditCategoryDialog(row) {
  editingCategoryId.value = row.id
  editingCategoryOriginalStatus.value = Boolean(row.is_active)
  editingCategoryIsFallback.value = row.name === '其他'
  categoryForm.name = row.name
  categoryForm.sort_order = Number(row.sort_order || 100)
  categoryForm.is_active = Boolean(row.is_active)
  categoryDialogVisible.value = true
}

async function submitCategory() {
  if (!categoryForm.name.trim()) {
    ElMessage.warning('分类名称不能为空')
    return
  }
  categorySubmitLoading.value = true
  try {
    const payload = {
      name: categoryForm.name.trim(),
      sort_order: Number(categoryForm.sort_order || 0),
      is_active: Boolean(categoryForm.is_active),
    }
    if (editingCategoryId.value) {
      const res = await updateAdminCategory(editingCategoryId.value, {
        name: payload.name,
        sort_order: payload.sort_order,
      })
      ElMessage.success(res.message || '分类更新成功')
      if (payload.is_active !== editingCategoryOriginalStatus.value) {
        await updateAdminCategoryStatus(editingCategoryId.value, { is_active: payload.is_active })
      }
    } else {
      const res = await createAdminCategory(payload)
      ElMessage.success(res.message || '分类创建成功')
    }
    categoryDialogVisible.value = false
    await loadCategories()
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '提交分类失败')
  } finally {
    categorySubmitLoading.value = false
  }
}

async function toggleCategoryStatus(row, targetStatus) {
  categoryLoadingId.value = row.id
  try {
    const res = await updateAdminCategoryStatus(row.id, { is_active: targetStatus })
    ElMessage.success(res.message || '分类状态更新成功')
    await loadCategories()
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '分类状态更新失败')
  } finally {
    categoryLoadingId.value = null
  }
}

async function handleDeleteCategory(row) {
  categoryLoadingId.value = row.id
  try {
    await ElMessageBox.confirm(
      `确认删除分类「${row.name}」吗？该分类下商品将自动迁移到“其他”。`,
      '删除分类',
      { type: 'warning' }
    )
    const res = await deleteAdminCategory(row.id)
    const migratedCount = Number(res?.data?.migrated_product_count || 0)
    ElMessage.success(`${res.message || '分类删除成功'}，已迁移 ${migratedCount} 个商品到“其他”`)
    await loadCategories()
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '分类删除失败')
  } finally {
    categoryLoadingId.value = null
  }
}

async function refreshAll() {
  await Promise.all([
    loadOverview(),
    loadSellers(),
    loadPendingSellerProfiles(),
    loadPendingProducts(),
    loadRecentOrders(),
    loadRefundCases(),
    loadCategories(),
  ])
}

function openProductAuditDialog(row, status) {
  productAuditForm.productId = row.id
  productAuditForm.approval_status = status
  productAuditForm.review_note = ''
  productAuditDialogVisible.value = true
}

async function submitProductAudit() {
  if (!productAuditForm.productId) return
  productAuditLoadingId.value = productAuditForm.productId
  try {
    const res = await auditProduct(productAuditForm.productId, {
      approval_status: productAuditForm.approval_status,
      review_note: productAuditForm.review_note,
    })
    ElMessage.success(res.message || '商品审核完成')
    productAuditDialogVisible.value = false
    await Promise.all([loadOverview(), loadSellers(), loadPendingProducts()])
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '商品审核失败')
  } finally {
    productAuditLoadingId.value = null
  }
}

async function handleProfileAudit(row, status) {
  profileAuditLoadingId.value = row.id
  try {
    const res = await auditSellerProfile(row.id, { approval_status: status })
    ElMessage.success(res.message || '店铺审核完成')
    await Promise.all([loadOverview(), loadSellers(), loadPendingSellerProfiles()])
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '店铺审核失败')
  } finally {
    profileAuditLoadingId.value = null
  }
}

function openRefundArbitrateDialog(row, action) {
  refundAuditForm.refundId = row.id
  refundAuditForm.action = action
  refundAuditForm.admin_note = ''
  refundDialogVisible.value = true
}

async function handleExecuteRefund(row, result) {
  refundAuditLoadingId.value = row.id
  try {
    const res = await executeRefund(row.id, {
      result,
      fail_reason: result === 'failed' ? '模拟执行失败（管理员手动标记）' : '',
    })
    ElMessage.success(res.message || '退款执行完成')
    await Promise.all([loadOverview(), loadRefundCases(), loadRecentOrders()])
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '退款执行失败')
  } finally {
    refundAuditLoadingId.value = null
  }
}

async function submitRefundArbitrate() {
  if (!refundAuditForm.refundId) return
  refundAuditLoadingId.value = refundAuditForm.refundId
  try {
    const res = await arbitrateRefund(refundAuditForm.refundId, {
      action: refundAuditForm.action,
      admin_note: refundAuditForm.admin_note,
    })
    ElMessage.success(res.message || '退款仲裁完成')
    refundDialogVisible.value = false
    await Promise.all([loadOverview(), loadRefundCases()])
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '退款仲裁失败')
  } finally {
    refundAuditLoadingId.value = null
  }
}

onMounted(refreshAll)
</script>

<template>
  <div class="admin-wrap">
    <section class="head-row">
      <el-alert
        title="运营后台：总览监控 + 审核中心 + 退款仲裁"
        type="info"
        show-icon
        :closable="false"
      />
      <el-button type="primary" @click="refreshAll">全量刷新</el-button>
    </section>

    <section class="overview-grid" v-loading="overviewLoading">
      <el-card v-for="item in overviewCards" :key="item.label" class="metric-card">
        <div class="metric-label">{{ item.label }}</div>
        <div class="metric-value">{{ item.value }}</div>
        <div class="metric-desc">{{ item.desc }}</div>
      </el-card>
    </section>

    <el-card>
      <template #header>
        <div class="card-header-row">
          <strong>分类治理</strong>
          <div class="actions">
            <el-button @click="loadCategories">刷新</el-button>
            <el-button type="primary" @click="openCreateCategoryDialog">新建分类</el-button>
          </div>
        </div>
      </template>
      <el-table v-loading="categoriesLoading" :data="categories" border stripe>
        <el-table-column prop="id" label="分类ID" width="90" />
        <el-table-column prop="name" label="分类名称" min-width="180" />
        <el-table-column prop="sort_order" label="排序" width="100" />
        <el-table-column label="状态" width="120">
          <template #default="scope">
            <el-tag :type="scope.row.is_active ? 'success' : 'info'">
              {{ scope.row.is_active ? '启用中' : '已停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="updated_at" label="更新时间" min-width="180">
          <template #default="scope">{{ formatTime(scope.row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="scope">
            <div class="actions">
              <el-button size="small" :loading="categoryLoadingId === scope.row.id" @click="openEditCategoryDialog(scope.row)">
                编辑
              </el-button>
              <el-button
                size="small"
                :type="scope.row.is_active ? 'warning' : 'success'"
                :loading="categoryLoadingId === scope.row.id"
                :disabled="scope.row.name === '其他' && scope.row.is_active"
                @click="toggleCategoryStatus(scope.row, !scope.row.is_active)"
              >
                {{ scope.row.is_active ? '停用' : '启用' }}
              </el-button>
              <el-button
                size="small"
                type="danger"
                :loading="categoryLoadingId === scope.row.id"
                :disabled="scope.row.name === '其他'"
                @click="handleDeleteCategory(scope.row)"
              >
                删除
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card>
      <template #header>
        <div class="card-header-row">
          <strong>待审核店铺</strong>
          <el-button @click="loadPendingSellerProfiles">刷新</el-button>
        </div>
      </template>
      <el-table v-loading="pendingProfilesLoading" :data="pendingSellerProfiles" border stripe>
        <el-table-column prop="id" label="资料ID" width="90" />
        <el-table-column prop="user_id" label="卖家ID" width="90" />
        <el-table-column prop="shop_name" label="店铺名称" min-width="180" />
        <el-table-column prop="shop_description" label="店铺描述" min-width="240" show-overflow-tooltip />
        <el-table-column prop="created_at" label="提交时间" min-width="180" />
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="scope">
            <div class="actions">
              <el-button
                type="success"
                size="small"
                :loading="profileAuditLoadingId === scope.row.id"
                @click="handleProfileAudit(scope.row, 'approved')"
              >
                通过
              </el-button>
              <el-button
                type="danger"
                size="small"
                :loading="profileAuditLoadingId === scope.row.id"
                @click="handleProfileAudit(scope.row, 'rejected')"
              >
                驳回
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card>
      <template #header>
        <strong>卖家列表</strong>
      </template>
      <el-table v-loading="sellersLoading" :data="sellers" border stripe>
        <el-table-column prop="id" label="卖家ID" width="100" />
        <el-table-column prop="email" label="卖家邮箱" min-width="220" />
        <el-table-column prop="shop_audit_status" label="店铺审核状态" width="140" />
        <el-table-column prop="total_products" label="商品总数" width="120" />
        <el-table-column prop="pending_products" label="待审核商品数" width="140" />
        <el-table-column prop="created_at" label="注册时间" min-width="180" />
      </el-table>
    </el-card>

    <el-card>
      <template #header>
        <div class="card-header-row">
          <strong>待审核商品</strong>
          <el-button @click="loadPendingProducts">刷新</el-button>
        </div>
      </template>
      <el-table v-loading="pendingProductsLoading" :data="pendingProducts" border stripe>
        <el-table-column prop="id" label="商品ID" width="90" />
        <el-table-column label="主图" width="96">
          <template #default="scope">
            <img
              :src="scope.row.cover"
              class="product-cover clickable"
              alt="商品主图"
              @error="resolveImage"
              @click="openImagePreview(scope.row.cover)"
            />
          </template>
        </el-table-column>
        <el-table-column prop="seller_id" label="卖家ID" width="90" />
        <el-table-column prop="seller_email" label="卖家邮箱" min-width="200" />
        <el-table-column prop="seller_shop_audit_status" label="店铺状态" width="120" />
        <el-table-column prop="name" label="商品名称" min-width="160" />
        <el-table-column prop="stock" label="库存" width="90" />
        <el-table-column prop="price" label="价格" width="100" />
        <el-table-column prop="created_at" label="提交时间" min-width="180" />
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="scope">
            <div class="actions">
              <el-button
                type="success"
                size="small"
                :loading="productAuditLoadingId === scope.row.id"
                @click="openProductAuditDialog(scope.row, 'approved')"
              >
                通过
              </el-button>
              <el-button
                type="danger"
                size="small"
                :loading="productAuditLoadingId === scope.row.id"
                @click="openProductAuditDialog(scope.row, 'rejected')"
              >
                驳回
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card>
      <template #header>
        <div class="card-header-row">
          <strong>最近订单监控</strong>
          <div class="filters">
            <el-select v-model="orderFilter.status" style="width: 140px" @change="() => { orderPage.page = 1; loadRecentOrders() }">
              <el-option label="全部订单状态" value="" />
              <el-option label="待支付" value="pending_paid" />
              <el-option label="已支付" value="paid" />
              <el-option label="已发货" value="shipped" />
              <el-option label="已完成" value="completed" />
              <el-option label="已取消" value="cancelled" />
              <el-option label="已关闭" value="closed" />
            </el-select>
            <el-select v-model="orderFilter.pay_status" style="width: 140px" @change="() => { orderPage.page = 1; loadRecentOrders() }">
              <el-option label="全部支付状态" value="" />
              <el-option label="待支付" value="pending" />
              <el-option label="已支付" value="paid" />
              <el-option label="已退款" value="refunded" />
              <el-option label="已关闭" value="closed" />
            </el-select>
            <el-input
              v-model="orderFilter.keyword"
              clearable
              placeholder="买家/卖家/商品关键词"
              style="width: 220px"
              @keyup.enter="() => { orderPage.page = 1; loadRecentOrders() }"
              @clear="() => { orderPage.page = 1; loadRecentOrders() }"
            />
            <el-button @click="() => { orderPage.page = 1; loadRecentOrders() }">筛选</el-button>
          </div>
        </div>
      </template>
      <el-table v-loading="recentOrdersLoading" :data="recentOrders" border stripe>
        <el-table-column prop="id" label="订单ID" width="90" />
        <el-table-column prop="buyer_email" label="买家" min-width="180" />
        <el-table-column prop="seller_email" label="卖家" min-width="180" />
        <el-table-column prop="product_name" label="商品" min-width="160" show-overflow-tooltip />
        <el-table-column prop="pay_amount" label="金额" width="100">
          <template #default="scope">¥{{ Number(scope.row.pay_amount || 0).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column label="订单状态" width="120">
          <template #default="scope">
            <el-tag :type="statusType(scope.row.status)">{{ statusLabel(scope.row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="支付状态" width="110">
          <template #default="scope">{{ scope.row.pay_status }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="下单时间" min-width="170">
          <template #default="scope">{{ formatTime(scope.row.created_at) }}</template>
        </el-table-column>
      </el-table>
      <div class="pager-wrap">
        <el-pagination
          background
          layout="total, prev, pager, next"
          :total="orderPage.total"
          :page-size="orderPage.page_size"
          :current-page="orderPage.page"
          @current-change="(p) => { orderPage.page = p; loadRecentOrders() }"
        />
      </div>
    </el-card>

    <el-card>
      <template #header>
        <div class="card-header-row">
          <strong>退款工单池（仲裁）</strong>
          <div class="filters">
            <el-select v-model="refundFilter.status" style="width: 160px" @change="() => { refundPage.page = 1; loadRefundCases() }">
              <el-option label="全部状态" value="all" />
              <el-option label="买家申请中" value="requested" />
              <el-option label="待执行退款" value="approved_pending_refund" />
              <el-option label="卖家已拒绝" value="seller_rejected" />
              <el-option label="已退款" value="refunded" />
              <el-option label="退款失败" value="refund_failed" />
              <el-option label="已关闭" value="closed" />
            </el-select>
            <el-input
              v-model="refundFilter.keyword"
              clearable
              placeholder="买家/卖家/订单关键词"
              style="width: 220px"
              @keyup.enter="() => { refundPage.page = 1; loadRefundCases() }"
              @clear="() => { refundPage.page = 1; loadRefundCases() }"
            />
            <el-button @click="() => { refundPage.page = 1; loadRefundCases() }">筛选</el-button>
          </div>
        </div>
      </template>
      <el-table v-loading="refundsLoading" :data="refundCases" border stripe>
        <el-table-column prop="id" label="工单ID" width="90" />
        <el-table-column prop="order_id" label="订单ID" width="90" />
        <el-table-column prop="buyer_email" label="买家" min-width="170" />
        <el-table-column prop="seller_email" label="卖家" min-width="170" />
        <el-table-column prop="amount" label="金额" width="100">
          <template #default="scope">¥{{ Number(scope.row.amount || 0).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column label="退款状态" width="130">
          <template #default="scope">
            <el-tag :type="refundStatusType(scope.row.status)">{{ refundStatusLabel(scope.row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="reason" label="申请原因" min-width="220" show-overflow-tooltip />
        <el-table-column prop="created_at" label="创建时间" min-width="170">
          <template #default="scope">{{ formatTime(scope.row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="scope">
            <div class="actions" v-if="scope.row.status === 'requested' || scope.row.status === 'seller_rejected'">
              <el-button
                type="success"
                size="small"
                :loading="refundAuditLoadingId === scope.row.id"
                @click="openRefundArbitrateDialog(scope.row, 'approve')"
              >
                同意退款
              </el-button>
              <el-button
                type="danger"
                size="small"
                :loading="refundAuditLoadingId === scope.row.id"
                @click="openRefundArbitrateDialog(scope.row, 'reject')"
              >
                驳回申请
              </el-button>
            </div>
            <div class="actions" v-else-if="scope.row.status === 'approved_pending_refund'">
              <el-button
                type="success"
                size="small"
                :loading="refundAuditLoadingId === scope.row.id"
                @click="handleExecuteRefund(scope.row, 'success')"
              >
                执行退款
              </el-button>
              <el-button
                type="warning"
                size="small"
                :loading="refundAuditLoadingId === scope.row.id"
                @click="handleExecuteRefund(scope.row, 'failed')"
              >
                标记失败
              </el-button>
            </div>
            <span v-else>-</span>
          </template>
        </el-table-column>
      </el-table>
      <div class="pager-wrap">
        <el-pagination
          background
          layout="total, prev, pager, next"
          :total="refundPage.total"
          :page-size="refundPage.page_size"
          :current-page="refundPage.page"
          @current-change="(p) => { refundPage.page = p; loadRefundCases() }"
        />
      </div>
    </el-card>

    <el-dialog v-model="productAuditDialogVisible" title="商品审核" width="460px">
      <el-form label-position="top">
        <el-form-item label="审核结果">
          <el-radio-group v-model="productAuditForm.approval_status">
            <el-radio value="approved">通过</el-radio>
            <el-radio value="rejected">驳回</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="审核备注">
          <el-input v-model="productAuditForm.review_note" type="textarea" :rows="3" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="productAuditDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="productAuditLoadingId === productAuditForm.productId" @click="submitProductAudit">
          提交审核
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="refundDialogVisible" title="退款仲裁" width="460px">
      <el-form label-position="top">
        <el-form-item label="仲裁结论">
          <el-radio-group v-model="refundAuditForm.action">
            <el-radio value="approve">同意退款</el-radio>
            <el-radio value="reject">驳回申请</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="仲裁说明">
          <el-input v-model="refundAuditForm.admin_note" type="textarea" :rows="3" placeholder="建议填写处理依据" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="refundDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="refundAuditLoadingId === refundAuditForm.refundId" @click="submitRefundArbitrate">
          提交仲裁
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="categoryDialogVisible" :title="editingCategoryId ? '编辑分类' : '新建分类'" width="460px" @closed="resetCategoryForm">
      <el-form label-position="top">
        <el-form-item label="分类名称" required>
          <el-input
            v-model="categoryForm.name"
            maxlength="80"
            show-word-limit
            :disabled="editingCategoryIsFallback"
            placeholder="请输入分类名称"
          />
        </el-form-item>
        <el-form-item label="排序（越小越靠前）">
          <el-input-number v-model="categoryForm.sort_order" :min="0" :max="9999" style="width: 100%" />
        </el-form-item>
        <el-form-item label="启用状态">
          <el-switch
            v-model="categoryForm.is_active"
            active-text="启用"
            inactive-text="停用"
            :disabled="editingCategoryIsFallback && categoryForm.is_active"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="categoryDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="categorySubmitLoading" @click="submitCategory">提交</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="imagePreviewVisible" title="商品主图预览" width="720px" destroy-on-close>
      <div class="preview-wrap">
        <img :src="previewImageUrl" class="preview-image" alt="商品主图预览" @error="resolveImage" />
      </div>
      <template #footer>
        <el-button type="primary" @click="imagePreviewVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.admin-wrap {
  display: grid;
  gap: 16px;
}

.head-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.metric-card {
  border-radius: 12px;
}

.metric-label {
  color: #7b8190;
  font-size: 13px;
}

.metric-value {
  margin-top: 6px;
  font-size: 28px;
  font-weight: 700;
  color: #1f2329;
  line-height: 1.2;
}

.metric-desc {
  margin-top: 6px;
  color: #5a6170;
  font-size: 12px;
}

.card-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.filters {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pager-wrap {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}

.actions {
  display: flex;
  gap: 8px;
}

.product-cover {
  width: 64px;
  height: 64px;
  border-radius: 8px;
  object-fit: cover;
  border: 1px solid #ebeef5;
  display: block;
}

.clickable {
  cursor: zoom-in;
}

.preview-wrap {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 280px;
  background: #f8fafc;
  border: 1px solid #ebeef5;
  border-radius: 10px;
  padding: 12px;
}

.preview-image {
  max-width: 100%;
  max-height: 70vh;
  object-fit: contain;
}

@media (max-width: 1024px) {
  .overview-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .head-row {
    flex-direction: column;
    align-items: stretch;
  }

  .overview-grid {
    grid-template-columns: 1fr;
  }

  .actions {
    flex-wrap: wrap;
  }

  .filters {
    width: 100%;
    justify-content: flex-end;
  }
}
</style>
