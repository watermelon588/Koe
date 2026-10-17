import { useRef, useState, type CSSProperties } from 'react'
import { Pause, Play, SkipBack, SkipForward, SpeakerHigh, SpeakerLow, SpeakerX, Minus, Plus } from '@phosphor-icons/react'
import { clock, positionAt } from './model'
import type { Music } from './useMusic'
import './music.css'
import { SpotifyIcon } from '../components/BrandIcon'

// Shared by the Music page and the mini player.

export function Art({ src, size }: { src: string | null | undefined; size: 'sm' | 'md' | 'lg' }) {
  const [failed, setFailed] = useState<string | null>(null)
  return src && failed !== src ? <img className={`music-art ${size}`} src={src} alt="" loading="lazy" onError={() => setFailed(src)} />
    : <span className={`music-art ${size} blank`} aria-hidden="true"><SpotifyIcon /></span>
}

export function Controls({ music, big }: { music: Music; big?: boolean }) {
  const { play, heldByVoice, track } = music
  const on = play.status === 'playing' || play.status === 'starting' || play.status === 'unknown'
  const first = music.tracks.findIndex((t) => t.playable)
  const toggle = () => (on ? music.pause() : track ? music.resume() : first >= 0 && music.start(first))
  return (
    <div className={`music-controls${big ? ' big' : ''}`} role="group" aria-label="Playback">
      <button className="icon-btn" aria-label="Previous track" disabled={!track || heldByVoice} onClick={() => void music.previous()}><SkipBack weight="fill" /></button>
      <button className="music-play" aria-label={on ? 'Pause' : 'Play'} disabled={heldByVoice || (!track && first < 0)} onClick={() => void toggle()}>
        {on ? <Pause weight="fill" /> : <Play weight="fill" />}
      </button>
      <button className="icon-btn" aria-label="Next track" disabled={!track || heldByVoice} onClick={() => void music.next()}><SkipForward weight="fill" /></button>
    </div>
  )
}

// Seek bar: moves locally while dragging, sends one seek when you let go.
export function Progress({ music, now }: { music: Music; now: number }) {
  const [drag, setDrag] = useState<number | null>(null)
  const ms = music.track?.ms ?? 0
  const at = drag ?? positionAt(music.play, now, ms)
  const commit = () => { if (drag !== null) void music.seek(drag); setDrag(null) }
  return (
    <div className="music-progress">
      <time>{clock(at)}</time>
      <input type="range" min={0} max={ms} step={1000} value={at} disabled={!music.track || music.heldByVoice}
        aria-label="Seek" aria-valuetext={`${clock(at)} of ${clock(ms)}`}
        onChange={(e) => setDrag(Number(e.target.value))} onPointerUp={commit} onKeyUp={commit} onBlur={commit} />
      <time>{clock(ms)}</time>
    </div>
  )
}

export function Volume({ music }: { music: Music }) {
  const [drag, setDrag] = useState<number | null>(null)
  const previous = useRef(.6)
  const v = drag ?? music.play.volume
  const Icon = v === 0 ? SpeakerX : v < 0.5 ? SpeakerLow : SpeakerHigh
  const commit = () => { if (drag !== null) { void music.setVolume(drag); setDrag(null) } }
  return (
    <div className="music-volume" role="group" aria-label="Volume controls" style={{ '--volume': `${v * 100}%` } as CSSProperties}>
      <button className="icon-btn" aria-label={v === 0 ? 'Unmute music' : 'Mute music'} onClick={() => { if (v > 0) previous.current = v; void music.setVolume(v === 0 ? previous.current : 0) }}><Icon /></button>
      <button className="icon-btn volume-step" aria-label="Decrease volume" disabled={v === 0} onClick={() => void music.setVolume(Math.max(0, v - .05))}><Minus /></button>
      <input type="range" min={0} max={1} step={0.05} value={v} aria-label="Volume" aria-valuetext={`${Math.round(v * 100)}%`}
        onChange={event => setDrag(Number(event.target.value))} onPointerUp={commit} onKeyUp={commit} onBlur={commit} />
      <button className="icon-btn volume-step" aria-label="Increase volume" disabled={v >= 1} onClick={() => void music.setVolume(Math.min(1, v + .05))}><Plus /></button>
      <output aria-live="off">{Math.round(v * 100)}%</output>
    </div>
  )
}
