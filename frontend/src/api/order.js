import request from '@/utils/request'

export function getOrders() {
  return request.get('/orders')
}

export function getOrderById(orderId) {
  return request.get(`/orders/${orderId}`)
}

export function createOrder(payload) {
  return request.post('/orders', payload)
}

export function payOrder(orderId, payChannel = 'simulated') {
  return request.post(`/orders/${orderId}/pay`, { pay_channel: payChannel })
}

export function closeOrder(orderId, reason = '订单超时未支付') {
  return request.post(`/orders/${orderId}/close`, { reason })
}

export function deleteOrder(orderId) {
  return request.delete(`/orders/${orderId}`)
}

export function getOrderStatus(orderId) {
  return request.get(`/orders/${orderId}/status`)
}

export function updateOrderStatus(orderId, status) {
  return request.patch(`/orders/${orderId}/status`, { status })
}

export function shipOrder(orderId, payload) {
  return request.post(`/orders/${orderId}/ship`, payload)
}

export function receiveOrder(orderId, reason = '买家确认收货') {
  return request.post(`/orders/${orderId}/receive`, { reason })
}

export function getOrderLogs(orderId) {
  return request.get(`/orders/${orderId}/logs`)
}

export function createOrderComment(orderId, payload) {
  return request.post(`/orders/${orderId}/comments`, payload)
}
