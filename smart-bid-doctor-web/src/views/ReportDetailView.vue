<!-- 报告详情（02 §6.2）：report_data 结构化渲染（清单/对照两形态）+ 免责声明确认 + 导出 -->
<template>
  <div class="page">
    <header class="page-head">
      <div class="back-link-wrap">
        <router-link class="back-link" :to="`/projects/${report?.project_id ?? ''}`">
          ← 返回项目
        </router-link>
      </div>
      <div>
        <p class="page-eyebrow">Report</p>
        <h1 class="page-title">
          {{ report?.kind === 'comparison' ? '对照检查报告' : '废标风险检查清单' }}
          <el-tag v-if="report" size="small" class="kind-tag">#{{ report.id }}</el-tag>
        </h1>
        <p class="page-desc">
          {{ generatedAt }} 生成 · 本报告由 AI 辅助生成，结论仅供人工复核参考
        </p>
      </div>
      <div class="page-actions">
        <el-button v-if="report && !report.disclaimer_ack" @click="onAck">确认免责声明</el-button>
        <el-button v-else type="primary" :loading="exporting" @click="onExport">
          导出报告
        </el-button>
      </div>
    </header>

    <template v-if="report">
      <div class="cascade-in">
        <!-- 统计卡 -->
        <el-row :gutter="16">
          <el-col v-for="s in statCards" :key="s.label" :xs="8" :md="6">
            <el-card class="lift-card stat-card" :class="s.tone">
              <p class="stat-value num">{{ s.value }}</p>
              <p class="stat-label">{{ s.label }}</p>
            </el-card>
          </el-col>
        </el-row>

        <el-alert
          v-if="!report.disclaimer_ack"
          class="mt"
          type="warning"
          :closable="false"
          show-icon
          title="查看或导出前请确认免责声明：本报告由 AI 辅助生成，不构成「保证不废标」承诺，高危项须人工确认。"
        />

        <!-- 清单形态 -->
        <template v-if="report.kind === 'checklist'">
          <el-alert v-for="(n, i) in notes" :key="i" class="mt" type="info" :closable="false" :title="n" />
          <el-card class="lift-card mt">
            <template #header>
              <div class="panel-head">
                <div class="panel-head-main">
                  <span class="panel-title">检查条款</span>
                  <span class="panel-count num">{{ items.length }}</span>
                </div>
              </div>
            </template>
            <el-table :data="items" size="large" empty-text="暂无条款（抽取引擎接入后自动出数）">
              <el-table-column prop="code" label="编号" width="110" />
              <el-table-column label="分类" width="120">
                <template #default="{ row }">
                  {{ CHECK_CATEGORY_LABELS[row.category as CheckCategory] ?? row.category }}
                </template>
              </el-table-column>
              <el-table-column prop="requirement" label="要求" min-width="240" show-overflow-tooltip />
              <el-table-column label="★" width="60">
                <template #default="{ row }">
                  <span v-if="row.is_mandatory" class="star">★</span>
                  <span v-else>—</span>
                </template>
              </el-table-column>
              <el-table-column prop="ref_page" label="原文页" width="90" />
            </el-table>
          </el-card>
        </template>

        <!-- 对照形态 -->
        <template v-else>
          <el-card class="lift-card mt">
            <template #header>
              <div class="panel-head">
                <div class="panel-head-main">
                  <span class="panel-title">逐条判定</span>
                  <span class="panel-count num">{{ compItems.length }}</span>
                </div>
              </div>
            </template>
            <el-table :data="compItems" size="large" empty-text="暂无判定（对照引擎 M2 接入）">
              <el-table-column label="级别" width="90">
                <template #default="{ row }">
                  <el-tag
                    :type="row.level === 'red' ? 'danger' : row.level === 'yellow' ? 'warning' : 'success'"
                    size="small"
                  >
                    {{ row.level }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="code" label="条款" width="110" />
              <el-table-column prop="requirement" label="要求" min-width="220" show-overflow-tooltip />
              <el-table-column prop="verdict" label="判定" width="110" />
              <el-table-column prop="reason" label="理由" min-width="240" show-overflow-tooltip />
              <el-table-column label="证据页" width="90">
                <template #default="{ row }">{{ row.bid_ref_page ?? '—' }}</template>
              </el-table-column>
            </el-table>
          </el-card>
        </template>

        <el-card class="lift-card mt">
          <p class="disclaimer">{{ disclaimer }}</p>
        </el-card>
      </div>
    </template>

    <el-skeleton v-else-if="loading" :rows="6" animated class="mt" />
    <el-empty v-else description="报告不存在或已随项目删除" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ackReport, getReport } from '@/api/projects'
import { downloadWithProgress, notifyApiError } from '@/api/client'
import { CHECK_CATEGORY_LABELS } from '@/constants/enums'
import type { CheckCategory } from '@/constants/enums'
import type { ReportOut } from '@/types'
import { formatDate } from '@/utils/format'

interface ChecklistItem {
  code: string
  category: string
  requirement: string
  raw_text: string
  ref_page: number
  is_mandatory: boolean
  check_hint?: string | null
}

interface ComparisonItem {
  code: string | null
  requirement: string | null
  verdict: string
  level: string
  reason: string
  bid_ref_page: number | null
}

const route = useRoute()
const router = useRouter()
const report = ref<ReportOut | null>(null)
const loading = ref(true)
const exporting = ref(false)

const data = computed(() => (report.value?.report_data ?? {}) as Record<string, unknown>)
const stats = computed(() => (data.value.stats ?? {}) as Record<string, unknown>)
const items = computed(() => (data.value.items ?? []) as ChecklistItem[])
const compItems = computed(() => (data.value.items ?? []) as ComparisonItem[])
const notes = computed(() => (data.value.notes ?? []) as string[])
const disclaimer = computed(() =>
  (data.value.disclaimer as string) ?? '本报告由 AI 辅助生成，仅供人工复核参考。',
)
const generatedAt = computed(() => {
  const v = data.value.generated_at_bj as string | undefined
  return v ?? (report.value ? formatDate(report.value.created_at) : '—')
})

const statCards = computed(() => {
  if (report.value?.kind === 'comparison') {
    return [
      { label: '红色·高风险', value: Number(stats.value.red ?? 0), tone: 'tone-danger' },
      { label: '黄色·待确认', value: Number(stats.value.yellow ?? 0), tone: 'tone-warn' },
      { label: '绿色·基本满足', value: Number(stats.value.green ?? 0), tone: 'tone-ok' },
      { label: '判定总数', value: Number(stats.value.total ?? 0), tone: '' },
    ]
  }
  return [
    { label: '条款总数', value: Number(stats.value.total ?? 0), tone: '' },
    { label: '★强制/否决项', value: Number(stats.value.mandatory ?? 0), tone: 'tone-danger' },
    { label: '五类分布', value: Object.keys(stats.value.by_category ?? {}).length, tone: '' },
  ]
})

async function load() {
  loading.value = true
  try {
    report.value = await getReport(Number(route.params.id))
  } catch (e) {
    report.value = null
    notifyApiError(e, '报告加载失败')
  } finally {
    loading.value = false
  }
}

async function onAck() {
  if (!report.value) return
  try {
    report.value = await ackReport(report.value.id)
    ElMessage.success('免责声明确认完成（留痕），可导出报告')
  } catch (e) {
    notifyApiError(e)
  }
}

async function onExport() {
  if (!report.value) return
  exporting.value = true
  try {
    const blob = await downloadWithProgress(`/reports/${report.value.id}/export`)
    const url = URL.createObjectURL(blob)
    window.open(url, '_blank') // HTML 报告新窗口打开，浏览器打印即 PDF
    setTimeout(() => URL.revokeObjectURL(url), 60_000)
  } catch (e) {
    notifyApiError(e, '导出失败')
  } finally {
    exporting.value = false
  }
}

onMounted(() => {
  void load()
  // 项目页跳转而来若缺少项目 id，返回链接兜底工作台
  if (!route.params.id) router.replace('/projects')
})
</script>

<style scoped lang="less">
.back-link-wrap {
  width: 100%;
}

.back-link {
  display: inline-block;
  margin-bottom: 6px;
  font-size: @fs-sm;
  color: @c-text-muted;
  text-decoration: none;
  transition: color @dur-fast @ease-out;

  &:hover {
    color: var(--app-accent);
  }
}

.kind-tag {
  margin-left: 8px;
  vertical-align: middle;
}

.mt {
  margin-top: 16px;
}

.stat-card {
  .stat-value {
    margin: 0;
    font-size: 24px;
    font-weight: 700;
  }

  .stat-label {
    margin: 4px 0 0;
    font-size: @fs-xs;
    color: @c-text-muted;
  }

  &.tone-ok .stat-value { color: @c-success; }
  &.tone-warn .stat-value { color: @c-warning; }
  &.tone-danger .stat-value { color: @c-danger; }
}

.star {
  color: @c-danger;
  font-weight: 700;
}

.disclaimer {
  margin: 0;
  font-size: @fs-xs;
  line-height: 1.8;
  color: @c-text-muted;
}
</style>
