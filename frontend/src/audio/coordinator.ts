// One audio owner at a time in this tab (docs/SPOTIFY_MUSIC_ARCHITECTURE.md §9): Spotify music, a live call, a
// voice-note recording or a recorded Koe reply. Voice never starts until music is confirmed paused: an unknown
// music state blocks it, and a timeout is not a pause. Nothing here ever resumes music; that's a button.
import { takeCrossTab, dropCrossTab } from './crossTab.ts'
import { requireStoppedEvidence } from './evidence.ts'
export type Owner = 'music' | 'call' | 'record' | 'reply'
export type PauseResult = 'paused' | 'unknown'
// What the music controller tells us: is it audible (null = can't tell), and a pause that settles every
// already-sent play/transfer first, then reports what it actually observed.
export type MusicControl = { playing: () => boolean | null; pause: () => Promise<PauseResult> }
export type Release = () => void

export const PAUSE_DEADLINE_MS = 3000
const MESSAGES = {
  busy: 'Koe is already using audio. Finish that first.',
  music: 'Couldn’t confirm the music stopped, so Koe didn’t start. Pause it and try again.',
  voice: 'Music is paused while Koe uses audio.',
}
export class AudioBusy extends Error {
  reason: keyof typeof MESSAGES
  constructor(reason: keyof typeof MESSAGES) {
    super(MESSAGES[reason])
    this.reason = reason
  }
}

type Holder = { owner: Owner; id: number; onLost?: () => void }
let holder: Holder | null = null
let switching = false // a handoff is in flight; a second click must not race it
let music: MusicControl | null = null
let nextId = 1
let snap: { owner: Owner | null; switching: boolean } = { owner: null, switching: false }
const listeners = new Set<() => void>()

function changed() {
  snap = { owner: holder?.owner ?? null, switching }
  listeners.forEach((fn) => fn())
}
export const subscribe = (fn: () => void) => (listeners.add(fn), () => void listeners.delete(fn))
export const current = () => snap // stable between changes, for useSyncExternalStore
export const setMusic = (control: MusicControl | null) => { music = control }

const deadline = (ms: number) => new Promise<PauseResult>((ok) => setTimeout(() => ok('unknown'), ms))

// Take audio for `owner`. Resolves with a release function (idempotent) or rejects with AudioBusy.
// `onLost` runs if someone else takes over: a newer reply clip, or voice taking audio from music.
export async function acquire(owner: Owner, onLost?: () => void): Promise<Release> {
  const voice = owner !== 'music'
  if (switching) throw new AudioBusy(voice ? 'busy' : 'voice')
  if (holder && holder.owner !== 'music') {
    if (!voice) throw new AudioBusy('voice')
    if (!(owner === 'reply' && holder.owner === 'reply')) throw new AudioBusy('busy') // calls/recordings never preempt
  }
  if (holder?.owner === 'music' && owner === 'music') return release(holder.id)
  switching = true
  changed()
  try {
    if (voice && music && music.playing() !== false) {
      const seen = await Promise.race([music.pause(), deadline(PAUSE_DEADLINE_MS)])
      if (seen !== 'paused' || music.playing() !== false) throw new AudioBusy('music')
    }
    await takeCrossTab(owner, async () => {
      if (holder?.owner !== 'music' || !music) return false
      const paused = await Promise.race([music.pause(), deadline(PAUSE_DEADLINE_MS)])
      if (paused !== 'paused' || music.playing() !== false) return false
      const lost = holder; holder = null; lost.onLost?.(); changed()
      return true
    })
    if (voice) {
      try { requireStoppedEvidence() } catch (error) { dropCrossTab(); throw error }
    }
    const lost = holder
    holder = { owner, id: nextId++, onLost }
    lost?.onLost?.()
    changed()
    return release(holder.id)
  } finally {
    switching = false
    changed()
  }
}

function release(id: number): Release {
  return () => {
    if (holder?.id !== id) return
    holder = null
    dropCrossTab()
    changed()
  }
}

// Voice owns audio right now (or is about to): music must stay paused.
export const voiceActive = () => switching || (!!holder && holder.owner !== 'music')

// External SDK resume during voice invalidates the audio guarantee: stop capture/output immediately.
export function interruptVoiceForMusic() { if (holder && holder.owner !== 'music') holder.onLost?.() }

export function resetForTests() {
  holder = null; switching = false; music = null; listeners.clear(); changed()
  dropCrossTab()
}
