import assert from 'node:assert/strict'
import { resolve } from 'node:path'
import { createServer } from '../../../../node_modules/vite/dist/node/index.js'
import { chromium } from '../../../../node_modules/playwright-core/index.mjs'
const root = resolve(import.meta.dirname, '../../../../..')
const track = resolve(root, '.superpowers/sdd/2026-11-03-prod-e2e/trip-disc')
const server = await createServer({ root: resolve(root, 'web'), configFile: false, cacheDir: resolve(track, 'fixture-cache'), esbuild: { jsx: 'automatic' },
  server: { host: '127.0.0.1', port: 5444, strictPort: true, fs: { allow: [root] } },
  plugins: [{ name: 'discovery-fixture', configureServer(s) { s.middlewares.use((req, res, next) => {
    if (!req.url?.startsWith('/trip-disc.html')) return next()
    res.setHeader('Content-Type', 'text/html')
    res.end('<html lang="vi"><head><meta charset="UTF-8"></head><body><div id="root"></div><script type="module" src="/src/user/screens/understand/trip-disc.fixture.tsx"></script></body></html>')
  }) } }],
})
let browser
try {
  await server.listen()
  browser = await chromium.launch({ executablePath: resolve(root, '.cache/ms-playwright/chromium-1169/chrome-linux/chrome'), chromiumSandbox: true, headless: true })
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
  await page.goto('http://127.0.0.1:5444/trip-disc.html')
  await page.getByRole('button', { name: 'Tiếp tục đến chọn nơi' }).waitFor()
  assert.doesNotMatch(await page.locator('body').innerText(), /Cần bổ sung|Bổ sung lưu ý/)
  await page.getByRole('region', { name: 'Gu của chuyến' }).waitFor({ timeout: 5000 })
  await page.screenshot({ path: resolve(track, 'shots/board-discovery.png'), fullPage: true })
  await page.getByRole('button', { name: /Xoá gu/ }).click()
  assert.equal(await page.getByRole('button', { name: /Xoá gu/ }).count(), 0)
  assert.equal(await page.getByRole('button', { name: 'Tiếp tục đến chọn nơi' }).isEnabled(), true)
  await page.screenshot({ path: resolve(track, 'shots/board-removed.png'), fullPage: true })
  await page.goto('http://127.0.0.1:5444/trip-disc.html?discovery=off')
  await page.getByRole('button', { name: 'Tiếp tục đến chọn nơi' }).waitFor()
  assert.match(await page.locator('body').innerText(), /Bổ sung lưu ý/)
  assert.equal(await page.getByRole('region', { name: 'Gu của chuyến' }).count(), 0)
  await page.screenshot({ path: resolve(track, 'shots/board-legacy.png'), fullPage: true })
  console.log('PASS both rollout states: preferences, removal, neutral missing facts, legacy board, continue')
} finally { await browser?.close(); await server.close() }
