<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { createMyProduct, deleteMyProduct, getMyProducts, updateMyProduct, uploadProductImage } from '@/api/seller'
import { getCategories } from '@/api/category'

const loading = ref(false)
const submitLoading = ref(false)
const products = ref([])
const categories = ref([])
const categoriesLoading = ref(false)
const dialogVisible = ref(false)
const editingId = ref(null)

const FALLBACK_IMAGE =
  'data:image/svg+xml;utf8,' +
  encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="300" height="200"><defs><linearGradient id="g" x1="0" x2="1" y1="0" y2="1"><stop stop-color="#fff0ec" offset="0"/><stop stop-color="#ffe2cb" offset="1"/></linearGradient></defs><rect fill="url(#g)" width="300" height="200" rx="18"/><text x="50%" y="46%" dominant-baseline="middle" text-anchor="middle" font-size="20" fill="#c14a33" font-family="Arial">商品图</text><text x="50%" y="58%" dominant-baseline="middle" text-anchor="middle" font-size="14" fill="#9d5e49" font-family="Arial">未设置</text></svg>'
  )

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1'
const BACKEND_ORIGIN = API_BASE.replace(/\/api\/v1\/?$/, '')

function resolveImageUrl(url) {
  if (!url) return FALLBACK_IMAGE
  if (url.startsWith('/uploads/')) return BACKEND_ORIGIN + url
  return url
}

const form = reactive({
  name: '',
  description: '',
  stock: 0,
  price: 0,
  category_id: null,
  image_urls: [],
})

const imageUploading = ref(false)

function statusType(status) {
  if (status === 'approved') return 'success'
  if (status === 'rejected') return 'danger'
  return 'warning'
}

function statusLabel(status) {
  const map = {
    pending: '待审核',
    approved: '已通过',
    rejected: '已驳回',
  }
  return map[status] || status
}

function resetForm() {
  form.name = ''
  form.description = ''
  form.stock = 0
  form.price = 0
  form.category_id = null
  form.image_urls = []
  editingId.value = null
}

function normalizeProducts(data) {
  return (data || []).map((item) => {
    const imageUrls = Array.isArray(item.image_urls) ? item.image_urls.filter(Boolean) : []
    return {
      ...item,
      image_urls: imageUrls,
      cover: resolveImageUrl(imageUrls[0]),
    }
  })
}

function resolveImage(event) {
  event.target.src = FALLBACK_IMAGE
}

async function handleImageUpload(uploadFile) {
  if (form.image_urls.length >= 5) {
    ElMessage.warning('最多上传 5 张商品图')
    return
  }
  const file = uploadFile.raw
  const ext = file.name.split('.').pop().toLowerCase()
  const allowed = ['jpg', 'jpeg', 'png', 'gif', 'webp']
  if (!allowed.includes(ext)) {
    ElMessage.warning('仅支持 jpg/png/gif/webp 格式')
    return
  }
  if (file.size > 5 * 1024 * 1024) {
    ElMessage.warning('图片大小不能超过 5MB')
    return
  }
  imageUploading.value = true
  try {
    const res = await uploadProductImage(file)
    form.image_urls.push(res.data.url)
    ElMessage.success('图片上传成功')
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '上传失败')
  } finally {
    imageUploading.value = false
  }
}

function removeImage(index) {
  form.image_urls.splice(index, 1)
}

async function loadProducts() {
  loading.value = true
  try {
    const res = await getMyProducts()
    products.value = normalizeProducts(res.data)
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '加载商品失败')
  } finally {
    loading.value = false
  }
}

async function loadCategories() {
  categoriesLoading.value = true
  try {
    const res = await getCategories()
    categories.value = res.data || []
  } catch (error) {
    categories.value = []
    ElMessage.error(error?.response?.data?.detail || '加载分类失败')
  } finally {
    categoriesLoading.value = false
  }
}

function openCreate() {
  resetForm()
  dialogVisible.value = true
}

function openEdit(row) {
  editingId.value = row.id
  form.name = row.name
  form.description = row.description
  form.stock = row.stock
  form.price = Number(row.price)
  form.category_id = row.category_id || null
  form.image_urls = row.image_urls?.length ? [...row.image_urls] : []
  dialogVisible.value = true
}

async function submitForm() {
  if (!form.name.trim()) {
    ElMessage.warning('商品名称不能为空')
    return
  }
  if (Number(form.price) <= 0) {
    ElMessage.warning('价格必须大于 0')
    return
  }
  if (!form.category_id) {
    ElMessage.warning('请选择商品分类')
    return
  }

  const imageUrls = form.image_urls.filter(Boolean)
  if (imageUrls.length > 5) {
    ElMessage.warning('最多支持 5 张商品图')
    return
  }

  submitLoading.value = true
  try {
    const payload = {
      name: form.name.trim(),
      description: form.description,
      stock: Number(form.stock),
      price: Number(form.price),
      category_id: Number(form.category_id),
      image_urls: imageUrls,
    }
    if (editingId.value) {
      await updateMyProduct(editingId.value, payload)
      ElMessage.success('商品更新成功，已重新待审核')
    } else {
      await createMyProduct(payload)
      ElMessage.success('商品创建成功，待审核')
    }
    dialogVisible.value = false
    await loadProducts()
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '提交失败')
  } finally {
    submitLoading.value = false
  }
}

async function handleDelete(row) {
  try {
    await deleteMyProduct(row.id)
    ElMessage.success('删除成功')
    await loadProducts()
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '删除失败')
  }
}

onMounted(async () => {
  await Promise.all([loadProducts(), loadCategories()])
})
</script>

<template>
  <div class="seller-products-page">
    <section class="head page-block">
      <div>
        <h1 class="page-title">商品管理</h1>
        <p class="page-subtitle">支持商品图片上传、库存、价格与审核状态全量管理。</p>
      </div>
      <div class="head-actions">
        <el-button type="primary" @click="openCreate">新增商品</el-button>
        <el-button @click="loadProducts">刷新</el-button>
      </div>
    </section>

    <section class="page-block table-wrap">
      <el-table v-loading="loading" :data="products" stripe>
        <el-table-column label="主图" width="102">
          <template #default="scope">
            <img :src="scope.row.cover" class="cover-thumb" alt="商品图" @error="resolveImage" />
          </template>
        </el-table-column>
        <el-table-column prop="id" label="ID" width="90" />
        <el-table-column prop="name" label="商品名称" min-width="180" />
        <el-table-column prop="category_name" label="分类" width="130" />
        <el-table-column prop="stock" label="库存" width="95" />
        <el-table-column prop="price" label="价格" width="120">
          <template #default="scope">¥{{ Number(scope.row.price).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column label="审核状态" width="120">
          <template #default="scope">
            <el-tag :type="statusType(scope.row.approval_status)">
              {{ statusLabel(scope.row.approval_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="review_note" label="审核备注" min-width="180" />
        <el-table-column label="操作" width="190" fixed="right">
          <template #default="scope">
            <el-button size="small" @click="openEdit(scope.row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(scope.row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑商品' : '新增商品'" width="680px" @closed="resetForm">
      <el-form label-position="top">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="商品名称">
              <el-input v-model="form.name" maxlength="120" show-word-limit />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="价格">
              <el-input-number v-model="form.price" :min="0" :precision="2" :step="0.1" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="商品描述">
          <el-input v-model="form.description" type="textarea" :rows="3" maxlength="1000" show-word-limit />
        </el-form-item>

        <el-form-item label="库存">
          <el-input-number v-model="form.stock" :min="0" style="width: 180px" />
        </el-form-item>

        <el-form-item label="商品分类" required>
          <el-select
            v-model="form.category_id"
            placeholder="请选择分类"
            style="width: 260px"
            :loading="categoriesLoading"
          >
            <el-option v-for="item in categories" :key="item.id" :label="item.name" :value="item.id" />
          </el-select>
        </el-form-item>

        <el-form-item label="商品图片（最多 5 张）">
          <div class="image-upload-area">
            <div class="image-preview-list">
              <div v-for="(url, index) in form.image_urls" :key="index" class="image-preview-item">
                <img :src="resolveImageUrl(url)" class="preview-img" @error="resolveImage" />
                <el-button class="remove-btn" type="danger" circle size="small" @click="removeImage(index)">X</el-button>
              </div>
            </div>
            <el-upload
              v-if="form.image_urls.length < 5"
              drag
              :auto-upload="false"
              :show-file-list="false"
              accept=".jpg,.jpeg,.png,.gif,.webp"
              :on-change="handleImageUpload"
              :disabled="imageUploading"
              class="image-uploader"
            >
              <div v-loading="imageUploading" class="upload-placeholder">
                <div>点击或拖拽上传</div>
                <div class="upload-hint">jpg / png / gif / webp，最大 5MB</div>
              </div>
            </el-upload>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="submitForm">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.seller-products-page {
  display: grid;
  gap: 16px;
}

.head {
  padding: 18px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.head-actions {
  display: flex;
  gap: 8px;
}

.table-wrap {
  padding: 12px;
}

.cover-thumb {
  width: 72px;
  height: 72px;
  border-radius: 8px;
  object-fit: cover;
  border: 1px solid var(--jd-border);
}

.image-upload-area {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: flex-start;
}

.image-preview-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.image-preview-item {
  position: relative;
  width: 100px;
  height: 100px;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--jd-border);
}

.preview-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.remove-btn {
  position: absolute;
  top: 4px;
  right: 4px;
  opacity: 0.85;
}

.image-uploader {
  width: 100px;
  height: 100px;
}

.image-uploader :deep(.el-upload) {
  width: 100px;
  height: 100px;
}

.image-uploader :deep(.el-upload-dragger) {
  width: 100px;
  height: 100px;
  padding: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.upload-placeholder {
  text-align: center;
  font-size: 12px;
  color: #888;
}

.upload-hint {
  margin-top: 4px;
  font-size: 11px;
  color: #bbb;
}

@media (max-width: 768px) {
  .head {
    flex-direction: column;
    align-items: flex-start;
  }

  .image-upload-area {
    flex-direction: column;
  }
}
</style>
