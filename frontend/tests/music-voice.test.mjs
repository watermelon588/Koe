import assert from 'node:assert/strict'
import { test } from 'node:test'
import { musicVoiceBoundary } from '../src/music/voice.ts'

const grant = { connection_id: 'generation', playlist_id: 'p'.repeat(22) }
const command = (action, id = 'a'.repeat(64)) => ({ type: 'command', id, ...grant, action })

test('voice play waits for a release; duplicate command and release never play twice', async () => {
  const calls = []
  const bridge = musicVoiceBoundary(grant, async () => true, async item => { calls.push(item.action); return 'applied' })
  const play = command('play')
  assert.equal(await bridge.receive(play), 'queued')
  assert.equal(await bridge.receive(play), 'queued')
  assert.deepEqual(calls, [])
  const release = { ...play, type: 'release' }
  assert.equal(await bridge.receive(release), 'applied')
  assert.equal(await bridge.receive(release), 'applied')
  assert.deepEqual(calls, ['play'])
})

test('pause cancels a queued play rather than resuming after a later turn', async () => {
  const calls = []
  const bridge = musicVoiceBoundary(grant, async () => true, async item => { calls.push(item.action); return 'applied' })
  const play = command('play')
  await bridge.receive(play)
  assert.equal(await bridge.receive(command('pause', 'b'.repeat(64))), 'applied')
  assert.equal(await bridge.receive({ ...play, type: 'release' }), 'failed')
  assert.deepEqual(calls, ['pause'])
})

test('stale playlist, revoked permission and closed player cannot execute', async () => {
  let allowed = true, sent = 0
  const bridge = musicVoiceBoundary(grant, async () => allowed, async () => { sent++; return 'applied' })
  assert.equal(await bridge.receive({ ...command('pause'), playlist_id: 'q'.repeat(22) }), 'failed')
  const play = command('play')
  await bridge.receive(play)
  allowed = false
  assert.equal(await bridge.receive({ ...play, type: 'release' }), 'failed')
  bridge.close()
  assert.equal(await bridge.receive(command('pause', 'c'.repeat(64))), 'failed')
  assert.equal(sent, 0)
})

test('only the latest explicit queued playback survives; no metadata crosses the reply', async () => {
  const calls = []
  const bridge = musicVoiceBoundary(grant, async () => true, async item => { calls.push(item.action); return 'applied' })
  const play = command('play'), next = command('next', 'b'.repeat(64))
  await bridge.receive(play); await bridge.receive(next)
  assert.equal(await bridge.receive({ ...play, type: 'release' }), 'failed')
  assert.equal(await bridge.receive({ ...next, type: 'release' }), 'applied')
  assert.deepEqual(calls, ['next'])
})

test('uncertain execution is not retried; concurrent delivery is held unknown', async () => {
  let sent = 0, finish
  const bridge = musicVoiceBoundary(grant, async () => true, async () => { sent++; await new Promise(resolve => { finish = resolve }); throw Error('lost') })
  const item = command('volume_up')
  const first = bridge.receive(item)
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(await bridge.receive(item), 'outcome_unknown')
  finish()
  assert.equal(await first, 'outcome_unknown')
  assert.equal(await bridge.receive(item), 'outcome_unknown')
  assert.equal(sent, 1)
})

test('revocation during permission check prevents a queued command from running', async () => {
  let finish, sent = 0
  const bridge = musicVoiceBoundary(grant, () => new Promise(resolve => { finish = resolve }), async () => { sent++; return 'applied' })
  const result = bridge.receive(command('pause'))
  bridge.close(); finish(true)
  assert.equal(await result, 'failed')
  assert.equal(sent, 0)
})
