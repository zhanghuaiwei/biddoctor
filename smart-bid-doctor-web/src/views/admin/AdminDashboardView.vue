<!-- 监控大盘（05 §4.1）：任务 / LLM / 容量水位 + 告警入口，即席聚合自动刷新 -->
<template>
  <div class="page">
    <header class="page-head">
      <div>
        <p class="page-eyebrow">Monitoring</p>
        <h1 class="page-title">监控大盘</h1>
        <p class="page-desc">任务队列、LLM 用量与容量水位实时聚合（30s 自动刷新）</p>
      </div>
      <div class="page-actions">
        <el-button :loading="loading" @click="load">刷新</el-button>
      </div>
    </header>

    <div class="cascade-in">
      <el-row :gutter="16">
        <el-col v-for="s in taskStats" :key="s.label" :xs="12" :md="6">
          <el-card class="lift-card stat-card" :class="s.tone">
            <p class="stat-value num">{{ s.value }}</p>
            <p class="stat-label">{{ s.label }}</p>
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="16" class="mt">
        <el-col :xs="24" :md="14">
          <el-card class="lift-card">
            <template #header>
              <div class="panel-head">
                <div class="panel-head-main">
                  <span class="panel-title">任务状态分布</span>
                  <span class="panel-count">实时</span>
                </div>
                <span class="panel-hint">今日成功率 {{ pct(data.tasks.today_success_rate) }}</span>
              </div>
            </template>
            <div class="status-grid">
              <div v-for="(n, k) in data.tasks.by_status" :key="k" class="status-cell">
                <span class="num status-num">{{ n }}</span>
                <span class="status-key">{{ k }}</span>
              </div>
              <p v-if="!Object.keys(data.tasks.by_status ?? {}).length" class="empty-line">暂无任务数据</p>
            </div>
            <el-divider />
            <div class="kv"><span>pending 积压</span><b class="num">{{ data.tasks.backlog_minutes ?? 0 }} 分钟</b></div>
            <div class="kv"><span>今日任务总数</span><b class="num">{{ data.tasks.today_total ?? 0 }}</b></div>
          </el-card>
        </el-col>

        <el-col :xs="24" :md="10">
          <el-card class="lift-card">
            <template #header>
              <div class="panel-head">
                <div class="panel-head-main">
                  <span class="panel-title">容量水位</span>
                  <span class="panel-hint">扩容触发线：doc_blocks 500 万行</span>
                </div>
              </div>
            </template>
            <div class="kv"><span>doc_blocks 行数</span><b class="num">{{ fmtNum(data.capacity.doc_blocks_rows) }}</b></div>
            <div class="kv"><span>在册文档数</span><b class="num">{{ fmtNum(data.capacity.documents) }}</b></div>
            <el-divider />
            <div class="kv"><span>今日 LLM 调用</span><b class="num">{{ data.llm.today_calls ?? 0 }}</b></div>
            <div class="kv"><span>今日 LLM 成本</span><b class="num">¥{{ data.llm.today_cost_cny ?? '0.0000' }}</b></div>
          </el-card>
        </el-col>
      </el-row>

      <el-card class="lift-card mt">
        <template #header>
          <div class="panel-head">
            <div class="panel-head-main">
              <span class="panel-title">LLM 用量（按模型）</span>
              <span class="panel-hint">M1 接入后自动出数</span>
            </div>
          </div>
        </template>
        <el-table :data="data.llm.models ?? []" size="large" empty-text="暂无调用记录">
          <el-table-column prop="model" label="模型" min-width="140" />
          <el-table-column prop="calls" label="调用量" width="100" />
          <el-table-column label="成功率" width="100">
            <template #default="{ row }">{{ pct(row.success_rate) }}</template>
          </el-table-column>
          <el-table-column label="平均时延" width="110">
            <template #default="{ row }">{{ row.avg_latency_ms != null ? row.avg_latency_ms + ' ms' : '—' }}</template>
          </el-table-column>
          <el-table-column prop="prompt_tokens" label="输入 tokens" width="130" />
          <el-table-column prop="output_tokens" label="输出 tokens" width="130" />
          <el-table-column label="成本（元）" width="120">
            <template #default="{ row }"><span class="num">¥{{ row.cost_cny }}</span></template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'

import { getMonitorOverview } from '@/api/admin'
import type { MonitorOverview } from '@/types'
import { usePolling } from '@/composables/usePolling'
import { notifyApiError } from '@/api/client'
import { formatLocaleNum, formatPercent } from '@/utils/format'

const data = ref<MonitorOverview>({
  tasks: {}, llm: {}, capacity: {}, unacked_alerts: 0,
})
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    data.value = await getMonitorOverview()
  } catch (e) {
    notifyApiError(e, '监控数据加载失败')
  } finally {
    loading.value = false
  }
}

const taskStats = computed(() => [
  { label: '排队中 pending', value: data.value.tasks.pending ?? 0, tone: '' },
  { label: '执行中 running', value: data.value.tasks.running ?? 0, tone: 'tone-warn' },
  { label: '需人工复核', value: data.value.tasks.need_review ?? 0, tone: 'tone-warn' },
  { label: '未确认告警', value: data.value.unacked_alerts, tone: data.value.unacked_alerts ? 'tone-danger' : '' },
])

const pct = (v: number | null | undefined) => formatPercent(v)
const fmtNum = (v: number | undefined) => formatLocaleNum(v)

const { start, stop } = usePolling(async () => {
  await load()
  return true
}, 30_000)

onMounted(() => {
  void load()
  start()
})
onUnmounted(stop)
</script>

<style scoped lang="less">
.mt {
  margin-top: 16px;
}

.stat-card {
  .stat-value {
    margin: 0;
    font-size: 26px;
    font-weight: 700;
  }

  .stat-label {
    margin: 4px 0 0;
    font-size: @fs-xs;
    color: @c-text-muted;
  }

  &.tone-warn .stat-value { color: @c-warning; }
  &.tone-danger .stat-value { color: @c-danger; }
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(96px, 1fr));
  gap: 10px;
}

.status-cell {
  padding: 10px 12px;
  border: 1px solid @c-line-soft;
  border-radius: @radius-sm;
}

.status-num {
  display: block;
  font-size: 18px;
  font-weight: 700;
}

.status-key {
  font-size: @fs-xs;
  color: @c-text-muted;
}

.empty-line {
  margin: 0;
  color: @c-text-muted;
  font-size: @fs-sm;
}

.kv {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  font-size: @fs-sm;
  color: @c-text-sub;

  b {
    color: @c-text;
  }
}
</style>
