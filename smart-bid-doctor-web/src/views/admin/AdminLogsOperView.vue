<script setup lang="ts">
import LogsPanel from '@/components/admin/LogsPanel.vue'
</script>

<template>
  <LogsPanel
    kind="oper"
    title="操作日志"
    desc="管理端 HTTP 请求级日志（module/action/状态码/耗时），留存 180 天"
  />
</template>
