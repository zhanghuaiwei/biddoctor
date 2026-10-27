/**
 * 后端 API DTO 类型——与 smart-bid-doctor-api/app/schemas 对齐。
 * 枚举字段使用 constants/enums 的字面量联合；金额（amount_cny）后端以
 * Decimal 序列化为字符串，避免浮点精度丢失，前端直接展示不做数值运算。
 */
import type {
  CheckCategory,
  ComparisonStatus,
  DocumentRole,
  Industry,
  OrderStatus,
  ParseStatus,
  ProjectStatus,
  ReportKind,
  TaskStatus,
  TaskType,
} from './constants/enums'

export type {
  CheckCategory,
  ComparisonStatus,
  DocumentRole,
  Industry,
  OrderStatus,
  ParseStatus,
  ProjectStatus,
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
