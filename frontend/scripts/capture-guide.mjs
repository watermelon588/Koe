// Capture the real interface with local illustrative data, never real account records.
// node scripts/capture-guide.mjs <Playwright package directory> [origin]
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
import { fileURLToPath, pathToFileURL } from 'node:url'
import path from 'node:path'

const [playwrightPath, origin = 'http://127.0.0.1:5173'] = process.argv.slice(2)
if (!playwrightPath) throw Error('Provide the bundled Playwright package directory.')
const { chromium } = await import(pathToFileURL(path.join(playwrightPath, 'index.mjs')).href)
const output = fileURLToPath(new URL('../public/guide/', import.meta.url))
await mkdir(output, { recursive: true })
const browser = await chromium.launch({ channel: 'msedge', headless: true })
const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, timezoneId: 'Asia/Kolkata', serviceWorkers: 'block' })
await context.addInitScript(() => {
  localStorage.setItem('koe-theme', 'dark')
  localStorage.setItem('koe-mascot', 'kami')
})
const page = await context.newPage()
const errors = [], writes = []
page.on('pageerror', error => errors.push(error.message))
const stamp = '2026-10-28T10:00:00+05:30'
const panel = result => ({ ts: stamp, date: '2026-10-28', timezone: 'Asia/Kolkata', result })
const records = [
  { id: 'guide-note', title: 'Project handoff notes', kind: 'Note', status: 'Open' },
  { id: 'guide-task', title: 'Review the onboarding checklist', kind: 'Task', status: 'Open' },
  { id: 'guide-log', title: 'Daily log · 28 October', kind: 'Daily log', status: 'Done' },
].map(row => ({ ...row, date: { start: '2026-10-28' }, url: `https://www.notion.so/${row.id}`, last_edited_time: stamp, in_trash: false }))
const snapshot = { type: 'snapshot', panels: {
  calendar: panel({ events: [
    { id: 'guide-sync', title: 'Project catch-up', start: { dateTime: '2026-10-28T11:00:00+05:30' }, end: { dateTime: '2026-10-28T11:30:00+05:30' } },
    { id: 'guide-focus', title: 'Focus time', start: { dateTime: '2026-10-28T14:00:00+05:30' }, end: { dateTime: '2026-10-28T15:00:00+05:30' } },
  ] }),
  reviews: panel({ prs: [{ repo: 'demo/koe', number: 42, title: 'A clearer onboarding flow', ci: 'passing', review: 'requested', conflicts: 'no' }] }),
  prs: panel({ prs: [{ repo: 'demo/koe', number: 43, title: 'Improve calendar previews', ci: 'passing', review: 'approved', conflicts: 'no' }] }),
  github_yesterday: panel({ since: '2026-10-27', until: '2026-10-28', timezone: 'Asia/Kolkata', totals: { commits: 4, merged_prs: 1 }, totals_are_complete: true, commits: [], prs: [] }),
}, pending: [{ id: 'guide-proposal', summary: 'Create a 30-minute project catch-up', display: { title: 'Project catch-up', lines: ['Tomorrow · 11:00–11:30', 'Proposed event · not saved'] }, channel: 'app', expires_ts: new Date(Date.now() + 600000).toISOString() }], activity: [], latencies: [], storage: 'guide-sample-data' }
await context.route('**/auth/**', route => {
  assert.equal(new URL(route.request().url()).pathname, '/auth/status', 'No real auth navigation')
  return route.fulfill({ json: { google: true, user: { email: 'demo@example.test', name: 'Demo account', is_admin: false } } })
})
await context.route('**/api/**', route => {
  const request = route.request(), endpoint = new URL(request.url()).pathname
  if (request.method() !== 'GET' && endpoint !== '/api/ws-ticket') {
    writes.push(`${request.method()} ${endpoint}`)
    return route.fulfill({ status: 409, json: { detail: 'Guide capture: writes disabled.' } })
  }
  let json = {}
  if (endpoint === '/api/ws-ticket') json = { ticket: 'guide-local-fixture' }
  else if (endpoint === '/api/connections') json = { ready: true, github_ready: true, github_token_ready: true, docs_ready: true, features: { github_scope: true }, github_repo_mode: 'selected', timesheet: 'https://docs.google.com/spreadsheets/d/guide-example/edit', connections: [
    { provider: 'google', connected: true, account: 'demo@example.test' },
    { provider: 'github', connected: true, account: 'demo-developer' },
    { provider: 'notion', connected: true, account: 'Example workspace' },
    { provider: 'spotify', connected: false, account: '' },
    { provider: 'gemini', connected: false, account: '' },
  ] }
  else if (endpoint === '/api/connections/github/repos') json = { mode: 'selected', repos: ['demo/koe', 'demo/website'], selected: ['demo/koe'], next_page: null }
  else if (endpoint === '/api/people') return route.fulfill({ status: 403, json: { detail: 'Owner only' } })
  else if (endpoint === '/api/music/status') json = { contract_version: '1.0.0', configured: false, enabled: false, connected: false, capabilities: {} }
  else if (endpoint === '/api/notion/status') json = { connected: true, workflow_ready: true, missing_properties: [], name: 'Example workspace', database_url: 'https://www.notion.so/guide-example' }
  else if (endpoint === '/api/notion/records') json = { pages: records, next_cursor: null }
  else if (endpoint.startsWith('/api/notion/records/')) json = { page: records[0], blocks: [{ id: 'guide-block', type: 'paragraph', text: 'Keep the handoff simple: project context, decisions and next steps. Review the onboarding checklist before the next catch-up.', has_children: false }], truncated: false, preview_note: '' }
  else if (endpoint === '/api/notion/pending') json = { pending_action: null }
  else if (endpoint === '/api/notion/activity') json = { activity: [] }
  else if (endpoint === '/api/notion/schema') json = { source_id: 'guide-example', editable: [], read_only_or_reserved: [], partial: false, note: '' }
  else if (endpoint === '/api/app/messages') json = { messages: [], workspace: [] }
  return route.fulfill({ json })
})
await page.routeWebSocket(/\/ws\//, socket => {
  socket.onMessage(message => {
    const event = JSON.parse(String(message))
    if (event.type === 'auth' || event.type === 'refresh') socket.send(JSON.stringify(snapshot))
  })
})
const capture = async name => {
  await page.evaluate(() => document.fonts.ready)
  await page.waitForTimeout(400)
  await page.screenshot({ path: path.join(output, `${name}.jpg`), type: 'jpeg', quality: 88 })
  console.log(`Captured ${name}`)
}
try {
  await page.goto(origin)
  await page.locator('.hp-scene[data-ready="true"]').waitFor({ timeout: 90000 })
  await page.waitForFunction(() => getComputedStyle(document.querySelector('#hp-title')).opacity === '1')
  await page.evaluate(() => scrollTo(0, 0))
  await capture('companion')
  await page.goto(origin + '/app/dashboard')
  await page.getByRole('status').filter({ hasText: /^Live$/ }).waitFor()
  await page.getByText('A clearer onboarding flow').waitFor()
  await capture('dashboard')
  await page.goto(origin + '/app/settings')
  await page.getByText('Connected as demo@example.test').waitFor()
  await page.getByRole('button', { name: 'Choose', exact: true }).click()
  await page.getByText('All accessible repositories', { exact: true }).waitFor()
  await page.locator('.set-section').filter({ has: page.getByRole('heading', { name: 'Connections', exact: true }) }).scrollIntoViewIfNeeded()
  await capture('connections')
  await page.goto(origin + '/app/notion')
  await page.getByRole('button').filter({ has: page.getByText('Project handoff notes', { exact: true }) }).click()
  await page.getByText('Keep the handoff simple:', { exact: false }).waitFor()
  await capture('notion')
  assert.deepEqual(errors, [])
  assert.deepEqual(writes, [])
  console.log('Four current-interface screenshots captured with sample data; no provider writes or uncaught errors.')
} finally { await browser.close() }
