<template>
  <el-container class="layout">
    <el-aside class="aside" width="200px">
      <div class="brand">标书废检</div>
      <!-- 菜单配色经 CSS 变量注入（见 .menu 样式），令牌归口 variables.less -->
      <el-menu router :default-active="$route.path" class="menu">
        <el-menu-item index="/projects">项目列表</el-menu-item>
        <el-menu-item index="/quota">次数与订单</el-menu-item>
      </el-menu>
    </el-aside>

    <el-drawer v-model="menuOpen" direction="ltr" size="220px" :with-header="false" class="mobile-menu">
      <div class="brand brand-dark">标书废检</div>
      <el-menu router :default-active="$route.path" @select="menuOpen = false">
        <el-menu-item index="/projects">项目列表</el-menu-item>
        <el-menu-item index="/quota">次数与订单</el-menu-item>
      </el-menu>
    </el-drawer>

    <el-container>
      <el-header class="header">
        <el-button class="menu-toggle" text @click="menuOpen = true" aria-label="打开菜单">
          菜单
        </el-button>
        <span class="header-spacer" />
        <QuotaBadge ref="quotaBadge" />
        <span class="user-email">{{ email }}</span>
        <el-button size="small" @click="logout">退出登录</el-button>
      </el-header>
      <el-main class="main">
        <!-- 子路由切换过渡（key 强制按路径重建，项目详情换 ID 也触发进场） -->
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
import { ref } from 'vue'
import { useRouter } from 'vue-router'

import { useAuth } from '@/composables/useAuth'
import QuotaBadge from '@/components/QuotaBadge.vue'

const router = useRouter()
const { email, logout: doLogout } = useAuth()
const menuOpen = ref(false)
const quotaBadge = ref<InstanceType<typeof QuotaBadge>>()

function logout() {
  doLogout()
  router.push('/login')
}
</script>

<style scoped lang="less">
.layout {
  height: 100vh;
}

.aside {
  background: @c-nav-bg;

  @media (max-width: @bp-md) {
    display: none;
  }
}

.brand {
  color: #fff;
  font-weight: 700;
  padding: 20px 16px;
  font-size: 18px;
  letter-spacing: 1px;
}

.brand-dark {
  color: @c-primary;
}

// 菜单配色经 Element Plus CSS 变量注入，色值统一取 variables.less 导航令牌
.menu {
  --el-menu-bg-color: @c-nav-bg;
  --el-menu-text-color: @c-nav-text;
  --el-menu-active-color: #fff;
  --el-menu-hover-bg-color: @c-nav-hover-bg;
  --el-menu-hover-text-color: #fff;
  border: none;

  :deep(.el-menu-item) {
    transition:
      background-color @dur-base @ease-out,
      color @dur-base @ease-out,
      box-shadow @dur-base @ease-out;

    &.is-active {
      background: @c-nav-active-bg;
      // 选中项左侧强调条（inset 阴影模拟，不占布局宽度）
      box-shadow: inset 3px 0 0 @c-accent;
    }
  }
}

.header {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  background: #fff;
  box-shadow: @shadow-sm;
  // 顶栏压在滚动内容之上，滚动时阴影分界
  position: relative;
  z-index: 10;
}

.menu-toggle {
  display: none;

  @media (max-width: @bp-md) {
    display: inline-flex;
  }
}

.header-spacer {
  flex: 1;
}

.user-email {
  color: @c-text-sub;
  font-size: 13px;

  @media (max-width: @bp-sm) {
    display: none;
  }
}

.main {
  padding: 0;
}
</style>
