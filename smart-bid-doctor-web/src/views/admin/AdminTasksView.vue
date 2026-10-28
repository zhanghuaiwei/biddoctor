<!-- 任务巡检（05 §4.1）：队列任务只读巡检（状态/类型筛选 + 进度与错误定位） -->
<template>
  <div class="page">
    <PageHeader eyebrow="Inspection" title="任务巡检" desc="异步任务队列巡检：定位卡住/失败任务与错误码（tasks 状态机留痕）">
      <template #actions>
        <el-button :loading="loading" @click="reload">刷新</el-button>
      </template>
    </PageHeader>

    <el-card class="lift-card cascade-in">
      <template #header>
        <div class="panel-head">
          <div class="panel-head-main">
            <span class="panel-title">任务列表</span>
            <span class="panel-count num">{{ total }}</span>
          </div>
          <div class="panel-tools">
            <el-select v-model="status" clearable placeholder="全部状态" style="width: 140px" @change="reload">
              <el-option v-for="(label, v) in TASK_STATUS_LABELS" :key="v" :label="label" :value="v" />
            </el-select>
            <el-select v-model="type" clearable placeholder="全部类型" style="width: 140px" @change="reload">
              <el-option v-for="t in TASK_TYPES" :key="t" :label="t" :value="t" />
            </el-select>
          </div>
        </div>
      </template>

      <el-table :data="tasks" v-loading="loading" size="large" empty-text="暂无任务">
        <el-table-column prop="id" label="ID" width="76" />
        <el-table-column prop="type" label="类型" width="100" />
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <EnumTag :value="row.status" :labels="TASK_STATUS_LABELS" :tags="TASK_STATUS_TAGS" />
          </template>
        </el-table-column>
        <el-table-column label="进度" min-width="160">
          <template #default="{ row }">
            <el-progress :percentage="row.progress" :stroke-width="8" :show-text="false" />
            <span class="stage">{{ row.stage ?? '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="attempt" label="尝试" width="70" />
        <el-table-column label="错误" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.error_code" class="err">[{{ row.error_code }}] {{ row.error_msg }}</span>
            <span v-else class="stage">—</span>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="完成时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.finished_at) }}</template>
        </el-table-column>
      </el-table>

      <ListPager :total="total" :page="page" :page-size="pageSize" @change="onPage" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

import { listAdminTasks } from '@/api/admin'
import EnumTag from '@/components/EnumTag.vue'
import ListPager from '@/components/ListPager.vue'
import PageHeader from '@/components/PageHeader.vue'
import { usePagedList } from '@/composables/usePagedList'
import { TASK_STATUS_LABELS, TASK_STATUS_TAGS, TASK_TYPES } from '@/constants/enums'
import type { TaskAdminOut } from '@/types'
import { formatDateTime } from '@/utils/format'

const status = ref('')
const type = ref('')

const { items: tasks, total, page, pageSize, loading, reload, onPage } = usePagedList<TaskAdminOut>(
  ({ limit, offset }) =>
    listAdminTasks({
      status: status.value || undefined,
      type: type.value || undefined,
      offset,
      limit,
    }),
  { errorText: '任务加载失败' },
)
</script>

<style scoped lang="less">
// .panel-tools/.pager 取全局共享类
.stage {
  display: block;
  font-size: @fs-xs;
  color: @c-text-muted;
}

.err {
  color: @c-danger;
  font-size: @fs-sm;
}
</style>
