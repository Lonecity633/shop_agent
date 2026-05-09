import request from '@/utils/request'

export function getSellers() {
  return request.get('/admin/sellers')
}

export function getAdminOverview() {
  return request.get('/admin/overview')
}

export function getPendingProducts() {
  return request.get('/admin/products/pending')
}

export function auditProduct(productId, payload) {
  return request.patch(`/products/${productId}/audit`, payload)
}

export function getPendingSellerProfiles() {
  return request.get('/admin/seller-profiles/pending')
}

export function auditSellerProfile(profileId, payload) {
  return request.patch(`/admin/seller-profiles/${profileId}/audit`, payload)
}

export function getRecentOrders(limit = 20) {
  return request.get('/admin/orders/recent', { params: { limit } })
}

export function getAdminRefunds(params = {}) {
  return request.get('/admin/refunds', { params })
}

export function getAdminOrdersPaged(params = {}) {
  return request.get('/admin/orders', { params })
}

export function getAdminRefundsPaged(params = {}) {
  return request.get('/admin/refunds/paged', { params })
}

export function arbitrateRefund(refundId, payload) {
  return request.patch(`/admin/refunds/${refundId}/arbitrate`, payload)
}

export function executeRefund(refundId, payload) {
  return request.post(`/admin/refunds/${refundId}/execute`, payload)
}

export function getOperationTimeline(entityType, entityId, params = {}) {
  return request.get(`/admin/timelines/${entityType}/${entityId}`, { params })
}

export function getAdminCategories() {
  return request.get('/admin/categories')
}

export function createAdminCategory(payload) {
  return request.post('/admin/categories', payload)
}

export function updateAdminCategory(categoryId, payload) {
  return request.put(`/admin/categories/${categoryId}`, payload)
}

export function updateAdminCategoryStatus(categoryId, payload) {
  return request.patch(`/admin/categories/${categoryId}/status`, payload)
}

export function deleteAdminCategory(categoryId) {
  return request.delete(`/admin/categories/${categoryId}`)
}

export function uploadKbDocument(payload) {
  return request.post('/admin/knowledge/documents', payload)
}

export function listKbDocuments(params = {}) {
  return request.get('/admin/knowledge/documents', { params })
}

export function deleteKbDocument(documentId) {
  return request.delete(`/admin/knowledge/documents/${documentId}`)
}

export function uploadKbDocumentFile(title, file) {
  const formData = new FormData()
  formData.append('title', title)
  formData.append('file', file)
  return request.post('/admin/knowledge/documents/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}
