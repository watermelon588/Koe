import assert from 'node:assert/strict'
import { test } from 'node:test'
import { playlistId, statusFrom, positionAt, clock, createMockPlayer, MOCK_TRACKS, IDLE } from '../src/music/model.ts'

const ID = '37i9dQZF1DX4WYpdgoIcn6'

test('playlist links: share links, locale prefixes and URIs; nothing else', () => {
  assert.equal(playlistId(`https://open.spotify.com/playlist/${ID}?si=abc123`), ID)
  assert.equal(playlistId(`  https://open.spotify.com/intl-ja/playlist/${ID}  `), ID)
  assert.equal(playlistId(`spotify:playlist:${ID}`), ID)
  for (const bad of [`http://open.spotify.com/playlist/${ID}`, `https://evil.example/playlist/${ID}`, `https://open.spotify.com/album/${ID}`,
    'https://open.spotify.com/playlist/short', `https://open.spotify.com.evil.example/playlist/${ID}`, `javascript:alert(1)`, ''])
    assert.equal(playlistId(bad), null, bad)
})

test('server status: a missing music API is "not set up", never a fake connection', () => {
  assert.equal(statusFrom(404).phase, 'unavailable')
  assert.equal(statusFrom(501).phase, 'unavailable')
  assert.equal(statusFrom(401).phase, 'signed-out')
  assert.equal(statusFrom(200).phase, 'unavailable') // until the contract is wired, a 200 body isn't trusted
  assert.equal(statusFrom(0).phase, 'unavailable')
})

test('progress extrapolates only while playing, clamped to the track', () => {
  const s = { ...IDLE, status: 'playing', position: 1000, at: 0 }
  assert.equal(positionAt(s, 500, 10000), 1500)
  assert.equal(positionAt(s, 99999, 10000), 10000)
  assert.equal(positionAt({ ...s, status: 'paused' }, 99999, 10000), 1000)
  assert.equal(positionAt({ ...s, status: 'unknown' }, 99999, 10000), 1000) // unknown never looks like progress
  assert.equal(clock(61999), '1:01')
})

test('mock player: skips unavailable tracks, pause reports paused, restart within 3 s', async () => {
  let t = 0
  const p = createMockPlayer(MOCK_TRACKS, () => t)
  await p.play(4) // unavailable
  assert.equal(p.state().status, 'idle')
  await p.play(3)
  await p.next()
  assert.equal(p.state().index, 5) // 4 is skipped
  t = 5000
  await p.previous() // past 3 s: back to the start of this track
  assert.equal(p.state().index, 5)
  assert.equal(p.state().position, 0)
  await p.previous()
  assert.equal(p.state().index, 3)
  assert.equal(await p.pause(), 'paused')
  assert.equal(p.playing(), false)
})

import { trackFrom, say } from '../src/music/model.ts'
const base = { contract_version: '1.0.0', configured: true, enabled: true, connected: false, reconnect_required: false, connection_id: null,
  selected_playlist_id: null, unavailable_reason: null, external_url: 'https://open.spotify.com/',
  capabilities: { connect: true, playlist_read: false, playlist_write: false, playback: false, remove_occurrence: false, remove_all_occurrences: false, voice_control: false } }

test('contract v1 status: SDK playback follows the backend capability; browser support is gated by the controller', () => {
  assert.deepEqual(statusFrom(200, { ...base, configured: false, enabled: false, unavailable_reason: 'spotify_not_configured' }),
    { phase: 'unavailable', message: say('spotify_not_configured') })
  assert.equal(statusFrom(200, { ...base, enabled: false, unavailable_reason: 'spotify_disabled' }).message, say('spotify_disabled'))
  assert.deepEqual(statusFrom(200, base), { phase: 'disconnected', canConnect: true, reconnect: false, message: '' })
  assert.equal(statusFrom(200, { ...base, connected: true, connection_id: 'c1', reconnect_required: true }).reconnect, true)
  const on = statusFrom(200, { ...base, connected: true, connection_id: 'c1', selected_playlist_id: 'p',
    capabilities: { ...base.capabilities, playlist_read: true, playback: true } })
  assert.equal(on.phase, 'connected'); assert.equal(on.read, true); assert.equal(on.inApp, true)
  assert.equal(statusFrom(200, { ...base, contract_version: '2.0.0' }).phase, 'unavailable') // a breaking server change is not guessed at
  assert.equal(statusFrom(403, { error: { code: 'spotify_owner_required' } }).message, say('spotify_owner_required'))
})

test('tracks: missing URI or unplayable never becomes playable; unknown error codes get a plain line', () => {
  const t = { id: null, uri: null, name: 'Local file', artists: ['A', 'B'], album: '', image_url: null, spotify_url: null, duration_ms: 1, playable: true, unavailable_reason: 'local' }
  const m = trackFrom(t, 'p3')
  assert.equal(m.playable, false); assert.equal(m.id, 'p3'); assert.equal(m.artists, 'A, B'); assert.match(m.url, /^https:\/\/open\.spotify\.com\//)
  assert.equal(say('made_up_code'), 'Something went wrong with Spotify. Try again.')
})
