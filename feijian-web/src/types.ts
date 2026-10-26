/** 后端 API DTO 类型（与 feijian-api/app/schemas 对齐） */

export interface UserOut {
  id: number
  email: string
  role: string
}

export interface LoginOut {
  token: string
  user: UserOut
}

export interface EmailCodeOut {
  sent: boolean
  dev_code: string | null
}

export interface ProjectOut {
  id: number
  uuid: string
  name: string
  industry: 'general' | 'medical'
  status: string
  created_at: string
}

export interface QuotaOut {
  free_left: number
  packs: { id: number; type: string; remain: number; expires_at: string | null }[]
}

export interface OrderOut {
  order_no: string
  sku: string
  amount_cny: number
  status: string
  pay_hint: string
  created_at: string
}

export interface DocumentItem {
  id: number
  role: 'tender' | 'bid'
  orig_name: string
  sha256: string
  size_bytes: number
  total_pages: number | null
  parse_status: string
  parse_warnings: string[]
  created_at: string
}

export interface CheckItemOut {
  id: number
  code: string
  category: string
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

export interface TaskOut {
  id: number
  type: string
  status: string
  stage: string | null
  progress: number
  error_code: string | null
  error_msg: string | null
}

export interface UploadResult {
  document_id: number
  task_id: number | null
  dup: boolean
}
