<!-- 统一弹层承载：内容少 → 弹窗，内容多 → 抽屉（AGENTS 规则）。
     形态可被交互偏好覆盖（按内容自动 / 强制弹窗 / 强制抽屉），抽屉宽度与遮罩/ESC 关闭行为同样取偏好；
     业务弹层一律使用本组件，禁止在视图内各自写 el-dialog / el-drawer 造成形态与关闭行为不一致。 -->
<template>
  <el-drawer
    v-if="asDrawer"
    v-model="open"
    :size="theme.drawerSize"
    :with-header="false"
    :close-on-click-modal="theme.closeOnClickModal"
    :close-on-press-escape="theme.closeOnPressEscape"
    class="overlay-panel overlay-drawer"
  >
    <header class="overlay-head">
      <div class="overlay-head-main">
        <h2 class="overlay-title">{{ title }}</h2>
        <p v-if="desc" class="overlay-desc">{{ desc }}</p>
      </div>
      <el-button text circle aria-label="关闭" @click="open = false">
        <svg class="close-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" aria-hidden="true">
          <path d="M6 6l12 12M18 6L6 18" />
        </svg>
      </el-button>
    </header>
    <div class="overlay-body"><slot /></div>
    <footer v-if="$slots.footer" class="overlay-foot"><slot name="footer" /></footer>
  </el-drawer>

  <el-dialog
    v-else
    v-model="open"
    :title="title"
    :width="dialogWidth"
    align-center
    :close-on-click-modal="theme.closeOnClickModal"
    :close-on-press-escape="theme.closeOnPressEscape"
    class="overlay-panel"
  >
    <slot />
    <template v-if="$slots.footer" #footer><slot name="footer" /></template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import { useThemeStore } from '@/stores/theme'

const props = withDefaults(
  defineProps<{
    modelValue: boolean
    title: string
    desc?: string
    /** 内容量：sm 走弹窗，lg 走抽屉（auto 模式下生效） */
    contentSize?: 'sm' | 'lg'
  }>(),
  { desc: '', contentSize: 'sm' },
)

const emit = defineEmits<{ 'update:modelValue': [boolean] }>()

const theme = useThemeStore()

const open = computed({
  get: () => props.modelValue,
  set: (v: boolean) => emit('update:modelValue', v),
})

/** 承载形态：偏好强制，或 auto 按内容量判定 */
const asDrawer = computed(
  () => theme.overlayMode === 'drawer' || (theme.overlayMode === 'auto' && props.contentSize === 'lg'),
)

const dialogWidth = computed(() => (props.contentSize === 'lg' ? 'min(560px, 92vw)' : 'min(440px, 92vw)'))
</script>

<style scoped lang="less">
// ---- 抽屉形态 ----
.overlay-drawer {
  :deep(.el-drawer__body) {
    display: flex;
    flex-direction: column;
    padding: 0;
    background: var(--app-surface);
  }
}

.overlay-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 22px 22px 16px;
  border-bottom: 1px solid @c-line-soft;
}

.overlay-title {
  margin: 0;
  font-size: @fs-h2;
  font-weight: 700;
  color: @c-text;
}

.overlay-desc {
  margin: 6px 0 0;
  font-size: @fs-xs;
  line-height: 1.6;
  color: @c-text-muted;
}

.close-icon {
  width: 17px;
  height: 17px;
}

.overlay-body {
  flex: 1;
  overflow: auto;
  padding: 20px 22px;
}

.overlay-foot {
  padding: 14px 22px 20px;
  border-top: 1px solid @c-line-soft;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>
