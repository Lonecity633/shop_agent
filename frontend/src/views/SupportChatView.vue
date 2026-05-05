<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { autoReply, createMySupportSession, getMyLatestSupportSession, getSupportMessages } from '@/api/support'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const role = computed(() => authStore.user?.role || '')
const userId = computed(() => authStore.user?.id || '')

const loading = ref(false)
const sending = ref(false)
const messages = ref([])
const input = ref('')
const sessionId = ref(null)
const chatBody = ref(null)

function sessionStorageKey() {
  return userId.value ? `support_session_id_${userId.value}` : 'support_session_id_guest'
}

function formatTime(value) {
  if (!value) return '-'
  const dt = new Date(value)
  if (Number.isNaN(dt.getTime())) return value
  return dt.toLocaleString()
}

function normalizeMessages(rows) {
  const visibleRoles = new Set(['system', 'user', 'assistant'])
  return (rows || [])
    .filter((item) => visibleRoles.has(item.role))
    .map((item) => ({
      id: item.id,
      role: item.role,
      content: item.content,
      created_at: item.created_at,
    }))
}

async function ensureSession() {
  if (sessionId.value) return sessionId.value
  const cached = Number(localStorage.getItem(sessionStorageKey()) || 0) || null
  if (cached) {
    sessionId.value = cached
    return sessionId.value
  }
  try {
    const latest = await getMyLatestSupportSession()
    const latestId = latest.data?.id
    if (latestId) {
      sessionId.value = Number(latestId)
      localStorage.setItem(sessionStorageKey(), String(sessionId.value))
      return sessionId.value
    }
  } catch {
    // ignore and fallback to create session
  }
  const res = await createMySupportSession({ question: '买家发起客服会话', queried_entities: [] })
  sessionId.value = res.data?.id
  if (sessionId.value) {
    localStorage.setItem(sessionStorageKey(), String(sessionId.value))
  }
  return sessionId.value
}

async function loadMessages() {
  if (!sessionId.value) return
  const res = await getSupportMessages(sessionId.value)
  messages.value = normalizeMessages(res.data)
  await nextTick()
  scrollToBottom()
}

function scrollToBottom() {
  if (!chatBody.value) return
  chatBody.value.scrollTop = chatBody.value.scrollHeight
}

async function sendMessage() {
  const content = input.value.trim()
  if (!content || sending.value) return

  sending.value = true
  const localUserId = Date.now()
  messages.value.push({ id: localUserId, role: 'user', content, created_at: new Date().toISOString() })
  input.value = ''
  await nextTick()
  scrollToBottom()

  try {
    let sid = await ensureSession()
    let res
    try {
      res = await autoReply(sid, { content })
    } catch (error) {
      if (error?.response?.status === 404) {
        localStorage.removeItem(sessionStorageKey())
        sessionId.value = null
        sid = await ensureSession()
        res = await autoReply(sid, { content })
      } else {
        throw error
      }
    }
    messages.value.push({
      id: `${localUserId}-a`,
      role: 'assistant',
      content: res.data?.answer || '暂无回复',
      created_at: new Date().toISOString(),
    })
    await nextTick()
    scrollToBottom()
    await loadMessages()
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '发送失败')
  } finally {
    sending.value = false
  }
}

async function initChat() {
  if (role.value !== 'buyer') {
    ElMessage.warning('当前账号不是买家，无法使用该客服入口')
    return
  }
  loading.value = true
  try {
    await ensureSession()
    await loadMessages()
  } catch (error) {
    if (sessionId.value && error?.response?.status === 404) {
      localStorage.removeItem(sessionStorageKey())
      sessionId.value = null
      await ensureSession()
      await loadMessages()
    } else {
      ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '客服会话初始化失败')
    }
  } finally {
    loading.value = false
  }
}

onMounted(initChat)
</script>

<template>
  <div class="support-page">
    <section class="page-block support-head">
      <div>
        <h1 class="page-title">在线客服</h1>
        <p class="page-subtitle">可直接咨询订单、物流、发票、售后等问题。</p>
      </div>
    </section>

    <section class="page-block support-chat" v-loading="loading">
      <div ref="chatBody" class="chat-body">
        <el-empty v-if="!messages.length" description="开始输入你的问题" />
        <div v-for="item in messages" :key="item.id" class="msg-row" :class="item.role">
          <div class="msg-bubble">
            <div class="msg-content">{{ item.content }}</div>
            <div class="msg-time">{{ formatTime(item.created_at) }}</div>
          </div>
        </div>
      </div>

      <div class="chat-editor">
        <el-input
          v-model="input"
          type="textarea"
          :rows="3"
          maxlength="2000"
          show-word-limit
          placeholder="请输入咨询内容"
          @keyup.ctrl.enter="sendMessage"
        />
        <div class="editor-actions">
          <el-button type="primary" :loading="sending" @click="sendMessage">发送</el-button>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.support-page {
  display: grid;
  gap: 16px;
}

.support-chat {
  padding: 12px;
}

.chat-body {
  max-height: 55vh;
  overflow-y: auto;
  padding: 8px;
  background: #fffaf7;
  border: 1px solid #f2dfd7;
  border-radius: 12px;
}

.msg-row {
  display: flex;
  margin-bottom: 10px;
}

.msg-row.user {
  justify-content: flex-end;
}

.msg-row.assistant {
  justify-content: flex-start;
}

.msg-bubble {
  max-width: min(86%, 680px);
  padding: 10px 12px;
  border-radius: 10px;
  background: #fff;
  border: 1px solid #ead8cf;
}

.msg-row.user .msg-bubble {
  background: #fff1eb;
  border-color: #f5c4b0;
}

.msg-content {
  white-space: pre-wrap;
  word-break: break-word;
  color: #2e2e2e;
}

.msg-time {
  margin-top: 6px;
  font-size: 12px;
  color: #8a8f99;
}

.chat-editor {
  margin-top: 12px;
}

.editor-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 8px;
}
</style>
