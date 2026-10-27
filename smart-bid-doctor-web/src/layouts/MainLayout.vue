<template>
  <el-container style="height: 100vh">
    <el-aside width="200px" style="background: #16233b">
      <div style="color: #fff; font-weight: 700; padding: 20px 16px; font-size: 18px">
        标书废检
      </div>
      <el-menu router :default-active="$route.path" background-color="#16233b" text-color="#c9d4e4"
        active-text-color="#ffffff" style="border: none">
        <el-menu-item index="/projects">项目列表</el-menu-item>
        <el-menu-item index="/quota">次数与订单</el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header style="display: flex; align-items: center; justify-content: flex-end; background: #fff">
        <span style="margin-right: 16px; color: #66707c; font-size: 13px">{{ email }}</span>
        <el-button size="small" @click="logout">退出登录</el-button>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { clearToken } from '../api'

const router = useRouter()
const email = ref(localStorage.getItem('fj_email') || '')

function logout() {
  clearToken()
  localStorage.removeItem('fj_email')
  router.push('/login')
}
</script>
