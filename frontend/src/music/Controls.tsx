import { useState } from 'react'
import { MusicNotes, Pause, Play, SkipBack, SkipForward, SpeakerHigh, SpeakerLow, SpeakerX } from '@phosphor-icons/react'
import { clock, positionAt } from './model'
import type { Music } from './useMusic'
import './music.css'

// Shared by the Music page and the mini player.

export function Art({ src, size }: { src: string | null | undefined; size: 'sm' | 'md' | 'lg' }) {
  return src ? <img className={`music-art ${size}`} src={src} alt="" loading="lazy" />
    : <span className={`music-art ${size} blank`} aria-hidden="true"><MusicNotes /></span>
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
  const v = music.play.volume
  const Icon = v === 0 ? SpeakerX : v < 0.5 ? SpeakerLow : SpeakerHigh
  return (
    <label className="music-volume">
      <Icon aria-hidden="true" />
      <input type="range" min={0} max={1} step={0.05} value={v} aria-label="Volume" aria-valuetext={`${Math.round(v * 100)}%`}
        onChange={(e) => void music.setVolume(Number(e.target.value))} />
    </label>
  )
}
