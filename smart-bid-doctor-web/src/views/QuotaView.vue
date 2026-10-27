<!-- 次数页（02 §9.5）：免费额度 + 有效次数包展示；SKU 目录取自 constants/skus.ts
     （与后端 FJ_SKU_CATALOG 同源），下单走 billing 资源模块，支付为人工核销引导文案。 -->
<template>
  <div class="page">
    <header class="page-head">
      <div>
        <span class="page-eyebrow">Billing</span>
        <h1 class="page-title">次数与订单</h1>
        <p class="page-desc">免费额度与次数包余量一目了然，付款采用人工核销，到账后自动入账。</p>
      </div>
    </header>

    <!-- 额度概览：三张数据卡，强数值弱说明，首屏即可判断余量 -->
    <div class="overview cascade-in">
      <div class="stat stat-accent">
        <span class="stat-label">本月免费额度</span>
        <div class="stat-value num">{{ quota.free_left }}<small>个</small></div>
        <p class="stat-note">每月自动重置，删除项目不返还名额</p>
      </div>
      <div class="stat">
        <span class="stat-label">对照次数余额</span>
        <div class="stat-value num">{{ packRemain }}<small>次</small></div>
        <p class="stat-note num">{{ quota.packs.length }} 个有效次数包</p>
      </div>
      <div class="stat">
        <span class="stat-label">历史订单</span>
        <div class="stat-value num">{{ orderTotal }}<small>笔</small></div>
        <p class="stat-note">人工核销，核销后次数自动发放</p>
      </div>
    </div>

    <el-card class="block lift-card">
      <template #header>
        <div class="panel-head">
          <div class="panel-head-main">
            <span class="panel-title">有效次数包</span>
            <span class="panel-count num">{{ quota.packs.length }}</span>
          </div>
        </div>
      </template>

      <el-table v-if="quota.packs.length" :data="quota.packs">
        <el-table-column label="次数包" min-width="200">
          <template #default="{ row }">
            <span class="cell-strong">{{ skuTitle(row.type) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="剩余次数" width="140">
          <template #default="{ row }">
            <span class="remain num">{{ row.remain }}<small> 次</small></span>
          </template>
        </el-table-column>
        <el-table-column label="到期时间" width="160">
          <template #default="{ row }">
            <span class="cell-muted num">{{ row.expires_at ? formatDate(row.expires_at) : '长期有效' }}</span>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else description="暂无有效次数包，下单核销后自动到账" :image-size="72" />
    </el-card>

    <el-card class="block lift-card">
      <template #header>
        <div class="panel-head">
          <div class="panel-head-main">
            <span class="panel-title">购买次数包</span>
          </div>
          <span class="panel-hint">人工收款 · 核销后发放</span>
        </div>
      </template>

      <div class="packs">
        <article
          v-for="s in SKUS"
          :key="s.code"
          class="pack"
          :class="{ 'is-best': s.code === bestCode }"
        >
          <span v-if="s.code === bestCode" class="pack-badge">更划算</span>
          <div class="pack-name">{{ s.title }}</div>
          <div class="pack-price num">¥{{ s.priceCny }}<small>共 {{ s.times }} 次</small></div>
          <p class="pack-unit num">约 ¥{{ unitPrice(s) }} / 次</p>
          <el-button type="primary" :plain="s.code !== bestCode" @click="order(s)">立即下单</el-button>
        </article>
      </div>
    </el-card>

    <el-card class="lift-card">
      <template #header>
        <div class="panel-head">
          <div class="panel-head-main">
            <span class="panel-title">我的订单</span>
            <span class="panel-count num">{{ orderTotal }}</span>
          </div>
        </div>
      </template>

      <el-table v-if="orders.length" :data="orders">
        <el-table-column prop="order_no" label="订单号" min-width="190">
          <template #default="{ row }">
            <span class="num cell-mono">{{ row.order_no }}</span>
          </template>
        </el-table-column>
        <el-table-column label="商品" min-width="170">
          <template #default="{ row }">
            <span class="cell-strong">{{ skuTitle(row.sku) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="金额" width="110">
          <template #default="{ row }">
            <span class="num amount">¥{{ row.amount_cny }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag size="small" :type="ORDER_STATUS_TAGS[row.status as OrderStatus] ?? 'info'">
              <span class="tag-dot" />{{ ORDER_STATUS_LABELS[row.status as OrderStatus] ?? row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="160">
          <template #default="{ row }">
            <span class="cell-muted num">{{ formatDateTime(row.created_at) }}</span>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else description="暂无订单记录" :image-size="72" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { createOrder, getQuota, listOrders } from '@/api/billing'
import { notifyApiError } from '@/api/client'
import { ORDER_STATUS_LABELS, ORDER_STATUS_TAGS, type OrderStatus } from '@/constants/enums'
import { SKUS, type SkuInfo } from '@/constants/skus'
import { formatDate, formatDateTime } from '@/utils/format'
import { confirmAction } from '@/utils/confirm'
import type { OrderOut, QuotaOut } from '@/types'

const quota = ref<QuotaOut>({ free_left: 0, packs: [] })
const orders = ref<OrderOut[]>([])
const orderTotal = ref(0)

const packRemain = computed(() => quota.value.packs.reduce((sum, p) => sum + p.remain, 0))

/** 单价最低的 SKU 作为推荐档（换算展示，不参与计价） */
const bestCode = computed(() =>
  SKUS.reduce((best, s) => (s.priceCny / s.times < best.priceCny / best.times ? s : best)).code,
)

function unitPrice(s: SkuInfo) {
  return (s.priceCny / s.times).toFixed(1)
}

/** SKU 展示名：优先本地目录，未知 code（后端新增）回退原码 */
function skuTitle(code: string): string {
  return SKUS.find((s) => s.code === code)?.title ?? code
}

async function load() {
  try {
    const [q, o] = await Promise.all([getQuota(), listOrders()])
    quota.value = q
    orders.value = o.items
    orderTotal.value = o.total
  } catch (e) {
    notifyApiError(e, '次数与订单加载失败')
  }
}

async function order(sku: SkuInfo) {
  const ok = await confirmAction(`将以人工转账方式购买「${sku.title}」，金额 ¥${sku.priceCny}，核销后次数自动发放。`, {
    title: '确认下单',
    confirmText: '确认下单',
  })
  if (!ok) return
  try {
    const res = await createOrder(sku.code)
    // 纯文本拼接订单信息（不使用 HTML 注入）
    ElMessageBox.alert(
      `订单号：${res.order_no}\n商品：${sku.title}\n金额：¥${res.amount_cny}\n\n${res.pay_hint}`,
      '下单成功，请完成转账',
      { confirmButtonText: '我知道了' },
    )
    await load()
  } catch (e) {
    notifyApiError(e, '下单失败')
  }
}

onMounted(load)
</script>

<style scoped lang="less">
// ---- 额度概览 ----
.overview {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 20px;

  @media (max-width: @bp-md) {
    grid-template-columns: 1fr;
  }
}

.stat {
  padding: 20px 22px;
  border: 1px solid @c-line-soft;
  border-radius: @radius-lg;
  background: @c-surface;
  box-shadow: @shadow-xs;
  transition:
    transform @dur-base @ease-out,
    box-shadow @dur-base @ease-out;

  &:hover {
    transform: translateY(-2px);
    box-shadow: @shadow-md;
  }
}

// 主额度卡：强调色渐变，视觉重心前置
.stat-accent {
  border-color: transparent;
  background: linear-gradient(150deg, var(--app-accent-light) 0%, var(--app-accent) 46%, var(--app-accent-dark) 100%);
  box-shadow: @shadow-accent-lg;
  color: #fff;

  .stat-label,
  .stat-note {
    color: fade(#fff, 82%);
  }

  .stat-value small {
    color: fade(#fff, 78%);
  }

  &:hover {
    box-shadow: @shadow-accent-xl;
  }
}

.stat-label {
  font-size: @fs-xs;
  color: @c-text-sub;
  letter-spacing: 0.02em;
}

.stat-value {
  margin-top: 8px;
  font-size: 34px;
  font-weight: 700;
  line-height: 1.1;
  letter-spacing: -0.02em;
  color: @c-text;

  small {
    margin-left: 6px;
    font-size: @fs-sm;
    font-weight: 500;
    color: @c-text-sub;
  }
}

.stat-note {
  margin: 8px 0 0;
  font-size: @fs-xs;
  color: @c-text-muted;
}

// ---- 次数包商品 ----
.block {
  margin-bottom: 20px;
}

.packs {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 16px;

  @media (max-width: @bp-sm) {
    grid-template-columns: 1fr;
  }
}

.pack {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  padding: 20px;
  border: 1px solid @c-line;
  border-radius: @radius-lg;
  background: @c-surface;
  transition:
    transform @dur-base @ease-out,
    box-shadow @dur-base @ease-out,
    border-color @dur-base @ease-out;

  &:hover {
    transform: translateY(-3px);
    box-shadow: @shadow-md;
    border-color: color-mix(in srgb, var(--app-accent) 60%, var(--app-surface));
  }

  // 推荐档：强调描边 + 浅底，形成价格锚点
  &.is-best {
    border-color: color-mix(in srgb, var(--app-accent) 30%, var(--app-surface));
    background: linear-gradient(180deg, @c-accent-soft 0%, @c-surface 58%);
  }

  .el-button {
    width: 100%;
    margin-top: 10px;
  }

  @media (max-width: @bp-sm) {
    &:hover {
      transform: none;
    }
  }
}

.pack-badge {
  position: absolute;
  top: 14px;
  right: 14px;
  padding: 2px 8px;
  border-radius: @radius-pill;
  background: @c-accent;
  color: #fff;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.04em;
}

.pack-name {
  font-size: @fs-sm;
  font-weight: 600;
  color: @c-text;
}

.pack-price {
  font-size: 28px;
  font-weight: 700;
  line-height: 1.2;
  letter-spacing: -0.02em;
  color: @c-accent;

  small {
    margin-left: 6px;
    font-size: @fs-xs;
    font-weight: 500;
    color: @c-text-muted;
  }
}

.pack-unit {
  margin: 0 0 4px;
  font-size: @fs-xs;
  color: @c-text-muted;
}

// ---- 表格单元 ----
.cell-strong {
  font-size: @fs-sm;
  color: @c-text;
}

.cell-muted {
  font-size: @fs-xs;
  color: @c-text-muted;
}

.cell-mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: @fs-xs;
  color: @c-text-sub;
}

.remain {
  font-size: @fs-h2;
  font-weight: 700;
  color: @c-text;

  small {
    font-size: @fs-xs;
    font-weight: 500;
    color: @c-text-muted;
  }
}

.amount {
  font-weight: 600;
  color: @c-text;
}
</style>
