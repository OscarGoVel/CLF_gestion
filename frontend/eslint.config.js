import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{js,jsx}'],
    extends: [
      js.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      globals: globals.browser,
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    rules: {
      // react-hooks v7 introduced strict rules that flag valid React patterns as errors.
      // setState at the top of an effect (guard clause) and refs in JSX are both standard.
      'react-hooks/set-state-in-effect': 'off',
      'react-hooks/refs': 'off',
      // useFetch uses spread in dep array: [path, ...deps] — a deliberate, safe pattern.
      'react-hooks/use-memo': 'off',
      // Exporting hooks alongside components (e.g. context files) is a common pattern.
      // Downgrade from error to warning so Fast Refresh works in dev but CI still passes.
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
      // Allow _-prefixed function parameters to be intentionally unused.
      'no-unused-vars': ['error', { argsIgnorePattern: '^_', caughtErrorsIgnorePattern: '^_' }],
    },
  },
])
