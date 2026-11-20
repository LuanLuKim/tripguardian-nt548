// Screenshots of the chat's clip stage (owner 20/11/2026): the reply's clip line, the stage (TikTok-like, ↑ ↓ / wheel), and
// "▶ N clip" on a place card of the photo stage, for review before production (RULE.md §0.2). Signs in with DEV_ACCOUNT_* from
// .env (never printed); the chat turn is a fixture stream whose clips block is the real place_clips result, built by
// trip.infrastructure.reads.Reads.clips over data/serving/clips/dalat.json (argv[3], JSON of trip.api.blocks.clips_block).
// Usage: node scripts/shots_clip_stage.mjs <vite-base-url> <clips_block.json>
import { mkdirSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { chromium } from 'playwright-core'

const base = process.argv[2] ?? 'http://127.0.0.1:5233'
const block = JSON.parse(readFileSync(process.argv[3], 'utf8'))
const out = resolve(import.meta.dirname, '../../frontend_images/clip-stage-2026-11-20')
mkdirSync(out, { recursive: true })
const env = Object.fromEntries(readFileSync(resolve(import.meta.dirname, '../../.env'), 'utf8').split('\n').filter((l) => /^[A-Z_]+=/.test(l)).map((l) => { const i = l.indexOf('='); return [l.slice(0, i), l.slice(i + 1).replace(/^["']|["']$/g, '')] }))
const browser = await chromium.launch({ executablePath: resolve(import.meta.dirname, '../../.cache/ms-playwright/chromium-1169/chrome-linux/chrome'), args: ['--no-sandbox', '--autoplay-policy=no-user-gesture-required'] })
const sse = (req, events) => events.map(([event, data]) => `data: ${JSON.stringify({ request_id: req.request_id, stage: req.stage, revision: req.expected_revision, event, data })}\n\n`).join('')
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
const errors = []
page.on('pageerror', (e) => errors.push(e.message))
const shot = async (name, wait = 900) => { await page.waitForTimeout(wait); await page.screenshot({ path: resolve(out, `${name}.png`) }); console.log('shot', name) }
let turn = 0
await page.route('**/api/**', async (route) => {
  const req = route.request()
  const path = new URL(req.url()).pathname
  if (req.method() === 'POST' && /\/api\/harness\/sessions\/[^/]+\/request$/.test(path)) {
    const body = req.postDataJSON()
    if (body.operation === 'trip' && body.payload?.kind === 'text') {
      const id = path.split('/')[4]
      const journey = await (await fetch(`http://127.0.0.1:8769/api/harness/sessions/${id}?view=0`, { headers: { cookie: (await page.context().cookies()).map((c) => `${c.name}=${c.value}`).join('; ') } })).json()
      turn++
      const events = turn === 1
        ? [['say', { replace: 'Săn mây ở Đa Phú thì đi từ 4 giờ 30 sáng, lên đỉnh trước bình minh. Mình để vài clip người đã đến bên dưới để bạn xem đường lên và mây thật nhé.' }], ['block', block]]
        : [['say', { replace: 'Hai nơi săn mây hợp với bạn nè, bấm để xem ảnh và clip.' }], ['places', { ids: block.cards.map((c) => c.id), why: 'Đồi săn mây buổi sớm', cards: block.cards }]]
      return route.fulfill({ status: 200, headers: { 'content-type': 'text/event-stream' }, body: sse(body, [...events, ['done', {}], ['journey', { ...journey, stage: 'decision', result: {} }]]) })
    }
  }
  return route.continue({ headers: { ...req.headers(), origin: 'http://127.0.0.1:8769' } })
})
try {
  await page.goto(base + '/app', { waitUntil: 'load' })
  const email = page.locator('input[type=email]')
  if (await email.waitFor({ timeout: 15000 }).then(() => true, () => false)) {
    await email.fill(env.DEV_ACCOUNT_EMAIL)
    await page.locator('input[type=password]').first().fill(env.DEV_ACCOUNT_PASSWORD)
    await page.locator('input[type=password]').first().press('Enter')
  }
  await page.locator('.tg-hm__go').waitFor({ timeout: 30000 })
  await page.evaluate(async () => { const me = await (await fetch('/api/harness/me')).json(); localStorage.setItem(`tg-tour-seen:${me.id}`, '1'); localStorage.removeItem('tg.trip.v1') })
  await page.reload({ waitUntil: 'load' })
  await page.locator('.tg-drop__bar').waitFor({ timeout: 30000 })
  await page.waitForTimeout(1200)
  if (!(await page.locator('.tg-drop.is-open').count())) await page.locator('.tg-drop__bar').click()
  await page.locator('#tg-asst-in').fill('Đồi Đa Phú săn mây thế nào?')
  await page.locator('#tg-asst-in').press('Enter')
  await page.locator('.tg-clips__open').waitFor({ timeout: 60000 })
  await shot('01-chat-clip-line')
  await page.locator('.tg-clips__open').click()
  await page.locator('.tg-cs').waitFor()
  await shot('02-clip-stage', 4500)
  await page.mouse.move(720, 450)
  await page.mouse.wheel(0, 120)
  await shot('03-clip-stage-next', 4500)
  await page.locator('.tg-cs__like').click()
  await page.locator('.tg-cs__tap').click()
  await shot('04-liked-paused', 1200)
  await page.setViewportSize({ width: 412, height: 860 })
  await shot('05-clip-stage-phone', 2500)
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.keyboard.press('Escape')
  await page.waitForTimeout(600)
  // the photo stage of places: "▶ N clip" on a card opens that place's clips over it
  await page.locator('#tg-asst-in').fill('Gợi ý chỗ săn mây')
  await page.locator('#tg-asst-in').press('Enter')
  await page.locator('.tg-stage__reopen:not(.tg-clips__open)').last().waitFor({ timeout: 60000 })
  await page.locator('.tg-stage__reopen:not(.tg-clips__open)').last().click()
  await page.locator('.tg-stage__clips').first().waitFor({ timeout: 10000 })
  await shot('06-photo-stage-clip-chip')
  await page.locator('.tg-stage__card.is-front .tg-stage__clips').click()
  await page.locator('.tg-cs').waitFor()
  await shot('07-place-clips-over-photo-stage', 4000)
  await page.keyboard.press('Escape')
  await page.waitForTimeout(700)
  console.log('photo stage still open and blurred:', await page.locator('.tg-stage__ring').count(), await page.evaluate(() => document.documentElement.classList.contains('tg-stage-open')))
} finally {
  if (errors.length) console.log('page errors:', errors.slice(0, 5).join(' | ').slice(0, 1500))
  await browser.close()
}
