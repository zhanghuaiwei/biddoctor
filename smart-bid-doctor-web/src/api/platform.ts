/** 用户端平台资源：导航/公告/法务签署/附件（05 §3/§7/§8） */
import { api, uploadWithProgress, withQuery } from './client'
import type {
  AttachmentOut,
  LegalCurrentOut,
  MeMenusOut,
  NoticeItem,
} from '@/types'

/** 管理端导航数据：菜单树 + 权限点集合（非 admin 返回空集） */
export function getMyMenus() {
  return api<MeMenusOut>('/me/menus')
}

/** 公告横幅（公开） */
export function listNotices(limit = 5) {
  return api<Array<NoticeItem & { publish_at: string }>>(withQuery('/notices', { limit }))
}

/** 三类法务文档当前生效版 + 本人已签署版本 */
export function getCurrentLegal() {
  return api<LegalCurrentOut>('/legal/current')
}

/** 批量签署（登录首次勾选/新版本再确认） */
export function signAgreements(legalDocIds: number[]) {
  return api<LegalCurrentOut>('/legal/agreements', {
    method: 'POST',
    body: JSON.stringify(legalDocIds),
  })
}

/** 附件上传（≤20MB 白名单；order_voucher 需 business_id=订单 id） */
export function uploadAttachment(
  module: string,
  file: File,
  businessId?: number,
  onProgress?: (percent: number) => void,
) {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('module', module)
  if (businessId !== undefined) fd.append('business_id', String(businessId))
  return uploadWithProgress<AttachmentOut>('/attachments', fd, { timeoutMs: 60_000, onProgress })
}

export function deleteAttachment(id: number) {
  return api<void>(`/attachments/${id}`, { method: 'DELETE' })
}

/** 附件下载（走 fetch 流式，归口 client 统一鉴权） */
export function downloadAttachment(id: number) {
  return import('./client').then(({ downloadWithProgress }) =>
    downloadWithProgress(`/attachments/${id}/download`),
  )
}
