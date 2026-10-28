<!-- 告警中心（05 §4）：未确认常驻提示 + 人工确认（ack）闭环，确认写审计 -->
<template>
  <div class="page">
    <PageHeader eyebrow="Monitoring" title="告警中心" desc="阈值触发（任务失败率/积压/磁盘/连续失败），人工确认后闭环">
      <template #actions>
        <el-button :loading="loading" @click="reload">刷新</el-button>
      </template>
    </PageHeader>

    <el-card class="lift-card cascade-in">
      <template #header>
        <div class="panel-head">
          <div class="panel-head-main">
            <span class="panel-title">告警列表</span>
            <el-tag v-if="unacked > 0" type="danger" size="small" effect="light">
              未确认 {{ unacked }}
            </el-tag>
          </div>
          <div class="panel-tools">
            <el-select v-model="acked" clearable placeholder="全部" style="width: 140px" @change="reload">
              <el-option label="未确认" :value="false" />
              <el-option label="已确认" :value="true" />
            </el-select>
            <el-select v-model="level" clearable placeholder="全部级别" style="width: 120px" @change="reload">
              <el-option v-for="(label, v) in NOTICE_LEVEL_LABELS" :key="v" :label="label" :value="v" />
            </el-select>
          </div>
        </div>
      </template>

      <el-table :data="rows" v-loading="loading" size="large" empty-text="暂无告警（阈值触发后自动落记录）">
        <el-table-column label="级别" width="90">
          <template #default="{ row }">
            <EnumTag :value="row.level" :labels="NOTICE_LEVEL_LABELS" :tags="NOTICE_LEVEL_TAGS" />
          </template>
        </el-table-column>
        <el-table-column prop="title" label="标题" min-width="260" show-overflow-tooltip />
        <el-table-column prop="rule_key" label="规则" min-width="180" />
        <el-table-column label="指标快照" min-width="220">
          <template #default="{ row }">
            <code v-if="row.metric" class="metric">{{ JSON.stringify(row.metric) }}</code>
            <span v-else>—</span>
          </template>
        </el-table-column>
        <el-table-column label="触发时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="120" fixed="right">
          <template #default="{ row }">
            <el-button v-if="!row.acked_at" size="small" type="primary" @click="onAck(row as AlertOut)">确认</el-button>
            <span v-else class="acked">已确认</span>
          </template>
        </el-table-column>
      </el-table>

      <ListPager :total="total" :page="page" :page-size="pageSize" @change="onPage" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

import { ackAlert, listAlerts } from '@/api/admin'
import EnumTag from '@/components/EnumTag.vue'
import ListPager from '@/components/ListPager.vue'
import PageHeader from '@/components/PageHeader.vue'
import { useApiAction } from '@/composables/useApiAction'
import { usePagedList } from '@/composables/usePagedList'
import { NOTICE_LEVEL_LABELS, NOTICE_LEVEL_TAGS } from '@/constants/enums'
import type { AlertOut } from '@/types'
import { formatDateTime } from '@/utils/format'

const acked = ref<boolean | ''>('')
const level = ref('')
// 未确认计数来自同响应的聚合字段（fetcher 闭包捕获）
const unacked = ref(0)

const { items: rows, total, page, pageSize, loading, reload, onPage } = usePagedList<AlertOut>(
  ({ limit, offset }) =>
    listAlerts({
      acked: acked.value === '' ? undefined : (acked.value as boolean),
      level: level.value || undefined,
      offset,
      limit,
    }).then((data) => {
      unacked.value = data.unacked
      return data
    }),
  { errorText: '告警加载失败' },
)

const { run: runAck } = useApiAction()

async function onAck(row: AlertOut) {
  const res = await runAck(() => ackAlert(row.id))
  if (!res.ok) return
  ElMessage.success('已确认（写入审计 alert_ack）')
  void reload()
}
</script>

<style scoped lang="less">
// .panel-tools/.pager 取全局共享类
.metric {
  font-size: @fs-xs;
  color: @c-text-sub;
  word-break: break-all;
}

.acked {
  font-size: @fs-sm;
  color: @c-text-muted;
}
</style>
