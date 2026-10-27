/**
 * 登录态模块级单例（轻量替代 pinia：MVP 仅 token+email 两项状态；
 * 状态复杂化后再引 pinia，接口形态保持一致）。
 */
import { ref } from 'vue'

import { clearToken, getToken, setToken, STORAGE_KEYS } from '../constants/storage'

const token = ref<string | null>(getToken())
const email = ref<string>(localStorage.getItem(STORAGE_KEYS.email) ?? '')

export function useAuth() {
  function login(newToken: string, newEmail: string) {
    setToken(newToken)
    localStorage.setItem(STORAGE_KEYS.email, newEmail)
    token.value = newToken
    email.value = newEmail
  }

  function logout() {
    clearToken()
    localStorage.removeItem(STORAGE_KEYS.email)
    token.value = null
    email.value = ''
  }

  return { token, email, isLoggedIn: () => !!token.value, login, logout }
}
