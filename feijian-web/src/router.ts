import { createRouter, createWebHistory } from 'vue-router'
import { getToken } from './api'

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
  ],
})

router.beforeEach((to) => {
  if (to.path !== '/login' && !getToken()) return '/login'
})

export default router
