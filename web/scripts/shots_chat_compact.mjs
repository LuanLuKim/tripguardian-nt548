// Screenshots of the home chat panel when empty (fits its welcome), after the first message (full height) and after
// "Trò chuyện mới" (back to the welcome; the trip stays), at two window sizes,
// for review before production (RULE.md §0.2). Signs in with DEV_ACCOUNT_* from .env (never printed); the chat turn is a fixture
// stream so the shot works while the harness runs older code. Usage: node scripts/shots_chat_compact.mjs [vite-base-url]
import { mkdirSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { chromium } from 'playwright-core'

const base = process.argv[2] ?? 'http://127.0.0.1:5233'
const out = resolve(import.meta.dirname, '../../frontend_images/chat-compact-2026-11-20')
mkdirSync(out, { recursive: true })
const env = Object.fromEntries(readFileSync(resolve(import.meta.dirname, '../../.env'), 'utf8').split('\n').filter((l) => /^[A-Z_]+=/.test(l)).map((l) => { const i = l.indexOf('='); return [l.slice(0, i), l.slice(i + 1).replace(/^["']|["']$/g, '')] }))
const browser = await chromium.launch({ executablePath: resolve(import.meta.dirname, '../../.cache/ms-playwright/chromium-1169/chrome-linux/chrome'), args: ['--no-sandbox'] })
const sse = (req, events) => events.map(([event, data]) => `data: ${JSON.stringify({ request_id: req.request_id, stage: req.stage, revision: req.expected_revision, event, data })}\n\n`).join('')

for (const [w, h] of [[1440, 900], [1280, 760]]) {
  const page = await browser.newPage({ viewport: { width: w, height: h } })
  const errors = []
  page.on('pageerror', (e) => errors.push(e.message))
  const shot = async (name) => { await page.waitForTimeout(900); await page.screenshot({ path: resolve(out, `${name}-${w}.png`) }); console.log('shot', name, w) }
  await page.route('**/api/**', async (route) => {
    const req = route.request()
    const path = new URL(req.url()).pathname
    if (req.method() === 'POST' && /\/api\/harness\/sessions\/[^/]+\/request$/.test(path)) {
      const body = req.postDataJSON()
      if (body.operation === 'trip' && body.payload?.kind === 'text') {
        const id = path.split('/')[4]
        const journey = await (await fetch(`http://127.0.0.1:8769/api/harness/sessions/${id}?view=0`, { headers: { cookie: (await page.context().cookies()).map((c) => `${c.name}=${c.value}`).join('; ') } })).json()
        return route.fulfill({ status: 200, headers: { 'content-type': 'text/event-stream' }, body: sse(body, [
          ['say', { replace: 'Cuối tháng này Đà Lạt vui lắm nè! Quảng trường Lâm Viên có Diễu hành áo dài, còn Mây Lang Thang có đêm nhạc ngày 27/11. Bạn muốn mình thêm nơi nào vào chuyến không?' }],
          ['replies', { options: ['Thêm Mây Lang Thang', 'Yên tĩnh hơn'] }],
          ['done', {}],
          ['journey', { ...journey, stage: 'decision', result: {} }],
        ]) })
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
    await page.waitForTimeout(1500)
    if (!(await page.locator('.tg-drop.is-open').count())) await page.locator('.tg-drop__bar').click()
    await shot('01-home-chat-empty')
    const box = await page.locator('.tg-drop__panel').boundingBox()
    console.log('empty panel height', Math.round(box.height), 'of window', h)
    await page.locator('#tg-asst-in').fill('Tháng này có lễ hội gì không?')
    await page.locator('#tg-asst-in').press('Enter')
    await page.locator('.tg-cx__m.is-bot .tg-cx__say').first().waitFor({ timeout: 60000 })
    await shot('02-home-chat-first-message')
    console.log('chat panel height', Math.round((await page.locator('.tg-drop__panel').boundingBox()).height))
    const fresh = page.locator('.tg-drop__panel .tg-asst__new')
    await fresh.hover()
    await page.locator('.tg-drop__panel .tg-asst__head').screenshot({ path: resolve(out, `03-header-new-chat-${w}.png`) })
    const sent = page.waitForRequest((r) => r.method() === 'POST' && r.url().endsWith('/request') && r.postDataJSON()?.operation === 'new_chat')
    await fresh.click()
    console.log('new_chat sent', JSON.stringify((await sent).postDataJSON().payload))
    await page.locator('.tg-tchat__welcome').waitFor({ timeout: 5000 })
    await shot('04-after-new-chat')
    console.log('after new chat height', Math.round((await page.locator('.tg-drop__panel').boundingBox()).height), 'button disabled', await fresh.isDisabled())
    await page.locator('.tg-drop__panel .tg-asst__head').screenshot({ path: resolve(out, `05-header-empty-${w}.png`) })
    // Lựa chọn: the same header in the chat pinned beside the grid (the narrowest panel)
    await page.goto(base + '/app/explore', { waitUntil: 'load' })
    await page.locator('.tg-grid [data-place]').first().waitFor({ timeout: 90000 })
    if (!(await page.locator('.tg-drop.is-open').count())) await page.locator('.tg-drop__bar').click()
    await page.locator('.tg-drop__panel button[aria-label="Ghim cạnh danh sách"]').click()
    await page.locator('.tg-asst.is-pinned').waitFor({ timeout: 5000 })
    await shot('06-explore-pinned')
    await page.locator('.tg-asst.is-pinned .tg-asst__head').screenshot({ path: resolve(out, `07-pinned-header-${w}.png`) })
    await page.locator('.tg-asst.is-pinned button[aria-label="Bỏ ghim"]').click()
  } finally {
    if (errors.length) console.log('page errors:', errors.slice(0, 5).join(' | ').slice(0, 1500))
    await page.close()
  }
}
await browser.close()
