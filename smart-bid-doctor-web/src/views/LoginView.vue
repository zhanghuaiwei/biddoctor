<!-- 登录页（02 §9.1）：邮箱验证码登录。产品化分屏布局：左侧品牌区（Logo/Slogan/卖点/光晕/网格纹理，
     级联进场），右侧表单卡片（大号输入 + CTA 悬停动效）；窄屏（<@bp-lg）品牌区折叠为顶部横幅。
     流程：发码（60s 倒计时，useCountdown 卸载清理）→ 输码登录 → auth store 写入 token →
     按登录前 URL 回跳（client.ts 401 时携带的 redirect）。dev 环境固定码 123456 由后端返回。 -->
<template>
  <div class="auth-layout">
    <!-- 品牌区：深色渐变底 + 网格纹理 + 双光晕漂浮装饰，内容级联进场（动画类见 global.less） -->
    <aside class="brand-panel">
      <div class="glow glow-accent" aria-hidden="true" />
      <div class="glow glow-cool" aria-hidden="true" />
      <div class="brand-inner cascade-in">
        <div class="brand-logo">
          <span class="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 3l7 3v5c0 4.4-3 8.1-7 10-4-1.9-7-5.6-7-10V6l7-3z" />
              <path d="M9 12l2 2 4-4" />
            </svg>
          </span>
          <span class="brand-name">
            <strong>标书废检</strong>
            <small>BID RISK INSPECTOR</small>
          </span>
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

    <!-- 表单区：居中窄列卡片，首屏上浮淡入 -->
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
          <el-form-item prop="invite_code">
            <el-input v-model="form.invite_code" placeholder="邀请码（邀测期新账号必填，选填）" clearable>
              <template #prefix>
                <svg class="input-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <rect x="3" y="5" width="18" height="14" rx="2" />
                  <path d="M3 10h18" />
                  <path d="M9 15h6" />
                </svg>
              </template>
            </el-input>
          </el-form-item>
          <el-button type="primary" class="submit" :loading="loading" @click="login">
            登录 / 注册
          </el-button>
        </el-form>
        <div class="login-foot">
          <p class="footer-note">© 2026 标书废检 · 标书废标风险 AI 自查</p>
          <el-button text size="small" class="theme-entry" @click="theme.openDrawer()">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <circle cx="12" cy="12" r="3.2" />
              <path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-1.8-.3 1.6 1.6 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.2a1.6 1.6 0 0 0-1-1.5 1.6 1.6 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.6 1.6 0 0 0 .3-1.8 1.6 1.6 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.2a1.6 1.6 0 0 0 1.5-1 1.6 1.6 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 1.8.3H9a1.6 1.6 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.2a1.6 1.6 0 0 0 1 1.5 1.6 1.6 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0-.3 1.8V9a1.6 1.6 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.2a1.6 1.6 0 0 0-1.5 1z" />
            </svg>
            外观设置
          </el-button>
        </div>
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
import { useThemeStore } from '@/stores/theme'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const theme = useThemeStore()

const formRef = ref<FormInstance>()
const form = reactive({ email: '', code: '', invite_code: '' })
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
    const res = await loginApi(form.email, form.code, form.invite_code)
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
  background: @c-bg;

  @media (max-width: @bp-lg) {
    flex-direction: column;
  }
}

// ---- 品牌区 ----
.brand-panel {
  position: relative;
  flex: 0 0 46%;
  display: flex;
  align-items: center;
  padding: 64px 60px;
  background: @c-brand-grad;
  color: @c-brand-text;
  overflow: hidden;

  // 网格纹理：低对比度细线 + 右上角径向遮罩，避免脏底又增加质感
  &::before {
    content: '';
    position: absolute;
    inset: 0;
    background-image:
      linear-gradient(rgba(255, 255, 255, 0.045) 1px, transparent 1px),
      linear-gradient(90deg, rgba(255, 255, 255, 0.045) 1px, transparent 1px);
    background-size: 44px 44px;
    -webkit-mask-image: radial-gradient(circle at 70% 20%, #000 0%, transparent 72%);
    mask-image: radial-gradient(circle at 70% 20%, #000 0%, transparent 72%);
    pointer-events: none;
  }

  @media (max-width: @bp-lg) {
    flex: none;
    align-items: flex-start;
    padding: 34px 24px 30px;
  }
}

.glow {
  position: absolute;
  width: 380px;
  height: 380px;
  border-radius: 50%;
  filter: blur(52px);
  pointer-events: none;
  animation: float-drift @dur-ambient @ease-out infinite alternate;
}

.glow-accent {
  top: -110px;
  right: -90px;
  background: @c-brand-glow-accent;
}

.glow-cool {
  bottom: -130px;
  left: -90px;
  background: @c-brand-glow-cool;
  animation-delay: @dur-ambient / 2;
}

.brand-inner {
  position: relative;
  z-index: 1;
  max-width: 460px;
}

.brand-logo {
  display: flex;
  align-items: center;
  gap: 12px;
}

.brand-mark {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  border-radius: @radius;
  background: linear-gradient(150deg, var(--app-accent-light), var(--app-accent-dark));
  box-shadow: @shadow-accent-sm;
  color: #fff;

  svg {
    width: 21px;
    height: 21px;
  }
}

.brand-name {
  display: flex;
  flex-direction: column;
  line-height: 1.3;
  letter-spacing: 0.04em;

  strong {
    font-size: 17px;
    font-weight: 700;
  }

  small {
    margin-top: 2px;
    font-size: 9px;
    letter-spacing: 0.16em;
    color: @c-brand-text-sub;
  }
}

.brand-slogan {
  margin: 34px 0 30px;
  font-size: 32px;
  line-height: 1.38;
  font-weight: 700;
  letter-spacing: -0.01em;

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
      border-top: 1px solid @c-brand-line;
    }
  }

  strong {
    font-size: @fs-h3 - 1px;
  }

  p {
    margin: 4px 0 0;
    font-size: @fs-sm;
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
  border-radius: @radius-sm;
  background: rgba(255, 255, 255, 0.07);
  border: 1px solid @c-brand-line;
  color: @c-accent-light-5;

  :deep(svg) {
    width: 19px;
    height: 19px;
  }
}

// ---- 表单区 ----
.auth-main {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px 32px;
  background:
    radial-gradient(circle at 82% 12%, color-mix(in srgb, var(--app-accent) 7%, transparent) 0%, transparent 42%),
    @c-bg;

  @media (max-width: @bp-lg) {
    align-items: flex-start;
    padding: 24px 16px 48px;
  }
}

.login-card {
  width: 100%;
  max-width: 420px;
  padding: 44px 40px 36px;
  border: 1px solid @c-line-soft;
  border-radius: @radius-lg;
  background: @c-surface;
  box-shadow: @shadow-md;
  // 首屏进场：上浮淡入（配合路由 page 过渡，双层节奏更丝滑）
  animation: rise-in @dur-slow @ease-out both;

  @media (max-width: @bp-sm) {
    padding: 28px 22px 24px;
    box-shadow: @shadow-sm;
  }
}

.title {
  margin: 0;
  font-size: @fs-h1;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.subtitle {
  margin: 8px 0 26px;
  font-size: @fs-sm;
  line-height: 1.6;
  color: @c-text-sub;
}

.input-icon {
  width: 16px;
  height: 16px;
  color: @c-text-muted;
}

// 表单控件间距统一
:deep(.el-form-item) {
  margin-bottom: 18px;
}

.code-row {
  display: flex;
  gap: 8px;
  width: 100%;
}

.code-btn {
  // 固定最小宽度：倒计时文案切换时按钮不抖动
  min-width: 124px;
}

.submit {
  width: 100%;
  height: 46px;
  margin-top: 6px;
  border-radius: @radius-pill;
  font-weight: 600;
  letter-spacing: 0.12em;
}

.login-foot {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  margin-top: 24px;
}

.footer-note {
  margin: 0;
  font-size: @fs-xs;
  text-align: center;
  color: @c-text-muted;
}

.theme-entry {
  font-size: @fs-xs;
  color: @c-text-muted;

  svg {
    width: 14px;
    height: 14px;
    margin-right: 4px;
  }

  &:hover {
    color: var(--app-accent);
  }
}
</style>
