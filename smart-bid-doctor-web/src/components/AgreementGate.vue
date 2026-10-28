<!-- 协议签署弹层（05 §8）：登录后存在未签署的生效法务文档时强制展示，
     勾选全部并确认后调 POST /legal/agreements 留痕（PIPL「告知-同意」）。 -->
<template>
  <el-dialog
    :model-value="open"
    title="服务协议与隐私保护"
    width="560px"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    :show-close="false"
    class="agreement-dialog"
    append-to-body
  >
    <p class="agreement-lead">
      我们更新了以下法律文档，请阅读并同意后继续使用（签署记录将留痕存档）：
    </p>

    <div class="agreement-tabs">
      <button
        v-for="doc in pending"
        :key="doc.id"
        class="agreement-tab"
        :class="{ active: current?.id === doc.id }"
        @click="current = doc"
      >
        {{ LEGAL_DOC_TYPE_LABELS[doc.doc_type] }}
        <small>{{ doc.version }}</small>
      </button>
    </div>

    <div v-if="current" class="agreement-body">
      <h3 class="agreement-title">{{ current.title }}</h3>
      <pre class="agreement-content">{{ current.content }}</pre>
    </div>

    <el-checkbox v-model="agreed" class="agreement-check">
      我已阅读并同意
      <b>{{ pending.map((d) => LEGAL_DOC_TYPE_LABELS[d.doc_type]).join('、') }}</b>
    </el-checkbox>

    <template #footer>
      <el-button @click="logoutAndExit">不同意并退出</el-button>
      <el-button type="primary" :disabled="!agreed" :loading="signing" @click="sign">
        同意并继续
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { getCurrentLegal, signAgreements } from '@/api/platform'
import { notifyApiError } from '@/api/client'
import { LEGAL_DOC_TYPE_LABELS } from '@/constants/enums'
import type { LegalDocOut } from '@/types'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const open = ref(false)
const documents = ref<LegalDocOut[]>([])
const signedIds = ref<number[]>([])
const current = ref<LegalDocOut | null>(null)
const agreed = ref(false)
const signing = ref(false)

const pending = computed(() => documents.value.filter((d) => !signedIds.value.includes(d.id)))

onMounted(async () => {
  try {
    const data = await getCurrentLegal()
    documents.value = data.documents
    signedIds.value = data.signed_ids
    if (pending.value.length) {
      current.value = pending.value[0]
      agreed.value = false
      open.value = true
    }
  } catch {
    // 法务门禁拉取失败不阻断主流程（后端写操作不拦截时无强制语义）
  }
})

async function sign() {
  signing.value = true
  try {
    const data = await signAgreements(pending.value.map((d) => d.id))
    signedIds.value = data.signed_ids
    open.value = false
    ElMessage.success('签署完成，感谢您的信任')
  } catch (e) {
    notifyApiError(e, '签署失败，请稍后重试')
  } finally {
    signing.value = false
  }
}

function logoutAndExit() {
  useAuthStore().logout()
  void router.push('/login')
}
</script>

<style scoped lang="less">
.agreement-lead {
  margin: 0 0 14px;
  font-size: @fs-sm;
  color: @c-text-sub;
}

.agreement-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.agreement-tab {
  padding: 6px 14px;
  border: 1px solid @c-line;
  border-radius: @radius-pill;
  background: none;
  font-size: @fs-sm;
  color: @c-text-sub;
  cursor: pointer;
  transition: all @dur-fast @ease-out;

  small {
    margin-left: 6px;
    color: @c-text-muted;
  }

  &.active {
    border-color: var(--app-accent);
    color: var(--app-accent);
    background: var(--app-accent-soft);
    font-weight: 600;
  }
}

.agreement-body {
  border: 1px solid @c-line-soft;
  border-radius: @radius;
  padding: 14px 18px;
  background: fade(#000, 2%);
}

.agreement-title {
  margin: 0 0 8px;
  font-size: @fs-h3;
}

.agreement-content {
  margin: 0;
  max-height: 300px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  font-size: @fs-sm;
  line-height: 1.75;
  color: @c-text-sub;
}

.agreement-check {
  margin-top: 14px;
}
</style>
