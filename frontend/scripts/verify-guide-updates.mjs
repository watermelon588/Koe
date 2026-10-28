// Local public-page verification: preservation, real screenshots, links and demo-only controls.
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { fileURLToPath, pathToFileURL } from 'node:url'
import path from 'node:path'

const [playwrightPath, output] = process.argv.slice(2)
if (!playwrightPath || !output) throw Error('Provide Playwright and evidence directories.')
const { chromium } = await import(pathToFileURL(path.join(playwrightPath, 'index.mjs')).href)
const browser = await chromium.launch({ channel: 'msedge', headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, serviceWorkers: 'block', reducedMotion: 'reduce' })
const page = await context.newPage()
const errors = [], backendRequests = [], checks = []
const origin = process.env.KOE_HOMEPAGE_ORIGIN ?? 'http://127.0.0.1:5173'
page.on('pageerror', error => errors.push(error.message))
await context.route(/\/(api|auth)\//, route => {
  backendRequests.push(route.request().url())
  return route.fulfill({ status: 503, json: { detail: 'Public-page check: no backend' } })
})
await mkdir(output, { recursive: true })
try {
  const previous = execFileSync('git', ['show', 'HEAD:frontend/src/pages/Guide.tsx'], { encoding: 'utf8' })
  const current = await readFile(fileURLToPath(new URL('../src/pages/Guide.tsx', import.meta.url)), 'utf8')
  // The user explicitly removed the future roadmap; preserve all other original content.
  const retained = previous.replace(/<Section id="later"[\s\S]*?<\/Section>/, '')
  const originalLines = retained.split(/\r?\n/).map(line => line.trim()).filter(line => /^<(p[ >]|li[ >]|dd[ >]|dt[ >]|Section )/.test(line))
  for (const line of originalLines) assert.ok(current.includes(line), `Original guide content removed: ${line.slice(0, 90)}`)
  checks.push(`All ${originalLines.length} original guide paragraphs, list entries, troubleshooting entries and section headings preserved`)

  await page.goto(origin + '/guide')
  await page.getByRole('heading', { name: 'Guide', exact: true }).waitFor()
  assert.match(await page.locator('.doc-foot').innerText(), /Updated 28 October 2026/)
  const sections = await page.locator('.doc-page section').evaluateAll(nodes => nodes.map(node => node.id))
  const toc = await page.locator('.doc-toc a').evaluateAll(nodes => nodes.map(node => node.hash.slice(1)))
  assert.deepEqual(toc, sections, 'Table of contents follows every actual section in order')
  assert.equal(new Set(sections).size, sections.length)
  assert.equal(await page.locator('#later, a[href="#later"]').count(), 0)
  assert.equal(await page.getByText('Coming later', { exact: true }).count(), 0)
  checks.push('Guide update date, complete ordered contents and unique section anchors verified')

  assert.equal(await page.locator('.guide-screenshot').count(), 4)
  for (const figure of await page.locator('.guide-screenshot').all()) {
    await figure.scrollIntoViewIfNeeded()
    await figure.locator('img').evaluate(image => image.decode())
    const dimensions = await figure.locator('img').evaluate(image => [image.naturalWidth, image.naturalHeight])
    assert.deepEqual(dimensions, [1280, 900])
    assert.ok((await figure.locator('img').getAttribute('alt')).length > 25)
    assert.equal(await figure.locator('a').first().getAttribute('href'), await figure.locator('img').getAttribute('src'))
  }
  assert.equal(await page.getByText('EXAMPLE WORKSPACE · SAMPLE DATA', { exact: true }).count(), 3)
  checks.push('Four local screenshots decode at 1280×900 with descriptive alt text, full-size links and sample-data captions')

  for (const theme of ['dark', 'light']) {
    await page.addInitScript(value => localStorage.setItem('koe-theme', value), theme)
    await page.reload()
    for (const width of [320, 375, 768, 1440]) {
      await page.setViewportSize({ width, height: 1000 })
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `${theme} guide overflow at ${width}`)
      if (width === 375 || width === 1440) {
        await page.locator('#connect .guide-screenshot').scrollIntoViewIfNeeded()
        await page.screenshot({ path: path.join(output, `guide-${theme}-${width}.png`) })
      }
    }
  }
  checks.push('Guide screenshots and text fit 320/375/768/1440px in dark and light themes')
  assert.deepEqual(backendRequests, [], 'The public guide requires no backend or account access')

  await page.goto(origin)
  await page.locator('.hp-scene[data-ready="true"]').waitFor({ timeout: 90000 })
  for (const id of ['product', 'connections', 'companion', 'questions', 'updates']) assert.equal(await page.locator(`section#${id}`).count(), 1)
  assert.equal(await page.locator('.hp-integration').count(), 6)
  assert.equal(await page.locator('.hp-portrait').count(), 3)
  assert.equal(await page.locator('.hp-faq details').count(), 9)
  assert.equal(await page.getByRole('button', { name: 'Start my day', exact: true }).count(), 1)
  assert.equal(await page.getByRole('button', { name: 'Find a time', exact: true }).count(), 1)
  assert.equal(await page.getByRole('button', { name: 'Capture a thought', exact: true }).count(), 1)
  for (const scenario of ['Draft a document', 'Correct an entry']) {
    await page.getByRole('button', { name: scenario, exact: true }).click()
    await page.getByRole('button', { name: 'Try approving', exact: true }).click()
    assert.equal(await page.getByRole('button', { name: 'Approved in demo', exact: true }).isDisabled(), true)
  }
  checks.push('Existing homepage sections, integrations, companions and three scenarios remain; both new demos work locally')
  const guideLinks = await page.locator('#updates a[href^="/guide#"]').evaluateAll(nodes => nodes.map(node => node.hash.slice(1)))
  for (const id of guideLinks) assert.ok(sections.includes(id), `Broken guide deep link: ${id}`)
  for (const width of [320, 375, 768, 1440]) {
    await page.setViewportSize({ width, height: 1000 })
    await page.locator('#updates').scrollIntoViewIfNeeded()
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `Homepage overflow at ${width}`)
    if (width === 375 || width === 1440) await page.screenshot({ path: path.join(output, `homepage-updates-${width}.png`) })
  }
  checks.push('Recent-improvement links target real guide sections; expanded demo and updates fit mobile/tablet/desktop')
  assert.deepEqual(errors, [])
  assert.deepEqual(backendRequests, [])
  await writeFile(path.join(output, 'verification.json'), JSON.stringify({ checks, errors, backendRequests }, null, 2))
  console.log(JSON.stringify({ passed: checks.length, checks, errors, backendRequests }, null, 2))
} finally { await browser.close() }
