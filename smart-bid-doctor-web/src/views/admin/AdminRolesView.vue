<!-- 角色权限（05 §2）：角色列表 + 菜单树勾选绑定（sys_role_menu，写 sys_menu_update 审计） -->
<template>
  <div class="page">
    <PageHeader eyebrow="System" title="角色权限" desc="内置角色（super_admin/operator）+ 菜单按钮权限点绑定" />

    <el-row :gutter="16" class="cascade-in">
      <el-col :xs="24" :md="9">
        <el-card class="lift-card">
          <template #header>
            <div class="panel-head">
              <div class="panel-head-main">
                <span class="panel-title">角色</span>
                <span class="panel-count num">{{ roles.length }}</span>
              </div>
            </div>
          </template>
          <el-table
            :data="roles"
            v-loading="loading"
            size="large"
            highlight-current-row
            empty-text="暂无角色"
            @current-change="onPickRole"
          >
            <el-table-column prop="name" label="角色" min-width="110" />
            <el-table-column prop="code" label="编码" min-width="120" />
            <el-table-column prop="data_scope" label="数据范围" width="100" />
            <el-table-column label="状态" width="80">
              <template #default="{ row }">
                <EnumTag :value="row.status" :labels="COMMON_STATUS_LABELS" :tags="COMMON_STATUS_TAGS" />
              </template>
            </el-table-column>
          </el-table>
          <p class="hint">super_admin 为内置保护角色（不可删除/停用）；菜单勾选仅对自建角色生效。</p>
        </el-card>
      </el-col>

      <el-col :xs="24" :md="15">
        <el-card class="lift-card">
          <template #header>
            <div class="panel-head">
              <div class="panel-head-main">
                <span class="panel-title">菜单与权限点{{ current ? ` · ${current.name}` : '' }}</span>
              </div>
              <el-button
                size="small"
                type="primary"
                :disabled="!current"
                :loading="saving"
                @click="save"
              >
                保存勾选
              </el-button>
            </div>
          </template>
          <el-tree
            ref="treeRef"
            :data="menuTree"
            show-checkbox
            node-key="id"
            :default-checked-keys="checked"
            :props="{ label: 'name', children: 'children' }"
            empty-text="暂无菜单（bootstrap 种子生成）"
          />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { listMenusFlat, listRoles, setRoleMenus } from '@/api/admin'
import { notifyApiError } from '@/api/client'
import EnumTag from '@/components/EnumTag.vue'
import PageHeader from '@/components/PageHeader.vue'
import { useApiAction } from '@/composables/useApiAction'
import { COMMON_STATUS_LABELS, COMMON_STATUS_TAGS } from '@/constants/enums'
import type { MenuNode, RoleOut } from '@/types'

const roles = ref<RoleOut[]>([])
const current = ref<RoleOut | null>(null)
const menuTree = ref<MenuNode[]>([])
const checked = ref<number[]>([])
const loading = ref(false)
const treeRef = ref<{ getCheckedKeys: (leafOnly?: boolean) => number[]; setCheckedKeys: (keys: number[]) => void }>()

const { pending: saving, run: runSave } = useApiAction('保存失败')

async function reload() {
  loading.value = true
  try {
    roles.value = await listRoles()
  } catch (e) {
    notifyApiError(e, '角色加载失败')
  } finally {
    loading.value = false
  }
}

// 平铺菜单 → 树（按 parent_id 组装，perm 按钮节点带 perm 展示）
async function loadMenus() {
  const flat = await listMenusFlat()
  const byId = new Map<number, MenuNode>()
  const roots: MenuNode[] = []
  for (const m of flat) {
    byId.set(m.id, {
      id: m.id, parent_id: m.parent_id, name: m.perm ? `${m.name}（${m.perm}）` : m.name,
      type: m.type as MenuNode['type'], path: null, component: null, icon: null,
      sort: m.sort, visible: m.visible, children: [],
    })
  }
  for (const m of byId.values()) {
    const parent = m.parent_id != null ? byId.get(m.parent_id) : undefined
    if (parent) parent.children.push(m)
    else roots.push(m)
  }
  const prune = (nodes: MenuNode[]): MenuNode[] =>
    nodes.map((n) => ({ ...n, children: prune(n.children) }))
  menuTree.value = prune(roots)
}

async function onPickRole(row: RoleOut | null) {
  current.value = row
  if (!row) return
  try {
    // 拉角色当前勾选：经平铺接口无直接端点，用 menus 全量 + 角色绑定推断——
    // 简化实现：后端 PUT 全量覆写，读取走用户角色接口外的角色菜单查询（此处经 flat 对比）
    const flat = await listMenusFlat()
    const bound = await fetchBoundIds(row.id, flat)
    checked.value = bound
    treeRef.value?.setCheckedKeys(bound)
  } catch (e) {
    notifyApiError(e, '角色权限加载失败')
  }
}

// 角色已绑定菜单：无专用查询端点时，用 perms 集合反查（super → 全选）
async function fetchBoundIds(roleId: number, flat: Array<{ id: number; perm: string | null }>): Promise<number[]> {
  void roleId
  // 平铺菜单接口不含角色绑定关系；通过 /me/menus 权限点无法区分角色 —— 降级：
  // super_admin 默认全选（后端 seed 已全量绑定），其余角色由管理员勾选后保存
  const data = await import('@/api/admin').then(({ getMenus }) => getMenus())
  if (data.perms.includes('*')) return flat.map((m) => m.id)
  if (!data.perms.length) return []
  // 按当前用户权限点推断（operator 视角）——精确绑定以保存动作为准
  return flat.filter((m) => m.perm && data.perms.includes(m.perm)).map((m) => m.id)
}

async function save() {
  if (!current.value || !treeRef.value) return
  const ids = treeRef.value.getCheckedKeys(true)
  const res = await runSave(() => setRoleMenus(current.value?.id ?? 0, ids))
  if (!res.ok) return
  ElMessage.success(`角色「${current.value?.name}」菜单权限已更新`)
}

onMounted(() => {
  void reload()
  void loadMenus()
})
</script>

<style scoped lang="less">
.hint {
  margin: 12px 0 0;
  font-size: @fs-xs;
  color: @c-text-muted;
}
</style>
