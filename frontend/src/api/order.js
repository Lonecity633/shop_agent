import request from '@/utils/request'

function encodeOrderNo(orderNo) {
  return encodeURIComponent(String(orderNo || '').trim())
}

export function getOrders() {
  return request.get('/orders')
}

export function getOrderByNo(orderNo) {
  return request.get(`/orders/${encodeOrderNo(orderNo)}`)
}

export function createOrder(payload) {
  return request.post('/orders', payload)
}

export function payOrder(orderNo, payChannel = 'simulated') {
  return request.post(`/orders/${encodeOrderNo(orderNo)}/pay`, { pay_channel: payChannel })
}

export function closeOrder(orderNo, reason = '订单超时未支付') {
  return request.post(`/orders/${encodeOrderNo(orderNo)}/close`, { reason })
}

export function deleteOrder(orderNo) {
  return request.delete(`/orders/${encodeOrderNo(orderNo)}`)
}

export function getOrderStatus(orderNo) {
  return request.get(`/orders/${encodeOrderNo(orderNo)}/status`)
}

export function updateOrderStatus(orderNo, status) {
  return request.patch(`/orders/${encodeOrderNo(orderNo)}/status`, { status })
}

export function shipOrder(orderNo, payload) {
  return request.post(`/orders/${encodeOrderNo(orderNo)}/ship`, payload)
}

export function receiveOrder(orderNo, reason = '买家确认收货') {
  return request.post(`/orders/${encodeOrderNo(orderNo)}/receive`, { reason })
}

export function getOrderLogs(orderNo) {
  return request.get(`/orders/${encodeOrderNo(orderNo)}/logs`)
}

export function createOrderComment(orderNo, payload) {
  return request.post(`/orders/${encodeOrderNo(orderNo)}/comments`, payload)
}
