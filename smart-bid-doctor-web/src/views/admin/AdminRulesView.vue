<!-- 规则库（P2 行业包）：版本管理 draft→active→retired + 条目维护（注入引擎预筛/复核） -->
<template>
  <div class="page">
    <PageHeader eyebrow="Rules" title="规则库" desc="行业包规则版本（law_version 法版本追踪），M2 引擎接入时读取">
      <template #actions>
        <el-button type="primary" @click="createOpen = true">新建规则库</el-button>
      </template>
    </PageHeader>

    <el-row :gutter="16" class="cascade-in">
      <el-col :xs="24" :md="10">
        <el-card class="lift-card">
          <template #header>
            <div class="panel-head">
              <div class="panel-head-main">
                <span class="panel-title">规则库版本</span>
                <span class="panel-count num">{{ sets.length }}</span>
              </div>
            </div>
          </template>
          <el-table
            :data="sets"
            v-loading="loading"
            size="large"
            highlight-current-row
            empty-text="暂无规则库"
            @current-change="onPick"
          >
            <el-table-column prop="industry" label="行业" width="100" />
            <el-table-column prop="law_version" label="法版本" min-width="150" show-overflow-tooltip />
            <el-table-column prop="version" label="版本" width="70" />
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <EnumTag
                  :value="row.status"
                  :labels="{ active: '生效', draft: '草稿', retired: '已退役' }"
                  :tags="{ active: 'success', draft: 'info', retired: 'warning' }"
                />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button v-if="row.status === 'draft'" size="small" text type="success" @click.stop="onActivate(row as RuleSetOut)">
                  激活
                </el-button>
                <el-button v-if="row.status === 'active'" size="small" text type="warning" @click.stop="onRetire(row as RuleSetOut)">
                  退役
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <el-col :xs="24" :md="14">
        <el-card class="lift-card">
          <template #header>
            <div class="panel-head">
              <div class="panel-head-main">
                <span class="panel-title">规则条目{{ current ? ` · v${current.version}` : '' }}</span>
                <span class="panel-count num">{{ items.length }}</span>
              </div>
              <el-button size="small" type="primary" :disabled="!current" @click="itemOpen = true">新增条目</el-button>
            </div>
          </template>
          <el-table :data="items" v-loading="itemsLoading" size="large" empty-text="左侧选择规则库后查看条目">
            <el-table-column prop="category" label="分类" width="110" />
            <el-table-column prop="kind" label="类型" width="90" />
            <el-table-column prop="pattern" label="表达式" min-width="200" show-overflow-tooltip />
            <el-table-column prop="action" label="动作" width="80" />
            <el-table-column label="操作" width="90" fixed="right">
              <template #default="{ row }">
                <el-button size="small" text type="danger" @click="onDeleteItem(row as RuleItemOut)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <OverlayPanel v-model="createOpen" title="新建规则库" content-size="sm">
      <el-form label-width="80px">
        <el-form-item label="行业">
          <el-select v-model="form.industry" style="width: 100%">
            <el-option label="通用" value="general" />
            <el-option label="医疗器械" value="medical" />
          </el-select>
        </el-form-item>
        <el-form-item label="法版本"><el-input v-model="form.law_version" placeholder="如 tender-law-2027rev" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="form.notes" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createOpen = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="createSet">创建</el-button>
      </template>
    </OverlayPanel>

    <OverlayPanel v-model="itemOpen" title="新增规则条目" content-size="sm">
      <el-form label-width="80px">
        <el-form-item label="分类">
          <el-select v-model="item.category" style="width: 100%">
            <el-option label="资格性" value="qualification" />
            <el-option label="符合性" value="compliance" />
            <el-option label="★强制" value="star" />
            <el-option label="报价" value="price" />
            <el-option label="签章密封" value="format_seal" />
          </el-select>
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="item.kind" style="width: 100%">
            <el-option label="正则" value="regex" />
            <el-option label="关键词" value="keyword" />
            <el-option label="数值" value="numeric" />
            <el-option label="日期" value="date" />
          </el-select>
        </el-form-item>
        <el-form-item label="表达式"><el-input v-model="item.pattern" /></el-form-item>
        <el-form-item label="动作">
          <el-radio-group v-model="item.action">
            <el-radio value="hint">hint（预筛）</el-radio>
            <el-radio value="must">must（必核）</el-radio>
            <el-radio value="veto">veto（否决）</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="说明"><el-input v-model="item.description" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="itemOpen = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="addItem">创建</el-button>
      </template>
    </OverlayPanel>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { activateRuleSet, addRuleItem, createRuleSet, deleteRuleItem, listRuleItems, listRuleSets, retireRuleSet } from '@/api/admin'
import { notifyApiError } from '@/api/client'
import EnumTag from '@/components/EnumTag.vue'
import OverlayPanel from '@/components/OverlayPanel.vue'
import PageHeader from '@/components/PageHeader.vue'
import { useApiAction } from '@/composables/useApiAction'
import type { RuleItemOut, RuleSetOut } from '@/types'
import { confirmAction } from '@/utils/confirm'

const sets = ref<RuleSetOut[]>([])
const items = ref<RuleItemOut[]>([])
const current = ref<RuleSetOut | null>(null)
const loading = ref(false)
const itemsLoading = ref(false)
const createOpen = ref(false)
const itemOpen = ref(false)

const form = reactive({ industry: 'general', law_version: '', notes: '' })
const item = reactive({ category: 'qualification', kind: 'keyword', pattern: '', action: 'hint', description: '' })

// saving 由 createSet/addItem 共用（两个弹层不同时打开）
const { pending: saving, run: runSave } = useApiAction('创建失败')
const { run: runRule } = useApiAction()

async function reload() {
  loading.value = true
  try {
    sets.value = await listRuleSets()
  } catch (e) {
    notifyApiError(e, '规则库加载失败')
  } finally {
    loading.value = false
  }
}

async function onPick(row: RuleSetOut | null) {
  current.value = row
  if (!row) return
  itemsLoading.value = true
  try {
    items.value = await listRuleItems(row.id)
  } catch (e) {
    notifyApiError(e, '条目加载失败')
  } finally {
    itemsLoading.value = false
  }
}

async function createSet() {
  if (!form.law_version) {
    ElMessage.warning('请填写法版本')
    return
  }
  const res = await runSave(() =>
    createRuleSet({ industry: form.industry, law_version: form.law_version, notes: form.notes || undefined }),
  )
  if (!res.ok) return
  ElMessage.success('规则库已创建（draft）')
  createOpen.value = false
  form.law_version = ''
  form.notes = ''
  void reload()
}

async function onActivate(row: RuleSetOut) {
  const res = await runRule(() => activateRuleSet(row.id))
  if (!res.ok) return
  ElMessage.success('已激活（同法版本旧 active 自动退役）')
  void reload()
}

async function onRetire(row: RuleSetOut) {
  const ok = await confirmAction(`退役规则库 v${row.version}？`, { title: '退役', danger: true })
  if (!ok) return
  const res = await runRule(() => retireRuleSet(row.id))
  if (!res.ok) return
  void reload()
}

async function addItem() {
  if (!current.value || !item.pattern) {
    ElMessage.warning('请填写表达式')
    return
  }
  const res = await runSave(() => addRuleItem(current.value?.id ?? 0, { ...item }))
  if (!res.ok) return
  ElMessage.success('条目已创建')
  itemOpen.value = false
  void onPick(current.value)
}

async function onDeleteItem(row: RuleItemOut) {
  const ok = await confirmAction('删除该规则条目？', { title: '删除', danger: true })
  if (!ok) return
  const res = await runRule(() => deleteRuleItem(row.id))
  if (!res.ok) return
  void onPick(current.value)
}

onMounted(reload)
</script>
