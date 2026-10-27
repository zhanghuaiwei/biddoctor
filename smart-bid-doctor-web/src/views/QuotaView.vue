<!-- 次数页（02 §9.5）：免费额度 + 有效次数包展示；SKU 目录取自 constants/skus.ts
     （与后端 FJ_SKU_CATALOG 同源），下单走 billing 资源模块，支付为人工核销引导文案。 -->
<template>
  <div class="page">
    <el-card class="block lift-card" header="我的次数">
      <p>本月免费项目额度剩余：<b>{{ quota.free_left }}</b> 个</p>
      <div v-for="p in quota.packs" :key="p.id" class="pack-line">
        次数包 {{ skuTitle(p.type) }}：剩余 <b>{{ p.remain }}</b> 次
        <span v-if="p.expires_at">（{{ formatDate(p.expires_at) }} 到期）</span>
      </div>
      <el-empty v-if="!quota.packs.length" description="暂无次数包" :image-size="50" />
    </el-card>

    <el-card class="block lift-card" header="购买次数包（人工收款）">
      <div class="packs">
        <el-card v-for="s in SKUS" :key="s.code" shadow="never" class="pack">
          <div class="pack-name">{{ s.title }}</div>
          <div class="pack-price">¥{{ s.priceCny }}</div>
          <el-button type="primary" plain size="small" @click="order(s)">下单</el-button>
        </el-card>
      </div>
    </el-card>

    <el-card class="lift-card" header="我的订单">
      <el-table :data="orders">
        <el-table-column prop="order_no" label="订单号" width="180" />
        <el-table-column label="商品" width="160">
          <template #default="{ row }">{{ skuTitle(row.sku) }}</template>
        </el-table-column>
        <el-table-column label="金额(¥)" width="100">
          <template #default="{ row }">{{ row.amount_cny }}</template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag size="small" :type="ORDER_STATUS_TAGS[row.status as OrderStatus] ?? 'info'">
              {{ ORDER_STATUS_LABELS[row.status as OrderStatus] ?? row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { createOrder, getQuota, listOrders } from '@/api/billing'
import { notifyApiError } from '@/api/client'
import { ORDER_STATUS_LABELS, ORDER_STATUS_TAGS, type OrderStatus } from '@/constants/enums'
import { SKUS, type SkuInfo } from '@/constants/skus'
import { formatDate, formatDateTime } from '@/utils/format'
import type { OrderOut, QuotaOut } from '@/types'

const quota = ref<QuotaOut>({ free_left: 0, packs: [] })
const orders = ref<OrderOut[]>([])

/** SKU 展示名：优先本地目录，未知 code（后端新增）回退原码 */
function skuTitle(code: string): string {
  return SKUS.find((s) => s.code === code)?.title ?? code
}

async function load() {
  try {
    const [q, o] = await Promise.all([getQuota(), listOrders()])
    quota.value = q
    orders.value = o.items
  } catch (e) {
    notifyApiError(e, '次数与订单加载失败')
  }
}

async function order(sku: SkuInfo) {
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
.block {
  margin-bottom: 16px;
}

.pack-line {
  color: @c-text-sub;
}

// 商品卡：宽屏并排、窄屏折行铺满
.packs {
  display: flex;
  gap: 16px;

  @media (max-width: @bp-sm) {
    flex-direction: column;
  }
}

.pack {
  width: 260px;
  border: 1px solid @c-line;
  // 商品卡悬停：抬升 + 阴影，强化可点击感
  transition:
    transform @dur-base @ease-out,
    box-shadow @dur-base @ease-out,
    border-color @dur-base @ease-out;

  &:hover {
    transform: translateY(-3px);
    box-shadow: @shadow-md;
    border-color: tint(@c-accent, 60%);
  }

  @media (max-width: @bp-sm) {
    width: 100%;

    // 触屏无悬停，去掉抬升避免粘滞态
    &:hover {
      transform: none;
    }
  }
}

.pack-name {
  font-weight: 700;
}

.pack-price {
  font-size: 24px;
  margin: 8px 0;
  color: @c-accent;
}
</style>
