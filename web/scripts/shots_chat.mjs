// Screenshots of the one chat (home page + Lựa chọn), the "Khám phá nơi muốn đến" tag picker, the "Xem chi tiết lịch trình" way to the
// schedule, Trending events and the TikTok Video tab, for review before production (RULE.md §0.2). Signs in with DEV_ACCOUNT_* from .env
// (never printed) against the running harness; only the chat turns themselves (decision.trip with a typed message) are answered by a
// fixture stream, so the shots work while the harness runs older code. Usage: node scripts/shots_chat.mjs [vite-base-url]
import { mkdirSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { chromium } from 'playwright-core'

const base = process.argv[2] ?? 'http://127.0.0.1:5233'
const out = resolve(import.meta.dirname, '../../frontend_images/one-chat-2026-11-19')
mkdirSync(out, { recursive: true })
const env = Object.fromEntries(readFileSync(resolve(import.meta.dirname, '../../.env'), 'utf8').split('\n').filter((l) => /^[A-Z_]+=/.test(l)).map((l) => { const i = l.indexOf('='); return [l.slice(0, i), l.slice(i + 1).replace(/^["']|["']$/g, '')] }))
const snap = JSON.parse(readFileSync(resolve(import.meta.dirname, '../public/data/snapshot-lite.json'), 'utf8'))
const named = (q) => snap.places.find((p) => p.name === q)
const cards = ['Đồi Đa Phú', 'Quảng trường Lâm Viên', 'Mây Lang Thang', 'Hồ Xuân Hương', 'Thiền viện Trúc Lâm', 'Ga Đà Lạt'].map(named).filter(Boolean)
  .map((p) => ({ id: p.id, name: p.name, category: p.category, area: null, rating: p.rating ?? null, reviews: p.reviewCount ?? null, photos: [], hours_today: null, price: null, liked: false }))

const browser = await chromium.launch({ executablePath: resolve(import.meta.dirname, '../../.cache/ms-playwright/chromium-1169/chrome-linux/chrome'), args: ['--no-sandbox'] })
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
const errors = []
page.on('pageerror', (e) => errors.push(e.message))
if (process.env.DEBUG) { page.on('console', (m) => console.log('console', m.type(), m.text().slice(0, 300))); page.on('response', (r) => { if (r.url().includes('/api/harness/sessions')) console.log('res', r.status(), r.request().method(), new URL(r.url()).pathname) }) }
const shot = async (name) => { await page.waitForTimeout(700); await page.screenshot({ path: resolve(out, `${name}.png`) }); console.log('shot', name) }

// The harness checks Origin against its own host; Vite's proxy changes Host only.
const sse = (req, events) => events.map(([event, data]) => `data: ${JSON.stringify({ request_id: req.request_id, stage: req.stage, revision: req.expected_revision, event, data })}\n\n`).join('')
await page.route('**/api/**', async (route) => {
  const req = route.request()
  const path = new URL(req.url()).pathname
  if (req.method() === 'POST' && /\/api\/harness\/sessions\/[^/]+\/request$/.test(path)) {
    const body = req.postDataJSON()
    if (body.stage === 'planning' && body.operation === 'trip' && body.payload?.kind === 'text') {
      const id = path.split('/')[4]
      const journey = await (await fetch(`http://127.0.0.1:8769/api/harness/sessions/${id}?view=0`, { headers: { cookie: (await page.context().cookies()).map((c) => `${c.name}=${c.value}`).join('; ') } })).json()
      return route.fulfill({ status: 200, headers: { 'content-type': 'text/event-stream' }, body: sse(body, [
        ['say', { replace: 'Xong rồi nè! Mình dời Đồi Đa Phú sang sáng ngày 2 để kịp săn mây, ngày 1 nhẹ nhàng hơn.' }],
        ['view', { view: null, diff: { days: [{ day: 2, stops: cards.slice(0, 3).map((c, i) => ({ id: c.id, start: ['05:30', '09:00', '11:30'][i], name: c.name })) }] } }],
        ['done', {}],
        ['journey', { ...journey, stage: 'planning', result: {} }],
      ]) })
    }
    if (body.stage === 'decision' && body.operation === 'trip' && body.payload?.kind === 'text') {
      const id = path.split('/')[4]
      const journey = await (await fetch(`http://127.0.0.1:8769/api/harness/sessions/${id}?view=0`, { headers: { cookie: (await page.context().cookies()).map((c) => `${c.name}=${c.value}`).join('; ') } })).json()
      const text = body.payload.text
      const say = /sự kiện|lễ hội/i.test(text)
        ? 'Cuối tháng này Đà Lạt vui lắm nè! Quảng trường Lâm Viên có Diễu hành áo dài đến 20/11, còn Mây Lang Thang có đêm nhạc Bạch Công Khanh – Dương Edward ngày 27/11. Bạn muốn mình thêm nơi nào vào chuyến không?'
        : 'Săn mây buổi sớm thì Đồi Đa Phú là chuẩn bài, còn chiều muộn ghé quảng trường dạo chơi. Mình để vài nơi hợp gu bên dưới, bấm tim là thêm vào chuyến nhé!'
      return route.fulfill({ status: 200, headers: { 'content-type': 'text/event-stream' }, body: sse(body, [
        ['progress', { steps: [{ id: 'read', label: 'Đọc tin nhắn', status: 'done' }, { id: 'places', label: 'Tìm nơi hợp gu', status: 'done' }] }],
        ['say', { replace: say }],
        ['places', { ids: cards.map((c) => c.id), why: '', cards }],
        ['replies', { options: ['Thêm Đồi Đa Phú', 'Yên tĩnh hơn', 'Có quán cà phê săn mây nào?'] }],
        ['done', {}],
        ['journey', { ...journey, stage: 'decision', result: {} }],
      ]) })
    }
  }
  return route.continue({ headers: { ...req.headers(), origin: 'http://127.0.0.1:8769' } })
})

try {
  await page.goto(base + '/app', { waitUntil: 'load' })
  await page.locator('input[type=email]').waitFor({ timeout: 30000 })
  await page.locator('input[type=email]').fill(env.DEV_ACCOUNT_EMAIL)
  await page.locator('input[type=password]').first().fill(env.DEV_ACCOUNT_PASSWORD)
  await page.locator('input[type=password]').first().press('Enter')
  await page.locator('.tg-hm__go').waitFor({ timeout: 30000 })
  // the mascot tour covers the page on a first visit: mark it seen for this account and reload
  await page.evaluate(async () => { const me = await (await fetch('/api/harness/me')).json(); localStorage.setItem(`tg-tour-seen:${me.id}`, '1') })
  await page.reload({ waitUntil: 'load' })
  await page.locator('.tg-hm__go').waitFor({ timeout: 30000 })
  await page.waitForTimeout(2500)
  await shot('01-home-button-and-chat-tab')

  // Trending events: tidied names, a picture for every row
  const events = page.locator('.tg-pulse').first()
  if (await events.isVisible().catch(() => false)) await events.screenshot({ path: resolve(out, '02-trending-events.png') })

  // The home chat: same panel as Lựa chọn
  await page.locator('.tg-drop__bar').click()
  await shot('03-home-chat-open')
  // with no trip on screen the first message starts one, and the answer comes on the home page
  await page.evaluate(() => localStorage.removeItem('tg.trip.v1'))
  await page.reload({ waitUntil: 'load' })
  await page.locator('.tg-drop__bar').waitFor({ timeout: 30000 })
  await page.waitForTimeout(800)
  if (!(await page.locator('.tg-drop.is-open').count())) await page.locator('.tg-drop__bar').click() // the chat may still be open from before
  await page.locator('#tg-asst-in').fill('Tháng này có lễ hội gì không?')
  await page.locator('#tg-asst-in').press('Enter')
  await page.locator('.tg-cx__m.is-bot .tg-cx__say').first().waitFor({ timeout: 60000 }).catch(async (e) => { await shot('debug-home-first'); console.log('notice:', await page.locator('.tg-tchat .tg-alert').textContent().catch(() => null)); throw e })
  await shot('03b-home-chat-first-message')
  await page.keyboard.press('Escape')

  // "Khám phá nơi muốn đến": tags to tap
  await page.locator('.tg-hm__go').click()
  await page.locator('.tg-tags-pick').waitFor()
  await page.locator('.tg-tags-pick__grid button').nth(0).click()
  await page.locator('.tg-tags-pick__grid button').nth(1).click()
  await page.locator('.tg-tags-pick__who button').nth(2).click()
  await shot('04-tag-picker')
  await page.locator('.tg-tags-pick__go .tg-btn--primary').click()

  // Lựa chọn opens straight away; the picks are the chat's first message
  await page.waitForURL('**/app/explore', { timeout: 20000 })
  await page.locator('.tg-grid [data-place]').first().waitFor({ timeout: 90000 })
  await page.locator('.tg-cx__m.is-bot').first().waitFor({ timeout: 30000 })
  await shot('05-explore-chat-first-message')
  await page.locator('#tg-asst-in').fill('Tháng này có sự kiện gì vui không?')
  await page.locator('#tg-asst-in').press('Enter')
  await page.waitForTimeout(1500)
  await shot('06-explore-chat-answer')
  // a photo card of the reply opens the big photo stage at that place
  const card = page.locator('.tg-pstrip__open').nth(1)
  if (await card.isVisible().catch(() => false)) { await card.click(); await page.waitForTimeout(1200); await shot('06b-chat-card-photo-stage'); await page.keyboard.press('Escape'); await page.waitForTimeout(600) }
  await page.keyboard.press('Escape')

  // Pick three places, open the map: "Xem chi tiết lịch trình" on the map and in the notch
  const adds = page.locator('.tg-grid [data-place] button', { hasText: /^\s*Thêm\s*$/ })
  for (let i = 0; i < 3; i++) { await adds.nth(i).click().catch(() => {}); await page.waitForTimeout(500) }
  await page.locator('.tg-notch button', { hasText: 'Bản đồ lịch trình' }).click()
  await page.locator('.tg-split').waitFor()
  await page.waitForTimeout(6000)
  await shot('07-explore-map-see-schedule')
  const full = page.locator('.tg-split__full')
  if (await full.isVisible().catch(() => false)) {
    await full.click()
    await page.waitForURL('**/app/plan', { timeout: 60000 }).catch(() => {})
    await page.waitForTimeout(8000)
    await shot('10-schedule-from-map')
    // the same chat on Lịch trình: an edit goes to the schedule's assistant, the changed day is listed under the reply
    await page.locator('.tg-drop__bar').click()
    await page.locator('#tg-asst-in').fill('Dời Đồi Đa Phú sang ngày 2')
    await page.locator('#tg-asst-in').press('Enter')
    await page.waitForTimeout(2500)
    await shot('10b-plan-chat-edit')
    await page.keyboard.press('Escape')
    const up = page.locator('.tg-it-crumb__up')
    if (await up.isVisible().catch(() => false)) { await up.click(); await page.waitForURL('**/app/explore', { timeout: 30000 }).catch(() => {}); await page.waitForTimeout(2500); await shot('11-back-to-schedule-map') }
  }

  // A place with TikTok clips: the Video tab plays them in TikTok's player, posters from our frames
  const withClips = snap.places.find((p) => p.name === 'Mây Lang Thang') ?? snap.places[0]
  await page.goto(base + `/app/explore?place=${encodeURIComponent(withClips.id)}`, { waitUntil: 'load' })
  const tab = page.getByRole('tab', { name: 'Video' })
  await tab.waitFor({ timeout: 30000 })
  await tab.click()
  await shot('08-place-video-tab')
  await page.locator('.tg-ps__cplay').first().click()
  await page.waitForTimeout(2500)
  await shot('09-clip-viewer')
} finally {
  if (errors.length) console.log('page errors:', errors.slice(0, 5).join(' | ').slice(0, 1500))
  await browser.close()
}
