import request from '@/utils/request'

export function getFavorites() {
  return request.get('/favorites')
}

export function addFavorite(productId) {
  return request.post('/favorites', { product_id: productId })
}

export function removeFavorite(productId) {
  return request.delete(`/favorites/${productId}`)
}
