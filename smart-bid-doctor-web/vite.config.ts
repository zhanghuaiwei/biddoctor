import vue from '@vitejs/plugin-vue'
import { defineConfig, loadEnv } from 'vite'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

// 环境变量体系（与后端同名对齐）：.env < .env.development/.env.production/.env.test
// < .env.development.local（个人覆盖）；env 文件一律不入库，键清单见根目录 README「配置说明」
export default defineConfig(({ mode }) => {
  // 第三个参数 '' 表示不限定 VITE_ 前缀（proxy target 等构建期变量复用同一体系）
  const env = loadEnv(mode, process.cwd(), '')

  return {
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
      // dev 代理后端地址走环境变量（.env.development.local 可按本机端口覆盖）
      proxy: { '/api': env.VITE_API_PROXY_TARGET || 'http://localhost:8000' },
    },
  }
})
