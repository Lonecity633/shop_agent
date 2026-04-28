import request from '@/utils/request'

export function getCategories() {
  return request.get('/categories')
}
