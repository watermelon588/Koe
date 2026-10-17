// Production bundle UI checks with synthetic HTTP/socket data; no real GitHub writes.
import assert from 'node:assert/strict'
import { spawn, execFileSync } from 'node:child_process'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const modules = process.env.KOE_E2E_NODE_MODULES
if (!modules) throw Error('Set KOE_E2E_NODE_MODULES to an existing directory containing playwright.')
const { chromium } = await import(pathToFileURL(path.join(modules, 'playwright/index.mjs')).href)
const origin = 'http://127.0.0.1:5187'
const server = spawn(process.execPath, [path.join(root, 'frontend/node_modules/vite/bin/vite.js'), 'preview', '--host', '127.0.0.1', '--port', '5187', '--strictPort'],
  { cwd: path.join(root, 'frontend'), windowsHide: true, stdio: 'ignore' })
let browser
const checks = [], errors = []
try {
  let ready = false
  for (let n = 0; n < 60; n++) {
    if (server.exitCode !== null) throw Error('Test preview server exited.')
    try { if ((await fetch(origin)).ok) { ready = true; break } } catch {}
    await new Promise(resolve => setTimeout(resolve, 250))
  }
  assert.ok(ready)
  browser = await chromium.launch({ channel: 'msedge', headless: true })
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, serviceWorkers: 'block' })
  let failRepos = true, saved = null
  await context.route('**/*', async route => {
    const url = new URL(route.request().url())
    if (url.origin !== origin) return route.abort()
    if (!url.pathname.startsWith('/api/') && !url.pathname.startsWith('/auth/')) return route.continue()
    let body = {}
    if (url.pathname === '/auth/status') body = { google: true, user: { name: 'Test owner', email: 'owner@example.test', is_admin: false } }
    else if (url.pathname === '/api/ws-ticket') body = { ticket: 'synthetic-ticket' }
    else if (url.pathname === '/api/people') return route.fulfill({ status: 403, json: { detail: 'Owner only' } })
    else if (url.pathname === '/api/connections') body = { ready: true, github_ready: true, connections: [{ provider: 'github', connected: true, account: 'me' }] }
    else if (url.pathname === '/api/connections/github/repos') {
      if (route.request().method() === 'PUT') { saved = route.request().postDataJSON().repos; return route.fulfill({ status: 204 }) }
      if (failRepos) return route.fulfill({ status: 502, json: { detail: 'Synthetic provider error' } })
      body = { repos: url.searchParams.get('page') === '2' ? ['me/notes'] : ['me/app'], selected: ['me/app'], next_page: url.searchParams.get('page') === '2' ? null : 2 }
    } else if (url.pathname === '/api/music/status') return route.fulfill({ status: 503, json: { error: { code: 'spotify_disabled' } } })
    return route.fulfill({ json: body })
  })
  const ts = new Date().toISOString()
  const result = { since: '2026-10-16T18:30:00Z', until: '2026-10-17T18:30:00Z', timezone: 'Asia/Kolkata', as_of: ts,
    totals: { commits: 2, merged_prs: 1 }, by_repository: [{ repo: 'me/app', commits: 2, merged_prs: 1 }],
    commits: [{ repo: 'me/app', sha: 'abcdef123456', title: 'Fix delayed playback', url: 'https://github.com/me/app/commit/abcdef123456', date: '2026-10-17T10:00:00Z' }],
    scope: 'Author-matched default-branch commits.', partial: false }
  await context.routeWebSocket(/.*/, ws => ws.onMessage(() => ws.send(JSON.stringify({ type: 'snapshot',
    panels: { github_yesterday: { ts, result }, reviews: { result: { prs: [] } }, prs: { result: { prs: [] } } }, activity: [], pending: [], latencies: [] }))))
  const page = await context.newPage()
  page.on('pageerror', error => errors.push(error.message))
  await page.goto(origin + '/app/dashboard')
  await page.getByRole('heading', { name: 'Yesterday', exact: true }).waitFor()
  assert.equal(await page.getByRole('link', { name: 'Fix delayed playback' }).getAttribute('href'), result.commits[0].url)
  checks.push('Yesterday stats and linked commit evidence appear without an agent call')
  await page.setViewportSize({ width: 375, height: 812 })
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false)
  checks.push('Dashboard fits 375px mobile width')
  await page.goto(origin + '/app/settings')
  await page.getByRole('button', { name: 'Choose', exact: true }).click()
  await page.getByText('Could not load repositories. Check your GitHub connection and retry.').waitFor()
  failRepos = false
  await page.getByRole('button', { name: 'Choose', exact: true }).click()
  await page.getByRole('button', { name: 'Load more repositories' }).click()
  await page.getByRole('checkbox', { name: 'me/notes', exact: true }).check()
  await page.locator('.repo-pick').getByRole('button', { name: 'Save 2', exact: true }).click()
  assert.deepEqual(saved, ['me/app', 'me/notes'])
  checks.push('Repository load error, explicit retry, pagination and saved selections work on mobile')
  assert.deepEqual(errors, [])
  const output = path.join(root, 'backend/data/github-ui-browser')
  await mkdir(output, { recursive: true })
  await page.goto(origin + '/app/dashboard')
  await page.getByRole('heading', { name: 'Yesterday', exact: true }).waitFor()
  await page.screenshot({ path: path.join(output, 'dashboard-mobile.png'), fullPage: true })
  await writeFile(path.join(output, 'report.json'), JSON.stringify({ checks, errors, coverage: 'Production frontend; synthetic API/socket provider data. Backend authorization and agent paths are tested separately.' }, null, 2))
  console.log(JSON.stringify({ checks, errors }))
} finally {
  await browser?.close()
  if (server.exitCode === null) {
    if (process.platform === 'win32') execFileSync('taskkill', ['/PID', String(server.pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore' })
    else server.kill()
  }
}
