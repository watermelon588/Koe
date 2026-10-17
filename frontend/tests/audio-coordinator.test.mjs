import assert from 'node:assert/strict'
import { test, beforeEach } from 'node:test'
import { acquire, setMusic, current, voiceActive, resetForTests, AudioBusy } from '../src/audio/coordinator.ts'

// A fake music controller: `playing` is what it reports; pause() settles with `result` after `delay` ms.
function fakeMusic({ playing = true, result = 'paused', delay = 0 } = {}) {
  const m = { playing, pauses: 0 }
  setMusic({
    playing: () => m.playing,
    pause: () => { m.pauses++; return new Promise((ok) => setTimeout(() => { if (result === 'paused') m.playing = false; ok(result) }, delay)) },
  })
  return m
}
const busy = (reason) => (e) => e instanceof AudioBusy && e.reason === reason

beforeEach(resetForTests)

test('no music: a call takes audio at once and releases it', async () => {
  const release = await acquire('call')
  assert.equal(current().owner, 'call')
  release(); release() // idempotent
  assert.equal(current().owner, null)
})

test('a call waits for a confirmed pause, then music learns it lost audio', async () => {
  const m = fakeMusic({ delay: 10 })
  let lost = false
  await acquire('music', () => { lost = true })
  const pending = acquire('call')
  assert.equal(voiceActive(), true) // music can't restart during the handoff
  await pending
  assert.equal(m.pauses, 1)
  assert.equal(m.playing, false)
  assert.equal(lost, true)
  assert.equal(current().owner, 'call')
})

test('unknown or still-playing music blocks voice; nothing is taken', async () => {
  fakeMusic({ result: 'unknown' })
  await assert.rejects(acquire('call'), busy('music'))
  assert.equal(current().owner, null)
  resetForTests()
  fakeMusic({ playing: null, result: 'paused' }) // unknown state is not "paused" until pause() confirms it
  await acquire('record')
  assert.equal(current().owner, 'record')
})

test('a pause that never settles times out as unknown', { timeout: 5000 }, async () => {
  setMusic({ playing: () => true, pause: () => new Promise(() => {}) })
  await assert.rejects(acquire('call'), busy('music'))
  assert.equal(voiceActive(), false)
})

test('double click: the second start during a handoff is refused', async () => {
  fakeMusic({ delay: 10 })
  const first = acquire('call')
  await assert.rejects(acquire('call'), busy('busy'))
  await first
})

test('voice never preempts voice; music cannot start while voice holds audio', async () => {
  const release = await acquire('call')
  await assert.rejects(acquire('record'), busy('busy'))
  await assert.rejects(acquire('reply'), busy('busy'))
  await assert.rejects(acquire('music'), busy('voice'))
  release()
  await acquire('music')
  assert.equal(current().owner, 'music')
})

test('a newer reply clip replaces the playing one', async () => {
  let firstStopped = false
  const first = await acquire('reply', () => { firstStopped = true })
  await acquire('reply')
  assert.equal(firstStopped, true)
  first() // the old clip's late release must not free the new one
  assert.equal(current().owner, 'reply')
})

test('paused music is taken over without another pause', async () => {
  const m = fakeMusic({ playing: false })
  await acquire('music')
  await acquire('call')
  assert.equal(m.pauses, 0)
})

// Recovery remains inside audio ownership; a rejection cannot begin microphone capture.
test('verified recovery can unblock a lost player, but failed recovery leaves voice idle', async () => {
  const { setAudioRecovery } = await import('../src/audio/coordinator.ts')
  fakeMusic({ playing: null, result: 'unknown' })
  setAudioRecovery(async () => { throw Error('Provider still playing') })
  await assert.rejects(acquire('call'), /Provider still playing/)
  assert.equal(current().owner, null)
  setAudioRecovery(async () => { setMusic({ playing: () => false, pause: async () => 'paused' }) })
  const release = await acquire('call')
  assert.equal(current().owner, 'call')
  release()
})
