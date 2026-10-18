import { createServer } from 'node:http'
import { readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import assert from 'node:assert/strict'
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
if (!process.env.KOE_MOCKUP_MODULES) throw Error('Set KOE_MOCKUP_MODULES to an existing node_modules directory containing playwright')
const { chromium } = await import(pathToFileURL(path.join(process.env.KOE_MOCKUP_MODULES, 'playwright/index.mjs')).href)
const types = { '.html':'text/html; charset=utf-8', '.css':'text/css', '.png':'image/png', '.svg':'image/svg+xml', '.ttf':'font/ttf', '.json':'application/json' }
const server = createServer(async (req, res) => {
  try {
    const pathname = decodeURIComponent(new URL(req.url, 'http://localhost').pathname)
    const file = path.resolve(root, '.' + (pathname === '/' ? '/index.html' : pathname))
    if (!file.startsWith(root + path.sep)) { res.writeHead(403); return res.end() }
    const body = await readFile(file)
    res.writeHead(200, { 'Content-Type': types[path.extname(file)] || 'application/octet-stream' }); res.end(body)
  } catch { res.writeHead(404); res.end('Not found') }
})
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
const origin = `http://127.0.0.1:${server.address().port}`
const browser = await chromium.launch({ channel: 'msedge', headless: true })
const context = await browser.newContext({ viewport:{width:1440,height:1000}, deviceScaleFactor:2, serviceWorkers:'block' })
const errors = [], verified = []
const page = await context.newPage()
page.on('pageerror', error => errors.push(error.message))
await context.route('**/*', route => new URL(route.request().url()).origin === origin ? route.continue() : route.abort())
const manifest = JSON.parse(await readFile(path.join(root,'manifest.json'),'utf8'))
try {
  for (const mockup of manifest) {
    await page.goto(origin + '/' + mockup.html, { waitUntil:'networkidle' })
    await page.evaluate(() => document.fonts.ready)
    const failures = await page.locator('img').evaluateAll(images => images.filter(img => !img.complete || !img.naturalWidth).map(img => img.getAttribute('src')))
    assert.deepEqual(failures,[],mockup.slug + ': broken asset')
    const size = await page.locator('.artboard,.mobile-board').boundingBox()
    assert.equal(size.width,1440); assert.equal(size.height,1000)
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth === 1440),mockup.slug + ': horizontal overflow')
    await page.screenshot({path:path.join(root,mockup.png),fullPage:true})
    const words = (await page.locator('body').innerText()).trim().split(/\s+/).length
    verified.push({slug:mockup.slug,words,width:2880,height:2000,imagesLoaded:true})
    console.log('Rendered ' + mockup.slug + ' · ' + words + ' words')
  }
  const sheetContext = await browser.newContext({ viewport:{width:1600,height:1000}, deviceScaleFactor:1, serviceWorkers:'block' })
  const sheet = await sheetContext.newPage()
  await sheet.goto(origin+'/?sheet',{waitUntil:'networkidle'})
  await sheet.evaluate(async () => { await document.fonts.ready; await Promise.all([...document.images].map(img => img.decode())) })
  await sheet.screenshot({path:path.join(root,'contact-sheet.png'),fullPage:true})
  assert.deepEqual(errors,[])
  await writeFile(path.join(root,'verification.json'),JSON.stringify({renderedAt:new Date().toISOString(),renderer:'Headless Microsoft Edge / Playwright',mockups:verified,errors,productionFilesModified:false,method:'Native HTML/CSS with original artwork; no generated or retouched mascot images.'},null,2))
  console.log('Verified 10 high-resolution mockups and the contact sheet.')
} finally { await browser.close(); await new Promise(resolve => server.close(resolve)) }
