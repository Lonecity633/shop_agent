import request from '@/utils/request'

export function getSellerProfile() {
  return request.get('/seller/profile')
}

export function saveSellerProfile(payload) {
  return request.put('/seller/profile', payload)
}

export function getMyProducts() {
  return request.get('/seller/products')
}

export function createMyProduct(payload) {
  return request.post('/seller/products', payload)
}

export function updateMyProduct(productId, payload) {
  return request.put(`/seller/products/${productId}`, payload)
}

export function deleteMyProduct(productId) {
  return request.delete(`/seller/products/${productId}`)
}
