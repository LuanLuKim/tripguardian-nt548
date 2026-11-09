import assert from 'node:assert/strict'
import { mkdir, copyFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { createServer } from '../../../../node_modules/vite/dist/node/index.js'
import { chromium } from '../../../../node_modules/playwright-core/index.mjs'

const root = process.cwd()
const track = resolve(root, '.superpowers/sdd/2026-11-03-prod-e2e/web-e')
const server = await createServer({ root: resolve(root, 'web'), configFile: false,
  cacheDir: resolve(track, 'vite-cache'), esbuild: { jsx: 'automatic' },
  resolve: { alias: { react: resolve(root, 'web/node_modules/react'), 'react-dom': resolve(root, 'web/node_modules/react-dom') } },
  optimizeDeps: { include: ['react', 'react-dom/client', 'react/jsx-runtime'] },
  server: { host: '127.0.0.1', port: 5495, strictPort: true, fs: { allow: [root] }, proxy: { '/api': 'http://127.0.0.1:8769' } },
  plugins: [{ name: 'planning-notes-fixture', configureServer(s) { s.middlewares.use((req, res, next) => {
    if (!req.url?.startsWith('/fixture.html')) return next()
    res.setHeader('Content-Type', 'text/html')
    res.end('<html lang="vi"><head><meta charset="UTF-8"></head><body><div id="root"></div><script type="module" src="/src/user/screens/plan/notes.fixture.tsx"></script></body></html>')
  }) } }],
})
let browser
try {
  await server.listen()
  browser = await chromium.launch({ executablePath: resolve(root, '.cache/ms-playwright/chromium-1169/chrome-linux/chrome'), chromiumSandbox: true, headless: true })
  const page = await browser.newPage({ viewport: { width: 1100, height: 1100 } })
  await page.addInitScript(() => { window.Worker = undefined })
  const errors = []
  page.on('pageerror', e => { errors.push(e.message); console.error(e.message) })
  page.on('console', msg => { if (msg.type() === 'error') console.error(msg.text()) })
  page.on('requestfailed', req => console.error(`${req.url()}: ${req.failure()?.errorText}`))
  await page.route('**/api/**', r => r.fulfill({ status: 401, json: {} }))
  await page.route('**/data/**', r => new URL(r.request().url()).pathname.startsWith('/data/') ? r.fulfill({ json: {} }) : r.continue())
  let failures = 0
  for (const state of ['notes', 'none', 'empty', 'ghost-only', 'busy', 'swap']) {
    try {
      const response = await page.goto(`http://127.0.0.1:5495/fixture.html?case=${state}`)
      assert.equal(response.status(), 200, await response.text())
      await page.locator(state === 'swap' ? '.tg-it-result' : '.tg-sidecard').first().waitFor({ timeout: 15000 })
      if (state === 'swap') {
        for (const card of await page.locator('.tg-it-result').all()) {
          assert.equal(await card.getByText('chưa rõ có cho mang thú cưng không', { exact: true }).count(), 1)
          assert.equal(await card.getByText('Giờ mở cửa <chưa xác minh> & cần kiểm tra', { exact: true }).count(), 1)
        }
        await page.getByRole('button', { name: 'Thêm vào lịch', exact: true }).first().click()
        assert.ok(['backup', 'suggested'].includes((await page.evaluate(() => window.__action)).id))
      } else {
        const hasNotes = !['none', 'empty'].includes(state)
        const time = page.locator('.tg-sidecard').filter({ has: page.getByRole('heading', { name: 'Giờ ghé · Ngày 2', exact: true }) })
        assert.equal(await time.getByText('chưa rõ có cho mang thú cưng không', { exact: true }).count(), hasNotes && state !== 'ghost-only' ? 1 : 0)
        assert.equal(await page.locator('.tg-ghost').getByText('chưa rõ có cho mang thú cưng không', { exact: true }).count(), hasNotes ? 1 : 0)
        assert.equal(await time.getByText('Giờ mở cửa <chưa xác minh> & cần kiểm tra', { exact: true }).count(), hasNotes && state !== 'ghost-only' ? 1 : 0)
        const backup = page.locator('.tg-sidecard').filter({ has: page.getByRole('heading', { name: 'Phương án dự phòng · Ngày 2', exact: true }) })
        assert.equal(await backup.getByText('chưa rõ có cho mang thú cưng không', { exact: true }).count(), hasNotes ? 1 : 0)
        assert.equal(await backup.getByText('Giờ mở cửa <chưa xác minh> & cần kiểm tra', { exact: true }).count(), hasNotes ? 1 : 0)
        assert.equal(await page.getByText('Không được hiện ngày này', { exact: true }).count(), 0)
        assert.equal(await page.getByRole('button', { name: 'Thêm Gợi ý bữa trưa mẫu', exact: true }).count(), 1)
        if (!hasNotes) assert.equal(await page.locator('small.tg-faint:empty').count(), 0)
        const add = page.getByRole('button', { name: 'Thêm Gợi ý bữa trưa mẫu', exact: true })
        assert.equal(await add.isEnabled(), state !== 'busy')
        if (state !== 'busy') {
          await add.click()
          assert.deepEqual(await page.evaluate(() => window.__action), { id: 'ghost', day: 2 })
          const backupButton = page.getByRole('button', { name: 'Thay bằng Dự phòng mẫu (≈8′)', exact: true })
          await backupButton.click()
          assert.deepEqual(await page.evaluate(() => window.__action), { place: 'original', id: 'backup' })
        }
        assert.equal(await page.getByRole('dialog').count(), 0)
      }
      if (process.argv.includes('--shots')) {
        await mkdir(resolve(track, 'shots'), { recursive: true })
        await page.screenshot({ path: resolve(track, `shots/${state}.png`), fullPage: true })
        await mkdir(resolve(root, 'frontend_images'), { recursive: true })
        await copyFile(resolve(track, `shots/${state}.png`), resolve(root, `frontend_images/web-e-${state}.png`))
      }
      console.log(`PASS ${state}`)
    } catch (e) { failures++; console.error(`FAIL ${state}: ${e.message.slice(0, 250)}`) }
  }
  assert.deepEqual(errors, [])
  assert.equal(failures, 0, `${failures} component regressions failed`)
} finally { await browser?.close(); await server.close() }
