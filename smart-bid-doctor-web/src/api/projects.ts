/** 项目 / 文件 / 清单 / 对照 / 报告 / 任务资源（02 §9.2–9.4、§9.6） */
import { api, withQuery } from './client'
import type { DocumentRole } from '@/constants/enums'
import type {
  CheckItemsPage,
  ComparisonOut,
  CompareStartedOut,
  DocumentListOut,
  DocumentStatusOut,
  ProjectOut,
  ProjectPage,
  ReportOut,
  TaskOut,
  UploadOut,
} from '@/types'

export function listProjects(params: { status?: string; limit?: number; offset?: number } = {}) {
  return api<ProjectPage>(withQuery('/projects', params))
}

export function getProject(id: number) {
  return api<ProjectOut>(`/projects/${id}`)
}

export function createProject(body: { name: string; industry: string }) {
  return api<ProjectOut>('/projects', { method: 'POST', body: JSON.stringify(body) })
}

export function deleteProject(id: number) {
  return api<void>(`/projects/${id}`, { method: 'DELETE' })
}

/** 上传超时放宽：100MB 文件在弱网下 30s 默认超时不够 */
export function uploadDocument(projectId: number, role: DocumentRole, file: File) {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('role', role)
  return api<UploadOut>(`/projects/${projectId}/documents`, {
    method: 'POST',
    body: fd,
    timeoutMs: 120_000,
  })
}

export function listDocuments(projectId: number) {
  return api<DocumentListOut>(`/projects/${projectId}/documents`)
}

export function getDocumentStatus(documentId: number) {
  return api<DocumentStatusOut>(`/projects/documents/${documentId}/status`)
}

export function listCheckItems(
  projectId: number,
  params: { category?: string; limit?: number; offset?: number } = {},
) {
  return api<CheckItemsPage>(withQuery(`/projects/${projectId}/check-items`, params))
}

/** M1 接入前为 501（ApiError.code === 'NOT_IMPLEMENTED'） */
export function startChecklistReport(projectId: number) {
  return api<{ report_id: number }>(`/projects/${projectId}/checklist-report`, { method: 'POST' })
}

export function startCompare(projectId: number) {
  return api<CompareStartedOut>(`/projects/${projectId}/compare`, { method: 'POST' })
}

/** 404 表示尚无对照记录（ApiError.code === 'COMPARISON_NOT_FOUND'） */
export function getLatestComparison(projectId: number) {
  return api<ComparisonOut>(`/projects/${projectId}/comparison`)
}

export function getReport(reportId: number) {
  return api<ReportOut>(`/reports/${reportId}`)
}

export function getTask(taskId: number) {
  return api<TaskOut>(`/tasks/${taskId}`)
}
