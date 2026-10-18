// Read-only visual references. All application APIs/sockets are synthetic; external requests and writes are blocked.
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const modules = process.env.KOE_MOCKUP_MODULES
if (!modules) throw Error('Set KOE_MOCKUP_MODULES to an existing node_modules directory containing playwright')
const { chromium } = await import(pathToFileURL(path.join(modules, 'playwright/index.mjs')).href)
const origin = process.env.KOE_MOCKUP_ORIGIN || 'http://127.0.0.1:5182'
const browser = await chromium.launch({ channel: 'msedge', headless: true, args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] })
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1, serviceWorkers: 'block', permissions: ['microphone'], reducedMotion: 'reduce' })
const page = await context.newPage(), errors = [], captures = [], blocked = []
page.setDefaultTimeout(60_000)
page.on('pageerror', e => errors.push(e.message))
const stamp = new Date().toISOString(), day = '2026-10-18'
const panel = result => ({ ts: stamp, date: day, timezone: 'Asia/Kolkata', result })
const row = { id: 'design-note', title: 'A quieter workspace', kind: 'Note', status: 'Open', date: { start: day }, url: 'https://www.notion.so/design-note', last_edited_time: stamp, in_trash: false }
const snapshot = { type: 'snapshot', panels: {
  calendar: panel({ events: [{ id: 'sync', title: 'Design sync', start: { dateTime: `${day}T11:00:00+05:30` }, end: { dateTime: `${day}T11:30:00+05:30` } }] }),
  reviews: panel({ prs: [{ repo: 'preview/koe', number: 42, title: 'A calmer onboarding', ci: 'passing', review: 'requested', conflicts: 'no' }] }),
  prs: panel({ prs: [{ repo: 'preview/koe', number: 43, title: 'Workspace polish', ci: 'passing', review: 'approved', conflicts: 'no' }] }),
}, activity: [], pending: [], latencies: [], storage: 'Isolated visual fixture' }
await context.route('**/*', async route => {
  const req = route.request(), url = new URL(req.url()), p = url.pathname
  if (url.origin !== origin) { blocked.push(url.origin); return route.abort() }
  const json = body => route.fulfill({ json: body })
  if (p === '/auth/status') return json({ google: true, user: { email: 'design@example.test', name: 'Rohit', is_admin: false } })
  if (p.startsWith('/api/')) {
    if (req.method() !== 'GET' && p !== '/api/ws-ticket') return route.fulfill({ status: 409, json: { detail: 'Visual fixture: writes disabled' } })
    if (p === '/api/ws-ticket') return json({ ticket: 'synthetic-visual-fixture' })
    if (p === '/api/connections') return json({ ready: true, github_ready: true, timesheet: '', connections: [
      { provider: 'google', connected: true, account: 'design@example.test' }, { provider: 'github', connected: true, account: 'rohit' },
      { provider: 'notion', connected: true, account: 'Personal workspace' }, { provider: 'spotify', connected: true, account: 'Design preview' },
    ] })
    if (p === '/api/people') return route.fulfill({ status: 403, json: { detail: 'Visual preview account' } })
    if (p === '/api/music/status') return json({ contract_version: '1.0.0', configured: true, enabled: true, connected: true,
      reconnect_required: false, connection_id: 'visual-music', selected_playlist_id: 'visual-playlist',
      capabilities: { connect: true, playlist_read: true, playlist_write: false, playback: false } })
    if (p === '/api/music/playlist/items') return json({ playlist: { id: 'visual-playlist', name: 'Quiet hours', spotify_url: 'https://open.spotify.com/playlist/visual', snapshot_id: 'visual', total: 3, image_url: null },
      items: ['First light', 'Room to think', 'Slow morning'].map((name, i) => ({ position: i, track: { id: `visual-${i}`, uri: `spotify:track:visual-${i}`, name, artists: ['Sample artist'], album: 'Visual fixture', image_url: null, duration_ms: 180000, playable: true, spotify_url: 'https://open.spotify.com/track/visual' } })), next_offset: null })
    if (p === '/api/app/messages') return json({ messages: [{ id: 1, ts: stamp, role: 'you', text: 'What does my day look like?', voice: null, action_id: null, action_status: null }, { id: 2, ts: stamp, role: 'koe', text: 'Design sync at 11. The afternoon is yours.', voice: null, action_id: null, action_status: null }], workspace: [] })
    if (p === '/api/notion/status') return json({ connected: true, workflow_ready: true, missing_properties: [], name: 'Personal workspace', database_url: 'https://www.notion.so/visual' })
    if (p === '/api/notion/records') return json({ pages: [row], next_cursor: null })
    if (p === '/api/notion/pending') return json({ pending_action: null })
    if (p === '/api/notion/activity') return json({ activity: [] })
    if (p === '/api/notion/schema') return json({ source_id: 'visual', editable: [], read_only_or_reserved: [], partial: false })
    return json({})
  }
  return route.continue()
})
await page.routeWebSocket(/\/ws\/(events|call)$/, socket => {
  const call = socket.url().endsWith('/call')
  socket.onMessage(message => {
    if (typeof message !== 'string') return
    const data = JSON.parse(message)
    if (!call && ['auth', 'refresh'].includes(data.type)) socket.send(JSON.stringify(snapshot))
    if (call && data.type === 'auth') {
      socket.send(JSON.stringify({ type: 'transcript', role: 'koe', text: 'I’m listening. What’s on your mind?' }))
      socket.send(JSON.stringify({ type: 'turn_complete' }))
    }
  })
})
await page.addInitScript(() => { localStorage.setItem('koe-theme', 'dark'); localStorage.setItem('koe-mascot', 'kami') })
await mkdir(path.join(root, 'screenshots/current'), { recursive: true })
async function capture(slug, route, mobile = false) {
  await page.setViewportSize(mobile ? { width: 390, height: 844 } : { width: 1440, height: 1000 })
  await page.goto(origin + route, { waitUntil: 'domcontentloaded' })
  await page.locator(route === '/' ? '.hp' : '#main-content').waitFor()
  if (route === '/app' || route === '/app/settings') {
    await page.locator('.mascot-view[data-load="ready"]').first().waitFor({ timeout: 90_000 }).catch(() => {})
  }
  await page.evaluate(() => document.fonts.ready)
  const height = await page.evaluate(() => document.documentElement.scrollHeight)
  for (let y = 0; y < height; y += 800) { await page.evaluate(y => scrollTo(0, y), y); await page.waitForTimeout(100) }
  await page.evaluate(() => scrollTo(0, 0)); await page.waitForTimeout(400)
  await page.screenshot({ path: path.join(root, 'screenshots/current', slug + '.png'), fullPage: true })
  captures.push({ file: slug + '.png', route, width: mobile ? 390 : 1440, syntheticData: true })
  console.log('Captured ' + slug)
}
try {
  for (const [slug, route] of [['01-landing', '/'], ['02-home', '/app'], ['03-dashboard', '/app/dashboard'], ['04-chat', '/app/chat'], ['05-notion', '/app/notion'], ['06-music', '/app/music'], ['07-settings', '/app/settings'], ['08-install', '/app/install'], ['09-guide', '/guide'], ['10-privacy', '/privacy'], ['11-terms', '/terms']]) await capture(slug, route)
  await page.goto(origin + '/app', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Call Koe', exact: true }).click()
  await page.locator('.app[data-state="listening"]').waitFor()
  await page.waitForTimeout(600)
  await page.screenshot({ path: path.join(root, 'screenshots/current/12-live-call.png'), fullPage: true })
  captures.push({ file: '12-live-call.png', route: '/app', state: 'synthetic call', width: 1440 })
  await page.getByRole('button', { name: 'End call', exact: true }).click()
  for (const [slug, route] of [['13-home-mobile', '/app'], ['14-chat-mobile', '/app/chat'], ['15-music-mobile', '/app/music']]) await capture(slug, route, true)
  await writeFile(path.join(root, 'screenshots/current/capture-report.json'), JSON.stringify({ capturedAt: new Date().toISOString(), revision: '06fb643', captures, errors, externalOriginsBlocked: [...new Set(blocked)], note: 'Current frontend code with synthetic API/socket data. No real sign-in or provider writes.' }, null, 2))
} finally { await browser.close() }
