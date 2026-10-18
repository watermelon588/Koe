// Production bundle UI checks with synthetic HTTP/socket data; no real Google writes.
import assert from 'node:assert/strict'
import { spawn, execFileSync } from 'node:child_process'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const modules = process.env.KOE_E2E_NODE_MODULES
if (!modules) throw Error('Set KOE_E2E_NODE_MODULES to an existing directory containing playwright.')
const { chromium } = await import(pathToFileURL(path.join(modules, 'playwright/index.mjs')).href)
const origin = 'http://127.0.0.1:5188'
const server = spawn(process.execPath, [path.join(root, 'frontend/node_modules/vite/bin/vite.js'), 'preview', '--host', '127.0.0.1', '--port', '5188', '--strictPort'],
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

  let docsReady = false, serial = 0, pending = null, decisionCount = 0
  const messages = []
  const ts = new Date().toISOString()
  const makeMessage = (role, text, action = null) => ({id: ++serial, ts, role, text, voice:null, action_id:action, action_status:null})
  await context.route('**/*', async route => {
    const req = route.request(), url = new URL(req.url())
    if (url.origin !== origin) return route.abort()
    if (!url.pathname.startsWith('/api/') && !url.pathname.startsWith('/auth/')) return route.continue()
    let body = {}
    if (url.pathname === '/auth/status') body = {google:true,user:{name:'Test owner',email:'owner@example.test',is_admin:false}}
    else if (url.pathname === '/api/connections') body = {ready:true,docs_ready:docsReady,connections:[{provider:'google',connected:true,account:'owner@example.test'}]}
    else if (url.pathname === '/api/ws-ticket') body = {ticket:'fixture'}
    else if (url.pathname === '/api/music/status') return route.fulfill({status:503,json:{error:{code:'spotify_disabled'}}})
    else if (url.pathname === '/api/app/messages') {
      if (req.method() === 'POST') {
        const id = `doc-${serial}`
        const work = {service:'docs',operation:'docs_create',action_id:id,details:{title:'Weekly update',body:'Shipped the GitHub workflow.\nNext: Google Docs.'}}
        pending = {id, work}
        const mine = makeMessage('you', req.postDataJSON().text), reply = makeMessage('koe','Review the document before saving.',id)
        reply.approval = {id,summary:'Create Weekly update with the exact text shown.',expires_ts:'2099-01-01T00:00:00Z',display:{title:'Create Weekly update',lines:['Google Docs'],url:''}}
        messages.push(mine,reply)
        body = {messages:[mine,reply],workspace:[{type:'approval_pending',work}]}
      } else body = {messages:messages.filter(m => m.id > Number(url.searchParams.get('after') || 0))}
    } else if (url.pathname.startsWith('/api/app/approvals/')) {
      assert.ok(pending)
      decisionCount++
      const approved = req.postDataJSON().approve, status = approved ? 'executed' : 'rejected'
      body = {messages:[makeMessage('koe',approved?'Saved: Weekly update.':'Cancelled. Nothing was changed.')],action:{id:pending.id,status},
        workspace:[{type:'approval_result',status,work:{...pending.work,...(approved?{title:'Weekly update',message:'Document created.',url:'https://docs.google.com/document/d/doc-123/edit'}:{})}}]}
      pending = null
    }
    return route.fulfill({json:body})
  })
  await context.routeWebSocket(/.*/, ws => ws.onMessage(() => ws.send(JSON.stringify({type:'snapshot',panels:{},activity:[],pending:[],latencies:[]}))))
  const page = await context.newPage()
  page.on('pageerror', e => errors.push(e.message))
  await page.goto(origin + '/app/settings')
  const enable = page.getByRole('link',{name:'Enable Docs',exact:true})
  assert.equal(await enable.getAttribute('href'), '/auth/google/connect?docs=true&next=%2Fapp%2Fsettings')
  assert.ok(await page.locator('img[src="/brands/docs.png"]').count())
  docsReady = true
  await page.reload()
  await page.getByRole('link',{name:'Open chat',exact:true}).click()
  await page.getByRole('textbox',{name:'Message',exact:true}).fill('Create a Google Doc called Weekly update.')
  await page.getByRole('button',{name:'Send',exact:true}).click()
  const panel = page.locator('#live-workspace')
  await panel.getByText('Preview only. Nothing saved yet.').waitFor()
  assert.equal(await panel.getByRole('heading',{name:'Google Docs',exact:true}).count(), 1)
  await panel.getByRole('button',{name:'Confirm',exact:true}).click()
  await panel.getByRole('heading',{name:'Saved in Google Docs',exact:true}).waitFor()
  assert.equal(decisionCount,1)
  assert.equal(await panel.locator('.lw-receipt a').getAttribute('href'), 'https://docs.google.com/document/d/doc-123/edit')
  checks.push('Docs consent upgrade and logo, desktop chat preview, confirmation and saved receipt')
  const output = path.join(root,'backend/data/docs-ui-browser')
  await mkdir(output,{recursive:true})
  await page.waitForFunction(() => Number(getComputedStyle(document.querySelector('#live-workspace')).opacity) > 0.99)
  await page.screenshot({path:path.join(output,'docs-desktop.png'),fullPage:true})
  await page.setViewportSize({width:375,height:812})
  await page.getByRole('button',{name:'Close live workspace',exact:true}).click()
  await page.getByRole('textbox',{name:'Message',exact:true}).fill('Create another Google Doc for tomorrow.')
  await page.getByRole('button',{name:'Send',exact:true}).click()
  await panel.getByText('Preview only. Nothing saved yet.').waitFor()
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth),false)
  assert.equal(await panel.evaluate(el => el.scrollWidth > el.clientWidth),false)
  await page.waitForFunction(() => Number(getComputedStyle(document.querySelector('#live-workspace')).opacity) > 0.99)
  await page.screenshot({path:path.join(output,'docs-mobile.png'),fullPage:true})
  await panel.getByRole('button',{name:'Cancel',exact:true}).click()
  await panel.getByText('Cancelled',{exact:true}).waitFor()
  assert.equal(decisionCount,2)
  checks.push('375px phone workspace fits, full preview scrolls, cancellation remains unsaved')
  assert.deepEqual(errors,[])
  await writeFile(path.join(output,'report.json'),JSON.stringify({checks,errors,coverage:'Built frontend with synthetic API/socket responses. OAuth, shared agent and provider requests covered by backend integration tests.'},null,2))
  console.log(JSON.stringify({checks,errors}))
} finally {
  await browser?.close()
  if (server.exitCode === null) {
    if (process.platform === 'win32') { try { execFileSync('taskkill', ['/PID', String(server.pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore' }) } catch {} }
    else server.kill()
  }
}
