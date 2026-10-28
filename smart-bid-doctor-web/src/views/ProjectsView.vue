<!-- 项目列表页（02 §9.2）：本人项目分页展示（统一 limit/offset）+ status 筛选 +
     新建（免费配额 402 时提示）+ 软删（不释放当月名额）。入口经 api/projects.ts 资源模块。 -->
<template>
  <div class="page">
    <PageHeader
      eyebrow="Workspace"
      title="项目检查"
      desc="上传招标与投标文件，AI 逐条比对废标风险，结论全程留痕可查。"
    >
      <template #actions>
        <el-button type="primary" @click="dialog = true">
          <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true">
            <path d="M12 5v14M5 12h14" />
          </svg>
          新建项目
        </el-button>
      </template>
    </PageHeader>

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
            <EnumTag :value="row.industry" :labels="INDUSTRY_LABELS" :tags="INDUSTRY_TAGS" plain />
          </template>
        </el-table-column>
        <el-table-column label="状态" width="126">
          <template #default="{ row }">
            <EnumTag :value="row.status" :labels="PROJECT_STATUS_LABELS" :tags="PROJECT_STATUS_TAGS" dot />
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

      <ListPager
        :total="total"
        :page="page"
        :page-size="pageSize"
        layout="total, prev, pager, next"
        hide-single
        @change="onPage"
      />
    </el-card>

    <OverlayPanel v-model="dialog" title="新建检查项目" desc="创建后上传招标与投标文件即可开始自查" content-size="sm">
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
    </OverlayPanel>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'

import { createProject, deleteProject, listProjects } from '@/api/projects'
import EnumTag from '@/components/EnumTag.vue'
import ListPager from '@/components/ListPager.vue'
import OverlayPanel from '@/components/OverlayPanel.vue'
import PageHeader from '@/components/PageHeader.vue'
import { useApiAction } from '@/composables/useApiAction'
import { usePagedList } from '@/composables/usePagedList'
import { INDUSTRIES, INDUSTRY_LABELS, INDUSTRY_TAGS, PROJECT_STATUS_LABELS, PROJECT_STATUS_TAGS } from '@/constants/enums'
import { formatDateTime } from '@/utils/format'
import { confirmAction } from '@/utils/confirm'
import type { ProjectOut } from '@/types'

const { items, total, page, pageSize, loading, reload: load, onPage } = usePagedList<ProjectOut>(
  ({ limit, offset }) => listProjects({ limit, offset }),
  { errorText: '项目列表加载失败' },
)

const dialog = ref(false)
const form = reactive({ name: '', industry: 'general' })

const { pending: creating, run: runCreate } = useApiAction('创建失败')
const { run: runRemove } = useApiAction('删除失败')

async function create() {
  if (!form.name.trim()) return ElMessage.warning('请输入项目名称')
  const res = await runCreate(() =>
    createProject({ name: form.name.trim(), industry: form.industry }),
  )
  if (!res.ok) return
  dialog.value = false
  form.name = ''
  ElMessage.success('项目已创建')
  await load()
}

async function remove(row: ProjectOut) {
  const ok = await confirmAction('删除后本项目不再出现在列表，当月免费名额不因删除释放。', {
    title: `删除项目「${row.name}」`,
    confirmText: '删除',
    danger: true,
  })
  if (!ok) return
  const res = await runRemove(() => deleteProject(row.id))
  if (!res.ok) return
  ElMessage.success('已删除（当月免费名额不因删除释放）')
  await load()
}
</script>

<style scoped lang="less">
.btn-icon {
  width: 15px;
  height: 15px;
  margin-right: 4px;
}

.create-form {
  padding-top: 4px;
}
</style>
