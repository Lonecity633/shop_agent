import request from '@/utils/request'

export function createMySupportSession(payload = {}) {
  return request.post('/support/me/sessions', payload)
}

export function getMyLatestSupportSession() {
  return request.get('/support/me/sessions/latest')
}

export function getSupportMessages(sessionId) {
  return request.get(`/support/sessions/${sessionId}/messages`)
}

export function autoReply(sessionId, payload) {
  return request.post(`/support/sessions/${sessionId}/reply`, payload, { timeout: 45000 })
}

export function createSupportTicket(payload) {
  return request.post('/support/tickets', payload)
}

export function getMySupportTickets() {
  return request.get('/support/me/tickets')
}

export function getSupportTicket(ticketId) {
  return request.get(`/support/tickets/${ticketId}`)
}
