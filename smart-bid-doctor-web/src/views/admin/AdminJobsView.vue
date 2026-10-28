<!-- 定时任务管理（05 §3.4）：启停/手动触发/运行历史（sys_job_log），不破坏 tasks 状态机 -->
<template>
  <div class="page">
    <PageHeader eyebrow="Operations" title="定时任务" desc="调度元数据入 sys_job，执行复用 tasks 队列范式或 worker 内联执行">
      <template #actions>
        <el-button :loading="loading" @click="reload">刷新</el-button>
      </template>
    </PageHeader>

    <el-card class="lift-card cascade-in">
      <el-table :data="jobs" v-loading="loading" size="large" empty-text="暂无任务（bootstrap 种子生成）">
        <el-table-column prop="job_key" label="任务" min-width="130" />
        <el-table-column prop="name" label="名称" min-width="150" />
        <el-table-column prop="cron_expr" label="cron" width="120" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'" size="small">
              {{ row.enabled ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="上次运行" width="170">
          <template #default="{ row }">{{ formatDateTime(row.last_run_at) }}</template>
        </el-table-column>
        <el-table-column label="下次运行" width="170">
          <template #default="{ row }">{{ formatDateTime(row.next_run_at) }}</template>
        </el-table-column>
        <el-table-column prop="remark" label="说明" min-width="220" show-overflow-tooltip />
        <el-table-column label="操作" width="230" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="onRun(row as JobOut)">手动触发</el-button>
            <el-button v-if="row.enabled" size="small" text type="warning" @click="onToggle(row as JobOut, false)">停用</el-button>
            <el-button v-else size="small" text type="success" @click="onToggle(row as JobOut, true)">启用</el-button>
            <el-button size="small" text @click="openLogs(row as JobOut)">历史</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <OverlayPanel v-model="logsOpen" :title="`运行历史 · ${logsKey}`" content-size="lg">
      <el-table :data="logs" v-loading="logsLoading" size="large" empty-text="暂无运行记录" max-height="420">
        <el-table-column label="时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="结果" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 'ok' ? 'success' : 'danger'" size="small">
              {{ row.status === 'ok' ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="耗时" width="90">
          <template #default="{ row }">
            <span class="num">{{ row.cost_ms != null ? `${row.cost_ms} ms` : '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="结果摘要 / 错误" min-width="280">
          <template #default="{ row }">
            <span v-if="row.error" class="err">{{ row.error }}</span>
            <code v-else-if="row.result" class="result">{{ JSON.stringify(row.result) }}</code>
            <span v-else>—</span>
          </template>
        </el-table-column>
      </el-table>
    </OverlayPanel>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { disableJob, enableJob, listJobLogs, listJobs, runJob } from '@/api/admin'
import { notifyApiError } from '@/api/client'
import OverlayPanel from '@/components/OverlayPanel.vue'
import PageHeader from '@/components/PageHeader.vue'
import { useApiAction } from '@/composables/useApiAction'
import type { JobLogOut, JobOut } from '@/types'
import { confirmAction } from '@/utils/confirm'
import { formatDateTime } from '@/utils/format'

const jobs = ref<JobOut[]>([])
const loading = ref(false)
const logsOpen = ref(false)
const logsLoading = ref(false)
const logsKey = ref('')
const logs = ref<JobLogOut[]>([])

const { run: runJobAction } = useApiAction()

async function reload() {
  loading.value = true
  try {
    jobs.value = await listJobs()
  } catch (e) {
    notifyApiError(e, '任务加载失败')
  } finally {
    loading.value = false
  }
}

async function onRun(row: JobOut) {
  const ok = await confirmAction(`立即触发「${row.name}」？worker 将在数秒内执行。`, {
    title: '手动触发',
    confirmText: '触发',
  })
  if (!ok) return
  const res = await runJobAction(() => runJob(row.id))
  if (!res.ok) return
  ElMessage.success('已触发，稍后可在运行历史查看结果')
  void reload()
}

async function onToggle(row: JobOut, enabled: boolean) {
  const res = await runJobAction(() => (enabled ? enableJob(row.id) : disableJob(row.id)))
  if (!res.ok) return
  ElMessage.success(enabled ? '已启用' : '已停用')
  void reload()
}

async function openLogs(row: JobOut) {
  logsKey.value = row.job_key
  logs.value = []
  logsOpen.value = true
  logsLoading.value = true
  try {
    const data = await listJobLogs(row.job_key, { limit: 50 })
    logs.value = data.items
  } catch (e) {
    notifyApiError(e, '运行历史加载失败')
  } finally {
    logsLoading.value = false
  }
}

onMounted(reload)
</script>

<style scoped lang="less">
.err {
  color: @c-danger;
  font-size: @fs-xs;
}

.result {
  font-size: @fs-xs;
  color: @c-text-sub;
  word-break: break-all;
}
</style>
