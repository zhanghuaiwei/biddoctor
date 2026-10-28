<!-- 枚举状态标签统一渲染：labels/tags 引用 constants/enums 注册表，
     未知取值回退原码 + info 色；dot 显示状态点（全局 .tag-dot），plain 为描边形态（分类类标签）。 -->
<script setup lang="ts">
import { computed } from 'vue'

import type { TagType } from '@/constants/enums'

const props = defineProps<{
  value: string | null | undefined
  labels?: Record<string, string>
  tags?: Record<string, TagType>
  dot?: boolean
  plain?: boolean
}>()

const label = computed(() =>
  props.value != null ? (props.labels?.[props.value] ?? props.value) : '—',
)
const type = computed<TagType>(() =>
  props.value != null ? (props.tags?.[props.value] ?? 'info') : 'info',
)
</script>

<template>
  <el-tag :type="type" size="small" :effect="plain ? 'plain' : 'light'">
    <span v-if="dot" class="tag-dot" />{{ label }}
  </el-tag>
</template>
