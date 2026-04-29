import request from '@/utils/request'

export function getAddresses() {
  return request.get('/addresses')
}

export function createAddress(payload) {
  return request.post('/addresses', payload)
}

export function updateAddress(addressId, payload) {
  return request.put(`/addresses/${addressId}`, payload)
}

export function deleteAddress(addressId) {
  return request.delete(`/addresses/${addressId}`)
}
