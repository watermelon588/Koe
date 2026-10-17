import assert from 'node:assert/strict'
import { test } from 'node:test'
import { spotifyPlayer } from '../src/music/sdk.ts'
import { MusicIntents } from '../src/music/intents.ts'

function setup({ unknown = false, nullState = false, delayedState = false, delayedResume = false, registrationDenied = false, registrationDeniedAfterPlay = false, firstConnectFails = false } = {}) {
  const events = {}; const trace = []; let playing = false
  let readsAfterPlay = 0
  let settleResume
  const resumeWait = new Promise(resolve => { settleResume = resolve })
  class Fake {
    constructor() { trace.push('created') }
    addListener(name, fn) { events[name] = fn; return true }
    removeListener(name) { delete events[name]; return true }
    async connect() { trace.push('connect'); if (firstConnectFails && trace.filter(value => value === 'connect').length === 1) return false; events.ready({ device_id: 'browser' }); return true }
    disconnect() { trace.push('disconnect') }
    async activateElement() { trace.push('activate') }
    async getCurrentState() {
      if (delayedState && playing && ++readsAfterPlay <= 3) return readsAfterPlay === 1 ? null : { paused: readsAfterPlay === 2, position: 0, disallows: {}, track_window: { current_track: { uri: 'spotify:track:old' } } }
      return nullState ? null : { paused: !playing, position: 0, duration: 1000, disallows: {}, track_window: { current_track: { uri: 'spotify:track:t' } } } }
    async pause() { trace.push('pause'); playing = false }
    async resume() { if (delayedResume) await resumeWait; playing = true }
    async seek() {} async nextTrack() {} async previousTrack() {} async setVolume() {}
  }
  const memory = new Map(); const saved = { getItem: k => memory.get(k) ?? null, setItem: (k, v) => memory.set(k, v), removeItem: k => memory.delete(k) }
  const request = async (_path, method, body) => {
    if (_path === '/api/music/device' && (registrationDenied || registrationDeniedAfterPlay && trace.includes('play'))) return { http: 409, body: { error: { code: 'spotify_device_unavailable' } } }
    if (body?.operation) { trace.push(body.operation); if (body.operation === 'play') playing = true; return { http: unknown ? 202 : 200, body: { state: unknown ? 'outcome_unknown' : 'confirmed', result: { accepted: true } } } }
    if (_path.includes('/mutations/')) return { http: 202, body: { state: 'outcome_unknown' } }
    return { http: 200, body: method === 'POST' ? { device_id: 'browser' } : { device_id: 'browser', state: 'observed' } }
  }
  const intents = new MusicIntents('g', request, saved)
  return { player: spotifyPlayer(Fake, { connectionId: 'g', tracks: () => [{ uri: 'spotify:track:t', playable: true }], request, intents }), trace, events, settleResume }
}

test('play waits for the requested track after delayed null, paused and previous-track SDK state without replay', async () => {
  const { player, trace } = setup({ delayedState: true })
  await player.play(0)
  assert.equal(player.state().status, 'playing')
  assert.equal(player.state().index, 0)
  assert.equal(trace.filter(value => value === 'play').length, 1)
  assert.equal(trace.filter(value => value === 'transfer').length, 1)
  player.dispose()
})

test('explicit pause supersedes a pending playback observation and verifies silence', async () => {
  const { player, trace } = setup({ delayedState: true })
  const start = player.play(0)
  const pause = player.pause()
  await start
  assert.equal(await pause, 'paused')
  assert.equal(player.playing(), false)
  assert.equal(trace.filter(value => value === 'play').length, 1)
  player.dispose()
})
test('device registration rejection before any sent playback remains idle and does not block voice', async () => {
  const { player, trace } = setup({ registrationDenied: true, nullState: true })
  await assert.rejects(player.play(0))
  assert.equal(player.state().status, 'idle')
  assert.equal(player.playing(), false)
  assert.equal(await player.pause(), 'paused')
  assert.equal(trace.includes('transfer'), false)
  assert.equal(trace.includes('play'), false)
  player.dispose()
})
test('a failed SDK connection can reconnect on the next explicit play', async () => {
  const { player, trace } = setup({ firstConnectFails: true })
  await assert.rejects(player.play(0))
  await player.play(0)
  assert.equal(trace.filter(value => value === 'connect').length, 2)
  assert.equal(trace.filter(value => value === 'play').length, 1)
  player.dispose()
})
test('registration failure after actual playback preserves the voice barrier until verified pause', async () => {
  const { player } = setup({ registrationDeniedAfterPlay: true })
  await player.play(0)
  await assert.rejects(player.play(0))
  assert.equal(player.state().status, 'unknown')
  assert.equal(player.playing(), null)
  assert.equal(await player.pause(), 'paused')
  player.dispose()
})
test('SDK not_ready invalidates readiness and reconnects on explicit play', async () => {
  const { player, events, trace } = setup()
  await player.play(0)
  await player.pause()
  events.not_ready({ device_id: 'browser' })
  await player.play(0)
  assert.equal(trace.filter(value => value === 'connect').length, 2)
  player.dispose()
})
test('SDK is inert until explicit playback; activate stays synchronous and pause follows every sent command', async () => {
  const { player, trace } = setup()
  assert.deepEqual(trace, ['created'])
  assert.equal(await player.pause(), 'paused')
  player.activate()
  assert.equal(trace.at(-1), 'activate')
  await player.play(0)
  assert.equal(await player.pause(), 'paused')
  assert.deepEqual(trace.slice(-3), ['transfer', 'play', 'pause'])
  player.dispose()
})
test('an uncertain sent transfer remains a voice barrier even when local pause returns', async () => {
  const { player, trace } = setup({ unknown: true })
  await assert.rejects(player.play(0))
  assert.equal(await player.pause(), 'unknown')
  assert.equal(trace.filter(v => v === 'transfer').length, 1)
  assert.equal(trace.includes('play'), false)
  player.dispose()
})
test('null SDK state after playback is unknown and cannot be treated as paused', async () => {
  const { player } = setup({ nullState: true })
  await assert.rejects(player.play(0))
  assert.equal(player.playing(), null)
  assert.equal(await player.pause(), 'unknown')
  player.dispose()
})

test('a timed-out SDK resume keeps the barrier closed until it settles and a later pause is verified', async () => {
  const {player,settleResume} = setup({delayedResume:true})
  await player.play(0)
  assert.equal(await player.pause(),'paused')
  await assert.rejects(player.resume())
  assert.equal(await player.pause(),'unknown')
  settleResume()
  await new Promise(resolve => setTimeout(resolve,0))
  assert.equal(await player.pause(),'paused')
  assert.equal(player.playing(),false)
  player.dispose()
})
