import request from '@/utils/request'

function encodeOrderNo(orderNo) {
  return encodeURIComponent(String(orderNo || '').trim())
}

function encodePaymentNo(paymentNo) {
  return encodeURIComponent(String(paymentNo || '').trim())
}

export function initiatePayment(orderNo, channel = 'mock_alipay') {
  return request.post(`/payments/orders/${encodeOrderNo(orderNo)}/initiate`, { channel })
}

export function mockPaymentCallback(paymentNo, result, failureReason = '') {
  return request.post(`/payments/${encodePaymentNo(paymentNo)}/mock-callback`, {
    result,
    failure_reason: failureReason,
  })
}

export function getOrderPayments(orderNo) {
  return request.get(`/payments/orders/${encodeOrderNo(orderNo)}`)
}
