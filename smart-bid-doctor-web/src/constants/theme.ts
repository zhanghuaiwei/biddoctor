/**
 * 主题配置注册表——外观模式与强调色预设的唯一来源。
 * 与 variables.less / global.less 的 --app-* 运行期变量配合：store 按此计算色阶并写回 root。
 */

// ---- 外观模式 ----
export const THEME_MODES = ['light', 'dark', 'system'] as const
export type ThemeMode = (typeof THEME_MODES)[number]

export const THEME_MODE_LABELS: Record<ThemeMode, string> = {
  light: '亮色',
  dark: '暗色',
  system: '跟随系统',
}

// ---- 强调色预设（主题色）----
export interface AccentPreset {
  key: string
  label: string
  color: string
}

export const ACCENT_PRESETS: readonly AccentPreset[] = [
  { key: 'brick', label: '砖红', color: '#be3b2e' },
  { key: 'indigo', label: '靛蓝', color: '#3b5bdb' },
  { key: 'teal', label: '墨绿', color: '#0f7b6c' },
  { key: 'amber', label: '琥珀', color: '#b07418' },
  { key: 'violet', label: '紫罗兰', color: '#7048b6' },
]

export const DEFAULT_ACCENT = ACCENT_PRESETS[0].color

// ---- 弹层承载（内容少用弹窗、内容多用抽屉；形态可配置覆盖）----
export const OVERLAY_MODES = ['auto', 'dialog', 'drawer'] as const
export type OverlayMode = (typeof OVERLAY_MODES)[number]

export const OVERLAY_MODE_LABELS: Record<OverlayMode, string> = {
  auto: '按内容自动',
  dialog: '弹窗',
  drawer: '抽屉',
}

// ---- 抽屉宽度 ----
export const DRAWER_WIDTHS = ['narrow', 'medium', 'wide'] as const
export type DrawerWidth = (typeof DRAWER_WIDTHS)[number]

export const DRAWER_WIDTH_LABELS: Record<DrawerWidth, string> = {
  narrow: '窄',
  medium: '中',
  wide: '宽',
}

export const DRAWER_SIZE_MAP: Record<DrawerWidth, string> = {
  narrow: '320px',
  medium: '400px',
  wide: '480px',
}

// ---- 布局偏好 ----
export const NAV_LAYOUTS = ['side', 'top'] as const
export type NavLayout = (typeof NAV_LAYOUTS)[number]

export const NAV_LAYOUT_LABELS: Record<NavLayout, string> = {
  side: '侧边栏',
  top: '顶部导航',
}

export const PAGE_WIDTHS = ['standard', 'wide'] as const
export type PageWidth = (typeof PAGE_WIDTHS)[number]

export const PAGE_WIDTH_LABELS: Record<PageWidth, string> = {
  standard: '标准',
  wide: '全宽',
}

export const DENSITIES = ['compact', 'standard', 'comfortable'] as const
export type Density = (typeof DENSITIES)[number]

export const DENSITY_LABELS: Record<Density, string> = {
  compact: '紧凑',
  standard: '标准',
  comfortable: '宽松',
}

// ---- 交互偏好默认值 ----
export const DEFAULT_INTERACTION = {
  overlayMode: 'auto' as OverlayMode,
  drawerWidth: 'medium' as DrawerWidth,
  closeOnClickModal: true,
  closeOnPressEscape: true,
}

// ---- 布局偏好默认值 ----
export const DEFAULT_LAYOUT = {
  navLayout: 'side' as NavLayout,
  pageWidth: 'standard' as PageWidth,
  density: 'standard' as Density,
}
