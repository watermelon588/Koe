import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Dev only: the browser talks to :5173 and Vite forwards /api, /auth and /ws to the backend (KOE_BACKEND, default
// :8000). xfwd adds X-Forwarded-Host, so the backend knows the page is on localhost:5173: Google's sign-in
// redirect must go back there (koe/auth.py `site`). https://vite.dev/config/server-options#server-proxy
const backend = process.env.KOE_BACKEND ?? 'http://localhost:8000'
const simulatedSpotify = process.env.KOE_SPOTIFY_E2E === 'true'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), ...(simulatedSpotify ? [{ name: 'koe-local-spotify-fixture', apply: 'serve' as const,
    transformIndexHtml: () => [{ tag: 'script', attrs: { src: '/__e2e/player.js' }, injectTo: 'head' as const }],
  }] : [])],
  build: {
    rolldownOptions: {
      output: { codeSplitting: { groups: [
        { name: 'three-core', test: /node_modules[\\/]three[\\/]build[\\/]three\.core\.js$/, priority: 20 },
        { name: 'three-renderer', test: /node_modules[\\/]three[\\/]/, priority: 10 },
        { name: 'vrm', test: /node_modules[\\/]@pixiv[\\/]/ },
      ] } },
    },
  },
  server: {
    proxy: {
      ...(simulatedSpotify ? { '/__e2e': { target: backend } } : {}),
      '/ws': { target: backend.replace(/^http/, 'ws'), ws: true },
      '/api': { target: backend, xfwd: true },
      '/auth': { target: backend, xfwd: true },
    },
    // The phone reaches the dev server through a cloudflared quick tunnel (HTTPS is required to install the
    // app and receive push). https://vite.dev/config/server-options#server-allowedhosts
    allowedHosts: ['.trycloudflare.com'],
  },
})
