/** 认证资源（02 §9.1） */
import { api } from './client'
import type { EmailCodeOut, LoginOut } from '@/types'

export function requestEmailCode(email: string): Promise<EmailCodeOut> {
  return api<EmailCodeOut>('/auth/email-code', { method: 'POST', body: JSON.stringify({ email }) })
}

export function login(email: string, code: string): Promise<LoginOut> {
  return api<LoginOut>('/auth/login', { method: 'POST', body: JSON.stringify({ email, code }) })
}
