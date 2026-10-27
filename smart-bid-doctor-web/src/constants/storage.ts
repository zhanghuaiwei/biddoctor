/** localStorage 键与访问器归口（浏览器本地仅存非敏感展示信息；token 泄露面以最短会话为限） */

export const STORAGE_KEYS = {
  token: 'sbd_token',
  email: 'sbd_email',
  theme: 'sbd_theme',
} as const

export const getToken = (): string | null => localStorage.getItem(STORAGE_KEYS.token)

export const setToken = (t: string): void => localStorage.setItem(STORAGE_KEYS.token, t)

export const clearToken = (): void => localStorage.removeItem(STORAGE_KEYS.token)
