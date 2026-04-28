<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import UserAvatar from '@/components/UserAvatar.vue'
import { normalizeAvatarUrl } from '@/utils/avatar'

const authStore = useAuthStore()
const saving = ref(false)

const user = computed(() => authStore.user || {})

const form = reactive({
  display_name: '',
  phone: '',
  avatar_url: '',
})

watch(
  user,
  (value) => {
    form.display_name = value.display_name || ''
    form.phone = value.phone || ''
    form.avatar_url = value.avatar_url || ''
  },
  { immediate: true }
)

const roleLabel = computed(() => {
  if (user.value.role === 'admin') return '管理员'
  if (user.value.role === 'seller') return '卖家'
  return '买家'
})

const avatarPreview = computed(() => normalizeAvatarUrl(form.avatar_url))

function formatTime(value) {
  if (!value) return '-'
  const dt = new Date(value)
  if (Number.isNaN(dt.getTime())) return value
  return dt.toLocaleString()
}

async function handleSave() {
  saving.value = true
  try {
    const payload = {
      display_name: form.display_name,
      phone: form.phone,
      avatar_url: normalizeAvatarUrl(form.avatar_url),
    }
    const res = await authStore.updateProfile(payload)
    ElMessage.success(res.message || '个人资料保存成功')
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <el-card class="profile-card">
    <template #header>
      <div class="card-header">
        <strong>个人信息</strong>
        <el-tag type="danger" effect="plain">{{ roleLabel }}</el-tag>
      </div>
    </template>

    <div class="profile-layout">
      <aside class="avatar-box">
        <UserAvatar :size="100" :src="avatarPreview" :text="form.display_name || user.email || '?'" />
        <div class="avatar-tips">支持填写头像 URL（留空则显示默认头像）</div>
      </aside>

      <section class="form-box">
        <el-form label-width="96px">
          <el-form-item label="用户 ID">
            <el-input :model-value="String(user.id || '-')" disabled />
          </el-form-item>
          <el-form-item label="邮箱">
            <el-input :model-value="user.email || '-'" disabled />
          </el-form-item>
          <el-form-item label="昵称">
            <el-input v-model="form.display_name" maxlength="60" placeholder="请输入昵称" show-word-limit />
          </el-form-item>
          <el-form-item label="电话">
            <el-input v-model="form.phone" maxlength="30" placeholder="请输入电话" />
          </el-form-item>
          <el-form-item label="头像链接">
            <el-input v-model="form.avatar_url" maxlength="512" placeholder="https://example.com/avatar.png" />
          </el-form-item>
          <el-form-item label="注册时间">
            <el-input :model-value="formatTime(user.created_at)" disabled />
          </el-form-item>
          <el-form-item label="更新时间">
            <el-input :model-value="formatTime(user.updated_at)" disabled />
          </el-form-item>
        </el-form>

        <div class="actions">
          <el-button type="danger" :loading="saving" @click="handleSave">保存个人信息</el-button>
        </div>
      </section>
    </div>
  </el-card>
</template>

<style scoped>
.profile-card {
  border-radius: 14px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.profile-layout {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 24px;
}

.avatar-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  padding-top: 8px;
}

.avatar-tips {
  color: #7b8190;
  font-size: 12px;
  line-height: 1.5;
  text-align: center;
}

.form-box {
  min-width: 0;
}

.actions {
  display: flex;
  justify-content: flex-end;
}

@media (max-width: 900px) {
  .profile-layout {
    grid-template-columns: 1fr;
    gap: 14px;
  }

  .avatar-box {
    align-items: flex-start;
  }

  .actions {
    justify-content: flex-start;
  }
}
</style>
