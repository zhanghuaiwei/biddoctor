const TOKEN_KEY = 'fj_token'

export const getToken = () => localStorage.getItem(TOKEN_KEY)
export const setToken = (t: string) => localStorage.setItem(TOKEN_KEY, t)
export const clearToken = () => localStorage.removeItem(TOKEN_KEY)

export async function api<T = any>(path: string, opts: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {}
  if (!(opts.body instanceof FormData)) headers['Content-Type'] = 'application/json'
  if (getToken()) headers['Authorization'] = `Bearer ${getToken()}`
  const res = await fetch('/api' + path, { ...opts, headers })
  if (res.status === 401 && location.pathname !== '/login') {
    location.href = '/login'
    throw new Error('未登录')
  }
  if (!res.ok) {
    let msg = res.statusText
    try {
      const j = await res.json()
      msg = j?.error?.message || msg
    } catch {}
    throw new Error(msg)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}
