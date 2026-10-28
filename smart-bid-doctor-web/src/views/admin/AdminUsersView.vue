<!-- 用户管理（05 §2）：禁用/解禁 + 角色授予 + 邀请码签发（P1 邀测管控） -->
<template>
  <div class="page">
    <PageHeader eyebrow="System" title="用户管理" desc="账号状态、角色绑定与邀测邀请码（操作全量写审计）">
      <template #actions>
        <el-button type="primary" @click="inviteOpen = true">签发邀请码</el-button>
      </template>
    </PageHeader>

    <el-card class="lift-card cascade-in">
      <template #header>
        <div class="panel-head">
          <div class="panel-head-main">
            <span class="panel-title">用户列表</span>
            <span class="panel-count num">{{ total }}</span>
          </div>
          <div class="panel-tools">
            <el-input
              v-model="email"
              placeholder="按邮箱搜索"
              clearable
              style="width: 220px"
              @keyup.enter="reload"
              @clear="reload"
            />
            <el-button :loading="loading" @click="reload">查询</el-button>
          </div>
        </div>
      </template>

      <el-table :data="users" v-loading="loading" size="large" empty-text="暂无用户">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="email" label="邮箱" min-width="200" show-overflow-tooltip />
        <el-table-column label="角色" width="110">
          <template #default="{ row }">
            <EnumTag :value="row.role" :labels="USER_ROLE_LABELS" :tags="USER_ROLE_TAGS" />
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <EnumTag :value="row.status" :labels="USER_STATUS_LABELS" :tags="USER_STATUS_TAGS" />
          </template>
        </el-table-column>
        <el-table-column prop="org_name" label="所属机构" width="130">
          <template #default="{ row }">{{ row.org_name ?? '个人用户' }}</template>
        </el-table-column>
        <el-table-column label="最近登录" width="170">
          <template #default="{ row }">{{ formatDateTime(row.last_login_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="openRoles(row as AdminUserOut)">角色</el-button>
            <el-button
              v-if="row.status === 'active'"
              size="small"
              text
              type="danger"
              @click="onBan(row as AdminUserOut)"
            >
              禁用
            </el-button>
            <el-button v-else size="small" text type="success" @click="onUnban(row as AdminUserOut)">解禁</el-button>
          </template>
        </el-table-column>
      </el-table>

      <ListPager :total="total" :page="page" :page-size="pageSize" @change="onPage" />
    </el-card>

    <el-card class="lift-card mt">
      <template #header>
        <div class="panel-head">
          <div class="panel-head-main">
            <span class="panel-title">邀请码</span>
            <span class="panel-hint">signup.require_invite 开启后新注册需有效邀请码</span>
          </div>
        </div>
      </template>
      <el-table :data="invites" size="large" empty-text="暂无邀请码">
        <el-table-column prop="code" label="邀请码" width="140" />
        <el-table-column label="已用/上限" width="110">
          <template #default="{ row }">
            <span class="num">{{ row.used_count }}/{{ row.max_uses }}</span>
          </template>
        </el-table-column>
        <el-table-column label="过期时间" width="170">
          <template #default="{ row }">{{ row.expires_at ? formatDateTime(row.expires_at) : '永不过期' }}</template>
        </el-table-column>
        <el-table-column label="签发时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 角色授予 -->
    <OverlayPanel v-model="rolesOpen" title="分配角色" content-size="sm">
      <p class="roles-user">{{ rolesEmail }}</p>
      <el-checkbox-group v-model="selectedRoles" class="roles-group">
        <el-checkbox v-for="r in allRoles" :key="r.id" :value="r.id" :label="r.name" />
      </el-checkbox-group>
      <p class="roles-hint">提示：管理员账号未绑定任何角色时拥有全量权限（兼容 seed_admin 提权路径）。</p>
      <template #footer>
        <el-button @click="rolesOpen = false">取消</el-button>
        <el-button type="primary" :loading="savingRoles" @click="saveRoles">保存</el-button>
      </template>
    </OverlayPanel>

    <!-- 签发邀请码 -->
    <OverlayPanel v-model="inviteOpen" title="签发邀请码" content-size="sm">
      <el-form label-width="90px">
        <el-form-item label="可用次数">
          <el-input-number v-model="inviteMaxUses" :min="1" :max="999" />
        </el-form-item>
        <el-form-item label="有效天数">
          <el-input-number v-model="inviteTtl" :min="0" :max="365" />
          <span class="roles-hint">0 = 永不过期</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="inviteOpen = false">取消</el-button>
        <el-button type="primary" :loading="savingInvite" @click="createInvite">签发</el-button>
      </template>
    </OverlayPanel>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

import {
  banUser,
  getUserRoles,
  issueInvite,
  listAdminUsers,
  listInvites,
  listRoles,
  setUserRoles,
  unbanUser,
} from '@/api/admin'
import { notifyApiError } from '@/api/client'
import EnumTag from '@/components/EnumTag.vue'
import ListPager from '@/components/ListPager.vue'
import OverlayPanel from '@/components/OverlayPanel.vue'
import PageHeader from '@/components/PageHeader.vue'
import { useApiAction } from '@/composables/useApiAction'
import { usePagedList } from '@/composables/usePagedList'
import { USER_ROLE_LABELS, USER_ROLE_TAGS, USER_STATUS_LABELS, USER_STATUS_TAGS } from '@/constants/enums'
import type { AdminUserOut, InviteOut, RoleOut } from '@/types'
import { confirmAction } from '@/utils/confirm'
import { formatDateTime } from '@/utils/format'

const invites = ref<InviteOut[]>([])
const allRoles = ref<RoleOut[]>([])
const email = ref('')

// 用户分页主列表；邀请码列表为连带副产物（fetcher 内一并拉取，失败同口径提示）
const { items: users, total, page, pageSize, loading, reload, onPage } = usePagedList<AdminUserOut>(
  async ({ limit, offset }) => {
    const data = await listAdminUsers({
      email: email.value || undefined,
      offset,
      limit,
    })
    const invitesData = await listInvites({ limit: 20 })
    invites.value = invitesData.items
    return data
  },
  { errorText: '用户加载失败' },
)

const rolesOpen = ref(false)
const rolesEmail = ref('')
const rolesUserId = ref(0)
const selectedRoles = ref<number[]>([])

const inviteOpen = ref(false)
const inviteMaxUses = ref(1)
const inviteTtl = ref(30)

const { pending: savingRoles, run: runSaveRoles } = useApiAction('角色保存失败')
const { pending: savingInvite, run: runIssueInvite } = useApiAction('签发失败')
const { run: runBan } = useApiAction()

async function openRoles(row: AdminUserOut) {
  rolesUserId.value = row.id
  rolesEmail.value = row.email
  try {
    const [current, roles] = await Promise.all([getUserRoles(row.id), listRoles()])
    selectedRoles.value = current.roles.map((r) => r.id)
    allRoles.value = roles
    rolesOpen.value = true
  } catch (e) {
    notifyApiError(e, '角色加载失败')
  }
}

async function saveRoles() {
  const res = await runSaveRoles(() => setUserRoles(rolesUserId.value, selectedRoles.value))
  if (!res.ok) return
  ElMessage.success('角色已更新')
  rolesOpen.value = false
  void reload()
}

async function onBan(row: AdminUserOut) {
  const ok = await confirmAction(`禁用后该用户将立即无法登录（${row.email}）。`, {
    title: '禁用账号',
    confirmText: '禁用',
    danger: true,
  })
  if (!ok) return
  const res = await runBan(() => banUser(row.id))
  if (!res.ok) return
  ElMessage.success('已禁用')
  void reload()
}

async function onUnban(row: AdminUserOut) {
  const res = await runBan(() => unbanUser(row.id))
  if (!res.ok) return
  ElMessage.success('已解禁')
  void reload()
}

async function createInvite() {
  const res = await runIssueInvite(() =>
    issueInvite({ max_uses: inviteMaxUses.value, ttl_days: inviteTtl.value }),
  )
  if (!res.ok) return
  ElMessage.success(`已签发邀请码 ${res.data.code}`)
  inviteOpen.value = false
  void reload()
}

</script>

<style scoped lang="less">
// .mt/.panel-tools/.pager 取全局共享类
.roles-user {
  margin: 0 0 12px;
  font-size: @fs-sm;
  color: @c-text-sub;
}

.roles-group {
  display: flex;
  flex-direction: column;
}

.roles-hint {
  margin: 10px 0 0;
  font-size: @fs-xs;
  color: @c-text-muted;
  margin-left: 8px;
}
</style>
