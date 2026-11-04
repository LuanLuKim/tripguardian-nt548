import { THEMES } from './themes'

// The tags the "Kể chuyến đi" dialog offers and the subtags under each one (docs/PLACE_DECISION.md §Tag và subtag).
// Both come from the harness, nothing is computed here: GET /api/harness/tags/trending (tags people post about now, each with
// the cover photo of its most posted places) and GET /api/harness/tags?ref=<axis>:<key> (the tag split into subtags).
export type Topic = { ref: string; label: string; cover: string | null }
export type Sub = { id: string; label: string; count: number }

const MAX = 8
const WANT = 4 // fewer topics than this is no menu: the fixed ones below take over

// When the daily job never wrote tags (or they are too old): the home's own themes, each tied to the tag it stands for.
const FALLBACK: Topic[] = ([
  ['experience:cloud_hunting', 'Săn mây', 'cloud'], ['category:cafe', 'Quán cà phê', 'cafe'], ['experience:nature', 'Thiên nhiên, rừng thông', 'pine'],
  ['experience:sunset_view', 'Ngắm hoàng hôn, bình minh', 'lake'], ['experience:weather_exposed=sheltered', 'Có mái che, trú mưa', 'rain'],
] as const).map(([ref, label, theme]) => ({ ref, label, cover: THEMES.find((t) => t.id === theme)?.photo ?? null }))

let topics: Promise<Topic[]> | null = null
export function loadTopics(): Promise<Topic[]> {
  topics ??= fetch('/api/harness/tags/trending')
    .then((r) => (r.ok ? r.json() : null))
    .then((j: { tags?: { ref: string; label: string; cover?: string[] }[] } | null) => {
      const list = (j?.tags ?? []).slice(0, MAX).map((t) => ({ ref: t.ref, label: t.label, cover: t.cover?.[0] ?? null }))
      return list.length >= WANT ? list : FALLBACK
    }, () => FALLBACK)
  return topics
}

const subs = new Map<string, Promise<Sub[]>>()
// A tag nothing splits (or a call that failed) has no subtags: the tag alone is the pick.
export function loadSubs(ref: string): Promise<Sub[]> {
  let hit = subs.get(ref)
  if (!hit) {
    hit = fetch(`/api/harness/tags?ref=${encodeURIComponent(ref)}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((j: { block?: { subtags?: { id: string; label: string; count: number }[] } } | null) => (j?.block?.subtags ?? []).map((s) => ({ id: s.id, label: s.label, count: s.count })),
        () => { subs.delete(ref); return [] })
    subs.set(ref, hit)
  }
  return hit
}
