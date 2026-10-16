// Run against Vite with KOE_E2E_NODE_MODULES pointing to an existing Playwright installation.
import assert from 'node:assert/strict'
import path from 'node:path'
import { pathToFileURL } from 'node:url'
const modules = process.env.KOE_E2E_NODE_MODULES
if (!modules) throw Error('Set KOE_E2E_NODE_MODULES to an existing Playwright package directory')
const { chromium } = await import(pathToFileURL(path.join(modules, 'playwright', 'index.mjs')).href)
const origin = process.env.KOE_S2_ORIGIN || 'http://127.0.0.1:5181'
const browser = await chromium.launch({ channel: 'msedge', headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
const page = await context.newPage(), errors = [], decisions = []
page.setDefaultTimeout(60_000)
page.on('pageerror', e => errors.push(e.message))
const action = { id: 'synthetic-calendar', expires_ts: '2099-01-01T00:00:00Z',
  summary: 'Create Weekly sync.\nExact audit: {"recurrence":["RRULE:FREQ=WEEKLY;COUNT=4"],"dateTime":"2026-10-19T10:00:00+05:30","optional":null}',
  display: { title: 'Create Weekly sync', lines: ['19 Oct 2026 · 10:00–10:30 · Asia/Kolkata', 'Every week · 4 times', 'Guests: teammate@example.com', 'Request a Google Meet · link available after Google confirms'], url: '' } }
const sheet = { title: 'Add column Billable', lines: ['Tab: Timesheet'], url: 'https://docs.google.com/spreadsheets/d/synthetic/edit' }
let chatStatus = null
const fixture = { action, dashboard: { panels: {}, pending: [action], latencies: [], storage: '', activity: [
  { id: 'today', ts: new Date().toISOString(), type: 'approval_result', channel: 'web', result: { status: 'executed', display: sheet, summary: 'Full exact Sheets audit' } },
  { id: 'yesterday', ts: new Date(Date.now() - 86400000).toISOString(), kind: 'approval', channel: 'app', summary: 'rejected', display: sheet, audit_summary: 'Full rejected change' },
] } }
await context.route('**/*', async route => {
  const request = route.request(), url = new URL(request.url())
  if (url.origin !== origin) return route.abort()
  const pathname = url.pathname
  const json = body => route.fulfill({ json: body })
  if (pathname === '/__s2/fixture') return json(fixture)
  if (pathname === '/__s2/decision') { decisions.push(request.postDataJSON()); return json({ status: 'Synthetic decision recorded' }) }
  if (pathname === '/api/app/messages') return json({ messages: url.searchParams.get('after') > 0 ? [] : [{ id: 1, ts: new Date().toISOString(), role: 'koe', text: `Review this change.\nPending: ${action.summary}. Confirm with yes or cancel with no.`, voice: null, action_id: action.id, action_status: chatStatus, approval: action }], workspace: [] })
  if (pathname === '/api/app/approvals/' + action.id) {
    decisions.push({ action_id: action.id, ...request.postDataJSON() }); chatStatus = 'executed'
    return json({ action: { id: action.id, status: chatStatus }, messages: [], workspace: [] })
  }
  if (pathname === '/api/notion/status') return json({ connected: true, workflow_ready: true, missing_properties: [], name: 'Synthetic workspace' })
  if (pathname === '/api/notion/records') return json({ pages: [], next_cursor: null })
  if (pathname === '/api/notion/pending') return json({ pending_action: { ...action, display: { title: 'Create Meeting notes', lines: ['Meeting · Open', '16 Oct 2026', 'Meeting record only · no Calendar booking'] } } })
  if (pathname === '/api/notion/activity') return json({ activity: [] })
  if (pathname === '/api/notion/schema') return json({ fields: [], schema_version: 'synthetic' })
  if (pathname.startsWith('/api/')) return json({ connections: [] })
  return route.continue()
})
try {
  await page.goto(origin + '/tests/fixtures/approvals.html', { waitUntil: 'domcontentloaded' })
  await page.getByRole('heading', { name: 'Review changes' }).waitFor()
  assert.ok(!(await page.locator('body').innerText()).includes('RRULE'))
  assert.equal(await page.getByRole('heading', { name: 'Today', exact: true }).count(), 1)
  assert.equal(await page.getByRole('heading', { name: 'Yesterday', exact: true }).count(), 1)
  assert.equal(await page.locator('.feed time').first().evaluate(e => getComputedStyle(e).whiteSpace), 'nowrap')
  const details = page.getByRole('region', { name: 'Dashboard approval' }).locator('summary')
  await details.focus(); await page.keyboard.press('Enter')
  assert.ok((await page.locator('body').innerText()).includes('RRULE'))
  await page.keyboard.press('Enter')
  await page.getByRole('region', { name: 'Dashboard approval' }).getByRole('button', { name: 'Approve', exact: true }).click()
  assert.deepEqual(decisions[0], { action_id: action.id, approve: true })
  if (process.env.KOE_S2_SCREENSHOT) await page.screenshot({ path: process.env.KOE_S2_SCREENSHOT, fullPage: true })
  for (const width of [320, 375, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 1000 })
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `Overflow at ${width}px`)
  }
  await page.getByRole('button', { name: 'chat', exact: true }).click()
  await page.getByText('Review this change.', { exact: true }).waitFor()
  assert.ok(!(await page.locator('.thread').innerText()).includes('RRULE'))
  await page.locator('.thread').getByRole('button', { name: 'Confirm', exact: true }).click()
  await page.getByText('Done', { exact: true }).waitFor()
  assert.equal(decisions.at(-1).action_id, action.id)
  await page.reload({ waitUntil: 'domcontentloaded' }); await page.getByRole('button', { name: 'chat', exact: true }).click()
  await page.getByText('Done', { exact: true }).waitFor()
  await page.getByRole('button', { name: 'notion', exact: true }).click()
  await page.getByText('Create Meeting notes', { exact: true }).waitFor()
  assert.ok(!(await page.locator('.workspace-approval').innerText()).includes('RRULE'))
  assert.deepEqual(errors, [])
  console.log('PASS: cards, keyboard Details, dated Activity, 24-hour/no-wrap time, safe Open links, 5 widths, chat decision/reload, Notion preview; no page errors or external writes.')
} finally { await browser.close() }
