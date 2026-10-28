import { ref } from 'vue'

import { notifyApiError } from '@/api/client'

/** 动作结果判别联合：失败时已就地提示（notifyApiError），调用方按 ok 分支处理 */
export type ActionResult<T> = { ok: true; data: T } | { ok: false }

/**
 * 异步动作封装：按钮 pending 态 + 统一错误提示收口。
 * 成功后的 UI 反馈（ElMessage / 关弹层 / 刷新列表）由调用方在 fn 内或 await 后处理。
 */
export function useApiAction(fallback = '操作失败，请稍后重试') {
  const pending = ref(false)

  async function run<T>(fn: () => Promise<T>): Promise<ActionResult<T>> {
    pending.value = true
    try {
      return { ok: true, data: await fn() }
    } catch (e) {
      notifyApiError(e, fallback)
      return { ok: false }
    } finally {
      pending.value = false
    }
  }

  return { pending, run }
}
