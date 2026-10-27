<!-- 主题配置抽屉：外观模式（亮/暗/跟随系统）+ 主题色预设 + 实时预览。
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
        <p class="drawer-desc">偏好保存在本机浏览器，修改后立即生效</p>
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
          <span class="swatch-label">{{ p.label }}</span>
        </button>
      </div>
    </section>

    <section class="section">
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

    <section class="section">
      <h3 class="section-title">效果预览</h3>
      <div class="preview">
        <div class="preview-head">
          <span class="preview-title">检查项目</span>
          <el-tag size="small" type="success"><span class="tag-dot" />清单就绪</el-tag>
        </div>
        <p class="preview-desc">上传双文件后自动比对废标风险，结论全程留痕。</p>
        <div class="preview-actions">
          <el-button type="primary" size="small">新建项目</el-button>
          <el-button size="small">查看详情</el-button>
        </div>
      </div>
    </section>

    <footer class="drawer-foot">
      <el-button class="reset-btn" @click="theme.reset()">恢复默认（外观 + 交互）</el-button>
      <p class="foot-note">当前：{{ modeLabel }}</p>
    </footer>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import {
  DRAWER_WIDTHS,
  DRAWER_WIDTH_LABELS,
  OVERLAY_MODES,
  OVERLAY_MODE_LABELS,
  THEME_MODES,
  THEME_MODE_LABELS,
  type ThemeMode,
} from '@/constants/theme'
import { useThemeStore } from '@/stores/theme'

const theme = useThemeStore()

const modeLabel = computed(() => THEME_MODE_LABELS[theme.mode])

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

// ---- 主题色 ----
.swatches {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 6px;
}

.swatch {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
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
  transition: box-shadow @dur-fast @ease-out;

  svg {
    width: 14px;
    height: 14px;
  }
}

.swatch.is-active .swatch-dot {
  box-shadow:
    0 0 0 2px @c-surface,
    0 0 0 4px var(--swatch);
}

.swatch-label {
  font-size: 11px;
  color: @c-text-muted;
}

.swatch.is-active .swatch-label {
  color: @c-text;
  font-weight: 600;
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

// ---- 预览 ----
.preview {
  padding: 16px;
  border: 1px solid @c-line-soft;
  border-radius: @radius;
  background: @c-surface-alt;
}

.preview-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.preview-title {
  font-size: @fs-sm;
  font-weight: 600;
  color: @c-text;
}

.preview-desc {
  margin: 8px 0 14px;
  font-size: @fs-xs;
  line-height: 1.6;
  color: @c-text-sub;
}

.preview-actions {
  display: flex;
  gap: 8px;
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
