import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import './style.css'

// Element Plus 组件由 unplugin-vue-components 按需自动注册（vite.config.ts）
createApp(App).use(router).mount('#app')
