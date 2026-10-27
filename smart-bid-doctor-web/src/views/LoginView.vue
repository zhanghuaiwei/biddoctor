<!-- 登录页（02 §9.1）：邮箱验证码登录。
     流程：发码（60s 倒计时，useCountdown 卸载清理）→ 输码登录 → auth store 写入 token →
     按登录前 URL 回跳（client.ts 401 时携带的 redirect）。dev 环境固定码 123456 由后端返回。 -->
<template>
  <div class="login-card">
    <h2 class="title">标书废检 · 登录</h2>
    <el-form ref="formRef" label-position="top" :model="form" :rules="rules" @submit.prevent>
      <el-form-item label="邮箱" prop="email">
        <el-input v-model="form.email" placeholder="you@example.com" @keyup.enter="sendCode" />
      </el-form-item>
      <el-form-item label="验证码" prop="code">
        <div class="code-row">
          <el-input v-model="form.code" placeholder="6 位验证码" @keyup.enter="login" />
          <el-button :disabled="remaining > 0" @click="sendCode">
            {{ remaining > 0 ? `${remaining}s 后重发` : '获取验证码' }}
          </el-button>
        </div>
      </el-form-item>
      <el-button type="primary" class="submit" :loading="loading" @click="login">
        登录 / 注册
      </el-button>
    </el-form>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { FormInstance, FormRules } from 'element-plus'

import { login as loginApi, requestEmailCode } from '@/api/auth'
import { notifyApiError } from '@/api/client'
import { useCountdown } from '@/composables/useCountdown'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const formRef = ref<FormInstance>()
const form = reactive({ email: '', code: '' })
const rules: FormRules = {
  email: [{ required: true, message: '请输入邮箱', trigger: 'blur' }],
  code: [{ required: true, message: '请输入验证码', trigger: 'blur' }],
}
const loading = ref(false)
const { remaining, start } = useCountdown(60)

async function sendCode() {
  if (!form.email) return ElMessage.warning('请先输入邮箱')
  try {
    const res = await requestEmailCode(form.email)
    if (res.dev_code) ElMessage.info(`开发环境验证码：${res.dev_code}`)
    else ElMessage.success('验证码已发送，请查收邮箱')
    start()
  } catch (e) {
    notifyApiError(e, '验证码发送失败')
  }
}

async function login() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  try {
    const res = await loginApi(form.email, form.code)
    auth.login(res.token, res.user.email)
    // 支持登录后回跳来源页（api/client 401 时携带 redirect）
    router.push(typeof route.query.redirect === 'string' ? route.query.redirect : '/projects')
  } catch (e) {
    notifyApiError(e, '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped lang="less">
.login-card {
  max-width: 420px;
  margin: 12vh 16px 24px;
  background: #fff;
  padding: 40px;
  border-radius: @radius;
  box-shadow: @shadow-lg;
  // 品牌识别：顶部强调条
  border-top: 3px solid @c-accent;
  // 首屏进场：上浮淡入（配合路由 page 过渡，双层节奏更丝滑）
  animation: rise-in @dur-slow @ease-out both;

  @media (min-width: @bp-sm) {
    margin: 12vh auto;
  }

  @media (max-width: @bp-sm) {
    padding: 24px 20px;
    // 移动端去掉顶部条与阴影，避免小屏厚重感
    border-top: none;
    box-shadow: @shadow-sm;
  }
}

.title {
  margin-top: 0;
}

.code-row {
  display: flex;
  gap: 8px;
  width: 100%;
}

.submit {
  width: 100%;
  margin-top: 8px;
}
</style>
