/**
 * 次数包 SKU 目录——与后端 `FJ_SKU_CATALOG` 配置、落地页价格卡三处同源。
 * 后端是价目单一事实来源（下单时校验 + 计价）；改价需同步此处展示与落地页。
 * times 仅用于前端单价换算展示，下单仍以 code 为准。
 */
export interface SkuInfo {
  code: string
  title: string
  priceCny: number
  times: number
}

export const SKUS: readonly SkuInfo[] = [
  { code: 'cmp_x5', title: '对照检查 5 次包', priceCny: 99, times: 5 },
  { code: 'cmp_x20', title: '对照检查 20 次包', priceCny: 199, times: 20 },
]
