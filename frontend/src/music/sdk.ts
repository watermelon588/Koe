import { IDLE, type Player, type PlayState, type Track } from './model.ts'
import { MusicFailure, MusicIntents, type MusicRequest } from './intents.ts'
import { audioEvidence } from '../audio/evidence.ts'

export type SDKState = { paused: boolean; position: number; duration: number;
  disallows: Record<string, boolean>; track_window: { current_track: { uri: string } } }
type SDKEvents = { ready: { device_id: string }; not_ready: { device_id: string }; player_state_changed: SDKState | null;
  initialization_error: { message: string }; authentication_error: { message: string }; account_error: { message: string };
  playback_error: { message: string }; autoplay_failed: Record<string, never> }
export interface SDKPlayer {
  addListener<K extends keyof SDKEvents>(event: K, listener: (data: SDKEvents[K]) => void): boolean
  removeListener(event: keyof SDKEvents): boolean
  connect(): Promise<boolean>; disconnect(): void; activateElement(): Promise<void>
  getCurrentState(): Promise<SDKState | null>; pause(): Promise<void>; resume(): Promise<void>
  seek(ms: number): Promise<void>; previousTrack(): Promise<void>; nextTrack(): Promise<void>
  setVolume(volume: number): Promise<void>
}
type SDKConstructor = new (options: { name: string; volume: number; getOAuthToken: (callback: (token: string) => void) => void }) => SDKPlayer
declare global { interface Window { Spotify?: { Player: SDKConstructor }; onSpotifyWebPlaybackSDKReady?: () => void } }
let loading: Promise<SDKConstructor> | null = null

export function loadSpotifySDK(): Promise<SDKConstructor> {
  if (window.Spotify?.Player) return Promise.resolve(window.Spotify.Player)
  if (loading) return loading
  loading = new Promise<SDKConstructor>((resolve, reject) => {
    const previous = window.onSpotifyWebPlaybackSDKReady
    const cleanup = () => {
      clearTimeout(timer)
      if (window.onSpotifyWebPlaybackSDKReady === onReady) window.onSpotifyWebPlaybackSDKReady = previous
    }
    const failed = () => {
      cleanup()
      document.querySelector('script[data-koe-spotify-sdk]')?.remove()
      reject(new MusicFailure('spotify_unavailable', 'Spotify’s player did not load. Try again.'))
    }
    const timer = setTimeout(failed, 15000)
    const onReady = () => {
      cleanup()
      if (window.Spotify?.Player) resolve(window.Spotify.Player)
      else reject(new MusicFailure('spotify_unavailable'))
      previous?.()
    }
    window.onSpotifyWebPlaybackSDKReady = onReady
    if (!document.querySelector('script[data-koe-spotify-sdk]')) {
      const script = document.createElement('script')
      script.src = 'https://sdk.scdn.co/spotify-player.js'; script.async = true; script.dataset.koeSpotifySdk = 'true'
      script.onerror = failed
      document.head.appendChild(script)
    }
  }).catch(error => { loading = null; throw error })
  return loading
}

type Options = { connectionId: string; tracks: () => Track[]; request: MusicRequest; intents: MusicIntents; volume?: number }
const bounded = <T>(promise: Promise<T>, ms = 8000): Promise<T> => new Promise((resolve, reject) => {
  const timer = setTimeout(() => reject(new MusicFailure('spotify_device_unavailable', 'Spotify’s player did not respond.')), ms)
  promise.then(value => { clearTimeout(timer); resolve(value) }, error => { clearTimeout(timer); reject(error) })
})

// Exposed constructor injection keeps the actual queue/barrier testable without the network SDK.
export function spotifyPlayer(Constructor: SDKConstructor, options: Options): Player {
  const { connectionId, request, intents } = options
  const evidence = audioEvidence()
  let state: PlayState = { ...IDLE, volume: options.volume ?? .6 }
  let device = ''
  let disposed = false
  let connected = false
  let played = evidence?.has(connectionId) === true || intents.blocking().some(i => i.path === '/api/music/playback')
  if (played) state.status = 'unknown'
  let disallows: Record<string, boolean> = {}
  let tail: Promise<unknown> = Promise.resolve()
  let localInFlight = 0
  let startInFlight = false
  let pauseVersion = 0
  let resolveReady: (id: string) => void = () => {}
  let ready = new Promise<string>(resolve => { resolveReady = resolve })
  const listeners = new Set<() => void>()
  const update = (patch: Partial<PlayState>) => { if (!disposed) { state = { ...state, ...patch }; listeners.forEach(fn => fn()) } }
  const fail = (code: string, message: string) => { update({ status: played ? 'unknown' : 'idle', error: message }); return new MusicFailure(code, message) }
  const raw = new Constructor({ name: 'Koe Web Player', volume: options.volume ?? .6, getOAuthToken: callback => {
    void request('/api/music/sdk-token', 'POST', { connection_id: connectionId }).then(reply => {
      const body = reply.body as { access_token?: string; connection_id?: string; error?: { code?: string } }
      if (!disposed && reply.http === 200 && body.connection_id === connectionId && typeof body.access_token === 'string') callback(body.access_token)
      else fail(body.error?.code ?? 'spotify_reconnect_required', 'Spotify needs to connect again.')
    }).catch(() => fail('spotify_unavailable', 'Could not refresh Spotify access.'))
  } })
  const observe = (seen: SDKState | null) => {
    if (!seen || typeof seen.paused !== 'boolean') { update({ status: played ? 'unknown' : 'idle' }); return }
    if (!seen.paused) played = true
    disallows = seen.disallows ?? {}
    const tracks = options.tracks()
    const uri = seen.track_window?.current_track?.uri
    const index = tracks[state.index]?.uri === uri ? state.index : tracks.findIndex(t => t.uri === uri)
    update({ status: seen.paused ? 'paused' : 'playing', index, position: seen.position, at: performance.now(), error: '' })
  }
  raw.addListener('ready', info => { if (!disposed) { device = info.device_id; resolveReady(device) } })
  raw.addListener('not_ready', () => {
    device = ''; connected = false
    ready = new Promise<string>(resolve => { resolveReady = resolve })
    fail('spotify_device_unavailable', 'This browser’s Spotify player disconnected.')
  })
  raw.addListener('player_state_changed', observe)
  raw.addListener('account_error', () => fail('spotify_premium_required', 'Spotify Premium is required for this player.'))
  raw.addListener('authentication_error', () => fail('spotify_reconnect_required', 'Reconnect Spotify to renew access.'))
  raw.addListener('initialization_error', () => fail('spotify_unavailable', 'This browser cannot start Spotify. Use the Spotify app or web player.'))
  raw.addListener('playback_error', () => fail('spotify_unavailable', 'Spotify could not play this track.'))
  raw.addListener('autoplay_failed', () => fail('spotify_device_unavailable', 'Press Play again to allow audio in this browser.'))
  const queue = <T>(operation: () => Promise<T>): Promise<T> => {
    const run = tail.then(async () => { if (disposed) throw new MusicFailure('spotify_device_unavailable'); return operation() })
    tail = run.catch(() => {})
    return run
  }
  const refresh = async () => { const seen = await bounded(raw.getCurrentState()); observe(seen); return seen }
  const allowed = (action: string) => { if (disallows[action]) throw new MusicFailure('spotify_unsupported_operation', 'Spotify does not allow this control right now.') }
  const local = (action: string, run: () => Promise<void>) => queue(async () => {
    allowed(action); evidence?.mark(connectionId); evidence?.local(connectionId, true); played = true
    localInFlight++
    const sent = Promise.resolve().then(run).finally(() => { localInFlight--; if (!localInFlight) evidence?.local(connectionId, false) })
    await bounded(sent); await refresh()
  })
  const pause = () => {
    pauseVersion++ // Stop observing a start once an explicit pause is queued behind it.
    return queue(async (): Promise<'paused' | 'unknown'> => {
      if (!played) return 'paused'
      try {
        await intents.inspect()
        if (localInFlight || evidence?.localPending(connectionId)) { await bounded(raw.pause()); update({ status: 'unknown', error: 'A sent player command is still unresolved. Voice stays blocked.' }); return 'unknown' }
        if (intents.blocking().some(i => i.path === '/api/music/playback')) { await bounded(raw.pause()); update({ status: 'unknown', error: 'A sent playback action is unconfirmed. Voice stays blocked.' }); return 'unknown' }
        allowed('pausing'); await bounded(raw.pause())
        const until = performance.now() + 2000
        do {
          const seen = await refresh()
          if (seen?.paused === true) { evidence?.clear(connectionId); return 'paused' }
          await new Promise(resolve => setTimeout(resolve, 80))
        } while (performance.now() < until)
      } catch { /* A pause call or null state is never promoted to stopped. */ }
      update({ status: 'unknown', error: 'Could not confirm music stopped. Try pausing again.' })
      return 'unknown'
    })
  }
  const prepare = async () => {
    if (!connected) { connected = await bounded(raw.connect()); if (!connected) throw fail('spotify_device_unavailable', 'Spotify’s player did not connect. Press Play to retry.') }
    const id = device || await bounded(ready)
    const registered = await request('/api/music/device', 'POST', { connection_id: connectionId, device_id: id })
    if (registered.http !== 200) {
      const error = (registered.body as { error?: { code?: string; message?: string } })?.error
      throw fail(error?.code ?? 'spotify_device_unavailable', error?.message ?? 'Spotify has not made this browser available. No playback was requested; press Play to retry.')
    }
    return id
  }
  return {
    mock: false, state: () => state, playing: () => startInFlight ? null : !played ? false : localInFlight || state.status === 'unknown' || state.status === 'starting' ? null : state.status === 'playing',
    subscribe: fn => { listeners.add(fn); return () => { listeners.delete(fn) } },
    activate: () => { void raw.activateElement().catch(() => fail('spotify_device_unavailable', 'Press Play again to allow audio.')) },
    prepare: () => queue(async () => { await prepare() }),
    unsettled: () => startInFlight || localInFlight > 0 || state.status === 'starting',
    recovered: () => { played = false; update({ status: state.index >= 0 ? 'paused' : 'idle', error: '' }) },
    async play(index, snapshot) {
      const beforePause = pauseVersion
      return queue(async () => {
        if (!options.tracks()[index]?.playable) throw new MusicFailure('spotify_invalid_request')
        const requestedUri = options.tracks()[index].uri
        startInFlight = true
        try {
          update({ status: 'starting', index, error: '' })
          const id = await prepare()
          evidence?.mark(connectionId)
          played = true // Only sent transfer/play can leave uncertain playback behind.
          await intents.write('/api/music/playback', 'POST', { device_id: id, operation: 'transfer' })
          // Spotify transfer is asynchronous; confirm target before the start request.
          const until = performance.now() + 4000
          let targeted = false
          do {
            const result = await request(`/api/music/playback?connection_id=${encodeURIComponent(connectionId)}&device_id=${encodeURIComponent(id)}`)
            if ((result.body as { device_id?: string })?.device_id === id) { targeted = true; break }
            await new Promise(resolve => setTimeout(resolve, 100))
          } while (performance.now() < until)
          if (!targeted) throw fail('spotify_device_unavailable', 'Spotify has not confirmed this browser as the active player.')
          await intents.write('/api/music/playback', 'POST', { device_id: id, operation: 'play', position: index, ...(snapshot ? { snapshot_id: snapshot } : {}) })
          // Accepted Web API writes precede SDK state propagation. Observe only;
          // never resend play, or accept the previous track as this request's result.
          const confirmationDeadline = performance.now() + 8000
          do {
            if (pauseVersion !== beforePause) return // The queued pause still has to verify silence.
            const seen = await bounded(raw.getCurrentState(), Math.max(1, confirmationDeadline - performance.now()))
            observe(seen)
            if (seen?.paused === false && seen.track_window?.current_track?.uri === requestedUri) return
            await new Promise(resolve => setTimeout(resolve, 150))
          } while (!disposed && performance.now() < confirmationDeadline)
          throw new MusicFailure('spotify_outcome_unknown', 'Spotify accepted the request but playback is not confirmed. Check the player before trying again.')
        } finally { startInFlight = false }
      }).catch(error => { update({ status: played ? 'unknown' : 'idle', error: error instanceof Error ? error.message : 'Spotify could not start.' }); throw error })
    },
    resume: () => local('resuming', () => raw.resume()), pause,
    next: () => local('skipping_next', () => raw.nextTrack()), previous: () => local('skipping_prev', () => raw.previousTrack()),
    seek: ms => local('seeking', () => raw.seek(ms)),
    setVolume: volume => queue(async () => { await bounded(raw.setVolume(volume)); update({ volume }) }),
    shuffle: enabled => queue(async () => { if (!device) throw new MusicFailure('spotify_device_unavailable'); await intents.write('/api/music/playback', 'POST', { device_id: device, operation: 'shuffle', state: enabled }) }),
    repeat: mode => queue(async () => { if (!device) throw new MusicFailure('spotify_device_unavailable'); await intents.write('/api/music/playback', 'POST', { device_id: device, operation: 'repeat', state: mode }) }),
    dispose: () => { disposed = true; for (const event of ['ready', 'not_ready', 'player_state_changed', 'account_error', 'authentication_error', 'initialization_error', 'playback_error', 'autoplay_failed'] as const) raw.removeListener(event); raw.disconnect(); listeners.clear() },
  }
}

export async function createSpotifyPlayer(options: Options) { return spotifyPlayer(await loadSpotifySDK(), options) }
