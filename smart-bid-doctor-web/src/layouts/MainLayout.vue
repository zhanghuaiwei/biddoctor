<!-- 主布局：深色品牌侧栏 + 毛玻璃顶栏（面包屑/额度徽标/用户区）。
     侧栏 <@bp-md 折叠为抽屉；顶栏左侧 hamburger 唤出。视觉令牌统一取 variables.less。 -->
<template>
  <el-container class="layout">
    <!-- 导航布局可配置：侧边栏（默认）/ 顶部导航 -->
    <el-aside v-if="theme.navLayout === 'side'" class="aside" width="236px">
      <div class="brand">
        <span class="brand-mark" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 3l7 3v5c0 4.4-3 8.1-7 10-4-1.9-7-5.6-7-10V6l7-3z" />
            <path d="M9 12l2 2 4-4" />
          </svg>
        </span>
        <span class="brand-copy">
          <strong>标书废检</strong>
          <small>BID RISK INSPECTOR</small>
        </span>
      </div>

      <nav class="nav">
        <p class="nav-label">工作台</p>
        <el-menu router :default-active="$route.path" class="menu">
          <el-menu-item index="/projects">
            <span class="nav-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
                <path d="M4 5h16" />
                <path d="M4 12h16" />
                <path d="M4 19h10" />
                <circle cx="18" cy="19" r="2" />
              </svg>
            </span>
            <span>项目检查</span>
          </el-menu-item>
          <el-menu-item index="/quota">
            <span class="nav-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="6" width="18" height="13" rx="2.5" />
                <path d="M3 10h18" />
                <path d="M7 15h4" />
              </svg>
            </span>
            <span>次数与订单</span>
          </el-menu-item>
        </el-menu>
      </nav>

      <footer class="aside-footer">
        <p class="aside-note">AI 自查 · 结论留痕 · 风险可溯</p>
        <p class="aside-version">v0.1 · MVP</p>
      </footer>
    </el-aside>

    <el-drawer v-model="menuOpen" direction="ltr" size="236px" :with-header="false" class="mobile-menu">
      <div class="brand brand-dark">
        <span class="brand-mark" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 3l7 3v5c0 4.4-3 8.1-7 10-4-1.9-7-5.6-7-10V6l7-3z" />
            <path d="M9 12l2 2 4-4" />
          </svg>
        </span>
        <span class="brand-copy">
          <strong>标书废检</strong>
          <small>BID RISK INSPECTOR</small>
        </span>
      </div>
      <el-menu router :default-active="$route.path" class="menu menu-drawer" @select="menuOpen = false">
        <el-menu-item index="/projects">
          <span class="nav-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
              <path d="M4 5h16" />
              <path d="M4 12h16" />
              <path d="M4 19h10" />
              <circle cx="18" cy="19" r="2" />
            </svg>
          </span>
          <span>项目检查</span>
        </el-menu-item>
        <el-menu-item index="/quota">
          <span class="nav-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
              <rect x="3" y="6" width="18" height="13" rx="2.5" />
              <path d="M3 10h18" />
              <path d="M7 15h4" />
            </svg>
          </span>
          <span>次数与订单</span>
        </el-menu-item>
      </el-menu>
    </el-drawer>

    <el-container class="body">
      <el-header class="header">
        <el-button class="menu-toggle" text @click="menuOpen = true" aria-label="打开菜单">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" aria-hidden="true">
            <path d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </el-button>

        <div v-if="theme.navLayout === 'top'" class="brand brand-top">
          <span class="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 3l7 3v5c0 4.4-3 8.1-7 10-4-1.9-7-5.6-7-10V6l7-3z" />
              <path d="M9 12l2 2 4-4" />
            </svg>
          </span>
          <span class="brand-name">标书废检</span>
        </div>

        <el-menu
          v-if="theme.navLayout === 'top'"
          router
          mode="horizontal"
          :default-active="$route.path"
          :ellipsis="false"
          class="top-menu"
        >
          <el-menu-item index="/projects">项目检查</el-menu-item>
          <el-menu-item index="/quota">次数与订单</el-menu-item>
        </el-menu>

        <div v-if="theme.navLayout === 'side'" class="crumb" aria-label="当前位置">
          <span class="crumb-root">工作台</span>
          <span class="crumb-sep">/</span>
          <span class="crumb-current">{{ pageTitle }}</span>
        </div>

        <span class="header-spacer" />
        <QuotaBadge ref="quotaBadge" />
        <span class="header-divider" aria-hidden="true" />
        <router-link v-if="isAdmin" class="admin-entry" to="/admin/dashboard">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <rect x="3" y="4" width="18" height="14" rx="2" />
            <path d="M3 9h18" />
            <path d="M8 14h8" />
          </svg>
          管理控制台
        </router-link>
        <div class="user">
          <span class="avatar" aria-hidden="true">{{ initial }}</span>
          <span class="user-email">{{ email }}</span>
        </div>
        <el-tooltip content="外观设置" placement="bottom" :show-after="300">
          <el-button class="icon-btn" text circle aria-label="外观设置" @click="theme.openDrawer()">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <circle cx="12" cy="12" r="3.2" />
              <path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-1.8-.3 1.6 1.6 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.2a1.6 1.6 0 0 0-1-1.5 1.6 1.6 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.6 1.6 0 0 0 .3-1.8 1.6 1.6 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.2a1.6 1.6 0 0 0 1.5-1 1.6 1.6 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 1.8.3H9a1.6 1.6 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.2a1.6 1.6 0 0 0 1 1.5 1.6 1.6 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0-.3 1.8V9a1.6 1.6 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.2a1.6 1.6 0 0 0-1.5 1z" />
            </svg>
          </el-button>
        </el-tooltip>
        <el-tooltip content="退出登录" placement="bottom" :show-after="300">
          <el-button class="icon-btn" text circle aria-label="退出登录" @click="logout">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M10 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h4" />
              <path d="M15 8l4 4-4 4" />
              <path d="M19 12H9" />
            </svg>
          </el-button>
        </el-tooltip>
      </el-header>

      <el-main class="main">
        <NoticeBanner />
        <!-- 子路由切换过渡（key 强制按路径重建，项目详情换 ID 也触发进场） -->
        <router-view v-slot="{ Component }">
          <transition name="page" mode="out-in">
            <component :is="Component" :key="$route.path" />
          </transition>
        </router-view>
      </el-main>
    </el-container>

    <!-- 协议签署门禁（05 §8：生效版未签署时强制弹层） -->
    <AgreementGate />
  </el-container>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { usePermissionStore } from '@/stores/permission'
import QuotaBadge from '@/components/QuotaBadge.vue'
import NoticeBanner from '@/components/NoticeBanner.vue'
import AgreementGate from '@/components/AgreementGate.vue'
import { confirmAction } from '@/utils/confirm'

const router = useRouter()
const route = useRoute()
// storeToRefs 解构保持响应性（email 展示随登录态实时更新）
const { email } = storeToRefs(useAuthStore())
const theme = useThemeStore()
const permission = usePermissionStore()
const menuOpen = ref(false)
const quotaBadge = ref<InstanceType<typeof QuotaBadge>>()

// 管理端入口（05 §2.3）：登录后拉取权限点，非 admin 不渲染
const isAdmin = computed(() => permission.perms.size > 0)

onMounted(() => {
  void permission.load()
})

// 顶栏面包屑末级（详情页统一按前缀判定，避免路由参数散落判断）
const PAGE_TITLES: Record<string, string> = {
  '/projects': '项目检查',
  '/quota': '次数与订单',
}
const pageTitle = computed(() =>
  route.path.startsWith('/projects/') ? '项目详情' : (PAGE_TITLES[route.path] ?? '工作台'),
)

const initial = computed(() => (email.value ? email.value.slice(0, 1).toUpperCase() : 'U'))

async function logout() {
  const ok = await confirmAction('退出后需重新登录才能继续查看项目与报告。', {
    title: '退出登录',
    confirmText: '退出',
  })
  if (!ok) return
  useAuthStore().logout()
  router.push('/login')
}
</script>

<style scoped lang="less">
.layout {
  min-height: 100vh;
}

// ---- 侧栏 ----
.aside {
  display: flex;
  flex-direction: column;
  padding: 20px 14px;
  background: @c-brand-grad;
  color: @c-brand-text;

  @media (max-width: @bp-md) {
    display: none;
  }
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 8px 22px;
  border-bottom: 1px solid @c-brand-line;
}

.brand-mark {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: @radius;
  background: linear-gradient(150deg, var(--app-accent-light), var(--app-accent-dark));
  box-shadow: @shadow-accent-sm;
  color: #fff;

  svg {
    width: 19px;
    height: 19px;
  }
}

.brand-copy {
  display: flex;
  flex-direction: column;
  line-height: 1.3;

  strong {
    font-size: 16px;
    font-weight: 700;
    letter-spacing: 0.04em;
  }

  small {
    margin-top: 2px;
    font-size: 9px;
    letter-spacing: 0.14em;
    color: @c-brand-text-sub;
  }
}

.nav {
  flex: 1;
  padding-top: 18px;
}

// ---- 顶部导航布局（navLayout = top 时顶栏内渲染）----
.brand-top {
  padding: 0;
  border-bottom: none;
  gap: 8px;
  margin-right: 4px;

  .brand-mark {
    width: 30px;
    height: 30px;
    border-radius: @radius-sm;

    svg {
      width: 17px;
      height: 17px;
    }
  }

  @media (max-width: @bp-md) {
    display: none;
  }
}

.brand-name {
  font-size: @fs-h3;
  font-weight: 700;
  letter-spacing: 0.04em;
  white-space: nowrap;
  color: @c-text;
}

.top-menu {
  --el-menu-bg-color: transparent;
  --el-menu-text-color: @c-text-sub;
  --el-menu-active-color: var(--app-accent);
  --el-menu-hover-bg-color: transparent;
  --el-menu-hover-text-color: var(--app-accent);
  --el-menu-horizontal-height: @header-h;
  border-bottom: none;
  margin-left: 8px;

  :deep(.el-menu-item) {
    height: @header-h;
    padding: 0 14px;
    font-size: @fs-sm;
    border-bottom: 2px solid transparent;
    transition:
      color @dur-fast @ease-out,
      border-color @dur-fast @ease-out;
  }

  :deep(.el-menu-item.is-active) {
    font-weight: 600;
    border-bottom-color: var(--app-accent);
  }

  @media (max-width: @bp-md) {
    display: none;
  }
}

.nav-label {
  margin: 0 0 8px;
  padding: 0 12px;
  font-size: 10px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: fade(#fff, 38%);
}

// 菜单配色经 Element Plus CSS 变量注入，色值统一取 variables.less 导航令牌
.menu {
  --el-menu-bg-color: transparent;
  --el-menu-text-color: @c-nav-text;
  --el-menu-active-color: #fff;
  --el-menu-hover-bg-color: @c-nav-hover-bg;
  --el-menu-hover-text-color: #fff;
  --el-menu-item-height: 42px;
  border: none;

  :deep(.el-menu-item) {
    margin-bottom: 4px;
    border-radius: @radius-sm;
    font-size: @fs-sm;
    transition:
      background-color @dur-base @ease-out,
      color @dur-base @ease-out,
      box-shadow @dur-base @ease-out;

    &.is-active {
      background: @c-nav-active-bg;
      font-weight: 600;
      // 选中项左侧强调条（inset 阴影模拟，不占布局宽度）
      box-shadow: inset 3px 0 0 @c-accent;
    }
  }
}

.nav-icon {
  display: inline-flex;
  margin-right: 10px;
  opacity: 0.85;

  svg {
    width: 17px;
    height: 17px;
  }
}

.aside-footer {
  padding: 16px 12px 4px;
  border-top: 1px solid @c-brand-line;
}

.aside-note {
  margin: 0;
  font-size: @fs-xs;
  color: @c-brand-text-sub;
}

.aside-version {
  margin: 4px 0 0;
  font-size: 10px;
  letter-spacing: 0.08em;
  color: fade(#fff, 32%);
}

// ---- 顶栏 ----
.body {
  min-width: 0;
}

.header {
  display: flex;
  align-items: center;
  height: @header-h;
  padding: 0 24px;
  gap: 10px;
  background: var(--app-header-bg);
  backdrop-filter: saturate(180%) blur(12px);
  border-bottom: 1px solid @c-line-soft;
  // 顶栏压在滚动内容之上，滚动时阴影分界
  position: relative;
  z-index: 10;

  @media (max-width: @bp-sm) {
    padding: 0 14px;
  }
}

.menu-toggle {
  display: none;
  padding: 6px;

  svg {
    width: 20px;
    height: 20px;
  }

  @media (max-width: @bp-md) {
    display: inline-flex;
  }
}

.crumb {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: @fs-sm;
  min-width: 0;
}

.crumb-root {
  color: @c-text-muted;
}

.crumb-sep {
  color: @c-line;
}

.crumb-current {
  font-weight: 600;
  color: @c-text;
}

.header-spacer {
  flex: 1;
}

.header-divider {
  width: 1px;
  height: 20px;
  margin: 0 4px;
  background: @c-line;

  @media (max-width: @bp-sm) {
    display: none;
  }
}

.user {
  display: flex;
  align-items: center;
  gap: 8px;
}

.admin-entry {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border-radius: @radius-pill;
  background: @c-accent-soft;
  color: @c-accent;
  font-size: @fs-xs;
  font-weight: 600;
  text-decoration: none;
  transition: box-shadow @dur-base @ease-out, transform @dur-base @ease-out;

  svg {
    width: 14px;
    height: 14px;
  }

  &:hover {
    box-shadow: @shadow-accent-sm;
    transform: translateY(-1px);
  }

  @media (max-width: @bp-md) {
    display: none;
  }
}

.avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: @c-accent-soft;
  color: @c-accent;
  font-size: @fs-sm;
  font-weight: 700;
}

.user-email {
  color: @c-text-sub;
  font-size: @fs-sm;

  @media (max-width: @bp-sm) {
    display: none;
  }
}

.icon-btn {
  color: @c-text-muted;
  padding: 6px;

  svg {
    width: 18px;
    height: 18px;
  }

  &:hover {
    color: var(--app-accent);
  }
}

.main {
  padding: 0;
}

// ---- 移动端抽屉（深色同侧栏） ----
.brand-dark {
  padding: 24px 12px 20px;
  border-bottom: none;
}

.mobile-menu {
  :deep(.el-drawer__body) {
    padding: 0 14px;
    background: @c-brand-grad;
  }
}

.menu-drawer {
  --el-menu-bg-color: transparent;
}
</style>
