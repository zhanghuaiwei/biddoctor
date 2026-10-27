<!-- 项目列表页（02 §9.2）：本人项目分页展示（统一 limit/offset）+ status 筛选 +
     新建（免费配额 402 时提示）+ 软删（不释放当月名额）。入口经 api/projects.ts 资源模块。 -->
<template>
  <div class="page">
    <el-card>
      <div class="head">
        <span class="head-title">检查项目</span>
        <el-button type="primary" @click="dialog = true">新建项目</el-button>
      </div>
      <el-table :data="items" v-loading="loading">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="name" label="项目名称" min-width="160" />
        <el-table-column label="行业" width="120">
          <template #default="{ row }">
            <el-tag size="small" :type="INDUSTRY_TAGS[row.industry as Industry] ?? 'info'">
              {{ INDUSTRY_LABELS[row.industry as Industry] ?? row.industry }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag size="small" :type="PROJECT_STATUS_TAGS[row.status as ProjectStatus] ?? 'info'">
              {{ PROJECT_STATUS_LABELS[row.status as ProjectStatus] ?? row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="更新时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="$router.push(`/projects/${row.id}`)">进入</el-button>
            <el-button size="small" type="danger" plain @click="remove(row as ProjectOut)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="pager">
        <el-pagination
          layout="total, prev, pager, next"
          :total="total"
          :page-size="pageSize"
          :current-page="page"
          @current-change="onPage"
        />
      </div>
    </el-card>

    <el-dialog v-model="dialog" title="新建项目" width="min(420px, 92vw)">
      <el-form label-position="top">
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
.head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;

  @media (max-width: @bp-sm) {
    flex-wrap: wrap;
  }
}

.head-title {
  font-weight: 700;
}

.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
