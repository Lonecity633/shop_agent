<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { createOrderComment, getOrderLogs, getOrderStatus, getOrders, receiveOrder, shipOrder, updateOrderStatus } from '@/api/order'
import { initiatePayment, mockPaymentCallback } from '@/api/payment'
import { createRefund } from '@/api/refund'

const authStore = useAuthStore()
const role = computed(() => authStore.user?.role || '')

const loading = ref(false)
const orders = ref([])
const checkingStatusId = ref(null)
const updatingStatusId = ref(null)
const loadingLogId = ref(null)

const shipDialogVisible = ref(false)
const shipSubmitting = ref(false)
const shipForm = reactive({
  orderNo: '',
  tracking_no: '',
  logistics_company: '',
})

const logDialogVisible = ref(false)
const currentLogOrderId = ref(null)
const orderLogs = ref([])
const currentLogOrderNo = ref('')

const commentDialogVisible = ref(false)
const commentSubmitting = ref(false)
const commentForm = reactive({
  orderNo: '',
  rating: 5,
  content: '',
})

const refundDialogVisible = ref(false)
const refundSubmitting = ref(false)
const refundForm = reactive({
  orderId: null,
  reason: '',
  buyer_note: '',
})

const paymentDialogVisible = ref(false)
const paymentSubmitting = ref(false)
const paymentLoading = ref(false)
const currentPaymentOrder = ref(null)
const currentPayment = ref(null)
const paymentForm = reactive({
  channel: 'mock_alipay',
  failure_reason: '余额不足，模拟支付失败',
})
const canSubmitPayment = computed(() => currentPayment.value?.status === 'pending')

function statusType(status) {
  if (status === 'pending_paid') return 'warning'
  if (status === 'paid') return 'primary'
  if (status === 'shipped') return 'primary'
  if (status === 'completed') return 'success'
  if (status === 'closed') return 'info'
  if (status === 'cancelled') return 'danger'
  return 'info'
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

function payStatusType(status) {
  if (status === 'paid') return 'success'
  if (status === 'pending') return 'warning'
  if (status === 'refunded') return 'info'
  if (status === 'closed') return 'danger'
  return 'info'
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

function formatTime(value) {
  if (!value) return '-'
  const dt = new Date(value)
  if (Number.isNaN(dt.getTime())) return value
  return dt.toLocaleString()
}

function formatAddress(snapshot) {
  if (!snapshot) return '-'
  if (typeof snapshot !== 'string') return '-'
  try {
    const parsed = JSON.parse(snapshot)
    if (!parsed || typeof parsed !== 'object') return '-'
    const receiver = parsed.receiver_name || ''
    const phone = parsed.receiver_phone || ''
    const region = [parsed.province, parsed.city, parsed.district].filter(Boolean).join('')
    const detail = parsed.detail_address || ''
    const addressLine = `${region}${detail}`.trim()
    const head = [receiver, phone].filter(Boolean).join(' ')
    if (head && addressLine) return `${head}，${addressLine}`
    return head || addressLine || '-'
  } catch {
    return '-'
  }
}

function displayOrderNo(order) {
  return order.order_no || '-'
}

function formatReason(log) {
  return log.reason || '-'
}

function canCancel(order) {
  return role.value === 'buyer' && order.status === 'pending_paid'
}

function canReceive(order) {
  return role.value === 'buyer' && order.status === 'shipped'
}

function canShip(order) {
  return role.value === 'seller' && order.status === 'paid'
}

function canPay(order) {
  return role.value === 'buyer' && order.status === 'pending_paid'
}

function canComment(order) {
  return role.value === 'buyer' && order.status === 'completed'
}

function canApplyRefund(order) {
  return role.value === 'buyer' && order.pay_status === 'paid' && order.status !== 'shipped'
}

async function fetchOrders() {
  loading.value = true
  try {
    const res = await getOrders()
    orders.value = res.data || []
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '获取订单列表失败')
  } finally {
    loading.value = false
  }
}

async function handleGetLatestStatus(order) {
  checkingStatusId.value = order.order_no
  try {
    const res = await getOrderStatus(order.order_no)
    order.status = res.data?.status || order.status
    ElMessage.success(`订单 ${displayOrderNo(order)} 最新状态：${statusLabel(order.status)}`)
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '查询订单状态失败')
  } finally {
    checkingStatusId.value = null
  }
}

async function handleViewLogs(order) {
  loadingLogId.value = order.order_no
  try {
    const res = await getOrderLogs(order.order_no)
    orderLogs.value = res.data || []
    currentLogOrderId.value = order.id
    currentLogOrderNo.value = displayOrderNo(order)
    logDialogVisible.value = true
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '获取状态轨迹失败')
  } finally {
    loadingLogId.value = null
  }
}

async function handleCancelOrder(order) {
  updatingStatusId.value = order.order_no
  try {
    const res = await updateOrderStatus(order.order_no, 'cancelled')
    order.status = res.data?.status || 'cancelled'
    ElMessage.success(res.message || '订单已取消')
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '取消订单失败')
  } finally {
    updatingStatusId.value = null
  }
}

async function handlePayOrder(order) {
  currentPaymentOrder.value = order
  currentPayment.value = null
  paymentForm.channel = 'mock_alipay'
  paymentForm.failure_reason = '余额不足，模拟支付失败'
  paymentDialogVisible.value = true
  paymentLoading.value = true
  try {
    const res = await initiatePayment(order.order_no, paymentForm.channel)
    currentPayment.value = res.data
  } catch (error) {
    paymentDialogVisible.value = false
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '发起支付失败')
  } finally {
    paymentLoading.value = false
  }
}

async function submitMockPayment(result) {
  if (!currentPayment.value?.payment_no || !currentPaymentOrder.value) return
  paymentSubmitting.value = true
  updatingStatusId.value = currentPaymentOrder.value.order_no
  try {
    const res = await mockPaymentCallback(
      currentPayment.value.payment_no,
      result,
      result === 'failed' ? paymentForm.failure_reason.trim() : ''
    )
    currentPayment.value = res.data
    if (result === 'success') {
      ElMessage.success('模拟支付成功')
      paymentDialogVisible.value = false
      await fetchOrders()
    } else {
      ElMessage.warning('模拟支付失败，订单仍可重新支付')
    }
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '支付回调处理失败')
  } finally {
    paymentSubmitting.value = false
    updatingStatusId.value = null
  }
}

async function handleReceiveOrder(order) {
  updatingStatusId.value = order.order_no
  try {
    const res = await receiveOrder(order.order_no)
    order.status = res.data?.status || order.status
    order.received_at = res.data?.received_at || order.received_at
    ElMessage.success(res.message || '确认收货成功')
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '确认收货失败')
  } finally {
    updatingStatusId.value = null
  }
}

function openShipDialog(order) {
  shipForm.orderNo = order.order_no || ''
  shipForm.tracking_no = ''
  shipForm.logistics_company = ''
  shipDialogVisible.value = true
}

async function submitShip() {
  if (!shipForm.orderNo) return
  if (!shipForm.tracking_no.trim()) {
    ElMessage.warning('请填写物流单号')
    return
  }
  if (!shipForm.logistics_company.trim()) {
    ElMessage.warning('请填写物流公司')
    return
  }

  shipSubmitting.value = true
  try {
    const res = await shipOrder(shipForm.orderNo, {
      tracking_no: shipForm.tracking_no.trim(),
      logistics_company: shipForm.logistics_company.trim(),
    })
    ElMessage.success(res.message || '发货成功')
    shipDialogVisible.value = false
    await fetchOrders()
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '发货失败')
  } finally {
    shipSubmitting.value = false
  }
}

function openCommentDialog(order) {
  commentForm.orderNo = order.order_no || ''
  commentForm.rating = 5
  commentForm.content = ''
  commentDialogVisible.value = true
}

async function submitComment() {
  if (!commentForm.orderNo) return

  commentSubmitting.value = true
  try {
    const res = await createOrderComment(commentForm.orderNo, {
      rating: Number(commentForm.rating),
      content: commentForm.content.trim(),
    })
    ElMessage.success(res.message || '评价成功')
    commentDialogVisible.value = false
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '评价失败')
  } finally {
    commentSubmitting.value = false
  }
}

function openRefundDialog(order) {
  refundForm.orderId = order.id
  refundForm.reason = ''
  refundForm.buyer_note = ''
  refundDialogVisible.value = true
}

async function submitRefund() {
  if (!refundForm.orderId) return
  if (!refundForm.reason.trim()) {
    ElMessage.warning('请填写退款原因')
    return
  }

  refundSubmitting.value = true
  try {
    const res = await createRefund({
      order_id: refundForm.orderId,
      reason: refundForm.reason.trim(),
      buyer_note: refundForm.buyer_note.trim(),
    })
    ElMessage.success(res.message || '退款申请已提交')
    refundDialogVisible.value = false
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '退款申请失败')
  } finally {
    refundSubmitting.value = false
  }
}

onMounted(fetchOrders)
</script>

<template>
  <div class="orders-page">
    <section class="orders-head page-block">
      <div>
        <h1 class="page-title">订单中心</h1>
        <p class="page-subtitle">订单状态与物流信息实时同步，支持角色化操作。</p>
      </div>
      <el-button type="primary" @click="fetchOrders">刷新订单</el-button>
    </section>

    <section class="page-block table-wrap">
      <el-table v-loading="loading" :data="orders" stripe>
        <el-table-column label="订单号" min-width="220">
          <template #default="scope">{{ displayOrderNo(scope.row) }}</template>
        </el-table-column>
        <el-table-column prop="product_id" label="商品ID" width="92" />
        <el-table-column prop="total_price" label="总价" width="110">
          <template #default="scope">¥{{ Number(scope.row.total_price).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="130">
          <template #default="scope">
            <el-tag class="status-tag" :type="statusType(scope.row.status)">
              {{ statusLabel(scope.row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="支付状态" width="120">
          <template #default="scope">
            <el-tag :type="payStatusType(scope.row.pay_status)">
              {{ payStatusLabel(scope.row.pay_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="logistics_company" label="物流公司" min-width="140">
          <template #default="scope">{{ scope.row.logistics_company || '-' }}</template>
        </el-table-column>
        <el-table-column prop="tracking_no" label="物流单号" min-width="160">
          <template #default="scope">{{ scope.row.tracking_no || '-' }}</template>
        </el-table-column>
        <el-table-column label="收货地址" min-width="280" show-overflow-tooltip>
          <template #default="scope">{{ formatAddress(scope.row.address_snapshot) }}</template>
        </el-table-column>
        <el-table-column label="发货时间" min-width="170">
          <template #default="scope">{{ formatTime(scope.row.shipped_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="520" fixed="right">
          <template #default="scope">
            <div class="actions">
              <el-button :loading="checkingStatusId === scope.row.order_no" @click="handleGetLatestStatus(scope.row)">
                刷新状态
              </el-button>
              <el-button :loading="loadingLogId === scope.row.order_no" @click="handleViewLogs(scope.row)">
                状态轨迹
              </el-button>

              <el-button
                v-if="canPay(scope.row)"
                type="warning"
                :loading="updatingStatusId === scope.row.order_no"
                @click="handlePayOrder(scope.row)"
              >
                模拟支付
              </el-button>

              <el-button
                v-if="canShip(scope.row)"
                type="primary"
                :loading="updatingStatusId === scope.row.order_no"
                @click="openShipDialog(scope.row)"
              >
                发货
              </el-button>

              <el-button
                v-if="canReceive(scope.row)"
                type="success"
                :loading="updatingStatusId === scope.row.order_no"
                @click="handleReceiveOrder(scope.row)"
              >
                确认收货
              </el-button>

              <el-button
                v-if="canCancel(scope.row)"
                type="danger"
                :loading="updatingStatusId === scope.row.order_no"
                @click="handleCancelOrder(scope.row)"
              >
                取消订单
              </el-button>

              <el-button
                v-if="canApplyRefund(scope.row)"
                type="danger"
                plain
                @click="openRefundDialog(scope.row)"
              >
                申请退款
              </el-button>

              <el-button
                v-if="canComment(scope.row)"
                type="success"
                plain
                @click="openCommentDialog(scope.row)"
              >
                评价订单
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-dialog v-model="shipDialogVisible" title="填写发货信息" width="460px">
      <el-form label-position="top">
        <el-form-item label="物流公司">
          <el-input v-model="shipForm.logistics_company" placeholder="如：顺丰速运" />
        </el-form-item>
        <el-form-item label="物流单号">
          <el-input v-model="shipForm.tracking_no" placeholder="请输入快递单号" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="shipDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="shipSubmitting" @click="submitShip">确认发货</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="paymentDialogVisible" title="模拟支付宝支付" width="520px">
      <div v-loading="paymentLoading" class="payment-panel">
        <div class="payment-row">
          <span>订单号</span>
          <strong>{{ currentPaymentOrder?.order_no || '-' }}</strong>
        </div>
        <div class="payment-row">
          <span>支付金额</span>
          <strong>¥{{ Number(currentPaymentOrder?.pay_amount || currentPaymentOrder?.total_price || 0).toFixed(2) }}</strong>
        </div>
        <div class="payment-row">
          <span>支付渠道</span>
          <el-select v-model="paymentForm.channel" :disabled="Boolean(currentPayment)" size="small" style="width: 160px">
            <el-option label="支付宝沙箱模拟" value="mock_alipay" />
            <el-option label="平台模拟支付" value="mock_platform" />
          </el-select>
        </div>
        <div class="payment-row">
          <span>支付流水</span>
          <strong>{{ currentPayment?.payment_no || '-' }}</strong>
        </div>
        <div class="payment-row">
          <span>流水状态</span>
          <el-tag v-if="currentPayment" :type="currentPayment.status === 'failed' ? 'danger' : currentPayment.status === 'succeeded' ? 'success' : 'warning'">
            {{ currentPayment.status }}
          </el-tag>
          <span v-else>-</span>
        </div>
        <el-input
          v-model="paymentForm.failure_reason"
          type="textarea"
          :rows="2"
          maxlength="2000"
          show-word-limit
          placeholder="模拟失败原因"
        />
      </div>
      <template #footer>
        <el-button @click="paymentDialogVisible = false">取消</el-button>
        <el-button :disabled="!canSubmitPayment" :loading="paymentSubmitting" @click="submitMockPayment('failed')">
          模拟失败
        </el-button>
        <el-button type="primary" :disabled="!canSubmitPayment" :loading="paymentSubmitting" @click="submitMockPayment('success')">
          模拟成功
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="logDialogVisible" :title="`订单 ${currentLogOrderNo || currentLogOrderId || ''} 状态轨迹`" width="640px">
      <el-empty v-if="!orderLogs.length" description="该订单暂无状态变更记录" />
      <el-timeline v-else>
        <el-timeline-item
          v-for="log in orderLogs"
          :key="log.id"
          :timestamp="formatTime(log.created_at)"
          placement="top"
        >
          <div class="log-item">
            <div>
              <strong>{{ statusLabel(log.from_status) }}</strong>
              <span class="arrow">→</span>
              <strong>{{ statusLabel(log.to_status) }}</strong>
            </div>
            <div class="log-meta">操作者：{{ log.actor_role }} #{{ log.actor_id }}</div>
            <div class="log-meta">原因：{{ formatReason(log) }}</div>
          </div>
        </el-timeline-item>
      </el-timeline>
      <template #footer>
        <el-button type="primary" @click="logDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="commentDialogVisible" title="订单评价" width="520px">
      <el-form label-position="top">
        <el-form-item label="评分">
          <el-rate v-model="commentForm.rating" :max="5" />
        </el-form-item>
        <el-form-item label="评价内容">
          <el-input v-model="commentForm.content" type="textarea" :rows="4" maxlength="2000" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="commentDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="commentSubmitting" @click="submitComment">提交评价</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="refundDialogVisible" title="申请退款" width="560px">
      <el-form label-position="top">
        <el-form-item label="退款原因" required>
          <el-input v-model="refundForm.reason" type="textarea" :rows="3" maxlength="2000" show-word-limit />
        </el-form-item>
        <el-form-item label="补充说明">
          <el-input v-model="refundForm.buyer_note" type="textarea" :rows="3" maxlength="2000" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="refundDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="refundSubmitting" @click="submitRefund">提交申请</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.orders-page {
  display: grid;
  gap: 16px;
}

.orders-head {
  padding: 18px 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.table-wrap {
  padding: 12px;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.log-item {
  display: grid;
  gap: 4px;
}

.arrow {
  margin: 0 8px;
  color: #8a8f99;
}

.log-meta {
  color: #6d7481;
  font-size: 13px;
}

.payment-panel {
  display: grid;
  gap: 12px;
}

.payment-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 32px;
}

.payment-row span {
  color: #6d7481;
}

.payment-row strong {
  min-width: 0;
  overflow-wrap: anywhere;
  text-align: right;
}

@media (max-width: 768px) {
  .orders-head {
    flex-direction: column;
    align-items: flex-start;
  }

  .payment-row {
    align-items: flex-start;
    flex-direction: column;
  }

  .payment-row strong {
    text-align: left;
  }
}
</style>
