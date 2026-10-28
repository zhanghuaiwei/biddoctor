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
/** 附件上传上限（05 §7：单文件 ≤20MB，与标书 100MB 分开） */
export const MAX_ATTACHMENT_MB = 20
export const MAX_PAGES = 500

// ============================================================================
// 平台化域枚举（05 文档 v2.0）：sys_* / 附件 / 法务 / AI 治理 / 订阅
// ============================================================================

// ---- 通用启停状态 ----
export const COMMON_STATUSES = ['active', 'disabled'] as const
export type CommonStatus = (typeof COMMON_STATUSES)[number]

export const COMMON_STATUS_LABELS: Record<CommonStatus, string> = {
  active: '启用',
  disabled: '停用',
}

export const COMMON_STATUS_TAGS: Record<CommonStatus, TagType> = {
  active: 'success',
  disabled: 'info',
}

// ---- 菜单节点类型 ----
export const MENU_TYPES = ['dir', 'menu', 'button'] as const
export type MenuType = (typeof MENU_TYPES)[number]

export const MENU_TYPE_LABELS: Record<MenuType, string> = {
  dir: '目录',
  menu: '页面',
  button: '按钮权限点',
}

// ---- 公告 ----
export const NOTICE_TYPES = ['notice', 'announcement'] as const
export type NoticeType = (typeof NOTICE_TYPES)[number]

export const NOTICE_TYPE_LABELS: Record<NoticeType, string> = {
  notice: '通知',
  announcement: '公告',
}

export const NOTICE_LEVELS = ['info', 'warn', 'critical'] as const
export type NoticeLevel = (typeof NOTICE_LEVELS)[number]

export const NOTICE_LEVEL_LABELS: Record<NoticeLevel, string> = {
  info: '常规',
  warn: '警告',
  critical: '紧急',
}

export const NOTICE_LEVEL_TAGS: Record<NoticeLevel, TagType> = {
  info: 'info',
  warn: 'warning',
  critical: 'danger',
}

export const NOTICE_STATUSES = ['draft', 'published', 'offline'] as const
export type NoticeStatus = (typeof NOTICE_STATUSES)[number]

export const NOTICE_STATUS_LABELS: Record<NoticeStatus, string> = {
  draft: '草稿',
  published: '已发布',
  offline: '已下线',
}

export const NOTICE_STATUS_TAGS: Record<NoticeStatus, TagType> = {
  draft: 'info',
  published: 'success',
  offline: 'info',
}

// ---- 登录日志 ----
export const LOGIN_RESULTS = ['success', 'fail'] as const
export type LoginResult = (typeof LOGIN_RESULTS)[number]

export const LOGIN_RESULT_LABELS: Record<LoginResult, string> = {
  success: '成功',
  fail: '失败',
}

export const LOGIN_RESULT_TAGS: Record<LoginResult, TagType> = {
  success: 'success',
  fail: 'danger',
}

// ---- 法务文档 ----
export const LEGAL_DOC_TYPES = ['user_agreement', 'privacy_policy', 'disclaimer'] as const
export type LegalDocType = (typeof LEGAL_DOC_TYPES)[number]

export const LEGAL_DOC_TYPE_LABELS: Record<LegalDocType, string> = {
  user_agreement: '用户协议',
  privacy_policy: '隐私政策',
  disclaimer: '免责声明',
}

export const LEGAL_STATUSES = ['draft', 'effective', 'retired'] as const
export type LegalStatus = (typeof LEGAL_STATUSES)[number]

export const LEGAL_STATUS_LABELS: Record<LegalStatus, string> = {
  draft: '草稿',
  effective: '生效中',
  retired: '已退役',
}

export const LEGAL_STATUS_TAGS: Record<LegalStatus, TagType> = {
  draft: 'info',
  effective: 'success',
  retired: 'info',
}

// ---- 订阅 ----
export const SUBSCRIPTION_STATUSES = ['active', 'expired', 'cancelled'] as const
export type SubscriptionStatus = (typeof SUBSCRIPTION_STATUSES)[number]

export const SUBSCRIPTION_STATUS_LABELS: Record<SubscriptionStatus, string> = {
  active: '生效中',
  expired: '已到期',
  cancelled: '已取消',
}

export const SUBSCRIPTION_STATUS_TAGS: Record<SubscriptionStatus, TagType> = {
  active: 'success',
  expired: 'info',
  cancelled: 'info',
}

// ---- 支付流水（P2 预留） ----
export const PAYMENT_STATUSES = ['created', 'paying', 'paid', 'failed', 'closed', 'refunded'] as const
export type PaymentStatus = (typeof PAYMENT_STATUSES)[number]

export const PAYMENT_STATUS_LABELS: Record<PaymentStatus, string> = {
  created: '已创建',
  paying: '支付中',
  paid: '已支付',
  failed: '失败',
  closed: '已关闭',
  refunded: '已退款',
}

// ---- 附件模块（05 §7 白名单）----
export const ATTACHMENT_MODULES = ['order_voucher', 'appeal', 'import', 'profile'] as const
export type AttachmentModule = (typeof ATTACHMENT_MODULES)[number]

export const ATTACHMENT_MODULE_LABELS: Record<AttachmentModule, string> = {
  order_voucher: '支付凭证',
  appeal: '申诉材料',
  import: '批量导入',
  profile: '资料补传',
}
