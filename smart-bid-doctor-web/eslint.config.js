/**
 * ESLint 平面配置（ESLint 10 + eslint-plugin-vue 10 + @vue/eslint-config-typescript）。
 * 定位：防错门禁，不做样式排版——选 vue/essential（错误预防）而非 recommended，
 * 避免对既有视图产生大批无关格式化 diff；代码风格由 vue-tsc 类型门禁 + 团队约定兜底。
 * unplugin 自动生成文件与产物不入检查范围。
 */
import { defineConfigWithVueTs, vueTsConfigs } from '@vue/eslint-config-typescript'
import pluginVue from 'eslint-plugin-vue'

export default defineConfigWithVueTs(
  {
    ignores: ['dist/**', 'node_modules/**', 'auto-imports.d.ts', 'components.d.ts'],
  },
  pluginVue.configs['flat/essential'],
  vueTsConfigs.recommended,
  {
    rules: {
      // 自动导入（unplugin-auto-import）注入的 Vue API 与 Element Plus 组件无需显式导入，
      // 由 auto-imports.d.ts / components.d.ts 提供类型；此处仅约束未使用变量提示级别
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
    },
  },
)
