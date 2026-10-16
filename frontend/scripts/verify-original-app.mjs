// Isolated local UI verification: synthetic account/API/socket data, fake microphone, no provider writes.
import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { pathToFileURL } from 'node:url'

const [playwrightPath, output] = process.argv.slice(2)
if (!playwrightPath || !output) throw Error('Provide the bundled Playwright directory and screenshot output directory.')
const { chromium } = await import(pathToFileURL(path.join(playwrightPath, 'index.mjs')).href)
const origin = process.env.KOE_HOMEPAGE_ORIGIN ?? 'http://127.0.0.1:5173'
const browser = await chromium.launch({ channel: 'msedge', headless: true, args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] })
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, serviceWorkers: 'block', permissions: ['microphone'] })
const page = await context.newPage()
const errors = [], checks = [], unexpectedWrites = []
let connectedPlaylist = false
page.on('pageerror', error => errors.push(error.message))
await mkdir(output, { recursive: true })
const stamp = new Date().toISOString()
const row = { id: 'studio-preview-note', title: 'Onboarding, a little clearer', kind: 'Note', status: 'Open', date: { start: '2026-10-16' }, url: 'https://www.notion.so/studio-preview-note', last_edited_time: stamp, in_trash: false }
const panel = result => ({ ts: stamp, date: '2026-10-16', timezone: 'Asia/Kolkata', result })
const snapshot = { type: 'snapshot', panels: {
  calendar: panel({ events: [{ id: 'preview-sync', title: 'Project catch-up', start: { dateTime: '2026-10-16T14:00:00+05:30' }, end: { dateTime: '2026-10-16T14:30:00+05:30' } }] }),
  reviews: panel({ prs: [{ repo: 'preview/koe', number: 42, title: 'Make onboarding feel effortless', ci: 'passing', review: 'requested', conflicts: 'no' }] }),
  prs: panel({ prs: [{ repo: 'preview/koe', number: 43, title: 'A clearer calendar workspace', ci: 'passing', review: 'approved', conflicts: 'no' }] }),
}, activity: [], pending: [], latencies: [], storage: 'synthetic-browser-fixture' }

await context.route('**/auth/status', route => route.fulfill({ json: { google: true, user: { email: 'preview@example.test', name: 'Preview account', is_admin: false } } }))
await context.route('**/api/**', async route => {
  const request = route.request(), url = new URL(request.url()), endpoint = url.pathname
  if (request.method() !== 'GET' && endpoint !== '/api/ws-ticket') {
    unexpectedWrites.push(`${request.method()} ${endpoint}`)
    return route.fulfill({ status: 409, json: { detail: 'UI fixture: writes disabled.' } })
  }
  let json = {}
  if (endpoint === '/api/ws-ticket') json = { ticket: 'local-ui-fixture' }
  else if (endpoint === '/api/connections') json = { ready: true, github_ready: true, timesheet: '', connections: [
    { provider: 'google', connected: true, account: 'preview@example.test' },
    { provider: 'github', connected: true, account: 'preview' },
    { provider: 'notion', connected: true, account: 'Personal workspace' },
    { provider: 'spotify', connected: false, account: '' },
    { provider: 'gemini', connected: false, account: '' },
  ] }
  else if (endpoint === '/api/people') return route.fulfill({ status: 403, json: { detail: 'Preview account is not an administrator.' } })
  else if (endpoint === '/api/music/status') json = { contract_version: '1.0.0', configured: true, enabled: true, connected: connectedPlaylist, reconnect_required: false, connection_id: connectedPlaylist ? 'preview-music' : null, selected_playlist_id: connectedPlaylist ? 'preview-playlist' : null, unavailable_reason: null, capabilities: { connect: true, playlist_read: connectedPlaylist, playlist_write: false, playback: false } }
  else if (endpoint === '/api/music/playlist/items') json = { playlist: { id: 'preview-playlist', name: 'A little focus', spotify_url: 'https://open.spotify.com/playlist/preview', snapshot_id: 'preview-snapshot', total: 2, image_url: null }, items: ['Quiet morning', 'Room to think'].map((name, index) => ({ position: index, track: { id: `preview-${index}`, uri: `spotify:track:preview-${index}`, name, artists: ['Preview artist'], album: 'Local UI fixture', image_url: null, spotify_url: 'https://open.spotify.com/track/preview', duration_ms: 180000, playable: true, unavailable_reason: null } })), next_offset: null }
  else if (endpoint === '/api/app/messages') json = { messages: [], workspace: [] }
  else if (endpoint === '/api/notion/status') json = { connected: true, workflow_ready: true, missing_properties: [], name: 'Personal workspace', database_url: 'https://www.notion.so/preview' }
  else if (endpoint === '/api/notion/records') json = { pages: [row], next_cursor: null }
  else if (endpoint.startsWith('/api/notion/records/')) json = { page: row, blocks: [{ id: 'preview-block', type: 'paragraph', text: 'A small note to keep the next steps clear.', has_children: false }], truncated: false, preview_note: '' }
  else if (endpoint === '/api/notion/pending') json = { pending_action: null }
  else if (endpoint === '/api/notion/activity') json = { activity: [] }
  else if (endpoint === '/api/notion/schema') json = { source_id: 'preview', editable: [], read_only_or_reserved: [], partial: false, note: '' }
  return route.fulfill({ json })
})
await page.routeWebSocket(/\/ws\/(events|call)$/, socket => {
  const call = socket.url().endsWith('/call')
  socket.onMessage(message => {
    if (typeof message !== 'string') return
    const data = JSON.parse(message)
    if (!call && (data.type === 'auth' || data.type === 'refresh')) socket.send(JSON.stringify(snapshot))
    if (call && data.type === 'auth') {
      socket.send(JSON.stringify({ type: 'transcript', role: 'model', text: 'Hello. This is an isolated browser preview.' }))
      socket.send(JSON.stringify({ type: 'approval_pending', id: 'preview-approval', summary: 'Preview only: a 30-minute focus block.', display: { title: 'Focus block', lines: ['Tomorrow · 30 minutes', 'Not saved'], url: 'https://calendar.google.com/calendar/u/0/r' }, expires_ts: new Date(Date.now() + 3600000).toISOString() }))
    }
    if (call && data.type === 'approval') socket.send(JSON.stringify({ type: 'approval_result', action_id: 'preview-approval', status: 'rejected', clear: true }))
  })
})
await page.addInitScript(() => {
  localStorage.setItem('koe-theme', 'dark')
  localStorage.setItem('koe-mascot', 'kami')
})

async function palette(expected) {
  const actual = await page.locator('.app').evaluate(element => {
    const style = getComputedStyle(element)
    return Object.fromEntries(['--bg', '--surface', '--surface-2', '--text', '--muted', '--accent'].map(key => [key, style.getPropertyValue(key).trim()]))
  })
  for (const [key, value] of Object.entries(expected)) assert.equal(actual[key], value, `Palette changed: ${key}`)
}
const dark = { '--bg': '#0e0f11', '--surface': '#16171a', '--surface-2': '#1e2024', '--text': '#e6e6e3', '--muted': '#8b8d92', '--accent': '#a6d6d1' }
const light = { '--bg': '#e2e2df', '--surface': '#eaeae7', '--surface-2': '#f2f2f0', '--text': '#1c1d1f', '--muted': '#5f6166', '--accent': '#3d7671' }

try {
  await page.goto(origin + '/app', { waitUntil: 'networkidle' })
  await page.locator('.stage .mascot-view[data-load="ready"]').waitFor({ timeout: 60000 })
  await palette(dark)
  async function originalShell() {
    const values = await page.locator('.app').evaluate(element => {
      const css = selector => getComputedStyle(element.querySelector(selector))
      return { body: getComputedStyle(document.body).fontSize, nav: css('.nav-link').fontSize,
        brand: css('.brand').fontSize, bar: css('.bar').position,
        logos: element.querySelectorAll('.brand-icon').length, tools: element.querySelectorAll('.studio-tools,.studio-eyebrow').length }
    })
    assert.deepEqual(values, { body: '15px', nav: '13px', brand: '16px', bar: 'fixed', logos: 4, tools: 0 })
  }
  await originalShell()
  assert.equal(await page.locator('.home').evaluate(element => getComputedStyle(element).paddingTop), '104px')
  assert.equal(await page.getByRole('button', { name: 'Call Koe', exact: true }).evaluate(element => getComputedStyle(element).fontSize), '15px')
  await page.screenshot({ path: path.join(output, 'original-home-dark.png') })
  checks.push('Home: original Engawa layout, navigation, typography, desk and palette preserved; original provider logos loaded')
  for (const route of ['dashboard', 'chat', 'notion', 'music', 'settings', 'install']) {
    await page.goto(origin + '/app#' + route, { waitUntil: 'networkidle' })
    await page.locator(`.app[data-page="${route}"]`).waitFor()
    if (route === 'settings') {
      await page.locator('.viewer .mascot-view[data-load="ready"]').waitFor({ timeout: 60000 })
      assert.equal(await page.getByRole('list', { name: 'Companions' }).getByRole('button').count(), 4)
      await page.getByRole('list', { name: 'Companions' }).getByRole('button', { name: 'Miku', exact: true }).waitFor()
      await page.getByRole('list', { name: 'Companions' }).getByRole('button', { name: 'Aoi', exact: true }).waitFor()
    }
    await palette(dark)
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `${route}: desktop overflow`)
    assert.equal(await page.locator('.app .studio-eyebrow').count(), 0)
    assert.deepEqual(await page.locator('.app .brand-icon').evaluateAll(images => images.filter(image => !image.complete || !image.naturalWidth).map(image => image.src)), [])
    await page.screenshot({ path: path.join(output, `original-${route}-desktop.png`) })
    await page.setViewportSize({ width: 375, height: 812 })
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `${route}: mobile overflow`)
    await page.screenshot({ path: path.join(output, `original-${route}-mobile.png`) })
    await page.setViewportSize({ width: 1440, height: 1000 })
    checks.push(`${route}: provider logos loaded within the original desktop/mobile design`)
  }
  await page.goto(origin + '/app', { waitUntil: 'networkidle' })
  await page.getByRole('button', { name: 'Switch to light theme' }).click()
  await palette(light)
  await originalShell()
  await page.getByRole('button', { name: 'Call Koe', exact: true }).click()
  await page.locator('.app[data-state="listening"]').waitFor({ timeout: 15000 })
  await page.getByRole('button', { name: 'Cancel', exact: true }).click()
  await page.getByRole('button', { name: 'Mute', exact: true }).click()
  await page.getByRole('button', { name: 'Unmute', exact: true }).waitFor()
  await page.getByRole('button', { name: 'End call', exact: true }).click()
  await page.locator('.app[data-call="off"]').waitFor()
  checks.push('Original light palette and call/cancel/mute/end behavior retained')
  await page.goto(origin + '/', { waitUntil: 'networkidle' })
  await page.locator('.hp').waitFor()
  assert.equal(await page.locator('.hp-portrait').count(), 3)
  await page.getByRole('button', { name: 'Preview Mei', exact: true }).waitFor()
  await page.evaluate(() => { location.hash = '#home' })
  await page.locator('.app').waitFor()
  await originalShell()
  checks.push('Landing page remains Studio with Mei; its styles cannot leak into the original app after hash navigation')
  assert.deepEqual(errors, [])
  assert.deepEqual(unexpectedWrites, [])
  await writeFile(path.join(output, 'verification.json'), JSON.stringify({ checks, errors, unexpectedWrites }, null, 2))
  console.log(JSON.stringify({ passed: checks.length, checks, errors, unexpectedWrites, output }, null, 2))
} finally { await browser.close() }
