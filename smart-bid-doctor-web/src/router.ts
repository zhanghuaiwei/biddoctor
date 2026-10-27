import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: () => import('./views/LoginView.vue') },
    {
      path: '/',
      component: () => import('./layouts/MainLayout.vue'),
      children: [
        { path: '', redirect: '/projects' },
        { path: 'projects', component: () => import('./views/ProjectsView.vue') },
        { path: 'projects/:id', component: () => import('./views/ProjectDetailView.vue') },
        { path: 'quota', component: () => import('./views/QuotaView.vue') },
      ],
    },
    // 兜底 404：无匹配路由时渲染引导页（否则 vue-router 空白）
    { path: '/:pathMatch(.*)*', component: () => import('./views/NotFoundView.vue') },
  ],
  scrollBehavior: () => ({ top: 0 }),
})

router.beforeEach((to) => {
  // 仅判本地 token 存在性（登录态归口 auth store）；有效性由 api/client 统一 401 兜底跳转
  // 守卫运行于 pinia 激活后，函数体内 useAuthStore() 安全
  if (to.path !== '/login' && !useAuthStore().token) {
    return { path: '/login', query: to.fullPath !== '/' ? { redirect: to.fullPath } : {} }
  }
})

router.afterEach((to) => {
  const titles: Record<string, string> = {
    '/login': '登录',
    '/projects': '项目列表',
    '/quota': '次数与订单',
  }
  document.title = to.path.startsWith('/projects/')
    ? '项目详情 · 标书废检'
    : `${titles[to.path] ?? '控制台'} · 标书废检`
})

export default router
