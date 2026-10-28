<script setup lang="ts">
import LogsPanel from '@/components/admin/LogsPanel.vue'
</script>

<template>
  <LogsPanel
    kind="audit"
    title="审计日志"
    desc="业务关键动作留痕（四链互查锚点），detail.request_id ↔ X-Request-ID"
  />
</template>
