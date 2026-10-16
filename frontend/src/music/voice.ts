// Transport-only boundary: no Spotify metadata or audio is sent to the voice agent.
export type VoiceCommand = { type: 'command' | 'release'; id: string; connection_id: string; playlist_id: string;
  action: 'play' | 'play_match' | 'pause' | 'next' | 'previous' | 'set_volume' | 'volume_up' | 'volume_down'; volume_percent?: number | null; position?: number; snapshot_id?: string }
export type VoiceResult = 'applied' | 'queued' | 'deferred' | 'failed' | 'outcome_unknown'
export type VoiceGrant = { connection_id: string; playlist_id: string }

export function musicVoiceBoundary(grant: VoiceGrant, verify: () => Promise<boolean>, apply: (command: VoiceCommand) => Promise<VoiceResult>) {
  const queued = new Map<string, { command: VoiceCommand; expires: number }>()
  const seen = new Map<string, VoiceResult>()
  let closed = false
  return {
    close() { closed = true; queued.clear() },
    async receive(command: VoiceCommand): Promise<VoiceResult> {
      if (closed || !/^[a-f0-9]{64}$/.test(command.id) || command.connection_id !== grant.connection_id || command.playlist_id !== grant.playlist_id) return 'failed'
      const key = `${command.type}:${command.id}`
      if (seen.has(key)) return seen.get(key)!
      if (seen.size >= 128) return 'failed'
      // Record before awaiting so concurrent or replayed delivery cannot duplicate playback.
      seen.set(key, 'outcome_unknown')
      try {
        if (!await verify() || closed) { seen.set(key, 'failed'); return 'failed' }
        let result: VoiceResult
        if (command.type === 'release') {
          const pending = queued.get(command.id)
          queued.delete(command.id)
          if (!pending || pending.expires < Date.now()) result = 'failed'
          else result = await apply(pending.command)
        } else if (['play', 'play_match', 'next', 'previous'].includes(command.action)) {
          queued.clear() // only the most recent requested playback may survive a turn
          queued.set(command.id, { command, expires: Date.now() + 30000 })
          result = 'queued'
        } else {
          if (command.action === 'pause') queued.clear()
          result = await apply(command)
        }
        seen.set(key, result)
        return result
      } catch { seen.set(key, 'outcome_unknown'); return 'outcome_unknown' }
    },
  }
}
