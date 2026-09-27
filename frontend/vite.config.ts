import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
//
// Le serveur de dev proxifie /api/* vers l'API FastAPI locale
// (sys_foot_quant.api.app, UI-2-B) - evite toute configuration CORS cote
// backend (hors perimetre de cette phase) : le navigateur ne voit qu'une
// seule origine (le serveur Vite), qui relaie server-side vers 127.0.0.1:8000.
export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
