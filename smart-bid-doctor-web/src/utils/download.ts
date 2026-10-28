/** Blob 落盘下载：CSV 导出 / 附件下载等已持有 Blob 的场景共用（a[download] 临时链接） */
export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}
