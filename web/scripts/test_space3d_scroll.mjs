// The wheel tour of the 3D viewer: overview zooms, a started tour walks the stops in order, half a scroll settles back,
// the ends hold. usage: node web/scripts/test_space3d_scroll.mjs <base url> [slug] [shots dir]
import assert from 'node:assert/strict'
import { resolve } from 'node:path'
import { chromium } from 'playwright-core'

const [BASE, SLUG = 'conga', SHOTS] = process.argv.slice(2)
const browser = await chromium.launch({
  executablePath: resolve(import.meta.dirname, '../../.cache/ms-playwright/chromium-1169/chrome-linux/chrome'),
  args: ['--use-angle=swiftshader', '--use-gl=angle', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'],
})
const page = await browser.newPage({ viewport: { width: 880, height: 540 }, bypassCSP: true })
const errors = []
page.on('pageerror', (e) => errors.push(e.message))
await page.goto(`${BASE}/space3d/viewer.html?place=${SLUG}`)
await page.waitForFunction(() => window.__ready === true, null, { timeout: 180000 })
await page.mouse.move(600, 200)

const step = () => page.textContent('#tour-step')
const idle = async () => {
  await page.waitForTimeout(400)
  await page.waitForFunction(() => !window.__tourBusy(), null, { timeout: 90000 })
}
const wheel = async (dy, times = 1) => {
  for (let i = 0; i < times; i++) {
    await page.mouse.wheel(0, dy)
    await page.waitForTimeout(60)
  }
}
const total = await page.evaluate(() => window.__hotspots.length)
const shot = (name) => (SHOTS ? page.screenshot({ path: `${SHOTS}/${name}.png`, timeout: 120000 }) : null)

// Overview: the wheel zooms, it does not start the tour.
const before = await page.evaluate(() => JSON.stringify(window.__viewState()))
await wheel(100, 3)
await page.waitForTimeout(800)
assert.equal(await page.evaluate(() => document.documentElement.classList.contains('is-touring')), false, 'wheel started the tour')
assert.notEqual(await page.evaluate(() => JSON.stringify(window.__viewState())), before, 'overview wheel no longer zooms')

await page.click('#tour-start')
await page.mouse.move(600, 200)
await idle()
assert.equal(await step(), `Điểm 1 / ${total}`)
assert.match(await page.textContent('#tour-guide-text'), /Lăn chuột xuống/)

// A small scroll settles back on the same stop.
await wheel(50)
await idle()
assert.equal(await step(), `Điểm 1 / ${total}`, 'small scroll left the stop')

// Scroll walks every stop, in order.
for (let i = 2; i <= total; i++) {
  await wheel(100, 3)
  if (i === 2) await shot('scroll-mid')
  await idle()
  assert.equal(await step(), `Điểm ${i} / ${total}`, `stop ${i}`)
}
assert.match(await page.textContent('#tour-guide-text'), /Điểm cuối/)
await shot('scroll-last')

// The end holds, and scrolling up walks back.
await wheel(100, 4)
await idle()
assert.equal(await step(), `Điểm ${total} / ${total}`)
await wheel(-100, 3)
await idle()
assert.equal(await step(), `Điểm ${total - 1} / ${total}`)

// A route dot still jumps; the overview button ends the tour.
await page.click('.tour-dot >> nth=1')
await idle()
assert.equal(await step(), `Điểm 2 / ${total}`)
await shot('scroll-dot')
await page.click('#tour-overview')
await idle()
assert.equal(await page.evaluate(() => document.documentElement.classList.contains('is-touring')), false)

// Back on the overview: the guide is there, and the wheel zooms and a drag turns the model again.
await page.waitForTimeout(700)
assert.equal(await page.isVisible('#view-guide'), true, 'overview guide hidden')
assert.equal(await page.evaluate(() => getComputedStyle(document.getElementById('view-guide')).opacity), '1')
await shot('overview-back')
const view = () => page.evaluate(() => JSON.stringify(window.__viewState()))
const start = await view()
await wheel(100, 3)
await page.waitForTimeout(1200)
const zoomed = await view()
assert.notEqual(zoomed, start, 'wheel does not zoom after the tour')
await page.mouse.move(500, 200)
await page.mouse.down()
await page.mouse.move(380, 230, { steps: 6 })
await page.mouse.up()
await page.waitForTimeout(1200)
assert.notEqual(await view(), zoomed, 'drag does not turn after the tour')
assert.deepEqual(errors, [])
console.log(`ok ${SLUG}: ${total} stops`)
await browser.close()
