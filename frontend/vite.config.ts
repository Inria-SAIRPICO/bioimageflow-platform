import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const backendPort =
  process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ??
  process.env.BIOIMAGEFLOW_BACKEND_PORT ??
  '8000'
const backendHttpUrl = `http://127.0.0.1:${backendPort}`
const backendWsUrl = `ws://127.0.0.1:${backendPort}`

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': backendHttpUrl,
      '/ws': {
        target: backendWsUrl,
        ws: true,
      },
    },
  },
})
