import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

export default defineConfig({
  resolve: {
    alias: { '@': '/src', '@styles': '/src/styles' },
  },
  css: {
    preprocessorOptions: {
      // 设计变量自动注入每个 <style lang="less">（variables.less），无需手动 @import
      less: { additionalData: `@import "@styles/variables.less";`, javascriptEnabled: true },
    },
  },
  plugins: [
    vue(),
    // Element Plus 按需引入（组件样式自动注入），构建产物不再打包全量库
    AutoImport({ resolvers: [ElementPlusResolver()], dts: 'src/auto-imports.d.ts' }),
    Components({ resolvers: [ElementPlusResolver()], dts: 'src/components.d.ts' }),
  ],
  server: {
    port: 5173,
    proxy: { '/api': 'http://localhost:8000' },
  },
})
