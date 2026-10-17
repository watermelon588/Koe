import assert from 'node:assert/strict'
import { test } from 'node:test'
import { loadSpotifySDK } from '../src/music/sdk.ts'

test('a timed-out SDK script can be replaced and successfully loaded on retry', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  let script = null
  let appended = 0
  globalThis.window = {}
  globalThis.document = {
    querySelector: () => script,
    createElement: () => ({ dataset: {}, remove() { script = null } }),
    head: { appendChild(value) { script = value; appended++ } },
  }
  try {
    const first = loadSpotifySDK()
    const rejected = assert.rejects(first)
    t.mock.timers.tick(15000)
    await rejected
    assert.equal(script, null)
    const retry = loadSpotifySDK()
    assert.equal(appended, 2)
    class Player {}
    window.Spotify = { Player }
    window.onSpotifyWebPlaybackSDKReady()
    assert.equal(await retry, Player)
  } finally { delete globalThis.window; delete globalThis.document }
})
