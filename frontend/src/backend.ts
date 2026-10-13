// Where the backend lives. In development it's the same origin: Vite proxies /api and /ws to :8000.
// On Vercel (static frontend), set VITE_BACKEND_URL to the backend's public https URL (cloudflared tunnel or
// the Azure VM). Vercel can't proxy WebSockets, so the browser talks to the backend directly.
// https://vite.dev/guide/env-and-mode
const base = (import.meta.env.VITE_BACKEND_URL ?? '').replace(/\/+$/, '')

export const httpUrl = (path: string) => base + path
export const wsUrl = (path: string) =>
  base ? base.replace(/^http/, 'ws') + path : `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}${path}`
