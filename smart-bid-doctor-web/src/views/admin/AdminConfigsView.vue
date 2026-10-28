<!-- 参数配置（05 §3.1）：运行时可调参数，改值即生效（TTL 缓存失效），写 sys_config_update 审计 -->
<template>
  <div class="page">
    <PageHeader eyebrow="Operations" title="参数配置" desc="运行时可调参数（配额/告警阈值/留存），改值即生效无需重启">
      <template #actions>
        <el-button :loading="loading" @click="reload">刷新</el-button>
      </template>
    </PageHeader>

    <el-card class="lift-card cascade-in">
      <el-table :data="rows" v-loading="loading" size="large" empty-text="暂无参数（bootstrap 种子生成）">
        <el-table-column prop="config_key" label="参数键" min-width="220" />
        <el-table-column prop="name" label="名称" min-width="160" />
        <el-table-column label="当前值" min-width="140">
          <template #default="{ row }">
            <code class="val num">{{ row.value }}</code>
          </template>
        </el-table-column>
        <el-table-column prop="value_type" label="类型" width="80" />
        <el-table-column prop="remark" label="说明" min-width="180" show-overflow-tooltip />
        <el-table-column label="更新时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="openEdit(row as ConfigOut)">修改</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <OverlayPanel v-model="editOpen" title="修改参数" content-size="sm">
      <p class="edit-key"><code>{{ editing?.config_key }}</code>（{{ editing?.name }}）</p>
      <p class="edit-hint">类型：{{ editing?.value_type }}{{ editing?.remark ? ` · ${editing.remark}` : '' }}</p>
      <el-input v-model="editValue" placeholder="新值" />
      <template #footer>
        <el-button @click="editOpen = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </OverlayPanel>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { listConfigs, updateConfig } from '@/api/admin'
import { notifyApiError } from '@/api/client'
import OverlayPanel from '@/components/OverlayPanel.vue'
import PageHeader from '@/components/PageHeader.vue'
import { useApiAction } from '@/composables/useApiAction'
import type { ConfigOut } from '@/types'
import { formatDateTime } from '@/utils/format'

const rows = ref<ConfigOut[]>([])
const loading = ref(false)
const editOpen = ref(false)
const editing = ref<ConfigOut | null>(null)
const editValue = ref('')

const { pending: saving, run: runSave } = useApiAction('保存失败')

async function reload() {
  loading.value = true
  try {
    rows.value = await listConfigs()
  } catch (e) {
    notifyApiError(e, '参数加载失败')
  } finally {
    loading.value = false
  }
}

function openEdit(row: ConfigOut) {
  editing.value = row
  editValue.value = row.value
  editOpen.value = true
}

async function save() {
  if (!editing.value) return
  const key = editing.value.config_key
  const res = await runSave(() => updateConfig(key, editValue.value))
  if (!res.ok) return
  ElMessage.success(`参数 ${key} 已生效`)
  editOpen.value = false
  void reload()
}

onMounted(reload)
</script>

<style scoped lang="less">
.val {
  padding: 2px 8px;
  background: @c-accent-soft;
  border-radius: @radius-xs;
  font-size: @fs-sm;
}

.edit-key code {
  font-size: @fs-sm;
  color: @c-text;
}

.edit-hint {
  margin: 6px 0 12px;
  font-size: @fs-xs;
  color: @c-text-muted;
}
</style>
