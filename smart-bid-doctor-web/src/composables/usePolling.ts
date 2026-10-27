import { onUnmounted } from 'vue'

/**
 * 轮询封装：组件卸载自动清理；回调返回 false 时自动停止。
 * 典型用法：任务/解析进度轮询——busy 时继续，全部终态返回 false。
 */
export function usePolling(fn: () => Promise<boolean> | boolean, intervalMs = 3000) {
  let timer: number | undefined

  async function tick() {
    const keep = await fn()
    if (keep === false) stop()
  }

  function start() {
    if (timer === undefined) timer = window.setInterval(tick, intervalMs)
  }

  function stop() {
    if (timer !== undefined) {
      clearInterval(timer)
      timer = undefined
    }
  }

  onUnmounted(stop)
  return { start, stop, isPolling: () => timer !== undefined }
}
