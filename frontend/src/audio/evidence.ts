// A crashed/closed/reloaded tab releases its Web Lock, but that does not prove Spotify stopped.
// Persist only connection-generation markers; never tokens or listening history.
const PREFIX = 'koe-music-audio:'
const LOCAL = 'koe-music-unsettled:'
export class AudioEvidence {
  private storage: Storage
  constructor(storage: Storage) { this.storage = storage }
  mark(generation: string) { this.storage.setItem(PREFIX + generation, 'unverified') }
  clear(generation: string) { this.storage.removeItem(PREFIX + generation) }
  has(generation: string) { return this.storage.getItem(PREFIX + generation) !== null || this.localPending(generation) }
  localPending(generation: string) { return this.storage.getItem(LOCAL + generation) !== null }
  local(generation: string, pending: boolean) { if (pending) this.storage.setItem(LOCAL + generation, 'unresolved'); else this.storage.removeItem(LOCAL + generation) }
  uncertain() {
    for (let i = 0; i < this.storage.length; i++) {
      const key = this.storage.key(i)
      if (key?.startsWith(PREFIX) || key?.startsWith(LOCAL)) return true
    }
    return false
  }
}
export const audioEvidence = () => typeof window === 'undefined' ? null : new AudioEvidence(localStorage)
export function requireStoppedEvidence() {
  if (audioEvidence()?.uncertain()) throw Error('Music from a previous or another Koe tab is unverified. Return to Music, play in this browser, then pause it before using voice.')
}
