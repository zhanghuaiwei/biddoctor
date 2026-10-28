<!-- 订阅管理（P2 商业化）：计划配置（code=sub_* 即 orders.sku）+ 用户订阅实例 -->
<template>
  <div class="page">
    <header class="page-head">
      <div>
        <p class="page-eyebrow">Commerce</p>
        <h1 class="page-title">订阅管理</h1>
        <p class="page-desc">售卖计划配置与用户订阅实例；核销走订单统一入口（订阅激活+按期发放）</p>
      </div>
      <div class="page-actions">
        <el-button type="primary" @click="planOpen = true">新建计划</el-button>
      </div>
    </header>

    <el-card class="lift-card cascade-in">
      <template #header>
        <div class="panel-head">
          <div class="panel-head-main">
            <span class="panel-title">售卖计划</span>
            <span class="panel-count num">{{ plans.length }}</span>
          </div>
        </div>
      </template>
      <el-table :data="plans" v-loading="loading" size="large" empty-text="暂无计划（bootstrap 内置示例为停售态）">
        <el-table-column prop="code" label="编码" min-width="120" />
        <el-table-column prop="name" label="名称" min-width="150" />
        <el-table-column label="价格" width="110">
          <template #default="{ row }"><span class="num">¥{{ row.price_cny }}</span></template>
        </el-table-column>
        <el-table-column label="周期" width="90">
          <template #default="{ row }">{{ row.period_months }} 个月</template>
        </el-table-column>
        <el-table-column prop="compare_quota" label="每期次数" width="100" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
              {{ row.status === 'active' ? '在售' : '停售' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="togglePlan(row as PlanOut)">
              {{ row.status === 'active' ? '停售' : '上架' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card class="lift-card mt">
      <template #header>
        <div class="panel-head">
          <div class="panel-head-main">
            <span class="panel-title">用户订阅</span>
            <span class="panel-count num">{{ subTotal }}</span>
          </div>
          <el-select v-model="subStatus" clearable placeholder="全部状态" style="width: 140px" @change="reloadSubs">
            <el-option v-for="(label, v) in SUBSCRIPTION_STATUS_LABELS" :key="v" :label="label" :value="v" />
          </el-select>
        </div>
      </template>
      <el-table :data="subs" v-loading="subsLoading" size="large" empty-text="暂无订阅（核销 sub_* 订单后激活）">
        <el-table-column prop="id" label="ID" width="76" />
        <el-table-column prop="user_email" label="用户" min-width="200" />
        <el-table-column prop="plan_code" label="计划" width="120" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="SUBSCRIPTION_STATUS_TAGS[row.status as SubscriptionStatus]" size="small">
              {{ SUBSCRIPTION_STATUS_LABELS[row.status as SubscriptionStatus] ?? row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="本期起" width="120">
          <template #default="{ row }">{{ formatDate(row.period_start) }}</template>
        </el-table-column>
        <el-table-column label="本期止" width="120">
          <template #default="{ row }">{{ formatDate(row.period_end) }}</template>
        </el-table-column>
        <el-table-column label="自动续费" width="100">
          <template #default="{ row }">{{ row.auto_renew ? '是' : '否' }}</template>
        </el-table-column>
      </el-table>
      <div class="pager">
        <el-pagination layout="prev, pager, next" :total="subTotal" :page-size="20" :current-page="subPage" @current-change="onSubPage" />
      </div>
    </el-card>

    <OverlayPanel v-model="planOpen" title="新建订阅计划" content-size="sm">
      <el-form label-width="90px">
        <el-form-item label="编码"><el-input v-model="plan.code" placeholder="sub_basic / sub_pro" /></el-form-item>
        <el-form-item label="名称"><el-input v-model="plan.name" /></el-form-item>
        <el-form-item label="价格（元）"><el-input v-model="plan.price_cny" /></el-form-item>
        <el-form-item label="周期（月）"><el-input-number v-model="plan.period_months" :min="1" :max="36" /></el-form-item>
        <el-form-item label="每期次数"><el-input-number v-model="plan.compare_quota" :min="1" :max="999" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="planOpen = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="createPlan">创建</el-button>
      </template>
    </OverlayPanel>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { createPlan as createPlanApi, listPlans, listSubscriptions, updatePlan } from '@/api/admin'
import { notifyApiError } from '@/api/client'
import { SUBSCRIPTION_STATUS_LABELS, SUBSCRIPTION_STATUS_TAGS } from '@/constants/enums'
import type { SubscriptionStatus } from '@/constants/enums'
import type { PlanOut, SubscriptionOut } from '@/types'
import OverlayPanel from '@/components/OverlayPanel.vue'
import { formatDate } from '@/utils/format'

const plans = ref<PlanOut[]>([])
const subs = ref<SubscriptionOut[]>([])
const subTotal = ref(0)
const subPage = ref(1)
const subStatus = ref('')
const loading = ref(false)
const subsLoading = ref(false)
const saving = ref(false)
const planOpen = ref(false)

const plan = reactive({ code: '', name: '', price_cny: '', period_months: 1, compare_quota: 20 })

async function reload() {
  loading.value = true
  try {
    plans.value = await listPlans()
  } catch (e) {
    notifyApiError(e, '计划加载失败')
  } finally {
    loading.value = false
  }
  await reloadSubs()
}

async function reloadSubs() {
  subsLoading.value = true
  try {
    const data = await listSubscriptions({
      status: subStatus.value || undefined,
      offset: (subPage.value - 1) * 20,
      limit: 20,
    })
    subs.value = data.items
    subTotal.value = data.total
  } catch (e) {
    notifyApiError(e, '订阅加载失败')
  } finally {
    subsLoading.value = false
  }
}

function onSubPage(p: number) {
  subPage.value = p
  void reloadSubs()
}

async function createPlan() {
  if (!plan.code || !plan.name || !plan.price_cny) {
    ElMessage.warning('请完整填写编码/名称/价格')
    return
  }
  saving.value = true
  try {
    await createPlanApi({ ...plan, price_cny: plan.price_cny })
    ElMessage.success('计划已创建（在售）')
    planOpen.value = false
    plan.code = ''
    plan.name = ''
    plan.price_cny = ''
    void reload()
  } catch (e) {
    notifyApiError(e, '创建失败')
  } finally {
    saving.value = false
  }
}

async function togglePlan(row: PlanOut) {
  try {
    await updatePlan(row.id, { status: row.status === 'active' ? 'retired' : 'active' })
    ElMessage.success(row.status === 'active' ? '已停售' : '已上架')
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

.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 14px;
}
</style>
