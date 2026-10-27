import { onUnmounted, ref } from 'vue'

/** 验证码等倒计时：组件卸载自动清理，避免定时器泄漏 */
export function useCountdown(defaultSeconds: number) {
  const remaining = ref(0)
  let timer: number | undefined

  function stop() {
    if (timer !== undefined) {
      clearInterval(timer)
      timer = undefined
    }
  }

  function start(seconds: number = defaultSeconds) {
    stop()
    remaining.value = seconds
    timer = window.setInterval(() => {
      remaining.value -= 1
      if (remaining.value <= 0) stop()
    }, 1000)
  }

  onUnmounted(stop)
  return { remaining, start, stop }
}
