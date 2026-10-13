import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Dev only: the browser talks to :5173, Vite forwards /ws/* to the backend.
    // https://vite.dev/config/server-options#server-proxy
    proxy: { '/ws': { target: 'ws://localhost:8000', ws: true }, '/api': 'http://localhost:8000', '/auth': 'http://localhost:8000' },
    // The phone reaches the dev server through a cloudflared quick tunnel (HTTPS is required to install the
    // app and receive push). https://vite.dev/config/server-options#server-allowedhosts
    allowedHosts: ['.trycloudflare.com'],
  },
})
