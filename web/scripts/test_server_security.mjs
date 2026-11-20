// Local HTTP regression tests for public proxy isolation; no external services or secrets.
import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { once } from 'node:events'
import { createServer, request } from 'node:http'
import { test } from 'node:test'

test('public server blocks private files and handles interrupted upstream responses', async (t) => {
  const upstream = createServer((req, res) => {
    if (req.url === '/api/harness/interrupted') {
      res.writeHead(200, { 'Content-Type': 'text/event-stream' })
      res.write('event: say\ndata: {}\n\n')
      return setTimeout(() => res.socket.destroy(), 10)
    }
    res.setHeader('Content-Type', 'application/json')
    res.end(JSON.stringify(req.headers))
  })
  upstream.listen(0, '127.0.0.1')
  await once(upstream, 'listening')
  // Stand-ins for the analytics server (answers /me by its cookie, like the real one) and the review server.
  const analytics = createServer((req, res) => {
    const signedIn = String(req.headers.cookie ?? '').includes('tg_admin=ok')
    res.setHeader('Content-Type', 'application/json')
    if (req.url === '/api/analytics/me' || req.url === '/api/analytics/today') {
      res.statusCode = signedIn ? 200 : 401
      return res.end(JSON.stringify({ signedIn }))
    }
    res.end(JSON.stringify(req.headers))
  })
  const review = createServer((req, res) => { res.setHeader('Content-Type', 'application/json'); res.end(JSON.stringify({ url: req.url })) })
  for (const s of [analytics, review]) { s.listen(0, '127.0.0.1'); await once(s, 'listening') }
  const reserve = createServer()
  reserve.listen(0, '127.0.0.1')
  await once(reserve, 'listening')
  const port = reserve.address().port
  await new Promise(resolve => reserve.close(resolve))
  const child = spawn(process.execPath, [new URL('../server.mjs', import.meta.url).pathname, String(port)], {
    env: { ...process.env, HARNESS_PORT: String(upstream.address().port), ANALYTICS_PORT: String(analytics.address().port), REVIEW_PORT: String(review.address().port) }, stdio: ['ignore', 'pipe', 'pipe'],
  })
  t.after(async () => {
    child.kill()
    await once(child, 'exit')
    for (const s of [upstream, analytics, review]) {
      s.closeAllConnections()
      await new Promise(resolve => s.close(resolve))
    }
  })
  await Promise.race([once(child.stdout, 'data'), once(child, 'exit').then(() => { throw new Error('server exited') })])
  function call(path, headers = {}, method = 'GET') {
    return new Promise((resolve, reject) => {
      const req = request({ host: '127.0.0.1', port, path, headers, method }, res => {
        const chunks = []
        res.on('data', chunk => chunks.push(chunk))
        res.on('end', () => resolve({ status: res.statusCode, body: Buffer.concat(chunks).toString() }))
        res.on('error', reject)
      })
      req.on('error', reject)
      req.setTimeout(2000, () => req.destroy(new Error('timeout')))
      req.end()
    })
  }
  for (const path of ['/.env', '/.git/config', '/assets/app.js.map', '/admin/app.js', '/api/trip/sessions', '/api/labels/other', '/api/decision/x', '/%2e%2e/etc/passwd']) {
    assert.equal((await call(path)).status, 404, path)
  }
  assert.equal((await call('/%zz')).status, 400)
  // Admin: analytics answers for itself; the review API and the admin snapshot need its confirmation of the cookie.
  const cookie = { cookie: 'tg_admin=ok' }
  assert.equal((await call('/api/analytics/today')).status, 401)
  assert.equal((await call('/api/analytics/today', cookie)).status, 200)
  assert.equal((await call('/api/decisions?kind=feature_review')).status, 401)
  assert.equal((await call('/api/labels/next?n=1', { cookie: 'tg_admin=forged' })).status, 401)
  assert.equal((await call('/data/snapshot-admin.json')).status, 401)
  assert.equal((await call('/data/admin-overview.json')).status, 401)
  assert.equal(JSON.parse((await call('/api/decisions?kind=feature_review', cookie)).body).url, '/api/decisions?kind=feature_review')
  const origin = { ...cookie, origin: `http://127.0.0.1:${port}` }
  assert.equal((await call('/api/decision', cookie, 'POST')).status, 404) // no Origin
  assert.equal((await call('/api/decision', { ...cookie, origin: 'https://evil.example' }, 'POST')).status, 404)
  assert.equal((await call('/api/decision', {}, 'POST')).status, 404)
  assert.equal((await call('/api/decision', origin, 'POST')).status, 200)
  assert.equal((await call('/api/decision', origin, 'DELETE')).status, 404)
  const viaTunnel = JSON.parse((await call('/api/analytics/login', { origin: `http://127.0.0.1:${port}`, 'x-tg-secure': '1', 'x-tg-client-ip': '9.9.9.9', 'cf-connecting-ip': '1.2.3.4' }, 'POST')).body)
  assert.equal(viaTunnel['x-tg-secure'], undefined) // only a real x-forwarded-proto: https sets it
  assert.equal(viaTunnel['x-tg-client-ip'], '1.2.3.4')
  const https = JSON.parse((await call('/api/analytics/login', { origin: `http://127.0.0.1:${port}`, 'x-forwarded-proto': 'https' }, 'POST')).body)
  assert.equal(https['x-tg-secure'], '1')
  const forwarded = JSON.parse((await call('/api/harness/headers', {
    'x-tg-client-ip': '9.9.9.9', 'x-forwarded-for': '9.9.9.9', 'cf-connecting-ip': '1.2.3.4',
  })).body)
  assert.equal(forwarded['x-tg-client-ip'], '1.2.3.4')
  assert.equal(forwarded['x-forwarded-for'], undefined)
  assert.equal(forwarded['cf-connecting-ip'], undefined)
  // Every interrupted SSE must close promptly and return its slot, even after more than the 64-slot quota.
  for (let i = 0; i < 65; i++) {
    await assert.rejects(call('/api/harness/interrupted'), /aborted|reset|closed/i)
  }
  assert.equal((await call('/api/harness/headers')).status, 200)
})
