<script setup>
import { computed, ref, watch } from 'vue'
import { normalizeAvatarUrl } from '@/utils/avatar'

const props = defineProps({
  src: {
    type: String,
    default: '',
  },
  size: {
    type: Number,
    default: 40,
  },
  text: {
    type: String,
    default: '',
  },
})

const hasError = ref(false)

watch(
  () => props.src,
  () => {
    hasError.value = false
  }
)

const safeSrc = computed(() => normalizeAvatarUrl(props.src))
const sizeStyle = computed(() => ({
  width: `${props.size}px`,
  height: `${props.size}px`,
  fontSize: `${Math.max(12, Math.floor(props.size * 0.42))}px`,
}))
const fallbackText = computed(() => String(props.text || '?').slice(0, 1).toUpperCase())

function onError() {
  hasError.value = true
}
</script>

<template>
  <div class="user-avatar" :style="sizeStyle">
    <img v-if="safeSrc && !hasError" :src="safeSrc" alt="avatar" referrerpolicy="no-referrer" @error="onError" />
    <span v-else>{{ fallbackText }}</span>
  </div>
</template>

<style scoped>
.user-avatar {
  border-radius: 50%;
  overflow: hidden;
  background: #f5d8d3;
  color: #b42318;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  line-height: 1;
}

.user-avatar img {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
}
</style>
