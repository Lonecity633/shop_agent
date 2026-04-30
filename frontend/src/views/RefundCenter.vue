<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { getOrders } from '@/api/order'
import { createRefund, getRefunds, sellerReviewRefund } from '@/api/refund'

const authStore = useAuthStore()
const role = computed(() => authStore.user?.role || '')
const isBuyer = computed(() => role.value === 'buyer')
const isSeller = computed(() => role.value === 'seller')

const loading = ref(false)
const submitting = ref(false)
const refunds = ref([])
const orders = ref([])

const createDialogVisible = ref(false)
const createForm = reactive({
  order_id: null,
  reason: '',
  buyer_note: '',
})

const reviewDialogVisible = ref(false)
const reviewForm = reactive({
  refund_id: null,
  action: 'approve',
  seller_note: '',
})

const reviewingId = ref(null)

const activeRefundOrderIds = computed(() => {
  const activeStatuses = new Set(['requested', 'approved_pending_refund', 'seller_approved'])
  return new Set(
    (refunds.value || [])
      .filter((item) => activeStatuses.has(item.status))
      .map((item) => Number(item.order_id))
  )
})

const orderNoById = computed(() => {
  const map = new Map()
  for (const order of orders.value || []) {
    map.set(Number(order.id), displayOrderNo(order))
  }
  return map
})

const eligibleOrders = computed(() => {
  if (!isBuyer.value) return []
  return (orders.value || []).filter((order) => {
    if (order.pay_status !== 'paid') return false
    if (order.status === 'shipped') return false
    return !activeRefundOrderIds.value.has(Number(order.id))
  })
})

function refundStatusType(status) {
  if (status === 'requested') return 'warning'
  if (status === 'approved_pending_refund') return 'primary'
  if (status === 'seller_rejected' || status === 'refund_failed') return 'danger'
  if (status === 'refunded') return 'success'
  if (status === 'closed') return 'info'
  return ''
}

function refundStatusLabel(status) {
  const map = {
    requested: '买家申请中',
    approved_pending_refund: '待执行退款',
    seller_approved: '卖家同意',
    seller_rejected: '卖家拒绝',
    refunded: '已退款',
    refund_failed: '退款失败',
    closed: '已关闭',
  }
  return map[status] || status
}

function formatTime(value) {
  if (!value) return '-'
  const dt = new Date(value)
  if (Number.isNaN(dt.getTime())) return value
  return dt.toLocaleString()
}

function formatPrice(value) {
  const num = Number(value || 0)
  return Number.isFinite(num) ? num.toFixed(2) : '0.00'
}

function displayOrderNo(order) {
  return order?.order_no || '-'
}

function statusLabel(status) {
  const map = {
    pending_paid: '待支付',
    paid: '已支付待发货',
    shipped: '已发货',
    received: '已收货',
    completed: '已完成',
    cancelled: '已取消',
    closed: '已关闭',
  }
  return map[status] || status
}

function payStatusLabel(status) {
  const map = {
    pending: '待支付',
    paid: '已支付',
    refunded: '已退款',
    closed: '已关闭',
  }
  return map[status] || status
}

function displayRefundOrderNo(refund) {
  return orderNoById.value.get(Number(refund?.order_id)) || '-'
}

async function fetchRefunds() {
  const res = await getRefunds()
  refunds.value = res.data || []
}

async function fetchOrdersForBuyer() {
  if (!isBuyer.value) {
    orders.value = []
    return
  }
  const res = await getOrders()
  orders.value = res.data || []
}

async function refreshData() {
  loading.value = true
  try {
    await Promise.all([fetchRefunds(), fetchOrdersForBuyer()])
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '加载退款数据失败')
  } finally {
    loading.value = false
  }
}

function openCreateDialog(prefillOrderId = null) {
  createForm.order_id = prefillOrderId ? Number(prefillOrderId) : null
  createForm.reason = ''
  createForm.buyer_note = ''
  createDialogVisible.value = true
}

async function submitCreateRefund() {
  if (!createForm.order_id) {
    ElMessage.warning('请选择订单')
    return
  }
  if (!createForm.reason.trim()) {
    ElMessage.warning('请填写退款原因')
    return
  }

  submitting.value = true
  try {
    const res = await createRefund({
      order_id: Number(createForm.order_id),
      reason: createForm.reason.trim(),
      buyer_note: createForm.buyer_note.trim(),
    })
    ElMessage.success(res.message || '退款申请已提交')
    createDialogVisible.value = false
    await refreshData()
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '退款申请失败')
  } finally {
    submitting.value = false
  }
}

function openReviewDialog(refund, action) {
  reviewForm.refund_id = refund.id
  reviewForm.action = action
  reviewForm.seller_note = ''
  reviewDialogVisible.value = true
}

async function submitReviewRefund() {
  if (!reviewForm.refund_id) return

  reviewingId.value = reviewForm.refund_id
  try {
    const res = await sellerReviewRefund(reviewForm.refund_id, {
      action: reviewForm.action,
      seller_note: reviewForm.seller_note.trim(),
    })
    ElMessage.success(res.message || '退款审核已提交')
    reviewDialogVisible.value = false
    await fetchRefunds()
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '退款审核失败')
  } finally {
    reviewingId.value = null
  }
}

onMounted(refreshData)
</script>

<template>
  <div class="refund-page" v-loading="loading">
    <section class="page-block refund-head">
      <div>
        <h1 class="page-title">退款中心</h1>
        <p class="page-subtitle">买家可发起退款，卖家可处理待审核退款单。</p>
      </div>
      <div class="head-actions">
        <el-button @click="refreshData">刷新</el-button>
        <el-button v-if="isBuyer" type="primary" @click="openCreateDialog()">发起退款</el-button>
      </div>
    </section>

    <section v-if="isBuyer" class="page-block">
      <div class="card-title-row">
        <strong>可申请退款订单</strong>
      </div>
      <el-empty v-if="!eligibleOrders.length" description="暂无可申请退款订单" />
      <el-table v-else :data="eligibleOrders" border stripe>
        <el-table-column label="订单号" min-width="220">
          <template #default="scope">{{ displayOrderNo(scope.row) }}</template>
        </el-table-column>
        <el-table-column prop="product_id" label="商品ID" width="100" />
        <el-table-column label="订单状态" width="130">
          <template #default="scope">{{ statusLabel(scope.row.status) }}</template>
        </el-table-column>
        <el-table-column label="支付状态" width="120">
          <template #default="scope">{{ payStatusLabel(scope.row.pay_status) }}</template>
        </el-table-column>
        <el-table-column label="支付金额" width="120">
          <template #default="scope">¥{{ formatPrice(scope.row.pay_amount) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="scope">
            <el-button type="danger" size="small" @click="openCreateDialog(scope.row.id)">申请退款</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <section class="page-block">
      <div class="card-title-row">
        <strong>{{ isSeller ? '我的待处理退款单' : '我的退款单' }}</strong>
      </div>
      <el-empty v-if="!refunds.length" description="暂无退款记录" />
      <el-table v-else :data="refunds" border stripe>
        <el-table-column prop="id" label="退款ID" width="92" />
        <el-table-column label="订单号" min-width="220">
          <template #default="scope">{{ displayRefundOrderNo(scope.row) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="140">
          <template #default="scope">
            <el-tag :type="refundStatusType(scope.row.status)">{{ refundStatusLabel(scope.row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="金额" width="120">
          <template #default="scope">¥{{ formatPrice(scope.row.amount) }}</template>
        </el-table-column>
        <el-table-column prop="reason" label="退款原因" min-width="200" show-overflow-tooltip />
        <el-table-column prop="buyer_note" label="买家备注" min-width="180" show-overflow-tooltip />
        <el-table-column prop="seller_note" label="卖家备注" min-width="180" show-overflow-tooltip />
        <el-table-column label="更新时间" min-width="180">
          <template #default="scope">{{ formatTime(scope.row.updated_at) }}</template>
        </el-table-column>
        <el-table-column v-if="isSeller" label="操作" width="200" fixed="right">
          <template #default="scope">
            <div class="table-actions" v-if="scope.row.status === 'requested'">
              <el-button
                size="small"
                type="success"
                :loading="reviewingId === scope.row.id"
                @click="openReviewDialog(scope.row, 'approve')"
              >
                同意
              </el-button>
              <el-button
                size="small"
                type="danger"
                :loading="reviewingId === scope.row.id"
                @click="openReviewDialog(scope.row, 'reject')"
              >
                拒绝
              </el-button>
            </div>
            <span v-else>-</span>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-dialog v-model="createDialogVisible" title="发起退款申请" width="560px">
      <el-form label-position="top">
        <el-form-item label="订单" required>
          <el-select v-model="createForm.order_id" placeholder="请选择订单" style="width: 100%">
            <el-option
              v-for="order in eligibleOrders"
              :key="order.id"
              :label="`${displayOrderNo(order)}（¥${formatPrice(order.pay_amount)}）`"
              :value="order.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="退款原因" required>
          <el-input v-model="createForm.reason" type="textarea" :rows="3" maxlength="2000" show-word-limit />
        </el-form-item>
        <el-form-item label="补充说明">
          <el-input v-model="createForm.buyer_note" type="textarea" :rows="2" maxlength="2000" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitCreateRefund">提交申请</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="reviewDialogVisible" title="卖家审核退款" width="520px">
      <el-form label-position="top">
        <el-form-item label="审核结果">
          <el-radio-group v-model="reviewForm.action">
            <el-radio value="approve">同意退款</el-radio>
            <el-radio value="reject">拒绝退款</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="卖家备注">
          <el-input v-model="reviewForm.seller_note" type="textarea" :rows="3" maxlength="2000" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="reviewDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="reviewingId === reviewForm.refund_id" @click="submitReviewRefund">确认提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.refund-page {
  display: grid;
  gap: 16px;
}

.refund-head {
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
  margin-bottom: 12px;
}

.table-actions {
  display: flex;
  gap: 8px;
}

@media (max-width: 900px) {
  .refund-head {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
