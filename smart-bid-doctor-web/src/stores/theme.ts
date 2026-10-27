/**
 * 主题 store（Pinia setup store）——外观模式 + 强调色，运行期写回 CSS 变量。
 * - 可持久：偏好经 STORAGE_KEYS.theme 写 localStorage（键名归口 constants/storage.ts）；
 * - 可配置：ThemeDrawer 只调用 store 动作，色阶计算与 DOM 应用集中在此；
 * - 生效范围：global.less 的 --app-* 变量（应用自身样式）与 --el-color-primary 全色阶（Element 组件）。
 */
import { computed, ref, watch } from 'vue'
import { defineStore } from 'pinia'

import { ACCENT_PRESETS, DEFAULT_ACCENT, type ThemeMode } from '@/constants/theme'
import { STORAGE_KEYS } from '@/constants/storage'
import { mixHex } from '@/utils/color'

interface ThemePrefs {
  mode: ThemeMode
  accent: string
}

const VALID_HEX = /^#[0-9a-fA-F]{6}$/

/** 读取持久化偏好（脏数据一律回退默认，避免坏值污染根变量） */
function loadPrefs(): ThemePrefs {
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.theme)
    if (!raw) return { mode: 'light', accent: DEFAULT_ACCENT }
    const parsed = JSON.parse(raw) as Partial<ThemePrefs>
    const mode: ThemeMode = parsed.mode === 'dark' || parsed.mode === 'system' ? parsed.mode : 'light'
    const accent = typeof parsed.accent === 'string' && VALID_HEX.test(parsed.accent) ? parsed.accent : DEFAULT_ACCENT
    return { mode, accent }
  } catch {
    return { mode: 'light', accent: DEFAULT_ACCENT }
  }
}

export const useThemeStore = defineStore('theme', () => {
  const prefs = loadPrefs()
  const mode = ref<ThemeMode>(prefs.mode)
  const accent = ref<string>(prefs.accent)
  const drawerOpen = ref(false)

  // 跟随系统：监听配色偏好变化，system 模式下实时切换
  const media = window.matchMedia('(prefers-color-scheme: dark)')
  const systemDark = ref(media.matches)
  media.addEventListener('change', (e) => {
    systemDark.value = e.matches
  })

  const isDark = computed(() => (mode.value === 'system' ? systemDark.value : mode.value === 'dark'))

  /** 写回根节点 CSS 变量 + dark class（Element 暗色主题以此为开关） */
  function apply() {
    const root = document.documentElement
    const dark = isDark.value
    root.classList.toggle('dark', dark)
    root.dataset.themeMode = mode.value

    const set = (name: string, value: string) => root.style.setProperty(name, value)
    set('--app-accent', accent.value)
    set('--app-accent-light', mixHex('#ffffff', accent.value, 0.06))
    set('--app-accent-dark', mixHex('#000000', accent.value, 0.14))
    set('--app-accent-light-3', mixHex('#ffffff', accent.value, 0.3))
    set('--app-accent-light-5', mixHex('#ffffff', accent.value, 0.5))
    set('--app-accent-light-7', mixHex('#ffffff', accent.value, 0.7))
    set('--app-accent-light-8', mixHex('#ffffff', accent.value, 0.8))
    set('--app-accent-light-9', mixHex('#ffffff', accent.value, 0.9))
    set('--app-accent-dark-2', mixHex('#000000', accent.value, 0.2))
    // 浅底：亮色下取近白，暗色下取近黑，保证强调色文字/图标始终可读
    set('--app-accent-soft', dark ? mixHex('#0d141d', accent.value, 0.82) : mixHex('#ffffff', accent.value, 0.9))
  }

  function save() {
    localStorage.setItem(STORAGE_KEYS.theme, JSON.stringify({ mode: mode.value, accent: accent.value }))
  }

  watch(
    [mode, accent, isDark],
    () => {
      apply()
      save()
    },
    { immediate: true },
  )

  function setMode(next: ThemeMode) {
    mode.value = next
  }

  function setAccent(color: string) {
    if (VALID_HEX.test(color)) accent.value = color
  }

  /** 恢复默认：亮色 + 首个品牌强调色 */
  function reset() {
    mode.value = 'light'
    accent.value = DEFAULT_ACCENT
  }

  function openDrawer() {
    drawerOpen.value = true
  }

  /** 预设列表：供抽屉渲染，避免组件侧重复维护色值 */
  const presets = ACCENT_PRESETS

  return {
    mode,
    accent,
    isDark,
    drawerOpen,
    presets,
    setMode,
    setAccent,
    reset,
    openDrawer,
  }
})
