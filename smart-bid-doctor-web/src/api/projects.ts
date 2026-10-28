/** 项目 / 文件 / 清单 / 对照 / 报告 / 任务资源（02 §9.2–9.4、§9.6） */
import { api, uploadWithProgress, withQuery } from './client'
import type { DocumentRole } from '@/constants/enums'
import type {
  CheckItemsPage,
  ComparisonOut,
  CompareStartedOut,
  DocumentListOut,
  DocumentStatusOut,
  FeedbackOut,
  ProjectOut,
  ProjectPage,
  ReportOut,
  ReportPage,
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

/** 上传超时放宽：100MB 文件在弱网下 30s 默认超时不够；onProgress 回调上传百分比（0-100） */
export function uploadDocument(
  projectId: number,
  role: DocumentRole,
  file: File,
  onProgress?: (percent: number) => void,
) {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('role', role)
  return uploadWithProgress<UploadOut>(`/projects/${projectId}/documents`, fd, {
    timeoutMs: 120_000,
    onProgress,
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

/** M1 报告闭环已实装：202 返回任务 id，前端轮询终态后拉取报告列表 */
export function startChecklistReport(projectId: number) {
  return api<{ task_id: number }>(`/projects/${projectId}/checklist-report`, { method: 'POST' })
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

export function listReports(projectId: number, params: { limit?: number; offset?: number } = {}) {
  return api<ReportPage>(withQuery(`/projects/${projectId}/reports`, params))
}

/** 免责声明确认（查看/导出前勾选） */
export function ackReport(reportId: number) {
  return api<ReportOut>(`/reports/${reportId}/ack`, { method: 'POST' })
}

/** 判定质量回流（P2）：agree 认可 / disagree 误报标记 */
export function feedbackFinding(findingId: number, feedback: 'agree' | 'disagree', note?: string) {
  return api<FeedbackOut>(`/findings/${findingId}/feedback`, {
    method: 'POST',
    body: JSON.stringify({ feedback, note }),
  })
}

export function getTask(taskId: number) {
  return api<TaskOut>(`/tasks/${taskId}`)
}
