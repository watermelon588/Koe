// Where the backend lives. HTTP (/api, /auth) is always same-origin: Vite proxies it to :8000 in development,
// Vercel rewrites it to Render in production (frontend/vercel.json), so the sign-in cookie is first-party.
// WebSockets can't go through Vercel's proxy: set VITE_BACKEND_URL to the backend's public https URL and the
// browser connects to it directly (signing in with a one-time ticket, session.ts).
// https://vite.dev/guide/env-and-mode
const base = (import.meta.env.VITE_BACKEND_URL ?? '').replace(/\/+$/, '')

export const httpUrl = (path: string) => path
export const wsUrl = (path: string) =>
  base ? base.replace(/^http/, 'ws') + path : `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}${path}`
