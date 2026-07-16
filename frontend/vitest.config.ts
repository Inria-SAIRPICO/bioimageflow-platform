import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

const backendPort = process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'
const backendHttpUrl = `http://localhost:${backendPort}`

export default defineConfig({
  plugins: [vue()],
  define: {
    'import.meta.env.VITE_BIOIMAGEFLOW_BACKEND_HTTP_URL': JSON.stringify(backendHttpUrl),
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    include: ['tests/unit/**/*.test.ts', 'src/**/__tests__/*.test.ts'],
    setupFiles: ['./tests/setup.ts'],
    onConsoleLog(log, type) {
      if (type === 'stderr') {
        throw new Error(`Unexpected console warning or error:\n${log}`)
      }
    },
  },
})
