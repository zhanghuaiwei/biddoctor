<!-- AI 治理（05 §9）：模型注册（计价快照/开关）+ Prompt 版本管理（激活须 eval_score 锚定） -->
<template>
  <div class="page">
    <header class="page-head">
      <div>
        <p class="page-eyebrow">AI Governance</p>
        <h1 class="page-title">AI 治理</h1>
        <p class="page-desc">模型注册与 Prompt 版本管理：切换供应商=新增注册行，prompt 漂移即评测可追溯</p>
      </div>
      <div class="page-actions">
        <el-button @click="modelOpen = true">注册模型</el-button>
        <el-button type="primary" @click="promptOpen = true">新增 Prompt</el-button>
      </div>
    </header>

    <el-card class="lift-card cascade-in">
      <template #header>
        <div class="panel-head">
          <div class="panel-head-main">
            <span class="panel-title">模型注册</span>
            <span class="panel-hint">M1 LLM Provider 读取此处计价与开关；停用即拒绝新调用</span>
          </div>
        </div>
      </template>
      <el-table :data="models" v-loading="loading" size="large" empty-text="暂无模型注册">
        <el-table-column prop="model_code" label="模型" min-width="130" />
        <el-table-column prop="provider" label="供应商" width="100" />
        <el-table-column prop="purpose" label="用途" width="90" />
        <el-table-column label="输入价（元/百万 token）" width="180">
          <template #default="{ row }"><span class="num">{{ row.input_price }}</span></template>
        </el-table-column>
        <el-table-column label="输出价" width="110">
          <template #default="{ row }"><span class="num">{{ row.output_price }}</span></template>
        </el-table-column>
        <el-table-column prop="rpm_limit" label="RPM 限流" width="100">
          <template #default="{ row }">{{ row.rpm_limit ?? '不限' }}</template>
        </el-table-column>
        <el-table-column label="启用" width="90">
          <template #default="{ row }">
            <el-switch :model-value="row.enabled" @change="onToggleModel(row as AiModelOut, $event)" />
          </template>
        </el-table-column>
        <el-table-column prop="remark" label="备注" min-width="180" show-overflow-tooltip />
      </el-table>
    </el-card>

    <el-card class="lift-card mt">
      <template #header>
        <div class="panel-head">
          <div class="panel-head-main">
            <span class="panel-title">Prompt 版本</span>
            <span class="panel-hint">激活必须携带金标评测结果（eval_score）</span>
          </div>
        </div>
      </template>
      <el-table :data="prompts" size="large" empty-text="暂无 Prompt 版本">
        <el-table-column prop="purpose" label="用途" width="100" />
        <el-table-column prop="name" label="名称" min-width="140" />
        <el-table-column prop="version" label="版本" width="80" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '生效中' : '备选' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="评测锚点" min-width="220">
          <template #default="{ row }">
            <code v-if="row.eval_score" class="eval">{{ JSON.stringify(row.eval_score) }}</code>
            <span v-else class="no-eval">未评测（不可激活）</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="{ row }">
            <el-button v-if="!row.is_active" size="small" text type="primary" @click="onActivate(row as PromptOut)">
              切换生效
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <OverlayPanel v-model="modelOpen" title="注册模型" content-size="sm">
      <el-form label-width="110px">
        <el-form-item label="模型编码"><el-input v-model="mForm.model_code" placeholder="如 glm-4.6" /></el-form-item>
        <el-form-item label="用途">
          <el-radio-group v-model="mForm.purpose">
            <el-radio value="heavy">heavy</el-radio>
            <el-radio value="light">light</el-radio>
            <el-radio value="embed">embed</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="输入价"><el-input v-model="mForm.input_price" placeholder="元/百万 token" /></el-form-item>
        <el-form-item label="输出价"><el-input v-model="mForm.output_price" /></el-form-item>
        <el-form-item label="RPM 限流"><el-input v-model="mForm.rpm_limit" placeholder="可空=不限" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="mForm.remark" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="modelOpen = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="createModel">注册</el-button>
      </template>
    </OverlayPanel>

    <OverlayPanel v-model="promptOpen" title="新增 Prompt 版本" content-size="lg">
      <el-form label-width="80px">
        <el-form-item label="用途">
          <el-select v-model="pForm.purpose" style="width: 100%">
            <el-option label="extract（抽取）" value="extract" />
            <el-option label="judge（判定）" value="judge" />
            <el-option label="summary（摘要）" value="summary" />
            <el-option label="retry（重试）" value="retry" />
          </el-select>
        </el-form-item>
        <el-form-item label="名称"><el-input v-model="pForm.name" placeholder="如 extract_v3" /></el-form-item>
        <el-form-item label="版本号"><el-input-number v-model="pForm.version" :min="1" /></el-form-item>
        <el-form-item label="模板"><el-input v-model="pForm.template" type="textarea" :rows="8" placeholder="模板全文（占位符）" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="promptOpen = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="createPrompt">保存</el-button>
      </template>
    </OverlayPanel>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { activatePrompt, createAiModel, createPrompt as createPromptApi, listAiModels, listPrompts, updateAiModel } from '@/api/admin'
import { notifyApiError } from '@/api/client'
import type { AiModelOut, PromptOut } from '@/types'
import { confirmAction } from '@/utils/confirm'
import OverlayPanel from '@/components/OverlayPanel.vue'

const models = ref<AiModelOut[]>([])
const prompts = ref<PromptOut[]>([])
const loading = ref(false)
const saving = ref(false)
const modelOpen = ref(false)
const promptOpen = ref(false)

const mForm = reactive({ model_code: '', purpose: 'heavy', input_price: '0', output_price: '0', rpm_limit: '', remark: '' })
const pForm = reactive({ purpose: 'extract', name: '', version: 1, template: '' })

async function reload() {
  loading.value = true
  try {
    models.value = await listAiModels()
    prompts.value = await listPrompts()
  } catch (e) {
    notifyApiError(e, 'AI 治理数据加载失败')
  } finally {
    loading.value = false
  }
}

async function createModel() {
  if (!mForm.model_code) {
    ElMessage.warning('请填写模型编码')
    return
  }
  saving.value = true
  try {
    await createAiModel({
      model_code: mForm.model_code,
      purpose: mForm.purpose,
      input_price: mForm.input_price || '0',
      output_price: mForm.output_price || '0',
      rpm_limit: mForm.rpm_limit ? Number(mForm.rpm_limit) : null,
      remark: mForm.remark || null,
    })
    ElMessage.success('模型已注册')
    modelOpen.value = false
    void reload()
  } catch (e) {
    notifyApiError(e, '注册失败')
  } finally {
    saving.value = false
  }
}

async function onToggleModel(row: AiModelOut, enabled: unknown) {
  try {
    await updateAiModel(row.id, { enabled: Boolean(enabled) })
    row.enabled = Boolean(enabled)
    ElMessage.success(enabled ? '已启用' : '已停用（新调用将被拒绝）')
  } catch (e) {
    notifyApiError(e)
  }
}

async function createPrompt() {
  if (!pForm.name || !pForm.template) {
    ElMessage.warning('请填写名称与模板')
    return
  }
  saving.value = true
  try {
    await createPromptApi({ ...pForm })
    ElMessage.success('Prompt 版本已保存（未激活）')
    promptOpen.value = false
    void reload()
  } catch (e) {
    notifyApiError(e, '保存失败')
  } finally {
    saving.value = false
  }
}

async function onActivate(row: PromptOut) {
  const ok = await confirmAction(
    row.eval_score
      ? `切换「${row.name} v${row.version}」为生效版本？切换将写入审计（ai_prompt_switch）。`
      : `「${row.name} v${row.version}」尚无金标评测结果（eval_score），激活会被拒绝。`,
    { title: '切换 Prompt', confirmText: '确认' },
  )
  if (!ok) return
  try {
    await activatePrompt(row.id)
    ElMessage.success('已切换生效')
    void reload()
  } catch (e) {
    notifyApiError(e)
  }
}

onMounted(reload)
</script>

<style scoped lang="less">
.mt {
  margin-top: 16px;
}

.eval {
  font-size: @fs-xs;
  color: @c-text-sub;
  word-break: break-all;
}

.no-eval {
  font-size: @fs-xs;
  color: @c-text-muted;
}
</style>
