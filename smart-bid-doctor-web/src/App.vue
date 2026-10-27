<template>
  <!-- 顶层路由过渡：登录页 ↔ 主布局 之间淡入上浮（样式类在 styles/global.less） -->
  <router-view v-slot="{ Component }">
    <transition name="page" mode="out-in">
      <component :is="Component" />
    </transition>
  </router-view>
  <!-- 主题配置抽屉：全局唯一实例，顶栏/登录页仅负责唤出（状态归口 theme store） -->
  <ThemeDrawer />
</template>

<script setup lang="ts">
import ThemeDrawer from '@/components/ThemeDrawer.vue'
</script>
