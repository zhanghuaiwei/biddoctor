/**
 * 登录态 store（Pinia setup store）——全局状态唯一归口 src/stores/。
 * - 可持久：token/email 经 constants/storage.ts 的 STORAGE_KEYS 写 localStorage，
 *   刷新自动恢复（键名管理权仍归口 constants，不引持久化插件）；
 * - 可扩展：新增全局状态按同模式加 store 文件（auth/quota/...）；
 * - 非组件模块（router 守卫、api client）可在函数体内直接 useAuthStore()，
 *   但禁止模块顶层调用（pinia 尚未随 app 激活）。
 */
import { ref } from 'vue'
import { defineStore } from 'pinia'

import { clearToken, getToken, setToken, STORAGE_KEYS } from '@/constants/storage'

export const useAuthStore = defineStore('auth', () => {
  // 初始值从 localStorage 恢复（持久化读取侧）
  const token = ref<string | null>(getToken())
  const email = ref<string>(localStorage.getItem(STORAGE_KEYS.email) ?? '')

  /** 登录成功：写 localStorage（持久化）+ 更新内存态 */
  function login(newToken: string, newEmail: string) {
    setToken(newToken)
    localStorage.setItem(STORAGE_KEYS.email, newEmail)
    token.value = newToken
    email.value = newEmail
  }

  /** 退出/会话过期：清 localStorage + 复位内存态 */
  function logout() {
    clearToken()
    localStorage.removeItem(STORAGE_KEYS.email)
    token.value = null
    email.value = ''
  }

  return { token, email, login, logout }
})
