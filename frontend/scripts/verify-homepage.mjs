// Local browser smoke check. Uses the already bundled Playwright; no accounts or provider mutations.
// node scripts/verify-homepage.mjs <absolute Playwright package directory> <absolute screenshot directory>
import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { auditControls } from './verify-interactions.mjs'
import { pathToFileURL } from 'node:url'

const [playwrightPath, output] = process.argv.slice(2)
if (!playwrightPath || !output) throw Error('Provide the Playwright package directory and screenshot directory.')
const { chromium } = await import(pathToFileURL(path.join(playwrightPath, 'index.mjs')).href)
const origin = process.env.KOE_HOMEPAGE_ORIGIN ?? 'http://127.0.0.1:5173'
const browser = await chromium.launch({ channel: 'msedge', headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, serviceWorkers: 'block' })
const page = await context.newPage()
const errors = []
const checks = []
const vrmRequests = []
const heroSources = new Set()
page.on('pageerror', error => errors.push(error.message))
page.on('request', request => { if (new URL(request.url()).pathname.endsWith('.vrm')) vrmRequests.push(request.url()) })
await mkdir(output, { recursive: true })

try {
  for (const look of ['studio']) {
    await page.goto(`${origin}/?look=${look}`, { waitUntil: 'networkidle' })
    await page.locator('.hp-scene[data-ready="true"]').waitFor({ timeout: 60000 })
    await page.locator('.hp-mascot-art').evaluate(image => image.decode())
    heroSources.add(await page.locator('.hp-mascot-art').getAttribute('src'))
    await page.locator('.hp-hero-bottom').scrollIntoViewIfNeeded()
    await page.evaluate(() => scrollTo(0, 0))
    await page.waitForTimeout(1100)
    assert.equal(await page.locator('.hp').getAttribute('data-look'), look)
    assert.equal(await page.locator('h1').count(), 1)
    const badImages = await page.locator('.hp .brand-icon').evaluateAll(images => images.filter(image => !image.complete || image.naturalWidth === 0).map(image => image.src))
    assert.deepEqual(badImages, [], `Broken provider logos: ${look}`)
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `Desktop overflow: ${look}`)
    await auditControls(page, 'Homepage', checks)
    await page.screenshot({ path: path.join(output, `${look}-desktop.png`) })
    assert.equal(await page.locator('.hp-scene canvas').count(), 0)
    checks.push(`${look}: supplied mascot PNG, original logos, no automatic 3D download, no desktop overflow`)

    await page.getByRole('button', { name: 'Find a time', exact: true }).click()
    await page.getByRole('button', { name: 'Try approving', exact: true }).click()
    assert.equal(await page.getByRole('button', { name: 'Approved in demo', exact: true }).isDisabled(), true)
    await page.getByRole('button', { name: 'Capture a thought', exact: true }).click()
    assert.equal(await page.getByRole('button', { name: 'Try approving', exact: true }).isEnabled(), true)
    await page.getByRole('button', { name: 'Coming next 02', exact: true }).click()
    assert.equal(await page.locator('.hp-integration').count(), 2)
    await page.getByRole('button', { name: 'Learn about Google Docs, planned integration' }).click()
    assert.equal(await page.getByRole('dialog').isVisible(), true)
    assert.equal(await page.getByRole('dialog').getByText('This connection is planned. You cannot connect it yet.').isVisible(), true)
    await page.keyboard.press('Escape')
    assert.equal(await page.getByRole('dialog').isVisible(), false)
    await page.getByRole('button', { name: 'Available 05', exact: true }).click()
    assert.equal(await page.locator('.hp-integration').count(), 5)
    await page.getByRole('button', { name: 'Learn about GitHub', exact: true }).click()
    assert.equal(await page.getByRole('dialog').getByRole('link', { name: 'Manage in the app' }).getAttribute('href'), '/app#settings')
    await page.getByRole('button', { name: 'Close connection details' }).click()
    await page.locator('summary').filter({ hasText: 'Do I have to use my voice?' }).click()
    assert.equal(await page.locator('details[open]').count(), 1)
    checks.push(`${look}: demo approval and reset, integration filters, modal details/Escape/focus, FAQ disclosure`)

    await page.getByRole('button', { name: 'All connections 07', exact: true }).click()
    await page.locator('.hp-closing').scrollIntoViewIfNeeded()
    await page.waitForTimeout(850)
    await page.screenshot({ path: path.join(output, `${look}-full.png`), fullPage: true })

    await page.setViewportSize({ width: 375, height: 812 })
    await page.evaluate(() => scrollTo(0, 0))
    await page.waitForTimeout(350)
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `Mobile overflow: ${look}`)
    await page.screenshot({ path: path.join(output, `${look}-mobile.png`) })
    checks.push(`${look}: 375px mobile layout without horizontal overflow`)
    await page.setViewportSize({ width: 1440, height: 1000 })
  }

  assert.equal(heroSources.size, 1, 'Only the Studio artwork should be used')
  assert.deepEqual(vrmRequests, [], 'Artwork previews must not automatically download a VRM')

  await page.goto(origin, { waitUntil: 'networkidle' })
  await page.getByRole('button', { name: 'Say hello to Kami' }).click()
  assert.equal(await page.getByText('Hey there. Let’s make today lighter.').isVisible(), true)
  await page.getByRole('button', { name: 'TRY IN 3D', exact: true }).click()
  await page.locator('.hp-scene[data-live="true"][data-ready="true"]').waitFor({ timeout: 60000 })
  assert.equal(await page.locator('.hp-scene canvas').isVisible(), true)
  assert.equal(vrmRequests.length, 1)
  await page.getByRole('button', { name: 'BACK TO ARTWORK', exact: true }).click()
  assert.equal(await page.locator('.hp-scene canvas').count(), 0)
  assert.equal(await page.locator('.hp-mascot-art').isVisible(), true)
  checks.push('Optional 3D downloads only on request and returns cleanly to the supplied PNG')
  await page.getByRole('button', { name: 'Preview Mei' }).click()
  await page.locator('.hp-mascot-art').evaluate(image => image.decode())
  assert.match(await page.locator('.hp-mascot-art').getAttribute('src'), /21-44\.png/)
  await page.getByRole('button', { name: 'Preview Kobashi' }).click()
  await page.locator('.hp-mascot-art').evaluate(image => image.decode())
  assert.match(await page.locator('.hp-mascot-art').getAttribute('src'), /17-58\.png/)
  checks.push('Mei and Kobashi selectors load their supplied Studio artwork')
  assert.equal(await page.locator('.hp-portrait').count(), 3)
  assert.equal(await page.getByRole('button', { name: 'Preview Aoi' }).count(), 0)
  assert.equal(await page.locator('img[src*="aoi"]').count(), 0)
  assert.equal(await page.locator('.hp-look-picker').count(), 0)
  assert.match(await page.locator('.hp-numbers > div').nth(2).innerText(), /03/)
  checks.push('Only Kami, Mei and Kobashi appear; companion count is three and the design picker is removed')

  for (const legacyLook of ['after-hours', 'field-notes']) {
    await page.goto(`${origin}/?look=${legacyLook}`, { waitUntil: 'networkidle' })
    await page.locator('.hp').waitFor()
    await page.waitForURL(url => !url.searchParams.has('look'))
    assert.equal(await page.locator('.hp').getAttribute('data-look'), 'studio')
    assert.equal(await page.locator('.hp-look-picker').count(), 0)
  }
  checks.push('Former variation URLs resolve to Studio and remove the obsolete query')

  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto(`${origin}/?look=studio`, { waitUntil: 'networkidle' })
  await page.locator('h1').waitFor()
  assert.equal(await page.locator('h1').isVisible(), true)
  assert.equal(await page.locator('.hp-hero-copy').evaluate(element => getComputedStyle(element).opacity), '1')
  await page.getByRole('button', { name: 'Say hello to Kami' }).click()
  assert.equal(await page.locator('.hp-mascot-art').evaluate(element => element.style.transform), '')
  checks.push('Reduced-motion mode shows content without entrance animations')
  await auditControls(page, 'Homepage reduced motion', checks, true)

  // Synthetic auth status checks route gating, with no live identity or session access.
  await context.route('**/auth/status', route => route.fulfill({ json: { google: true, user: null } }))
  for (const url of ['/app', '/#settings']) {
    await page.goto(origin + url)
    await page.getByRole('button', { name: 'Continue with Google' }).waitFor()
    assert.deepEqual(await page.locator('.signin .brand-icon').evaluate(image => {
      const style = getComputedStyle(image), bounds = image.getBoundingClientRect()
      return [bounds.width, bounds.height, style.borderRadius, style.boxShadow]
    }), [18, 18, '0px', 'none'], 'Google mark must not inherit mascot styles')
    checks.push(`${url}: existing sign-in gate preserved`)
  }
  for (const url of ['/guide', '/privacy', '/terms']) {
    await page.goto(origin + url, { waitUntil: 'networkidle' })
    assert.match(await page.locator('.doc-page').evaluate(element => getComputedStyle(element).fontFamily), /Geist/)
    assert.equal(await page.locator('.doc-page').evaluate(element => getComputedStyle(element).fontSize), '15px')
    await page.locator('.doc-top a').first().focus()
    await page.keyboard.press('Tab')
    assert.ok(await page.evaluate(() => parseFloat(getComputedStyle(document.activeElement).outlineWidth) >= 1))
    for (const width of [1440, 375]) {
      await page.setViewportSize({ width, height: 1000 })
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
    }
    checks.push(`${url}: consistent Geist typography and keyboard focus; desktop/mobile fit`)
  }
  assert.deepEqual(errors, [], 'Uncaught browser errors')
  await writeFile(path.join(output, 'verification.json'), JSON.stringify({ checks, errors }, null, 2))
  console.log(JSON.stringify({ passed: checks.length, checks, errors, output }, null, 2))
} finally {
  await browser.close()
}
