<!-- 附件库（05 §7）：全模块附件列表 + 软删 + 下载（删除写 attachment_delete 审计） -->
<template>
  <div class="page">
    <PageHeader eyebrow="Operations" title="附件库" desc="支付凭证/申诉/导入等通用附件；标书原件在项目内独立管理">
      <template #actions>
        <el-button :loading="loading" @click="reload">刷新</el-button>
      </template>
    </PageHeader>

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

      <ListPager :total="total" :page="page" :page-size="pageSize" @change="onPage" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

import { deleteAdminAttachment, downloadAdminAttachment, listAdminAttachments } from '@/api/admin'
import ListPager from '@/components/ListPager.vue'
import PageHeader from '@/components/PageHeader.vue'
import { useApiAction } from '@/composables/useApiAction'
import { usePagedList } from '@/composables/usePagedList'
import { ATTACHMENT_MODULE_LABELS } from '@/constants/enums'
import type { AttachmentModule } from '@/constants/enums'
import type { AttachmentOut } from '@/types'
import { confirmAction } from '@/utils/confirm'
import { saveBlob } from '@/utils/download'
import { formatBytes, formatDateTime } from '@/utils/format'

const module = ref('')

const { items: rows, total, page, pageSize, loading, reload, onPage } = usePagedList<AttachmentOut>(
  ({ limit, offset }) =>
    listAdminAttachments({
      module: module.value || undefined,
      offset,
      limit,
    }),
  { errorText: '附件加载失败' },
)

const { run: runAttachment } = useApiAction()

async function onDownload(row: AttachmentOut) {
  const res = await runAttachment(() => downloadAdminAttachment(row.id))
  if (!res.ok) return
  saveBlob(res.data, row.orig_name)
}

async function onDelete(row: AttachmentOut) {
  const ok = await confirmAction(`删除附件「${row.orig_name}」？物理文件将随 purge 周期回收。`, {
    title: '删除附件',
    danger: true,
  })
  if (!ok) return
  const res = await runAttachment(() => deleteAdminAttachment(row.id))
  if (!res.ok) return
  ElMessage.success('已删除（软删）')
  void reload()
}
</script>

<style scoped lang="less">
// .pager 取全局共享类
</style>
