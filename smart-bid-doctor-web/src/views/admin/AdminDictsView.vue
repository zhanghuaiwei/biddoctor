<!-- 字典管理（05 §3.2）：仅管展示层（label/排序/颜色），取值域以代码枚举注册表为准 -->
<template>
  <div class="page">
    <PageHeader eyebrow="Operations" title="字典管理" desc="仅管展示层标签/排序/颜色；业务取值域以枚举注册表为准">
      <template #actions>
        <el-button type="primary" @click="typeOpen = true">新建字典类型</el-button>
      </template>
    </PageHeader>

    <el-card class="lift-card cascade-in">
      <template #header>
        <div class="panel-head">
          <div class="panel-head-main">
            <span class="panel-title">字典类型</span>
            <span class="panel-count num">{{ types.length }}</span>
          </div>
        </div>
      </template>
      <el-table
        :data="types"
        v-loading="loading"
        size="large"
        highlight-current-row
        empty-text="暂无字典"
        @current-change="onPickType"
      >
        <el-table-column prop="dict_type" label="类型编码" min-width="180" />
        <el-table-column prop="name" label="名称" min-width="160" />
        <el-table-column prop="remark" label="备注" min-width="200" show-overflow-tooltip />
      </el-table>
    </el-card>

    <el-card v-if="currentType" class="lift-card mt">
      <template #header>
        <div class="panel-head">
          <div class="panel-head-main">
            <span class="panel-title">字典项 · {{ currentType.dict_type }}</span>
            <span class="panel-count num">{{ items.length }}</span>
          </div>
          <el-button size="small" type="primary" @click="openCreate">新增字典项</el-button>
        </div>
      </template>
      <el-table :data="items" v-loading="itemsLoading" size="large" empty-text="该类型暂无字典项">
        <el-table-column prop="value" label="取值" min-width="140" />
        <el-table-column prop="label" label="展示名" min-width="140" />
        <el-table-column prop="sort" label="排序" width="80" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <EnumTag :value="row.status" :labels="COMMON_STATUS_LABELS" :tags="COMMON_STATUS_TAGS" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="toggleStatus(row as DictDataOut)">
              {{ row.status === 'active' ? '停用' : '启用' }}
            </el-button>
            <el-button size="small" text type="danger" @click="onDelete(row as DictDataOut)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <OverlayPanel v-model="typeOpen" title="新建字典类型" content-size="sm">
      <el-form label-width="80px">
        <el-form-item label="编码"><el-input v-model="newType" placeholder="如 project_status" /></el-form-item>
        <el-form-item label="名称"><el-input v-model="newTypeName" placeholder="如 项目状态" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="typeOpen = false">取消</el-button>
        <el-button type="primary" :loading="savingType" @click="createType">创建</el-button>
      </template>
    </OverlayPanel>

    <OverlayPanel v-model="itemOpen" title="新增字典项" content-size="sm">
      <el-form label-width="80px">
        <el-form-item label="取值"><el-input v-model="newValue" placeholder="与枚举注册表一致" /></el-form-item>
        <el-form-item label="展示名"><el-input v-model="newLabel" /></el-form-item>
        <el-form-item label="排序"><el-input-number v-model="newSort" :min="0" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="itemOpen = false">取消</el-button>
        <el-button type="primary" :loading="savingItem" @click="createItem">创建</el-button>
      </template>
    </OverlayPanel>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { createDictData, createDictType, deleteDictData, listDictData, listDictTypes, updateDictData } from '@/api/admin'
import { notifyApiError } from '@/api/client'
import EnumTag from '@/components/EnumTag.vue'
import OverlayPanel from '@/components/OverlayPanel.vue'
import PageHeader from '@/components/PageHeader.vue'
import { useApiAction } from '@/composables/useApiAction'
import { COMMON_STATUS_LABELS, COMMON_STATUS_TAGS } from '@/constants/enums'
import type { DictDataOut, DictTypeOut } from '@/types'
import { confirmAction } from '@/utils/confirm'

const types = ref<DictTypeOut[]>([])
const items = ref<DictDataOut[]>([])
const currentType = ref<DictTypeOut | null>(null)
const loading = ref(false)
const itemsLoading = ref(false)

const typeOpen = ref(false)
const newType = ref('')
const newTypeName = ref('')
const itemOpen = ref(false)
const newValue = ref('')
const newLabel = ref('')
const newSort = ref(0)

const { pending: savingType, run: runCreateType } = useApiAction('创建失败')
const { pending: savingItem, run: runCreateItem } = useApiAction('创建失败')
const { run: runDictItem } = useApiAction()

async function reload() {
  loading.value = true
  try {
    types.value = await listDictTypes()
  } catch (e) {
    notifyApiError(e, '字典加载失败')
  } finally {
    loading.value = false
  }
}

async function onPickType(row: DictTypeOut | null) {
  currentType.value = row
  if (!row) return
  itemsLoading.value = true
  try {
    items.value = await listDictData(row.dict_type)
  } catch (e) {
    notifyApiError(e, '字典项加载失败')
  } finally {
    itemsLoading.value = false
  }
}

async function createType() {
  if (!newType.value || !newTypeName.value) {
    ElMessage.warning('请填写编码与名称')
    return
  }
  const res = await runCreateType(() => createDictType({ dict_type: newType.value, name: newTypeName.value }))
  if (!res.ok) return
  ElMessage.success('字典类型已创建')
  typeOpen.value = false
  newType.value = ''
  newTypeName.value = ''
  void reload()
}

function openCreate() {
  newValue.value = ''
  newLabel.value = ''
  newSort.value = items.value.length
  itemOpen.value = true
}

async function createItem() {
  if (!currentType.value) return
  const res = await runCreateItem(() =>
    createDictData(currentType.value?.dict_type ?? '', {
      value: newValue.value,
      label: newLabel.value,
      sort: newSort.value,
    }),
  )
  if (!res.ok) return
  ElMessage.success('字典项已创建')
  itemOpen.value = false
  void onPickType(currentType.value)
}

async function toggleStatus(row: DictDataOut) {
  const res = await runDictItem(() =>
    updateDictData(row.id, { status: row.status === 'active' ? 'disabled' : 'active' }),
  )
  if (res.ok) void onPickType(currentType.value)
}

async function onDelete(row: DictDataOut) {
  const ok = await confirmAction(`删除字典项「${row.label}」？`, { danger: true })
  if (!ok) return
  const res = await runDictItem(() => deleteDictData(row.id))
  if (!res.ok) return
  ElMessage.success('已删除')
  void onPickType(currentType.value)
}

onMounted(reload)
</script>

<style scoped lang="less">
// .mt 取全局共享类
</style>
