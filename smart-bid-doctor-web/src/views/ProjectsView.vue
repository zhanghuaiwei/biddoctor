<!-- 项目列表页（02 §9.2）：本人项目分页展示（统一 limit/offset）+ status 筛选 +
     新建（免费配额 402 时提示）+ 软删（不释放当月名额）。入口经 api/projects.ts 资源模块。 -->
<template>
  <div class="page">
    <header class="page-head">
      <div>
        <span class="page-eyebrow">Workspace</span>
        <h1 class="page-title">项目检查</h1>
        <p class="page-desc">上传招标与投标文件，AI 逐条比对废标风险，结论全程留痕可查。</p>
      </div>
      <div class="page-actions">
        <el-button type="primary" @click="dialog = true">
          <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true">
            <path d="M12 5v14M5 12h14" />
          </svg>
          新建项目
        </el-button>
      </div>
    </header>

    <el-card class="lift-card">
      <template #header>
        <div class="panel-head">
          <div class="panel-head-main">
            <span class="panel-title">全部项目</span>
            <span class="panel-count num">{{ total }}</span>
          </div>
          <span class="panel-hint">按更新时间倒序</span>
        </div>
      </template>

      <el-table v-if="loading || items.length" :data="items" v-loading="loading">
        <el-table-column label="编号" width="88">
          <template #default="{ row }">
            <span class="cell-id num">#{{ row.id }}</span>
          </template>
        </el-table-column>
        <el-table-column label="项目名称" min-width="200">
          <template #default="{ row }">
            <span class="cell-strong">{{ row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column label="行业" width="130">
          <template #default="{ row }">
            <el-tag size="small" effect="plain" :type="INDUSTRY_TAGS[row.industry as Industry] ?? 'info'">
              {{ INDUSTRY_LABELS[row.industry as Industry] ?? row.industry }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="126">
          <template #default="{ row }">
            <el-tag size="small" :type="PROJECT_STATUS_TAGS[row.status as ProjectStatus] ?? 'info'">
              <span class="tag-dot" />{{ PROJECT_STATUS_LABELS[row.status as ProjectStatus] ?? row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="更新时间" width="160">
          <template #default="{ row }">
            <span class="cell-muted num">{{ formatDateTime(row.updated_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click="$router.push(`/projects/${row.id}`)">
              进入
            </el-button>
            <el-button size="small" type="danger" link @click="remove(row as ProjectOut)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-else description="还没有检查项目，创建后可上传文件开始自查">
        <el-button type="primary" @click="dialog = true">创建第一个项目</el-button>
      </el-empty>

      <div v-if="total > pageSize" class="pager">
        <el-pagination
          layout="total, prev, pager, next"
          :total="total"
          :page-size="pageSize"
          :current-page="page"
          @current-change="onPage"
        />
      </div>
    </el-card>

    <el-dialog v-model="dialog" title="新建检查项目" width="min(440px, 92vw)">
      <el-form label-position="top" class="create-form">
        <el-form-item label="项目名称">
          <el-input v-model="form.name" placeholder="如：xx医院设备采购-2026-10" @keyup.enter="create" />
        </el-form-item>
        <el-form-item label="行业">
          <el-select v-model="form.industry" style="width: 100%">
            <el-option
              v-for="i in INDUSTRIES"
              :key="i"
              :label="INDUSTRY_LABELS[i]"
              :value="i"
              :disabled="i === 'medical'"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="create">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { createProject, deleteProject, listProjects } from '@/api/projects'
import { notifyApiError } from '@/api/client'
import {
  INDUSTRIES,
  INDUSTRY_LABELS,
  INDUSTRY_TAGS,
  PROJECT_STATUS_LABELS,
  PROJECT_STATUS_TAGS,
  type Industry,
  type ProjectStatus,
} from '@/constants/enums'
import { formatDateTime } from '@/utils/format'
import type { ProjectOut } from '@/types'

const items = ref<ProjectOut[]>([])
const loading = ref(false)
const dialog = ref(false)
const creating = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = 20
const form = reactive({ name: '', industry: 'general' })

async function load() {
  loading.value = true
  try {
    const res = await listProjects({ limit: pageSize, offset: (page.value - 1) * pageSize })
    items.value = res.items
    total.value = res.total
  } catch (e) {
    notifyApiError(e, '项目列表加载失败')
  } finally {
    loading.value = false
  }
}

function onPage(p: number) {
  page.value = p
  load()
}

async function create() {
  if (!form.name.trim()) return ElMessage.warning('请输入项目名称')
  creating.value = true
  try {
    await createProject({ name: form.name.trim(), industry: form.industry })
    dialog.value = false
    form.name = ''
    ElMessage.success('项目已创建')
    await load()
  } catch (e) {
    notifyApiError(e, '创建失败')
  } finally {
    creating.value = false
  }
}

async function remove(row: ProjectOut) {
  try {
    await ElMessageBox.confirm(`确认删除项目「${row.name}」？删除后本项目不再出现在列表。`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return // 用户取消
  }
  try {
    await deleteProject(row.id)
    ElMessage.success('已删除（当月免费名额不因删除释放）')
    await load()
  } catch (e) {
    notifyApiError(e, '删除失败')
  }
}

onMounted(load)
</script>

<style scoped lang="less">
.btn-icon {
  width: 15px;
  height: 15px;
  margin-right: 4px;
}

.cell-id {
  color: @c-text-muted;
  font-size: @fs-xs;
  letter-spacing: 0.02em;
}

.cell-strong {
  font-weight: 600;
  color: @c-text;
}

.cell-muted {
  color: @c-text-muted;
  font-size: @fs-xs;
}

.pager {
  margin-top: 18px;
  display: flex;
  justify-content: flex-end;
}

.create-form {
  padding-top: 4px;
}
</style>
