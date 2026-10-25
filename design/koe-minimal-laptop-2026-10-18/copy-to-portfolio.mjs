import {copyFile,mkdir,readFile,writeFile,access} from 'node:fs/promises'
import {createRequire} from 'node:module'
import {createHash} from 'node:crypto'
import path from 'node:path'
import {fileURLToPath} from 'node:url'
const source=path.dirname(fileURLToPath(import.meta.url))
const portfolio='C:/Users/Rohit Maity/Desktop/coding/Webdev/project/portfolio-2'
const target=path.join(portfolio,'site-assets/mockups/koe')
const thumbnail=path.join(portfolio,'site-assets/thumbnails/koe.webp')
const require=createRequire(path.join(portfolio,'package.json'))
const sharp=require('sharp')
const exists=async file=>{try{await access(file);return true}catch{return false}}
const hash=buffer=>createHash('sha256').update(buffer).digest('hex')
const names=['01-koe-logo.png','02-kami-face.png']
// Validate sources and existing targets before changing the portfolio.
for(const name of names){
 const input=await readFile(path.join(source,name))
 const meta=await sharp(input).metadata()
 if(meta.width!==1448||meta.height!==1086)throw Error('Unexpected original dimensions: '+name)
 if(await exists(path.join(target,name))){if(hash(await readFile(path.join(target,name)))!==hash(input))throw Error('Different file already exists: '+name)}
}
const optimized=await sharp(path.join(source,names[0])).resize({width:1200,withoutEnlargement:true}).webp({quality:90}).toBuffer()
await mkdir(target,{recursive:true})
if(await exists(thumbnail)&&!await exists(path.join(target,'previous-thumbnail.webp')))await copyFile(thumbnail,path.join(target,'previous-thumbnail.webp'))
for(const name of names){
 await copyFile(path.join(source,name),path.join(target,name))
 if(hash(await readFile(path.join(source,name)))!==hash(await readFile(path.join(target,name))))throw Error('Copy verification failed: '+name)
}
await writeFile(thumbnail,optimized)
const meta=await sharp(thumbnail).metadata()
if(meta.width!==1200||meta.height!==900)throw Error('Thumbnail dimensions failed')
await writeFile(path.join(target,'README.md'),`# Koe laptop mockups\n\nTwo original 1448 × 1086 PNGs copied from Koe/design/koe-minimal-laptop-2026-10-18 on 18 October 2026.\n\n- 01-koe-logo.png: minimal 声 / Koe screen.\n- 02-kami-face.png: minimal Kami portrait screen.\n- previous-thumbnail.webp: retained previous home preview, when present.\n\nThe logo image is encoded as a 1200 × 900 WebP at site-assets/thumbnails/koe.webp. The existing src/config/assets.js loader imports that shared thumbnail automatically for all five themes. No page or loader changes are required. The face version remains available here for a future import.\n\nBoth are generated presentation artwork based on the supplied Neuron laptop composition and Koe mascot reference, not application screenshots. Case-page screenshot evidence is unchanged. Original PNGs are copied byte for byte.\n`)
console.log(JSON.stringify({originals:names.map(n=>path.join(target,n)),thumbnail,width:meta.width,height:meta.height,bytes:optimized.length,copyHashesMatch:true},null,2))
