<!-- 分页条统一承载（global.less .pager）：默认管理端口径（始终显示）；
     hide-single 为单页数据隐藏（项目列表等轻量场景），layout 可覆盖分页器布局。 -->
<script setup lang="ts">
withDefaults(
  defineProps<{
    total: number
    page: number
    pageSize: number
    layout?: string
    hideSingle?: boolean
  }>(),
  { layout: 'prev, pager, next', hideSingle: false },
)

const emit = defineEmits<{ change: [page: number] }>()
</script>

<template>
  <div v-if="!hideSingle || total > pageSize" class="pager">
    <el-pagination
      :layout="layout"
      :total="total"
      :page-size="pageSize"
      :current-page="page"
      @current-change="emit('change', $event)"
    />
  </div>
</template>
