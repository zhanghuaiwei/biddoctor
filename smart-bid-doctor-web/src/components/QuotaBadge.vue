<!-- 顶栏配额徽标：挂载即拉 /me/quota 展示免费额度与对照次数余量（只读展示，
     不承担刷新职责；配额变动页面自行触发重新拉取）。 -->
<template>
  <span v-if="loaded" class="quota-badge">
    <span class="q-item">
      <span class="q-label">免费</span>
      <b class="num">{{ quota.free_left }}</b>
      <span class="q-unit">个</span>
    </span>
    <span class="q-sep" aria-hidden="true" />
    <span class="q-item">
      <span class="q-label">对照</span>
      <b class="num">{{ packRemain }}</b>
      <span class="q-unit">次</span>
    </span>
  </span>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { getQuota } from '@/api/billing'
import type { QuotaOut } from '@/types'

/** 头部全局额度徽标：项目列表/次数页不再各自重复请求展示 */
const loaded = ref(false)
const quota = ref<QuotaOut>({ free_left: 0, packs: [] })

const packRemain = computed(() => quota.value.packs.reduce((sum, p) => sum + p.remain, 0))

onMounted(load)

defineExpose({ reload: load })

async function load() {
  try {
    quota.value = await getQuota()
    loaded.value = true
  } catch {
    /* 静默 */
  }
}
</script>

<style scoped lang="less">
.quota-badge {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  height: 32px;
  padding: 0 12px;
  border: 1px solid @c-line-soft;
  border-radius: @radius-pill;
  background: @c-surface-alt;

  @media (max-width: @bp-sm) {
    display: none;
  }
}

.q-item {
  display: inline-flex;
  align-items: baseline;
  gap: 4px;
}

.q-label {
  font-size: 10px;
  color: @c-text-muted;
  letter-spacing: 0.04em;
}

.q-item b {
  font-size: @fs-sm;
  font-weight: 700;
  color: @c-text;
}

.q-unit {
  font-size: 10px;
  color: @c-text-muted;
}

.q-sep {
  width: 1px;
  height: 14px;
  background: @c-line;
}
</style>
