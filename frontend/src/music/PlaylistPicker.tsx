import { useEffect, useRef, useState } from 'react'
import { X, Plus, ArrowLeft, Check, ArrowsClockwise } from '@phosphor-icons/react'
import { Art } from './Controls'
import type { Music } from './useMusic'

export function PlaylistPicker({ music, modal = false }: { music: Music; modal?: boolean }) {
  const dialog = useRef<HTMLDialogElement>(null)
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState('')
  useEffect(() => { const element = dialog.current; if (modal) element?.showModal(); return () => element?.close() }, [modal])
  const content = <>
    <header className="music-picker-head"><div><p className="music-eyebrow">YOUR LIBRARY</p><h2 id="music-pick">{creating ? 'Create a playlist' : 'Choose your playlist'}</h2></div>
      {modal && <button className="icon-btn" aria-label="Close playlist selector" onClick={music.cancelPicker}><X /></button>}
    </header>
    {creating ? <form className="music-create" onSubmit={async event => {
      event.preventDefault()
      if (await music.mutate('create', name.trim())) { setCreating(false); setName('') }
    }}>
      <label htmlFor="playlist-name">Playlist name</label>
      <input id="playlist-name" autoFocus placeholder="Evening favourites" value={name} maxLength={100} onChange={event => setName(event.target.value)} />
      <p>Creates a private playlist in your Spotify account and selects it for Koe.</p>
      <footer><button type="button" className="ghost" disabled={!!music.busy} onClick={() => setCreating(false)}><ArrowLeft />Back</button>
        <button className="primary" disabled={!name.trim() || !!music.busy || music.pending > 0 || music.heldByVoice}>{music.busy === 'create' ? 'Creating…' : 'Create private playlist'}</button></footer>
    </form> : <>
      <p className="note">Private playlists you own. Selecting a playlist won’t start playback.</p>
      <div className="music-picker-toolbar"><button className="ghost" disabled={!!music.busy} onClick={() => void music.refreshChoices()}><ArrowsClockwise />Refresh</button>
        {music.status.phase === 'connected' && music.status.write && <button className="soft" onClick={() => setCreating(true)}><Plus />New playlist</button>}</div>
      {music.choices === null ? <p role="status">Loading your playlists…</p> : music.choices.items.length === 0 ? <p className="music-picker-empty">No private playlists yet. Create one here, or make a playlist you own private in Spotify, then refresh.</p> :
        <ul className="music-playlist-options">{music.choices.items.map(playlist => <li key={playlist.id}><Art src={playlist.art} size="sm" /><span><strong>{playlist.name}</strong><small>Private playlist</small></span>
          <button className="soft" disabled={!!music.busy || music.heldByVoice} aria-label={`Choose ${playlist.name}`} onClick={() => void music.choose(playlist.id)}>
            {music.busy === `choose:${playlist.id}` ? 'Selecting…' : playlist.id === music.playlist?.id ? <><Check />Selected</> : 'Choose'}</button></li>)}</ul>}
      {music.choices?.next != null && <button className="ghost" onClick={() => void music.moreChoices()}>Show more</button>}
    </>}
    {modal && music.notice && <p className="music-inline-status" role="status">{music.notice}</p>}
    {music.pending > 0 && <p className="music-inline-status">A previous change needs checking. <button className="music-link" onClick={() => void music.inspect()}>Check action status</button></p>}
  </>
  return modal ? <dialog ref={dialog} className="music-picker-dialog" aria-labelledby="music-pick" onCancel={event => { event.preventDefault(); music.cancelPicker() }}>{content}</dialog>
    : <section className="music-picker-panel" aria-labelledby="music-pick">{content}</section>
}
