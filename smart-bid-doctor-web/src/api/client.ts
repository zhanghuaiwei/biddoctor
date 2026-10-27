/**
 * 请求层唯一入口：统一鉴权注入、超时、统一错误体解析（{"error":{code,message}}）、
 * 401 回跳（携带 redirect）。资源函数一律经此发起请求，禁止组件内裸 fetch。
 */
import { useAuthStore } from '@/stores/auth'

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

/** 会话过期统一处理：清登录态（auth store，含 localStorage 持久层）→ 回登录页带 redirect → 返回 ApiError（调用方自行 throw / reject） */
function performUnauthorizedRedirect(): ApiError {
  // 运行期调用（请求发出即 pinia 已激活），非模块顶层，useAuthStore() 安全
  useAuthStore().logout()
  location.assign('/login?redirect=' + encodeURIComponent(location.pathname + location.search))
  return new ApiError(401, 'UNAUTHORIZED', '登录已过期，请重新登录')
}

/** Bearer 鉴权头（登录后才有；token 归口 auth store） */
function authHeaders(): Record<string, string> {
  const token = useAuthStore().token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function api<T>(path: string, opts: ApiOptions = {}): Promise<T> {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, ...init } = opts
  const headers: Record<string, string> = { ...authHeaders() }
  if (!(init.body instanceof FormData)) headers['Content-Type'] = 'application/json'

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

  if (res.status === 401 && location.pathname !== '/login') throw performUnauthorizedRedirect()
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

/**
 * 带上传进度的请求（大文件上传）：fetch 的上传进度（duplex 请求流）仅 Chromium 支持，
 * 跨浏览器唯一通用方案是 XHR 的 upload.onprogress，故此函数走 XHR，仍归口本文件统一处理
 * 鉴权注入、超时、统一错误体与 401 回跳。FormData 由浏览器自动生成 multipart 边界，禁手动设 Content-Type。
 */
export function uploadWithProgress<T>(
  path: string,
  body: FormData,
  opts: { timeoutMs?: number; onProgress?: (percent: number) => void } = {},
): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', '/api' + path)
    xhr.timeout = opts.timeoutMs ?? DEFAULT_TIMEOUT_MS
    for (const [k, v] of Object.entries(authHeaders())) xhr.setRequestHeader(k, v)

    // 上传进度：lengthComputable 恒真（有 Content-Length），取整为百分比
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) opts.onProgress?.(Math.round((e.loaded / e.total) * 100))
    }

    xhr.onload = () => {
      if (xhr.status === 401 && location.pathname !== '/login') {
        return reject(performUnauthorizedRedirect())
      }
      let data: { error?: { code?: string; message?: string } } | null = null
      try {
        data = JSON.parse(xhr.responseText)
      } catch {
        /* 非 JSON 响应体（如网关错误页），走兜底文案 */
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(data as T)
      } else {
        reject(
          new ApiError(
            xhr.status,
            data?.error?.code ?? 'HTTP_ERROR',
            data?.error?.message ?? (xhr.statusText || '请求失败'),
          ),
        )
      }
    }
    xhr.onerror = () => reject(new ApiError(0, 'NETWORK_ERROR', '网络异常，请稍后重试'))
    xhr.ontimeout = () => reject(new ApiError(0, 'NETWORK_ERROR', '网络异常或请求超时，请稍后重试'))
    xhr.send(body)
  })
}

/**
 * 带下载进度的请求（fetch 流式读取）：报告导出等大文件下载接入时使用。
 * - Content-Length 齐全且未压缩 → 百分比回调；
 * - gzip 响应的 Content-Length 是压缩字节数，与解压后累计不一致 → 降级为仅报已下载字节（percent=null）；
 * - chunked 无 Content-Length → 同上。
 * 返回完整 Blob，由调用方决定保存方式（URL.createObjectURL / 直接渲染）。
 */
export async function downloadWithProgress(
  path: string,
  opts: { onProgress?: (percent: number | null, loadedBytes: number) => void } = {},
): Promise<Blob> {
  let res: Response
  try {
    res = await fetch('/api' + path, { headers: authHeaders() })
  } catch {
    throw new ApiError(0, 'NETWORK_ERROR', '网络异常或请求超时，请稍后重试')
  }
  if (res.status === 401 && location.pathname !== '/login') throw performUnauthorizedRedirect()
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
  if (!res.body) throw new ApiError(0, 'NETWORK_ERROR', '当前浏览器不支持流式下载')

  const total = Number(res.headers.get('Content-Length')) || 0
  const percentable = total > 0 && !res.headers.get('Content-Encoding')
  const reader = res.body.getReader()
  // Blob 要求 ArrayBuffer backed 视图；read() 返回 ArrayBufferLike 泛型，此处断言收敛（零拷贝，不复制数据）
  const chunks: Uint8Array<ArrayBuffer>[] = []
  let loaded = 0
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    chunks.push(value as Uint8Array<ArrayBuffer>)
    loaded += value.length
    opts.onProgress?.(percentable ? Math.min(100, Math.round((loaded / total) * 100)) : null, loaded)
  }
  return new Blob(chunks)
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
