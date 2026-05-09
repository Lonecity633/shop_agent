<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listKbDocuments, uploadKbDocumentFile, deleteKbDocument } from '@/api/admin'

const router = useRouter()

const documents = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const dialogVisible = ref(false)
const submitting = ref(false)
const form = ref({ title: '' })
const selectedFile = ref(null)

function formatTime(value) {
  if (!value) return '-'
  const dt = new Date(value)
  if (Number.isNaN(dt.getTime())) return value
  return dt.toLocaleString()
}

async function loadDocuments() {
  loading.value = true
  try {
    const res = await listKbDocuments({ page: page.value, page_size: pageSize.value })
    documents.value = res.data?.items || []
    total.value = res.data?.total || 0
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '加载失败')
  } finally {
    loading.value = false
  }
}

function openUploadDialog() {
  form.value = { title: '' }
  selectedFile.value = null
  dialogVisible.value = true
}

function handleFileChange(uploadFile) {
  selectedFile.value = uploadFile.raw
}

function handleFileRemove() {
  selectedFile.value = null
}

async function handleUpload() {
  if (!form.value.title.trim()) {
    ElMessage.warning('请输入文档标题')
    return
  }
  if (!selectedFile.value) {
    ElMessage.warning('请选择要上传的文件')
    return
  }
  submitting.value = true
  try {
    await uploadKbDocumentFile(form.value.title.trim(), selectedFile.value)
    ElMessage.success('上传成功')
    dialogVisible.value = false
    page.value = 1
    await loadDocuments()
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '上传失败')
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定删除文档「${row.title}」？删除后向量数据也将清除。`, '确认删除', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await deleteKbDocument(row.id)
    ElMessage.success('已删除')
    await loadDocuments()
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.detail || '删除失败')
  }
}

function handlePageChange(p) {
  page.value = p
  loadDocuments()
}

onMounted(loadDocuments)
</script>

<template>
  <div class="kb-wrap">
    <el-card>
      <template #header>
        <div class="card-header-row">
          <div class="header-left">
            <el-button text @click="router.push('/admin/dashboard')">← 返回后台</el-button>
            <strong>知识库文档管理</strong>
          </div>
          <el-button type="primary" @click="openUploadDialog">上传文档</el-button>
        </div>
      </template>

      <el-table :data="documents" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
        <el-table-column prop="source" label="来源" width="100" />
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === 'ready' ? 'success' : 'info'" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="chunk_count" label="切片数" width="90" align="center" />
        <el-table-column label="创建时间" width="180">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100" align="center">
          <template #default="{ row }">
            <el-button type="danger" text size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-row" v-if="total > pageSize">
        <el-pagination
          background
          layout="prev, pager, next"
          :total="total"
          :page-size="pageSize"
          :current-page="page"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>

    <el-dialog v-model="dialogVisible" title="上传知识库文档" width="640px" :close-on-click-modal="false">
      <el-form label-position="top">
        <el-form-item label="文档标题">
          <el-input v-model="form.title" placeholder="例：退货退款政策" maxlength="255" show-word-limit />
        </el-form-item>
        <el-form-item label="上传文件">
          <el-upload
            drag
            :auto-upload="false"
            :limit="1"
            accept=".txt,.md,.pdf"
            :on-change="handleFileChange"
            :on-remove="handleFileRemove"
          >
            <div class="upload-inner">
              <div>将文件拖到此处，或<em>点击选择</em></div>
              <div class="upload-tip">支持 .txt / .md / .pdf 文件</div>
            </div>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleUpload">上传并切分</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.kb-wrap {
  width: min(1280px, calc(100vw - 30px));
  margin: 18px auto;
}

.card-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.pagination-row {
  display: flex;
  justify-content: center;
  margin-top: 16px;
}

.upload-inner {
  padding: 20px 0;
}

.upload-tip {
  margin-top: 8px;
  font-size: 12px;
  color: #999;
}
</style>
