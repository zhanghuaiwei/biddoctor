<!-- 项目工作台（02 §9.2–§9.4）：核心业务页面。
     主线：招标 PDF 上传（UploadSlot）→ 解析进度轮询（usePolling + documents/{did}/status，
     终态自动停）→ 对照发起（需双文件就绪，402 引导买次数包）→ 对照结果/清单查看（M1 引擎
     接入前清单生成/导出为 501，前端按 NOT_IMPLEMENTED 错误码提示）。 -->
<template>
  <div class="page" v-if="project">
    <el-card class="block">
      <div class="head">
        <div>
          <b class="proj-name">{{ project.name }}</b>
          <el-tag size="small" class="proj-status" :type="PROJECT_STATUS_TAGS[project.status]">
            {{ PROJECT_STATUS_LABELS[project.status] }}
          </el-tag>
        </div>
        <el-button @click="$router.push('/projects')">返回列表</el-button>
      </div>
    </el-card>

    <el-card class="block" :header="`文件上传（PDF，≤${MAX_UPLOAD_MB}MB / ≤${MAX_PAGES}页）`">
      <div class="upload-row">
        <UploadSlot :project-id="pid" role="tender" title="招标文件（tender）" @uploaded="onUploaded" />
        <UploadSlot :project-id="pid" role="bid" title="投标文件（bid）" @uploaded="onUploaded" />
      </div>
    </el-card>

    <el-card class="block" header="已上传文件">
      <el-table :data="docs">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column label="类型" width="100">
          <template #default="{ row }">{{ DOCUMENT_ROLE_LABELS[row.role as DocumentRole] }}</template>
        </el-table-column>
        <el-table-column prop="orig_name" label="文件名" min-width="140" />
        <el-table-column prop="total_pages" label="页数" width="80" />
        <el-table-column label="解析状态" width="120">
          <template #default="{ row }">
            <el-tag size="small" :type="PARSE_STATUS_TAGS[row.parse_status as ParseStatus] ?? 'info'">
              {{ PARSE_STATUS_LABELS[row.parse_status as ParseStatus] ?? row.parse_status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="提示" min-width="200">
          <template #default="{ row }">
            <span class="warn-text">{{ (row.parse_warnings || [])[0] }}</span>
          </template>
        </el-table-column>
      </el-table>
      <div v-if="activeTask" class="task-progress">
        <span class="warn-text">解析任务 #{{ activeTask.id }}：{{ TASK_STATUS_LABELS[activeTask.status] }}</span>
        <el-progress :percentage="activeTask.progress" :stroke-width="8" class="task-bar" />
      </div>
      <div class="actions">
        <el-button type="primary" @click="genChecklist">生成废标条款清单</el-button>
        <el-button type="danger" plain @click="startCompare">发起双文件对照（消耗 1 次）</el-button>
        <el-button @click="refreshDocs">刷新状态</el-button>
      </div>
    </el-card>

    <el-card header="废标条款清单">
      <template #header>
        <div class="checklist-head">
          <span>废标条款清单</span>
          <el-select v-model="categoryFilter" clearable placeholder="全部分类" size="small" class="cat-filter">
            <el-option
              v-for="c in CHECK_CATEGORIES"
              :key="c"
              :label="`${CHECK_CATEGORY_LABELS[c]}（${stats[c] ?? 0}）`"
              :value="c"
            />
          </el-select>
        </div>
      </template>
      <el-table :data="filteredItems">
        <el-table-column prop="code" label="编号" width="110" />
        <el-table-column label="类别" width="130">
          <template #default="{ row }">{{ CHECK_CATEGORY_LABELS[row.category as CheckCategory] }}</template>
        </el-table-column>
        <el-table-column prop="requirement" label="要求" min-width="220" />
        <el-table-column label="页码" width="80">
          <template #default="{ row }">第 {{ row.ref_page }} 页</template>
        </el-table-column>
      </el-table>
      <el-empty
        v-if="!checkItems.length"
        description="暂无清单数据（清单生成引擎 M1 接入，上传招标文件后自动生成）"
        :image-size="60"
      />
    </el-card>
  </div>
  <el-empty v-else-if="loadFailed" description="项目不存在或已被删除">
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
.block {
  margin-bottom: 16px;
}

.head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;

  @media (max-width: @bp-sm) {
    flex-wrap: wrap;
  }
}

.proj-name {
  font-size: 16px;
}

.proj-status {
  margin-left: 8px;
}

.upload-row {
  display: flex;
  gap: 32px;
  flex-wrap: wrap;

  @media (max-width: @bp-md) {
    gap: 16px;
  }
}

.actions {
  margin-top: 16px;
  display: flex;
  gap: 12px;

  @media (max-width: @bp-sm) {
    flex-wrap: wrap;

    :deep(.el-button) {
      margin-left: 0;
    }
  }
}

.task-progress {
  margin-top: 12px;
  max-width: 420px;
}

.task-bar {
  margin-top: 4px;
}

.warn-text {
  color: #909399;
  font-size: 12px;
}

.checklist-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.cat-filter {
  width: 200px;
}
</style>
