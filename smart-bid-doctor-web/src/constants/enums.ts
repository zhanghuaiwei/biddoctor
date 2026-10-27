/**
 * 业务枚举注册表——与后端 `app/core/enums.py`（03 数据库设计 §3 取值域）一一对应。
 * 状态/类别一律引用此处常量与映射，禁止在组件里散落字面量。
 */

// ---- 标签类型（Element Plus el-tag）----
export type TagType = 'success' | 'danger' | 'warning' | 'info' | 'primary'

// ---- 项目 ----
export const PROJECT_STATUSES = [
  'draft',
  'tender_parsing',
  'checklist_ready',
  'comparing',
  'report_ready',
  'archived',
] as const
export type ProjectStatus = (typeof PROJECT_STATUSES)[number]

export const PROJECT_STATUS_LABELS: Record<ProjectStatus, string> = {
  draft: '草稿',
  tender_parsing: '解析中',
  checklist_ready: '清单就绪',
  comparing: '对照中',
  report_ready: '报告就绪',
  archived: '已归档',
}

export const PROJECT_STATUS_TAGS: Record<ProjectStatus, TagType> = {
  draft: 'info',
  tender_parsing: 'warning',
  checklist_ready: 'success',
  comparing: 'warning',
  report_ready: 'success',
  archived: 'info',
}

export const INDUSTRIES = ['general', 'medical'] as const
export type Industry = (typeof INDUSTRIES)[number]

export const INDUSTRY_LABELS: Record<Industry, string> = {
  general: '通用',
  medical: '医疗器械（P2）',
}

export const INDUSTRY_TAGS: Record<Industry, TagType> = {
  general: 'info',
  medical: 'danger',
}

// ---- 文档 ----
export const DOCUMENT_ROLES = ['tender', 'bid'] as const
export type DocumentRole = (typeof DOCUMENT_ROLES)[number]

export const DOCUMENT_ROLE_LABELS: Record<DocumentRole, string> = {
  tender: '招标文件',
  bid: '投标文件',
}

export const DOCUMENT_ROLE_TAGS: Record<DocumentRole, TagType> = {
  tender: 'primary',
  bid: 'info',
}

export const PARSE_STATUSES = ['pending', 'running', 'done', 'failed', 'need_review'] as const
export type ParseStatus = (typeof PARSE_STATUSES)[number]

export const PARSE_STATUS_LABELS: Record<ParseStatus, string> = {
  pending: '待解析',
  running: '解析中',
  done: '已完成',
  failed: '失败',
  need_review: '需人工复核',
}

export const PARSE_STATUS_TAGS: Record<ParseStatus, TagType> = {
  pending: 'info',
  running: 'warning',
  done: 'success',
  failed: 'danger',
  need_review: 'warning',
}

/** 解析在途（轮询继续的判定条件） */
export const PARSE_BUSY_STATUSES: readonly ParseStatus[] = ['pending', 'running']

// ---- 任务 ----
export const TASK_TYPES = ['parse', 'extract', 'embed', 'checklist', 'compare', 'purge'] as const
export type TaskType = (typeof TASK_TYPES)[number]

export const TASK_STATUSES = [
  'pending',
  'running',
  'succeeded',
  'failed',
  'need_review',
  'cancelled',
] as const
export type TaskStatus = (typeof TASK_STATUSES)[number]

export const TASK_STATUS_LABELS: Record<TaskStatus, string> = {
  pending: '排队中',
  running: '执行中',
  succeeded: '已完成',
  failed: '失败',
  need_review: '需人工复核',
  cancelled: '已取消',
}

export const TASK_STATUS_TAGS: Record<TaskStatus, TagType> = {
  pending: 'info',
  running: 'warning',
  succeeded: 'success',
  failed: 'danger',
  need_review: 'warning',
  cancelled: 'info',
}

// ---- 清单条款（02 §3.1 五类）----
export const CHECK_CATEGORIES = ['qualification', 'compliance', 'star', 'price', 'format_seal'] as const
export type CheckCategory = (typeof CHECK_CATEGORIES)[number]

export const CHECK_CATEGORY_LABELS: Record<CheckCategory, string> = {
  qualification: '资格性要求',
  compliance: '符合性要求',
  star: '★号强制条款',
  price: '报价相关',
  format_seal: '签章密封格式',
}

// ---- 对照 ----
export const COMPARISON_STATUSES = ['pending', 'running', 'done', 'failed', 'need_review'] as const
export type ComparisonStatus = (typeof COMPARISON_STATUSES)[number]

export const COMPARISON_STATUS_LABELS: Record<ComparisonStatus, string> = {
  pending: '排队中',
  running: '对照中',
  done: '已完成',
  failed: '失败',
  need_review: '需人工复核',
}

export const COMPARISON_STATUS_TAGS: Record<ComparisonStatus, TagType> = {
  pending: 'info',
  running: 'warning',
  done: 'success',
  failed: 'danger',
  need_review: 'warning',
}

/** 对照判定（02 §4.2，M2）*/
export const VERDICTS = ['satisfied', 'deviated', 'missing', 'uncertain'] as const
export type Verdict = (typeof VERDICTS)[number]

export const VERDICT_LABELS: Record<Verdict, string> = {
  satisfied: '满足',
  deviated: '负偏离',
  missing: '未响应',
  uncertain: '无法判定',
}

// ---- 报告 ----
export const REPORT_KINDS = ['checklist', 'comparison'] as const
export type ReportKind = (typeof REPORT_KINDS)[number]

// ---- 订单 ----
export const ORDER_STATUSES = ['pending', 'granted', 'expired', 'refunded'] as const
export type OrderStatus = (typeof ORDER_STATUSES)[number]

export const ORDER_STATUS_LABELS: Record<OrderStatus, string> = {
  pending: '待核销',
  granted: '已到账',
  expired: '已过期',
  refunded: '已退款',
}

export const ORDER_STATUS_TAGS: Record<OrderStatus, TagType> = {
  pending: 'warning',
  granted: 'success',
  expired: 'info',
  refunded: 'info',
}

// ---- 上传约束（与后端 FJ_MAX_UPLOAD_MB / FJ_MAX_PAGES 同步；后端为最终校验方）----
export const MAX_UPLOAD_MB = 100
export const MAX_PAGES = 500
