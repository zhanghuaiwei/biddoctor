import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './styles/global.less'

// Element Plus 组件由 unplugin-vue-components 按需自动注册（vite.config.ts）
// pinia 先于 router 安装：路由守卫与 api client 在运行期经 useAuthStore 取登录态
createApp(App).use(createPinia()).use(router).mount('#app')
