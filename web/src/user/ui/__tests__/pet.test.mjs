import assert from 'node:assert/strict'
import { mkdir, copyFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { createServer } from '../../../../node_modules/vite/dist/node/index.js'
import { chromium } from '../../../../node_modules/playwright-core/index.mjs'

const root = process.cwd()
const track = resolve(root, '.superpowers/sdd/2026-11-03-prod-e2e/web-d')
const server = await createServer({ root: resolve(root, 'web'), configFile: false,
  cacheDir: resolve(track, 'vite-cache'),
  esbuild: { jsx: 'automatic' },
  resolve: { alias: { react: resolve(root, 'web/node_modules/react'), 'react-dom': resolve(root, 'web/node_modules/react-dom') } },
  optimizeDeps: { include: ['react', 'react-dom/client', 'react/jsx-runtime'] },
  server: { host: '127.0.0.1', port: 5494, strictPort: true, fs: { allow: [root] } },
  plugins: [{ name: 'pet-component-fixture',
    transform(code, id) {
      if (id.endsWith('/user/pd/decision.tsx')) return 'export const useDecision = () => ({busy: false, view: null, act: (action) => { window.__selected = action }})'
    },
    configureServer(s) { s.middlewares.use((req, res, next) => {
      if (!req.url?.startsWith('/fixture.html')) return next()
      res.setHeader('Content-Type', 'text/html')
      res.end('<html lang="vi"><head><meta charset="UTF-8"></head><body><div id="root"></div><script type="module" src="/src/user/ui/__tests__/pet.fixture.tsx"></script></body></html>')
    }) },
  }],
})
let browser
try {
  await server.listen()
  browser = await chromium.launch({ executablePath: resolve(root, '.cache/ms-playwright/chromium-1169/chrome-linux/chrome'), chromiumSandbox: true, headless: true })
  const page = await browser.newPage({ viewport: { width: 1000, height: 900 } })
  await page.addInitScript(() => { window.Worker = undefined })
  const errors = []
  page.on('pageerror', e => errors.push(e.message))
  page.on('console', msg => { if (msg.type() === 'error') console.error(msg.text()) })
  await page.route('**/api/**', r => r.fulfill({ status: 401, json: {} }))
  await page.route('**/data/**', r => {
    const path = new URL(r.request().url()).pathname
    if (!path.startsWith('/data/')) return r.continue()
    if (path.endsWith('snapshot-lite.json')) return r.fulfill({ status: 404, body: '' })
    if (!path.endsWith('snapshot.json')) return r.fulfill({ json: {} })
    return r.fulfill({ json: { places: [{ id: 'fixture', name: 'Địa điểm mẫu', group: 'food', lat: 11.94, lng: 108.44, hoursText: [], videos: [], features: [
      { id: 'pets', value: page.url().includes('not_allowed') ? 'not_allowed' : 'allowed', status: 'VERIFIED', n: page.url().includes('not_allowed') ? 4 : 7, agreement: 1, freshnessDays: 1, quotes: [{ text: page.url().includes('not_allowed') ? 'Quán không cho mang thú cưng vào.' : 'Quán cho mang thú cưng vào ngồi cùng.', source: 'gmaps', date: '2026-11-01' }] },
    ] }] } })
  })
  let failures = 0
  for (const state of ['allowed', 'not_allowed', 'unknown', 'other', 'mixed']) {
    try {
      await page.goto(`http://127.0.0.1:5494/fixture.html?case=${state}`)
      await page.locator('.tg-pc').waitFor({ timeout: 15000 })
      const card = page.locator('.tg-pc')
      if (state === 'allowed' || state === 'not_allowed') {
        const text = state === 'allowed' ? 'Cho mang thú cưng, theo 7 người' : 'Không cho mang thú cưng, theo 4 người'
        const fact = card.getByText(text, { exact: true })
        assert.equal(await fact.count(), 1)
        assert.equal(await card.locator('.tg-pc__why, .tg-pc__trade, .tg-pc__alert').filter({ hasText: /thú cưng/ }).count(), 0)
        assert.equal(await fact.locator('..').getAttribute('data-sid'), 'pets')
        await fact.focus()
        await page.keyboard.press('Enter')
        await card.getByText(state === 'not_allowed' ? 'Quán không cho mang thú cưng vào.' : 'Quán cho mang thú cưng vào ngồi cùng.', { exact: true }).waitFor({ timeout: 1500 })
      } else if (state !== 'other') {
        assert.equal(await card.getByText('Chưa rõ có cho mang thú cưng không', { exact: true }).count(), 1)
        assert.equal(await card.locator('.tg-pc__trade, .tg-pc__alert').filter({ hasText: /thú cưng/ }).count(), 0)
      }
      if (state === 'other') {
        assert.match(await card.locator('.tg-pc__trade').innerText(), /Đánh đổi:.*Cuối tuần đông/)
        assert.match(await card.locator('.tg-pc__alert').innerText(), /Không hợp điều kiện của bạn: Có chỗ đỗ xe: không/)
      }
      if (state === 'mixed') assert.match(await card.locator('.tg-pc__trade').innerText(), /Không hợp điều kiện của bạn: Có chỗ đỗ xe: không/)
      assert.equal(await card.locator('.tg-pc__why').innerText(), 'Không gian yên tĩnh')
      const select = card.getByRole('button', { name: 'Thêm vào chuyến', exact: true })
      assert.equal(await select.isEnabled(), true)
      await select.click()
      assert.deepEqual(await page.evaluate(() => window.__selected), { type: 'select', place_id: 'fixture' })
      assert.equal(await page.getByRole('dialog').count(), 0)
      if (process.argv.includes('--shots')) {
        await mkdir(resolve(track, 'shots'), { recursive: true })
        await page.screenshot({ path: resolve(track, `shots/${state}.png`), fullPage: true })
        await mkdir(resolve(root, 'frontend_images'), { recursive: true })
        await copyFile(resolve(track, `shots/${state}.png`), resolve(root, `frontend_images/web-d-${state}.png`))
      }
      console.log(`PASS ${state}`)
    } catch (e) { failures++; console.error(`FAIL ${state}: ${e.message.slice(0, 250)}`) }
  }
  assert.deepEqual(errors, [])
  assert.equal(failures, 0, `${failures} component regressions failed`)
} finally { await browser?.close(); await server.close() }
