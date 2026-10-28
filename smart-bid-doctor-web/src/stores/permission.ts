/**
 * 管理端权限状态（05 §2.3）：登录后拉取 /me/menus → 菜单树驱动导航渲染、
 * 权限点集合驱动按钮级过滤。非 admin 用户 menus/perms 为空，管理入口不渲染。
 */
import { ref } from 'vue'
import { defineStore } from 'pinia'

import { getMyMenus } from '@/api/platform'
import type { MenuNode } from '@/types'

export const usePermissionStore = defineStore('permission', () => {
  const menus = ref<MenuNode[]>([])
  const perms = ref<Set<string>>(new Set())
  const loaded = ref(false)

  /** 拉取当前用户菜单与权限点（登录后/进入管理区时调用） */
  async function load(force = false) {
    if (loaded.value && !force) return
    try {
      const data = await getMyMenus()
      menus.value = data.menus
      perms.value = new Set(data.perms)
      loaded.value = true
    } catch {
      // 拉取失败按无权限处理（进入管理区时会被 404 同形拦截）
      menus.value = []
      perms.value = new Set()
    }
  }

  function reset() {
    menus.value = []
    perms.value = new Set()
    loaded.value = false
  }

  /** 按钮级权限：'*' 为全量（未绑定角色的管理员） */
  function has(perm: string): boolean {
    return perms.value.has('*') || perms.value.has(perm)
  }

  /** 菜单树中 path 的可见性（叶子 menu 有 path；dir 需有可见子节点） */
  function menuVisible(path: string): boolean {
    const walk = (nodes: MenuNode[]): boolean =>
      nodes.some((n) => (n.path === path ? true : walk(n.children)))
    return walk(menus.value)
  }

  return { menus, perms, loaded, load, reset, has, menuVisible }
})
