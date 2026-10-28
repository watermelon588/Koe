// Isolated browser check; no accounts, backend calls or provider mutations.
// node scripts/verify-homepage-3d.mjs <Playwright package directory> <evidence directory>
import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { pathToFileURL } from 'node:url'

const [playwrightPath, output] = process.argv.slice(2)
if (!playwrightPath || !output) throw Error('Provide Playwright and evidence directories.')
const { chromium } = await import(pathToFileURL(path.join(playwrightPath, 'index.mjs')).href)
const browser = await chromium.launch({ channel: 'msedge', headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, serviceWorkers: 'block' })
// Test-only draw counter verifies actual GPU work stops on pause and offscreen.
await context.addInitScript(() => {
  window.__mascotDraws = 0
  const prototype = WebGL2RenderingContext.prototype
  const draw = prototype.drawElements
  prototype.drawElements = function (...args) {
    window.__mascotDraws++
    return draw.apply(this, args)
  }
})
const page = await context.newPage()
const errors = [], requests = [], checks = []
page.on('pageerror', error => errors.push(error.message))
page.on('request', request => {
  if (new URL(request.url()).pathname.endsWith('.vrm')) requests.push(request.url())
})
const origin = process.env.KOE_HOMEPAGE_ORIGIN ?? 'http://127.0.0.1:5173'
const ready = () => page.locator('.hp-scene[data-ready="true"]').waitFor({ timeout: 90000 })
const draws = () => page.evaluate(() => window.__mascotDraws)
await mkdir(output, { recursive: true })

try {
  await page.goto(origin)
  console.log('Homepage loaded; waiting for VRM')
  await ready()
  const canvas = page.locator('.hp-scene canvas')
  assert.equal(await canvas.isVisible(), true)
  assert.equal(await page.locator('.hp-mascot-art').isVisible(), false)
  assert.ok(requests.some(url => url.endsWith('/kami.vrm')))
  await page.waitForTimeout(500)
  const initial = await draws()
  await page.waitForTimeout(600)
  assert.ok(await draws() > initial, 'Idle model must actually render new frames')
  checks.push('Kami VRM loads automatically, replaces fallback and animates')
  console.log(checks.at(-1))

  await page.mouse.move(500, 260)
  await page.waitForTimeout(900)
  await page.screenshot({ path: path.join(output, 'cursor-left.png') })
  await page.mouse.move(1390, 400)
  await page.waitForTimeout(900)
  await page.screenshot({ path: path.join(output, 'cursor-right.png') })
  await page.getByRole('button', { name: 'Say hello to Kami' }).click()
  await page.waitForTimeout(700)
  await page.screenshot({ path: path.join(output, 'wave-desktop.png') })
  assert.equal(await page.getByText('Hey there. Let’s make today lighter.').isVisible(), true)
  checks.push('Cursor tracking and wave captured for visual inspection')

  await page.getByRole('button', { name: 'Pause companion movement' }).click()
  await page.waitForTimeout(250)
  const paused = await draws()
  await page.mouse.move(300, 150)
  await page.waitForTimeout(600)
  assert.equal(await draws(), paused, 'Pause stops rendering and cursor motion')
  await page.getByRole('button', { name: 'Resume companion movement' }).focus()
  await page.keyboard.press('Enter')
  await page.waitForTimeout(500)
  assert.ok(await draws() > paused, 'Keyboard resume restarts animation')
  checks.push('Pause freezes the model; keyboard resume restarts rendering')

  await page.getByRole('button', { name: 'Preview Mei' }).scrollIntoViewIfNeeded()
  await page.waitForTimeout(300)
  const offscreen = await draws()
  await page.waitForTimeout(500)
  assert.equal(await draws(), offscreen, 'Offscreen hero stops rendering')
  checks.push('Offscreen hero suspends GPU rendering')

  for (const [name, id] of [['Mei', 'miku'], ['Kobashi', 'kobashi'], ['Kami', 'kami']]) {
    await page.getByRole('button', { name: `Preview ${name}`, exact: true }).click()
    await ready()
    assert.equal(await page.locator('.hp-scene canvas').count(), 1)
    assert.equal(await canvas.getAttribute('aria-label').then(text => text.startsWith(name)), true)
    assert.ok(requests.some(url => url.endsWith(`/${id}.vrm`)))
    await page.locator('.hp-scene').scrollIntoViewIfNeeded()
    await page.waitForTimeout(400)
    await page.screenshot({ path: path.join(output, `${id}-desktop.png`) })
  }
  checks.push('All three selectors load corresponding VRMs with one canvas at a time')

  for (const width of [320, 375, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 1000 })
    await page.locator('.hp-scene').scrollIntoViewIfNeeded()
    await page.waitForTimeout(250)
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `Overflow at ${width}px`)
    assert.equal(await canvas.isVisible(), true)
    if (width === 375) await page.screenshot({ path: path.join(output, 'mobile.png') })
  }
  checks.push('3D hero fits 320, 375, 768, 1024 and 1440px layouts')

  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.waitForTimeout(250)
  assert.equal(await page.getByRole('button', { name: 'Resume companion movement' }).isVisible(), true)
  const reduced = await draws()
  await page.waitForTimeout(500)
  assert.equal(await draws(), reduced)
  await page.reload()
  await ready()
  await page.locator('.hp-scene').scrollIntoViewIfNeeded()
  await page.waitForTimeout(250)
  const reloadReduced = await draws()
  await page.waitForTimeout(500)
  assert.equal(await draws(), reloadReduced, 'Reduced motion also works on initial load')
  checks.push('Live reduced-motion changes and initial reduced-motion load freeze the 3D model')

  await context.route('**/mascot/kami.vrm', route => route.fulfill({ status: 503, body: 'Simulated unavailable model' }))
  await page.reload()
  await page.getByRole('alert').waitFor()
  assert.equal(await page.locator('.hp-mascot-art').isVisible(), true)
  assert.equal(await page.getByRole('button', { name: 'Say hello to Kami' }).isDisabled(), true)
  await context.unroute('**/mascot/kami.vrm')
  await page.getByRole('button', { name: 'Retry mascot' }).click()
  await ready()
  assert.equal(await page.locator('.hp-mascot-art').isVisible(), false)
  checks.push('Failed VRM keeps artwork visible and Retry restores 3D')

  assert.deepEqual(errors, [])
  await writeFile(path.join(output, 'verification.json'), JSON.stringify({ checks, errors, requests }, null, 2))
  console.log(JSON.stringify({ passed: checks.length, checks, errors }, null, 2))
} catch (error) {
  await page.screenshot({ path: path.join(output, 'failure.png') }).catch(() => {})
  console.error({ errors, requests, state: await page.locator('.mascot-view').getAttribute('data-load').catch(() => null) })
  throw error
} finally {
  await browser.close()
}
