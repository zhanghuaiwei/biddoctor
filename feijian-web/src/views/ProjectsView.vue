<template>
  <el-card>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px">
      <span style="font-weight: 700">检查项目（本月免费额度剩余 {{ freeLeft }} 个）</span>
      <el-button type="primary" @click="dialog = true">新建项目</el-button>
    </div>
    <el-table :data="items" v-loading="loading">
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="name" label="项目名称" />
      <el-table-column prop="industry" label="行业" width="110">
        <template #default="{ row }">
          <el-tag size="small" :type="row.industry === 'medical' ? 'danger' : 'info'">
            {{ row.industry === 'medical' ? '医疗器械' : '通用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="130" />
      <el-table-column prop="created_at" label="创建时间" width="180" />
      <el-table-column label="操作" width="150">
        <template #default="{ row }">
          <el-button size="small" @click="$router.push(`/projects/${row.id}`)">进入</el-button>
          <el-button size="small" type="danger" plain @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialog" title="新建项目" width="420px">
      <el-form label-position="top">
        <el-form-item label="项目名称">
          <el-input v-model="form.name" placeholder="如：xx医院设备采购-2026-10" />
        </el-form-item>
        <el-form-item label="行业">
          <el-select v-model="form.industry" style="width: 100%">
            <el-option label="通用" value="general" />
            <el-option label="医疗器械（P2）" value="medical" disabled />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="create">创建</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '../api'

const items = ref<any[]>([])
const loading = ref(false)
const dialog = ref(false)
const creating = ref(false)
const freeLeft = ref(0)
const form = ref({ name: '', industry: 'general' })

async function load() {
  loading.value = true
  try {
    const [list, quota] = await Promise.all([api('/projects'), api('/me/quota')])
    items.value = list.items
    freeLeft.value = quota.free_left
  } catch (e: any) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

async function create() {
  if (!form.value.name.trim()) return ElMessage.warning('请输入项目名称')
  creating.value = true
  try {
    await api('/projects', { method: 'POST', body: JSON.stringify(form.value) })
    dialog.value = false
    form.value = { name: '', industry: 'general' }
    await load()
  } catch (e: any) {
    ElMessage.error(e.message)
  } finally {
    creating.value = false
  }
}

async function remove(row: any) {
  await ElMessageBox.confirm(`确认删除项目「${row.name}」？`, '删除确认', { type: 'warning' })
  await api(`/projects/${row.id}`, { method: 'DELETE' })
  await load()
}

onMounted(load)
</script>
