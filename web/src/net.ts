// One network layer under every call the app makes to its own server (/api/harness/*, /api/auth/*), installed once in main.tsx:
// - a GET already on its way is not sent twice: every screen asking for the same URL at the same moment shares its answer;
// - the lists many screens read (the account, saved places, trips, inbox, friends, the bulletin) are reused for a few seconds,
//   so moving between screens paints from what the page already holds instead of asking again; any write drops them;
// - a 429 (this person's per-minute budget, config/security.yaml http.per_user_minute) is not an error to show: the call waits
//   the seconds the server names (Retry-After) and goes again, since a refused call was never run.
// Answers are handed out as clones, so each caller reads its own body.

const OWN = /^\/api\/(harness|auth)\//
const REUSE_MS = 4000
const REUSED = [/^\/api\/harness\/me$/, /^\/api\/harness\/me\/library$/, /^\/api\/harness\/trips$/, /^\/api\/harness\/notifications$/,
  /^\/api\/harness\/friends$/, /^\/api\/harness\/pulse$/, /^\/api\/harness\/tags\/trending$/, /^\/api\/harness\/calendar$/]
const STREAM = /\/events$|\/typing$/ // server-sent events and the friend's "..." poll: always live
const MAX_WAIT_S = 30 // past this the person sees the error instead of a frozen button
const RETRIES = 2

type Entry = { at: number; answer: Promise<Response> }

export function installNet(win: Window & typeof globalThis = window) {
  const raw = win.fetch.bind(win)
  const inflight = new Map<string, Promise<Response>>()
  const recent = new Map<string, Entry>()

  const patient = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const again = input instanceof Request ? input.clone() : input
    for (let n = 0; ; n++) {
      const res = await raw(n ? (again instanceof Request ? again.clone() : again) : input, init)
      if (res.status !== 429 || n >= RETRIES) return res
      const wait = Number(res.headers.get('Retry-After')) || 2
      if (wait > MAX_WAIT_S) return res
      await new Promise((done) => setTimeout(done, wait * 1000))
    }
  }

  win.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(input instanceof Request ? input.url : String(input), win.location.href)
    if (url.origin !== win.location.origin || !OWN.test(url.pathname)) return raw(input, init)
    const method = (init?.method ?? (input instanceof Request ? input.method : 'GET')).toUpperCase()
    if (method !== 'GET' || init?.body) {
      recent.clear() // a write may change any list
      return patient(input, init)
    }
    if (STREAM.test(url.pathname) || init?.signal || (init?.headers && new Headers(init.headers).get('Accept')?.includes('event-stream'))) return patient(input, init)
    const key = url.pathname + url.search
    const now = Date.now()
    const kept = recent.get(key)
    if (kept && now - kept.at < REUSE_MS) return kept.answer.then((r) => r.clone())
    const going = inflight.get(key)
    if (going) return going.then((r) => r.clone())
    const answer = patient(input, init)
    inflight.set(key, answer)
    answer.then((r) => {
      if (r.ok && REUSED.some((re) => re.test(url.pathname))) recent.set(key, { at: Date.now(), answer })
    }, () => {}).finally(() => { if (inflight.get(key) === answer) inflight.delete(key) })
    return answer.then((r) => r.clone())
  }
}

if (typeof window !== 'undefined' && typeof window.fetch === 'function') installNet()
