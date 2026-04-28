export function normalizeAvatarUrl(value) {
  const raw = (value || '').trim()
  if (!raw) return ''
  if (raw.startsWith('http://') || raw.startsWith('https://') || raw.startsWith('data:image/') || raw.startsWith('blob:')) {
    return raw
  }
  if (raw.startsWith('//')) return `https:${raw}`
  if (/^[\w.-]+\.[a-z]{2,}(\/.*)?$/i.test(raw)) return `https://${raw}`
  return raw
}
