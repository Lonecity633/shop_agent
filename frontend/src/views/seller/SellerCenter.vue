<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getSellerProfile, saveSellerProfile } from '@/api/seller'

const loading = ref(false)
const formLoading = ref(false)
const form = reactive({
  shop_name: '',
  shop_description: '',
})
const profileInfo = ref(null)

async function loadProfile() {
  loading.value = true
  try {
    const res = await getSellerProfile()
    profileInfo.value = res.data
    if (res.data) {
      form.shop_name = res.data.shop_name || ''
      form.shop_description = res.data.shop_description || ''
    }
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '加载店铺资料失败')
  } finally {
    loading.value = false
  }
}

async function submitProfile() {
  if (!form.shop_name.trim()) {
    ElMessage.warning('店铺名称不能为空')
    return
  }
  formLoading.value = true
  try {
    const res = await saveSellerProfile({
      shop_name: form.shop_name.trim(),
      shop_description: form.shop_description,
    })
    profileInfo.value = res.data
    ElMessage.success(res.message || '保存成功')
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '保存失败')
  } finally {
    formLoading.value = false
  }
}

onMounted(loadProfile)
</script>

<template>
  <div class="page-wrap" v-loading="loading">
    <el-card>
      <template #header>
        <strong>店铺资料</strong>
      </template>

      <el-alert
        v-if="profileInfo"
        :title="`审核状态：${profileInfo.audit_status}`"
        type="info"
        show-icon
        :closable="false"
        class="mb-12"
      />

      <el-form label-position="top">
        <el-form-item label="店铺名称">
          <el-input v-model="form.shop_name" maxlength="120" show-word-limit />
        </el-form-item>
        <el-form-item label="店铺描述">
          <el-input v-model="form.shop_description" type="textarea" :rows="4" maxlength="2000" show-word-limit />
        </el-form-item>
        <el-button type="primary" :loading="formLoading" @click="submitProfile">保存资料</el-button>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.page-wrap { display: grid; gap: 16px; }
.mb-12 { margin-bottom: 12px; }
</style>
