<!-- 订单管理（02 §9.5 / 05 §10）：核销（支付凭证查看）+ 支付流水（P2 预留） -->
<template>
  <div class="page">
    <PageHeader eyebrow="Operations" title="订单管理" desc="人工收款核销：核对转账凭证后发放次数包/订阅" />

    <el-card class="lift-card cascade-in">
      <template #header>
        <div class="panel-head">
          <div class="panel-head-main">
            <span class="panel-title">订单列表</span>
            <span class="panel-count num">{{ total }}</span>
          </div>
          <div class="panel-tools">
            <el-select v-model="status" clearable placeholder="全部状态" style="width: 140px" @change="reload">
              <el-option v-for="(label, v) in ORDER_STATUS_LABELS" :key="v" :label="label" :value="v" />
            </el-select>
            <el-button :loading="loading" @click="reload">刷新</el-button>
          </div>
        </div>
      </template>

      <el-table :data="orders" v-loading="loading" size="large" empty-text="暂无订单">
        <el-table-column prop="order_no" label="订单号" min-width="170" />
        <el-table-column prop="sku" label="商品" width="130" />
        <el-table-column label="金额" width="110">
          <template #default="{ row }"><span class="num">¥{{ row.amount_cny }}</span></template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <EnumTag :value="row.status" :labels="ORDER_STATUS_LABELS" :tags="ORDER_STATUS_TAGS" />
          </template>
        </el-table-column>
        <el-table-column label="下单时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="viewVoucher(row as OrderOut)">支付凭证</el-button>
            <el-button
              v-if="row.status === 'pending'"
              size="small"
              type="primary"
              @click="onGrant(row as OrderOut)"
            >
              核销
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <ListPager :total="total" :page="page" :page-size="pageSize" @change="onPage" />
    </el-card>

    <!-- 支付凭证弹层 -->
    <OverlayPanel v-model="voucherOpen" title="支付凭证" content-size="sm">
      <p class="voucher-order">订单号 <b>{{ voucherOrderNo }}</b></p>
      <div v-if="vouchers.length" class="voucher-list cascade-in">
        <div v-for="v in vouchers" :key="v.id" class="voucher-item">
          <span class="voucher-name">{{ v.orig_name }}</span>
          <span class="voucher-meta num">{{ formatBytes(v.size_bytes) }} · {{ formatDateTime(v.created_at) }}</span>
          <el-button size="small" text type="primary" @click="downloadVoucher(v)">下载</el-button>
        </div>
      </div>
      <p v-else class="voucher-empty">该订单暂未上传支付凭证</p>
    </OverlayPanel>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

import {
  downloadAdminAttachment,
  grantOrder,
  listAdminAttachments,
  listAdminOrders,
} from '@/api/admin'
import { notifyApiError } from '@/api/client'
import EnumTag from '@/components/EnumTag.vue'
import ListPager from '@/components/ListPager.vue'
import OverlayPanel from '@/components/OverlayPanel.vue'
import PageHeader from '@/components/PageHeader.vue'
import { useApiAction } from '@/composables/useApiAction'
import { usePagedList } from '@/composables/usePagedList'
import { ORDER_STATUS_LABELS, ORDER_STATUS_TAGS } from '@/constants/enums'
import type { AttachmentOut, OrderOut } from '@/types'
import { confirmAction } from '@/utils/confirm'
import { saveBlob } from '@/utils/download'
import { formatBytes, formatDateTime } from '@/utils/format'

const status = ref<string>('')

const { items: orders, total, page, pageSize, loading, reload, onPage } = usePagedList<OrderOut>(
  ({ limit, offset }) =>
    listAdminOrders({
      status: status.value || undefined,
      offset,
      limit,
    }),
  { errorText: '订单加载失败' },
)

const { run: runGrant } = useApiAction('核销失败')
const { run: runVoucher } = useApiAction('凭证下载失败')

const voucherOpen = ref(false)
const voucherOrderNo = ref('')
const vouchers = ref<AttachmentOut[]>([])

async function onGrant(row: OrderOut) {
  const ok = await confirmAction(
    `核销后立即为用户发放「${row.sku}」，金额 ¥${row.amount_cny}，操作将写入审计日志。确认已收到该笔转账？`,
    { title: '核销订单', confirmText: '确认核销', danger: true },
  )
  if (!ok) return
  const res = await runGrant(() => grantOrder(row.order_no))
  if (!res.ok) return
  ElMessage.success(`订单 ${row.order_no} 已核销`)
  void reload()
}

async function viewVoucher(row: OrderOut) {
  voucherOrderNo.value = row.order_no
  vouchers.value = []
  voucherOpen.value = true
  try {
    const data = await listAdminAttachments({ module: 'order_voucher', limit: 50 })
    vouchers.value = data.items.filter((a) => a.business_id !== null)
  } catch (e) {
    notifyApiError(e, '凭证加载失败')
  }
}

async function downloadVoucher(a: AttachmentOut) {
  const res = await runVoucher(() => downloadAdminAttachment(a.id))
  if (!res.ok) return
  saveBlob(res.data, a.orig_name)
}
</script>

<style scoped lang="less">
// .panel-tools/.pager 取全局共享类
.voucher-order {
  margin: 0 0 12px;
  font-size: @fs-sm;
  color: @c-text-sub;
}

.voucher-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.voucher-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border: 1px solid @c-line-soft;
  border-radius: @radius-sm;
}

.voucher-name {
  flex: 1;
  font-size: @fs-sm;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.voucher-meta {
  font-size: @fs-xs;
  color: @c-text-muted;
}

.voucher-empty {
  margin: 0;
  color: @c-text-muted;
  font-size: @fs-sm;
  text-align: center;
  padding: 18px 0;
}
</style>
