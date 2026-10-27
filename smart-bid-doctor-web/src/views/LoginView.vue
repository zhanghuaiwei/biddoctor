<!-- 登录页（02 §9.1）：邮箱验证码登录。产品化分屏布局：左侧品牌区（Logo/Slogan/卖点/氛围光晕，
     级联进场），右侧表单区（大号输入 + CTA 悬停动效）；窄屏（<@bp-lg）品牌区折叠为顶部横幅。
     流程：发码（60s 倒计时，useCountdown 卸载清理）→ 输码登录 → auth store 写入 token →
     按登录前 URL 回跳（client.ts 401 时携带的 redirect）。dev 环境固定码 123456 由后端返回。 -->
<template>
  <div class="auth-layout">
    <!-- 品牌区：深色渐变底 + 双光晕漂浮装饰，内容级联进场（动画类见 global.less） -->
    <aside class="brand-panel">
      <div class="glow glow-accent" aria-hidden="true" />
      <div class="glow glow-cool" aria-hidden="true" />
      <div class="brand-inner cascade-in">
        <div class="brand-logo">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M12 3l7 3v5c0 4.4-3 8.1-7 10-4-1.9-7-5.6-7-10V6l7-3z" />
            <path d="M9 12l2 2 4-4" />
          </svg>
          <span>标书废检</span>
        </div>
        <h1 class="brand-slogan">AI 自查废标风险，<br />让每一份标书安心交付</h1>
        <ul class="brand-points">
          <li v-for="p in points" :key="p.title">
            <span class="point-icon" v-html="p.icon" />
            <div>
              <strong>{{ p.title }}</strong>
              <p>{{ p.desc }}</p>
            </div>
          </li>
        </ul>
      </div>
    </aside>

    <!-- 表单区：白底居中窄列，首屏上浮淡入 -->
    <main class="auth-main">
      <div class="login-card">
        <h2 class="title">欢迎回来</h2>
        <p class="subtitle">邮箱验证码登录，未注册邮箱将自动创建账号</p>
        <el-form ref="formRef" size="large" :model="form" :rules="rules" @submit.prevent>
          <el-form-item prop="email">
            <el-input v-model="form.email" placeholder="you@example.com" @keyup.enter="sendCode">
              <template #prefix>
                <svg class="input-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <rect x="3" y="5" width="18" height="14" rx="2" />
                  <path d="M3 7l9 6 9-6" />
                </svg>
              </template>
            </el-input>
          </el-form-item>
          <el-form-item prop="code">
            <div class="code-row">
              <el-input v-model="form.code" placeholder="6 位验证码" @keyup.enter="login">
                <template #prefix>
                  <svg class="input-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <rect x="4" y="10" width="16" height="10" rx="2" />
                    <path d="M8 10V7a4 4 0 0 1 8 0v3" />
                  </svg>
                </template>
              </el-input>
              <el-button class="code-btn" :disabled="remaining > 0" @click="sendCode">
                {{ remaining > 0 ? `${remaining}s 后重发` : '获取验证码' }}
              </el-button>
            </div>
          </el-form-item>
          <el-button type="primary" class="submit" :loading="loading" @click="login">
            登录 / 注册
          </el-button>
        </el-form>
        <p class="footer-note">© 2026 标书废检 · 标书废标风险 AI 自查</p>
      </div>
    </main>
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

// 品牌区卖点（静态展示文案；图标为内联 SVG，避免引入图标库依赖）
const icon = (paths: string) =>
  `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths}</svg>`
const points = [
  {
    title: '条款智能对照',
    desc: '招标文件与投标文件逐项比对，疑点自动定位原文',
    icon: icon('<path d="M9 11l2 2 4-4" /><path d="M5 4h14v16H5z" /><path d="M9 4V2h6v2" />'),
  },
  {
    title: '废标风险预警',
    desc: '命中风险点即时标注等级，处置建议一并给出',
    icon: icon('<path d="M12 4l9 16H3l9-16z" /><path d="M12 10v4" /><path d="M12 17h.01" />'),
  },
  {
    title: '报告全程留痕',
    desc: '审计链路完整可查，每一次结论都有据可依',
    icon: icon('<path d="M6 3h9l4 4v14H6z" /><path d="M14 3v5h5" /><path d="M9 13h7M9 17h7" />'),
  },
]

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
.auth-layout {
  display: flex;
  min-height: 100vh;
  background: #fff;

  @media (max-width: @bp-lg) {
    flex-direction: column;
  }
}

// ---- 品牌区 ----
.brand-panel {
  position: relative;
  flex: 0 0 44%;
  display: flex;
  align-items: center;
  padding: 64px 56px;
  background: @c-brand-grad;
  color: @c-brand-text;
  overflow: hidden;

  @media (max-width: @bp-lg) {
    flex: none;
    align-items: flex-start;
    padding: 36px 24px 28px;
  }
}

.glow {
  position: absolute;
  width: 320px;
  height: 320px;
  border-radius: 50%;
  filter: blur(64px);
  pointer-events: none;
  animation: float-drift @dur-ambient @ease-out infinite alternate;
}

.glow-accent {
  top: -90px;
  right: -70px;
  background: @c-brand-glow-accent;
}

.glow-cool {
  bottom: -110px;
  left: -80px;
  background: @c-brand-glow-cool;
  animation-delay: @dur-ambient / 2;
}

.brand-inner {
  position: relative;
  max-width: 440px;
}

.brand-logo {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 20px;
  font-weight: 700;
  letter-spacing: 1px;

  svg {
    width: 32px;
    height: 32px;
    color: @c-accent-light-5;
  }
}

.brand-slogan {
  margin: 28px 0 36px;
  font-size: 30px;
  line-height: 1.4;
  font-weight: 700;

  @media (max-width: @bp-lg) {
    margin: 16px 0 0;
    font-size: 21px;
  }
}

.brand-points {
  margin: 0;
  padding: 0;
  list-style: none;

  @media (max-width: @bp-lg) {
    // 窄屏品牌区折叠为横幅，卖点列表让位表单
    display: none;
  }

  li {
    display: flex;
    gap: 14px;
    padding: 14px 0;

    & + li {
      border-top: 1px solid rgba(255, 255, 255, 0.08);
    }
  }

  strong {
    font-size: 15px;
  }

  p {
    margin: 4px 0 0;
    font-size: 13px;
    line-height: 1.6;
    color: @c-brand-text-sub;
  }
}

.point-icon {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  border-radius: @radius;
  background: rgba(255, 255, 255, 0.08);
  color: @c-accent-light-5;

  :deep(svg) {
    width: 20px;
    height: 20px;
  }
}

// ---- 表单区 ----
.auth-main {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px 24px;

  @media (max-width: @bp-lg) {
    align-items: flex-start;
    padding-top: 40px;
  }
}

.login-card {
  width: 100%;
  max-width: 400px;
  // 首屏进场：上浮淡入（配合路由 page 过渡，双层节奏更丝滑）
  animation: rise-in @dur-slow @ease-out both;
}

.title {
  margin: 0;
  font-size: 26px;
}

.subtitle {
  margin: 8px 0 28px;
  font-size: 14px;
  color: @c-text-sub;
}

.input-icon {
  width: 16px;
  height: 16px;
  color: @c-text-sub;
}

.code-row {
  display: flex;
  gap: 8px;
  width: 100%;
}

.code-btn {
  // 固定最小宽度：倒计时文案切换时按钮不抖动
  min-width: 128px;
}

.submit {
  width: 100%;
  margin-top: 8px;
  font-weight: 600;
  letter-spacing: 2px;
  transition:
    transform @dur-fast @ease-out,
    box-shadow @dur-fast @ease-out;

  &:hover {
    transform: translateY(-1px);
    box-shadow: @shadow-accent;
  }

  &:active {
    transform: translateY(0);
  }
}

.footer-note {
  margin: 32px 0 0;
  font-size: 12px;
  text-align: center;
  color: @c-text-sub;
}
</style>
