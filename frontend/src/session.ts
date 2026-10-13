import { httpUrl } from './backend'
import { saveToken } from './chat/api'

// Continue with Google (ACCOUNTS_SPEC.md, backend: koe/auth.py). Signed in, the stored "token" is the marker SESSION:
// HTTP requests carry the HttpOnly session cookie (same origin through Vercel's proxy), and the two WebSockets,
// which go straight to the backend, trade it for a one-time ticket. Without Google sign-in on the server, the old
// access-token flow is unchanged.
export const SESSION = 'session'

export function signIn() {
  const next = location.hash ? `/${location.hash}` : '/'
  location.href = httpUrl(`/auth/google/start?next=${encodeURIComponent(next)}`)
}

export async function signOut() {
  await fetch(httpUrl('/auth/logout'), { method: 'POST' }).catch(() => {})
  saveToken('')
  location.replace('/')
}

export async function wsCredential(token: string): Promise<string> {
  if (token !== SESSION) return token
  const r = await fetch(httpUrl('/api/ws-ticket'), { method: 'POST' })
  if (!r.ok) throw new Error(r.status === 403 ? 'Koe isn’t ready for friends yet.' : 'Sign in to Koe again.')
  return (await r.json()).ticket
}
