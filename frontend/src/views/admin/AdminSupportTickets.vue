<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  closeAdminSupportTicket,
  getAdminSupportTickets,
  rejectAdminSupportTicket,
  resolveAdminSupportTicket,
} from '@/api/admin'

const router = useRouter()
const loading = ref(false)
const tickets = ref([])
const actionLoadingId = ref(null)
const dialogVisible = ref(false)
const currentAction = ref('resolve')
const currentTicket = ref(null)
const form = reactive({ replyContent: '' })
const filter = reactive({
  status: 'all',
  assigned_role: 'all',
  category: 'all',
  keyword: '',
})

function statusType(status) {
  if (status === 'pending' || status === 'processing') return 'warning'
  if (status === 'replied') return 'success'
  if (status === 'cancelled' || status === 'closed') return 'info'
  if (status === 'escalated') return 'primary'
  return ''
}

function statusLabel(status) {
  const map = {
    pending: '待处理',
    processing: '处理中',
    replied: '已回复',
    closed: '已关闭',
    cancelled: '已取消',
    escalated: '已升级',
  }
  return map[status] || status
}

function roleLabel(value) {
  return value === 'seller' ? '卖家' : '管理员'
}

function formatTime(value) {
  if (!value) return '-'
  const dt = new Date(value)
  if (Number.isNaN(dt.getTime())) return value
  return dt.toLocaleString()
}

function canHandle(row) {
  return !['replied', 'cancelled', 'closed'].includes(row.status)
}

async function loadTickets() {
  loading.value = true
  try {
    const res = await getAdminSupportTickets({
      status: filter.status,
      assigned_role: filter.assigned_role,
      category: filter.category,
      keyword: filter.keyword || undefined,
    })
    tickets.value = res.data || []
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '加载人工工单池失败')
  } finally {
    loading.value = false
  }
}

function openAction(row, action) {
  currentTicket.value = row
  currentAction.value = action
  form.replyContent = ''
  dialogVisible.value = true
}

async function submitAction() {
  if (!currentTicket.value) return
  if (currentAction.value !== 'close' && !form.replyContent.trim()) {
    ElMessage.warning('请填写处理说明')
    return
  }
  actionLoadingId.value = currentTicket.value.id
  try {
    const payload = { reply_content: form.replyContent.trim() }
    if (currentAction.value === 'resolve') {
      await resolveAdminSupportTicket(currentTicket.value.id, payload)
      ElMessage.success('工单已回复')
    } else if (currentAction.value === 'reject') {
      await rejectAdminSupportTicket(currentTicket.value.id, payload)
      ElMessage.success('工单已取消')
    } else {
      await closeAdminSupportTicket(currentTicket.value.id, payload)
      ElMessage.success('工单已关闭')
    }
    dialogVisible.value = false
    await loadTickets()
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '操作失败')
  } finally {
    actionLoadingId.value = null
  }
}

onMounted(loadTickets)
</script>

<template>
  <div class="admin-ticket-page">
    <section class="page-block head-row">
      <div>
        <el-button text @click="router.push('/admin/dashboard')">返回后台</el-button>
        <h1 class="page-title">人工客服工单池</h1>
        <p class="page-subtitle">处理 AI 转人工、Guardrail、高风险和卖家升级工单。</p>
      </div>
      <el-button type="primary" @click="loadTickets">刷新</el-button>
    </section>

    <section class="page-block filters">
      <el-select v-model="filter.status" style="width: 140px" @change="loadTickets">
        <el-option label="全部状态" value="all" />
        <el-option label="待处理" value="pending" />
        <el-option label="处理中" value="processing" />
        <el-option label="已升级" value="escalated" />
        <el-option label="已回复" value="replied" />
        <el-option label="已取消" value="cancelled" />
        <el-option label="已关闭" value="closed" />
      </el-select>
      <el-select v-model="filter.assigned_role" style="width: 140px" @change="loadTickets">
        <el-option label="全部处理方" value="all" />
        <el-option label="管理员" value="admin" />
        <el-option label="卖家" value="seller" />
      </el-select>
      <el-select v-model="filter.category" style="width: 150px" @change="loadTickets">
        <el-option label="全部分类" value="all" />
        <el-option label="商品咨询" value="product_consultation" />
        <el-option label="物流问题" value="logistics_issue" />
        <el-option label="退款售后" value="refund_issue" />
        <el-option label="质量问题" value="quality_issue" />
        <el-option label="投诉" value="complaint" />
        <el-option label="支付异常" value="payment_issue" />
        <el-option label="平台规则" value="platform_rule" />
        <el-option label="其他" value="other" />
      </el-select>
      <el-input
        v-model="filter.keyword"
        clearable
        placeholder="工单/订单/关键词"
        style="width: 220px"
        @keyup.enter="loadTickets"
        @clear="loadTickets"
      />
      <el-button @click="loadTickets">筛选</el-button>
    </section>

    <section class="page-block">
      <el-table v-loading="loading" :data="tickets" border stripe>
        <el-table-column prop="id" label="工单ID" width="90" />
        <el-table-column prop="title" label="标题" min-width="220" show-overflow-tooltip />
        <el-table-column label="状态" width="110">
          <template #default="scope">
            <el-tag :type="statusType(scope.row.status)">{{ statusLabel(scope.row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="处理方" width="100">
          <template #default="scope">{{ roleLabel(scope.row.assigned_role) }}</template>
        </el-table-column>
        <el-table-column prop="category" label="分类" width="100" />
        <el-table-column prop="source" label="来源" width="130" />
        <el-table-column prop="content" label="描述" min-width="240" show-overflow-tooltip />
        <el-table-column prop="reply_content" label="回复" min-width="180" show-overflow-tooltip />
        <el-table-column prop="trigger_reason" label="触发原因" min-width="180" show-overflow-tooltip />
        <el-table-column label="创建时间" min-width="170">
          <template #default="scope">{{ formatTime(scope.row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="scope">
            <div class="actions" v-if="canHandle(scope.row)">
              <el-button size="small" type="success" :loading="actionLoadingId === scope.row.id" @click="openAction(scope.row, 'resolve')">解决</el-button>
              <el-button size="small" type="danger" :loading="actionLoadingId === scope.row.id" @click="openAction(scope.row, 'reject')">取消</el-button>
              <el-button size="small" :loading="actionLoadingId === scope.row.id" @click="openAction(scope.row, 'close')">关闭</el-button>
            </div>
            <span v-else>-</span>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-dialog v-model="dialogVisible" title="处理人工工单" width="560px">
      <el-input v-model="form.replyContent" type="textarea" :rows="4" maxlength="8000" show-word-limit placeholder="请输入处理说明" />
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="actionLoadingId === currentTicket?.id" @click="submitAction">确认提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.admin-ticket-page {
  display: grid;
  gap: 16px;
}

.head-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.filters,
.actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
</style>
