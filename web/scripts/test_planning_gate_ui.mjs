// Isolated gate fixtures exercise the real sheet and journey client without a model or database.
import assert from 'node:assert/strict'
import { mkdirSync } from 'node:fs'
import { resolve } from 'node:path'
import { chromium } from 'playwright-core'

const base = process.argv[2] ?? 'http://127.0.0.1:5186'
const out = resolve(import.meta.dirname, '../../frontend_images/2026-11-10-planning-gate')
mkdirSync(out, { recursive: true })
const browser = await chromium.launch({ executablePath: resolve(import.meta.dirname, '../../.cache/ms-playwright/chromium-1169/chrome-linux/chrome'), args: ['--no-sandbox'] })
const option = (id, label) => ({ id, label, description: '', prefilled: false, because: '', writes: [] })
const cards = {
  trip: { qid: 'trip', kind: 'required', header: 'Ngày đi', question: 'Bạn ở Đà Lạt từ ngày nào đến ngày nào?', why: 'Để chia ngày cho lịch trình.', inputs: ['dates'], options: [], multi: false },
  care: { qid: 'care', kind: 'required', header: 'Lưu ý', question: 'Có điều gì về sức khỏe, đi lại hay ăn uống cần lưu ý?', why: 'Để tránh nơi không phù hợp.', inputs: [], options: [option('none', 'Không có')], multi: true },
}
const html = `<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><body style="background:#ded5c4"><div id="root"></div><script type="module">
import { injectIntoGlobalHook } from '/@react-refresh'; injectIntoGlobalHook(window); window.$RefreshReg$ = () => {}; window.$RefreshSig$ = () => (type) => type
</script><script type="module" src="/src/user/ui/__tests__/gate.fixture.tsx"></script></body></html>`

try {
  for (const scenario of [
    { name: 'dates-and-care', missing: ['trip', 'care'], width: 1440, height: 1000 },
    { name: 'dates-only', missing: ['trip'], width: 1440, height: 1000 },
    { name: 'care-only', missing: ['care'], width: 1440, height: 1000 },
    { name: 'care-mobile', missing: ['care'], width: 375, height: 844 },
  ]) {
    const page = await browser.newPage({ viewport: { width: scenario.width, height: scenario.height }, reducedMotion: 'reduce' })
    const errors = [], turns = []
    page.on('pageerror', e => errors.push(e.message))
    let missing = [...scenario.missing], revision = 0, advances = 0, failNext = scenario.name === 'care-only'
    const readback = () => ({ lines: [], digest: null, ok: false, missing, deck: missing.length ? { kind: 'deck', at: 'gate', tabs: missing.map(k => cards[k]), left: missing.length, total: 2 } : null })
    const journey = () => ({ id: 'gate-test', stage: 'decision', revision, sessions: {}, outputs: {}, result: { view: {} } })
    await page.route('**/__planning_gate', route => route.fulfill({ contentType: 'text/html', body: html }))
    await page.route('**/api/harness/sessions/**', async route => {
      const req = route.request(), path = new URL(req.url()).pathname
      if (path.endsWith('/read/trip/readback')) return route.fulfill({ json: readback() })
      if (!path.endsWith('/request')) return route.fulfill({ json: journey() })
      const input = req.postDataJSON()
      if (input.operation === 'advance') {
        advances++
        if (missing.length) return route.fulfill({ status: 409, json: { error: 'trip_incomplete', missing, readback: readback() } })
        revision++
        return route.fulfill({ contentType: 'text/event-stream', body: `data: ${JSON.stringify({ event: 'journey', data: { ...journey(), stage: 'planning' }, stage: 'planning', revision, request_id: input.request_id })}\n\n` })
      }
      turns.push(input.payload)
      if (failNext) { failNext = false; return route.fulfill({ status: 400, json: { error: 'invalid answer' } }) }
      const answers = input.payload.answers
      assert.equal(input.payload.kind, 'deck')
      if (answers['trip.dates']) missing = missing.filter(k => k !== 'trip')
      if (answers.care?.includes('none')) missing = missing.filter(k => k !== 'care')
      revision++
      return route.fulfill({ contentType: 'text/event-stream', body: `data: ${JSON.stringify({ event: 'journey', data: journey(), stage: 'decision', revision, request_id: input.request_id })}\n\n` })
    })
    await page.goto(base + '/__planning_gate')
    await page.getByRole('button', { name: 'Tiếp tục đến lịch trình', exact: true }).click()
    const dialog = page.getByRole('dialog')
    await dialog.waitFor()
    assert.equal(await dialog.locator('.tg-gt__card').count(), scenario.missing.length)
    assert.equal(await dialog.locator('.tg-gt__meter, .tg-gt__check, .tg-gt__ledger').count(), 0)
    assert.equal(await dialog.getByText('Đúng rồi, xếp lịch', { exact: true }).count(), 0)
    assert.equal(await dialog.getByRole('button', { name: 'Sửa trong Tìm hiểu' }).count(), 1)
    if (missing.includes('trip')) {
      assert.equal(await dialog.locator('.tg-gt__hours').count(), 0)
      const days = dialog.locator('.tg-gt__cal-grid button:not(:disabled)')
      await days.first().click()
      await days.first().click()
    }
    await page.screenshot({ path: resolve(out, `${scenario.name}.png`) })
    if (!scenario.missing.includes('trip')) await dialog.getByRole('button', { name: 'Không có', exact: true }).click()
    await dialog.getByRole('button', { name: 'Xong', exact: true }).click()
    if (scenario.name === 'care-only') {
      await dialog.getByRole('alert').waitFor()
      await dialog.getByRole('button', { name: 'Xong', exact: true }).click()
    } else if (scenario.missing.includes('care') && scenario.missing.includes('trip')) {
      await dialog.getByRole('button', { name: 'Không có', exact: true }).click()
      await dialog.getByRole('button', { name: 'Xong', exact: true }).click()
    }
    await page.getByRole('heading', { name: 'Lịch trình sẵn sàng' }).waitFor()
    assert.equal(advances, 2)
    assert.ok(turns.every(t => t.kind === 'deck'))
    assert.deepEqual(errors, [])
    console.log(`PASS ${scenario.name}: last answer advances without read-back`)
    await page.close()
  }
} finally { await browser.close() }
