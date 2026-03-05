const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export type ReqOptions = {
  method?: string
  body?: unknown
  token?: string | null
  isForm?: boolean
}

function formatApiErrorPayload(payload: any): string {
  if (!payload) return 'Request failed'
  if (typeof payload.detail === 'string') return payload.detail
  if (Array.isArray(payload.detail)) {
    const messages = payload.detail.map((item: any) => {
      const loc = Array.isArray(item.loc) ? item.loc.join('.') : ''
      return loc ? `${loc}: ${item.msg || 'Invalid value'}` : (item.msg || 'Invalid value')
    })
    return messages.join(' | ')
  }
  return payload.message || 'Request failed'
}

export async function api(path: string, options: ReqOptions = {}) {
  const headers: Record<string, string> = {}
  if (!options.isForm) headers['Content-Type'] = 'application/json'
  if (options.token) headers['Authorization'] = `Bearer ${options.token}`

  const res = await fetch(`${API_URL}${path}`, {
    method: options.method || 'GET',
    headers,
    body: options.body
      ? options.isForm
        ? (options.body as FormData)
        : JSON.stringify(options.body)
      : undefined,
  })

  if (!res.ok) {
    if (res.status === 401) {
      window.dispatchEvent(new CustomEvent('auth:unauthorized'))
    }
    const contentType = res.headers.get('content-type') || ''
    if (contentType.includes('application/json')) {
      const payload = await res.json()
      throw new Error(formatApiErrorPayload(payload))
    }
    const text = await res.text()
    throw new Error(text || 'Request failed')
  }
  return res.json()
}
