<!-- 文件上传槽：role（tender/bid）绑定的单文件上传组件。
     走 api/projects.ts uploadDocument（120s 放宽超时）；上传后交由父页面轮询解析进度。
     仅做前端前置校验（类型/大小提示），权威校验以后端魔数/加密/页数/大小为准。 -->
<template>
  <div class="upload-slot">
    <div class="slot-title-row">
      <span class="slot-title">{{ title }}</span>
      <span class="slot-meta">PDF · ≤{{ MAX_UPLOAD_MB }}MB</span>
    </div>
    <div class="slot-row">
      <!-- 一步上传：点击选区选中文件即自动上传，不再单独放「上传」按钮 -->
      <button
        type="button"
        class="slot-zone"
        :class="{ 'has-file': !!fileName, 'is-uploading': uploading }"
        :disabled="uploading"
        @click="input?.click()"
      >
        <span class="zone-icon" aria-hidden="true">
          <svg v-if="!uploading" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 16V4" />
            <path d="M8 8l4-4 4 4" />
            <path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" />
          </svg>
          <svg v-else class="zone-spinner" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <path d="M12 3a9 9 0 1 0 9 9" />
          </svg>
        </span>
        <span class="zone-body">
          <span class="zone-main" :title="fileName || undefined">{{ zoneMain }}</span>
          <span class="zone-hint">{{ zoneHint }}</span>
        </span>
        <span class="zone-cta">{{ zoneCta }}</span>
      </button>
      <input
        ref="input"
        class="file-input"
        type="file"
        accept="application/pdf"
        :aria-label="`选择${title}（PDF）`"
        @change="onPick"
      />
    </div>
    <!-- 上传进度：XHR onprogress 百分比（文本已在选区右侧显示，进度条只做视觉进度） -->
    <el-progress
      v-if="uploading"
      class="slot-progress"
      :percentage="percent"
      :stroke-width="4"
      :show-text="false"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

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
const fileSize = ref(0)
const percent = ref(0)

// 选区文案由上传状态驱动：空闲引导选择，上传中显示文件名与百分比，完成后复位
const zoneMain = computed(() => fileName.value || '点击选择 PDF 文件')
const zoneHint = computed(() =>
  uploading.value
    ? `${formatBytes(fileSize.value)} · 上传中 ${percent.value}%`
    : '单个文件，选择后自动上传并解析',
)
const zoneCta = computed(() => (uploading.value ? `${percent.value}%` : '上传'))

function resetPicker() {
  fileName.value = ''
  fileSize.value = 0
  if (input.value) input.value.value = ''
}

/** 选中即上传（一步到位），尺寸不符时直接提示并复位选择 */
function onPick() {
  const file = input.value?.files?.[0]
  if (!file) return
  fileName.value = file.name
  fileSize.value = file.size
  void onUpload()
}

async function onUpload() {
  const file = input.value?.files?.[0]
  if (!file) return
  // 前端预校验（体验层）；后端魔数/加密/页数为最终校验方
  if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
    ElMessage.warning(`文件超过 ${MAX_UPLOAD_MB}MB 上限（当前 ${formatBytes(file.size)}）`)
    resetPicker()
    return
  }
  uploading.value = true
  percent.value = 0
  try {
    const res = await uploadDocument(props.projectId, props.role, file, (p) => {
      percent.value = p
    })
    ElMessage.success(res.dup ? '与已上传文件内容一致（sha256 去重），已复用' : '上传成功，解析任务已创建')
    emit('uploaded')
  } catch (e) {
    notifyApiError(e, '上传失败')
  } finally {
    uploading.value = false
    resetPicker()
  }
}
</script>

<style scoped lang="less">
// 工作台 upload-row（grid 两列）内的单个槽位：占满所在列，长文件名靠 ellipsis 收敛
.upload-slot {
  min-width: 0;
}

.slot-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}

.slot-title {
  font-size: @fs-sm;
  font-weight: 600;
  color: @c-text;
}

.slot-meta {
  font-size: @fs-xs;
  color: @c-text-muted;
}

.slot-row {
  display: flex;
  align-items: stretch;
}

.slot-progress {
  margin-top: 8px;
}

// 点击选区：虚线框 + 悬停提亮，选中后转为实线强调色
.slot-zone {
  flex: 1;
  min-width: 0;
  min-height: 62px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border: 1px dashed @c-line;
  border-radius: @radius;
  background: @c-surface-alt;
  cursor: pointer;
  text-align: left;
  font: inherit;
  transition:
    border-color @dur-base @ease-out,
    background-color @dur-base @ease-out,
    box-shadow @dur-base @ease-out;

  &:hover {
    border-color: color-mix(in srgb, var(--app-accent) 45%, var(--app-line));
    background: @c-accent-soft;

    .zone-cta {
      color: @c-accent;
    }
  }

  &.has-file,
  &.is-uploading {
    border-style: solid;
    border-color: color-mix(in srgb, var(--app-accent) 30%, var(--app-line));
    background: @c-accent-soft;

    .zone-icon {
      background: @c-accent;
      color: #fff;
    }
  }

  // 上传中不可再点，光标给出「进行中」反馈
  &:disabled {
    cursor: progress;
  }
}

// 上传中图标旋转（reduced-motion 下由 global.less 统一停用）
.zone-spinner {
  animation: zone-spin 0.9s linear infinite;
}

@keyframes zone-spin {
  to {
    transform: rotate(360deg);
  }
}

.zone-icon {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: @radius-sm;
  background: @c-surface;
  color: @c-text-sub;
  transition:
    background-color @dur-base @ease-out,
    color @dur-base @ease-out;

  svg {
    width: 18px;
    height: 18px;
  }
}

.zone-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.zone-main {
  font-size: @fs-sm;
  color: @c-text;
  // 长文件名省略，防撑破布局
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.zone-hint {
  font-size: @fs-xs;
  color: @c-text-muted;
}

.zone-cta {
  flex: none;
  font-size: @fs-xs;
  font-weight: 600;
  color: @c-text-muted;
  transition: color @dur-base @ease-out;
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
