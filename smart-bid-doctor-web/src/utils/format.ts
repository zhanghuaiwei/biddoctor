/** 展示格式化工具（本地时区） */

/** ISO → "YYYY-MM-DD HH:mm" */
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '-'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** ISO → "YYYY-MM-DD"（到期日等仅日期场景） */
export function formatDate(iso: string | null | undefined): string {
  return iso ? formatDateTime(iso).slice(0, 10) : '-'
}

/** 字节数 → 可读大小 */
export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}
