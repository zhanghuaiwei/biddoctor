<!-- 项目工作台（02 §9.2–§9.4）：核心业务页面。
     主线：招标 PDF 上传（UploadSlot）→ 解析进度轮询（usePolling + documents/{did}/status，
     终态自动停）→ 对照发起（需双文件就绪，402 引导买次数包）→ 对照结果/清单查看（M1 引擎
     接入前清单生成/导出为 501，前端按 NOT_IMPLEMENTED 错误码提示）。 -->
<template>
  <div v-if="project" class="page">
    <header class="page-head detail-head">
      <div class="detail-title-wrap">
        <button type="button" class="back-link" @click="$router.push('/projects')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M15 18l-6-6 6-6" />
          </svg>
          返回项目列表
        </button>
        <div class="title-row">
          <h1 class="page-title">{{ project.name }}</h1>
          <el-tag size="small" :type="PROJECT_STATUS_TAGS[project.status]">
            <span class="tag-dot" />{{ PROJECT_STATUS_LABELS[project.status] }}
          </el-tag>
        </div>
        <p class="page-desc num">项目编号 #{{ project.id }} · 最后更新 {{ formatDateTime(project.updated_at) }}</p>
      </div>
    </header>

    <!-- 概览指标：文件 / 解析中 / 条款 / 报告，全部取自列表接口，不用额外请求 -->
    <div class="stat-strip cascade-in">
      <div v-for="s in statItems" :key="s.key" class="stat" :class="`stat--${s.tone}`">
        <span class="stat-icon" v-html="s.icon" aria-hidden="true" />
        <div class="stat-body">
          <strong class="stat-value num">{{ s.value }}</strong>
          <span class="stat-label">{{ s.label }}</span>
        </div>
        <span class="stat-note">{{ s.note }}</span>
      </div>
    </div>

    <!-- 流程引导：状态由真实数据推导（上传齐 → 双文件解析完成 → 有报告），当前步呼吸高亮 -->
    <div class="step-bar cascade-in">
      <template v-for="(s, i) in steps" :key="s.key">
        <span v-if="i" class="step-line" :class="{ 'is-done': s.done }" aria-hidden="true" />
        <div class="step" :class="{ 'is-done': s.done, 'is-active': s.active }">
          <span class="step-index num">
            <svg v-if="s.done" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M5 12.5l4.5 4.5L19 7" />
            </svg>
            <template v-else>{{ s.index }}</template>
          </span>
          <div>
            <strong>{{ s.title }}</strong>
            <p>{{ s.desc }}</p>
          </div>
        </div>
      </template>
    </div>

    <el-card class="block lift-card">
      <template #header>
        <div class="panel-head">
          <div class="panel-head-main">
            <span class="panel-title">文件上传</span>
            <span class="panel-count">2 个槽位</span>
          </div>
          <span class="panel-hint">PDF · ≤{{ MAX_UPLOAD_MB }}MB · ≤{{ MAX_PAGES }} 页</span>
        </div>
      </template>
      <div class="upload-row">
        <UploadSlot :project-id="pid" role="tender" title="招标文件（tender）" @uploaded="onUploaded" />
        <UploadSlot :project-id="pid" role="bid" title="投标文件（bid）" @uploaded="onUploaded" />
      </div>
      <div class="actions">
        <el-button type="primary" :disabled="!canChecklist" @click="genChecklist">生成废标条款清单</el-button>
        <el-button type="danger" plain :disabled="!canCompare" @click="startCompare">
          发起双文件对照（消耗 1 次）
        </el-button>
        <el-button @click="refreshDocs">刷新状态</el-button>
      </div>
      <p v-if="actionHint" class="action-hint">{{ actionHint }}</p>
    </el-card>

    <el-card class="block lift-card">
      <template #header>
        <div class="panel-head">
          <div class="panel-head-main">
            <span class="panel-title">已上传文件</span>
            <span class="panel-count num">{{ docs.length }}</span>
          </div>
        </div>
      </template>

      <el-table v-if="docs.length" :data="docs">
        <el-table-column label="编号" width="88">
          <template #default="{ row }">
            <span class="cell-id num">#{{ row.id }}</span>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="120">
          <template #default="{ row }">
            <el-tag size="small" effect="plain" :type="DOCUMENT_ROLE_TAGS[row.role as DocumentRole]">
              {{ DOCUMENT_ROLE_LABELS[row.role as DocumentRole] }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="orig_name" label="文件名" min-width="180">
          <template #default="{ row }">
            <span class="cell-file">{{ row.orig_name }}</span>
          </template>
        </el-table-column>
        <el-table-column label="页数" width="90">
          <template #default="{ row }">
            <span class="num cell-muted">{{ row.total_pages ?? '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="解析状态" width="130">
          <template #default="{ row }">
            <el-tag size="small" :type="PARSE_STATUS_TAGS[row.parse_status as ParseStatus] ?? 'info'">
              <span class="tag-dot" />{{ PARSE_STATUS_LABELS[row.parse_status as ParseStatus] ?? row.parse_status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="提示" min-width="200">
          <template #default="{ row }">
            <span class="warn-text">{{ (row.parse_warnings || [])[0] }}</span>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else description="尚未上传文件，先上传招标文件即可开始解析" :image-size="72" />

      <div v-if="activeTask" class="task-progress" :class="`is-${activeTask.status}`">
        <div class="task-meta">
          <span class="task-title num">
            <span class="task-dot" aria-hidden="true" />解析任务 #{{ activeTask.id }}
          </span>
          <span class="task-status">
            {{ TASK_STATUS_LABELS[activeTask.status] }} · {{ activeTask.progress }}%
          </span>
        </div>
        <el-progress :percentage="activeTask.progress" :stroke-width="8" :show-text="false" />
      </div>
    </el-card>

    <el-card class="lift-card">
      <template #header>
        <div class="panel-head">
          <div class="panel-head-main">
            <span class="panel-title">废标条款清单</span>
            <span class="panel-count num">{{ filteredItems.length }}</span>
          </div>
          <span class="panel-hint">按分类筛选</span>
        </div>
      </template>

      <div class="chips" role="group" aria-label="条款分类筛选">
        <button
          type="button"
          class="chip"
          :class="{ 'is-active': !categoryFilter }"
          @click="categoryFilter = ''"
        >
          全部<span class="chip-num num">{{ checkItems.length }}</span>
        </button>
        <button
          v-for="c in CHECK_CATEGORIES"
          :key="c"
          type="button"
          class="chip"
          :class="{ 'is-active': categoryFilter === c }"
          @click="categoryFilter = c"
        >
          {{ CHECK_CATEGORY_LABELS[c] }}<span class="chip-num num">{{ stats[c] ?? 0 }}</span>
        </button>
      </div>

      <el-table v-if="filteredItems.length" :data="filteredItems">
        <el-table-column label="编号" width="120">
          <template #default="{ row }">
            <span class="num cell-mono">{{ row.code }}</span>
          </template>
        </el-table-column>
        <el-table-column label="类别" width="140">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ CHECK_CATEGORY_LABELS[row.category as CheckCategory] }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="requirement" label="要求" min-width="240">
          <template #default="{ row }">
            <span class="cell-strong">{{ row.requirement }}</span>
          </template>
        </el-table-column>
        <el-table-column label="页码" width="100">
          <template #default="{ row }">
            <span class="num cell-muted">第 {{ row.ref_page }} 页</span>
          </template>
        </el-table-column>
      </el-table>

      <el-empty
        v-else
        description="暂无清单数据（抽取引擎接入后自动出数）；可先点击「生成废标条款清单」产出报告框架"
        :image-size="72"
      />
    </el-card>

    <el-card v-if="reports.length" class="lift-card">
      <template #header>
        <div class="panel-head">
          <div class="panel-head-main">
            <span class="panel-title">检查报告</span>
            <span class="panel-count num">{{ reports.length }}</span>
          </div>
          <span class="panel-hint">生成后原件按阅后即焚策略回收，报告长期留存</span>
        </div>
      </template>
      <el-table :data="reports" class="report-table" @row-click="openReport">
        <el-table-column prop="id" label="报告" width="100">
          <template #default="{ row }">
            <span class="num cell-id">#{{ row.id }}</span>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="130">
          <template #default="{ row }">
            <el-tag size="small" effect="plain" :type="row.kind === 'comparison' ? 'warning' : 'primary'">
              {{ REPORT_KIND_LABELS[row.kind as ReportKind] ?? row.kind }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="生成时间" min-width="180">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click.stop="openReport(row)">查看报告</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>

  <!-- 首屏骨架：项目/文件/清单/报告并发拉取期间避免白屏闪空态 -->
  <div v-else-if="loading" class="page">
    <el-skeleton animated :rows="2" class="skeleton-head" />
    <div class="stat-strip">
      <el-skeleton v-for="i in 4" :key="i" animated class="skeleton-stat">
        <template #template>
          <el-skeleton-item variant="rect" style="height: 76px; border-radius: 12px" />
        </template>
      </el-skeleton>
    </div>
    <el-skeleton animated :rows="7" class="skeleton-block" />
  </div>

  <el-empty v-else-if="loadFailed" description="项目不存在或已被删除" class="notfound-empty">
    <el-button type="primary" @click="$router.push('/projects')">返回项目列表</el-button>
  </el-empty>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ApiError, notifyApiError } from '@/api/client'
import {
  getProject,
  getTask,
  listCheckItems,
  listDocuments,
  listReports,
  startChecklistReport,
  startCompare as startCompareApi,
} from '@/api/projects'
import UploadSlot from '@/components/UploadSlot.vue'
import { usePolling } from '@/composables/usePolling'
import {
  CHECK_CATEGORIES,
  CHECK_CATEGORY_LABELS,
  DOCUMENT_ROLE_LABELS,
  DOCUMENT_ROLE_TAGS,
  MAX_PAGES,
  MAX_UPLOAD_MB,
  PARSE_BUSY_STATUSES,
  PARSE_STATUS_LABELS,
  PARSE_STATUS_TAGS,
  PROJECT_STATUS_LABELS,
  PROJECT_STATUS_TAGS,
  REPORT_KIND_LABELS,
  TASK_STATUS_LABELS,
  type CheckCategory,
  type DocumentRole,
  type ParseStatus,
  type ReportKind,
} from '@/constants/enums'
import { formatDateTime } from '@/utils/format'
import { confirmAction } from '@/utils/confirm'
import type { CheckItemOut, DocumentItem, ProjectOut, ReportOut, TaskOut } from '@/types'

const route = useRoute()
const router = useRouter()
const pid = computed(() => Number(route.params.id))

const project = ref<ProjectOut | null>(null)
const docs = ref<DocumentItem[]>([])
const checkItems = ref<CheckItemOut[]>([])
const stats = ref<Record<string, number>>({})
const activeTask = ref<TaskOut | null>(null)
const loadFailed = ref(false)
const categoryFilter = ref<CheckCategory | ''>('')
const reports = ref<ReportOut[]>([])
const checklistTaskId = ref<number | null>(null)
const loading = ref(true)

const latestReportId = computed(() => reports.value[0]?.id ?? null)

const filteredItems = computed(() =>
  categoryFilter.value ? checkItems.value.filter((i) => i.category === categoryFilter.value) : checkItems.value,
)

const parsingCount = computed(() => docs.value.filter((d) => PARSE_BUSY_STATUSES.includes(d.parse_status)).length)
const tenderDoc = computed(() => docs.value.find((d) => d.role === 'tender') ?? null)
const bidDoc = computed(() => docs.value.find((d) => d.role === 'bid') ?? null)

// 按钮可用性与后端前置校验同口径（check.py：招标解析 done/need_review 可生成清单；compare_svc：双文件均 done 才可对照）
const canChecklist = computed(
  () => !!tenderDoc.value && ['done', 'need_review'].includes(tenderDoc.value.parse_status),
)
const canCompare = computed(
  () => tenderDoc.value?.parse_status === 'done' && bidDoc.value?.parse_status === 'done',
)

/** 下一步缺什么：写在按钮下方，避免用户点了才收到 400 */
const actionHint = computed(() => {
  if (!tenderDoc.value) return '先上传招标文件；解析完成后可生成清单，双文件就绪后可发起对照'
  if (parsingCount.value > 0) return '文件解析中，完成后按钮自动可用（本页每 3 秒自动刷新）'
  if (!bidDoc.value) return '还需上传投标文件，才能发起双文件对照'
  if (!canChecklist.value) return '招标文件解析未通过，请查看下方「已上传文件」的提示后重新上传'
  if (!canCompare.value) return '投标文件尚未解析完成，稍候即可发起双文件对照'
  return ''
})

/** 三步进度：由真实数据推导，当前步高亮（不是静态说明文案） */
const steps = computed(() => {
  const flags = [!!tenderDoc.value && !!bidDoc.value, canCompare.value, reports.value.length > 0]
  const activeIndex = flags.indexOf(false)
  const base = [
    { key: 'upload', index: '01', title: '上传双文件', desc: '招标文件 + 投标文件（PDF）' },
    { key: 'parse', index: '02', title: '等待解析', desc: '自动抽取页数、条款与风险点' },
    { key: 'compare', index: '03', title: '发起对照', desc: '逐条比对并生成废标结论' },
  ]
  return base.map((s, i) => ({ ...s, done: flags[i], active: i === activeIndex }))
})

// 内联 SVG（不引图标库）：与全站线性图标同风格
const ICONS = {
  docs: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3h8l4 4v14H6z"/><path d="M14 3v5h5"/><path d="M9 13h6M9 17h4"/></svg>',
  parsing: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M20 12a8 8 0 1 1-2.3-5.6"/><path d="M20 4v5h-5"/></svg>',
  items: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M4 6h16M4 12h16M4 18h10"/><path d="M17 17l2 2 3-4"/></svg>',
  reports:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M5 4h14v16H5z"/><path d="M9 9h6M9 13h6"/><path d="M9 17l1.5 1.5L14 15"/></svg>',
}

const statItems = computed(() => [
  { key: 'docs', label: '已上传文件', value: docs.value.length, note: '2 槽位', tone: 'plain', icon: ICONS.docs },
  {
    key: 'parsing',
    label: '解析中',
    value: parsingCount.value,
    note: parsingCount.value ? '进行中' : '空闲',
    tone: parsingCount.value ? 'busy' : 'plain',
    icon: ICONS.parsing,
  },
  {
    key: 'items',
    label: '清单条款',
    value: checkItems.value.length,
    note: checkItems.value.length ? '已生成' : '待生成',
    tone: 'plain',
    icon: ICONS.items,
  },
  {
    key: 'reports',
    label: '检查报告',
    value: reports.value.length,
    note: reports.value.length ? '可查看' : '暂无',
    tone: 'plain',
    icon: ICONS.reports,
  },
])

// el-table 行数据为 Element 的 DefaultRow 类型，按通用记录接收后只取 id
function openReport(row: Record<string, unknown>) {
  void router.push(`/reports/${String(row.id)}`)
}

/** 文档表在途轮询：全部终态即停（usePolling 回调返回 false） */
const polling = usePolling(async () => {
  await refreshDocs()
  const busy = docs.value.some((d) => PARSE_BUSY_STATUSES.includes(d.parse_status))
  if (!busy && activeTask.value) {
    const t = await getTask(activeTask.value.id).catch(() => null)
    activeTask.value = t
  }
  return busy
}, 3000)

async function loadProject() {
  try {
    project.value = await getProject(pid.value)
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) loadFailed.value = true
    else notifyApiError(e, '项目加载失败')
  }
}

async function refreshDocs() {
  try {
    const res = await listDocuments(pid.value)
    docs.value = res.items
  } catch (e) {
    notifyApiError(e, '文件列表加载失败')
  }
}

async function loadCheckItems() {
  try {
    const res = await listCheckItems(pid.value)
    checkItems.value = res.items
    stats.value = res.stats
  } catch (e) {
    notifyApiError(e, '清单加载失败')
  }
}

function onUploaded() {
  refreshDocs()
  polling.start()
}

async function genChecklist() {
  const ok = await confirmAction(
    '将基于招标文件解析结果生成《废标风险检查清单》报告（生成后原件按阅后即焚策略回收）。继续？',
    { title: '生成检查清单', confirmText: '生成' },
  )
  if (!ok) return
  try {
    const res = await startChecklistReport(pid.value)
    checklistTaskId.value = res.task_id
    ElMessage.success(`清单报告任务已创建（task #${res.task_id}），生成中…`)
    reportPolling.start()
  } catch (e) {
    notifyApiError(e)
  }
}

/** 清单任务轮询：终态后拉报告并跳转报告详情 */
const reportPolling = usePolling(async () => {
  if (!checklistTaskId.value) return false
  const t = await getTask(checklistTaskId.value).catch(() => null)
  if (!t) return false
  activeTask.value = null
  if (t.status === 'succeeded') {
    checklistTaskId.value = null
    await loadReports()
    if (latestReportId.value) {
      ElMessage.success('清单报告已生成')
      void router.push(`/reports/${latestReportId.value}`)
    }
    return false
  }
  if (t.status === 'failed') {
    ElMessage.error(t.error_msg ?? '报告生成失败')
    checklistTaskId.value = null
    return false
  }
  return true
}, 2500)

async function loadReports() {
  try {
    const res = await listReports(pid.value, { limit: 10 })
    reports.value = res.items
  } catch {
    reports.value = []
  }
}

async function startCompare() {
  const ok = await confirmAction('本次对照将消耗 1 次对照次数，发起后不可撤回。', {
    title: '发起双文件对照',
    confirmText: '确认发起',
  })
  if (!ok) return
  try {
    const res = await startCompareApi(pid.value)
    ElMessage.success(`对照任务已创建（task #${res.task_id}），结果生成后可在本页查看`)
  } catch (e) {
    if (e instanceof ApiError && e.code === 'QUOTA_EXCEEDED') {
      ElMessage.warning('对照次数不足，请到「次数与订单」购买次数包')
      return
    }
    notifyApiError(e)
  }
}

watch(
  () => route.params.id,
  () => init(), // 同组件不同项目跳转：重跑加载（无需整页刷新）
)

async function init() {
  loading.value = true
  loadFailed.value = false
  try {
    await loadProject()
    if (!loadFailed.value) {
      await Promise.all([refreshDocs(), loadCheckItems(), loadReports()])
      if (docs.value.some((d) => PARSE_BUSY_STATUSES.includes(d.parse_status))) polling.start()
    }
  } finally {
    loading.value = false
  }
}

onMounted(init)
</script>

<style scoped lang="less">
.detail-title-wrap {
  min-width: 0;
}

.back-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 12px;
  padding: 0;
  border: none;
  background: none;
  font: inherit;
  font-size: @fs-sm;
  color: @c-text-muted;
  cursor: pointer;
  transition: color @dur-fast @ease-out;

  svg {
    width: 14px;
    height: 14px;
  }

  &:hover {
    color: @c-accent;
  }
}

.title-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

// ---- 概览指标 ----
.stat-strip {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 16px;

  @media (max-width: @bp-md) {
    grid-template-columns: repeat(2, 1fr);
  }
}

.stat {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 13px 15px;
  border: 1px solid @c-line-soft;
  border-radius: @radius-lg;
  background: @c-surface;
  box-shadow: @shadow-sm;
  transition:
    transform @dur-base @ease-out,
    box-shadow @dur-base @ease-out,
    border-color @dur-base @ease-out;

  &:hover {
    transform: translateY(-2px);
    border-color: var(--app-line);
    box-shadow: @shadow-md;
  }
}

.stat-icon {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: @radius;
  background: @c-accent-soft;
  color: @c-accent;

  :deep(svg) {
    width: 18px;
    height: 18px;
  }
}

.stat-body {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}

.stat-value {
  font-size: 22px;
  font-weight: 700;
  line-height: 1.1;
  color: @c-text;
}

.stat-label {
  font-size: @fs-xs;
  color: @c-text-muted;
}

.stat-note {
  margin-left: auto;
  padding: 2px 8px;
  border-radius: @radius-pill;
  background: @c-surface-alt;
  font-size: 10px;
  color: @c-text-muted;
}

// 解析中：图标呼吸 + 徽标强调，提示「页面在自动刷新」
.stat--busy {
  .stat-icon {
    animation: pulse-dot 2s @ease-out infinite;
  }

  .stat-note {
    background: @c-accent-soft;
    color: @c-accent;
    font-weight: 600;
  }
}

// ---- 流程引导 ----
.step-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
  padding: 16px 20px;
  border: 1px solid @c-line-soft;
  border-radius: @radius-lg;
  background: @c-surface;

  @media (max-width: @bp-md) {
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
  }
}

.step {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;

  strong {
    display: block;
    font-size: @fs-sm;
    color: @c-text;
  }

  p {
    margin: 2px 0 0;
    font-size: @fs-xs;
    color: @c-text-muted;
  }
}

.step-index {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: @c-accent-soft;
  color: @c-accent;
  font-size: @fs-xs;
  font-weight: 700;
  transition:
    background-color @dur-base @ease-out,
    color @dur-base @ease-out,
    box-shadow @dur-base @ease-out;

  svg {
    width: 14px;
    height: 14px;
  }
}

// 已完成：实心徽标打勾；进行中：强调色描边呼吸，焦点一眼可见
.step.is-done .step-index {
  background: color-mix(in srgb, var(--app-accent) 16%, transparent);
}

.step.is-active {
  .step-index {
    background: var(--app-accent);
    color: #fff;
    animation: step-pulse 2.4s @ease-out infinite;
  }

  strong {
    color: @c-accent;
  }
}

@keyframes step-pulse {
  0%,
  100% {
    box-shadow: 0 0 0 0 color-mix(in srgb, var(--app-accent) 34%, transparent);
  }

  50% {
    box-shadow: 0 0 0 6px color-mix(in srgb, var(--app-accent) 0%, transparent);
  }
}

.step-line {
  flex: 0 0 32px;
  height: 1px;
  background: @c-line;
  transition: background-color @dur-base @ease-out;

  // 已完成步骤之间的连接线点亮为强调色
  &.is-done {
    background: color-mix(in srgb, var(--app-accent) 50%, transparent);
  }

  @media (max-width: @bp-md) {
    display: none;
  }
}

// ---- 面板 ----
.block {
  margin-bottom: 20px;
}

// 两个上传槽等宽两列（grid 保证右槽不被长文件名撑偏），窄屏回落单列
.upload-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;

  @media (max-width: @bp-md) {
    grid-template-columns: 1fr;
    gap: 16px;
  }
}

.actions {
  margin-top: 20px;
  display: flex;
  gap: 10px;

  @media (max-width: @bp-sm) {
    flex-wrap: wrap;
  }
}

// 下一步缺什么（与按钮禁用同源，避免用户点完才收到 400）
.action-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 10px 0 0;
  font-size: @fs-xs;
  color: @c-text-muted;

  &::before {
    content: '';
    flex: none;
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: var(--app-accent);
    opacity: 0.7;
  }
}

.cell-id {
  color: @c-text-muted;
  font-size: @fs-xs;
}

.cell-file {
  color: @c-text;
  font-size: @fs-sm;
}

.cell-muted {
  color: @c-text-muted;
  font-size: @fs-xs;
}

.cell-mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: @fs-xs;
  color: @c-text-sub;
}

.cell-strong {
  color: @c-text;
  font-size: @fs-sm;
}

.warn-text {
  color: @c-text-muted;
  font-size: @fs-xs;
}

.task-progress {
  margin-top: 18px;
  padding: 12px 16px;
  border-radius: @radius;
  background: @c-surface-alt;
  max-width: 480px;
}

.task-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.task-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: @fs-xs;
  color: @c-text-sub;
}

// 状态点：在途呼吸，终态定色
.task-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: @c-accent;
  animation: pulse-dot 1.6s @ease-out infinite;
}

.task-progress.is-succeeded .task-dot {
  background: @c-success;
  animation: none;
}

.task-progress.is-failed .task-dot {
  background: @c-danger;
  animation: none;
}

.task-progress.is-need_review .task-dot {
  background: @c-warning;
  animation: none;
}

.task-status {
  font-size: @fs-xs;
  color: @c-accent;
  font-weight: 600;
}

// ---- 分类筛选 chips ----
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 14px;
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border: 1px solid @c-line;
  border-radius: @radius-pill;
  background: @c-surface;
  font: inherit;
  font-size: @fs-xs;
  color: @c-text-sub;
  cursor: pointer;
  transition:
    color @dur-fast @ease-out,
    border-color @dur-fast @ease-out,
    background-color @dur-fast @ease-out;

  &:hover {
    border-color: color-mix(in srgb, var(--app-accent) 55%, var(--app-line));
    color: @c-accent;
  }

  &.is-active {
    border-color: @c-accent;
    background: @c-accent-soft;
    color: @c-accent;
    font-weight: 600;
  }
}

.chip-num {
  padding: 0 5px;
  border-radius: @radius-pill;
  background: color-mix(in srgb, var(--app-text) 6%, transparent);
  font-size: 10px;
  line-height: 15px;
}

// ---- 报告表格：整行可点，悬停已是全局行底色 ----
.report-table :deep(.el-table__row) {
  cursor: pointer;
}

// ---- 首屏骨架 ----
.skeleton-head {
  margin-bottom: 18px;
}

.skeleton-stat {
  display: block;
}

.skeleton-block {
  margin-top: 16px;
}

.notfound-empty {
  padding-top: 12vh;
}
</style>
