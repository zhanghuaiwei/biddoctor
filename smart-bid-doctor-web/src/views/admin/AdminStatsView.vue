<!-- 统计报表（05 §6）：T+1 汇总表维度查询 + SVG 趋势图 + CSV 导出（写 log_export 审计） -->
<template>
  <div class="page">
    <header class="page-head">
      <div>
        <p class="page-eyebrow">Analytics</p>
        <h1 class="page-title">统计报表</h1>
        <p class="page-desc">T+1 汇总（stats_rollup 每日 01:30）；明细实时聚合见监控大盘</p>
      </div>
      <div class="page-actions">
        <el-button :loading="rolling" @click="onRollup">补算昨日</el-button>
        <el-button type="primary" :loading="exporting" @click="onExport">导出 CSV</el-button>
      </div>
    </header>

    <el-card class="lift-card cascade-in">
      <template #header>
        <div class="panel-head">
          <div class="panel-head-main">
            <span class="panel-title">查询条件</span>
          </div>
        </div>
      </template>
      <div class="filters">
        <el-select v-model="dim" clearable placeholder="维度 dim" style="width: 150px" @change="reload">
          <el-option v-for="d in DIMS" :key="d" :label="d" :value="d" />
        </el-select>
        <el-select v-model="metric" filterable clearable placeholder="指标 metric" style="width: 240px" @change="reload">
          <el-option v-for="m in metricOptions" :key="m.value" :label="`${m.value}（${m.label}）`" :value="m.value" />
        </el-select>
        <el-date-picker
          v-model="range"
          type="daterange"
          value-format="YYYY-MM-DD"
          start-placeholder="开始"
          end-placeholder="结束"
          style="width: 260px"
          @change="reload"
        />
        <el-button :loading="loading" @click="reload">查询</el-button>
      </div>
    </el-card>

    <el-card v-if="trendPoints.length" class="lift-card mt">
      <template #header>
        <div class="panel-head">
          <div class="panel-head-main">
            <span class="panel-title">{{ trendMetric }} 趋势</span>
          </div>
        </div>
      </template>
      <TrendChart :points="trendPoints" />
    </el-card>

    <el-card class="lift-card mt">
      <template #header>
        <div class="panel-head">
          <div class="panel-head-main">
            <span class="panel-title">明细数据</span>
            <span class="panel-count num">{{ rows.length }}</span>
          </div>
        </div>
      </template>
      <el-table :data="rows" v-loading="loading" size="large" empty-text="暂无数据（stats_rollup 汇总后出数）">
        <el-table-column prop="stat_date" label="日期" width="120" />
        <el-table-column prop="dim" label="维度" width="110" />
        <el-table-column prop="metric" label="指标" min-width="220" />
        <el-table-column label="数值" width="140">
          <template #default="{ row }"><span class="num">{{ row.value_num }}</span></template>
        </el-table-column>
        <el-table-column label="细分" min-width="180">
          <template #default="{ row }">
            <span v-if="row.dims" class="dims">{{ JSON.stringify(row.dims) }}</span>
            <span v-else>—</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { exportStatsCsv, listStats, manualRollup } from '@/api/admin'
import { notifyApiError } from '@/api/client'
import type { StatRowOut } from '@/types'
import TrendChart from '@/components/TrendChart.vue'
import { saveBlob } from '@/utils/download'

const DIMS = ['user', 'business', 'commerce', 'cost', 'quality', 'system'] as const

const METRICS: Record<string, string> = {
  registered_users: '用户增长', active_users_7d: '活跃用户', orgs_count: '机构数',
  projects_created: '新建项目', checklist_done: '清单完成', compare_done: '对照完成',
  pages_processed: '解析页数', scanned_ratio_avg: '扫描页占比',
  orders_created: '下单数', orders_granted: '核销数', gmv_cny: 'GMV', subs_active: '生效订阅',
  token_prompt: '输入 tokens', token_output: '输出 tokens', token_cost_cny: 'LLM 成本',
  task_success_rate: '任务成功率', need_review_rate: '复核率',
  pending_backlog_peak: '积压峰值', job_fail_count: '任务失败次数',
}

const rows = ref<StatRowOut[]>([])
const dim = ref('')
const metric = ref('')
const range = ref<[string, string] | null>(null)
const loading = ref(false)
const exporting = ref(false)
const rolling = ref(false)

const metricOptions = computed(() =>
  Object.entries(METRICS).map(([value, label]) => ({ value, label })),
)

const trendMetric = computed(() => {
  if (!rows.value.length) return ''
  return rows.value[0].metric
})

const trendPoints = computed(() => {
  // 单一指标序列才出趋势图（混合查询不渲染）
  const first = rows.value[0]
  if (!first) return []
  if (rows.value.some((r) => r.metric !== first.metric || r.dim !== first.dim)) return []
  return rows.value.map((r) => ({ label: r.stat_date.slice(5), value: Number(r.value_num) }))
})

async function reload() {
  loading.value = true
  try {
    rows.value = await listStats({
      dim: dim.value || undefined,
      metric: metric.value || undefined,
      from: range.value?.[0],
      to: range.value?.[1],
    })
  } catch (e) {
    notifyApiError(e, '统计加载失败')
  } finally {
    loading.value = false
  }
}

async function onExport() {
  exporting.value = true
  try {
    const blob = await exportStatsCsv({
      dim: dim.value || undefined,
      metric: metric.value || undefined,
      from: range.value?.[0],
      to: range.value?.[1],
    })
    saveBlob(blob, 'stats-daily.csv')
  } catch (e) {
    notifyApiError(e, '导出失败')
  } finally {
    exporting.value = false
  }
}

async function onRollup() {
  rolling.value = true
  try {
    const r = await manualRollup()
    ElMessage.success(`已补算：${JSON.stringify(r)}`)
    void reload()
  } catch (e) {
    notifyApiError(e, '补算失败')
  } finally {
    rolling.value = false
  }
}

onMounted(reload)
</script>

<style scoped lang="less">
.mt {
  margin-top: 16px;
}

.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.dims {
  font-size: @fs-xs;
  color: @c-text-muted;
  word-break: break-all;
}
</style>
