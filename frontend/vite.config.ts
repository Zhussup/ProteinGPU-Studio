import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // проксируем /api на FastAPI-бэкенд в разработке
    // 开发期将 /api 代理到 FastAPI 后端
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8077',
        changeOrigin: true,
      },
    },
  },
})