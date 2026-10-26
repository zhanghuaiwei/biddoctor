<template>
  <div style="max-width: 420px; margin: 12vh auto; background: #fff; padding: 40px; border-radius: 8px">
    <h2 style="margin-top: 0">标书废检 · 登录</h2>
    <el-form label-position="top">
      <el-form-item label="邮箱">
        <el-input v-model="email" placeholder="you@example.com" />
      </el-form-item>
      <el-form-item label="验证码">
        <div style="display: flex; gap: 8px; width: 100%">
          <el-input v-model="code" placeholder="6 位验证码" />
          <el-button :disabled="cooling > 0" @click="sendCode">
            {{ cooling > 0 ? `${cooling}s` : '获取验证码' }}
          </el-button>
        </div>
      </el-form-item>
      <el-button type="primary" style="width: 100%" :loading="loading" @click="login">登录 / 注册</el-button>
    </el-form>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api, setToken } from '../api'

const router = useRouter()
const email = ref('')
const code = ref('')
const loading = ref(false)
const cooling = ref(0)

async function sendCode() {
  if (!email.value) return ElMessage.warning('请先输入邮箱')
  try {
    const res = await api('/auth/email-code', {
      method: 'POST',
      body: JSON.stringify({ email: email.value }),
    })
    if (res.dev_code) ElMessage.info(`开发环境验证码：${res.dev_code}`)
    else ElMessage.success('验证码已发送，请查收邮箱')
    cooling.value = 60
    const t = setInterval(() => {
      cooling.value -= 1
      if (cooling.value <= 0) clearInterval(t)
    }, 1000)
  } catch (e: any) {
    ElMessage.error(e.message)
  }
}

async function login() {
  loading.value = true
  try {
    const res = await api('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email: email.value, code: code.value }),
    })
    setToken(res.token)
    localStorage.setItem('fj_email', res.user.email)
    router.push('/projects')
  } catch (e: any) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}
</script>
