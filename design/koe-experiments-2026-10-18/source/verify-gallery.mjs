import {readFile,writeFile} from 'node:fs/promises'
import path from 'node:path'
import {fileURLToPath,pathToFileURL} from 'node:url'
import assert from 'node:assert/strict'
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..')
if(!process.env.KOE_MOCKUP_MODULES)throw Error('Set KOE_MOCKUP_MODULES to an existing node_modules containing playwright')
const {chromium}=await import(pathToFileURL(path.join(process.env.KOE_MOCKUP_MODULES,'playwright/index.mjs')).href)
const manifest=JSON.parse(await readFile(path.join(root,'manifest.json'),'utf8'))
assert.equal(manifest.length,5)
const browser=await chromium.launch({channel:'msedge',headless:true})
const page=await browser.newPage({viewport:{width:1600,height:1000},deviceScaleFactor:1})
const errors=[],checks=[]
page.on('pageerror',e=>errors.push(e.message))
try{
 await page.goto(pathToFileURL(path.join(root,'index.html')).href+'?sheet')
 await page.evaluate(async()=>{await document.fonts.ready;await Promise.all([...document.images].map(i=>i.decode()))})
 const images=await page.locator('main img').evaluateAll(imgs=>imgs.map(i=>({src:i.getAttribute('src'),width:i.naturalWidth,height:i.naturalHeight})))
 assert.equal(images.length,5)
 for(const m of manifest){const actual=images.find(i=>i.src===m.png);assert.equal(actual.width,m.width);assert.equal(actual.height,m.height)}
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth),1600)
 await page.screenshot({path:path.join(root,'contact-sheet.png'),fullPage:true})
 checks.push('Five original PNGs loaded and dimensions match manifest','Desktop gallery has no horizontal overflow','Full-page overview captured')
 await page.goto(pathToFileURL(path.join(root,'index.html')).href)
 await page.setViewportSize({width:390,height:844})
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth),390)
 checks.push('390px gallery has no horizontal overflow')
 assert.deepEqual(errors,[])
 await writeFile(path.join(root,'verification.json'),JSON.stringify({verifiedAt:new Date().toISOString(),renderer:'Microsoft Edge via Playwright',checks,errors,artworkMode:'Built-in image_gen',productionAppModifiedByThisTask:false},null,2))
 console.log('Verified 5 files, native dimensions, desktop/mobile gallery, no page errors; overview saved.')
}finally{await browser.close()}
