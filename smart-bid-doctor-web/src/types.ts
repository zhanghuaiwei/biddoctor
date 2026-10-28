/**
 * 后端 API DTO 类型——与 smart-bid-doctor-api/app/schemas 对齐。
 * 枚举字段使用 constants/enums 的字面量联合；金额（amount_cny）后端以
 * Decimal 序列化为字符串，避免浮点精度丢失，前端直接展示不做数值运算。
 */
import type {
  CheckCategory,
  CommonStatus,
  ComparisonStatus,
  DocumentRole,
  Industry,
  LegalDocType,
  LegalStatus,
  LoginResult,
  NoticeLevel,
  NoticeStatus,
  NoticeType,
  OrderStatus,
  ParseStatus,
  PaymentStatus,
  ProjectStatus,
  ReportKind,
  SubscriptionStatus,
  TaskStatus,
  TaskType,
  UserStatus,
} from './constants/enums'

export type {
  CheckCategory,
  CommonStatus,
  ComparisonStatus,
  DocumentRole,
  Industry,
  LegalDocType,
  LegalStatus,
  LoginResult,
  NoticeLevel,
  NoticeStatus,
  NoticeType,
  OrderStatus,
  ParseStatus,
  PaymentStatus,
  ProjectStatus,
  ReportKind,
  SubscriptionStatus,
}

// ---- 认证（schemas/auth.py）----
export interface UserOut {
  id: number
  email: string
  role: 'user' | 'admin'
}

export interface LoginOut {
  token: string
  user: UserOut
}

export interface EmailCodeOut {
  sent: boolean
  dev_code: string | null
}

// ---- 项目 / 文件 / 任务（schemas/project.py）----
export interface ProjectOut {
  id: number
  uuid: string
  name: string
  industry: Industry
  status: ProjectStatus
  created_at: string
  updated_at: string
}

export interface ProjectPage {
  items: ProjectOut[]
  total: number
}

export interface DocumentItem {
  id: number
  role: DocumentRole
  orig_name: string
  sha256: string
  size_bytes: number
  total_pages: number | null
  parse_status: ParseStatus
  embedding_status: 'pending' | 'done' | 'skipped' | 'failed'
  parse_warnings: string[]
  created_at: string
}

export interface DocumentListOut {
  items: DocumentItem[]
}

export interface UploadOut {
  document_id: number
  task_id: number | null
  dup: boolean
}

export interface DocumentStatusOut {
  parse_status: ParseStatus
  progress: number
  stage: string | null
  warnings: string[]
  is_scanned_ratio: number | null
  task_id: number | null
}

export interface TaskOut {
  id: number
  type: TaskType
  status: TaskStatus
  stage: string | null
  progress: number
  attempt: number
  error_code: string | null
  error_msg: string | null
  created_at: string
}

// ---- 清单 / 对照 / 报告（schemas/check.py）----
export interface CheckItemOut {
  id: number
  code: string
  category: CheckCategory
  requirement: string
  raw_text: string
  ref_page: number
  is_mandatory: boolean
  confidence: number
}

export interface CheckItemsPage {
  items: CheckItemOut[]
  total: number
  stats: Record<string, number>
}

export interface ComparisonStats {
  red?: number
  yellow?: number
  green?: number
  stub?: boolean
}

export interface ComparisonOut {
  id: number
  project_id: number
  tender_doc_id: number
  bid_doc_id: number
  status: ComparisonStatus
  stats: ComparisonStats
  created_at: string
  finished_at: string | null
}

export interface CompareStartedOut {
  comparison_id: number
  task_id: number
}

export interface ReportOut {
  id: number
  project_id: number
  kind: ReportKind
  report_data: Record<string, unknown>
  disclaimer_ack: boolean
  created_at: string
}

// ---- 配额 / 订单（schemas/billing.py）----
export interface QuotaPackOut {
  id: number
  type: string
  remain: number
  expires_at: string | null
}

export interface QuotaOut {
  free_left: number
  packs: QuotaPackOut[]
}

export interface OrderOut {
  id: number
  order_no: string
  sku: string
  amount_cny: string
  status: OrderStatus
  pay_hint: string
  created_at: string
}

export interface OrderPage {
  items: OrderOut[]
  total: number
}

// ============================================================================
// 平台域（05 v2.0）：管理端 + 用户端平台功能
// ============================================================================

// ---- 导航 / 权限 ----
export interface MenuNode {
  id: number
  parent_id: number | null
  name: string
  type: 'dir' | 'menu' | 'button'
  path: string | null
  component: string | null
  icon: string | null
  sort: number
  visible: boolean
  children: MenuNode[]
}

export interface MeMenusOut {
  menus: MenuNode[]
  perms: string[]
}

// ---- 公告 ----
export interface NoticeItem {
  id: number
  title: string
  content: string
  type: NoticeType
  level: NoticeLevel
  publish_at: string | null
  status: NoticeStatus
  created_by: number | null
  created_at: string
}

export interface NoticePage {
  items: NoticeItem[]
  total: number
}

// ---- 附件 ----
export interface AttachmentOut {
  id: number
  uuid: string
  module: string
  business_id: number | null
  orig_name: string
  content_type: string | null
  size_bytes: number
  uploaded_by: number | null
  created_at: string
}

export interface AttachmentPage {
  items: AttachmentOut[]
  total: number
}

// ---- 法务 ----
export interface LegalDocOut {
  id: number
  doc_type: LegalDocType
  version: string
  title: string
  content: string
  effective_at: string
  status: LegalStatus
  created_at: string
}

export interface LegalCurrentOut {
  documents: LegalDocOut[]
  signed_ids: number[]
}

export interface SignatureOut {
  id: number
  user_id: number
  user_email: string | null
  legal_doc_id: number
  ip: string | null
  signed_at: string
}

export interface SignaturePage {
  items: SignatureOut[]
  total: number
}

// ---- 系统管理 ----
export interface OrgNode {
  id: number
  parent_id: number | null
  name: string
  code: string | null
  sort: number
  leader: string | null
  status: CommonStatus
  children: OrgNode[]
}

export interface RoleOut {
  id: number
  code: string
  name: string
  data_scope: 'all' | 'org' | 'self'
  sort: number
  status: CommonStatus
  remark: string | null
}

export interface AdminUserOut {
  id: number
  email: string
  nickname: string | null
  role: 'user' | 'admin'
  status: UserStatus
  org_id: number | null
  org_name: string | null
  created_at: string
  last_login_at: string | null
}

export interface AdminUserPage {
  items: AdminUserOut[]
  total: number
}

export interface InviteOut {
  id: number
  code: string
  max_uses: number
  used_count: number
  expires_at: string | null
  created_by: number | null
  created_at: string
}

export interface InvitePage {
  items: InviteOut[]
  total: number
}

// ---- 运维 ----
export interface ConfigOut {
  id: number
  config_key: string
  value: string
  value_type: 'str' | 'int' | 'bool' | 'json'
  name: string
  remark: string | null
  updated_by: number | null
  updated_at: string
}

export interface DictTypeOut {
  id: number
  dict_type: string
  name: string
  remark: string | null
}

export interface DictDataOut {
  id: number
  dict_type: string
  value: string
  label: string
  sort: number
  extra: Record<string, unknown> | null
  status: CommonStatus
}

export interface JobOut {
  id: number
  job_key: string
  name: string
  cron_expr: string
  handler: string
  enabled: boolean
  last_run_at: string | null
  next_run_at: string | null
  remark: string | null
}

export interface JobLogOut {
  id: number
  job_key: string
  status: 'ok' | 'fail'
  cost_ms: number | null
  result: Record<string, unknown> | null
  error: string | null
  created_at: string
}

export interface JobLogPage {
  items: JobLogOut[]
  total: number
}

// ---- 监控 / 告警 ----
export interface TaskAdminOut {
  id: number
  type: TaskType
  status: TaskStatus
  stage: string | null
  progress: number
  attempt: number
  error_code: string | null
  error_msg: string | null
  project_id: number | null
  document_id: number | null
  comparison_id: number | null
  created_at: string
  finished_at: string | null
}

export interface TaskAdminPage {
  items: TaskAdminOut[]
  total: number
}

export interface AlertOut {
  id: number
  rule_key: string
  level: NoticeLevel
  title: string
  content: string | null
  metric: Record<string, unknown> | null
  acked_by: number | null
  acked_at: string | null
  created_at: string
}

export interface AlertPage {
  items: AlertOut[]
  total: number
  unacked: number
}

export interface MonitorOverview {
  tasks: {
    by_status?: Record<string, number>
    pending?: number
    running?: number
    need_review?: number
    today_total?: number
    today_success_rate?: number | null
    backlog_minutes?: number
  }
  llm: {
    models?: Array<{
      model: string
      calls: number
      success_rate: number | null
      avg_latency_ms: number | null
      prompt_tokens: number
      output_tokens: number
      cost_cny: string
    }>
    today_calls?: number
    today_cost_cny?: string
  }
  capacity: {
    doc_blocks_rows?: number
    documents?: number
  }
  unacked_alerts: number
}

// ---- 日志 ----
export interface AuditLogOut {
  id: number
  user_id: number | null
  user_email: string | null
  action: string
  target: string | null
  detail: Record<string, unknown>
  ip: string | null
  created_at: string
}

export interface AuditLogPage {
  items: AuditLogOut[]
  total: number
}

export interface LoginLogOut {
  id: number
  user_id: number | null
  email: string | null
  result: LoginResult
  fail_reason: string | null
  ip: string | null
  user_agent: string | null
  created_at: string
}

export interface LoginLogPage {
  items: LoginLogOut[]
  total: number
}

export interface OperLogOut {
  id: number
  user_id: number | null
  module: string
  action: string
  method: string | null
  path: string | null
  status_code: number | null
  cost_ms: number | null
  request: Record<string, unknown> | null
  ip: string | null
  created_at: string
}

export interface OperLogPage {
  items: OperLogOut[]
  total: number
}

// ---- 统计 ----
export interface StatRowOut {
  stat_date: string
  dim: string
  metric: string
  value_num: string
  dims: Record<string, unknown> | null
}

// ---- AI 治理 ----
export interface AiModelOut {
  id: number
  model_code: string
  provider: string
  purpose: 'heavy' | 'light' | 'embed'
  input_price: string
  output_price: string
  rpm_limit: number | null
  enabled: boolean
  remark: string | null
  updated_at: string
}

export interface PromptOut {
  id: number
  name: string
  purpose: string
  version: number
  template: string
  variables: Record<string, unknown> | null
  is_active: boolean
  eval_score: Record<string, unknown> | null
  updated_by: number | null
  created_at: string
}

// ---- 订阅 / 规则库 / 支付 ----
export interface PlanOut {
  id: number
  code: string
  name: string
  price_cny: string
  period_months: number
  compare_quota: number
  status: 'active' | 'retired'
}

export interface SubscriptionOut {
  id: number
  user_id: number
  user_email: string | null
  plan_id: number
  plan_code: string | null
  status: SubscriptionStatus
  period_start: string
  period_end: string
  auto_renew: boolean
  created_at: string
}

export interface SubscriptionPage {
  items: SubscriptionOut[]
  total: number
}

export interface RuleSetOut {
  id: number
  industry: Industry
  law_version: string
  version: number
  status: 'draft' | 'active' | 'retired'
  effective_from: string | null
  notes: string | null
  created_at: string
}

export interface RuleItemOut {
  id: number
  rule_set_id: number
  category: CheckCategory
  kind: 'regex' | 'keyword' | 'numeric' | 'date'
  pattern: string
  action: 'hint' | 'must' | 'veto'
  weight: string
  description: string | null
}

export interface PaymentOut {
  id: number
  order_id: number
  channel: string
  out_trade_no: string
  amount_cny: string
  status: PaymentStatus
  paid_at: string | null
  created_at: string
}

export interface PaymentPage {
  items: PaymentOut[]
  total: number
}

export interface ReportPage {
  items: ReportOut[]
  total: number
}

export interface FeedbackOut {
  id: number
  feedback: 'agree' | 'disagree' | null
  feedback_note: string | null
  feedback_at: string | null
}
