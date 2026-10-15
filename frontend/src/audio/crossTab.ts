// A Web Lock, held for the full audio activity, is the authority. Messages only request a verified handoff.
export type AudioOwner = 'music' | 'call' | 'record' | 'reply'
export class CrossTabAudio {
  private locks: LockManager
  private channel: BroadcastChannel
  private release: (() => void) | null = null
  private owner: AudioOwner | null = null
  private handoff: (() => Promise<boolean>) | null = null
  private waiters = new Map<string, (ok: boolean) => void>()
  constructor(locks: LockManager, channel: BroadcastChannel) {
    this.locks = locks; this.channel = channel
    channel.addEventListener('message', async (event: MessageEvent) => {
      const message = event.data as { type?: string; id?: string; ok?: boolean }
      if (typeof message?.id !== 'string' || message.id.length > 100) return
      if (message.type === 'answer') return this.waiters.get(message.id)?.(message.ok === true)
      if (message.type !== 'handoff' || !this.release) return
      let stopped = false
      if (this.owner === 'music') {
        try { stopped = await this.handoff?.() === true } catch { /* uncertain never releases the lock */ }
        if (stopped) this.drop()
      }
      channel.postMessage({ type: 'answer', id: message.id, ok: stopped })
    })
  }
  private attempt(signal?: AbortSignal): Promise<(() => void) | null> {
    return new Promise((resolve, reject) => {
      this.locks.request('koe-exclusive-audio-v1', { mode: 'exclusive', ...(!signal ? { ifAvailable: true } : { signal }) }, async lock => {
        if (!lock) { resolve(null); return }
        await new Promise<void>(done => resolve(done))
      }).catch(reject)
    })
  }
  async take(owner: AudioOwner, handoff: () => Promise<boolean>) {
    if (this.release) { this.owner = owner; this.handoff = handoff; return }
    let release = await this.attempt()
    if (!release && owner !== 'music') {
      const id = crypto.randomUUID()
      const acknowledged = await new Promise<boolean>(resolve => {
        const timer = setTimeout(() => { this.waiters.delete(id); resolve(false) }, 3200)
        this.waiters.set(id, ok => { clearTimeout(timer); this.waiters.delete(id); resolve(ok) })
        this.channel.postMessage({ type: 'handoff', id })
      })
      if (acknowledged) {
        const controller = new AbortController()
        const timer = setTimeout(() => controller.abort(), 1500)
        try { release = await this.attempt(controller.signal) } finally { clearTimeout(timer) }
      }
    }
    if (!release) throw Error('Another Koe tab owns audio. Pause it or finish its call, then try again.')
    this.release = release; this.owner = owner; this.handoff = handoff
  }
  drop() { this.release?.(); this.release = null; this.owner = null; this.handoff = null }
  close() { this.drop(); this.channel.close() }
}

export const crossTabSupported = () => typeof window !== 'undefined' && !!navigator.locks && typeof BroadcastChannel !== 'undefined'
let gate: CrossTabAudio | null = null
export async function takeCrossTab(owner: AudioOwner, handoff: () => Promise<boolean>) {
  // Existing voice remains usable where combined music is disabled. Node unit tests have no browser surface.
  if (!crossTabSupported()) { if (owner === 'music' && typeof window !== 'undefined') throw Error('This browser cannot safely coordinate music across tabs. Use Spotify instead.'); return }
  gate ??= new CrossTabAudio(navigator.locks, new BroadcastChannel('koe-audio-handoff-v1'))
  await gate.take(owner, handoff)
}
export function dropCrossTab() { gate?.drop() }
