/**
 * 主题 store（Pinia setup store）——外观模式 + 强调色 + 弹层交互偏好，运行期写回 CSS 变量。
 * - 可持久：偏好经 STORAGE_KEYS.theme 写 localStorage（键名归口 constants/storage.ts）；
 * - 可配置：ThemeDrawer 只调用 store 动作，色阶计算与 DOM 应用集中在此；
 * - 生效范围：global.less 的 --app-* 变量（应用自身样式）与 --el-color-primary 全色阶（Element 组件）；
 *   交互偏好（弹窗/抽屉形态、抽屉宽度、遮罩与 ESC 关闭）由 components/OverlayPanel.vue 消费。
 */
import { computed, ref, watch } from 'vue'
import { defineStore } from 'pinia'

import {
  ACCENT_PRESETS,
  DEFAULT_ACCENT,
  DEFAULT_AUTH_LAYOUT,
  DEFAULT_INTERACTION,
  DEFAULT_LAYOUT,
  DRAWER_SIZE_MAP,
  type AuthFormPosition,
  type Density,
  type DrawerWidth,
  type NavLayout,
  type OverlayMode,
  type PageWidth,
  type ThemeMode,
} from '@/constants/theme'
import { STORAGE_KEYS } from '@/constants/storage'
import { mixHex } from '@/utils/color'

interface ThemePrefs {
  mode: ThemeMode
  accent: string
  overlayMode: OverlayMode
  drawerWidth: DrawerWidth
  closeOnClickModal: boolean
  closeOnPressEscape: boolean
  navLayout: NavLayout
  pageWidth: PageWidth
  density: Density
  authFormPosition: AuthFormPosition
}

const VALID_HEX = /^#[0-9a-fA-F]{6}$/

/** 读取持久化偏好（脏数据一律回退默认，避免坏值污染根变量） */
function loadPrefs(): ThemePrefs {
  const fallback: ThemePrefs = {
    mode: 'light',
    accent: DEFAULT_ACCENT,
    ...DEFAULT_INTERACTION,
    ...DEFAULT_LAYOUT,
    ...DEFAULT_AUTH_LAYOUT,
  }
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.theme)
    if (!raw) return fallback
    const parsed = JSON.parse(raw) as Partial<ThemePrefs>
    const mode: ThemeMode = parsed.mode === 'dark' || parsed.mode === 'system' ? parsed.mode : 'light'
    const overlayMode: OverlayMode =
      parsed.overlayMode === 'dialog' || parsed.overlayMode === 'drawer' ? parsed.overlayMode : 'auto'
    const drawerWidth: DrawerWidth =
      parsed.drawerWidth === 'narrow' || parsed.drawerWidth === 'wide' ? parsed.drawerWidth : 'medium'
    const navLayout: NavLayout = parsed.navLayout === 'top' ? 'top' : 'side'
    const pageWidth: PageWidth = parsed.pageWidth === 'wide' ? 'wide' : 'standard'
    const density: Density =
      parsed.density === 'compact' || parsed.density === 'comfortable' ? parsed.density : 'standard'
    const authFormPosition: AuthFormPosition =
      parsed.authFormPosition === 'left' || parsed.authFormPosition === 'center'
        ? parsed.authFormPosition
        : DEFAULT_AUTH_LAYOUT.authFormPosition
    return {
      mode,
      accent: typeof parsed.accent === 'string' && VALID_HEX.test(parsed.accent) ? parsed.accent : DEFAULT_ACCENT,
      overlayMode,
      drawerWidth,
      navLayout,
      pageWidth,
      density,
      authFormPosition,
      closeOnClickModal:
        typeof parsed.closeOnClickModal === 'boolean' ? parsed.closeOnClickModal : DEFAULT_INTERACTION.closeOnClickModal,
      closeOnPressEscape:
        typeof parsed.closeOnPressEscape === 'boolean'
          ? parsed.closeOnPressEscape
          : DEFAULT_INTERACTION.closeOnPressEscape,
    }
  } catch {
    return fallback
  }
}

export const useThemeStore = defineStore('theme', () => {
  const prefs = loadPrefs()
  const mode = ref<ThemeMode>(prefs.mode)
  const accent = ref<string>(prefs.accent)
  const overlayMode = ref<OverlayMode>(prefs.overlayMode)
  const drawerWidth = ref<DrawerWidth>(prefs.drawerWidth)
  const closeOnClickModal = ref(prefs.closeOnClickModal)
  const closeOnPressEscape = ref(prefs.closeOnPressEscape)
  const navLayout = ref<NavLayout>(prefs.navLayout)
  const pageWidth = ref<PageWidth>(prefs.pageWidth)
  const density = ref<Density>(prefs.density)
  const authFormPosition = ref<AuthFormPosition>(prefs.authFormPosition)
  const drawerOpen = ref(false)

  // 跟随系统：监听配色偏好变化，system 模式下实时切换
  const media = window.matchMedia('(prefers-color-scheme: dark)')
  const systemDark = ref(media.matches)
  media.addEventListener('change', (e) => {
    systemDark.value = e.matches
  })

  const isDark = computed(() => (mode.value === 'system' ? systemDark.value : mode.value === 'dark'))

  /** 抽屉实际宽度（统一由偏好换算，组件禁硬编码） */
  const drawerSize = computed(() => DRAWER_SIZE_MAP[drawerWidth.value])

  /** 写回根节点 CSS 变量 + dark class（Element 暗色主题以此为开关） */
  function apply() {
    const root = document.documentElement
    const dark = isDark.value
    root.classList.toggle('dark', dark)
    root.dataset.themeMode = mode.value
    // 布局偏好经 data-* 交由 global.less / MainLayout 消费，避免组件内散落判断
    root.dataset.navLayout = navLayout.value
    root.dataset.pageWidth = pageWidth.value
    root.dataset.density = density.value
    // 登录/注册页布局独立：表单位置由 LoginView 的 :global 选择器消费（仅登录页生效）
    root.dataset.authFormPosition = authFormPosition.value

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
    const payload: ThemePrefs = {
      mode: mode.value,
      accent: accent.value,
      overlayMode: overlayMode.value,
      drawerWidth: drawerWidth.value,
      closeOnClickModal: closeOnClickModal.value,
      closeOnPressEscape: closeOnPressEscape.value,
      navLayout: navLayout.value,
      pageWidth: pageWidth.value,
      density: density.value,
      authFormPosition: authFormPosition.value,
    }
    localStorage.setItem(STORAGE_KEYS.theme, JSON.stringify(payload))
  }

  watch(
    [
      mode,
      accent,
      overlayMode,
      drawerWidth,
      closeOnClickModal,
      closeOnPressEscape,
      navLayout,
      pageWidth,
      density,
      authFormPosition,
      isDark,
    ],
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

  function setOverlayMode(next: OverlayMode) {
    overlayMode.value = next
  }

  function setDrawerWidth(next: DrawerWidth) {
    drawerWidth.value = next
  }

  function setNavLayout(next: NavLayout) {
    navLayout.value = next
  }

  function setPageWidth(next: PageWidth) {
    pageWidth.value = next
  }

  function setDensity(next: Density) {
    density.value = next
  }

  function setAuthFormPosition(next: AuthFormPosition) {
    authFormPosition.value = next
  }

  /** 恢复默认：亮色 + 首个品牌强调色 + 默认交互与布局偏好 */
  function reset() {
    mode.value = 'light'
    accent.value = DEFAULT_ACCENT
    overlayMode.value = DEFAULT_INTERACTION.overlayMode
    drawerWidth.value = DEFAULT_INTERACTION.drawerWidth
    closeOnClickModal.value = DEFAULT_INTERACTION.closeOnClickModal
    closeOnPressEscape.value = DEFAULT_INTERACTION.closeOnPressEscape
    navLayout.value = DEFAULT_LAYOUT.navLayout
    pageWidth.value = DEFAULT_LAYOUT.pageWidth
    density.value = DEFAULT_LAYOUT.density
    authFormPosition.value = DEFAULT_AUTH_LAYOUT.authFormPosition
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
    overlayMode,
    drawerWidth,
    drawerSize,
    closeOnClickModal,
    closeOnPressEscape,
    navLayout,
    pageWidth,
    density,
    authFormPosition,
    setMode,
    setAccent,
    setOverlayMode,
    setDrawerWidth,
    setNavLayout,
    setPageWidth,
    setDensity,
    setAuthFormPosition,
    reset,
    openDrawer,
  }
})
