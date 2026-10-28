<!-- 主题配置抽屉：外观模式 + 主题色（登录页与工作台共用）；
     布局配置与交互偏好为工作台专属，登录/注册路由下隐藏（登录页为独立分屏版式，不参与工作台布局偏好）。
     所有状态归口 stores/theme.ts，本组件只负责展示与调用动作（色阶计算/DOM 写回均在 store）。 -->
<template>
  <el-drawer
    v-model="theme.drawerOpen"
    direction="rtl"
    :size="theme.drawerSize"
    :with-header="false"
    :close-on-click-modal="theme.closeOnClickModal"
    :close-on-press-escape="theme.closeOnPressEscape"
    class="theme-drawer"
  >
    <header class="drawer-head">
      <div>
        <h2 class="drawer-title">外观设置</h2>
        <p class="drawer-desc">
          {{ isLogin ? '仅调整登录页外观与布局，偏好保存在本机浏览器' : '偏好保存在本机浏览器，修改后立即生效' }}
        </p>
      </div>
      <el-button text circle aria-label="关闭外观设置" @click="theme.drawerOpen = false">
        <svg class="close-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" aria-hidden="true">
          <path d="M6 6l12 12M18 6L6 18" />
        </svg>
      </el-button>
    </header>

    <section class="section">
      <h3 class="section-title">外观模式</h3>
      <div class="mode-grid">
        <button
          v-for="m in THEME_MODES"
          :key="m"
          type="button"
          class="mode-card"
          :class="{ 'is-active': theme.mode === m }"
          @click="theme.setMode(m)"
        >
          <span class="mode-icon" v-html="MODE_ICONS[m]" />
          <span>{{ THEME_MODE_LABELS[m] }}</span>
        </button>
      </div>
    </section>

    <section class="section">
      <h3 class="section-title">主题色</h3>
      <div class="accent-row">
        <div class="swatches">
          <button
            v-for="p in theme.presets"
            :key="p.key"
            type="button"
            class="swatch"
            :class="{ 'is-active': theme.accent === p.color }"
            :style="{ '--swatch': p.color }"
            :aria-label="`使用${p.label}主题色`"
            @click="theme.setAccent(p.color)"
          >
            <span class="swatch-dot">
              <svg v-if="theme.accent === p.color" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M5 12l5 5 9-10" />
              </svg>
            </span>
          </button>
        </div>
        <el-color-picker
          class="accent-picker"
          :model-value="theme.accent"
          color-format="hex"
          :show-alpha="false"
          :predefine="predefineColors"
          :validate-event="false"
          aria-label="自定义主题色"
          @change="onPickColor"
        />
      </div>
      <p class="accent-hint">
        点击色块使用品牌预设，右侧取色器可自定义任意主题色{{ activePreset ? `（当前：${activePreset.label}）` : '（当前为自定义色）' }}
      </p>
    </section>

    <section v-if="isLogin" class="section">
      <h3 class="section-title">登录页布局</h3>
      <div class="field">
        <span class="field-label">表单位置</span>
        <div class="viz-grid">
          <button
            v-for="p in AUTH_FORM_POSITIONS"
            :key="p"
            type="button"
            class="viz-card"
            :class="{ 'is-active': theme.authFormPosition === p }"
            @click="theme.setAuthFormPosition(p)"
          >
            <span class="viz viz-split" :class="`viz-split--${p}`" aria-hidden="true">
              <i class="viz-brand" />
              <i class="viz-form" />
            </span>
            <span>{{ AUTH_FORM_POSITION_LABELS[p] }}</span>
          </button>
        </div>
        <p class="field-hint">居右为默认分屏（品牌区在左）；居中时品牌区全屏铺底、表单浮在其上；窄屏统一为品牌横幅在上</p>
      </div>
    </section>

    <section v-if="!isLogin" class="section">
      <h3 class="section-title">布局配置</h3>
      <div class="field">
        <span class="field-label">导航布局</span>
        <div class="viz-grid">
          <button
            v-for="n in NAV_LAYOUTS"
            :key="n"
            type="button"
            class="viz-card"
            :class="{ 'is-active': theme.navLayout === n }"
            @click="theme.setNavLayout(n)"
          >
            <span class="viz viz-nav" :class="`viz-nav--${n}`" aria-hidden="true">
              <i class="viz-bar" />
              <span class="viz-lines">
                <i />
                <i />
                <i />
              </span>
            </span>
            <span>{{ NAV_LAYOUT_LABELS[n] }}</span>
          </button>
        </div>
      </div>
      <div class="field">
        <span class="field-label">内容宽度</span>
        <div class="viz-grid">
          <button
            v-for="w in PAGE_WIDTHS"
            :key="w"
            type="button"
            class="viz-card"
            :class="{ 'is-active': theme.pageWidth === w }"
            @click="theme.setPageWidth(w)"
          >
            <span class="viz viz-width" :class="`viz-width--${w}`" aria-hidden="true">
              <i class="viz-page">
                <i />
                <i />
                <i />
              </i>
            </span>
            <span>{{ PAGE_WIDTH_LABELS[w] }}</span>
          </button>
        </div>
      </div>
      <div class="field">
        <span class="field-label">界面密度</span>
        <div class="viz-grid">
          <button
            v-for="d in DENSITIES"
            :key="d"
            type="button"
            class="viz-card"
            :class="{ 'is-active': theme.density === d }"
            @click="theme.setDensity(d)"
          >
            <span class="viz viz-density" :class="`viz-density--${d}`" aria-hidden="true">
              <i />
              <i />
              <i />
            </span>
            <span>{{ DENSITY_LABELS[d] }}</span>
          </button>
        </div>
      </div>
    </section>

    <section v-if="!isLogin" class="section">
      <h3 class="section-title">交互偏好</h3>
      <div class="field">
        <span class="field-label">大内容承载</span>
        <div class="seg">
          <button
            v-for="m in OVERLAY_MODES"
            :key="m"
            type="button"
            class="seg-btn"
            :class="{ 'is-active': theme.overlayMode === m }"
            @click="theme.setOverlayMode(m)"
          >
            {{ OVERLAY_MODE_LABELS[m] }}
          </button>
        </div>
        <p class="field-hint">内容少用弹窗、内容多用抽屉；「按内容自动」由弹层内容量决定</p>
      </div>
      <div class="field">
        <span class="field-label">抽屉宽度</span>
        <div class="seg">
          <button
            v-for="w in DRAWER_WIDTHS"
            :key="w"
            type="button"
            class="seg-btn"
            :class="{ 'is-active': theme.drawerWidth === w }"
            @click="theme.setDrawerWidth(w)"
          >
            {{ DRAWER_WIDTH_LABELS[w] }}
          </button>
        </div>
      </div>
      <div class="field-row">
        <span class="field-label">点击遮罩关闭</span>
        <el-switch v-model="theme.closeOnClickModal" size="small" />
      </div>
      <div class="field-row">
        <span class="field-label">ESC 关闭</span>
        <el-switch v-model="theme.closeOnPressEscape" size="small" />
      </div>
    </section>

    <footer class="drawer-foot">
      <el-button class="reset-btn" @click="theme.reset()">
        {{ isLogin ? '恢复默认外观与布局' : '恢复默认（外观 + 布局 + 交互）' }}
      </el-button>
      <p class="foot-note">当前：{{ modeLabel }}{{ activePreset ? '' : ' · 自定义主题色' }}</p>
    </footer>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import {
  ACCENT_PRESETS,
  AUTH_FORM_POSITION_LABELS,
  AUTH_FORM_POSITIONS,
  DENSITIES,
  DENSITY_LABELS,
  DRAWER_WIDTHS,
  DRAWER_WIDTH_LABELS,
  NAV_LAYOUTS,
  NAV_LAYOUT_LABELS,
  OVERLAY_MODES,
  OVERLAY_MODE_LABELS,
  PAGE_WIDTHS,
  PAGE_WIDTH_LABELS,
  THEME_MODES,
  THEME_MODE_LABELS,
  type ThemeMode,
} from '@/constants/theme'
import { useThemeStore } from '@/stores/theme'

const route = useRoute()
const theme = useThemeStore()

// 作用域：登录/注册路由下只保留适用于登录页的配置项（App.vue 全局唯一实例，按路由自动切换）
const isLogin = computed(() => route.path === '/login')

const modeLabel = computed(() => THEME_MODE_LABELS[theme.mode])

const activePreset = computed(() => theme.presets.find((p) => p.color === theme.accent))

/** 颜色选择器预置色 = 品牌预设（快捷自选 + 任意自定义） */
const predefineColors = ACCENT_PRESETS.map((p) => p.color)

function onPickColor(color: string | null) {
  // null = 清空选择，忽略保持当前色；非法值由 store 的 VALID_HEX 守卫静默拒绝
  if (color) theme.setAccent(color)
}

// 模式图标：内联 SVG，避免引入图标库依赖
const MODE_ICONS: Record<ThemeMode, string> = {
  light:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><circle cx="12" cy="12" r="4.2"/><path d="M12 2.5v2.2M12 19.3v2.2M4.7 4.7l1.6 1.6M17.7 17.7l1.6 1.6M2.5 12h2.2M19.3 12h2.2M4.7 19.3l1.6-1.6M17.7 6.3l1.6-1.6"/></svg>',
  dark: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M20 14.5A8.5 8.5 0 1 1 9.5 4a6.8 6.8 0 0 0 10.5 10.5z"/></svg>',
  system:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="12.5" rx="2"/><path d="M9 20.5h6M12 16.5v4"/></svg>',
}
</script>

<style scoped lang="less">
:deep(.el-drawer__body) {
  padding: 22px 22px 28px;
  background: var(--app-surface);
}

.drawer-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 18px;
  border-bottom: 1px solid @c-line-soft;
}

.drawer-title {
  margin: 0;
  font-size: @fs-h2;
  font-weight: 700;
  color: @c-text;
}

.drawer-desc {
  margin: 6px 0 0;
  font-size: @fs-xs;
  color: @c-text-muted;
}

.close-icon {
  width: 17px;
  height: 17px;
}

.section {
  margin-top: 24px;
}

.section-title {
  margin: 0 0 12px;
  font-size: @fs-xs;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: @c-text-sub;
}

// ---- 外观模式 ----
.mode-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.mode-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 14px 6px;
  border: 1px solid @c-line;
  border-radius: @radius;
  background: @c-surface;
  font: inherit;
  font-size: @fs-xs;
  color: @c-text-sub;
  cursor: pointer;
  transition:
    border-color @dur-fast @ease-out,
    background-color @dur-fast @ease-out,
    color @dur-fast @ease-out;

  &:hover {
    border-color: color-mix(in srgb, var(--app-accent) 45%, var(--app-line));
  }

  &.is-active {
    border-color: var(--app-accent);
    background: @c-accent-soft;
    color: var(--app-accent);
    font-weight: 600;
  }
}

.mode-icon {
  display: flex;

  :deep(svg) {
    width: 20px;
    height: 20px;
  }
}

// ---- 主题色（预设 + 取色器）----
.accent-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.swatches {
  display: flex;
  flex: 1;
  gap: 10px;
}

.swatch {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 4px;
  border: none;
  background: none;
  font: inherit;
  cursor: pointer;
}

.swatch-dot {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: var(--swatch);
  color: #fff;
  box-shadow: 0 0 0 2px transparent;
  transition: box-shadow @dur-fast @ease-out, transform @dur-fast @ease-out;

  svg {
    width: 14px;
    height: 14px;
  }
}

.swatch:hover .swatch-dot {
  transform: scale(1.1);
}

.swatch.is-active .swatch-dot {
  box-shadow:
    0 0 0 2px @c-surface,
    0 0 0 4px var(--swatch);
}

.accent-picker {
  flex: none;
}

.accent-hint {
  margin: 10px 0 0;
  font-size: 11px;
  line-height: 1.5;
  color: @c-text-muted;
}

// ---- 交互偏好 ----
.field + .field {
  margin-top: 14px;
}

.field-label {
  display: block;
  margin-bottom: 8px;
  font-size: @fs-xs;
  color: @c-text-sub;
}

.field-hint {
  margin: 8px 0 0;
  font-size: 11px;
  line-height: 1.5;
  color: @c-text-muted;
}

.field-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;

  & + & {
    margin-top: 12px;
  }

  .field-label {
    margin-bottom: 0;
  }
}

// 分段控件：形态/宽度二选一，选中态取强调色浅底
.seg {
  display: flex;
  gap: 4px;
  padding: 3px;
  border-radius: @radius;
  background: @c-surface-alt;
}

.seg-btn {
  flex: 1;
  padding: 7px 8px;
  border: none;
  border-radius: @radius-sm;
  background: transparent;
  font: inherit;
  font-size: @fs-xs;
  color: @c-text-sub;
  cursor: pointer;
  transition:
    background-color @dur-fast @ease-out,
    color @dur-fast @ease-out;

  &:hover {
    color: @c-text;
  }

  &.is-active {
    background: @c-surface;
    color: var(--app-accent);
    font-weight: 600;
    box-shadow: @shadow-xs;
  }
}

// ---- 可视化布局选项（表单位置 / 导航 / 宽度 / 密度）----
// 以缩略图直观看效果，替代表单式分段控件；缩略图由纯 CSS 方块拼出，不引入图标或图片资源。
.viz-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(0, 1fr));
  gap: 8px;
}

.viz-card {
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 7px;
  padding: 8px 6px 10px;
  border: 1px solid @c-line;
  border-radius: @radius;
  background: @c-surface;
  font: inherit;
  font-size: @fs-xs;
  color: @c-text-sub;
  cursor: pointer;
  transition:
    border-color @dur-fast @ease-out,
    background-color @dur-fast @ease-out,
    color @dur-fast @ease-out;

  &:hover {
    border-color: color-mix(in srgb, var(--app-accent) 45%, var(--app-line));
  }

  &.is-active {
    border-color: var(--app-accent);
    background: @c-accent-soft;
    color: var(--app-accent);
    font-weight: 600;
  }
}

// 缩略图外框：统一底色/内边距，各控件只换内部拼块
.viz {
  box-sizing: border-box;
  display: flex;
  width: 100%;
  height: 38px;
  padding: 4px;
  gap: 3px;
  border: 1px solid @c-line-soft;
  border-radius: @radius-sm;
  background-color: @c-bg;
  // 细网格底纹：版式蓝图感，区域块之间的留白处透出格线（线色取主题描边色并降低不透明度）
  background-image:
    linear-gradient(to right, color-mix(in srgb, var(--app-line) 42%, transparent) 1px, transparent 1px),
    linear-gradient(to bottom, color-mix(in srgb, var(--app-line) 42%, transparent) 1px, transparent 1px);
  background-size: 9px 9px;
  pointer-events: none;

  i {
    display: block;
    border-radius: 2px;
  }
}

// -- 表单位置：品牌块 + 表单块 --
.viz-brand {
  flex: 0 0 38%;
  background: color-mix(in srgb, var(--app-accent) 30%, transparent);
}

.viz-form {
  flex: 1;
  border: 1px solid color-mix(in srgb, var(--app-accent) 35%, transparent);
  background: @c-surface;
}

.viz-split--left {
  flex-direction: row-reverse;
}

.viz-split--center {
  position: relative;

  .viz-brand {
    flex: 1;
  }

  // 居中：品牌全屏铺底，表单块浮在正中
  .viz-form {
    position: absolute;
    top: 50%;
    left: 50%;
    width: 42%;
    height: 62%;
    transform: translate(-50%, -50%);
  }
}

// -- 导航布局：侧边栏竖条 / 顶部横条 + 内容行 --
.viz-nav {
  align-items: stretch;
}

.viz-bar {
  flex: none;
  background: color-mix(in srgb, var(--app-accent) 55%, transparent);
}

.viz-nav--side {
  flex-direction: row;

  .viz-bar {
    width: 22%;
  }
}

.viz-nav--top {
  flex-direction: column;

  .viz-bar {
    width: auto;
    height: 24%;
  }
}

.viz-lines {
  display: flex;
  flex: 1;
  flex-direction: column;
  justify-content: center;
  gap: 3px;

  i {
    height: 3px;
    background: @c-line;
  }
}

// -- 内容宽度：内容块居中收窄 / 撑满 --
.viz-width {
  align-items: stretch;
  justify-content: center;
}

.viz i.viz-page {
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 3px;
  padding: 3px;
  background: color-mix(in srgb, var(--app-accent) 12%, transparent);

  i {
    height: 3px;
    background: color-mix(in srgb, var(--app-accent) 45%, transparent);
  }
}

.viz-width--standard .viz-page {
  flex: 0 0 62%;
}

.viz-width--wide .viz-page {
  flex: 1;
}

// -- 界面密度：行高与间距随档位变化 --
.viz-density {
  box-sizing: border-box;
  flex-direction: column;
  justify-content: center;
  padding: 6px;

  i {
    width: 100%;
    background: @c-line;
  }
}

.viz-density--compact {
  gap: 3px;

  i {
    height: 2px;
  }
}

.viz-density--standard {
  gap: 4px;

  i {
    height: 4px;
  }
}

.viz-density--comfortable {
  gap: 5px;

  i {
    height: 6px;
  }
}

// ---- 底部 ----
.drawer-foot {
  margin-top: 28px;
  padding-top: 18px;
  border-top: 1px solid @c-line-soft;
}

.reset-btn {
  width: 100%;
}

.foot-note {
  margin: 10px 0 0;
  font-size: @fs-xs;
  text-align: center;
  color: @c-text-muted;
}
</style>
