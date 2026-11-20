import type { LodgingCandidate } from '../planning/types'
import type { Action, ActResult, Card, CompareResult, PlanPreview, SearchResult, TripSummary, TurnHandlers, View, WhyNot } from './types'
import { setScenePhotos } from '../../data/store'
import { FORGET_EVENT } from '../account'
import { acceptsRevision, json, loadJourney, mutateJourney, readJourney, resumeJourney, type JourneyView } from '../journey'
export { JourneyError as DecisionError } from '../journey'
// Cards bring their scene photos (no people, one per scene); every list the screens read goes through here, so PlacePhoto,
// the disc and the sheet show them before the place's cover gallery. Cards without photos change nothing.
export const withPhotos = <T extends { view?: View; cards?: Card[] }>(r: T): T => {
  const cards = [...(r.cards ?? []), ...(r.view?.groups.flatMap((g) => g.cards) ?? []), ...(r.view?.unverified?.cards ?? [])]
  for (const c of cards) setScenePhotos(c.id, c.photos)
  return r
}
// Understand starts the first read of this stage the moment it has advanced, so the screen finds it on arrival instead of
// asking after the route changed. A journey that has just advanced has nothing to recover, so that step is skipped too.
const primed = new Map<string, Promise<JourneyView>>()
export const primeDecision = (id: string, view?: JourneyView | Promise<JourneyView>) => {
  const read = view ? Promise.resolve(view) : loadJourney(id, 'decision')
  read.catch(() => {})
  primed.set(id, read)
  setTimeout(() => primed.delete(id), 30_000)
}
const loading = new Map<string, ReturnType<typeof readDecision>>()
export const loadDecision = (id: string) => {
  const existing = loading.get(id)
  if (existing) return existing
  const request = readDecision(id).finally(() => { if (loading.get(id) === request) loading.delete(id) })
  loading.set(id, request)
  return request
}
const readDecision = async (id: string) => {
  const early = primed.get(id)
  primed.delete(id)
  if (early) {
    try {
      const j = await early
      if (acceptsRevision(id, j.revision)) return withPhotos({ ...(j.result as { view: View }), id: j.id, stage: j.stage, recoveredHandoff: undefined })
    } catch { /* the full path below reads it again and reports the error */ }
  }
  const recovery = await resumeJourney(id, 'decision')
  const j = recovery.view
  return withPhotos({ ...(j.result as {view: View}), id: j.id, stage: j.stage, recoveredHandoff: recovery.recoveredOperation === 'advance' && j.stage === 'planning' && recovery.recoveredView?.stage === 'planning' ? recovery.recoveredView : undefined })
}
export const act = async (id: string, a: Action) => withPhotos((await mutateJourney(id, 'decision', 'act', a)).result as ActResult)
export const compare = (id: string, a: string, b: string) => readJourney<CompareResult>(id, `decision/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`)
// Page n (1 = first) of one tab; without n the next page.
export const gotoPage = (id: string, group: string, n?: number) => readJourney<{ view: View }>(id, `decision/page?group=${encodeURIComponent(group)}${n ? `&n=${n}` : ''}`).then(withPhotos)
export const searchList = (id: string, q: string) => readJourney<SearchResult>(id, `decision/search?q=${encodeURIComponent(q)}`).then(withPhotos)
export const whyNot = (id: string, place: string) => readJourney<WhyNot>(id, `decision/why-not?place=${encodeURIComponent(place)}`)
// A reply's view replaces the one on screen, so its cards bring their scene photos here too (a card first seen in a reply had none).
export async function sendText(id: string, text: string, h: TurnHandlers): Promise<void> {
  const on = { ...h, view: (r: Parameters<NonNullable<TurnHandlers['view']>>[0]) => { withPhotos(r); h.view?.(r) } }
  await mutateJourney(id, 'decision', 'turn', {text}, on as Record<string, ((d: any) => void) | undefined>)
}
// Served stays around the places chosen so far, ranked by Planning; "empty" until a place is chosen.
// Every served stay, one page at a time (`total` of them): those around the chosen places first.
export const lodgingOptions = (id: string, offset = 0) => readJourney<{ status: 'empty' | 'ready' | 'unavailable'; candidates: LodgingCandidate[]; total?: number }>(id, `decision/lodging?offset=${offset}`)
export const previewPlan = (id: string) => fetch(`/api/harness/sessions/${id}/preview`).then(json<PlanPreview>)
// The last list the server gave, so the chat history and the calendar paint at once on every visit and refresh behind it.
let kept: TripSummary[] | null = null
export const keptTripSummaries = () => kept
if (typeof window !== 'undefined') addEventListener(FORGET_EVENT, () => { kept = null })
export const deleteTrip = (id: string) => fetch(`/api/harness/sessions/${id}`, { method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: '{}' }).then(json<{ deleted: boolean }>).then((r) => { kept = kept?.filter((t) => t.id !== id) ?? null; return r })
export const tripSummaries = () => fetch('/api/harness/trips').then(json<TripSummary[]>).then((l) => (kept = l))
