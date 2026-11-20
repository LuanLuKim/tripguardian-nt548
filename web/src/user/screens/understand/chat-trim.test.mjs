import assert from 'node:assert/strict'
import { mkdir, copyFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { createServer } from '../../../../node_modules/vite/dist/node/index.js'
import { chromium } from '../../../../node_modules/playwright-core/index.mjs'

const root = resolve(import.meta.dirname, '../../../../..')
const track = resolve(root, '.superpowers/sdd/2026-11-03-prod-e2e/chat-trim')
const server = await createServer({ root: resolve(root, 'web'), configFile: false, cacheDir: resolve(track, 'fixture-cache'), esbuild: { jsx: 'automatic' },
  resolve: { alias: { react: resolve(root, 'web/node_modules/react'), 'react-dom': resolve(root, 'web/node_modules/react-dom') } },
  optimizeDeps: { include: ['react', 'react-dom/client', 'react/jsx-runtime'] },
  server: { host: '127.0.0.1', port: 5443, strictPort: true, fs: { allow: [root] } },
  plugins: [{ name: 'chat-trim-fixture', configureServer(s) { s.middlewares.use((req, res, next) => {
    if (!req.url?.startsWith('/chat-trim.html')) return next()
    res.setHeader('Content-Type', 'text/html')
    res.end('<html lang="vi"><head><meta charset="UTF-8"></head><body><div id="root"></div><script type="module" src="/src/user/screens/understand/chat-trim.fixture.tsx"></script></body></html>')
  }) } }],
})
let browser
let failures = 0
try {
  await server.listen()
  browser = await chromium.launch({ executablePath: resolve(root, '.cache/ms-playwright/chromium-1169/chrome-linux/chrome'), chromiumSandbox: true, headless: true })
  await mkdir(resolve(track, 'shots'), { recursive: true })
  for (const name of ['completed', 'waiting', 'dish']) {
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' })
    const errors = []
    page.on('pageerror', e => errors.push(e.message))
    await page.route('**/api/**', r => r.fulfill({ json: {} }))
    await page.route('**/data/**', r => new URL(r.request().url()).pathname.startsWith('/data/') ? r.fulfill({ json: {} }) : r.continue())
    try {
      await page.goto(`http://127.0.0.1:5443/chat-trim.html?case=${name}`)
      await page.locator(name === 'dish' ? '.tg-cx-dish' : '.tg-cx__m').waitFor()
      if (name === 'completed') {
        // a finished turn folds to one quiet line; its steps open on a click
        assert.equal(await page.locator('.tg-cx__think').count(), 1)
        assert.equal(await page.locator('.tg-cx__think.is-open').count(), 0)
        assert.match(await page.locator('.tg-cx__think-h').innerText(), /Đã xử lý trong/)
      } else if (name === 'waiting') {
        assert.equal(await page.locator('[aria-busy="true"]').count(), 1)
        // a running turn shows what it is doing, and its steps are open: nobody waits on a blank screen (owner 2026-11-17)
        assert.equal(await page.getByRole('status').count(), 1)
        assert.equal(await page.locator('.tg-cx__think.is-open').count(), 1)
        assert.match(await page.locator('.tg-cx__think-h').innerText(), /Đang soạn câu trả lời/)
        assert.match(await page.locator('.tg-cx__steps').innerText(), /Ghi nhận phương tiện/)
      } else {
        assert.equal(await page.locator('.tg-cx-dish').getAttribute('aria-label'), 'Quán có món Lẩu Gà Lá É')
        assert.equal(await page.locator('.tg-cx-dish q, .tg-cx-dish__list').count(), 0)
        assert.doesNotMatch(await page.locator('body').innerText(), /LONG_MENU_EXCERPT|Xem trên Google Maps/)
        await page.locator('.tg-stage__reopen').click()
        await page.getByText('Quán kiểm thử', { exact: true }).waitFor()
      }
      assert.deepEqual(errors, [])
      await page.screenshot({ path: resolve(track, `shots/${name}.png`), fullPage: true })
      if (process.argv.includes('--shots')) await copyFile(resolve(track, `shots/${name}.png`), resolve(root, `frontend_images/chat-trim-${name}.png`))
      console.log(`PASS ${name}`)
    } catch (e) { failures++; console.error(`FAIL ${name}: ${e.message.slice(0, 260)}`); await page.screenshot({ path: resolve(track, `shots/${name}-red.png`), fullPage: true }) }
    await page.close()
  }
  assert.equal(failures, 0)
} finally { await browser?.close(); await server.close() }
