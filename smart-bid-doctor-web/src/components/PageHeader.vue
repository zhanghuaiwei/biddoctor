<!-- 页头统一承载（global.less .page-head 体系）：eyebrow/标题/描述 + 右侧 actions 插槽。
     项目详情等自定义头部结构（返回链接 + 标题行内联标签）不适用本组件时仍直写 .page-head。 -->
<script setup lang="ts">
defineProps<{
  eyebrow: string
  title: string
  desc?: string
}>()
</script>

<template>
  <header class="page-head">
    <div>
      <span class="page-eyebrow">{{ eyebrow }}</span>
      <h1 class="page-title">{{ title }}</h1>
      <p v-if="desc" class="page-desc">{{ desc }}</p>
    </div>
    <div v-if="$slots.actions" class="page-actions">
      <slot name="actions" />
    </div>
  </header>
</template>
