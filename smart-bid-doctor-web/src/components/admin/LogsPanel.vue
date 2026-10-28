<!-- 日志三表共用面板（05 §5）：audit/login/oper 分页查询 + CSV 导出（写 log_export 审计） -->
<template>
  <div class="page">
    <header class="page-head">
      <div>
        <p class="page-eyebrow">Audit</p>
        <h1 class="page-title">{{ title }}</h1>
        <p class="page-desc">{{ desc }}</p>
      </div>
      <div class="page-actions">
        <el-button type="primary" :loading="exporting" @click="onExport">导出 CSV</el-button>
        <el-button :loading="loading" @click="reload">刷新</el-button>
      </div>
    </header>

    <el-card class="lift-card cascade-in">
      <template #header>
        <div class="panel-head">
          <div class="panel-head-main">
            <span class="panel-title">查询</span>
            <span class="panel-count num">{{ total }}</span>
          </div>
          <div class="panel-tools">
            <template v-if="kind === 'audit'">
              <el-select v-model="filterA" filterable clearable placeholder="action" style="width: 220px" @change="reload">
                <el-option v-for="a in actions" :key="a" :label="a" :value="a" />
              </el-select>
              <el-input v-model="filterUid" placeholder="用户 ID" clearable style="width: 120px" @keyup.enter="reload" />
            </template>
            <template v-else-if="kind === 'login'">
              <el-input v-model="filterEmail" placeholder="按邮箱搜索" clearable style="width: 220px" @keyup.enter="reload" />
              <el-select v-model="filterResult" clearable placeholder="结果" style="width: 110px" @change="reload">
                <el-option label="成功" value="success" />
                <el-option label="失败" value="fail" />
              </el-select>
            </template>
            <el-input v-else v-model="filterModule" placeholder="module" clearable style="width: 180px" @keyup.enter="reload" />
            <el-button :loading="loading" @click="reload">查询</el-button>
          </div>
        </div>
      </template>

      <!-- 审计日志 -->
      <el-table v-if="kind === 'audit'" :data="auditRows" size="large" empty-text="暂无日志" v-loading="loading">
        <el-table-column prop="id" label="ID" width="76" />
        <el-table-column prop="action" label="动作" min-width="170" />
        <el-table-column prop="user_email" label="用户" min-width="170">
          <template #default="{ row }">{{ row.user_email ?? row.user_id ?? '系统' }}</template>
        </el-table-column>
        <el-table-column prop="target" label="目标" min-width="140" />
        <el-table-column label="详情" min-width="240">
          <template #default="{ row }">
            <code class="detail">{{ JSON.stringify(row.detail) }}</code>
          </template>
        </el-table-column>
        <el-table-column prop="ip" label="IP" width="130" />
        <el-table-column label="时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
      </el-table>

      <!-- 登录日志 -->
      <el-table v-else-if="kind === 'login'" :data="loginRows" size="large" empty-text="暂无日志" v-loading="loading">
        <el-table-column prop="id" label="ID" width="76" />
        <el-table-column prop="email" label="邮箱" min-width="190" />
        <el-table-column label="结果" width="90">
          <template #default="{ row }">
            <el-tag :type="LOGIN_RESULT_TAGS[row.result as LoginResult]" size="small">
              {{ LOGIN_RESULT_LABELS[row.result as LoginResult] ?? row.result }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="fail_reason" label="失败原因" width="120" />
        <el-table-column prop="ip" label="IP" width="130" />
        <el-table-column prop="user_agent" label="UA" min-width="220" show-overflow-tooltip />
        <el-table-column label="时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
      </el-table>

      <!-- 操作日志 -->
      <el-table v-else :data="operRows" size="large" empty-text="暂无日志" v-loading="loading">
        <el-table-column prop="id" label="ID" width="76" />
        <el-table-column prop="module" label="模块" width="130" />
        <el-table-column prop="action" label="动作" min-width="160" />
        <el-table-column label="请求" min-width="220">
          <template #default="{ row }">
            <span class="detail">{{ row.method }} {{ row.path }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="status_code" label="状态码" width="90" />
        <el-table-column label="耗时" width="90">
          <template #default="{ row }">
            <span class="num">{{ row.cost_ms != null ? `${row.cost_ms} ms` : '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="ip" label="IP" width="130" />
        <el-table-column label="时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <el-pagination
          layout="prev, pager, next"
          :total="total"
          :page-size="pageSize"
          :current-page="page"
          @current-change="onPage"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { exportLogsCsv, listAuditActions, listAuditLogs, listLoginLogs, listOperLogs } from '@/api/admin'
import { notifyApiError } from '@/api/client'
import { LOGIN_RESULT_LABELS, LOGIN_RESULT_TAGS } from '@/constants/enums'
import type { LoginResult } from '@/constants/enums'
import type { AuditLogOut, LoginLogOut, OperLogOut } from '@/types'
import { formatDateTime } from '@/utils/format'
import { saveBlob } from '@/utils/download'

const props = defineProps<{
  kind: 'audit' | 'login' | 'oper'
  title: string
  desc: string
}>()

const auditRows = ref<AuditLogOut[]>([])
const loginRows = ref<LoginLogOut[]>([])
const operRows = ref<OperLogOut[]>([])
const actions = ref<string[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)
const exporting = ref(false)

const filterA = ref('')
const filterUid = ref('')
const filterEmail = ref('')
const filterResult = ref('')
const filterModule = ref('')

async function reload() {
  loading.value = true
  try {
    if (props.kind === 'audit') {
      const data = await listAuditLogs({
        action: filterA.value || undefined,
        user_id: filterUid.value ? Number(filterUid.value) : undefined,
        offset: (page.value - 1) * pageSize,
        limit: pageSize,
      })
      auditRows.value = data.items
      total.value = data.total
      if (!actions.value.length) actions.value = await listAuditActions()
    } else if (props.kind === 'login') {
      const data = await listLoginLogs({
        email: filterEmail.value || undefined,
        result: filterResult.value || undefined,
        offset: (page.value - 1) * pageSize,
        limit: pageSize,
      })
      loginRows.value = data.items
      total.value = data.total
    } else {
      const data = await listOperLogs({
        module: filterModule.value || undefined,
        offset: (page.value - 1) * pageSize,
        limit: pageSize,
      })
      operRows.value = data.items
      total.value = data.total
    }
  } catch (e) {
    notifyApiError(e, '日志加载失败')
  } finally {
    loading.value = false
  }
}

function onPage(p: number) {
  page.value = p
  void reload()
}

async function onExport() {
  exporting.value = true
  try {
    const blob = await exportLogsCsv(props.kind)
    saveBlob(blob, `${props.kind}-logs.csv`)
  } catch (e) {
    notifyApiError(e, '导出失败')
  } finally {
    exporting.value = false
  }
}

onMounted(reload)
</script>

<style scoped lang="less">
.panel-tools {
  display: flex;
  gap: 10px;
}

.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 14px;
}

.detail {
  font-size: @fs-xs;
  color: @c-text-sub;
  word-break: break-all;
}
</style>
