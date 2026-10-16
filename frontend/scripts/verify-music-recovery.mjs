import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import { pathToFileURL } from 'node:url'
const [modules, output] = process.argv.slice(2)
const { chromium } = await import(pathToFileURL(path.join(modules, 'index.mjs')).href)
const browser = await chromium.launch({ channel: 'msedge', headless: true })
await fs.mkdir(output, { recursive: true })
const checks = []
const base = { contract_version: '1.0.0', configured: true, enabled: true, connected: false, reconnect_required: false,
  connection_id: null, selected_playlist_id: null, unavailable_reason: null, capabilities: { connect: true, playlist_read: false, playlist_write: false, playback: false } }
try {
  for (const recovery of ['connected-service', 'expired-session', 'ineligible-playlist', 'ineligible-empty']) {
    const context = await browser.newContext({ viewport: { width: 375, height: 812 }, serviceWorkers: 'block' })
    const page = await context.newPage()
    const errors = [], writes = []
    let reads = 0
    page.on('pageerror', error => errors.push(error.message))
    await context.route('**/auth/status', route => route.fulfill({ json: { google: true, user: { name: 'Fixture', email: 'fixture@example.test', is_admin: true } } }))
    await context.route('**/api/**', route => {
      const request = route.request(), endpoint = new URL(request.url()).pathname
      if (endpoint === '/api/music/status') {
        reads++
        if (recovery.startsWith('ineligible')) return route.fulfill({ json: { ...base, connected: true, connection_id: 'fixture-generation',
          selected_playlist_id: 'A'.repeat(22), capabilities: { connect: true, playlist_read: true, playlist_write: true, playback: false } } })
        if (reads === 1) return route.fulfill({ status: 503, json: { detail: 'Temporary backend outage' } })
        return route.fulfill({ status: recovery === 'expired-session' ? 401 : 200,
          json: recovery === 'expired-session' ? { error: { code: 'spotify_sign_in_required' } } : base })
      }
      if (endpoint === '/api/music/playlist/items') return route.fulfill({ status: 400, json: { error: { code: 'spotify_playlist_ineligible' } } })
      if (endpoint === '/api/music/playlists' && request.method() === 'GET') return route.fulfill({ json: { items: recovery === 'ineligible-empty' ? [] :
        [{ id: 'B'.repeat(22), name: 'My eligible private playlist', spotify_url: 'https://open.spotify.com/playlist/' + 'B'.repeat(22),
          snapshot_id: 'fixture-snapshot', total: 0, image_url: null }], next_offset: null } })
      if (request.method() !== 'GET' && endpoint !== '/api/ws-ticket') writes.push(endpoint)
      return route.fulfill({ status: 401, json: { detail: 'Synthetic browser fixture' } })
    })
    await page.goto('http://127.0.0.1:5173/app#music')
    if (recovery.startsWith('ineligible')) {
      await page.getByRole('heading', { name: 'Choose your playlist', exact: true }).waitFor()
      assert.equal(await page.getByRole('button', { name: 'Disconnect Spotify', exact: true }).count(), 1)
      assert.equal(await page.getByRole('button', { name: 'Connect Spotify', exact: true }).count(), 0)
      assert.equal(await page.getByRole('heading', { name: 'Couldn’t load music', exact: true }).count(), 0)
      assert.equal(await page.getByText('Spotify is connected. Your selected playlist must be private, non-collaborative and owned by you. Choose another playlist or create one below.', { exact: true }).count(), 1)
      assert.equal(await page.getByRole('button', { name: 'Create private playlist', exact: true }).isEnabled(), true)
      assert.equal(await page.getByRole('button', { name: 'Refresh playlists', exact: true }).isEnabled(), true)
      assert.equal(await page.getByRole('link', { name: 'Open selected playlist in Spotify', exact: true }).getAttribute('href'), 'https://open.spotify.com/playlist/' + 'A'.repeat(22))
      if (recovery === 'ineligible-playlist') assert.equal(await page.getByRole('button', { name: 'Choose', exact: true }).count(), 1)
      else assert.equal(await page.getByText('No eligible private playlists found.', { exact: false }).count(), 1)
      assert.deepEqual(writes, [])
      assert.deepEqual(errors, [])
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false)
      await page.screenshot({ path: path.join(output, `${recovery}.png`), fullPage: true })
      checks.push(`${recovery}: account remains connected, stale selection returns to picker with choose/create controls, no automatic write`)
      await context.close()
      continue
    }
    await page.getByRole('heading', { name: 'Couldn’t load music', exact: true }).waitFor()
    await page.getByRole('button', { name: 'Retry', exact: true }).click()
    if (recovery === 'expired-session') {
      await page.getByRole('heading', { name: 'Sign in to use music', exact: true }).waitFor()
      assert.equal(await page.getByRole('button', { name: 'Sign in with Google' }).count(), 1)
    } else {
      await page.getByRole('heading', { name: 'Connect Spotify', exact: true }).waitFor()
      assert.equal(await page.getByRole('button', { name: 'Connect Spotify', exact: true }).isEnabled(), true)
    }
    assert.equal(reads, 2)
    assert.deepEqual(writes, [])
    assert.deepEqual(errors, [])
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false)
    await page.screenshot({ path: path.join(output, `${recovery}.png`), fullPage: true })
    checks.push(`${recovery}: temporary error retries one read, recovers honestly, no Spotify write/consent/playback`)
    await context.close()
  }
  await fs.writeFile(path.join(output, 'report.json'), JSON.stringify({ checks }, null, 2))
  console.log(JSON.stringify({ passed: checks.length, checks, output }, null, 2))
} finally { await browser.close() }
