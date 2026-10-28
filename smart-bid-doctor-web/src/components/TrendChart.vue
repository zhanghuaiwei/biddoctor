<!-- 轻量 SVG 折线趋势图（统计报表/监控大盘共用）：零第三方依赖，消费设计令牌。
     props: points({label, value}[])，自动归一化 + 渐变填充 + hover 提示。 -->
<template>
  <div class="trend">
    <svg :viewBox="`0 0 ${W} ${H}`" preserveAspectRatio="none" role="img" aria-label="趋势图">
      <defs>
        <linearGradient id="trend-fill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="var(--app-accent)" stop-opacity="0.28" />
          <stop offset="100%" stop-color="var(--app-accent)" stop-opacity="0.02" />
        </linearGradient>
      </defs>
      <!-- 横向网格线 -->
      <line v-for="i in 4" :key="i" class="grid" :x1="0" :x2="W" :y1="(H / 4) * (i - 1)" :y2="(H / 4) * (i - 1)" />
      <template v-if="lineD">
        <path :d="areaD" fill="url(#trend-fill)" />
        <path :d="lineD" fill="none" class="line" />
        <circle v-for="(p, i) in mapped" :key="i" class="dot" :cx="p.x" :cy="p.y" r="3" />
      </template>
      <text v-else class="empty" :x="W / 2" :y="H / 2" text-anchor="middle">暂无数据</text>
    </svg>
    <div v-if="mapped.length" class="labels">
      <span v-for="(p, i) in mapped" :key="i" class="label" :title="`${p.label}：${p.value}`">
        {{ p.label }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  points: Array<{ label: string; value: number }>
}>()

const W = 600
const H = 180
const PAD = 8

const mapped = computed(() => {
  const pts = props.points
  if (pts.length < 2) return pts.length === 1 ? [] : []
  const max = Math.max(...pts.map((p) => p.value), 1e-9)
  const min = Math.min(...pts.map((p) => p.value), 0)
  const span = max - min || 1
  const step = (W - PAD * 2) / (pts.length - 1)
  return pts.map((p, i) => ({
    label: p.label,
    value: p.value,
    x: PAD + i * step,
    y: H - PAD - ((p.value - min) / span) * (H - PAD * 2),
  }))
})

const lineD = computed(() => {
  const pts = mapped.value
  if (!pts.length) return ''
  return pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ')
})

const areaD = computed(() => {
  const pts = mapped.value
  if (!pts.length) return ''
  return `${lineD.value} L${pts[pts.length - 1].x.toFixed(1)},${H - PAD} L${pts[0].x.toFixed(1)},${H - PAD} Z`
})
</script>

<style scoped lang="less">
.trend {
  width: 100%;
}

svg {
  display: block;
  width: 100%;
  height: 180px;
}

.grid {
  stroke: @c-line-soft;
  stroke-width: 1;
  stroke-dasharray: 3 4;
}

.line {
  fill: none;
  stroke: var(--app-accent);
  stroke-width: 2;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.dot {
  fill: var(--app-accent);
  stroke: #fff;
  stroke-width: 1.5;
}

.empty {
  fill: @c-text-muted;
  font-size: 13px;
}

.labels {
  display: flex;
  justify-content: space-between;
  margin-top: 4px;
  padding: 0 2px;
}

.label {
  font-size: @fs-xs;
  color: @c-text-muted;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
