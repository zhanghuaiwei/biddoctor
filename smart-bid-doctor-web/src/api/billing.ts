/** 配额 / 订单资源（02 §9.5）+ 订阅计划（P2，05 商业化） */
import { api, withQuery } from './client'
import type { OrderOut, OrderPage, PlanOut, QuotaOut } from '@/types'

export function getQuota() {
  return api<QuotaOut>('/me/quota')
}

export function listOrders(params: { limit?: number; offset?: number } = {}) {
  return api<OrderPage>(withQuery('/orders', params))
}

export function createOrder(sku: string, note?: string) {
  return api<OrderOut>('/orders', { method: 'POST', body: JSON.stringify({ sku, note }) })
}

/** 用户端订阅计划（仅 active 在售；P2 订阅闭环） */
export function listActivePlans() {
  return api<PlanOut[]>('/subs/plans')
}
