// Stills of the 3D viewer. Poster mode writes the loading still of every place in web/space3d/places.json into
// web/public/space3d/posters/<slug>.webp; check mode writes overview + first stop PNGs and fails on a console error.
// usage: node web/scripts/shots_space3d.mjs <base url> poster|check [out dir] [slug ...]
import { execFileSync } from 'node:child_process'
import { mkdirSync, readFileSync, rmSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { chromium } from 'playwright-core'

const WEB = resolve(import.meta.dirname, '..')
const [BASE, MODE = 'check', DIR = join(WEB, 'shots/space3d'), ...only] = process.argv.slice(2)
const places = JSON.parse(readFileSync(join(WEB, 'space3d/places.json'), 'utf8')).map((p) => p.slug).filter((s) => !only.length || only.includes(s))
const OUT = MODE === 'poster' ? join(WEB, 'public/space3d/posters') : DIR
mkdirSync(OUT, { recursive: true })

const browser = await chromium.launch({
  executablePath: resolve(WEB, '../.cache/ms-playwright/chromium-1169/chrome-linux/chrome'),
  // SPACE3D_GL=gpu renders on the machine's GPU (much faster); the default CPU renderer works everywhere.
  args: process.env.SPACE3D_GL === 'gpu'
    ? ['--use-angle=gl-egl', '--use-gl=angle', '--enable-gpu', '--ignore-gpu-blocklist']
    : ['--use-angle=swiftshader', '--use-gl=angle', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'],
})
let bad = 0
for (const slug of places) {
  const page = await browser.newPage({ viewport: { width: 880, height: 540 }, bypassCSP: true }) // poster mode's page CSP refuses eval
  const errors = []
  page.on('pageerror', (e) => errors.push(e.message))
  page.on('console', (m) => { if (m.type() === 'error' && !/fonts\.g|favicon/.test(m.text() + m.location().url)) errors.push(m.text()) })
  // not 'load': a slow web font must not fail the place; the scene's own ready flag is awaited below
  await page.goto(`${BASE}/space3d/viewer.html?place=${slug}${MODE === 'poster' ? '&poster=1' : ''}`, { waitUntil: 'domcontentloaded' })
  await page.waitForFunction(() => window.__ready === true, null, { timeout: 180000 })
  await page.waitForTimeout(1500)
  if (MODE === 'poster') {
    const png = join(OUT, `${slug}.png`)
    await page.screenshot({ path: png, timeout: 180000 })
    execFileSync(resolve(WEB, '../.venv/bin/python'), ['-c', 'import sys;from PIL import Image;Image.open(sys.argv[1]).convert("RGB").save(sys.argv[2],"WEBP",quality=78,method=6)', png, join(OUT, `${slug}.webp`)])
    rmSync(png)
  } else {
    await page.screenshot({ path: join(OUT, `${slug}-0.png`), timeout: 180000 })
    await page.click('#tour-start'); await page.mouse.move(600, 80)
    await page.waitForTimeout(6000)
    await page.screenshot({ path: join(OUT, `${slug}-1.png`), timeout: 180000 })
  }
  console.log(slug, errors.length ? `ERRORS ${errors.slice(0, 3).join(' | ')}` : 'ok')
  bad += errors.length
  await page.close()
}
await browser.close()
process.exit(bad ? 1 : 0)
