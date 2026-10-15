// Operational request IDs survive reload. Tokens are never stored here.
export type MusicReply = { http: number; body: unknown }
export type MusicRequest = (path: string, method?: string, body?: unknown) => Promise<MusicReply>
export type PendingIntent = { id: string; path: string; method: string; body: Record<string, unknown> }
type Result = { state?: string; result?: { accepted?: boolean }; error?: { code?: string; outcome?: string } }

export class MusicFailure extends Error {
  code: string
  constructor(code: string, message = 'Spotify could not finish this action.') { super(message); this.code = code }
}

export class MusicIntents {
  private key: string
  private entries: PendingIntent[] = []
  private invalid = false
  private generation: string
  private request: MusicRequest
  private storage: Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>
  private uuid: () => string
  constructor(generation: string, request: MusicRequest, storage: Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>,
              uuid = () => crypto.randomUUID()) {
    this.generation = generation; this.request = request; this.storage = storage; this.uuid = uuid
    this.key = `koe-music-intents:${generation}`
    try {
      const saved = JSON.parse(storage.getItem(this.key) ?? '[]')
      if (!Array.isArray(saved) || saved.length > 20 || saved.some(i => typeof i?.id !== 'string' || typeof i?.path !== 'string')) throw Error('invalid')
      this.entries = saved
    } catch { this.invalid = true }
  }
  pending() { return [...this.entries] }
  private persist() {
    try { this.storage.setItem(this.key, JSON.stringify(this.entries)) }
    catch { throw new MusicFailure('spotify_storage_unavailable', 'Koe could not remember this action safely. Allow browser storage before changing music.') }
  }
  async write(path: string, method: string, args: Record<string, unknown>) {
    if (this.invalid) throw new MusicFailure('spotify_storage_unavailable', 'Koe could not remember earlier music actions safely.')
    if (this.entries.length) throw new MusicFailure('spotify_outcome_unknown', 'An earlier music action is unconfirmed. Check its status before another change.')
    const id = this.uuid()
    const body = { ...args, connection_id: this.generation, request_id: id }
    const intent = { id, path, method, body }
    this.entries.push(intent)
    try { this.persist() } catch (e) { this.entries.pop(); throw e }
    let response: MusicReply
    try { response = await this.request(path, method, body) }
    catch { throw new MusicFailure('spotify_outcome_unknown', 'The response was lost. This action will not be sent again automatically.') }
    const result = response.body as Result | undefined
    if (result?.state === 'confirmed' || result?.error?.outcome === 'not_sent') {
      this.entries = this.entries.filter(i => i.id !== id); this.persist()
      if (result.error) throw new MusicFailure(result.error.code ?? 'spotify_unavailable')
      if (result.result?.accepted === false) throw new MusicFailure('spotify_unavailable')
      return response
    }
    throw new MusicFailure('spotify_outcome_unknown', 'Spotify has not confirmed this action. It will not be sent twice.')
  }
  async inspect() {
    for (const intent of [...this.entries]) {
      const reply = await this.request(`/api/music/mutations/${encodeURIComponent(intent.id)}?connection_id=${encodeURIComponent(this.generation)}`, 'GET')
      const result = reply.body as Result | undefined
      if (result?.state === 'confirmed' || result?.error?.outcome === 'not_sent') {
        this.entries = this.entries.filter(i => i.id !== intent.id); this.persist()
      }
    }
    return this.pending()
  }
  clear() { this.storage.removeItem(this.key); this.entries = []; this.invalid = false }
}
