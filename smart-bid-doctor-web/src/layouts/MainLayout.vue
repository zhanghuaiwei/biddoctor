<template>
  <el-container class="layout">
    <el-aside class="aside" width="200px">
      <div class="brand">标书废检</div>
      <el-menu
        router
        :default-active="$route.path"
        background-color="#16233b"
        text-color="#c9d4e4"
        active-text-color="#ffffff"
        class="menu"
      >
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
        <router-view />
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
  background: #16233b;

  @media (max-width: @bp-md) {
    display: none;
  }
}

.brand {
  color: #fff;
  font-weight: 700;
  padding: 20px 16px;
  font-size: 18px;
}

.brand-dark {
  color: @c-primary;
}

.menu {
  border: none;
}

.header {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  background: #fff;
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
