/** 配额 / 订单资源（02 §9.5） */
import { api, withQuery } from './client'
import type { OrderOut, OrderPage, QuotaOut } from '@/types'

export function getQuota() {
  return api<QuotaOut>('/me/quota')
}

export function listOrders(params: { limit?: number; offset?: number } = {}) {
  return api<OrderPage>(withQuery('/orders', params))
}

export function createOrder(sku: string, note?: string) {
  return api<OrderOut>('/orders', { method: 'POST', body: JSON.stringify({ sku, note }) })
}
