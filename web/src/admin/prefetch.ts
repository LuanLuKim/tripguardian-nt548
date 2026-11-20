// The reads index.html starts for /admin before any script has loaded (window.__adminPre). A reader takes its answer
// once; later reads, and any read the early request failed, go to the network as usual.
type Pre = Record<string, Promise<Response | void> | undefined>

// After a sign-in the early answers (read before it, so 401) are stale: drop them.
export function forgetEarly() {
  delete (window as unknown as { __adminPre?: Pre }).__adminPre
}

export function early(key: 'me' | 'overview' | 'today', url: string): Promise<Response> {
  const pre = (window as unknown as { __adminPre?: Pre }).__adminPre
  const taken = pre?.[key]
  if (pre) pre[key] = undefined
  return (taken ?? Promise.resolve()).then((r) => r ?? fetch(url))
}
