// Real browser + Vite proxy + Koe HTTP/auth/storage; Spotify itself is simulated.
// Run with KOE_E2E_NODE_MODULES pointing to an existing Playwright installation.
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const modules = process.env.KOE_E2E_NODE_MODULES
if (!modules) throw new Error('Set KOE_E2E_NODE_MODULES to an existing Node package directory containing playwright')
const { chromium } = await import(pathToFileURL(path.join(modules, 'playwright/index.mjs')).href)
const origin = process.env.KOE_E2E_ORIGIN ?? 'http://127.0.0.1:5174'
const fixture = process.env.KOE_E2E_FIXTURE ?? 'http://127.0.0.1:8001'
const output = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../data/spotify-voice-e2e-browser')
await fs.mkdir(output, { recursive: true })
const checks = []
const errors = []
const browser = await chromium.launch({ channel: 'msedge', headless: true,
  args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] })
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, permissions: ['microphone'] })
const page = await context.newPage()
page.on('pageerror', e => errors.push(e.message))
await context.route(origin + '/__e2e/**', async route => {
  const response = await route.fetch({url: fixture + new URL(route.request().url()).pathname})
  await route.fulfill({response})
})
await context.route('https://sdk.scdn.co/spotify-player.js', route => route.fulfill({
  contentType: 'application/javascript', path: path.join(path.dirname(fileURLToPath(import.meta.url)), 'spotify_e2e_sdk.js'),
}))
const state = async () => (await context.request.get(fixture + '/__e2e/state')).json()
const control = data => context.request.post(fixture + '/__e2e/control', {data})
async function until(test, message) {
  for (let n = 0; n < 100; n++) { if (await test()) return; await new Promise(r => setTimeout(r,100)) }
  throw Error(message)
}
await context.route('https://accounts.spotify.com/authorize**', async route => {
  const url = new URL(route.request().url())
  assert.equal(url.searchParams.get('redirect_uri'), origin + '/auth/spotify/callback')
  await route.fulfill({ status: 302, headers: { location: origin + '/auth/spotify/callback?code=simulated-code&state=' + encodeURIComponent(url.searchParams.get('state')) }, body: '' })
})

// Instrument the actual voice AudioContext without replacing its audio behavior.
await context.addInitScript(() => {
  window.__audioClosed = []
  const close = AudioContext.prototype.close
  AudioContext.prototype.close = function () {
    return close.call(this).then(() => { window.__audioClosed.push({ rate: this.sampleRate, state: this.state }) })
  }
  const request = window.fetch.bind(window)
  window.fetch = (url, options) => {
    if (String(url).includes('/api/music/voice-release')) window.__releaseAfterVoiceClosed = window.__audioClosed.some(item => item.rate === 24000 && item.state === 'closed')
    return request(url, options)
  }
})
context.on('page', child => child.on('pageerror', error => errors.push(error.message)))
try {
  await control({ reset: true })
  await page.goto(fixture + '/__e2e/demo', { waitUntil: 'networkidle' })
  await page.getByRole('heading', { name: /^(Choose your playlist|TEST — simulated Spotify \(no sound\))$/ }).waitFor()
  if (await page.getByRole('heading', { name: 'Choose your playlist', exact: true }).isVisible()) await page.getByRole('button', { name: 'Choose', exact: true }).click()
  await page.getByRole('heading', { name: 'TEST — simulated Spotify (no sound)', exact: true }).waitFor()
  const voice = page
  assert.equal(await page.getByRole('link', { name: 'Open voice agent', exact: true }).count(),0)
  await page.locator('.music-assistant-portrait').waitFor()
  assert.equal(await voice.locator('.bar').evaluate(element => getComputedStyle(element).position), 'fixed')
  assert.equal(await voice.evaluate(() => getComputedStyle(document.body).fontSize), '15px')
  checks.push('Voice and music share Music; compact portrait replaces full body, app font size preserved')
  async function startCall() {
    await voice.getByRole('button', { name: 'Call Koe', exact: true }).click()
    await voice.locator('.app[data-state="listening"]').waitFor({ timeout: 20000 })
    assert.equal((await state()).playing, false)
  }
  async function send(args) {
    const count = (await state()).music_results.length
    await voice.getByRole('textbox', { name: 'Message', exact: true }).fill('E2E_MUSIC ' + JSON.stringify(args))
    await voice.getByRole('button', { name: 'Send', exact: true }).click()
    await until(async () => (await state()).music_results.length > count, 'Music function response missing')
    return (await state()).music_results.at(-1)
  }
  await startCall()
  assert.equal((await (await context.request.get(origin + '/api/music/voice-permission')).json()).enabled, true)
  checks.push('Call explicitly grants the selected playlist and prepares its control channel without manual Play')
  assert.deepEqual(await send({ action: 'set_volume', volume_percent: 30 }), { action: 'set_volume', state: 'applied' })
  assert.deepEqual(await send({ action: 'volume_down' }), { action: 'volume_down', state: 'applied' })
  assert.deepEqual(await send({ action: 'volume_up' }), { action: 'volume_up', state: 'applied' })
  assert.equal((await state()).playing, false)
  checks.push('Voice volume commands set a bounded future level while music remains paused')
  assert.deepEqual(await send({ action: 'play' }), { action: 'play', state: 'queued' })
  await voice.locator('.app[data-call="off"]').waitFor({ timeout: 20000 })
  await until(async () => (await state()).playing, 'Approved voice playback did not start after handoff')
  assert.equal(await voice.evaluate(() => window.__releaseAfterVoiceClosed), true)
  assert.ok(Math.abs((await state()).volume - .3) < .001)
  checks.push('Real voice adapter queues play; drains PCM, closes voice audio and releases ownership before real HTTP music release starts the simulated SDK')
  await startCall()
  assert.deepEqual(await send({ action: 'next' }), { action: 'next', state: 'queued' })
  await voice.locator('.app[data-call="off"]').waitFor()
  await until(async () => (await state()).playing && (await state()).index === 1, 'Bounded next failed')
  await startCall()
  assert.deepEqual(await send({ action: 'previous' }), { action: 'previous', state: 'queued' })
  await voice.locator('.app[data-call="off"]').waitFor()
  await until(async () => (await state()).playing && (await state()).index === 0, 'Bounded previous failed')
  checks.push('Next/previous remain within the explicitly allowed playlist and use the same audio handoff')
  await startCall()
  assert.deepEqual(await send({ action: 'pause' }), { action: 'pause', state: 'applied' })
  await voice.getByRole('button', { name: 'End call', exact: true }).click()
  await voice.locator('.app[data-call="off"]').waitFor()
  assert.equal((await state()).playing, false)
  checks.push('Pause cancels playback and ordinary hang-up does not auto-resume music')
  await startCall()
  await page.getByRole('button', { name: 'Disable voice controls', exact: true }).click()
  await until(async () => !(await (await context.request.get(origin + '/api/music/voice-permission')).json()).enabled, 'Grant was not revoked')
  const denied = await send({ action: 'play' })
  assert.equal(denied.error.code, 'spotify_voice_permission_required')
  assert.equal((await state()).playing, false)
  await voice.getByRole('button', { name: 'End call', exact: true }).click()
  checks.push('Revocation denies the voice tool immediately and does not send a playback command')
  assert.equal(JSON.stringify((await state()).music_results).includes('spotify:track:'), false)
  assert.equal(JSON.stringify((await state()).music_results).includes('access_token'), false)
  checks.push('Model tool responses contain only generic transport outcomes, never Spotify content or credentials')
  await page.screenshot({ path: path.join(output, 'separate-music-window.png'), fullPage: true })
  await voice.screenshot({ path: path.join(output, 'original-voice-window.png') })
  await page.setViewportSize({ width: 375, height: 812 })
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false)
  await page.screenshot({ path: path.join(output, 'music-mobile.png'), fullPage: true })
  assert.deepEqual(await page.locator('.brand-icon').evaluateAll(images => images.filter(image => !image.complete || !image.naturalWidth).map(image => image.src)), [])
  checks.push('Original provider artwork loads and the new permission controls fit the existing mobile layout')
  assert.deepEqual(errors, [])
  const report = { checks, errors, coverage: 'Actual Vite/FastAPI/auth/SQLite/music bridge/voice adapter/PCM/Web Locks; Spotify, SDK audio and Gemini function selection simulated. No live streaming or speech-recognition claim.' }
  await fs.writeFile(path.join(output, 'report.json'), JSON.stringify(report, null, 2))
  console.log(JSON.stringify({ passed: checks.length, ...report, output }, null, 2))
} catch (error) {
  await page.screenshot({ path: path.join(output, 'failure.png'), fullPage: true }).catch(() => {})
  const failure = JSON.stringify({ error: String(error), checks, errors, state: await state() }, null, 2)
  await fs.writeFile(path.join(output, 'failure.json'), failure)
  console.error(failure)
  process.exitCode = 1
} finally { await browser.close() }
