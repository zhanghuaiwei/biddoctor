import { createApp } from 'vue'
import { createPinia } from 'pinia'
import 'element-plus/theme-chalk/dark/css-vars.css'
// 编程式 API（ElMessage / ElMessageBox）不经过模板解析，unplugin 只自动导入函数不带样式，
// 缺样式时确认弹窗会退化成无背景、无居中的裸文本（utils/confirm.ts 全站二次确认因此受影响）
import 'element-plus/es/components/message/style/css'
import 'element-plus/es/components/message-box/style/css'
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
