<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getMySupportTickets } from '@/api/support'
import { escalateSellerSupportTicket, getSellerSupportTickets, resolveSellerSupportTicket } from '@/api/seller'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const role = computed(() => authStore.user?.role || '')
const isSeller = computed(() => role.value === 'seller')

const loading = ref(false)
const tickets = ref([])
const actionLoadingId = ref(null)
const resolveDialogVisible = ref(false)
const escalateDialogVisible = ref(false)
const currentTicket = ref(null)
const form = reactive({
  replyContent: '',
  reason: '',
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
  return isSeller.value && row.assigned_role === 'seller' && !['replied', 'cancelled', 'closed', 'escalated'].includes(row.status)
}

async function loadTickets() {
  loading.value = true
  try {
    const res = isSeller.value ? await getSellerSupportTickets() : await getMySupportTickets()
    tickets.value = res.data || []
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '加载人工工单失败')
  } finally {
    loading.value = false
  }
}

function openResolve(row) {
  currentTicket.value = row
  form.replyContent = ''
  resolveDialogVisible.value = true
}

function openEscalate(row) {
  currentTicket.value = row
  form.reason = ''
  escalateDialogVisible.value = true
}

async function submitResolve() {
  if (!currentTicket.value || !form.replyContent.trim()) {
    ElMessage.warning('请填写处理结果')
    return
  }
  actionLoadingId.value = currentTicket.value.id
  try {
    await resolveSellerSupportTicket(currentTicket.value.id, { reply_content: form.replyContent.trim() })
    ElMessage.success('工单已回复')
    resolveDialogVisible.value = false
    await loadTickets()
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '处理失败')
  } finally {
    actionLoadingId.value = null
  }
}

async function submitEscalate() {
  if (!currentTicket.value || !form.reason.trim()) {
    ElMessage.warning('请填写升级原因')
    return
  }
  actionLoadingId.value = currentTicket.value.id
  try {
    await escalateSellerSupportTicket(currentTicket.value.id, { reason: form.reason.trim() })
    ElMessage.success('工单已升级给管理员')
    escalateDialogVisible.value = false
    await loadTickets()
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '升级失败')
  } finally {
    actionLoadingId.value = null
  }
}

onMounted(loadTickets)
</script>

<template>
  <div class="tickets-page">
    <section class="page-block tickets-head">
      <div>
        <h1 class="page-title">人工客服工单</h1>
        <p class="page-subtitle">{{ isSeller ? '处理分配给店铺的人工工单。' : '查看智能客服转人工后的处理进度。' }}</p>
      </div>
      <el-button type="primary" @click="loadTickets">刷新</el-button>
    </section>

    <section class="page-block">
      <el-empty v-if="!loading && !tickets.length" description="暂无人工工单" />
      <el-table v-else v-loading="loading" :data="tickets" border stripe>
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
        <el-table-column prop="category" label="分类" width="110" />
        <el-table-column prop="priority" label="优先级" width="100" />
        <el-table-column prop="content" label="问题描述" min-width="260" show-overflow-tooltip />
        <el-table-column prop="reply_content" label="回复内容" min-width="220" show-overflow-tooltip />
        <el-table-column label="创建时间" min-width="170">
          <template #default="scope">{{ formatTime(scope.row.created_at) }}</template>
        </el-table-column>
        <el-table-column v-if="isSeller" label="操作" width="190" fixed="right">
          <template #default="scope">
            <div class="actions" v-if="canHandle(scope.row)">
              <el-button size="small" type="success" :loading="actionLoadingId === scope.row.id" @click="openResolve(scope.row)">解决</el-button>
              <el-button size="small" type="warning" :loading="actionLoadingId === scope.row.id" @click="openEscalate(scope.row)">升级</el-button>
            </div>
            <span v-else>-</span>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-dialog v-model="resolveDialogVisible" title="解决人工工单" width="560px">
      <el-input v-model="form.replyContent" type="textarea" :rows="4" maxlength="8000" show-word-limit placeholder="请输入处理结果" />
      <template #footer>
        <el-button @click="resolveDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="actionLoadingId === currentTicket?.id" @click="submitResolve">确认解决</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="escalateDialogVisible" title="升级给管理员" width="560px">
      <el-input v-model="form.reason" type="textarea" :rows="4" maxlength="4000" show-word-limit placeholder="请输入升级原因" />
      <template #footer>
        <el-button @click="escalateDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="actionLoadingId === currentTicket?.id" @click="submitEscalate">确认升级</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.tickets-page {
  display: grid;
  gap: 16px;
}

.tickets-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.actions {
  display: flex;
  gap: 8px;
}
</style>
