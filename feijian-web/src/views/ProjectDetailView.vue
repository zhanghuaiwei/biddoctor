<template>
  <div v-if="project">
    <el-card style="margin-bottom: 16px">
      <div style="display: flex; justify-content: space-between; align-items: center">
        <div>
          <b style="font-size: 16px">{{ project.name }}</b>
          <el-tag style="margin-left: 8px" size="small">{{ project.status }}</el-tag>
        </div>
        <el-button @click="$router.push('/projects')">返回列表</el-button>
      </div>
    </el-card>

    <el-card style="margin-bottom: 16px" header="文件上传（PDF，≤100MB / ≤500页）">
      <div style="display: flex; gap: 32px; flex-wrap: wrap">
        <div>
          <div style="margin-bottom: 8px; color: #66707c">招标文件（tender）</div>
          <div style="display: flex; gap: 8px">
            <input ref="tenderInput" type="file" accept="application/pdf" />
            <el-button size="small" type="primary" plain :loading="uploading === 'tender'"
              @click="upload('tender')">上传</el-button>
          </div>
        </div>
        <div>
          <div style="margin-bottom: 8px; color: #66707c">投标文件（bid）</div>
          <div style="display: flex; gap: 8px">
            <input ref="bidInput" type="file" accept="application/pdf" />
            <el-button size="small" type="primary" plain :loading="uploading === 'bid'"
              @click="upload('bid')">上传</el-button>
          </div>
        </div>
      </div>
    </el-card>

    <el-card style="margin-bottom: 16px" header="已上传文件">
      <el-table :data="docs">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="role" label="类型" width="90">
          <template #default="{ row }">
            {{ row.role === 'tender' ? '招标' : '投标' }}
          </template>
        </el-table-column>
        <el-table-column prop="orig_name" label="文件名" />
        <el-table-column prop="total_pages" label="页数" width="80" />
        <el-table-column prop="parse_status" label="解析状态" width="120">
          <template #default="{ row }">
            <el-tag size="small" :type="statusType(row.parse_status)">{{ row.parse_status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="提示" min-width="200">
          <template #default="{ row }">
            <span style="color: #909399; font-size: 12px">{{ (row.parse_warnings || [])[0] }}</span>
          </template>
        </el-table-column>
      </el-table>
      <div style="margin-top: 16px; display: flex; gap: 12px">
        <el-button type="primary" @click="genChecklist">生成废标条款清单</el-button>
        <el-button type="danger" plain @click="startCompare">发起双文件对照（消耗 1 次）</el-button>
        <el-button @click="loadDocs">刷新状态</el-button>
      </div>
    </el-card>

    <el-card header="废标条款清单（引擎接入后展示）">
      <el-table :data="checkItems">
        <el-table-column prop="code" label="编号" width="110" />
        <el-table-column prop="category" label="类别" width="130" />
        <el-table-column prop="requirement" label="要求" />
        <el-table-column prop="ref_page" label="页码" width="80" />
      </el-table>
      <el-empty v-if="!checkItems.length" description="暂无数据（清单生成引擎 M1 接入）" :image-size="60" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api'

const route = useRoute()
const pid = Number(route.params.id)
const project = ref<any>(null)
const docs = ref<any[]>([])
const checkItems = ref<any[]>([])
const uploading = ref('')
const tenderInput = ref<HTMLInputElement>()
const bidInput = ref<HTMLInputElement>()
let timer: any = null

type TagType = 'success' | 'danger' | 'warning' | 'info' | 'primary'

function statusType(s: string): TagType {
  return ({ done: 'success', failed: 'danger', need_review: 'warning' } as Record<string, TagType>)[s] || 'info'
}

async function loadProject() {
  project.value = await api(`/projects/${pid}`)
}

async function loadDocs() {
  const res = await api(`/projects/${pid}/documents`)
  docs.value = res.items
  const busy = res.items.some((d: any) => ['pending', 'running'].includes(d.parse_status))
  if (!busy && timer) {
    clearInterval(timer)
    timer = null
  }
}

async function loadCheckItems() {
  const res = await api(`/projects/${pid}/check-items`)
  checkItems.value = res.items
}

async function upload(role: 'tender' | 'bid') {
  const input = role === 'tender' ? tenderInput.value : bidInput.value
  const file = input?.files?.[0]
  if (!file) return ElMessage.warning('请先选择 PDF 文件')
  uploading.value = role
  try {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('role', role)
    const res = await api(`/projects/${pid}/documents`, { method: 'POST', body: fd })
    ElMessage.success(res.dup ? '文件重复上传（sha256 一致）' : '上传成功，解析任务已创建')
    await loadDocs()
    if (!timer) timer = setInterval(loadDocs, 3000)
  } catch (e: any) {
    ElMessage.error(e.message)
  } finally {
    uploading.value = ''
    if (input) input.value = ''
  }
}

async function genChecklist() {
  try {
    await api(`/projects/${pid}/checklist-report`, { method: 'POST' })
  } catch (e: any) {
    ElMessage.warning(e.message)
  }
}

async function startCompare() {
  try {
    const res = await api(`/projects/${pid}/compare`, { method: 'POST' })
    ElMessage.success(`对照任务已创建（task ${res.task_id}）`)
  } catch (e: any) {
    ElMessage.error(e.message)
  }
}

onMounted(async () => {
  await loadProject()
  await Promise.all([loadDocs(), loadCheckItems()])
})
onUnmounted(() => timer && clearInterval(timer))
</script>
