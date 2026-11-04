import assert from 'node:assert/strict'
import { mkdir, copyFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { createServer } from '../../../node_modules/vite/dist/node/index.js'
import { chromium } from '../../../node_modules/playwright-core/index.mjs'

const root = resolve(import.meta.dirname, '../../../..')
const track = resolve(root, '.superpowers/sdd/2026-11-03-prod-e2e/web-f')
const server = await createServer({ root: resolve(root, 'web'), configFile: false, cacheDir: resolve(track, 'fixture-cache'), esbuild: { jsx: 'automatic' },
  resolve: { alias: { react: resolve(root, 'web/node_modules/react'), 'react-dom': resolve(root, 'web/node_modules/react-dom') } },
  optimizeDeps: { include: ['react', 'react-dom/client', 'react/jsx-runtime'] },
  server: { host: '127.0.0.1', port: 5442, strictPort: true, fs: { allow: [root] } },
  plugins: [{ name: 'web-f-fixture', configureServer(s) { s.middlewares.use((req, res, next) => {
    if (!req.url?.startsWith('/web-f.html')) return next()
    res.setHeader('Content-Type', 'text/html')
    res.end('<html lang="vi"><head><meta charset="UTF-8"></head><body><div id="root"></div><script type="module" src="/src/user/pd/web-f.fixture.tsx"></script></body></html>')
  }) } }],
})
let browser
let failures = 0
try {
  await server.listen()
  browser = await chromium.launch({ executablePath: resolve(root, '.cache/ms-playwright/chromium-1169/chrome-linux/chrome'), chromiumSandbox: true, headless: true })
  await mkdir(resolve(track, 'shots'), { recursive: true })
  const tests = ['drop', 'counts', 'undo', 'dish', 'dish-unmatched'].filter(name => !process.env.WEB_F_CASE || process.env.WEB_F_CASE === name)
  for (const name of tests) {
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' })
    page.setDefaultTimeout(6000)
    const errors = []
    page.on('pageerror', e => errors.push(e.message))
    const chosen = ['one', 'two']
    let revision = 0
    const view = () => ({ version: revision, groups: [], change: {}, selected: [...chosen], locked: [], unverified: { count: 0, cards: [] }, excluded: { by_rule: [] }, dropped: [], days: [], pending: null,
      feasibility: { totals: { places: chosen.length, visit: 60, travel: 15, available: 900 }, known_days: true } })
    const journey = () => ({ id: 'web-f', stage: 'decision', revision, outputs: {}, result: { view: view(), diff: { added: [], removed: [], status: ['ok', 'ok'], delta: { places: -1, visit: 0, travel: 0 }, text: 'Đã bỏ Bánh Căn Nhỏ', scope: { from: null, keep: [] } } } })
    await page.addInitScript(() => localStorage.setItem('tg.trip.v1', JSON.stringify({ journeyId: 'web-f', decisionId: 'web-f' })))
    await page.route('**/api/**', async route => {
      if (route.request().method() !== 'POST') return route.fulfill({ json: journey() })
      const { payload } = route.request().postDataJSON()
      if (payload.type === 'drop') {
        if (name === 'counts') await new Promise(r => setTimeout(r, 1200))
        chosen.splice(chosen.indexOf(payload.place_id), 1)
      } else if (payload.type === 'undo') chosen.unshift('one')
      revision++
      return route.fulfill({ json: journey() })
    })
    await page.route('**/data/**', r => new URL(r.request().url()).pathname.startsWith('/data/') ? r.fulfill({ json: {} }) : r.continue())
    try {
      await page.goto(`http://127.0.0.1:5442/web-f.html?case=${name}`)
      if (name.startsWith('dish')) {
        await page.locator('.tg-cx-dish').waitFor()
        const label = name === 'dish' ? 'Quán có món Lẩu Gà Lá É' : 'Quán có món lau ga la e'
        assert.equal(await page.locator('.tg-cx-dish').getAttribute('aria-label'), label)
      } else {
        await page.getByText('one,two', { exact: true }).waitFor()
        await page.getByRole('button', { name: 'Bỏ Bánh Căn Nhỏ', exact: true }).click()
        if (name === 'counts') {
          await page.getByText('two', { exact: true }).waitFor({ timeout: 700 })
          assert.equal(await page.locator('.tg-bar__stats .tg-mono').first().innerText(), '1')
        } else {
          await page.getByText('two', { exact: true }).waitFor({ timeout: 1500 })
          assert.equal(await page.getByRole('dialog').count(), 0)
          if (name === 'undo') {
            await page.getByRole('button', { name: 'Hoàn tác', exact: true }).first().click()
            await page.getByText('one,two', { exact: true }).waitFor()
          }
        }
      }
      assert.deepEqual(errors, [])
      await page.screenshot({ path: resolve(track, `shots/${name}.png`), fullPage: true })
      console.log(`PASS ${name}`)
    } catch (e) { failures++; console.error(`FAIL ${name}: ${e.message.slice(0, 220)}`); await page.screenshot({ path: resolve(track, `shots/${name}-red.png`), fullPage: true }) }
    await page.close()
  }
  if (process.argv.includes('--shots') && !failures) {
    await mkdir(resolve(root, 'frontend_images'), { recursive: true })
    for (const name of tests) await copyFile(resolve(track, `shots/${name}.png`), resolve(root, `frontend_images/web-f-${name}.png`))
  }
  assert.equal(failures, 0, `${failures} regressions failed`)
} finally { await browser?.close(); await server.close() }
