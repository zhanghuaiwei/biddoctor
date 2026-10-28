<script setup lang="ts">
import LogsPanel from '@/components/admin/LogsPanel.vue'
</script>

<template>
  <LogsPanel
    kind="login"
    title="登录日志"
    desc="登录尝试全量记录（成功/失败/锁定原因），留存 180 天"
  />
</template>
