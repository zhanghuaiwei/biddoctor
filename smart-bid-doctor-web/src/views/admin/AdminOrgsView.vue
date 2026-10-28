<!-- 机构管理（05 §2.4）：树形 CRUD，软删且有子节点/在职用户时拒绝 -->
<template>
  <div class="page">
    <PageHeader eyebrow="System" title="机构管理" desc="组织归属与权限范围（不做数据隔离）；SaaS 默认单根节点">
      <template #actions>
        <el-button type="primary" @click="openCreate(null)">新建根机构</el-button>
      </template>
    </PageHeader>

    <el-card class="lift-card cascade-in">
      <el-table :data="tree" v-loading="loading" row-key="id" default-expand-all size="large" empty-text="暂无机构">
        <el-table-column prop="name" label="机构名称" min-width="240" />
        <el-table-column prop="code" label="编码" width="130" />
        <el-table-column prop="leader" label="负责人" width="130" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <EnumTag :value="row.status" :labels="COMMON_STATUS_LABELS" :tags="COMMON_STATUS_TAGS" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="230" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="openCreate((row as OrgNode).id)">加下级</el-button>
            <el-button size="small" text type="primary" @click="openEdit(row as OrgNode)">编辑</el-button>
            <el-button size="small" text type="danger" @click="onDelete(row as OrgNode)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <OverlayPanel v-model="formOpen" :title="editId ? '编辑机构' : '新建机构'" content-size="sm">
      <el-form label-width="80px">
        <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="编码"><el-input v-model="form.code" placeholder="唯一，可空" /></el-form-item>
        <el-form-item label="负责人"><el-input v-model="form.leader" placeholder="仅展示" /></el-form-item>
        <el-form-item label="排序"><el-input-number v-model="form.sort" :min="0" /></el-form-item>
        <el-form-item label="状态" v-if="editId">
          <el-radio-group v-model="form.status">
            <el-radio value="active">启用</el-radio>
            <el-radio value="disabled">停用</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formOpen = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </OverlayPanel>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { createOrg, deleteOrg, getOrgTree, updateOrg } from '@/api/admin'
import { notifyApiError } from '@/api/client'
import EnumTag from '@/components/EnumTag.vue'
import OverlayPanel from '@/components/OverlayPanel.vue'
import PageHeader from '@/components/PageHeader.vue'
import { useApiAction } from '@/composables/useApiAction'
import { COMMON_STATUS_LABELS, COMMON_STATUS_TAGS } from '@/constants/enums'
import type { CommonStatus } from '@/constants/enums'
import type { OrgNode } from '@/types'
import { confirmAction } from '@/utils/confirm'

const tree = ref<OrgNode[]>([])
const loading = ref(false)
const formOpen = ref(false)
const editId = ref<number | null>(null)
const parentId = ref<number | null>(null)

const form = reactive({
  name: '', code: '', leader: '', sort: 0, status: 'active' as CommonStatus,
})

const { pending: saving, run: runSave } = useApiAction('保存失败')
const { run: runDelete } = useApiAction()

async function reload() {
  loading.value = true
  try {
    tree.value = await getOrgTree()
  } catch (e) {
    notifyApiError(e, '机构加载失败')
  } finally {
    loading.value = false
  }
}

function openCreate(pid: number | null) {
  editId.value = null
  parentId.value = pid
  form.name = ''
  form.code = ''
  form.leader = ''
  form.sort = 0
  form.status = 'active'
  formOpen.value = true
}

function openEdit(row: OrgNode) {
  editId.value = row.id
  form.name = row.name
  form.code = row.code ?? ''
  form.leader = row.leader ?? ''
  form.sort = row.sort
  form.status = row.status
  formOpen.value = true
}

async function save() {
  if (!form.name) {
    ElMessage.warning('请填写机构名称')
    return
  }
  const res = await runSave(async () => {
    if (editId.value) {
      await updateOrg(editId.value, {
        name: form.name, code: form.code || undefined, leader: form.leader || undefined,
        sort: form.sort, status: form.status,
      })
      ElMessage.success('已保存')
    } else {
      await createOrg({
        name: form.name, parent_id: parentId.value,
        code: form.code || undefined, leader: form.leader || undefined, sort: form.sort,
      })
      ElMessage.success('已创建')
    }
  })
  if (!res.ok) return
  formOpen.value = false
  void reload()
}

async function onDelete(row: OrgNode) {
  const ok = await confirmAction(`删除机构「${row.name}」？仅允许删除无子节点且无用户挂靠的机构。`, {
    title: '删除机构',
    danger: true,
  })
  if (!ok) return
  const res = await runDelete(() => deleteOrg(row.id))
  if (!res.ok) return
  ElMessage.success('已删除（软删）')
  void reload()
}

onMounted(reload)
</script>
