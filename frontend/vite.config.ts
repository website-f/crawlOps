import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        // heavy libraries get their own long-cached chunks, fetched only by the pages that use them
        manualChunks: {
          react: ['react', 'react-dom', 'react-router-dom'],
          three: ['three'],
          leaflet: ['leaflet', 'react-leaflet'],
          recharts: ['recharts'],
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: { '/api': { target: 'http://localhost:8401', changeOrigin: true } },
  },
})
