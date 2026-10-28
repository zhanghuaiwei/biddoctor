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
        { path: 'reports/:id', component: () => import('./views/ReportDetailView.vue') },
      ],
    },
    {
      // 管理端路由区（05 §2.3）：静态注册组件，导航由 /me/menus 驱动；
      // 无权限访问由后端 404 同形拦截（api/client 统一错误体透出）
      path: '/admin',
      component: () => import('./layouts/AdminLayout.vue'),
      children: [
        { path: '', redirect: '/admin/dashboard' },
        { path: 'dashboard', component: () => import('./views/admin/AdminDashboardView.vue') },
        { path: 'orders', component: () => import('./views/admin/AdminOrdersView.vue') },
        { path: 'subs', component: () => import('./views/admin/AdminSubsView.vue') },
        { path: 'users', component: () => import('./views/admin/AdminUsersView.vue') },
        { path: 'tasks', component: () => import('./views/admin/AdminTasksView.vue') },
        { path: 'stats', component: () => import('./views/admin/AdminStatsView.vue') },
        { path: 'attachments', component: () => import('./views/admin/AdminAttachmentsView.vue') },
        { path: 'configs', component: () => import('./views/admin/AdminConfigsView.vue') },
        { path: 'dicts', component: () => import('./views/admin/AdminDictsView.vue') },
        { path: 'notices', component: () => import('./views/admin/AdminNoticesView.vue') },
        { path: 'jobs', component: () => import('./views/admin/AdminJobsView.vue') },
        { path: 'alerts', component: () => import('./views/admin/AdminAlertsView.vue') },
        { path: 'logs-audit', component: () => import('./views/admin/AdminLogsAuditView.vue') },
        { path: 'logs-login', component: () => import('./views/admin/AdminLogsLoginView.vue') },
        { path: 'logs-oper', component: () => import('./views/admin/AdminLogsOperView.vue') },
        { path: 'orgs', component: () => import('./views/admin/AdminOrgsView.vue') },
        { path: 'roles', component: () => import('./views/admin/AdminRolesView.vue') },
        { path: 'legal', component: () => import('./views/admin/AdminLegalView.vue') },
        { path: 'ai', component: () => import('./views/admin/AdminAiView.vue') },
        { path: 'rules', component: () => import('./views/admin/AdminRulesView.vue') },
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
  if (to.path.startsWith('/admin/')) {
    document.title = '管理控制台 · 标书废检'
    return
  }
  document.title = to.path.startsWith('/projects/')
    ? '项目详情 · 标书废检'
    : to.path.startsWith('/reports/')
      ? '报告详情 · 标书废检'
      : `${titles[to.path] ?? '控制台'} · 标书废检`
})

export default router
