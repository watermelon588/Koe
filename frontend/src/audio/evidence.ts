// A crashed/closed/reloaded tab releases its Web Lock, but that does not prove Spotify stopped.
// Persist only connection-generation markers; never tokens or listening history.
const PREFIX = 'koe-music-audio:'
const LOCAL = 'koe-music-unsettled:'
export class AudioEvidence {
  private storage: Storage
  constructor(storage: Storage) { this.storage = storage }
  mark(generation: string) { this.storage.setItem(PREFIX + generation, 'unverified') }
  clear(generation: string) { this.storage.removeItem(PREFIX + generation) }
  generations() {
    const found = new Set<string>()
    for (let i = 0; i < this.storage.length; i++) {
      const key = this.storage.key(i)
      for (const prefix of [PREFIX, LOCAL]) if (key?.startsWith(prefix)) found.add(key.slice(prefix.length))
    }
    return [...found]
  }
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
  if (audioEvidence()?.uncertain()) throw Error('Spotify could not confirm that music stopped. Pause it in Spotify, then try Call again.')
}
