import { useEffect, useRef, useState, type FormEvent } from 'react'
import { ArrowSquareOut, SpeakerHigh, Warning, Phone, PhoneDisconnect, Microphone, MicrophoneSlash, PaperPlaneRight, Check } from '@phosphor-icons/react'
import gsap from 'gsap'
import { useGSAP } from '@gsap/react'
import type { useCall } from '../call/useCall'
import { mascotProfile, type MascotId } from '../mascot/catalog'
import { ApprovalPreview } from '../approvals/ApprovalPreview'
import { LiveWorkspace } from '../workspace/LiveWorkspace'
import { SpotifyIcon } from '../components/BrandIcon'
import { signIn } from '../session'
import { appPlaylist, clock, playlistId, webPlaylist, type Playlist, type Track } from './model'
import { Art, Controls, Progress, Volume } from './Controls'
import { useNow, type Music } from './useMusic'

gsap.registerPlugin(useGSAP)

// #music: your dedicated playlist and the in-app player (when the server offers it), plus a plain way out to the
// Spotify app or web player. Koe can't see or pause music played there, and the page says so.
export function MusicPage({ music, call, model, token }: { music: Music; call: ReturnType<typeof useCall>; model: MascotId; token: string }) {
  const root = useRef<HTMLElement>(null)
  const [preview, setPreview] = useState<Preview | null>(null)
  const { status, load } = music
  useEffect(() => { void load() }, [load])
  const connected = status.phase === 'connected'
  const inApp = connected && status.inApp
  useGSAP(() => {
    const media = gsap.matchMedia()
    media.add('(prefers-reduced-motion: no-preference)', () => {
      gsap.from('.music-head, .music-assistant, .music-layout, .music-search', { y: 12, opacity: 0, duration: .45, stagger: .06, ease: 'power2.out' })
    })
    return () => media.revert()
  }, { scope: root, dependencies: [connected, !!music.playlist], revertOnUpdate: true })
  return (
    <main ref={root} className="music-page" id="main-content" tabIndex={-1}>
      <header className="music-head">
        <div><p className="music-eyebrow">A little company. Your kind of music.</p><h1><SpotifyIcon size={30} /> Music</h1><p>Listen, discover, or ask Koe to find your next song.</p></div>
        {connected && status.mock && <span className="music-mock" role="note">Mock data · not Spotify · no sound</span>}
        {connected && !status.mock && <button className="ghost" disabled={music.busy === 'disconnect'} onClick={() => void music.disconnect()}>
          {music.busy === 'disconnect' ? 'Disconnecting…' : 'Disconnect Spotify'}</button>}
      </header>
      <MusicAssistant music={music} call={call} model={model} token={token} />
      {music.notice && <p className="music-notice" role="status">{music.notice}
        {music.notice === 'Spotify disconnected from Koe.' && <> To remove Koe on Spotify’s side too, use <a href="https://www.spotify.com/account/apps/" target="_blank" rel="noopener">Spotify app access</a>.</>}</p>}
      {connected && status.read
        ? music.playlist
          ? <><div className="music-layout"><TrackList music={music} preview={setPreview} />{inApp ? <NowPlaying music={music} /> : <PlayInSpotify />}</div>
              {status.write && !status.mock && <Search music={music} />}</>
          : <Picker music={music} preview={setPreview} />
        : <NotHere music={music} />}
      {music.pending > 0 && <section className="music-pending" role="status"><p>An action is unconfirmed. Koe will not send it again. Inspect your playlist in Spotify before another change.</p>
        <button className="ghost" disabled={!!music.busy} onClick={() => void music.inspect()}>Check action status</button></section>}
      {preview && <ConfirmEdit music={music} preview={preview} close={() => setPreview(null)} />}
      <Elsewhere playlist={connected && !status.mock ? music.playlist : null} />
    </main>
  )
}

function MusicAssistant({ music, call, model, token }: { music: Music; call: ReturnType<typeof useCall>; model: MascotId; token: string }) {
  const [draft, setDraft] = useState('')
  const active = call.state !== 'idle'
  const state = { idle: 'Here when you need me', connecting: 'Getting ready…', listening: 'Listening', speaking: 'Speaking', thinking: 'Thinking' }[call.state]
  return <section className="music-assistant" aria-label="Koe music assistant" data-active={active}>
    <header className="music-assistant-head">
      <img className="music-assistant-portrait" src={mascotProfile(model).portrait} width="64" height="64" alt={mascotProfile(model).name} />
      <div className="music-assistant-copy"><h2>A little company, while you listen.</h2><p><span className="dot" aria-hidden="true" /> Koe · {state}</p></div>
      <div className="music-assistant-actions">{active ? <>
        <button className="icon-btn" aria-label={call.muted ? 'Unmute microphone' : 'Mute microphone'} aria-pressed={call.muted} onClick={call.toggleMute}>{call.muted ? <MicrophoneSlash /> : <Microphone />}</button>
        <button className="end" onClick={call.stop}><PhoneDisconnect />End call</button>
      </> : <button className="primary" onClick={() => void call.start(token, music.status.phase === 'connected' && music.playlist ? music.prepareVoice : undefined)}><Phone />Call Koe</button>}</div>
    </header>
    <p className="music-assistant-hint">Ask about your day, or say “play some Kesha” or “play my favourite song”.</p>
    <p className="music-assistant-note">Calling allows Koe to control this playlist. For music, she finishes her reply and ends the call before playback. Call again to pause and talk.</p>
    {music.voice.available && music.voice.enabled && <button className="music-link" onClick={() => void music.voice.allow(false)}>Disable voice controls</button>}
    {(call.error || music.voice.notice) && <p className="music-inline-status" role="status">{call.error || music.voice.notice}</p>}
    {call.lines.length > 0 && <ol className="music-conversation" aria-live="polite">{call.lines.slice(-6).map(line => <li key={line.id} data-who={line.who}><small>{line.who === 'you' ? 'You' : line.who === 'koe' ? 'Koe' : 'Activity'}</small><p>{line.text}</p></li>)}</ol>}
    {call.approval && <section className="music-call-approval"><ApprovalPreview action={call.approval} /><div className="pair"><button className="ghost" disabled={call.deciding} onClick={() => call.decide(false)}>Cancel</button><button className="soft" disabled={call.deciding} onClick={() => call.decide(true)}>Confirm</button></div></section>}
    {active && <form className="music-assistant-composer" onSubmit={event => { event.preventDefault(); if (call.send(draft)) setDraft('') }}>
      <input aria-label="Message" placeholder="Or type to Koe…" value={draft} maxLength={2000} onChange={event => setDraft(event.target.value)} />
      <button className="icon-btn" aria-label="Send" disabled={!draft.trim() || call.state === 'connecting'}><PaperPlaneRight /></button>
    </form>}
    {call.workspace.active && <details className="music-call-work"><summary>View your workspace</summary><LiveWorkspace inline work={call.workspace} decision={id => call.approval?.id === id ? { deciding: call.deciding, decide: call.decide } : null} /></details>}
  </section>
}

function NotHere({ music }: { music: Music }) {
  const s = music.status
  return (
    <section className="music-empty" aria-live="polite">
      {s.phase === 'loading' ? <p>Checking Spotify…</p>
        : s.phase === 'signed-out' ? <><h2>Sign in to use music</h2><p>Spotify connects to your Koe account.</p><button className="soft" onClick={signIn}>Sign in with Google</button></>
        : s.phase === 'unavailable' ? <><Warning size={22} aria-hidden="true" /><h2>{s.retryable ? 'Couldn’t load music' : 'In-app music is unavailable'}</h2><p>{s.message} You can still listen in Spotify below.</p>
            {s.retryable && <button className="soft" onClick={() => void music.load()}>Retry</button>}</>
        : s.phase === 'disconnected' ? <><SpotifyIcon size={26} aria-hidden="true" /><h2>{s.reconnect ? 'Connect Spotify again' : 'Connect Spotify'}</h2>
            <p>{s.message || 'For your playlist on this page. Koe’s voice never hears or sees your music.'}</p>
            <button className="soft" disabled={!s.canConnect || music.busy === 'connect'} onClick={() => void music.connect()}>
              {music.busy === 'connect' ? 'Opening Spotify…' : 'Connect Spotify'}</button></>
        : <><h2>Playlist access is off</h2><p>Spotify is connected, but Koe can’t read playlists right now. Try connecting again.</p></>}
    </section>
  )
}

// First visit after connecting: pick which of your private playlists Koe shows. Choosing never plays anything.
function Picker({ music, preview }: { music: Music; preview: (p: Preview) => void }) {
  const list = music.choices
  const [name, setName] = useState('Koe — Chill')
  return (
    <section className="music-empty music-picker" aria-labelledby="music-pick">
      <h2 id="music-pick">Choose your playlist</h2>
      <p>Only private playlists you own are listed. You can change it later.</p>
      <p className="actions">
        {music.status.phase === 'connected' && music.status.playlistId && <a className="ghost" href={webPlaylist(music.status.playlistId)} target="_blank" rel="noopener">Open selected playlist in Spotify</a>}
        <button className="ghost" onClick={() => void music.load()}>Refresh playlists</button>
      </p>
      {list === null ? <p>Loading your playlists…</p> : !list.items.length ? <p>No eligible private playlists found. Create one below, or make a playlist you own private in Spotify, then refresh playlists.</p>
        : <ul>{list.items.map((p) => <li key={p.id}>
            <Art src={p.art} size="sm" /><span>{p.name}</span>
            <button className="soft" disabled={!!music.busy} onClick={() => void music.choose(p.id)}>{music.busy === `choose:${p.id}` ? 'Choosing…' : 'Choose'}</button>
          </li>)}</ul>}
      {list?.next != null && <button className="ghost" onClick={() => void music.moreChoices()}>Show more</button>}
      {music.status.phase === 'connected' && music.status.write && <form className="music-edit-form" onSubmit={event => { event.preventDefault(); preview({ kind: 'create', name: name.trim() }) }}>
        <label>New private playlist<input aria-label="New playlist name" value={name} maxLength={100} onChange={event => setName(event.target.value)} /></label>
        <button className="soft" disabled={!name.trim() || !!music.busy || music.pending > 0}>Create private playlist</button></form>}
    </section>
  )
}

function PlayInSpotify() {
  return (
    <section className="music-now music-elsewhere-note" aria-label="Playback">
      <SpotifyIcon size={28} aria-hidden="true" />
      <h2>Play it in Spotify</h2>
      <p>Playing inside Koe isn’t switched on yet. Open the playlist in the Spotify app or web player below, or tap a track to open it.</p>
    </section>
  )
}

function TrackList({ music, preview }: { music: Music; preview: (p: Preview) => void }) {
  const { status, tracks, play, playlist } = music
  const inApp = status.phase === 'connected' && status.inApp
  const total = tracks.reduce((n, t) => n + t.ms, 0)
  if (!playlist) return null
  return (
    <section className="music-list" aria-labelledby="music-playlist">
      <div className="music-pl">
        <Art src={playlist.art} size="md" />
        <div><h2 id="music-playlist">{playlist.name}</h2><small>{tracks.length} tracks · {Math.round(total / 60000)} min</small></div>
        <a className="icon-btn" href={playlist.url} target="_blank" rel="noopener" aria-label="Open this playlist in Spotify" title="Open in Spotify"><SpotifyIcon /></a>
        <button className="ghost" disabled={!!music.busy || music.pending > 0} onClick={() => void music.changePlaylist()}>Change playlist</button>
      </div>
      <ol className="music-tracks">
        {tracks.map((t, i) => {
          const here = i === play.index
          const row = <>
            <span className="music-n">{here ? <SpeakerHigh aria-hidden="true" /> : i + 1}</span>
            <Art src={t.art} size="sm" />
            <span className="music-tt"><span>{t.name}</span><small>{t.playable ? t.artists : 'Not available to play'}</small></span>
            <time>{clock(t.ms)}</time>
          </>
          // No in-app player: each row opens the track in Spotify instead (and says so).
          return <li key={`${t.id}-${i}`} className="music-edit-row">{inApp
            ? <button className="music-track" aria-current={here || undefined} disabled={!t.playable || music.heldByVoice}
                aria-label={t.playable ? `Play ${t.name} by ${t.artists}` : `${t.name} isn’t available`} onClick={() => void music.start(i)}>{row}</button>
            : <a className="music-track" href={t.url} target="_blank" rel="noopener" aria-label={`Open ${t.name} by ${t.artists} in Spotify`}>{row}</a>}
            {status.phase === 'connected' && status.write && !status.mock && <span className="music-edit-actions">
              <button aria-label={`Move ${t.name} up`} disabled={i === 0 || !!music.busy || music.pending > 0} onClick={() => preview({ kind: 'move', track: t, index: i, direction: 'up', snapshot: playlist.snapshot })}>↑</button>
              <button aria-label={`Move ${t.name} down`} disabled={i >= tracks.length - 1 || !!music.busy || music.pending > 0} onClick={() => preview({ kind: 'move', track: t, index: i, direction: 'down', snapshot: playlist.snapshot })}>↓</button>
              <button aria-label={`Remove all copies of ${t.name}`} disabled={!t.uri || !!music.busy || music.pending > 0} onClick={() => preview({ kind: 'remove', track: t, snapshot: playlist.snapshot })}>Remove all</button>
            </span>}</li>
        })}
      </ol>
      {music.more !== null && <button className="ghost music-more" onClick={() => void music.loadMore()}>Load more tracks</button>}
    </section>
  )
}

function NowPlaying({ music }: { music: Music }) {
  const { track, play, heldByVoice } = music
  const now = useNow(play.status === 'playing')
  return (
    <section className="music-now" aria-label="Now playing">
      <Art src={track?.art} size="lg" />
      <div className="music-meta">
        <h2>{track?.name ?? 'Nothing playing'}</h2>
        <p>{track?.artists ?? 'Press play, or pick a track.'}</p>
      </div>
      <Progress music={music} now={now} />
      <Controls music={music} big />
      <Volume music={music} />
      {music.status.phase === 'connected' && !music.status.mock && <div className="music-modes">
        <button className="ghost" aria-pressed={music.shuffle} disabled={!track || heldByVoice || !!music.busy || music.pending > 0} onClick={() => void music.toggleShuffle()}>Shuffle {music.shuffle ? 'on' : 'off'}</button>
        <button className="ghost" disabled={!track || heldByVoice || !!music.busy || music.pending > 0} onClick={() => void music.cycleRepeat()}>Repeat: {music.repeat}</button>
      </div>}
      <p className="music-state" role="status">
        {heldByVoice ? 'Music is paused while Koe uses audio.' : play.status === 'unknown' ? 'Couldn’t confirm what’s playing.' : play.error}
      </p>
      {track && <a className="music-attrib" href={track.url} target="_blank" rel="noopener"><SpotifyIcon />Open in Spotify</a>}
    </section>
  )
}

type Preview = ({ kind: 'add'; track: Track } | { kind: 'remove'; track: Track } | { kind: 'move'; track: Track; index: number; direction: 'up' | 'down' } | { kind: 'create'; name: string }) & { snapshot?: string }

function Search({ music }: { music: Music }) {
  const [draft, setDraft] = useState({ text: '', suggestion: '' })
  const query = draft.suggestion === music.suggestion ? draft.text : music.suggestion
  return <section className="music-search" aria-labelledby="music-search-heading">
    <h2 id="music-search-heading">Find your next track</h2><p className="note">Discover a song. One click adds it to your playlist.</p>
    <form className="music-edit-form" onSubmit={event => { event.preventDefault(); void music.search(query) }}>
      <label>Search Spotify<input type="search" aria-label="Search Spotify tracks" placeholder="A song, an artist, a little inspiration…" maxLength={100} value={query} onChange={event => setDraft({ text: event.target.value, suggestion: music.suggestion })} /></label>
      <button className="soft" disabled={!query.trim() || music.busy === 'search'}>{music.busy === 'search' ? 'Searching…' : 'Search'}</button>
    </form>
    <ul>{music.searchResults.map((track, index) => <li key={`${track.id}-${index}`}><Art src={track.art} size="md" /><span><a href={track.url} target="_blank" rel="noopener"><strong>{track.name}</strong></a><small>{track.artists}</small></span><time>{clock(track.ms)}</time>
      <button className="soft" aria-label={music.added.has(track.uri) ? `Added ${track.name}` : `Add ${track.name}`} disabled={!track.playable || !!music.busy || music.pending > 0 || music.added.has(track.uri)}
        onClick={() => void music.mutate('add', track.uri, undefined, music.playlist?.snapshot)}>{music.added.has(track.uri) ? <><Check />Added</> : music.busy === 'add' ? 'Adding…' : 'Add'}</button></li>)}</ul>
  </section>
}

function ConfirmEdit({ music, preview, close }: { music: Music; preview: Preview; close: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  useEffect(() => { const element = dialog.current; element?.showModal(); return () => element?.close() }, [])
  const destination = music.playlist?.name ?? 'your Spotify account'
  const title = preview.kind === 'create' ? 'Create private playlist' : preview.kind === 'add' ? 'Add one copy' : preview.kind === 'remove' ? 'Remove all copies' : 'Move track'
  const detail = preview.kind === 'create' ? `Create “${preview.name}” as a private playlist and select it in Koe.`
    : preview.kind === 'remove' ? `Remove every occurrence of “${preview.track.name}” from “${destination}”.`
    : preview.kind === 'add' ? `Add one copy of “${preview.track.name}” to the end of “${destination}”.`
    : `Move “${preview.track.name}” ${preview.direction} one position in “${destination}”.`
  async function confirm() {
    if (preview.kind === 'create') await music.mutate('create', preview.name)
    else if (preview.kind === 'move') await music.mutate('move', preview.index, preview.direction, preview.snapshot)
    else await music.mutate(preview.kind, preview.track.uri, undefined, preview.snapshot)
    close()
  }
  return <dialog className="music-confirm" ref={dialog} aria-labelledby="music-confirm-title" onCancel={event => { event.preventDefault(); close() }}>
    <h2 id="music-confirm-title">{title}</h2><p>{detail}</p><div>
      <button className="ghost" disabled={!!music.busy} onClick={close}>Cancel</button>
      <button className="soft" disabled={!!music.busy || music.pending > 0} onClick={() => void confirm()}>{music.busy ? 'Saving…' : 'Confirm change'}</button>
    </div></dialog>
}

// The way out: the official app or web player. A link you paste stays on this device (localStorage).
const LINK_KEY = 'koe-spotify-playlist'
function savedLink() { try { return localStorage.getItem(LINK_KEY) ?? '' } catch { return '' } }

function Elsewhere({ playlist }: { playlist: Playlist | null }) {
  const [saved, setSaved] = useState(savedLink)
  const [draft, setDraft] = useState('')
  const [error, setError] = useState('')
  const [editing, setEditing] = useState(false)
  const id = playlist?.id ?? (saved || null)
  function save(e: FormEvent) {
    e.preventDefault()
    const found = playlistId(draft)
    if (!found) return setError('That isn’t a Spotify playlist link. In Spotify: Share → Copy link to playlist.')
    try { localStorage.setItem(LINK_KEY, found) } catch { /* kept for this visit only */ }
    setSaved(found); setDraft(''); setError(''); setEditing(false)
  }
  return (
    <section className="music-elsewhere" aria-labelledby="music-elsewhere">
      <div className="music-elsewhere-copy">
        <h2 id="music-elsewhere">Listen in Spotify</h2>
        <p>Opens the Spotify app or the web player. Koe can’t see or pause music there, so pause it yourself before a call.</p>
      </div>
      <div className="music-open">
        {id && <a className="soft" href={appPlaylist(id)}><SpotifyIcon />Open in Spotify app</a>}
        <a className="ghost" href={id ? webPlaylist(id) : 'https://open.spotify.com/'} target="_blank" rel="noopener"><ArrowSquareOut />Open web player</a>
      </div>
      {!playlist && (saved && !editing
        ? <p className="music-saved">Your playlist link is saved on this device. <button className="music-link" onClick={() => setEditing(true)}>Change</button></p>
        : <form className="music-link-form" onSubmit={save}>
            <input value={draft} onChange={(e) => { setDraft(e.target.value); setError('') }} placeholder="https://open.spotify.com/playlist/…"
              aria-label="Your Spotify playlist link" aria-invalid={!!error || undefined} aria-describedby="music-link-help" inputMode="url" autoComplete="off" />
            <button className="soft" disabled={!draft.trim()}>Save link</button>
            <small id="music-link-help" role={error ? 'alert' : undefined}>{error || 'Optional: paste your playlist’s share link so these buttons open it.'}</small>
          </form>)}
    </section>
  )
}
