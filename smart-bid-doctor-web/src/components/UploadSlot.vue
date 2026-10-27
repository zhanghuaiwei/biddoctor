<!-- 文件上传槽：role（tender/bid）绑定的单文件上传组件。
     走 api/projects.ts uploadDocument（120s 放宽超时）；上传后交由父页面轮询解析进度。
     仅做前端前置校验（类型/大小提示），权威校验以后端魔数/加密/页数/大小为准。 -->
<template>
  <div class="upload-slot">
    <div class="slot-title">{{ title }}</div>
    <div class="slot-row">
      <!-- 点击选区：原生 file input 隐藏保留（可访问性 aria-label），整区可点击 -->
      <button type="button" class="slot-zone" :class="{ 'has-file': !!fileName }" @click="input?.click()">
        <span class="zone-main">{{ fileName || '点击选择 PDF 文件' }}</span>
        <span class="zone-hint">PDF · ≤{{ MAX_UPLOAD_MB }}MB</span>
      </button>
      <input
        ref="input"
        class="file-input"
        type="file"
        accept="application/pdf"
        :aria-label="`选择${title}（PDF）`"
        @change="onPick"
      />
      <el-button size="small" type="primary" plain :loading="uploading" :disabled="!fileName" @click="onUpload">
        上传
      </el-button>
    </div>
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
const fileName = ref('')

function onPick() {
  fileName.value = input.value?.files?.[0]?.name ?? ''
}

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
    fileName.value = ''
    if (input.value) input.value.value = ''
  }
}
</script>

<style scoped lang="less">
// 工作台 upload-row 内两槽均分一行，窄屏随父级 flex-wrap 折行铺满
.upload-slot {
  flex: 1;
  min-width: 260px;
}

.slot-title {
  margin-bottom: 8px;
  color: @c-text-sub;
}

.slot-row {
  display: flex;
  gap: 8px;
  align-items: stretch;
}

// 点击选区：虚线框 + 悬停提亮，选中后显示文件名
.slot-zone {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 2px;
  padding: 8px 12px;
  border: 1px dashed @c-line;
  border-radius: @radius - 2px;
  background: #fafbfc;
  cursor: pointer;
  text-align: left;
  font: inherit;
  transition:
    border-color @dur-base @ease-out,
    background-color @dur-base @ease-out;

  &:hover {
    border-color: tint(@c-primary, 40%);
    background: tint(@c-bg, 40%);
  }

  &.has-file {
    border-style: solid;
    border-color: tint(@c-primary, 40%);

    .zone-main {
      color: @c-text;
    }
  }
}

.zone-main {
  font-size: 13px;
  color: @c-text-sub;
  // 长文件名省略，防撑破布局
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.zone-hint {
  font-size: 12px;
  color: @c-text-sub;
}

// 原生 input 视觉隐藏但保留在 DOM（aria-label + change 事件）
.file-input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}
</style>
