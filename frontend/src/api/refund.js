import request from '@/utils/request'

export function getRefunds() {
  return request.get('/refunds')
}

export function getRefundById(refundId) {
  return request.get(`/refunds/${refundId}`)
}

export function createRefund(payload) {
  return request.post('/refunds', payload)
}

export function sellerReviewRefund(refundId, payload) {
  return request.patch(`/refunds/${refundId}/seller-review`, payload)
}
