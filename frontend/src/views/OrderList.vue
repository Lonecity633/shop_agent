<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { getOrderLogs, getOrderStatus, getOrders, payOrder, receiveOrder, shipOrder, updateOrderStatus } from '@/api/order'

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
  orderId: null,
  tracking_no: '',
  logistics_company: '',
})

const logDialogVisible = ref(false)
const currentLogOrderId = ref(null)
const orderLogs = ref([])

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

function formatTime(value) {
  if (!value) return '-'
  const dt = new Date(value)
  if (Number.isNaN(dt.getTime())) return value
  return dt.toLocaleString()
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

async function fetchOrders() {
  loading.value = true
  try {
    const res = await getOrders()
    orders.value = res.data || []
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '获取订单列表失败')
  } finally {
    loading.value = false
  }
}

async function handleGetLatestStatus(order) {
  checkingStatusId.value = order.id
  try {
    const res = await getOrderStatus(order.id)
    order.status = res.data?.status || order.status
    ElMessage.success(`订单 ${order.id} 最新状态：${statusLabel(order.status)}`)
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '查询订单状态失败')
  } finally {
    checkingStatusId.value = null
  }
}

async function handleViewLogs(order) {
  loadingLogId.value = order.id
  try {
    const res = await getOrderLogs(order.id)
    orderLogs.value = res.data || []
    currentLogOrderId.value = order.id
    logDialogVisible.value = true
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '获取状态轨迹失败')
  } finally {
    loadingLogId.value = null
  }
}

async function handleCancelOrder(order) {
  updatingStatusId.value = order.id
  try {
    const res = await updateOrderStatus(order.id, 'cancelled')
    order.status = res.data?.status || 'cancelled'
    ElMessage.success(res.message || '订单已取消')
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '取消订单失败')
  } finally {
    updatingStatusId.value = null
  }
}

async function handlePayOrder(order) {
  updatingStatusId.value = order.id
  try {
    const res = await payOrder(order.id, 'simulated')
    order.status = res.data?.status || order.status
    order.pay_status = res.data?.pay_status || order.pay_status
    ElMessage.success(res.message || '支付成功')
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '支付失败')
  } finally {
    updatingStatusId.value = null
  }
}

async function handleReceiveOrder(order) {
  updatingStatusId.value = order.id
  try {
    const res = await receiveOrder(order.id)
    order.status = res.data?.status || order.status
    order.received_at = res.data?.received_at || order.received_at
    ElMessage.success(res.message || '确认收货成功')
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '确认收货失败')
  } finally {
    updatingStatusId.value = null
  }
}

function openShipDialog(order) {
  shipForm.orderId = order.id
  shipForm.tracking_no = ''
  shipForm.logistics_company = ''
  shipDialogVisible.value = true
}

async function submitShip() {
  if (!shipForm.orderId) return
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
    const res = await shipOrder(shipForm.orderId, {
      tracking_no: shipForm.tracking_no.trim(),
      logistics_company: shipForm.logistics_company.trim(),
    })
    ElMessage.success(res.message || '发货成功')
    shipDialogVisible.value = false
    await fetchOrders()
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '发货失败')
  } finally {
    shipSubmitting.value = false
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
        <el-table-column prop="id" label="订单ID" width="92" />
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
        <el-table-column prop="logistics_company" label="物流公司" min-width="140">
          <template #default="scope">{{ scope.row.logistics_company || '-' }}</template>
        </el-table-column>
        <el-table-column prop="tracking_no" label="物流单号" min-width="160">
          <template #default="scope">{{ scope.row.tracking_no || '-' }}</template>
        </el-table-column>
        <el-table-column label="发货时间" min-width="170">
          <template #default="scope">{{ formatTime(scope.row.shipped_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="340" fixed="right">
          <template #default="scope">
            <div class="actions">
              <el-button :loading="checkingStatusId === scope.row.id" @click="handleGetLatestStatus(scope.row)">
                刷新状态
              </el-button>
              <el-button :loading="loadingLogId === scope.row.id" @click="handleViewLogs(scope.row)">
                状态轨迹
              </el-button>

              <el-button
                v-if="canPay(scope.row)"
                type="warning"
                :loading="updatingStatusId === scope.row.id"
                @click="handlePayOrder(scope.row)"
              >
                模拟支付
              </el-button>

              <el-button
                v-if="canShip(scope.row)"
                type="primary"
                :loading="updatingStatusId === scope.row.id"
                @click="openShipDialog(scope.row)"
              >
                发货
              </el-button>

              <el-button
                v-if="canReceive(scope.row)"
                type="success"
                :loading="updatingStatusId === scope.row.id"
                @click="handleReceiveOrder(scope.row)"
              >
                确认收货
              </el-button>

              <el-button
                v-if="canCancel(scope.row)"
                type="danger"
                :loading="updatingStatusId === scope.row.id"
                @click="handleCancelOrder(scope.row)"
              >
                取消订单
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

    <el-dialog v-model="logDialogVisible" :title="`订单 ${currentLogOrderId || ''} 状态轨迹`" width="640px">
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

@media (max-width: 768px) {
  .orders-head {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
