import { useEffect, useRef, useState } from 'react'
import { ArrowSquareOut, SpeakerHigh, Warning, Phone, PhoneDisconnect, Microphone, MicrophoneSlash, PaperPlaneRight, Shuffle, Repeat, RepeatOnce, DotsThree, ArrowUp, ArrowDown, Trash } from '@phosphor-icons/react'
import gsap from 'gsap'
import { useGSAP } from '@gsap/react'
import type { useCall } from '../call/useCall'
import { mascotProfile, type MascotId } from '../mascot/catalog'
import { ApprovalPreview } from '../approvals/ApprovalPreview'
import { LiveWorkspace } from '../workspace/LiveWorkspace'
import { SpotifyIcon } from '../components/BrandIcon'
import { signIn } from '../session'
import { clock, type Track } from './model'
import { Art, Controls, Progress, Volume } from './Controls'
import { useNow, type Music } from './useMusic'
import { PlaylistPicker } from './PlaylistPicker'
import { MusicSearch } from './MusicSearch'

gsap.registerPlugin(useGSAP)

// /app/music: your dedicated playlist and the in-app player (when the server offers it), plus a plain way out to the
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
      {music.notice && !music.pending && <p className="music-notice" role="status">{music.notice}
        {music.notice === 'Spotify disconnected from Koe.' && <> To remove Koe on Spotify’s side too, use <a href="https://www.spotify.com/account/apps/" target="_blank" rel="noopener">Spotify app access</a>.</>}</p>}
      {connected && status.read
        ? music.playlist
          ? <div className="music-layout"><div className="music-library"><TrackList music={music} preview={setPreview} />
              {status.write && !status.mock && <MusicSearch music={music} />}</div>{inApp ? <NowPlaying music={music} /> : <PlayInSpotify />}</div>
          : <PlaylistPicker music={music} />
        : <NotHere music={music} />}
      {music.pending > 0 && <section className="music-pending" role="status"><p>An action is unconfirmed. Koe will not send it again. Inspect your playlist in Spotify before another change.</p>
        <button className="ghost" disabled={!!music.busy} onClick={() => void music.inspect()}>Check action status</button></section>}
      {music.picking && music.playlist && <PlaylistPicker music={music} modal />}
      {preview && <ConfirmEdit music={music} preview={preview} close={() => setPreview(null)} />}
      <footer className="music-external"><SpotifyIcon /><span>Prefer the Spotify app?</span><a href={music.playlist?.url ?? 'https://open.spotify.com/'} target="_blank" rel="noopener">Open Spotify <ArrowSquareOut /></a></footer>
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
      <div className="music-assistant-copy"><h2>Your music, with Koe.</h2><p><span className="dot" aria-hidden="true" /> Koe · {state}</p></div>
      <div className="music-assistant-actions">{active ? <>
        <button className="icon-btn" aria-label={call.muted ? 'Unmute microphone' : 'Mute microphone'} aria-pressed={call.muted} onClick={call.toggleMute}>{call.muted ? <MicrophoneSlash /> : <Microphone />}</button>
        <button className="end" onClick={call.stop}><PhoneDisconnect />End call</button>
      </> : <button className="primary" onClick={() => void call.start(token, music.status.phase === 'connected' && music.playlist ? music.prepareVoice : undefined)}><Phone />Call Koe</button>}</div>
    </header>
    <p className="music-assistant-hint">Talk about your day, or ask “play some keshi”.</p>
    <p className="music-assistant-note">Call to talk or choose music from this playlist. Koe finishes her reply before the music starts.</p>
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
  const snapshot = playlist.snapshot
  return (
    <section className="music-list" aria-labelledby="music-playlist">
      <div className="music-pl">
        <Art src={playlist.art} size="md" />
        <div><h2 id="music-playlist">{playlist.name}</h2><small>{tracks.length} tracks · {Math.round(total / 60000)} min</small></div>
        <a className="icon-btn" href={playlist.url} target="_blank" rel="noopener" aria-label="Open this playlist in Spotify" title="Open in Spotify"><SpotifyIcon /></a>
        <button className="ghost" disabled={music.heldByVoice} onClick={() => void music.changePlaylist()}>Change playlist</button>
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
            {status.phase === 'connected' && status.write && !status.mock && snapshot && <details className="music-track-menu">
              <summary aria-label={`Options for ${t.name}`}><DotsThree /></summary>
              <div><button aria-label={`Move ${t.name} up`} disabled={i === 0 || !!music.busy || music.pending > 0} onClick={() => preview({ kind: 'move', track: t, index: i, direction: 'up', snapshot })}><ArrowUp />Move up</button>
              <button aria-label={`Move ${t.name} down`} disabled={i >= tracks.length - 1 || !!music.busy || music.pending > 0} onClick={() => preview({ kind: 'move', track: t, index: i, direction: 'down', snapshot })}><ArrowDown />Move down</button>
              <button aria-label={`Remove all copies of ${t.name}`} disabled={!t.uri || !!music.busy || music.pending > 0} onClick={() => preview({ kind: 'remove', track: t, snapshot })}><Trash />Remove all copies</button></div>
            </details>}</li>
        })}
      </ol>
      {music.more !== null && <button className="ghost music-more" onClick={() => void music.loadMore()}>Load more tracks</button>}
    </section>
  )
}

function NowPlaying({ music }: { music: Music }) {
  const { track, play, heldByVoice } = music
  const display = track ?? music.tracks.find(item => item.playable)
  const now = useNow(play.status === 'playing')
  return (
    <section className="music-now" aria-label="Now playing">
      <Art src={display?.art ?? music.playlist?.art} size="lg" />
      <div className="music-meta">
        {!track && display && <small>READY TO PLAY</small>}
        <h2>{display?.name ?? 'Your next favourite'}</h2>
        <p>{display?.artists ?? 'Add a song to get started.'}</p>
      </div>
      <Progress music={music} now={now} />
      <Controls music={music} big />
      <Volume music={music} />
      {music.status.phase === 'connected' && !music.status.mock && <div className="music-modes">
        <button className="icon-btn" aria-label={`Shuffle ${music.shuffle ? 'on' : 'off'}`} title="Shuffle" aria-pressed={music.shuffle} disabled={!track || heldByVoice || !!music.busy || music.pending > 0} onClick={() => void music.toggleShuffle()}><Shuffle /></button>
        <button className="icon-btn" aria-label={`Repeat: ${music.repeat}`} title={`Repeat: ${music.repeat}`} aria-pressed={music.repeat !== 'off'} disabled={!track || heldByVoice || !!music.busy || music.pending > 0} onClick={() => void music.cycleRepeat()}>{music.repeat === 'track' ? <RepeatOnce /> : <Repeat />}</button>
      </div>}
      <p className="music-state" role="status">
        {heldByVoice ? 'Music is paused while Koe uses audio.' : play.status === 'unknown' ? 'Couldn’t confirm what’s playing.' : play.error}
      </p>
      {track && <a className="music-attrib" href={track.url} target="_blank" rel="noopener"><SpotifyIcon />Open in Spotify</a>}
    </section>
  )
}

type Preview = ({ kind: 'remove'; track: Track } | { kind: 'move'; track: Track; index: number; direction: 'up' | 'down' }) & { snapshot: string }

function ConfirmEdit({ music, preview, close }: { music: Music; preview: Preview; close: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  useEffect(() => { const element = dialog.current; element?.showModal(); return () => element?.close() }, [])
  const destination = music.playlist?.name ?? 'your Spotify account'
  const title = preview.kind === 'remove' ? 'Remove all copies' : 'Move track'
  const detail = preview.kind === 'remove' ? `Remove every occurrence of “${preview.track.name}” from “${destination}”.`
    : `Move “${preview.track.name}” ${preview.direction} one position in “${destination}”.`
  async function confirm() {
    const saved = preview.kind === 'move' ? await music.mutate('move', preview.index, preview.direction, preview.snapshot)
      : await music.mutate(preview.kind, preview.track.uri, undefined, preview.snapshot)
    if (saved) close()
  }
  return <dialog className="music-confirm" ref={dialog} aria-labelledby="music-confirm-title" onCancel={event => { event.preventDefault(); close() }}>
    <h2 id="music-confirm-title">{title}</h2><p>{detail}</p><div>
      <button className="ghost" disabled={!!music.busy} onClick={close}>Cancel</button>
      <button className="soft" disabled={!!music.busy || music.pending > 0} onClick={() => void confirm()}>{music.busy ? 'Saving…' : 'Confirm change'}</button>
    </div></dialog>
}
