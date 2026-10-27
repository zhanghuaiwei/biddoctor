<!-- 文件上传槽：role（tender/bid）绑定的单文件上传组件。
     走 api/projects.ts uploadDocument（120s 放宽超时）；上传后交由父页面轮询解析进度。
     仅做前端前置校验（类型/大小提示），权威校验以后端魔数/加密/页数/大小为准。 -->
<template>
  <div class="upload-slot">
    <div class="slot-title">{{ title }}</div>
    <div class="slot-row">
      <input
        ref="input"
        class="file-input"
        type="file"
        accept="application/pdf"
        :aria-label="`选择${title}（PDF）`"
      />
      <el-button size="small" type="primary" plain :loading="uploading" @click="onUpload">
        上传
      </el-button>
    </div>
    <div class="slot-hint">PDF · ≤{{ MAX_UPLOAD_MB }}MB</div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

import { uploadDocument } from '@/api/projects'
import { notifyApiError } from '@/api/client'
import { MAX_UPLOAD_MB, type DocumentRole } from '@/constants/enums'
import { formatBytes } from '@/utils/format'

const props = defineProps<{
  projectId: number
  role: DocumentRole
  title: string
}>()

const emit = defineEmits<{ uploaded: [] }>()

const input = ref<HTMLInputElement>()
const uploading = ref(false)

async function onUpload() {
  const file = input.value?.files?.[0]
  if (!file) return ElMessage.warning(`请先选择${props.title} PDF 文件`)
  // 前端预校验（体验层）；后端魔数/加密/页数为最终校验方
  if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
    return ElMessage.warning(`文件超过 ${MAX_UPLOAD_MB}MB 上限（当前 ${formatBytes(file.size)}）`)
  }
  uploading.value = true
  try {
    const res = await uploadDocument(props.projectId, props.role, file)
    ElMessage.success(res.dup ? '与已上传文件内容一致（sha256 去重），已复用' : '上传成功，解析任务已创建')
    emit('uploaded')
  } catch (e) {
    notifyApiError(e, '上传失败')
  } finally {
    uploading.value = false
    if (input.value) input.value.value = ''
  }
}
</script>

<style scoped lang="less">
.slot-title {
  margin-bottom: 8px;
  color: @c-text-sub;
}

.slot-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

// 原生 file input 样式收敛（可访问性：保留 aria-label）
.file-input {
  font-size: 12px;
  color: @c-text-sub;
  max-width: 220px;
}

.slot-hint {
  margin-top: 6px;
  font-size: 12px;
  color: @c-text-sub;
}
</style>
