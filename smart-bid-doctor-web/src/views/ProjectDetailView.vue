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

    <!-- 流程引导：静态三步说明（不引入额外状态判断，避免误导当前进度） -->
    <div class="step-bar cascade-in">
      <div class="step">
        <span class="step-index num">01</span>
        <div>
          <strong>上传双文件</strong>
          <p>招标文件 + 投标文件（PDF）</p>
        </div>
      </div>
      <span class="step-line" aria-hidden="true" />
      <div class="step">
        <span class="step-index num">02</span>
        <div>
          <strong>等待解析</strong>
          <p>自动抽取页数、条款与风险点</p>
        </div>
      </div>
      <span class="step-line" aria-hidden="true" />
      <div class="step">
        <span class="step-index num">03</span>
        <div>
          <strong>发起对照</strong>
          <p>逐条比对并生成废标结论</p>
        </div>
      </div>
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
        <el-button type="primary" @click="genChecklist">生成废标条款清单</el-button>
        <el-button type="danger" plain @click="startCompare">发起双文件对照（消耗 1 次）</el-button>
        <el-button @click="refreshDocs">刷新状态</el-button>
      </div>
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

      <div v-if="activeTask" class="task-progress">
        <div class="task-meta">
          <span class="task-title num">解析任务 #{{ activeTask.id }}</span>
          <span class="task-status">{{ TASK_STATUS_LABELS[activeTask.status] }}</span>
        </div>
        <el-progress :percentage="activeTask.progress" :stroke-width="8" />
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
        description="暂无清单数据（清单生成引擎 M1 接入，上传招标文件后自动生成）"
        :image-size="72"
      />
    </el-card>
  </div>

  <el-empty v-else-if="loadFailed" description="项目不存在或已被删除" class="notfound-empty">
    <el-button type="primary" @click="$router.push('/projects')">返回项目列表</el-button>
  </el-empty>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { ApiError, notifyApiError } from '@/api/client'
import {
  getProject,
  getTask,
  listCheckItems,
  listDocuments,
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
  TASK_STATUS_LABELS,
  type CheckCategory,
  type DocumentRole,
  type ParseStatus,
} from '@/constants/enums'
import { formatDateTime } from '@/utils/format'
import { confirmAction } from '@/utils/confirm'
import type { CheckItemOut, DocumentItem, ProjectOut, TaskOut } from '@/types'

const route = useRoute()
const pid = computed(() => Number(route.params.id))

const project = ref<ProjectOut | null>(null)
const docs = ref<DocumentItem[]>([])
const checkItems = ref<CheckItemOut[]>([])
const stats = ref<Record<string, number>>({})
const activeTask = ref<TaskOut | null>(null)
const loadFailed = ref(false)
const categoryFilter = ref<CheckCategory | ''>('')

const filteredItems = computed(() =>
  categoryFilter.value ? checkItems.value.filter((i) => i.category === categoryFilter.value) : checkItems.value,
)

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
  try {
    await startChecklistReport(pid.value)
  } catch (e) {
    // 501 NOT_IMPLEMENTED 为引擎未接入的预期态，提示降级为 warning 而非 error
    if (e instanceof ApiError && e.code === 'NOT_IMPLEMENTED') ElMessage.warning(e.message)
    else notifyApiError(e)
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
  loadFailed.value = false
  await loadProject()
  if (!loadFailed.value) {
    await Promise.all([refreshDocs(), loadCheckItems()])
    if (docs.value.some((d) => PARSE_BUSY_STATUSES.includes(d.parse_status))) polling.start()
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
}

.step-line {
  flex: 0 0 32px;
  height: 1px;
  background: @c-line;

  @media (max-width: @bp-md) {
    display: none;
  }
}

// ---- 面板 ----
.block {
  margin-bottom: 20px;
}

.upload-row {
  display: flex;
  gap: 24px;
  flex-wrap: wrap;

  @media (max-width: @bp-md) {
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
  font-size: @fs-xs;
  color: @c-text-sub;
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

.notfound-empty {
  padding-top: 12vh;
}
</style>
