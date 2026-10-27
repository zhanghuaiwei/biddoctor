<template>
  <!-- 顶层路由过渡：登录页 ↔ 主布局 之间淡入上浮（样式类在 styles/global.less） -->
  <router-view v-slot="{ Component }">
    <transition name="page" mode="out-in">
      <component :is="Component" />
    </transition>
  </router-view>
</template>
