import request from '@/utils/request'

export function getProducts(params = {}) {
  return request.get('/products', { params })
}

export function getProductById(productId) {
  return request.get(`/products/${productId}`)
}

export function searchProducts(keyword) {
  return request.get('/products/search', {
    params: { keyword },
  })
}

export function createProduct(payload) {
  return request.post('/products', payload)
}

export function updateProduct(productId, payload) {
  return request.put(`/products/${productId}`, payload)
}

export function deleteProduct(productId) {
  return request.delete(`/products/${productId}`)
}
