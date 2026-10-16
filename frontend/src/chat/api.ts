// The Koe app API (backend /api/app, SPEC §14). Every call carries the access token remembered on this device.
import { httpUrl } from '../backend'
import type { WorkEvent } from '../workspace/workState'
import type { ReviewAction } from '../approvals/presentation'

export type Message = {
  id: number
  ts: string
  role: 'you' | 'koe' | 'alert'
  text: string
  voice: string | null
  action_id: string | null
  action_status: string | null
  approval?: ReviewAction
  sending?: boolean // local only: on its way, not yet saved
}

// Koe's reply plus what it read, proposed or wrote in Calendar/Sheets/Notion (the live workspace, SPEC §2).
export type Reply = { messages: Message[]; workspace?: WorkEvent[] }

const KEY = 'koe-token'
export function savedToken(): string {
  try {
    return localStorage.getItem(KEY) ?? ''
  } catch {
    return '' // storage blocked: the token is asked for again
  }
}
export function saveToken(token: string): boolean {
  try {
    localStorage.setItem(KEY, token.trim())
    dispatchEvent(new Event('koe-auth-change'))
    return true
  } catch {
    return false
  }
}

export class AuthError extends Error {}

async function request(path: string, init: RequestInit = {}): Promise<Response> {
  const r = await fetch(httpUrl(`/api/app${path}`), { ...init, headers: { ...init.headers, Authorization: `Bearer ${savedToken()}` } })
  if (r.status === 401) {
    if (savedToken() === 'session') location.replace('/') // the Google session ended: back to Continue with Google
    throw new AuthError('Enter your Koe access token.')
  }
  if (!r.ok) throw new Error((await r.json().catch(() => null))?.detail ?? `Koe answered ${r.status}. Is the backend running?`)
  return r
}
const post = (body: unknown): RequestInit => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })

const voices = new Map<string, string>() // voice note name → object URL, fetched once
export const api = {
  messages: async (after = 0): Promise<Reply> => (await request(`/messages?after=${after}`)).json(),
  send: async (text: string): Promise<Reply> => (await request('/messages', post({ text }))).json(),
  sendVoice: async (wav: Blob): Promise<Reply> =>
    (await request('/voice', { method: 'POST', headers: { 'Content-Type': 'audio/wav' }, body: wav })).json(),
  decide: async (id: string, approve: boolean): Promise<Reply & { action: { id: string; status: string } }> =>
    (await request(`/approvals/${encodeURIComponent(id)}`, post({ approve }))).json(),
  voice: async (name: string): Promise<string> => {
    if (!voices.has(name)) voices.set(name, URL.createObjectURL(await (await request(`/voice/${name}`)).blob()))
    return voices.get(name)!
  },
  pushKey: async (): Promise<string> => (await (await request('/push/key')).json()).key,
  subscribe: async (subscription: PushSubscriptionJSON): Promise<void> => void (await request('/push/subscribe', post(subscription))),
  pushTest: async (): Promise<number> => (await (await request('/push/test', { method: 'POST' })).json()).sent,
}
