<!-- 管理端布局（05 §2.3）：/admin 路由区，侧栏由 /me/menus 菜单树驱动（权限点过滤），
     视觉延续主站深色品牌侧栏 + 毛玻璃顶栏。无权限访问由后端 404 同形拦截。 -->
<template>
  <el-container class="layout">
    <el-aside class="aside" width="236px">
      <div class="brand">
        <span class="brand-mark" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 3l7 3v5c0 4.4-3 8.1-7 10-4-1.9-7-5.6-7-10V6l7-3z" />
            <path d="M9 12l2 2 4-4" />
          </svg>
        </span>
        <span class="brand-copy">
          <strong>管理控制台</strong>
          <small>ADMIN CONSOLE</small>
        </span>
      </div>

      <nav class="nav">
        <template v-for="group in navGroups" :key="group.name">
          <p class="nav-label">{{ group.name }}</p>
          <el-menu router :default-active="$route.path" class="menu">
            <el-menu-item v-for="item in group.items" :key="item.path" :index="item.path">
              <span>{{ item.name }}</span>
            </el-menu-item>
          </el-menu>
        </template>
        <p v-if="!navGroups.length" class="nav-empty">暂无可见菜单</p>
      </nav>

      <footer class="aside-footer">
        <p class="aside-note">平台化管理 · 全操作留痕</p>
        <p class="aside-version">v2.0 · Platform</p>
      </footer>
    </el-aside>

    <el-drawer v-model="menuOpen" direction="ltr" size="236px" :with-header="false" class="mobile-menu">
      <template v-for="group in navGroups" :key="group.name">
        <p class="nav-label drawer-label">{{ group.name }}</p>
        <el-menu router :default-active="$route.path" class="menu menu-drawer" @select="menuOpen = false">
          <el-menu-item v-for="item in group.items" :key="item.path" :index="item.path">
            <span>{{ item.name }}</span>
          </el-menu-item>
        </el-menu>
      </template>
    </el-drawer>

    <el-container class="body">
      <el-header class="header">
        <el-button class="menu-toggle" text @click="menuOpen = true" aria-label="打开菜单">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" aria-hidden="true">
            <path d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </el-button>

        <div class="crumb" aria-label="当前位置">
          <span class="crumb-root">管理控制台</span>
          <span class="crumb-sep">/</span>
          <span class="crumb-current">{{ pageTitle }}</span>
        </div>

        <span class="header-spacer" />
        <router-link class="back-workbench" to="/projects">返回工作台</router-link>
        <el-tooltip v-if="unacked > 0" content="有未确认告警" placement="bottom" :show-after="300">
          <router-link class="alert-dot" to="/admin/alerts" aria-label="未确认告警">
            <span class="pulse-dot" aria-hidden="true" />
            <span class="alert-count">{{ unacked > 99 ? '99+' : unacked }}</span>
          </router-link>
        </el-tooltip>
        <span class="header-divider" aria-hidden="true" />
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
      </el-header>

      <el-main class="main">
        <router-view v-slot="{ Component }">
          <transition name="page" mode="out-in">
            <component :is="Component" :key="$route.path" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { storeToRefs } from 'pinia'

import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { usePermissionStore } from '@/stores/permission'
import { listAlerts } from '@/api/admin'

const route = useRoute()
const { email } = storeToRefs(useAuthStore())
const theme = useThemeStore()
const permission = usePermissionStore()
const menuOpen = ref(false)
const unacked = ref(0)

onMounted(() => {
  void permission.load()
  void refreshUnacked()
})

watch(() => route.path, () => void refreshUnacked())

async function refreshUnacked() {
  try {
    const data = await listAlerts({ acked: false, limit: 1 })
    unacked.value = data.unacked
  } catch {
    unacked.value = 0
  }
}

// 菜单树 → 扁平导航分组：dir 为分组标题，menu 叶子按 path 注册
interface NavItem { name: string; path: string }
const navGroups = computed(() => {
  const out: Array<{ name: string; items: NavItem[] }> = []
  const walk = (nodes: typeof permission.menus) => {
    for (const node of nodes) {
      if (node.type === 'dir') {
        const items: NavItem[] = []
        const collect = (children: typeof node.children) => {
          for (const c of children) {
            if (c.type === 'menu' && c.path) items.push({ name: c.name, path: c.path })
            else if (c.type === 'dir') collect(c.children)
          }
        }
        collect(node.children)
        if (items.length) out.push({ name: node.name, items })
      } else if (node.type === 'menu' && node.path) {
        out.push({ name: node.name, items: [{ name: node.name, path: node.path }] })
      }
    }
  }
  walk(permission.menus)
  return out
})

const pageTitle = computed(() => {
  for (const g of navGroups.value) {
    const hit = g.items.find((i) => i.path === route.path)
    if (hit) return hit.name
  }
  return '管理控制台'
})

const initial = computed(() => (email.value ? email.value.slice(0, 1).toUpperCase() : 'A'))
</script>

<style scoped lang="less">
.layout {
  min-height: 100vh;
}

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
  overflow-y: auto;
}

.nav-label {
  margin: 14px 0 6px;
  padding: 0 12px;
  font-size: 10px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: fade(#fff, 38%);

  &:first-child {
    margin-top: 0;
  }
}

.nav-empty {
  padding: 0 12px;
  font-size: @fs-sm;
  color: fade(#fff, 45%);
}

.menu {
  --el-menu-bg-color: transparent;
  --el-menu-text-color: @c-nav-text;
  --el-menu-active-color: #fff;
  --el-menu-hover-bg-color: @c-nav-hover-bg;
  --el-menu-hover-text-color: #fff;
  --el-menu-item-height: 38px;
  border: none;

  :deep(.el-menu-item) {
    margin-bottom: 3px;
    border-radius: @radius-sm;
    font-size: @fs-sm;
    transition:
      background-color @dur-base @ease-out,
      color @dur-base @ease-out,
      box-shadow @dur-base @ease-out;

    &.is-active {
      background: @c-nav-active-bg;
      font-weight: 600;
      box-shadow: inset 3px 0 0 @c-accent;
    }
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

.back-workbench {
  font-size: @fs-sm;
  color: @c-text-sub;
  text-decoration: none;
  transition: color @dur-fast @ease-out;

  &:hover {
    color: var(--app-accent);
  }
}

.alert-dot {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: @radius-pill;
  background: @c-accent-soft;
  color: @c-accent;
  text-decoration: none;
  font-size: @fs-xs;
  font-weight: 600;
}

.alert-count {
  font-variant-numeric: tabular-nums;
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

.drawer-label {
  color: @c-text-muted;
}

.menu-drawer {
  --el-menu-text-color: @c-text-sub;
  --el-menu-active-color: @c-accent;
  --el-menu-hover-bg-color: @c-accent-soft;
}
</style>
