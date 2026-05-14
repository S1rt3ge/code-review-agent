import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

const apiProxyTarget = process.env.VITE_DEV_PROXY_TARGET || 'http://localhost:8000'
const wsProxyTarget = process.env.VITE_DEV_WS_PROXY_TARGET || 'ws://localhost:8000'

export default defineConfig({
  plugins: [react({ babel: { plugins: [] } })],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src')
    }
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: apiProxyTarget,
        changeOrigin: true
      },
      '/ws': {
        target: wsProxyTarget,
        ws: true
      }
    }
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.js',
    coverage: {
      provider: 'v8',
      reporter: ['text'],
      thresholds: {
        statements: 70,
        branches: 55,
        functions: 65,
        lines: 75,
      },
    }
  }
})
