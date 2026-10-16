import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import { pathToFileURL } from 'node:url'
const [modules, output] = process.argv.slice(2)
if (!modules || !output) throw Error('Provide the Playwright package and screenshot directory.')
const { chromium } = await import(pathToFileURL(path.join(modules, 'index.mjs')).href)
const browser = await chromium.launch({ channel: 'msedge', headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, serviceWorkers: 'block' })
const page = await context.newPage()
const errors = [], checks = []
page.on('pageerror', error => errors.push(error.message))
await fs.mkdir(output, { recursive: true })
await context.route('**/auth/status', route => route.fulfill({ json: { google: true, user: null } }))
try {
  for (const theme of ['dark', 'light']) {
    for (const width of [1440, 375]) {
      await page.setViewportSize({ width, height: 1000 })
      await page.goto('http://127.0.0.1:5173/app#music')
      await page.getByRole('button', { name: 'Continue with Google', exact: true }).waitFor()
      await page.evaluate(value => document.documentElement.dataset.theme = value, theme)
      await page.locator('.signin .brand-icon').evaluate(image => image.decode())
      const logo = await page.locator('.signin .brand-icon').evaluate(image => {
        const style = getComputedStyle(image), rect = image.getBoundingClientRect()
        return { width: rect.width, height: rect.height, radius: style.borderRadius, shadow: style.boxShadow, margin: style.marginBottom }
      })
      await page.screenshot({ path: path.join(output, `${theme}-${width}.png`), fullPage: true })
      assert.deepEqual(logo, { width: 18, height: 18, radius: '0px', shadow: 'none', margin: '0px' }, 'Google logo must not inherit mascot sizing or ring')
      const mascot = await page.locator('.signin > img').evaluate(image => {
        const style = getComputedStyle(image), rect = image.getBoundingClientRect()
        return { width: rect.width, height: rect.height, radius: style.borderRadius, ring: style.boxShadow !== 'none' }
      })
      assert.deepEqual(mascot, { width: 96, height: 96, radius: '50%', ring: true })
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false)
      assert.ok(await page.locator('.signin .primary').evaluate(button => { const a = button.getBoundingClientRect(), b = button.querySelector('img').getBoundingClientRect(); return b.top >= a.top && b.bottom <= a.bottom }))
      await page.getByRole('button', { name: 'Continue with Google', exact: true }).focus()
      assert.equal(await page.getByRole('button', { name: 'Continue with Google', exact: true }).evaluate(button => document.activeElement === button), true)
      checks.push(`${theme} ${width}px: original mascot ring, 18px Google logo, button fit and keyboard focus`)
    }
  }
  assert.deepEqual(errors, [])
  await fs.writeFile(path.join(output, 'report.json'), JSON.stringify({ checks, errors }, null, 2))
  console.log(JSON.stringify({ passed: checks.length, checks, errors, output }, null, 2))
} finally { await browser.close() }
