import { useEffect, useRef, useState } from 'react'
import { Check, MagnifyingGlass } from '@phosphor-icons/react'
import { music as request } from './api'
import { Art } from './Controls'
import { clock } from './model'
import type { Music } from './useMusic'

type Artist = { id: string; name: string; image_url: string | null }
export function MusicSearch({ music }: { music: Music }) {
  const [draft, setDraft] = useState({ text: '', suggestion: '' })
  const query = draft.suggestion === music.suggestion ? draft.text : music.suggestion
  const [artists, setArtists] = useState<Artist[]>([])
  const [open, setOpen] = useState(false)
  const [selected, setSelected] = useState(-1)
  const [hint, setHint] = useState('')
  const [searched, setSearched] = useState(false)
  const search = useRef(music.search)
  useEffect(() => { search.current = music.search })
  useEffect(() => {
    const controller = new AbortController()
    const timer = setTimeout(async () => {
      if (query.trim().length < 2) { setArtists([]); setHint(''); await search.current(''); setSearched(false); return }
      setSearched(true)
      void search.current(query)
      if (query.startsWith('artist:')) { setArtists([]); return }
      setHint('Finding artists…')
      try {
        const reply = await request(`/api/music/search?kind=artist&limit=5&q=${encodeURIComponent(query.trim())}`, 'GET', undefined, controller.signal)
        if (controller.signal.aborted) return
        if (reply.http !== 200) throw Error('Artist suggestions are unavailable. You can still search tracks.')
        setArtists((reply.body as { items: Artist[] }).items); setHint('')
      } catch (error) { if (!controller.signal.aborted) { setArtists([]); setHint(error instanceof Error ? error.message : 'Could not load artists.') } }
    }, 400)
    return () => { clearTimeout(timer); controller.abort() }
  }, [query])
  function choose(artist: Artist) {
    const text = `artist:"${artist.name.replaceAll('"', '').slice(0, 85)}"`
    setDraft({ text, suggestion: music.suggestion }); setOpen(false); setSelected(-1)
  }
  return <section className="music-search" aria-labelledby="music-search-heading">
    <h2 id="music-search-heading">Find your next track</h2><p className="note">Search songs or artists. Add a favourite straight to your playlist.</p>
    <form className="music-search-form" onSubmit={event => { event.preventDefault(); if (open && selected >= 0 && artists[selected]) choose(artists[selected]); else { setOpen(false); setSearched(true); void music.search(query) } }}>
      <div className="music-search-field" onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false) }}>
        <MagnifyingGlass aria-hidden="true" />
        <input type="search" role="combobox" aria-label="Search Spotify tracks" aria-autocomplete="list" aria-controls="artist-suggestions" aria-expanded={open && artists.length > 0}
          aria-activedescendant={open && selected >= 0 ? `artist-${selected}` : undefined} placeholder="Search a song or artist" maxLength={100} value={query}
          onFocus={() => setOpen(true)} onChange={event => { setDraft({ text: event.target.value, suggestion: music.suggestion }); setArtists([]); setOpen(true); setSelected(-1) }}
          onKeyDown={event => { if (event.key === 'Escape') setOpen(false); if (['ArrowDown', 'ArrowUp'].includes(event.key) && artists.length) { event.preventDefault(); setOpen(true); setSelected(old => old < 0 ? (event.key === 'ArrowDown' ? 0 : artists.length - 1) : (old + (event.key === 'ArrowDown' ? 1 : artists.length - 1)) % artists.length) } }} />
        {open && artists.length > 0 && <ul id="artist-suggestions" className="music-suggestions" role="listbox" aria-label="Artists">{artists.map((artist, index) => <li role="option" id={`artist-${index}`} key={artist.id} aria-selected={selected === index} onMouseDown={event => event.preventDefault()} onClick={() => choose(artist)}>
          <Art src={artist.image_url} size="sm" /><span><strong>{artist.name}</strong><small>Artist · find songs</small></span>
        </li>)}</ul>}
      </div><button className="soft" disabled={!query.trim() || music.searching}>{music.searching ? 'Searching…' : 'Search'}</button>
    </form>
    {open && hint && <p className="music-inline-status" role="status">{hint}</p>}
    {searched && !music.searching && music.searchResults.length === 0 && <p className="music-inline-status" role="status">No tracks found. Try another song or artist.</p>}
    <ul className="music-search-results" aria-busy={music.searching}>{music.searchResults.map((track, index) => <li key={`${track.id}-${index}`}><Art src={track.art} size="md" /><span><a href={track.url} target="_blank" rel="noopener"><strong>{track.name}</strong></a><small>{track.artists}</small></span><time>{clock(track.ms)}</time>
      <button className="soft" aria-label={music.added.has(track.uri) ? `Added ${track.name}` : `Add ${track.name}`} disabled={!track.playable || !!music.busy || music.pending > 0 || music.added.has(track.uri)}
        onClick={() => void music.mutate('add', track.uri, undefined, music.playlist?.snapshot)}>{music.added.has(track.uri) ? <><Check />Added</> : 'Add'}</button></li>)}</ul>
  </section>
}
