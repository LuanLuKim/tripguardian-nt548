// Isolated browser fixture for an offered photo card (docs/TRIP_UNDERSTANDING.md §Luồng khám phá): after a pick the
// assistant offers the next aspect in words and its card waits folded under the reply (no stage opens by itself); a
// typed yes ("có") opens the stage like a tap, without a model call; the stage is headed by the card's label when the
// assistant wrote no question for it and holds as many cards as its line counts; a resumed chat keeps the card on the reply that offered it. No model or database
// calls. Usage: node scripts/test_understand_offer.mjs [base-url]
import assert from 'node:assert/strict'
import { mkdirSync } from 'node:fs'
import { resolve } from 'node:path'
import { chromium } from 'playwright-core'

const base = process.argv[2] ?? 'http://127.0.0.1:5173'
const out = resolve(import.meta.dirname, '../../frontend_images/chat-offer-2026-11-18')
mkdirSync(out, { recursive: true })
const required = ['trip', 'companions', 'mobility', 'care', 'pace', 'budget', 'lodging'].map(key => ({ key, label: key, done: false }))
const empty = () => ({ required, readback: null, purpose: null, trip: [], anchors: [], hard: [], soft: [], pace: null, max_leg_min: null, crowd_tolerance: null, novelty: null, budget_vnd: null, unknowns: [], unmapped: [], safety_pending: false, ready: false, missing: [], matching: 3208, total: 3208, board: { ids: [], vibe: [] }, vibes: [] })
const opt = (id, label, photo) => ({ id, label, description: '', prefilled: false, because: '', count: 40, photo: photo ? { url: photo, name: 'Nơi ' + label } : null, cues: [], places: [] })
const hills = { kind: 'deck', left: 7, total: 7, tabs: [{ qid: 'drill.ngắm đồi', kind: 'drill', header: 'Kiểu ngắm đồi', question: '', why: '', visual: true, multi: true, inputs: [],
  options: [opt('o0', 'Đồi thông xanh', '/img/home/pine.jpg'), opt('o1', 'Đồi hoa', '/img/home/cafe.jpg'), opt('o2', 'Hoàng hôn trên đồi', '/img/home/cloud.jpg'), opt('o3', 'Đi bộ lên đồi', '/img/home/lake.jpg'), opt('other', 'Khác'), opt('skip', 'Bỏ qua')] }] }
const block = { kind: 'tags', level: 'subtags', title: 'Các kiểu săn mây', sig: 'sig-cloud', axis: 'category', total: 24, other: 0, all: [], cards: [], criteria: {},
  subtags: [{ id: 'category:cafe', axis: 'category', label: 'Quán cà phê săn mây', count: 15, place_ids: [], cover: ['/img/home/cloud.jpg'] },
    { id: 'category:nature', axis: 'category', label: 'Đồi & điểm ngắm mây', count: 5, place_ids: [], cover: ['/img/home/pine.jpg'] },
    { id: 'category:camping', axis: 'category', label: 'Cắm trại, sáng dậy thấy mây', count: 4, place_ids: [], cover: ['/img/home/lake.jpg'] }] }
const offer = 'Ngồi giữa vườn cây, nhâm nhi ly cà phê nóng buổi sáng thì đúng chất sống chậm luôn! Quanh Đà Lạt còn mấy kiểu đồi ngắm cảnh đẹp lắm, bạn muốn xem thử không?'

const browser = await chromium.launch({ executablePath: resolve(import.meta.dirname, '../../.cache/ms-playwright/chromium-1169/chrome-linux/chrome'), args: ['--no-sandbox'] })
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  const errors = []
  page.on('pageerror', e => errors.push(e.message))
  page.on('console', m => { if (m.type() === 'error') errors.push(m.args().length ? m.text().slice(0, 1500) : m.text()) })
  const turns = []
  const journey = { id: 'offer', stage: 'trip', revision: 0, sessions: {}, outputs: {}, result: { id: 'offer', phase: 'chat', discovery: true, understanding: empty(), card: hills, transcript: [
    { role: 'user', text: 'Mình muốn sống chậm, ít điểm đến, nhiều quán cà phê đẹp.', turn: 1 },
    { role: 'agent', text: 'Đà Lạt mà sống chậm thì cà phê là nhất rồi.', turn: 1, kind: 'say' },
    { role: 'user', text: 'Kiểu quán cà phê: Sân vườn ngoài trời', turn: 2, kind: 'answer' },
    { role: 'agent', text: offer, turn: 2, kind: 'say' }] } }
  await page.route('**/data/*.json', r => r.fulfill({ json: r.request().url().endsWith('/photo_allow.json') ? {} : { places: [], stats: {} } }))
  await page.route('**/api/**', async route => {
    const req = route.request()
    const path = new URL(req.url()).pathname
    if (path === '/api/harness/me') return route.fulfill({ json: { id: 'offer-test', name: 'Ngọc Hương', guest: false, needs_consent: false, consents: {} } })
    if (path === '/api/harness/trips') return route.fulfill({ json: [{ id: 'cloud', stage: 'trip', revision: 0, days: null, title: 'Tui thích săn mây', people: null, start_date: null, places: [], confirmed: false, updated_at: new Date().toISOString() }, { id: 'offer', stage: 'trip', revision: 0, days: null, title: 'Mình muốn sống chậm', people: null, start_date: null, places: [], confirmed: false, updated_at: new Date().toISOString() }] })
    if (path === '/api/harness/sessions' && req.method() === 'POST') return route.fulfill({ json: { ...journey, id: 'fresh', result: { ...journey.result, id: 'fresh', transcript: [], card: null } } })
    if (path === '/api/harness/sessions/fresh') return route.fulfill({ json: { ...journey, id: 'fresh', result: { ...journey.result, id: 'fresh', transcript: [], card: null } } })
    if (path === '/api/harness/sessions/offer') return route.fulfill({ json: journey })
    if (path === '/api/harness/sessions/cloud') return route.fulfill({ json: { ...journey, id: 'cloud', result: { ...journey.result, id: 'cloud', card: null, transcript: [
      { role: 'user', text: 'Tui thích săn mây', turn: 1 }, { role: 'agent', text: 'Săn mây thì mê lắm luôn! Có mấy kiểu đây, bạn lướt thử nhé.', turn: 1, kind: 'say' },
      { role: 'agent', text: '', turn: 1, kind: 'block', block }] } } })
    if (path === '/api/harness/sessions/offer/request') { turns.push(req.postDataJSON().payload); return route.fulfill({ status: 500, json: {} }) }
    return route.fulfill({ json: {} })
  })

  // 1. The resumed chat: the offer and its folded card are one message; no stage covers the chat.
  await page.goto(base + '/app/understand')
  await page.locator('.tg-history__entry', { hasText: 'Mình muốn sống chậm' }).click()
  const reply = page.locator('.tg-cx__m.is-bot', { hasText: 'bạn muốn xem thử không?' })
  await reply.waitFor({ timeout: 20000 }).catch(async e => { console.log('page errors:', JSON.stringify(errors).slice(0, 3000)); throw e })
  await reply.locator('.tg-stage__reopen', { hasText: 'Kiểu ngắm đồi' }).waitFor()
  await page.waitForTimeout(600)
  assert.equal(await page.locator('.tg-stage__panel').count(), 0, 'the offered card does not open by itself')
  assert.equal(await page.locator('.tg-cx__say-ask').count(), 0, 'no stock question bubble')
  await page.screenshot({ path: resolve(out, 'offer-folded.png') })

  // 2. A typed yes opens the stage like a tap: no request, headed by the card's label.
  const box = page.getByRole('textbox', { name: 'Tin nhắn' })
  await box.fill('có')
  await box.press('Enter')
  const stage = page.locator('.tg-stage__panel')
  await stage.waitFor()
  assert.equal(await stage.locator('h3').innerText(), 'Kiểu ngắm đồi')
  assert.equal(await stage.locator('.tg-stage__card').count(), 4, 'the stage holds the 4 kinds its line counts, none twice')
  assert.equal(turns.length, 0, 'the yes made no model call')
  await page.waitForTimeout(500)
  await page.screenshot({ path: resolve(out, 'offer-open.png') })
  await page.keyboard.press('Escape')

  // 3. A tag stage counts what it shows: the chat line and the stage both say 3 kinds (Xem tất cả is not one of them).
  await page.locator('.tg-history__entry', { hasText: 'Tui thích săn mây' }).click()
  const row = page.locator('.tg-sub__row')
  await row.waitFor({ timeout: 20000 })
  assert.match(await row.innerText(), /3 kiểu/)
  await row.click()
  await page.locator('.tg-stage__panel').waitFor()
  await page.waitForTimeout(500)
  assert.match(await page.locator('.tg-stage__panel').innerText(), /3 kiểu · /)
  await page.screenshot({ path: resolve(out, 'tags-count.png') })
  assert.deepEqual(errors, [])
  console.log(`ok: offered card stays folded, a typed yes opens it (${out})`)
} finally {
  await browser.close()
}
