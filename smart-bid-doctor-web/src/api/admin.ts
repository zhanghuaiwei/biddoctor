/** 管理端资源（05 §10 /api/admin/*）：全端点走统一请求入口与错误体解析 */
import { api, withQuery } from './client'
import type {
  AdminUserPage,
  AiModelOut,
  AlertPage,
  AttachmentPage,
  AuditLogPage,
  ConfigOut,
  DictDataOut,
  DictTypeOut,
  InviteOut,
  InvitePage,
  JobLogPage,
  JobOut,
  LegalDocOut,
  LoginLogPage,
  MeMenusOut,
  MonitorOverview,
  NoticeItem,
  NoticePage,
  OperLogPage,
  OrderOut,
  PaymentPage,
  PlanOut,
  PromptOut,
  RoleOut,
  RuleItemOut,
  RuleSetOut,
  SignaturePage,
  StatRowOut,
  SubscriptionPage,
  TaskAdminPage,
} from '@/types'

// ── 导航 ──
export const getMenus = () => api<MeMenusOut>('/me/menus')

// ── 监控 / 告警 ──
export const getMonitorOverview = () => api<MonitorOverview>('/admin/monitor/overview')
export const getStorageUsage = () =>
  api<Record<string, unknown>>('/admin/monitor/storage')
export const listAdminTasks = (params: { status?: string; type?: string; limit?: number; offset?: number } = {}) =>
  api<TaskAdminPage>(withQuery('/admin/monitor/tasks', params))
export const listAlerts = (params: { acked?: boolean; level?: string; limit?: number; offset?: number } = {}) =>
  api<AlertPage>(withQuery('/admin/alerts', { ...params }))
export const ackAlert = (id: number) =>
  api<{ ok: boolean }>(`/admin/alerts/${id}/ack`, { method: 'POST' })

// ── 订单 / 支付 ──
export function listAdminOrders(params: { user_id?: number; status?: string; limit?: number; offset?: number } = {}) {
  return api<{ items: OrderOut[]; total: number }>(withQuery('/admin/orders', params))
}
export const grantOrder = (orderNo: string) =>
  api<{ order_no: string; status: string }>(`/admin/orders/${orderNo}/grant`, { method: 'POST' })
export const listPayments = (params: { status?: string; limit?: number; offset?: number } = {}) =>
  api<PaymentPage>(withQuery('/admin/payments', params))

// ── 用户 / 机构 / 角色 / 菜单 / 邀请码 ──
export function listAdminUsers(params: { email?: string; status?: string; org_id?: number; limit?: number; offset?: number } = {}) {
  return api<AdminUserPage>(withQuery('/admin/sys/users', params))
}
export const banUser = (id: number) => api<{ ok: boolean }>(`/admin/sys/users/${id}/ban`, { method: 'POST' })
export const unbanUser = (id: number) => api<{ ok: boolean }>(`/admin/sys/users/${id}/unban`, { method: 'POST' })
export const getUserRoles = (uid: number) =>
  api<{ roles: RoleOut[] }>(`/admin/sys/users/${uid}/roles`)
export const setUserRoles = (uid: number, roleIds: number[]) =>
  api<{ ok: boolean }>(`/admin/sys/users/${uid}/roles`, {
    method: 'PUT',
    body: JSON.stringify({ role_ids: roleIds }),
  })

export const listRoles = () => api<RoleOut[]>('/admin/sys/roles')
export const setRoleMenus = (rid: number, menuIds: number[]) =>
  api<{ ok: boolean }>(`/admin/sys/roles/${rid}/menus`, {
    method: 'PUT',
    body: JSON.stringify({ menu_ids: menuIds }),
  })

export const listMenusFlat = () =>
  api<Array<{ id: number; parent_id: number | null; name: string; type: string; path: string | null; perm: string | null; sort: number; visible: boolean; status: string }>>(
    '/admin/sys/menus',
  )
export const updateMenu = (id: number, body: Record<string, unknown>) =>
  api<{ ok: boolean }>(`/admin/sys/menus/${id}`, { method: 'PATCH', body: JSON.stringify(body) })

export const getOrgTree = () =>
  api<Array<import('@/types').OrgNode>>('/admin/sys/orgs/tree')
export function createOrg(body: { name: string; parent_id?: number | null; code?: string; sort?: number; leader?: string }) {
  return api<import('@/types').OrgNode>('/admin/sys/orgs', { method: 'POST', body: JSON.stringify(body) })
}
export const updateOrg = (id: number, body: Record<string, unknown>) =>
  api<{ ok: boolean }>(`/admin/sys/orgs/${id}`, { method: 'PATCH', body: JSON.stringify(body) })
export const deleteOrg = (id: number) =>
  api<{ ok: boolean }>(`/admin/sys/orgs/${id}`, { method: 'DELETE' })

export const issueInvite = (body: { max_uses: number; ttl_days: number }) =>
  api<InviteOut>('/admin/sys/invites', { method: 'POST', body: JSON.stringify(body) })
export function listInvites(params: { limit?: number; offset?: number } = {}) {
  return api<InvitePage>(withQuery('/admin/sys/invites', params))
}

// ── 参数 / 字典 / 公告 / 定时任务 ──
export const listConfigs = () => api<ConfigOut[]>('/admin/sys/configs')
export const updateConfig = (key: string, value: string) =>
  api<ConfigOut>(`/admin/sys/configs/${encodeURIComponent(key)}`, {
    method: 'PUT',
    body: JSON.stringify({ value }),
  })

export const listDictTypes = () => api<DictTypeOut[]>('/admin/sys/dicts')
export const createDictType = (body: { dict_type: string; name: string; remark?: string }) =>
  api<DictTypeOut>('/admin/sys/dicts', { method: 'POST', body: JSON.stringify(body) })
export const listDictData = (dictType: string) => api<DictDataOut[]>(`/admin/sys/dicts/${dictType}/data`)
export const createDictData = (dictType: string, body: { value: string; label: string; sort?: number }) =>
  api<DictDataOut>(`/admin/sys/dicts/${dictType}/data`, { method: 'POST', body: JSON.stringify(body) })
export const updateDictData = (id: number, body: Record<string, unknown>) =>
  api<DictDataOut>(`/admin/sys/dicts/data/${id}`, { method: 'PATCH', body: JSON.stringify(body) })
export const deleteDictData = (id: number) =>
  api<{ ok: boolean }>(`/admin/sys/dicts/data/${id}`, { method: 'DELETE' })

export function listAdminNotices(params: { status?: string; limit?: number; offset?: number } = {}) {
  return api<NoticePage>(withQuery('/admin/sys/notices', params))
}
export const createNotice = (body: { title: string; content: string; type: string; level: string }) =>
  api<NoticeItem>('/admin/sys/notices', { method: 'POST', body: JSON.stringify(body) })
export const publishNotice = (id: number) => api<NoticeItem>(`/admin/sys/notices/${id}/publish`, { method: 'POST' })
export const offlineNotice = (id: number) => api<NoticeItem>(`/admin/sys/notices/${id}/offline`, { method: 'POST' })
export const deleteNotice = (id: number) => api<{ ok: boolean }>(`/admin/sys/notices/${id}`, { method: 'DELETE' })

export const listJobs = () => api<JobOut[]>('/admin/sys/jobs')
export const enableJob = (id: number) => api<JobOut>(`/admin/sys/jobs/${id}/enable`, { method: 'POST' })
export const disableJob = (id: number) => api<JobOut>(`/admin/sys/jobs/${id}/disable`, { method: 'POST' })
export const runJob = (id: number) => api<JobOut>(`/admin/sys/jobs/${id}/run`, { method: 'POST' })
export function listJobLogs(jobKey: string, params: { limit?: number; offset?: number } = {}) {
  return api<JobLogPage>(withQuery(`/admin/sys/jobs/${jobKey}/logs`, params))
}

// ── 日志（CSV 导出走 fetch 下载）──
export function listAuditLogs(params: { action?: string; user_id?: number; limit?: number; offset?: number } = {}) {
  return api<AuditLogPage>(withQuery('/admin/logs/audit', params))
}
export const listAuditActions = () => api<string[]>('/admin/logs/audit/actions')
export function listLoginLogs(params: { email?: string; result?: string; limit?: number; offset?: number } = {}) {
  return api<LoginLogPage>(withQuery('/admin/logs/login', params))
}
export function listOperLogs(params: { module?: string; limit?: number; offset?: number } = {}) {
  return api<OperLogPage>(withQuery('/admin/logs/oper', params))
}
export const exportLogsCsv = (kind: 'audit' | 'login' | 'oper') =>
  import('./client').then(({ downloadWithProgress }) =>
    downloadWithProgress(`/admin/logs/${kind}/export`),
  )

// ── 统计 ──
export function listStats(params: { dim?: string; metric?: string; from?: string; to?: string } = {}) {
  return api<StatRowOut[]>(withQuery('/admin/stats/daily', params))
}
export const exportStatsCsv = (params: { dim?: string; metric?: string; from?: string; to?: string }) =>
  import('./client').then(({ downloadWithProgress }) =>
    downloadWithProgress(withQuery('/admin/stats/daily/export', params)),
  )
export const manualRollup = (day?: string) =>
  api<Record<string, unknown>>('/admin/stats/rollup', { method: 'POST', body: JSON.stringify(day ? { day } : {}) })

// ── 附件 ──
export function listAdminAttachments(params: { module?: string; business_id?: number; limit?: number; offset?: number } = {}) {
  return api<AttachmentPage>(withQuery('/admin/attachments', params))
}
export const deleteAdminAttachment = (id: number) =>
  api<{ ok: boolean }>(`/admin/attachments/${id}`, { method: 'DELETE' })
export const downloadAdminAttachment = (id: number) =>
  import('./client').then(({ downloadWithProgress }) =>
    downloadWithProgress(`/admin/attachments/${id}/download`),
  )

// ── 法务 ──
export const listLegalDocs = () => api<LegalDocOut[]>('/admin/legal/documents')
export function createLegalDoc(body: { doc_type: string; version: string; title: string; content: string; effective_at: string }) {
  return api<LegalDocOut>('/admin/legal/documents', { method: 'POST', body: JSON.stringify(body) })
}
export const publishLegalDoc = (id: number) => api<LegalDocOut>(`/admin/legal/documents/${id}/publish`, { method: 'POST' })
export const retireLegalDoc = (id: number) => api<LegalDocOut>(`/admin/legal/documents/${id}/retire`, { method: 'POST' })
export function listSignatures(params: { limit?: number; offset?: number } = {}) {
  return api<SignaturePage>(withQuery('/admin/legal/signatures', params))
}

// ── AI 治理 ──
export const listAiModels = () => api<AiModelOut[]>('/admin/ai/models')
export function createAiModel(body: Record<string, unknown>) {
  return api<AiModelOut>('/admin/ai/models', { method: 'POST', body: JSON.stringify(body) })
}
export const updateAiModel = (id: number, body: Record<string, unknown>) =>
  api<AiModelOut>(`/admin/ai/models/${id}`, { method: 'PATCH', body: JSON.stringify(body) })
export function listPrompts(params: { purpose?: string } = {}) {
  return api<PromptOut[]>(withQuery('/admin/ai/prompts', params))
}
export function createPrompt(body: { name: string; purpose: string; version: number; template: string }) {
  return api<PromptOut>('/admin/ai/prompts', { method: 'POST', body: JSON.stringify(body) })
}
export const activatePrompt = (id: number) =>
  api<PromptOut>(`/admin/ai/prompts/${id}/activate`, { method: 'POST' })

// ── 订阅 ──
export const listPlans = () => api<PlanOut[]>('/admin/subs/plans')
export function createPlan(body: { code: string; name: string; price_cny: string; period_months: number; compare_quota: number }) {
  return api<PlanOut>('/admin/subs/plans', { method: 'POST', body: JSON.stringify(body) })
}
export const updatePlan = (id: number, body: Record<string, unknown>) =>
  api<PlanOut>(`/admin/subs/plans/${id}`, { method: 'PATCH', body: JSON.stringify(body) })
export function listSubscriptions(params: { status?: string; limit?: number; offset?: number } = {}) {
  return api<SubscriptionPage>(withQuery('/admin/subs', params))
}

// ── 规则库 ──
export function listRuleSets(params: { industry?: string } = {}) {
  return api<RuleSetOut[]>(withQuery('/admin/rules/sets', params))
}
export const createRuleSet = (body: { industry: string; law_version: string; notes?: string }) =>
  api<RuleSetOut>('/admin/rules/sets', { method: 'POST', body: JSON.stringify(body) })
export const activateRuleSet = (id: number) =>
  api<RuleSetOut>(`/admin/rules/sets/${id}/activate`, { method: 'POST' })
export const retireRuleSet = (id: number) =>
  api<RuleSetOut>(`/admin/rules/sets/${id}/retire`, { method: 'POST' })
export const listRuleItems = (setId: number) => api<RuleItemOut[]>(`/admin/rules/sets/${setId}/items`)
export function addRuleItem(setId: number, body: Record<string, unknown>) {
  return api<RuleItemOut>(`/admin/rules/sets/${setId}/items`, { method: 'POST', body: JSON.stringify(body) })
}
export const deleteRuleItem = (id: number) =>
  api<{ ok: boolean }>(`/admin/rules/items/${id}`, { method: 'DELETE' })
