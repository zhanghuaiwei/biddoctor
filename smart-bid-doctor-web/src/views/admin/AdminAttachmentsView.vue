<!-- 附件库（05 §7）：全模块附件列表 + 软删 + 下载（删除写 attachment_delete 审计） -->
<template>
  <div class="page">
    <header class="page-head">
      <div>
        <p class="page-eyebrow">Operations</p>
        <h1 class="page-title">附件库</h1>
        <p class="page-desc">支付凭证/申诉/导入等通用附件；标书原件在项目内独立管理</p>
      </div>
      <div class="page-actions">
        <el-button :loading="loading" @click="reload">刷新</el-button>
      </div>
    </header>

    <el-card class="lift-card cascade-in">
      <template #header>
        <div class="panel-head">
          <div class="panel-head-main">
            <span class="panel-title">附件列表</span>
            <span class="panel-count num">{{ total }}</span>
          </div>
          <el-select v-model="module" clearable placeholder="全部模块" style="width: 160px" @change="reload">
            <el-option v-for="(label, v) in ATTACHMENT_MODULE_LABELS" :key="v" :label="label" :value="v" />
          </el-select>
        </div>
      </template>

      <el-table :data="rows" v-loading="loading" size="large" empty-text="暂无附件">
        <el-table-column prop="id" label="ID" width="76" />
        <el-table-column label="模块" width="110">
          <template #default="{ row }">
            {{ ATTACHMENT_MODULE_LABELS[row.module as AttachmentModule] ?? row.module }}
          </template>
        </el-table-column>
        <el-table-column prop="orig_name" label="文件名" min-width="220" show-overflow-tooltip />
        <el-table-column prop="business_id" label="关联业务" width="100" />
        <el-table-column label="大小" width="100">
          <template #default="{ row }"><span class="num">{{ formatBytes(row.size_bytes) }}</span></template>
        </el-table-column>
        <el-table-column label="上传时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="onDownload(row as AttachmentOut)">下载</el-button>
            <el-button size="small" text type="danger" @click="onDelete(row as AttachmentOut)">删除</el-button>
          </template>
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

import { deleteAdminAttachment, downloadAdminAttachment, listAdminAttachments } from '@/api/admin'
import { notifyApiError } from '@/api/client'
import { ATTACHMENT_MODULE_LABELS } from '@/constants/enums'
import type { AttachmentModule } from '@/constants/enums'
import type { AttachmentOut } from '@/types'
import { confirmAction } from '@/utils/confirm'
import { formatBytes, formatDateTime } from '@/utils/format'

const rows = ref<AttachmentOut[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const module = ref('')
const loading = ref(false)

async function reload() {
  loading.value = true
  try {
    const data = await listAdminAttachments({
      module: module.value || undefined,
      offset: (page.value - 1) * pageSize,
      limit: pageSize,
    })
    rows.value = data.items
    total.value = data.total
  } catch (e) {
    notifyApiError(e, '附件加载失败')
  } finally {
    loading.value = false
  }
}

function onPage(p: number) {
  page.value = p
  void reload()
}

async function onDownload(row: AttachmentOut) {
  try {
    const blob = await downloadAdminAttachment(row.id)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = row.orig_name
    link.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    notifyApiError(e, '下载失败')
  }
}

async function onDelete(row: AttachmentOut) {
  const ok = await confirmAction(`删除附件「${row.orig_name}」？物理文件将随 purge 周期回收。`, {
    title: '删除附件',
    danger: true,
  })
  if (!ok) return
  try {
    await deleteAdminAttachment(row.id)
    ElMessage.success('已删除（软删）')
    void reload()
  } catch (e) {
    notifyApiError(e)
  }
}

onMounted(reload)
</script>

<style scoped lang="less">
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 14px;
}
</style>
