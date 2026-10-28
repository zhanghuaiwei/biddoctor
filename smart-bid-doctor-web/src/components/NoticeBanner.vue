<!-- 公告横幅（05 §3.3）：published 且生效的记录，按 level 分级样式，可逐条关闭 -->
<template>
  <transition name="rise">
    <div v-if="visible.length" class="notice-banner" role="status">
      <div
        v-for="(n, i) in visible"
        :key="n.id"
        class="notice-item"
        :class="`notice-${n.level}`"
      >
        <span class="notice-icon" aria-hidden="true">
          <svg v-if="n.level === 'critical'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round">
            <path d="M12 9v4" /><path d="M12 17h.01" /><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
          </svg>
          <svg v-else-if="n.level === 'warn'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round">
            <circle cx="12" cy="12" r="9" /><path d="M12 8v4" /><path d="M12 16h.01" />
          </svg>
          <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round">
            <path d="M12 8a4 4 0 1 0-4 4c-3 0-5 2-5 4" transform="translate(5 2)" />
            <circle cx="12" cy="8" r="3.4" /><path d="M5 20c0-3.3 3.1-5.4 7-5.4s7 2.1 7 5.4" />
          </svg>
        </span>
        <div class="notice-body">
          <b class="notice-title">{{ n.title }}</b>
          <span class="notice-content">{{ n.content }}</span>
        </div>
        <button class="notice-close" aria-label="关闭公告" @click="dismiss(i)">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round">
            <path d="M6 6l12 12M18 6L6 18" />
          </svg>
        </button>
      </div>
    </div>
  </transition>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { listNotices } from '@/api/platform'
import type { NoticeItem } from '@/types'

const visible = ref<Array<NoticeItem & { publish_at: string }>>([])

onMounted(async () => {
  try {
    visible.value = await listNotices(3)
  } catch {
    // 公告为增强信息，失败静默不打扰主流程
  }
})

function dismiss(i: number) {
  visible.value.splice(i, 1)
}
</script>

<style scoped lang="less">
.notice-banner {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px 24px 0;

  @media (max-width: @bp-sm) {
    padding: 10px 14px 0;
  }
}

.notice-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 14px;
  border-radius: @radius;
  border: 1px solid transparent;
  animation: rise-in @dur-base @ease-out both;

  &.notice-info {
    background: var(--app-accent-soft);
    border-color: color-mix(in srgb, var(--app-accent) 26%, transparent);
    color: @c-text;

    .notice-icon { color: var(--app-accent); }
  }

  &.notice-warn {
    background: fade(@c-warning, 10%);
    border-color: fade(@c-warning, 34%);
    color: @c-text;

    .notice-icon { color: @c-warning; }
  }

  &.notice-critical {
    background: fade(@c-danger, 9%);
    border-color: fade(@c-danger, 32%);
    color: @c-text;

    .notice-icon { color: @c-danger; }
  }
}

.notice-icon {
  flex: none;
  display: inline-flex;
  padding-top: 2px;

  svg {
    width: 16px;
    height: 16px;
  }
}

.notice-body {
  flex: 1;
  min-width: 0;
  font-size: @fs-sm;
  line-height: 1.55;
}

.notice-title {
  margin-right: 8px;
}

.notice-content {
  color: @c-text-sub;
}

.notice-close {
  flex: none;
  display: inline-flex;
  padding: 4px;
  border: none;
  background: none;
  color: @c-text-muted;
  cursor: pointer;
  border-radius: @radius-xs;
  transition: color @dur-fast @ease-out, background-color @dur-fast @ease-out;

  svg {
    width: 14px;
    height: 14px;
  }

  &:hover {
    color: @c-text;
    background: fade(#000, 5%);
  }
}
</style>
