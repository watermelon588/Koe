import { Art, Controls } from './Controls'
import { SpotifyIcon } from '../components/BrandIcon'
import { positionAt } from './model'
import { useNow, type Music } from './useMusic'

// Visible on every page while a track is loaded, so music is never playing from a screen you can't see.
// Hidden on #music (the full player is there) and during a call (music is paused then).
export function MiniPlayer({ music, hidden }: { music: Music; hidden: boolean }) {
  const { track, play } = music
  const now = useNow(!hidden && play.status === 'playing')
  if (hidden || !track) return null
  const done = track.ms ? positionAt(play, now, track.ms) / track.ms : 0
  return (
    <aside className="mini-player" aria-label="Music">
      <Art src={track.art} size="sm" />
      <a className="mini-meta" href="/app/music">
        <span><SpotifyIcon size={14} /> {track.name}</span>
        <small>{music.heldByVoice ? 'Paused while Koe uses audio' : play.status === 'unknown' ? 'Playback unknown' : track.artists}</small>
      </a>
      <Controls music={music} />
      <span className="mini-progress" aria-hidden="true"><span style={{ transform: `scaleX(${done})` }} /></span>
    </aside>
  )
}
