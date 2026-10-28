import { onMounted, ref } from 'vue'
import type { Ref } from 'vue'

import { notifyApiError } from '@/api/client'

/** 分页列表响应统一契约（全站统一 limit/offset，列表响应带 total） */
export interface PagedResp<T> {
  items: T[]
  total: number
}

/**
 * 分页列表状态机：items/total/page/pageSize/loading + reload/onPage 的唯一封装。
 * fetcher 闭包内读取筛选条件并调用 api 资源函数（可附带副产物，如连带拉取的次级列表）；
 * 加载失败经 notifyApiError 统一提示；onMounted 自动首载；
 * 筛选变更直接调 reload()（保持当前页码，与既有列表页行为一致）。
 */
export function usePagedList<T>(
  fetcher: (params: { limit: number; offset: number }) => Promise<PagedResp<T>>,
  opts: { pageSize?: number; errorText?: string } = {},
) {
  const items = ref([]) as Ref<T[]>
  const total = ref(0)
  const page = ref(1)
  const loading = ref(false)
  const pageSize = opts.pageSize ?? 20

  async function reload() {
    loading.value = true
    try {
      const res = await fetcher({ limit: pageSize, offset: (page.value - 1) * pageSize })
      items.value = res.items
      total.value = res.total
    } catch (e) {
      notifyApiError(e, opts.errorText)
    } finally {
      loading.value = false
    }
  }

  function onPage(p: number) {
    page.value = p
    void reload()
  }

  onMounted(() => void reload())

  return { items, total, page, pageSize, loading, reload, onPage }
}
