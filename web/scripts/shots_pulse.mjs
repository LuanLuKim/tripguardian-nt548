// Screenshots of the home rail's Nhịp Đà Lạt bulletin in five states: with data (hot, season, expanded), stale, one section,
// and empty (the old "Top xu hướng" block stays). The account and the pulse call are answered from mocks, every other
// /api call gets an empty answer: no sign-in and no harness restart needed.
// usage: node web/scripts/shots_pulse.mjs <base url> <bulletin.json> [out dir]
import { mkdirSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { chromium } from 'playwright-core'

const [BASE, FILE, OUT = resolve(import.meta.dirname, '../../frontend_images')] = process.argv.slice(2)
mkdirSync(OUT, { recursive: true })
const exe = resolve(import.meta.dirname, '../../.cache/ms-playwright/chromium-1169/chrome-linux/chrome')
const browser = await chromium.launch({ executablePath: exe })
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
const errors = []
page.on('pageerror', (e) => errors.push(e.message))
const bulletin = JSON.parse(readFileSync(FILE, 'utf8'))
let serve = bulletin
const me = { id: 'a'.repeat(32), email: 'xem@test.local', name: 'Khách xem thử', avatar: null, nickname: 'xemthu', bio: '', guest: false, role: 'user',
  home_city: null, usual_mobility: null, usual_companions: null, consents: {}, needs_consent: false }
const json = (r, body) => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
await page.route('**/api/**', (r) => {
  const path = new URL(r.request().url()).pathname
  if (path === '/api/harness/pulse') return json(r, serve)
  if (path === '/api/harness/me') return json(r, me)
  if (path === '/api/harness/friends') return json(r, { friends: [], incoming: [], outgoing: [] })
  if (path === '/api/harness/me/library') return json(r, { saved: [], recent: [] })
  if (path === '/api/harness/events') return r.fulfill({ status: 204 })
  return json(r, [])
})
const open = async (wait) => {
  await page.goto(BASE + '/app', { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('.tg-hm', { timeout: 60000 })
  if (wait) await page.waitForSelector('.tg-pulse', { timeout: 20000 })
  await page.waitForTimeout(1000)
}
try {
  await open(true)
  await page.screenshot({ path: `${OUT}/pulse-home-hot.png` })
  await page.locator('.tg-pulse__tab', { hasText: 'Mùa đang diễn ra' }).click()
  await page.waitForTimeout(900)
  await page.screenshot({ path: `${OUT}/pulse-home-season.png` })
  await page.locator('.tg-pulse__tab').first().click()
  await page.locator('.tg-pulse__more').click()
  await page.waitForTimeout(900)
  await page.screenshot({ path: `${OUT}/pulse-home-more.png` })
  serve = { ...bulletin, stale: true, day: '2026-10-22' }
  await open(true)
  await page.screenshot({ path: `${OUT}/pulse-home-stale.png` })
  serve = { ...bulletin, sections: bulletin.sections.filter((x) => x.kind === 'event') }
  await open(true)
  await page.screenshot({ path: `${OUT}/pulse-home-one-section.png` })
  serve = { ...bulletin, sections: [] }
  await open(false)
  console.log('empty: pulse blocks', await page.locator('.tg-pulse').count(), '| old trend items', await page.locator('.tg-hm__idea').count())
  await page.screenshot({ path: `${OUT}/pulse-home-empty-fallback.png` })
} catch (e) {
  console.log('FAILED', String(e).split('\n')[0])
  await page.screenshot({ path: `${OUT}/pulse-failure.png` })
} finally {
  console.log(errors.length ? errors.join('\n') : 'no page errors')
  await browser.close()
}
