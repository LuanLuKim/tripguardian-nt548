// Isolated browser fixtures for the exploring chat (docs/TRIP_UNDERSTANDING.md §11, §19): the open question as a sheet over
// the blurred chat (Để sau folds it, a tap brings it back, a taste question takes several answers), switching chats from the
// history list (the list stays mounted, no welcome flash), plain history titles, and Xong on the tag stage telling the
// assistant what was kept. No model or database calls. Usage: node scripts/test_understand_explore.mjs [base-url]
import assert from 'node:assert/strict'
import { mkdirSync } from 'node:fs'
import { resolve } from 'node:path'
import { chromium } from 'playwright-core'

const base = process.argv[2] ?? 'http://127.0.0.1:5173'
const out = resolve(import.meta.dirname, '../../frontend_images')
mkdirSync(out, { recursive: true })
const required = ['trip', 'companions', 'mobility', 'care', 'pace', 'budget', 'lodging'].map(key => ({ key, label: key, done: false }))
const empty = () => ({ required, readback: null, purpose: null, trip: [], anchors: [], hard: [], soft: [], pace: null, max_leg_min: null, crowd_tolerance: null, novelty: null, budget_vnd: null, unknowns: [], unmapped: [], safety_pending: false, ready: false, missing: [], matching: 3208, total: 3208, board: { ids: [], vibe: [] }, vibes: [] })
const opt = (id, label, description) => ({ id, label, description, prefilled: false, because: '', count: 40, photo: null, cues: [], places: [] })
const exits = [opt('other', 'Khác', ''), opt('skip', 'Bỏ qua', '')]
const taste = { kind: 'deck', left: 7, total: 7, tabs: [{ qid: 'agent.cafe', kind: 'agent', header: 'Kiểu quán', question: 'Ngồi cà phê ở Đà Lạt, bạn mê không khí nào?', why: 'Vì bạn nói “muốn sống chậm”.', visual: false, multi: true, inputs: [],
  options: [opt('o0', 'Yên tĩnh, ít người', 'Mình ưu tiên nơi ít ồn.'), opt('o1', 'Có nhạc sống', 'Mình ưu tiên nơi có nhạc sống.'), opt('o2', 'View đồi thông', 'Mình ưu tiên nơi có view đẹp.'), ...exits] }] }
const photo = '/img/home/cloud.jpg'
const block = { kind: 'tags', level: 'subtags', title: 'Các kiểu săn mây', sig: 'sig-cloud', axis: 'category', total: 24, other: 0, all: [], cards: [], criteria: { must: [['cloud_hunting', 'present']] },
  subtags: [{ id: 'category:cafe', axis: 'category', label: 'Quán cà phê săn mây', count: 15, place_ids: [], cover: [photo] },
    { id: 'category:nature', axis: 'category', label: 'Đồi & điểm ngắm mây', count: 5, place_ids: [], cover: ['/img/home/pine.jpg'] },
    { id: 'category:camping', axis: 'category', label: 'Cắm trại, sáng dậy thấy mây', count: 4, place_ids: [], cover: ['/img/home/lake.jpg'] }] }
const vibes = { sig: 'sig-cloud', ref: 'category:cafe', label: 'Quán cà phê săn mây', count: 15, wished: false, nodes: [
  { ref: 'category:cafe/experience:sunset_view', kind: 'subtag', label: 'Quán cà phê ngắm hoàng hôn', count: 5, cover: photo, has_children: true },
  { ref: 'category:cafe/experience:flower_garden', kind: 'subtag', label: 'Quán cà phê có vườn hoa', count: 5, cover: '/img/home/cafe.jpg', has_children: true },
  { ref: 'category:cafe/experience:live_music', kind: 'subtag', label: 'Quán cà phê có nhạc sống', count: 5, cover: '/img/home/lake.jpg', has_children: true },
  { ref: 'category:cafe/*', kind: 'all', label: 'Xem tất cả', count: 15, cover: photo, has_children: true }] }

const browser = await chromium.launch({ executablePath: resolve(import.meta.dirname, '../../.cache/ms-playwright/chromium-1169/chrome-linux/chrome'), args: ['--no-sandbox'] })
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  const errors = []
  page.on('pageerror', e => errors.push(e.message))
  const turns = []
  const sessions = new Map()
  const days = n => new Date(Date.now() - n * 86_400_000).toISOString()
  const make = (id, transcript, card = null) => ({ id, stage: 'trip', revision: 0, sessions: {}, outputs: {}, result: { id, transcript, card, phase: 'chat', discovery: true, understanding: empty() } })
  const said = (n, me, bot) => [{ role: 'user', text: me, turn: n }, { role: 'agent', text: bot, turn: n, kind: 'say' }]
  sessions.set('ask', make('ask', said(1, 'Mình muốn sống chậm, ngồi cà phê', 'Sống chậm ở Đà Lạt thì cà phê là chuẩn rồi.'), taste))
  sessions.set('cloud', make('cloud', [...said(1, 'Tui thích săn mây', 'Săn mây có mấy kiểu: quán cà phê, đồi và cắm trại, bạn lướt xem nhé.'), { role: 'agent', text: '', turn: 1, kind: 'block', block }]))
  for (let i = 0; i < 14; i++) sessions.set(`old${i}`, make(`old${i}`, said(1, `Chuyến cũ số ${i}`, 'Ừ, mình nhớ rồi.')))
  const title = id => sessions.get(id).result.transcript[0]?.text ?? null
  const summaries = () => [...sessions.keys()].map((id, i) => ({ id, stage: 'trip', revision: 0, days: null, title: title(id), people: null, start_date: null, places: [], confirmed: false, updated_at: days(id.startsWith('old') ? 10 + i : 0) }))
  let slow = 0 // ms a session read waits: the chat column must show its loading shape meanwhile, never the welcome canvas
  await page.route('**/data/*.json', r => r.fulfill({ json: r.request().url().endsWith('/photo_allow.json') ? {} : { places: [], stats: {} } }))
  await page.route('**/api/**', async route => {
    const req = route.request()
    const path = new URL(req.url()).pathname
    if (path === '/api/harness/me') return route.fulfill({ json: { id: 'explore-test', name: 'Ngọc Hương', guest: false, needs_consent: false, consents: {} } })
    if (path === '/api/harness/trips') return route.fulfill({ json: summaries() })
    if (path === '/api/harness/sessions' && req.method() === 'POST') {
      const id = `new-${sessions.size}`
      sessions.set(id, make(id, []))
      return route.fulfill({ json: sessions.get(id) })
    }
    if (/\/read\/trip\/stage$/.test(path)) return route.fulfill({ json: vibes })
    const match = path.match(/^\/api\/harness\/sessions\/([^/]+)(\/request)?$/)
    if (match) {
      const journey = sessions.get(match[1])
      if (!journey) return route.fulfill({ status: 404, json: {} })
      if (!match[2]) {
        if (slow) await new Promise(r => setTimeout(r, slow))
        return route.fulfill({ json: journey })
      }
      const input = req.postDataJSON()
      turns.push(input.payload)
      journey.revision++
      const reply = input.payload.kind === 'explored' ? 'Có vẻ bạn mê ngồi cà phê ngắm mây; sáng sớm thử thêm đồi ngắm bình minh nhé.' : input.payload.kind === 'deck' ? 'Có vẻ bạn thích quán yên, có nhạc nhẹ.' : ''
      journey.result.card = null
      const events = [...(reply ? [['say', { delta: reply }]] : []), ['state', { understanding: empty() }], ['card', null], ['journey', journey]]
      return route.fulfill({ contentType: 'text/event-stream', body: events.map(([event, data]) => `data: ${JSON.stringify({ event, data, stage: input.stage, revision: journey.revision, request_id: input.request_id })}\n\n`).join('') })
    }
    return route.fulfill({ json: {} })
  })

  // 1. Old chats read as plainly as new ones: no blur, no fading mask.
  await page.goto(base + '/app/understand')
  await page.getByRole('complementary', { name: 'Lịch sử chat' }).getByText('Chuyến cũ số 13').waitFor({ timeout: 20000 })
  const looks = await page.locator('.tg-history__entry strong').evaluateAll(els => els.map(e => [getComputedStyle(e).filter, getComputedStyle(e).maskImage || getComputedStyle(e).webkitMaskImage]))
  assert.ok(looks.length >= 16 && looks.every(([filter, mask]) => filter === 'none' && (!mask || mask === 'none')), `history titles are plain: ${JSON.stringify(looks.slice(0, 3))}`)
  const list = page.locator('.tg-history__list')
  assert.equal(await list.evaluate(e => getComputedStyle(e).maskImage || getComputedStyle(e).webkitMaskImage), 'none')

  // 2. Switching: the history column is the same element (not rebuilt, its scroll holds) and the welcome canvas never shows.
  await list.evaluate(e => { e.dataset.mark = 'kept'; e.scrollTop = 200 })
  const top = await list.evaluate(e => e.scrollTop)
  slow = 700
  await page.locator('.tg-history__entry', { hasText: 'Mình muốn sống chậm' }).click()
  await page.locator('.tg-cx__loading').waitFor()
  assert.equal(await page.getByRole('heading', { name: /Chào Ngọc Hương/ }).count(), 0, 'no welcome flash while a chat opens')
  await page.screenshot({ path: resolve(out, 'understand-switch-loading.png') })
  await page.getByText('Sống chậm ở Đà Lạt thì cà phê là chuẩn rồi.').waitFor()
  assert.equal(await list.evaluate(e => e.dataset.mark), 'kept', 'the history list was not rebuilt')
  assert.equal(await list.evaluate(e => e.scrollTop), top, 'the history list kept its scroll')
  slow = 0

  // 3. The open question floats over the blurred chat; several answers; Để sau folds it to a line; a tap brings it back.
  const sheet = page.getByRole('dialog', { name: 'Ngồi cà phê ở Đà Lạt, bạn mê không khí nào?' })
  await sheet.waitFor()
  assert.equal(await page.locator('.tg-asks__veil').count(), 1)
  assert.ok((await page.locator('.tg-asks__veil').evaluate(e => getComputedStyle(e).backdropFilter)).includes('blur'), 'the chat behind is blurred')
  await page.waitForTimeout(400)
  await page.screenshot({ path: resolve(out, 'understand-ask-sheet.png') })
  await sheet.getByRole('button', { name: /Để sau/ }).click()
  await sheet.waitFor({ state: 'hidden' })
  await page.locator('.tg-asks__pill').waitFor()
  assert.equal(await page.locator('.tg-asks__veil').count(), 0)
  assert.ok(await page.getByRole('textbox', { name: 'Tin nhắn' }).isEnabled(), 'the user can keep typing')
  await page.screenshot({ path: resolve(out, 'understand-ask-later.png') })
  await page.locator('.tg-asks__pill').click()
  await sheet.waitFor()
  await page.keyboard.press('Escape')
  await sheet.waitFor({ state: 'hidden' })
  await page.locator('.tg-asks__pill').click()
  await sheet.getByRole('button', { name: /Yên tĩnh, ít người/ }).click()
  await sheet.getByRole('button', { name: /Có nhạc sống/ }).click()
  await page.waitForTimeout(250)
  await page.screenshot({ path: resolve(out, 'understand-ask-multi.png') })
  await sheet.getByRole('button', { name: 'Gửi', exact: true }).click()
  await page.getByText('Có vẻ bạn thích quán yên, có nhạc nhẹ.').waitFor()
  const deckTurn = turns.at(-1)
  assert.equal(deckTurn.kind, 'deck')
  assert.deepEqual(deckTurn.answers['agent.cafe'], ['o0', 'o1'], 'two readings of one taste go together')
  assert.equal(await page.locator('.tg-asks, .tg-asks__pill').count(), 0, 'an answered question leaves no sheet')

  // 4. The tag stage: a kind opens its vibes; Xong with a kept kind tells the assistant once, and it answers with a new direction.
  await page.locator('.tg-history__entry', { hasText: 'Tui thích săn mây' }).click()
  await page.getByText('Săn mây có mấy kiểu', { exact: false }).waitFor()
  await page.locator('.tg-sub__row').click()
  const stage = page.getByRole('dialog', { name: 'Các kiểu săn mây' })
  await stage.waitFor()
  await stage.locator('.tg-stage__card.is-front').click() // opens the kind in front
  await page.getByRole('dialog', { name: 'Quán cà phê săn mây: bạn mê kiểu nào?' }).waitFor()
  await page.waitForTimeout(400)
  await page.screenshot({ path: resolve(out, 'understand-stage-vibes.png') })
  await page.locator('.tg-stage__card.is-front .tg-stage__wish').click()
  await page.locator('.tg-basket__kind', { hasText: 'Quán cà phê' }).waitFor()
  await page.locator('.tg-basket').getByRole('button', { name: /^Xong/ }).click()
  await page.getByText(/^Mình chọn: Quán cà phê/).waitFor()
  await page.getByText('Có vẻ bạn mê ngồi cà phê ngắm mây; sáng sớm thử thêm đồi ngắm bình minh nhé.').waitFor()
  const kinds = turns.map(t => t.kind)
  assert.ok(kinds.indexOf('wish') >= 0 && kinds.indexOf('wish') < kinds.indexOf('explored'), 'the wish is written before Xong is told')
  const explored = turns.find(t => t.kind === 'explored')
  assert.equal(explored.qid, 'sig-cloud')
  assert.equal(explored.chips.length, 1)
  await page.screenshot({ path: resolve(out, 'understand-explored.png') })
  // the same picks are told once: closing again with nothing new sends nothing
  await page.locator('.tg-sub__row').click()
  await page.locator('.tg-basket').getByRole('button', { name: /^Xong/ }).click()
  await page.waitForTimeout(500)
  assert.equal(turns.filter(t => t.kind === 'explored').length, 1)

  for (const width of [1440, 1024, 390]) {
    await page.setViewportSize({ width, height: 860 })
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `no overflow at ${width}`)
  }
  assert.deepEqual(errors, [])
  console.log('Understand exploring: plain history, smooth switching, question sheet (multi, later, reopen), tag stage vibes and explored passed')
} finally {
  await browser.close()
}
