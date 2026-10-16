import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from 'react'
import { acquire, current, interruptVoiceForMusic, setMusic, subscribe, type Release } from '../audio/coordinator'
import { crossTabSupported } from '../audio/crossTab'
import { codeOf, music as call } from './api'
import { MusicFailure, MusicIntents } from './intents'
import { loadSpotifySDK, spotifyPlayer } from './sdk'
import { useMusicVoice } from './useMusicVoice'
import { createMockPlayer, IDLE, MOCK_PLAYLIST, MOCK_TRACKS, playlistFrom, say, statusFrom, trackFrom,
  type ApiPlaylist, type ApiTrack, type MusicStatus, type Player, type Playlist, type PlayState, type Track } from './model'

const MOCK = import.meta.env.DEV && new URLSearchParams(location.search).has('music-mock')
const BACK = { connected: 'Spotify connected.', cancelled: 'Connecting Spotify was cancelled.', error: 'Spotify did not finish connecting. Try again.' }
type Items = { items: { position: number; track: ApiTrack }[]; next_offset: number | null; playlist: ApiPlaylist }
type Choices = { items: ApiPlaylist[]; next_offset: number | null }

export function useMusic(musicWindow = false) {
  const [status, setStatus] = useState<MusicStatus>({ phase: 'loading' })
  const [tracks, setTracks] = useState<Track[]>([])
  const tracksRef = useRef(tracks)
  useEffect(() => { tracksRef.current = tracks }, [tracks])
  const [playlist, setPlaylist] = useState<Playlist | null>(null)
  const [more, setMore] = useState<number | null>(null)
  const [choices, setChoices] = useState<{ items: Playlist[]; next: number | null } | null>(null)
  const [busy, setBusy] = useState('')
  const [play, setPlay] = useState<PlayState>(IDLE)
  const [notice, setNotice] = useState('')
  const [pending, setPending] = useState(0)
  const [searchResults, setSearchResults] = useState<Track[]>([])
  const [suggestion, setSuggestion] = useState('')
  const [added, setAdded] = useState<Set<string>>(() => new Set())
  const writing = useRef(false)
  const onMusicPage = useRef(musicWindow)
  useEffect(() => { onMusicPage.current = musicWindow }, [musicWindow])
  const [shuffle, setShuffle] = useState(false)
  const [repeat, setRepeat] = useState<'off' | 'context' | 'track'>('off')
  const audio = useSyncExternalStore(subscribe, current)
  const player = useRef<Player | null>(null)
  const preferredVolume = useRef(.6)
  const owned = useRef<Release | null>(null)
  const intents = useRef<MusicIntents | null>(null)
  const generation = useRef('')
  const searchRequest = useRef<AbortController | null>(null)
  const searchSerial = useRef(0)
  const loadedMock = useRef(false)
  const loading = useRef(false)

  function report(error: unknown) {
    setNotice(error instanceof MusicFailure ? say(error.code, error.message) : error instanceof Error ? error.message : say(null))
    setPending(intents.current?.pending().length ?? 0)
  }
  async function loadChoices(offset = 0) {
    const reply = await call(`/api/music/playlists?offset=${offset}&limit=20`)
    if (reply.http !== 200) throw new MusicFailure(codeOf(reply.body) ?? 'spotify_unavailable')
    const page = reply.body as Choices
    setChoices(old => ({ items: [...(offset ? old?.items ?? [] : []), ...page.items.map(playlistFrom)], next: page.next_offset }))
  }
  async function loadItems(offset = 0) {
    const reply = await call(`/api/music/playlist/items?offset=${offset}&limit=50`)
    if (['spotify_playlist_required', 'spotify_playlist_ineligible'].includes(codeOf(reply.body) ?? '')) {
      setPlaylist(null); setTracks([]); setMore(null)
      if (codeOf(reply.body) === 'spotify_playlist_ineligible')
        setNotice('Spotify is connected. Your selected playlist must be private, non-collaborative and owned by you. Choose another playlist or create one below.')
      return loadChoices()
    }
    if (reply.http !== 200) throw new MusicFailure(codeOf(reply.body) ?? 'spotify_unavailable')
    const page = reply.body as Items
    const fresh = page.items.map(item => trackFrom(item.track, `p${item.position}`))
    tracksRef.current = offset ? [...tracksRef.current, ...fresh] : fresh
    setPlaylist(playlistFrom(page.playlist)); setTracks(tracksRef.current); setMore(page.next_offset)
    return page.next_offset
  }
  const load = useCallback(async () => {
    if (loading.current) return
    const back = new URLSearchParams(location.search).get('spotify') as keyof typeof BACK | null
    if (back) { const url = new URL(location.href); url.searchParams.delete('spotify'); history.replaceState(null, '', url.pathname + url.search + url.hash); setNotice(BACK[back] ?? '') }
    if (MOCK) {
      if (loadedMock.current) return
      loadedMock.current = true; setTracks(MOCK_TRACKS); setPlaylist(MOCK_PLAYLIST)
      setStatus({ phase: 'connected', connectionId: 'mock', playlistId: 'mock', read: true, write: false, inApp: true, mock: true }); return
    }
    loading.current = true
    setStatus(old => old.phase === 'connected' ? old : { phase: 'loading' })
    try {
      const reply = await call('/api/music/status')
      const next = statusFrom(reply.http, reply.body)
      const rememberedId = (reply.body as { connection_id?: unknown } | undefined)?.connection_id
      const nextId = next.phase === 'connected' ? next.connectionId : typeof rememberedId === 'string' ? rememberedId : ''
      if (nextId && generation.current !== nextId) {
        generation.current = nextId
        intents.current = new MusicIntents(nextId, call, {
          getItem: key => sessionStorage.getItem(key), setItem: (key, value) => sessionStorage.setItem(key, value), removeItem: key => sessionStorage.removeItem(key),
        })
      }
      setPending(intents.current?.pending().length ?? 0)
      if (next.phase === 'connected') {
        next.inApp = next.inApp && crossTabSupported()
        if (next.read) await loadItems()
      }
      setStatus(next)
    } catch (error) { setStatus(statusFrom(0)); report(error) }
    finally { loading.current = false }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps -- reads only setters/refs and stable helpers
  useEffect(() => { if (status.phase === 'connected' && status.inApp && !status.mock) void loadSpotifySDK().catch(report) }, [status])

  async function connect() {
    setBusy('connect'); setNotice('')
    try {
      const reply = await call('/auth/spotify/connect', 'POST', {})
      const url = (reply.body as { authorize_url?: string } | undefined)?.authorize_url
      if (reply.http === 200 && url && new URL(url).origin === 'https://accounts.spotify.com') { location.assign(url); return }
      throw new MusicFailure(codeOf(reply.body) ?? 'spotify_unavailable')
    } catch (error) { report(error) } finally { setBusy('') }
  }
  async function stopPlayer() {
    const p = player.current
    if (p && await p.pause() !== 'paused') throw new MusicFailure('spotify_outcome_unknown', 'Pause could not be verified. The player stays attached so voice cannot start unsafely.')
    p?.dispose(); player.current = null; setMusic(null); owned.current?.(); owned.current = null
    setPlay(old => ({ ...old, status: old.index >= 0 ? 'paused' : 'idle' }))
  }
  async function disconnect() {
    setBusy('disconnect'); setNotice('')
    try {
      await stopPlayer()
      const reply = await call('/api/connections/spotify', 'DELETE')
      if (reply.http !== 204) throw new MusicFailure(codeOf(reply.body) ?? 'spotify_unavailable')
      intents.current?.clear(); intents.current = null; generation.current = ''; setPending(0)
      setAdded(new Set())
      setTracks([]); setPlaylist(null); setChoices(null); setMore(null); setPlay(IDLE)
      await load(); setNotice('Spotify disconnected from Koe.')
    } catch (error) { report(error) } finally { setBusy('') }
  }
  async function choose(id: string) {
    if (status.phase !== 'connected') return
    setBusy(`choose:${id}`); setNotice('')
    try {
      await stopPlayer()
      const reply = await call('/api/music/playlist', 'PUT', { connection_id: status.connectionId, playlist_id: id })
      if (reply.http !== 200) throw new MusicFailure(codeOf(reply.body) ?? 'spotify_unavailable')
      setChoices(null); setAdded(new Set()); setStatus({ ...status, playlistId: id }); setPlay(IDLE); await loadItems()
    } catch (error) { report(error) } finally { setBusy('') }
  }
  function lostAudio() {
    owned.current = null
    if (onMusicPage.current) {
      setPlay(old => ({ ...old, status: old.index >= 0 ? 'paused' : 'idle' }))
      return // The same-page assistant keeps its explicitly activated SDK instance.
    }
    // Only after verified pause: removing the idle SDK device prevents remote resume during voice.
    player.current?.dispose(); player.current = null; setMusic(null)
    setPlay(old => ({ ...old, status: old.index >= 0 ? 'paused' : 'idle' }))
    setNotice('Paused for Koe. Press play when you want it back.')
  }
  function ensurePlayer(): Player | null {
    if (player.current) return player.current
    if (status.phase !== 'connected' || !status.inApp) return null
    let p: Player
    if (status.mock) p = createMockPlayer(tracksRef.current)
    else {
      if (!window.Spotify?.Player || !intents.current) { setNotice('Preparing Spotify’s player. Press Play again when it is ready.'); return null }
      p = spotifyPlayer(window.Spotify.Player, { connectionId: status.connectionId, tracks: () => tracksRef.current, request: call, intents: intents.current, volume: preferredVolume.current })
    }
    p.subscribe(() => {
      const seen = p.state(); setPlay(seen)
      const owner = current().owner
      if (seen.status === 'playing' && owner && owner !== 'music') { interruptVoiceForMusic(); void p.pause() }
    })
    setMusic({ playing: () => p.playing(), pause: () => p.pause() }); player.current = p
    return p
  }
  async function withAudio(run: (p: Player, fresh: boolean) => Promise<void>) {
    try {
      const fresh = player.current === null, p = ensurePlayer()
      if (!p) return
      p.activate?.() // preserve the click gesture before awaiting the lock/network
      owned.current = await acquire('music', lostAudio); setNotice(''); await run(p, fresh)
    }
    catch (error) { report(error) } finally { setPending(intents.current?.pending().length ?? 0) }
  }
  const controls = {
    start: (index: number) => withAudio(p => p.play(index)),
    resume: () => withAudio(async (p, fresh) => { if (fresh || play.status === 'idle') { await p.play(Math.max(0, play.index)); if (play.position) await p.seek(play.position) } else await p.resume() }),
    pause: async () => { try { if (player.current && await player.current.pause() !== 'paused') throw new MusicFailure('spotify_outcome_unknown') } catch (error) { report(error) } },
    next: () => withAudio(async (p, fresh) => { if (fresh) await p.play(Math.min(tracks.length - 1, play.index + 1)); else await p.next() }),
    previous: () => withAudio(async (p, fresh) => { if (fresh) await p.play(Math.max(0, play.index - 1)); else await p.previous() }),
    seek: async (ms: number) => { try { await player.current?.seek(ms) } catch (error) { report(error) } },
    setVolume: async (v: number) => { try { preferredVolume.current = v; await player.current?.setVolume(v); setPlay(old => ({ ...old, volume: v })) } catch (error) { report(error) } },
    toggleShuffle: () => withAudio(async p => { await p.shuffle?.(!shuffle); setShuffle(!shuffle) }),
    cycleRepeat: () => withAudio(async p => { const next = repeat === 'off' ? 'context' : repeat === 'context' ? 'track' : 'off'; await p.repeat?.(next); setRepeat(next) }),
  }
  async function search(q: string) {
    searchRequest.current?.abort(); const serial = ++searchSerial.current
    const controller = new AbortController(); searchRequest.current = controller; setBusy('search')
    try {
      const reply = await call(`/api/music/search?q=${encodeURIComponent(q.trim())}&limit=10`, 'GET', undefined, controller.signal)
      if (serial !== searchSerial.current) return
      if (reply.http !== 200) throw new MusicFailure(codeOf(reply.body) ?? 'spotify_unavailable')
      setSearchResults((reply.body as { items: ApiTrack[] }).items.map((track, i) => trackFrom(track, `search${i}`)))
    } catch (error) { if (!controller.signal.aborted) report(error) } finally { if (serial === searchSerial.current) setBusy('') }
  }
  async function mutate(kind: 'add' | 'remove' | 'move' | 'create', value: string | number, direction?: 'up' | 'down', expectedSnapshot?: string) {
    if (!intents.current || status.phase !== 'connected' || !status.write || writing.current) return
    writing.current = true
    setBusy(kind); setNotice('')
    try {
      let path = '/api/music/playlist/items', method = 'POST'
      let body: Record<string, unknown> = { snapshot_id: expectedSnapshot ?? playlist?.snapshot }
      if (kind === 'create') { path = '/api/music/playlists'; body = { name: value } }
      if (kind === 'add') body.uri = value
      if (kind === 'remove') { method = 'DELETE'; body = { ...body, uri: value, remove_all_occurrences: true } }
      if (kind === 'move') { path += '/order'; method = 'PUT'; body = { ...body, range_start: value, insert_before: Number(value) + (direction === 'up' ? -1 : 2), range_length: 1 } }
      await intents.current.write(path, method, body)
      if (kind === 'add') setAdded(old => new Set(old).add(String(value)))
      if (kind === 'create') { setChoices(null); setAdded(new Set()); await load() } else await loadItems()
      if (kind === 'remove') setAdded(old => { const next = new Set(old); next.delete(String(value)); return next })
      if (kind === 'add') setNotice('')
      else setNotice('Playlist updated.')
    } catch (error) {
      report(error)
      if (error instanceof MusicFailure && error.code === 'spotify_playlist_stale') await loadItems().catch(report)
    } finally { writing.current = false; setPending(intents.current.pending().length); setBusy('') }
  }
  async function inspect() {
    setBusy('inspect')
    try { await intents.current?.inspect(); setPending(intents.current?.pending().length ?? 0); setNotice(intents.current?.pending().length ? say('spotify_outcome_unknown') : 'Recorded actions are confirmed.'); await loadItems() }
    catch (error) { report(error) } finally { setBusy('') }
  }
  useEffect(() => () => {
    searchRequest.current?.abort()
    const p = player.current
    if (p) void p.pause().then(result => { if (result === 'paused') { p.dispose(); setMusic(null); owned.current?.() } })
    else owned.current?.()
  }, [])
  const track = play.index >= 0 ? tracks[play.index] ?? null : null
  const heldByVoice = audio.switching || (audio.owner !== null && audio.owner !== 'music')
  const voice = useMusicVoice(musicWindow && status.phase === 'connected' && status.inApp,
    status.phase === 'connected' && !status.mock ? status.connectionId : '', playlist?.id ?? '', async command => {
      if (command.action === 'pause') { await stopPlayer(); return 'applied' }
      if (['set_volume', 'volume_up', 'volume_down'].includes(command.action)) {
        const value = command.action === 'set_volume' ? (command.volume_percent ?? 60) / 100
          : Math.min(1, Math.max(0, preferredVolume.current + (command.action === 'volume_up' ? .1 : -.1)))
        preferredVolume.current = value
        if (player.current) await player.current.setVolume(value)
        setPlay(old => ({ ...old, volume: value }))
        return player.current ? 'applied' : 'deferred'
      }
      if (command.action === 'play_match') {
        if (!Number.isInteger(command.position) || command.position! < 0 || command.position! > 5000) throw Error('Invalid playlist position.')
        let offset = tracksRef.current.length
        while (offset <= command.position!) {
          const next = await loadItems(offset)
          if (tracksRef.current.length <= offset) break
          offset = tracksRef.current.length
          if (next == null) break
        }
      }
      const available = tracksRef.current
      let index = Math.max(0, play.index)
      if (command.action === 'play_match') index = command.position!
      if (command.action === 'next') index = available.findIndex((track, at) => at > play.index && track.playable)
      else if (command.action === 'previous') index = available.map((_, at) => at).filter(at => at < play.index && available[at].playable).at(-1) ?? -1
      if (index < 0 || !available[index]?.playable) throw Error('No available track in the allowed playlist.')
      const p = ensurePlayer()
      if (!p) throw Error('Open Music and press Play once to prepare this browser.')
      p.activate?.()
      owned.current = await acquire('music', lostAudio)
      await p.play(index, command.snapshot_id)
      if (command.action === 'play' && play.position > 0) await p.seek(play.position)
      if (p.state().status !== 'playing') throw Error('Playback was not confirmed.')
      return 'applied'
    }, (query, state) => {
      setSuggestion(query)
      setNotice(state === 'ambiguous' ? 'Several versions match. Tell Koe the artist or choose a track below.' : 'That song is not available in this playlist. Search below and add the version you want.')
      if (state !== 'ambiguous') void search(query)
    })
  async function prepareVoice() {
    const p = ensurePlayer()
    p?.activate?.() // Capture this Call click, before awaiting authentication/device discovery.
    if (voice.available) {
      if (!voice.enabled && !await voice.allow(true)) throw Error('Could not allow this playlist for voice. Try again.')
      await voice.waitReady()
    }
    if (p?.prepare) {
      try { await p.prepare() } catch (error) { report(error) } // Normal conversation remains available if Spotify is unavailable.
    }
  }
  return { status, tracks, playlist, more, choices, busy, play, track, notice, heldByVoice, pending, searchResults, suggestion, added, shuffle, repeat,
    voice,
    load, connect, choose, disconnect, search, mutate, inspect, prepareVoice,
    changePlaylist: async () => { try { await stopPlayer(); setPlaylist(null); await loadChoices() } catch (error) { report(error) } },
    loadMore: () => more !== null && loadItems(more).catch(report), moreChoices: () => choices?.next != null && loadChoices(choices.next).catch(report), ...controls }
}
export type Music = ReturnType<typeof useMusic>
export function useNow(active: boolean) {
  const [now, setNow] = useState(() => performance.now())
  useEffect(() => { if (!active) return; const timer = setInterval(() => setNow(performance.now()), 500); return () => clearInterval(timer) }, [active])
  return now
}
