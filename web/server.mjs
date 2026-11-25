// Public server for the built web (web/dist): what a Cloudflare tunnel may expose, and nothing else.
//   public : landing, /app (SPA), /assets, /img, /data (snapshot, covers), /media photos (jpg only),
//            /media/thumb WebP thumbnails (web/scripts/make_thumbs.py), /media/tiktok/<id>/frames/*.jpg clip posters (clips play in TikTok's player), /media/landing/*.mp4 films (Range),
//            /api/harness/* and /api/auth/* (Google sign-in) proxied to the harness (default 127.0.0.1:8769; JSON and SSE).
//   admin  : /admin (the SPA shell, which shows the sign-in form) and /api/analytics/* (the analytics server enforces
//            its own sign-in) are proxied; the review API (/api/queue, /api/decision(s), /api/labels*) and
//            /data/snapshot-admin.json are sent only after analytics confirms the `tg_admin` cookie (/api/analytics/me).
//   private: every other /api/* (module dev APIs), any other video file -> 404.
// Speed: .br/.gz made by web/scripts/prod_assets.mjs are sent to clients that accept them (the tunnel carries
// compressed bytes); every file has an ETag, so a revisit costs a 304; the harness is reached over keep-alive.
// usage: npm run build:prod --prefix web && node web/server.mjs [port, default 28899]
import { createReadStream, existsSync, realpathSync, statSync } from 'node:fs'
import { readFile } from 'node:fs/promises'
import { Agent, createServer, request } from 'node:http'
import { extname, resolve, sep } from 'node:path'
import { isIP } from 'node:net'
import { constants as Z, brotliCompress, createBrotliCompress, createGzip, gzip } from 'node:zlib'
import { promisify } from 'node:util'

const PORT = Number(process.argv[2] ?? process.env.PORT ?? 28899)
const HARNESS = { host: process.env.HARNESS_HOST ?? '127.0.0.1', port: Number(process.env.HARNESS_PORT ?? 8769), agent: new Agent({ keepAlive: true, maxSockets: 64 }), active: 0 }
// Admin: the analytics server (sign-in, numbers) and the review server (queue, labels), both on loopback.
const ANALYTICS = { host: '127.0.0.1', port: Number(process.env.ANALYTICS_PORT ?? 8770), agent: new Agent({ keepAlive: true, maxSockets: 16 }), active: 0 }
const REVIEW = { host: '127.0.0.1', port: Number(process.env.REVIEW_PORT ?? 8765), agent: new Agent({ keepAlive: true, maxSockets: 16 }), active: 0 }
const REVIEW_API = /^\/api\/(queue|decisions?|labels(\/(next|stats|photo|frame))?)$/
// Admin data files (not in dist): sent compressed once per file version and revalidated by ETag, so a revisit is a 304.
const ADMIN_FILES = {
  '/data/snapshot-admin.json': resolve(import.meta.dirname, 'public/data/snapshot-admin.json'),
  '/data/admin-overview.json': resolve(import.meta.dirname, 'public/data/admin-overview.json'),
}
const DIST = resolve(import.meta.dirname, 'dist')
const MEDIA = {
  '/media/thumb/': resolve(import.meta.dirname, '../data/thumbs'),
  '/media/gmaps/': resolve(import.meta.dirname, '../data/gmaps/places'),
  '/media/tiktok/': resolve(import.meta.dirname, '../data/tiktok/videos'),
}
const TYPES = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8', '.webp': 'image/webp', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
  '.png': 'image/png', '.bin': 'application/octet-stream', '.svg': 'image/svg+xml', '.ico': 'image/x-icon', '.woff2': 'font/woff2', '.txt': 'text/plain; charset=utf-8',
  '.webmanifest': 'application/manifest+json',
}
const MEDIA_TYPES = new Set(['.jpg', '.jpeg', '.webp', '.png'])
// The landing's own films (web/public/media/landing, copied into dist): sent in ranges, so Safari plays them and the bar can seek.
const LANDING_CLIP = /^\/media\/landing\/[\w-]+\.mp4$/
// Data files change only on a deploy: browsers and Cloudflare may reuse them briefly, then revalidate (ETag).
const DATA_CACHE = 'public, max-age=300, stale-while-revalidate=86400'
// The 3D viewer: its script is named by content hash (immutable); place data, posters and the index change only on a
// rebuild, so a short cache with background revalidation lets a dive start without a round trip over the tunnel.
const cacheFor = (path) =>
  path.startsWith('/assets/') || /^\/space3d\/viewer-[0-9a-f]+\.js$/.test(path) ? 'public, max-age=31536000, immutable'
    : path.startsWith('/data/') || /^\/space3d\/(index\.json|places\/|posters\/)/.test(path) ? DATA_CACHE
      : path.startsWith('/img/') || path.startsWith('/world/') || path.startsWith('/media/landing/') ? 'public, max-age=86400'
        : 'no-cache'

function notFound(res) {
  res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' })
  res.end('Not found')
}

// A file strictly inside `root`, or null (no path escapes, no directories).
function inside(root, rel) {
  const file = resolve(root, '.' + rel)
  if (!file.startsWith(root + sep)) return null
  try {
    const actual = realpathSync(file)
    return actual.startsWith(realpathSync(root) + sep) && statSync(actual).isFile() ? actual : null
  } catch {
    return null
  }
}

// The precompressed sibling the client accepts, if prod_assets.mjs made one.
function encoded(req, file) {
  const accept = String(req.headers['accept-encoding'] ?? '')
  for (const [enc, ext] of [['br', '.br'], ['gzip', '.gz']]) {
    if (!accept.includes(enc)) continue
    try {
      const st = statSync(file + ext)
      if (st.isFile()) return { enc, path: file + ext, st }
    } catch { /* not precompressed */ }
  }
  return null
}

function sendFile(req, res, file, cache) {
  const type = TYPES[extname(file).toLowerCase()] ?? 'application/octet-stream'
  const st = statSync(file)
  const etag = `"${st.size.toString(36)}-${Math.floor(st.mtimeMs).toString(36)}"`
  const head = { 'Content-Type': type, 'Cache-Control': cache, ETag: etag, 'Last-Modified': st.mtime.toUTCString(), 'X-Content-Type-Options': 'nosniff' }
  if (TYPES[extname(file).toLowerCase()]?.match(/text|json|svg|octet/)) head.Vary = 'Accept-Encoding'
  if (req.headers['if-none-match'] === etag) {
    res.writeHead(304, head)
    return res.end()
  }
  const z = encoded(req, file)
  res.writeHead(200, { ...head, 'Content-Length': (z?.st ?? st).size, ...(z && { 'Content-Encoding': z.enc }) })
  if (req.method === 'HEAD') return res.end()
  createReadStream(z?.path ?? file).pipe(res)
}

function sendRange(req, res, file) {
  const st = statSync(file)
  const head = { 'Content-Type': 'video/mp4', 'Accept-Ranges': 'bytes', 'Cache-Control': 'public, max-age=604800', 'X-Content-Type-Options': 'nosniff' }
  const m = /^bytes=(\d*)-(\d*)$/.exec(String(req.headers.range ?? ''))
  if (!m || (!m[1] && !m[2])) {
    res.writeHead(200, { ...head, 'Content-Length': st.size })
    return req.method === 'HEAD' ? res.end() : createReadStream(file).pipe(res)
  }
  const start = m[1] ? Number(m[1]) : Math.max(0, st.size - Number(m[2]))
  const end = m[1] && m[2] ? Math.min(Number(m[2]), st.size - 1) : st.size - 1
  if (start > end || start >= st.size) {
    res.writeHead(416, { ...head, 'Content-Range': `bytes */${st.size}` })
    return res.end()
  }
  res.writeHead(206, { ...head, 'Content-Range': `bytes ${start}-${end}/${st.size}`, 'Content-Length': end - start + 1 })
  return req.method === 'HEAD' ? res.end() : createReadStream(file, { start, end }).pipe(res)
}

function proxy(req, res, target = HARNESS) {
  if (target.active >= target.agent.maxSockets) {
    res.writeHead(503, { 'Content-Type': 'application/json', 'Retry-After': '1' })
    return res.end(JSON.stringify({ error: 'server busy' }))
  }
  target.active++
  let released = false
  const release = () => { if (!released) { released = true; target.active-- } }
  // Cloudflare overwrites CF-Connecting-IP; only the loopback tunnel can reach this server.
  const candidate = String(req.headers['cf-connecting-ip'] ?? '')
  const headers = { ...req.headers, host: `${target.host}:${target.port}`, 'x-tg-client-ip': isIP(candidate) ? candidate : req.socket.remoteAddress }
  // Whether the visitor reached the tunnel over https (the admin cookie gets Secure); never taken from the client.
  if (req.headers['x-forwarded-proto'] === 'https') headers['x-tg-secure'] = '1'
  else delete headers['x-tg-secure']
  delete headers['x-forwarded-for']
  delete headers['cf-connecting-ip']
  const up = request({ host: target.host, port: target.port, agent: target.agent, method: req.method, path: req.url, headers }, (r) => {
    r.on('aborted', () => { release(); res.destroy() })
    r.on('error', () => { release(); res.destroy() })
    // JSON goes compressed over the tunnel (a Lựa chọn view is ~0.5 MB of JSON: ~1.4 s uncompressed). SSE is never
    // compressed here: a compressor would hold events back until its buffer fills.
    const type = String(r.headers['content-type'] ?? ''), accept = String(req.headers['accept-encoding'] ?? '')
    const big = Number(r.headers['content-length'] ?? 0) >= 1024 || !r.headers['content-length']
    const enc = type.startsWith('application/json') && big && !r.headers['content-encoding']
      ? (/\bbr\b/.test(accept) ? 'br' : /\bgzip\b/.test(accept) ? 'gzip' : null) : null
    if (!enc) {
      res.writeHead(r.statusCode ?? 502, r.headers)
      return r.pipe(res) // streams SSE through unbuffered
    }
    const out = { ...r.headers, 'content-encoding': enc, vary: 'Accept-Encoding' }
    delete out['content-length']
    res.writeHead(r.statusCode ?? 502, out)
    const z = enc === 'br' ? createBrotliCompress({ params: { [Z.BROTLI_PARAM_QUALITY]: 4 } }) : createGzip({ level: 5 })
    z.on('error', () => { release(); res.destroy() })
    r.pipe(z).pipe(res)
  })
  up.on('error', () => {
    release()
    if (!res.headersSent) res.writeHead(502, { 'Content-Type': 'application/json' })
    res.end(JSON.stringify({ error: 'journey server unavailable' }))
  })
  res.on('close', () => { release(); up.destroy() })
  up.setTimeout(180_000, () => up.destroy(new Error('upstream timeout')))
  req.pipe(up)
}

// Whether analytics accepts this request's admin cookie.
function adminOk(req) {
  return new Promise((done) => {
    const up = request({ host: ANALYTICS.host, port: ANALYTICS.port, agent: ANALYTICS.agent, path: '/api/analytics/me', timeout: 3000,
      headers: { cookie: String(req.headers.cookie ?? '') } }, (r) => { r.resume(); done(r.statusCode === 200) })
    up.on('error', () => done(false))
    up.on('timeout', () => up.destroy())
    up.end()
  })
}

// A write from a page of this site only: Origin must name the Host it was sent to.
function sameOrigin(req) {
  try { return new URL(String(req.headers.origin ?? '')).host === req.headers.host } catch { return false }
}

// Ready before anyone asks: the files are compressed when the server starts (and again when a file changes).
function pack(path, etag) {
  let packed = adminPacked.get(path)
  if (packed?.key !== etag) {
    const raw = readFile(ADMIN_FILES[path])
    packed = { key: etag, br: raw.then((b) => brotli(b, { params: { [Z.BROTLI_PARAM_QUALITY]: 5 } })), gz: raw.then((b) => gz(b, { level: 6 })) }
    packed.br.catch(() => adminPacked.delete(path))
    adminPacked.set(path, packed)
  }
  return packed
}
const adminPacked = new Map() // path -> { key, br, gz }: promises of the compressed bytes of the file version in `key`
const brotli = promisify(brotliCompress), gz = promisify(gzip)
async function sendAdminFile(req, res, path) {
  let st
  try { st = statSync(ADMIN_FILES[path]) } catch { return notFound(res) }
  const etag = `"${st.size.toString(36)}-${Math.floor(st.mtimeMs).toString(36)}"`
  const head = { 'Content-Type': TYPES['.json'], 'Cache-Control': 'private, max-age=300, stale-while-revalidate=86400', ETag: etag, 'X-Content-Type-Options': 'nosniff', Vary: 'Accept-Encoding' }
  if (req.headers['if-none-match'] === etag) { res.writeHead(304, head); return res.end() }
  const accept = String(req.headers['accept-encoding'] ?? '')
  const enc = /\bbr\b/.test(accept) ? 'br' : /\bgzip\b/.test(accept) ? 'gz' : null
  if (!enc) {
    res.writeHead(200, { ...head, 'Content-Length': st.size })
    return req.method === 'HEAD' ? res.end() : createReadStream(ADMIN_FILES[path]).pipe(res)
  }
  const body = await pack(path, etag)[enc]
  res.writeHead(200, { ...head, 'Content-Encoding': enc === 'br' ? 'br' : 'gzip', 'Content-Length': body.length })
  res.end(req.method === 'HEAD' ? undefined : body)
}

// Admin routes. `gated` ones answer 401 until analytics confirms the cookie; analytics' own routes check it themselves.
async function admin(req, res, path) {
  const write = req.method !== 'GET' && req.method !== 'HEAD'
  if (write && (req.method !== 'POST' || !sameOrigin(req))) return notFound(res)
  const gated = !path.startsWith('/api/analytics/')
  if (gated && !(await adminOk(req))) {
    res.writeHead(401, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' })
    return res.end(JSON.stringify({ error: 'unauthorized' }))
  }
  if (path in ADMIN_FILES) return sendAdminFile(req, res, path).catch(() => res.destroy())
  return proxy(req, res, path.startsWith('/api/analytics/') ? ANALYTICS : REVIEW)
}

const server = createServer((req, res) => {
  let path
  try { path = decodeURIComponent((req.url ?? '/').split('?')[0]) } catch {
    res.writeHead(400, { 'Content-Type': 'text/plain' })
    return res.end('Invalid URL')
  }
  if (path.split('/').some(part => part.startsWith('.')) || path.endsWith('.map')) return notFound(res)
  if (path.startsWith('/api/harness/') || path.startsWith('/api/auth/')) return proxy(req, res)
  if (path.startsWith('/api/analytics/') || REVIEW_API.test(path) || path in ADMIN_FILES) return admin(req, res, path)
  if (path === '/admin' || path.startsWith('/admin/')) {
    // The shell only draws the sign-in form and the screens; every number behind it needs the cookie.
    if ((req.method !== 'GET' && req.method !== 'HEAD') || extname(path) || !existsSync(resolve(DIST, 'index.html'))) return notFound(res)
    res.setHeader('X-Robots-Tag', 'noindex')
    return sendFile(req, res, resolve(DIST, 'index.html'), 'no-cache')
  }
  if (path.startsWith('/api')) return notFound(res)
  if (req.method !== 'GET' && req.method !== 'HEAD') return notFound(res)
  if (LANDING_CLIP.test(path)) {
    const file = inside(DIST, path)
    return file ? sendRange(req, res, file) : notFound(res)
  }
  for (const [mount, root] of Object.entries(MEDIA)) {
    if (!path.startsWith(mount)) continue
    const file = MEDIA_TYPES.has(extname(path).toLowerCase()) && inside(root, path.slice(mount.length - 1))
    return file ? sendFile(req, res, file, 'public, max-age=604800, stale-while-revalidate=86400') : notFound(res)
  }
  const file = inside(DIST, path)
  if (file && TYPES[extname(path).toLowerCase()]) return sendFile(req, res, file, cacheFor(path))
  if (extname(path)) return notFound(res)
  // SPA routes (/, /app/...): the shell page
  sendFile(req, res, resolve(DIST, 'index.html'), 'no-cache')
})
server.headersTimeout = 15_000
server.requestTimeout = 30_000
server.maxRequestsPerSocket = 100
server.listen(PORT, '127.0.0.1', () => {
  for (const [path, file] of Object.entries(ADMIN_FILES)) {
    try { const st = statSync(file); pack(path, `"${st.size.toString(36)}-${Math.floor(st.mtimeMs).toString(36)}"`) } catch { /* no admin data on this machine */ }
  }
  if (!existsSync(resolve(DIST, 'index.html'))) console.warn('web/dist is missing: run npm run build --prefix web')
  console.log(`TripGuardian public web: http://127.0.0.1:${PORT} (harness ${HARNESS.host}:${HARNESS.port})`)
})
