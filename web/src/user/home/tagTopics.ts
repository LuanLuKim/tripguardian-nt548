export type Sub = { id: string; label: string; count: number }

const subs = new Map<string, Promise<Sub[]>>()
// The kinds inside one tag (GET /api/harness/tags?ref=<axis>:<key>, docs/PLACE_DECISION.md §20); nothing is computed here.
// A tag nothing splits (or a call that failed) has no subtags: the theme alone is the pick.
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
