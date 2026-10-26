<template>
  <div>
    <el-card style="margin-bottom: 16px" header="我的次数">
      <p>本月免费项目额度剩余：<b>{{ quota.free_left }}</b> 个</p>
      <div v-for="p in quota.packs" :key="p.id" style="color: #66707c">
        次数包 {{ p.type }}：剩余 <b>{{ p.remain }}</b> 次
        <span v-if="p.expires_at">（{{ p.expires_at.slice(0, 10) }} 到期）</span>
      </div>
      <el-empty v-if="!quota.packs.length" description="暂无次数包" :image-size="50" />
    </el-card>

    <el-card style="margin-bottom: 16px" header="购买次数包（人工收款）">
      <div style="display: flex; gap: 16px">
        <el-card shadow="never" style="width: 260px">
          <div style="font-weight: 700">对照检查 5 次包</div>
          <div style="font-size: 24px; margin: 8px 0; color: #be3b2e">¥99</div>
          <el-button type="primary" plain size="small" @click="order('cmp_x5')">下单</el-button>
        </el-card>
        <el-card shadow="never" style="width: 260px">
          <div style="font-weight: 700">对照检查 20 次包</div>
          <div style="font-size: 24px; margin: 8px 0; color: #be3b2e">¥199</div>
          <el-button type="primary" plain size="small" @click="order('cmp_x20')">下单</el-button>
        </el-card>
      </div>
    </el-card>

    <el-card header="我的订单">
      <el-table :data="orders">
        <el-table-column prop="order_no" label="订单号" width="180" />
        <el-table-column prop="sku" label="商品" width="120" />
        <el-table-column prop="amount_cny" label="金额(¥)" width="100" />
        <el-table-column prop="status" label="状态" width="110">
          <template #default="{ row }">
            <el-tag size="small" :type="row.status === 'granted' ? 'success' : 'warning'">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '../api'

const quota = ref<any>({ free_left: 0, packs: [] })
const orders = ref<any[]>([])

async function load() {
  const [q, o] = await Promise.all([api('/me/quota'), api('/orders')])
  quota.value = q
  orders.value = o.items
}

async function order(sku: string) {
  try {
    const res = await api('/orders', { method: 'POST', body: JSON.stringify({ sku }) })
    await ElMessageBox.alert(
      `订单号：<b>${res.order_no}</b><br/>金额：¥${res.amount_cny}<br/><br/>${res.pay_hint}`,
      '下单成功',
      { dangerouslyUseHTMLString: true },
    )
    await load()
  } catch (e: any) {
    ElMessage.error(e.message)
  }
}

onMounted(load)
</script>
