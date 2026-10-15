import { httpUrl } from '../backend'

// Same-origin JSON calls to Koe's music routes (API_CONTRACT.md v1). The session cookie authenticates; the browser
// adds Origin on writes. Never cached: tokens and playlists don't belong in any cache.
export type Reply = { http: number; body: unknown }
export async function music(path: string, method = 'GET', body?: unknown, signal?: AbortSignal): Promise<Reply> {
  const timeout = AbortSignal.timeout(15000)
  const r = await fetch(httpUrl(path), { method, cache: 'no-store', credentials: 'same-origin', signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body) })
  return { http: r.status, body: await r.json().catch(() => undefined) }
}
export const codeOf = (body: unknown) => (body as { error?: { code?: string } } | undefined)?.error?.code
