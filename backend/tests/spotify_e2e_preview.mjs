// Smoke check the same preview URL offered to the user, without OAuth or SDK interception.
import assert from 'node:assert/strict'
import path from 'node:path'
import {pathToFileURL} from 'node:url'
const {chromium} = await import(pathToFileURL(path.join(process.env.KOE_E2E_NODE_MODULES,'playwright/index.mjs')).href)
const browser = await chromium.launch({channel:'msedge',headless:true})
try {
  const context = await browser.newContext()
  const page = await context.newPage(); const errors=[]; page.on('pageerror',e=>errors.push(e.message))
  await context.route(url=>url.hostname.endsWith('spotify.com')||url.hostname==='sdk.scdn.co',route=>route.abort())
  await context.request.post('http://127.0.0.1:8001/__e2e/control',{data:{reset:true}})
  await page.goto('http://127.0.0.1:5174/__e2e/demo')
  const choose=page.getByRole('button',{name:'Choose',exact:true})
  await page.getByRole('heading',{name:/Choose your playlist|TEST — simulated Spotify/}).first().waitFor()
  if (await choose.count()) await choose.click()
  await page.getByRole('heading',{name:'TEST — simulated Spotify (no sound)',exact:true}).waitFor()
  await page.getByRole('button',{name:'Play',exact:true}).click()
  await page.getByRole('button',{name:'Pause',exact:true}).waitFor()
  await page.getByRole('button',{name:'Pause',exact:true}).click()
  await page.getByRole('button',{name:'Play',exact:true}).waitFor()
  await page.setViewportSize({width:375,height:812})
  const title=await page.getByRole('heading',{name:'TEST — simulated Spotify (no sound)',exact:true}).boundingBox()
  assert.ok(title.width>=150)
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false)
  await page.screenshot({path:'data/spotify-e2e-browser/preview-phone.png',fullPage:true})
  assert.deepEqual(errors,[])
  console.log('Preview entry, test login, playlist selection, local SDK play/pause and phone layout passed; real Spotify requests blocked.')
} finally {await browser.close()}
