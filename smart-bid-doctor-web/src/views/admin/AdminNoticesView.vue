<!-- 公告管理（05 §3.3）：draft → published → offline 状态机；发布/下线写审计 -->
<template>
  <div class="page">
    <PageHeader eyebrow="Operations" title="公告管理" desc="平台公告与维护通知：用户端首页横幅按 level 分级展示">
      <template #actions>
        <el-button type="primary" @click="openCreate">新建公告</el-button>
      </template>
    </PageHeader>

    <el-card class="lift-card cascade-in">
      <template #header>
        <div class="panel-head">
          <div class="panel-head-main">
            <span class="panel-title">公告列表</span>
            <span class="panel-count num">{{ total }}</span>
          </div>
          <el-select v-model="status" clearable placeholder="全部状态" style="width: 140px" @change="reload">
            <el-option v-for="(label, v) in NOTICE_STATUS_LABELS" :key="v" :label="label" :value="v" />
          </el-select>
        </div>
      </template>

      <el-table :data="rows" v-loading="loading" size="large" empty-text="暂无公告">
        <el-table-column prop="title" label="标题" min-width="220" show-overflow-tooltip />
        <el-table-column label="级别" width="90">
          <template #default="{ row }">
            <EnumTag :value="row.level" :labels="NOTICE_LEVEL_LABELS" :tags="NOTICE_LEVEL_TAGS" />
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <EnumTag :value="row.status" :labels="NOTICE_STATUS_LABELS" :tags="NOTICE_STATUS_TAGS" />
          </template>
        </el-table-column>
        <el-table-column label="发布时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.publish_at) }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="230" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'draft'"
              size="small"
              text
              type="primary"
              @click="onPublish(row as NoticeItem)"
            >
              发布
            </el-button>
            <el-button
              v-if="row.status === 'published'"
              size="small"
              text
              type="warning"
              @click="onOffline(row as NoticeItem)"
            >
              下线
            </el-button>
            <el-button
              v-if="row.status !== 'published'"
              size="small"
              text
              type="danger"
              @click="onDelete(row as NoticeItem)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <ListPager :total="total" :page="page" :page-size="pageSize" @change="onPage" />
    </el-card>

    <OverlayPanel v-model="createOpen" title="新建公告" content-size="lg">
      <el-form label-width="70px">
        <el-form-item label="标题"><el-input v-model="form.title" maxlength="128" /></el-form-item>
        <el-form-item label="级别">
          <el-radio-group v-model="form.level">
            <el-radio value="info">常规</el-radio>
            <el-radio value="warn">警告</el-radio>
            <el-radio value="critical">紧急</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="类型">
          <el-radio-group v-model="form.type">
            <el-radio value="notice">通知</el-radio>
            <el-radio value="announcement">公告</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="内容"><el-input v-model="form.content" type="textarea" :rows="6" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createOpen = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="create">保存草稿</el-button>
      </template>
    </OverlayPanel>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'

import { createNotice, deleteNotice, listAdminNotices, offlineNotice, publishNotice } from '@/api/admin'
import EnumTag from '@/components/EnumTag.vue'
import ListPager from '@/components/ListPager.vue'
import OverlayPanel from '@/components/OverlayPanel.vue'
import PageHeader from '@/components/PageHeader.vue'
import { useApiAction } from '@/composables/useApiAction'
import { usePagedList } from '@/composables/usePagedList'
import { NOTICE_LEVEL_LABELS, NOTICE_LEVEL_TAGS, NOTICE_STATUS_LABELS, NOTICE_STATUS_TAGS } from '@/constants/enums'
import type { NoticeItem } from '@/types'
import { confirmAction } from '@/utils/confirm'
import { formatDateTime } from '@/utils/format'

const status = ref('')
const createOpen = ref(false)

const { items: rows, total, page, pageSize, loading, reload, onPage } = usePagedList<NoticeItem>(
  ({ limit, offset }) =>
    listAdminNotices({
      status: status.value || undefined,
      offset,
      limit,
    }),
  { errorText: '公告加载失败' },
)

const form = reactive({ title: '', content: '', level: 'info', type: 'notice' })

const { pending: saving, run: runCreate } = useApiAction('创建失败')
const { run: runNotice } = useApiAction()

function openCreate() {
  form.title = ''
  form.content = ''
  form.level = 'info'
  form.type = 'notice'
  createOpen.value = true
}

async function create() {
  if (!form.title || !form.content) {
    ElMessage.warning('请填写标题与内容')
    return
  }
  const res = await runCreate(() => createNotice({ ...form }))
  if (!res.ok) return
  ElMessage.success('已保存为草稿')
  createOpen.value = false
  void reload()
}

async function onPublish(row: NoticeItem) {
  const res = await runNotice(() => publishNotice(row.id))
  if (!res.ok) return
  ElMessage.success('已发布，用户端横幅生效')
  void reload()
}

async function onOffline(row: NoticeItem) {
  const ok = await confirmAction(`下线后用户端不再展示「${row.title}」。`, { title: '下线公告' })
  if (!ok) return
  const res = await runNotice(() => offlineNotice(row.id))
  if (!res.ok) return
  ElMessage.success('已下线')
  void reload()
}

async function onDelete(row: NoticeItem) {
  const ok = await confirmAction(`删除公告「${row.title}」？`, { title: '删除公告', danger: true })
  if (!ok) return
  const res = await runNotice(() => deleteNotice(row.id))
  if (!res.ok) return
  ElMessage.success('已删除')
  void reload()
}

</script>
