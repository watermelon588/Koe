// Music: types, server-status mapping, Spotify link helpers and the labelled development mock.
// Plain TypeScript (no React) so tests run it directly. Server contract: docs/spotify/API_CONTRACT.md v1.0.0.
import type { PauseResult } from '../audio/coordinator'

export type Track = { id: string; uri: string; name: string; artists: string; art: string | null; url: string; ms: number; playable: boolean }
export type Playlist = { id: string; name: string; url: string; uri: string; art: string | null; snapshot?: string; total?: number }
export type MusicStatus =
  | { phase: 'loading' }
  | { phase: 'unavailable'; message: string; retryable?: boolean } // unavailable setup is distinct from a temporary read failure
  | { phase: 'signed-out' }
  | { phase: 'disconnected'; canConnect: boolean; reconnect: boolean; message: string }
  | { phase: 'connected'; connectionId: string; playlistId: string | null; read: boolean; write: boolean; inApp: boolean; mock: boolean }

export const CONTRACT = '1.0.0'
// Contract v1 shapes (API_CONTRACT.md "Shared shapes").
export type ApiPlaylist = { id: string; name: string; spotify_url: string; snapshot_id: string; total: number; image_url: string | null }
export type ApiTrack = { id: string | null; uri: string | null; name: string; artists: string[]; album: string; image_url: string | null;
  spotify_url: string | null; duration_ms: number; playable: boolean; unavailable_reason: string | null }
export type ApiStatus = { contract_version: string; configured: boolean; enabled: boolean; connected: boolean; reconnect_required: boolean;
  connection_id: string | null; selected_playlist_id: string | null; unavailable_reason: string | null
  capabilities: { connect: boolean; playlist_read: boolean; playlist_write: boolean; playback: boolean } }

export type PlayStatus = 'idle' | 'starting' | 'playing' | 'paused' | 'unknown'
// position is in ms, observed at `at` (performance.now()); the UI adds elapsed time instead of polling Spotify.
export type PlayState = { status: PlayStatus; index: number; position: number; at: number; volume: number; error: string }
export const IDLE: PlayState = { status: 'idle', index: -1, position: 0, at: 0, volume: 0.6, error: '' }

export interface Player {
  readonly mock: boolean
  state(): PlayState
  subscribe(fn: () => void): () => void
  playing(): boolean | null // null = can't tell (counts as playing for the voice gate)
  play(index: number, snapshot?: string): Promise<void>
  prepare?(): Promise<void>
  unsettled?(): boolean
  recovered?(): void
  resume(): Promise<void>
  pause(): Promise<PauseResult> // settles commands already sent, then reports what it saw
  next(): Promise<void>
  previous(): Promise<void>
  seek(ms: number): Promise<void>
  setVolume(v: number): Promise<void>
  activate?(): void
  shuffle?(enabled: boolean): Promise<void>
  repeat?(mode: 'off' | 'context' | 'track'): Promise<void>
  dispose(): void
}

// What a stable error code means to a person (API_CONTRACT.md "Errors"). Unknown codes get the generic line.
const SAY: Record<string, string> = {
  spotify_outcome_unknown: 'An earlier action is unconfirmed. Check its status before another change; Koe will not send it twice.',
  spotify_journal_full: 'Music action history is full. Resolve it before making more changes.',
  spotify_storage_unavailable: 'Music action storage is unavailable. No new change was sent.',
  spotify_not_configured: 'Spotify isn’t set up on this Koe server yet.',
  spotify_disabled: 'Spotify is turned off on this Koe server for now.',
  spotify_owner_required: 'Music is only available to Koe’s owner for now.',
  spotify_sign_in_required: 'Sign in to Koe again.',
  spotify_not_connected: 'Connect Spotify first.',
  spotify_reconnect_required: 'Spotify needs you to connect again.',
  spotify_scope_missing: 'Spotify didn’t grant everything Koe needs. Connect again and allow all permissions.',
  spotify_generation_stale: 'Your Spotify connection changed. Refresh the page.',
  spotify_playlist_required: 'Choose your playlist first.',
  spotify_playlist_stale: 'Your playlist changed in Spotify. It’s been reloaded; try again.',
  spotify_playlist_ineligible: 'Koe can only use a private playlist you own.',
  spotify_premium_required: 'Playing music in Koe needs Spotify Premium.',
  spotify_rate_limited: 'Spotify is busy right now. Try again shortly.',
  spotify_quota_exceeded: 'Koe has used its Spotify allowance for now. Try again later.',
  spotify_unavailable: 'Spotify isn’t answering right now. Try again shortly.',
  spotify_device_unavailable: 'The in-app player isn’t ready. Try again.',
}
export const say = (code: string | null | undefined, fallback = 'Something went wrong with Spotify. Try again.') => (code && SAY[code]) || fallback

// GET /api/music/status → what the page can honestly show. A server without the route is "not set up".
export function statusFrom(http: number, body?: unknown): MusicStatus {
  const code = (body as { error?: { code?: string } } | undefined)?.error?.code
  if (http === 401) return { phase: 'signed-out' }
  if (http === 404 || http === 405 || http === 501) return { phase: 'unavailable', message: say('spotify_not_configured') }
  if (http === 403) return { phase: 'unavailable', message: say(code ?? 'spotify_owner_required') }
  const s = body as ApiStatus | undefined
  if (http < 200 || http >= 300 || !s) return { phase: 'unavailable', retryable: true,
    message: say(code, 'Koe couldn’t finish loading music. Retry to request it again.') }
  if (s.contract_version?.split('.')[0] !== CONTRACT.split('.')[0])
    return { phase: 'unavailable', message: 'This version of the app can’t read the server’s music settings. Refresh the page.' }
  if (!s.configured || !s.enabled) return { phase: 'unavailable', message: say(s.unavailable_reason ?? (s.configured ? 'spotify_disabled' : 'spotify_not_configured')) }
  if (!s.connected || !s.connection_id || s.reconnect_required)
    return { phase: 'disconnected', canConnect: s.capabilities.connect, reconnect: s.reconnect_required, message: s.reconnect_required ? say('spotify_reconnect_required') : '' }
  return { phase: 'connected', connectionId: s.connection_id, playlistId: s.selected_playlist_id, read: s.capabilities.playlist_read,
    write: s.capabilities.playlist_write, inApp: s.capabilities.playback && SDK_READY, mock: false }
}
// Backend capability and browser cross-tab support still gate live playback.
export const SDK_READY = true

export const playlistFrom = (p: ApiPlaylist): Playlist => ({ id: p.id, name: p.name, url: p.spotify_url, uri: `spotify:playlist:${p.id}`, art: p.image_url, snapshot: p.snapshot_id, total: p.total })
export const trackFrom = (t: ApiTrack, key: string): Track => ({ id: t.id ?? key, uri: t.uri ?? '', name: t.name, artists: t.artists.join(', '),
  art: t.image_url, url: t.spotify_url ?? 'https://open.spotify.com/', ms: t.duration_ms, playable: t.playable && !!t.uri })

// Where a track is right now, without asking Spotify again.
export function positionAt(s: PlayState, now: number, ms: number) {
  const p = s.status === 'playing' ? s.position + (now - s.at) : s.position
  return Math.max(0, Math.min(ms || 0, p))
}

export const clock = (ms: number) => {
  const s = Math.floor(Math.max(0, ms) / 1000)
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

// A pasted playlist link → its ID. Accepts open.spotify.com (any locale prefix, any ?si=) and spotify:playlist: URIs.
// Spotify IDs are base-62: https://developer.spotify.com/documentation/web-api/concepts/spotify-uris-ids
export function playlistId(text: string): string | null {
  const t = text.trim()
  const uri = /^spotify:playlist:([0-9A-Za-z]{22})$/.exec(t)
  if (uri) return uri[1]
  try {
    const u = new URL(t)
    if (u.protocol !== 'https:' || u.hostname !== 'open.spotify.com') return null
    const m = /^\/(?:intl-[a-z-]+\/)?playlist\/([0-9A-Za-z]{22})\/?$/.exec(u.pathname)
    return m ? m[1] : null
  } catch {
    return null
  }
}
export const webPlaylist = (id: string) => `https://open.spotify.com/playlist/${id}`
export const appPlaylist = (id: string) => `spotify:playlist:${id}`

// ---- Development mock: only with ?music-mock on a dev build, always labelled on screen. No audio is played.
export const MOCK_PLAYLIST: Playlist = { id: 'mock', name: 'Koe — Chill (mock)', url: 'https://open.spotify.com/', uri: '', art: null }
export const MOCK_TRACKS: Track[] = [
  ['Mock track one', 'Mock artist', 214000],
  ['Mock track two', 'Another mock artist', 188000],
  ['A deliberately long mock title, to check how the list wraps a name this long', 'Mock artist, Featured mock artist', 241000],
  ['Mock track four', 'Mock artist', 176000],
  ['Unavailable mock track', 'Mock artist', 200000],
  ['Mock track six', 'Mock band', 229000],
].map(([name, artists, ms], i) => ({ id: `m${i}`, uri: `mock:${i}`, name: name as string, artists: artists as string, art: null,
  url: 'https://open.spotify.com/', ms: ms as number, playable: i !== 4 }))

export function createMockPlayer(tracks: Track[], now = () => performance.now()): Player {
  let s: PlayState = { ...IDLE }
  const fns = new Set<() => void>()
  const set = (patch: Partial<PlayState>) => { s = { ...s, ...patch }; fns.forEach((f) => f()) }
  const here = () => positionAt(s, now(), tracks[s.index]?.ms ?? 0)
  const step = (dir: 1 | -1) => {
    for (let i = s.index + dir; i >= 0 && i < tracks.length; i += dir) if (tracks[i].playable) return i
    return -1
  }
  return {
    mock: true,
    state: () => s,
    subscribe: (fn) => (fns.add(fn), () => void fns.delete(fn)),
    playing: () => s.status === 'playing' || s.status === 'starting',
    async play(index) { if (tracks[index]?.playable) set({ status: 'playing', index, position: 0, at: now(), error: '' }) },
    async resume() { if (s.index >= 0) set({ status: 'playing', position: here(), at: now() }) },
    async pause() { set({ status: s.index >= 0 ? 'paused' : 'idle', position: here(), at: now() }); return 'paused' },
    async next() { const i = step(1); if (i >= 0) set({ index: i, position: 0, at: now() }) },
    async previous() { if (here() > 3000) return set({ position: 0, at: now() }); const i = step(-1); if (i >= 0) set({ index: i, position: 0, at: now() }) },
    async seek(ms) { set({ position: ms, at: now() }) },
    async setVolume(v) { set({ volume: Math.max(0, Math.min(1, v)) }) },
    dispose() { fns.clear() },
  }
}
