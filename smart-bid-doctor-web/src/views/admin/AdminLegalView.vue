<!-- 法务文档管理（05 §8）：版本化（draft→effective→retired）+ 签署记录（PIPL 留痕） -->
<template>
  <div class="page">
    <PageHeader eyebrow="Compliance" title="法务文档" desc="用户协议/隐私政策/免责声明版本化管理，同类型至多一版生效">
      <template #actions>
        <el-button type="primary" @click="openCreate">上传新版本</el-button>
      </template>
    </PageHeader>

    <el-card class="lift-card cascade-in">
      <template #header>
        <div class="panel-head">
          <div class="panel-head-main">
            <span class="panel-title">文档版本</span>
            <span class="panel-count num">{{ docs.length }}</span>
          </div>
        </div>
      </template>
      <el-table :data="docs" v-loading="loading" size="large" empty-text="暂无法务文档（bootstrap 已内置 v1.0）">
        <el-table-column label="类型" width="120">
          <template #default="{ row }">{{ LEGAL_DOC_TYPE_LABELS[row.doc_type as LegalDocType] ?? row.doc_type }}</template>
        </el-table-column>
        <el-table-column prop="version" label="版本" width="90" />
        <el-table-column prop="title" label="标题" min-width="180" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <EnumTag :value="row.status" :labels="LEGAL_STATUS_LABELS" :tags="LEGAL_STATUS_TAGS" />
          </template>
        </el-table-column>
        <el-table-column label="生效时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.effective_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="230" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="viewDoc(row as LegalDocOut)">查看</el-button>
            <el-button v-if="row.status === 'draft'" size="small" text type="success" @click="onPublish(row as LegalDocOut)">
              生效
            </el-button>
            <el-button v-if="row.status === 'effective'" size="small" text type="warning" @click="onRetire(row as LegalDocOut)">
              退役
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card class="lift-card mt">
      <template #header>
        <div class="panel-head">
          <div class="panel-head-main">
            <span class="panel-title">签署记录</span>
            <span class="panel-hint">PIPL「告知-同意」留痕（用户/IP/时间）</span>
            <span class="panel-count num">{{ sigTotal }}</span>
          </div>
        </div>
      </template>
      <el-table :data="signatures" v-loading="sigLoading" size="large" empty-text="暂无签署记录">
        <el-table-column prop="id" label="ID" width="76" />
        <el-table-column prop="user_email" label="用户" min-width="200" />
        <el-table-column prop="legal_doc_id" label="文档" width="90" />
        <el-table-column prop="ip" label="IP" width="140" />
        <el-table-column label="签署时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.signed_at) }}</template>
        </el-table-column>
      </el-table>
      <ListPager :total="sigTotal" :page="sigPage" :page-size="20" @change="onSigPage" />
    </el-card>

    <!-- 新版本 -->
    <OverlayPanel v-model="createOpen" title="上传新版本" content-size="lg">
      <el-form label-width="80px">
        <el-form-item label="类型">
          <el-select v-model="form.doc_type" style="width: 100%">
            <el-option v-for="(label, v) in LEGAL_DOC_TYPE_LABELS" :key="v" :label="label" :value="v" />
          </el-select>
        </el-form-item>
        <el-form-item label="版本号"><el-input v-model="form.version" placeholder="如 v1.1" /></el-form-item>
        <el-form-item label="标题"><el-input v-model="form.title" /></el-form-item>
        <el-form-item label="内容">
          <el-input v-model="form.content" type="textarea" :rows="10" placeholder="Markdown 全文" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createOpen = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="create">保存草稿</el-button>
      </template>
    </OverlayPanel>

    <!-- 查看文档 -->
    <OverlayPanel v-model="viewOpen" :title="viewing?.title ?? '文档预览'" content-size="lg">
      <p class="doc-meta">
        {{ LEGAL_DOC_TYPE_LABELS[viewing?.doc_type as LegalDocType] }} · {{ viewing?.version }} ·
        {{ LEGAL_STATUS_LABELS[viewing?.status as LegalStatus] }}
      </p>
      <pre class="doc-content">{{ viewing?.content }}</pre>
    </OverlayPanel>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { createLegalDoc, listLegalDocs, listSignatures, publishLegalDoc, retireLegalDoc } from '@/api/admin'
import { notifyApiError } from '@/api/client'
import EnumTag from '@/components/EnumTag.vue'
import ListPager from '@/components/ListPager.vue'
import OverlayPanel from '@/components/OverlayPanel.vue'
import PageHeader from '@/components/PageHeader.vue'
import { useApiAction } from '@/composables/useApiAction'
import { LEGAL_DOC_TYPE_LABELS, LEGAL_STATUS_LABELS, LEGAL_STATUS_TAGS } from '@/constants/enums'
import type { LegalDocType, LegalStatus } from '@/constants/enums'
import type { LegalDocOut, SignatureOut } from '@/types'
import { confirmAction } from '@/utils/confirm'
import { formatDateTime } from '@/utils/format'

const docs = ref<LegalDocOut[]>([])
const signatures = ref<SignatureOut[]>([])
const sigTotal = ref(0)
const sigPage = ref(1)
const loading = ref(false)
const sigLoading = ref(false)
const createOpen = ref(false)
const viewOpen = ref(false)
const viewing = ref<LegalDocOut | null>(null)

const form = reactive({
  doc_type: 'user_agreement', version: '', title: '', content: '',
  effective_at: new Date().toISOString(),
})

const { pending: saving, run: runSave } = useApiAction('保存失败')
const { run: runLegal } = useApiAction()

async function reload() {
  loading.value = true
  try {
    docs.value = await listLegalDocs()
  } catch (e) {
    notifyApiError(e, '法务文档加载失败')
  } finally {
    loading.value = false
  }
  await loadSignatures()
}

async function loadSignatures() {
  sigLoading.value = true
  try {
    const data = await listSignatures({ offset: (sigPage.value - 1) * 20, limit: 20 })
    signatures.value = data.items
    sigTotal.value = data.total
  } catch (e) {
    notifyApiError(e, '签署记录加载失败')
  } finally {
    sigLoading.value = false
  }
}

function onSigPage(p: number) {
  sigPage.value = p
  void loadSignatures()
}

function openCreate() {
  form.version = ''
  form.title = ''
  form.content = ''
  createOpen.value = true
}

async function create() {
  if (!form.version || !form.title || !form.content) {
    ElMessage.warning('请完整填写版本号/标题/内容')
    return
  }
  const res = await runSave(() => createLegalDoc({ ...form, effective_at: new Date().toISOString() }))
  if (!res.ok) return
  ElMessage.success('已保存为草稿')
  createOpen.value = false
  void reload()
}

function viewDoc(row: LegalDocOut) {
  viewing.value = row
  viewOpen.value = true
}

async function onPublish(row: LegalDocOut) {
  const ok = await confirmAction(
    `「${row.title} ${row.version}」生效后，同类型旧版本自动退役，所有用户需重新签署确认。`,
    { title: '发布生效', confirmText: '生效' },
  )
  if (!ok) return
  const res = await runLegal(() => publishLegalDoc(row.id))
  if (!res.ok) return
  ElMessage.success('已生效（写审计 legal_publish）')
  void reload()
}

async function onRetire(row: LegalDocOut) {
  const ok = await confirmAction(`退役「${row.title} ${row.version}」？退役后无生效版本时签署弹层不再强制。`, {
    title: '退役版本',
    danger: true,
  })
  if (!ok) return
  const res = await runLegal(() => retireLegalDoc(row.id))
  if (!res.ok) return
  ElMessage.success('已退役')
  void reload()
}

onMounted(reload)
</script>

<style scoped lang="less">
// .mt/.pager 取全局共享类
.doc-meta {
  margin: 0 0 10px;
  font-size: @fs-xs;
  color: @c-text-muted;
}

.doc-content {
  margin: 0;
  max-height: 420px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: @fs-sm;
  line-height: 1.7;
  color: @c-text;
}
</style>
