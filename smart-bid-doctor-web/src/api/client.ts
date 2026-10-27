/**
 * 请求层唯一入口：统一鉴权注入、超时、统一错误体解析（{"error":{code,message}}）、
 * 401 回跳（携带 redirect）。资源函数一律经此发起请求，禁止组件内裸 fetch。
 */
import { STORAGE_KEYS } from '@/constants/storage'

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

interface ApiOptions extends RequestInit {
  /** 请求超时毫秒数；上传大文件时放宽（见 api/projects.ts） */
  timeoutMs?: number
}

const DEFAULT_TIMEOUT_MS = 30_000

export async function api<T>(path: string, opts: ApiOptions = {}): Promise<T> {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, ...init } = opts
  const headers: Record<string, string> = {}
  if (!(init.body instanceof FormData)) headers['Content-Type'] = 'application/json'
  const token = localStorage.getItem(STORAGE_KEYS.token)
  if (token) headers['Authorization'] = `Bearer ${token}`

  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), timeoutMs)
  let res: Response
  try {
    res = await fetch('/api' + path, { ...init, headers, signal: ctrl.signal })
  } catch {
    throw new ApiError(0, 'NETWORK_ERROR', '网络异常或请求超时，请稍后重试')
  } finally {
    clearTimeout(timer)
  }

  if (res.status === 401 && location.pathname !== '/login') {
    // 会话过期：回登录页并保留回跳目标
    localStorage.removeItem(STORAGE_KEYS.token)
    location.assign('/login?redirect=' + encodeURIComponent(location.pathname + location.search))
    throw new ApiError(401, 'UNAUTHORIZED', '登录已过期，请重新登录')
  }
  if (!res.ok) {
    let code = 'HTTP_ERROR'
    let msg = res.statusText || '请求失败'
    try {
      const j = await res.json()
      code = j?.error?.code ?? code
      msg = j?.error?.message ?? msg
    } catch {
      /* 非 JSON 响应体，保留 statusText */
    }
    throw new ApiError(res.status, code, msg)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

/** 组件层统一的错误提示：优先透出后端中文 message（统一错误体），兜底文案可自定义 */
export function notifyApiError(e: unknown, fallback = '操作失败，请稍后重试'): void {
  ElMessage.error(e instanceof Error && e.message ? e.message : fallback)
}

/** 拼接查询串（跳过空值） */
export function withQuery(path: string, params: Record<string, string | number | undefined>): string {
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== '') q.set(k, String(v))
  }
  const qs = q.toString()
  return qs ? `${path}?${qs}` : path
}
