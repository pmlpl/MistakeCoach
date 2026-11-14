import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      // 开发期把 /api 转发到 FastAPI（8001；8000 被其他项目占用）
      '/api': 'http://127.0.0.1:8001',
    },
  },
})
