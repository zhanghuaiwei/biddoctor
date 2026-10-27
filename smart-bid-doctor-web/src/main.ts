import { createApp } from 'vue'
import { createPinia } from 'pinia'
import 'element-plus/theme-chalk/dark/css-vars.css'
import App from './App.vue'
import router from './router'
import './styles/global.less'
import { useThemeStore } from './stores/theme'

// Element Plus 组件由 unplugin-vue-components 按需自动注册（vite.config.ts）
// 暗色主题 CSS 变量先于 global.less 引入，保证本项目的 --app-* 映射可覆盖
function bootstrap() {
  const pinia = createPinia()
  const app = createApp(App).use(pinia).use(router)
  // 挂载前应用主题（store 内 watch immediate），避免首屏闪白/闪暗
  useThemeStore(pinia)
  app.mount('#app')
}

bootstrap()
