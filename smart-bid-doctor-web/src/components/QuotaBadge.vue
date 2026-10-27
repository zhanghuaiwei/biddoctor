<!-- 顶栏配额徽标：挂载即拉 /me/quota 展示免费额度与对照次数余量（只读展示，
     不承担刷新职责；配额变动页面自行触发重新拉取）。 -->
<template>
  <span v-if="loaded" class="quota-badge">
    本月免费 <b>{{ quota.free_left }}</b> 个 · 对照次数 <b>{{ packRemain }}</b>
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
  margin-right: 16px;
  color: @c-text-sub;
  font-size: 13px;

  b {
    color: @c-text;
  }

  @media (max-width: @bp-sm) {
    display: none;
  }
}
</style>
