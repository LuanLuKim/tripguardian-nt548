import assert from 'node:assert/strict'
import { resolve } from 'node:path'
import { chromium } from 'playwright-core'

const base = process.argv[2] ?? 'http://127.0.0.1:5173'
const browser = await chromium.launch({ executablePath: resolve(import.meta.dirname, '../../.cache/ms-playwright/chromium-1169/chrome-linux/chrome'), args: ['--no-sandbox'] })
try {
  const page = await browser.newPage()
  let fail = true
  const requests = []
  await page.route('**/api/harness/sessions/**', async route => {
    const req = route.request()
    const view = { id: '0123456789ab', stage: requests.length ? 'planning' : 'decision', revision: requests.length, sessions: {}, outputs: {}, result: {} }
    if (req.method() === 'POST') {
      if (fail) return route.fulfill({ status: 400, json: { error: 'fixture failure' } })
      const input = req.postDataJSON()
      requests.push(input)
      return route.fulfill({ json: { ...view, stage: input.stage, revision: input.expected_revision + 1 } })
    }
    return route.fulfill({ json: view })
  })
  await page.route('**/data/*.json', route => route.fulfill({ json: { places: [] } }))
  await page.route('**/assistant-fixture.html', route => route.fulfill({ contentType: 'text/html', body: '<script type="module">import { injectIntoGlobalHook } from "/@react-refresh"; injectIntoGlobalHook(window); window.$RefreshReg$ = () => {}; window.$RefreshSig$ = () => (type) => type</script><div id="root"></div><script type="module" src="/src/user/ui/__tests__/assistant.fixture.tsx"></script>' }))
  await page.goto(base + '/assistant-fixture.html')
  const reset = page.getByRole('button', { name: 'Cuộc trò chuyện mới' })
  await page.getByText('Decision question', { exact: true }).waitFor()
  await page.getByRole('button', { name: 'Toggle streaming' }).click()
  assert.equal(await reset.isDisabled(), true)
  await page.getByRole('button', { name: 'Toggle streaming' }).click()
  await reset.click()
  await page.waitForFunction(() => !document.querySelector('.tg-asst__ops button')?.disabled)
  assert.equal(await page.getByText('Decision question', { exact: true }).count(), 1)
  fail = false
  await reset.click()
  await page.getByText('2 messages', { exact: true }).waitFor()
  assert.equal(await reset.isDisabled(), true)
  assert.equal(requests[0].operation, 'new_chat')
  assert.deepEqual(requests[0].payload.messages.map(m => m.text), ['Decision question', 'Decision reply'])
  await page.getByRole('button', { name: 'Switch stage' }).click()
  await page.getByText('Planning question', { exact: true }).waitFor()
  await reset.click()
  await page.getByText('0 messages', { exact: true }).waitFor()
  assert.equal(requests[1].stage, 'planning')
  console.log('Assistant: archive-before-clear, failure preservation, per-stage clearing, streaming/empty guards passed')
} finally { await browser.close() }
