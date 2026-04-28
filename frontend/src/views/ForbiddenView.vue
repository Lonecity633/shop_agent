<script setup>
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<template>
  <div class="forbidden-wrap">
    <el-result icon="warning" title="403 无权限" sub-title="你没有权限访问该页面。">
      <template #extra>
        <el-button type="primary" @click="router.push('/products')">返回首页</el-button>
      </template>
    </el-result>
  </div>
</template>

<style scoped>
.forbidden-wrap {
  min-height: 60vh;
  display: grid;
  place-items: center;
}
</style>
