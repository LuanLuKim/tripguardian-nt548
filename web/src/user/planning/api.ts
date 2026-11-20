import type { Action, ActPreview, ActResult, DayRoute, PlanOutput, ProgressEvent, Suggestions, TurnHandlers, View } from './types'
import type { TurnInput } from '../tu/types'
import { acceptsRevision, loadJourney, mutateJourney, readJourney, resumeJourney, type JourneyView } from '../journey'
import { setOptimized, type OptimizeParts } from '../store'
import { JourneyError } from '../journey'
export { JourneyError as PlanningError }
// Lựa chọn starts the first read of this stage the moment it has advanced (see pd/api primeDecision): no resume step, no wait for the route.
const primed = new Map<string, Promise<JourneyView>>()
export const primePlanning = (id: string, view?: JourneyView) => {
  const read = view ? Promise.resolve(view) : loadJourney(id, 'planning')
  read.catch(() => {})
  primed.set(id, read)
  setTimeout(() => primed.delete(id), 30_000)
}
const loading = new Map<string, ReturnType<typeof readPlanning>>()
export const loadPlanning = (id: string) => {
  const existing = loading.get(id)
  if (existing) return existing
  const request = readPlanning(id).finally(() => { if (loading.get(id) === request) loading.delete(id) })
  loading.set(id, request)
  return request
}
const readPlanning = async (id: string) => {
  const early = primed.get(id)
  primed.delete(id)
  let j: JourneyView | undefined
  if (early) j = await early.catch(() => undefined) // the full read below reports a real error
  if (j && !acceptsRevision(id, j.revision)) j = undefined
  if (!j) j = (await resumeJourney(id, 'planning')).view
  return { ...(j.result as {view: View}), id: j.id, revision: j.revision }
}
export const act = async (id: string, a: Action) => { const j = await mutateJourney(id, 'planning', 'act', a); return { ...(j.result as ActResult), revision: j.revision } }
// One typed message to the Lịch trình assistant: the client sends only the text (the harness adds the trip session). The
// plan the turn leaves comes back as the journey's result, with the revision to accept it under.
export const sendText = async (id: string, text: string, h: TurnHandlers) => {
  const j = await mutateJourney(id, 'planning', 'turn', { text }, h as Record<string, ((d: any) => void) | undefined>) // eslint-disable-line @typescript-eslint/no-explicit-any
  return { ...(j.result as { view: View }), revision: j.revision }
}
// THE chat on Lịch trình (planning.trip, docs/PLACE_DECISION.md §19 "Một khung chat"): the result is the schedule, changed or not.
export const sendChat = async (id: string, input: TurnInput, h: Record<string, ((d: any) => void) | undefined>) => { // eslint-disable-line @typescript-eslint/no-explicit-any
  const j = await mutateJourney(id, 'planning', 'trip', input, h)
  return { ...(j.result as { view?: View }), revision: j.revision }
}
export const readSuggestions = (id: string) => readJourney<Suggestions & { revision: number }>(id, 'planning/suggestions')
export const previewAct = (id: string, action: Action) => readJourney<ActPreview & { revision: number }>(id, `planning/preview-act?action=${encodeURIComponent(JSON.stringify(action))}`)
export const readRoutes = (id: string) => readJourney<{ days: DayRoute[] }>(id, 'planning/routes')
export { acceptsRevision }
export const confirm = async (id: string) => (await mutateJourney(id, 'planning', 'confirm')).result as PlanOutput
// GET + SSE: this route takes no body, so the native EventSource works (unlike /turn above).
export function watchLodging(id: string, onEvent: (e: { event: 'progress' | 'view' | 'done' | 'error'; data: unknown; revision: number }) => void) {
  const es = new EventSource(`/api/harness/sessions/${id}/planning/lodging/events`)
  let active = true
  const path = location.pathname + location.search
  const forward = (ev: MessageEvent) => {
    if (!active || path !== location.pathname + location.search || !ev.data) return
    const envelope = JSON.parse(ev.data)
    if (envelope.stage === 'planning' && acceptsRevision(id, envelope.revision)) onEvent({ event: envelope.event, data: envelope.data, revision: envelope.revision })
  }
  es.addEventListener('event', forward as EventListener)
  es.onerror = () => es.close() // the server closes the stream itself once done/error fires; a transport drop just stops silently
  return () => { active = false; es.close() }
}

export type { ProgressEvent }

const travelOf = (v: View) => {
  const chosen = v.variants.find((x) => x.id === v.state.chosen_variant) ?? v.variants[0]
  return v.travel_load ? v.travel_load.reduce((n, d) => n + d.travel_min, 0) : chosen?.metrics.travel_min ?? 0
}
// One proposal from the Planning Agent over the deterministic baseline; the server keeps it only when it is valid and
// not worse (docs/PLANNING.md). Remembers the before / after travel so Lịch trình can say what changed and offer undo.
export type OptimizeScope = 'keep_mine' | 'all'
// "Tối ưu lịch": the server's deterministic search (planning/optimize.py). keep_mine leaves the places the user moved and
// the days they ordered as they are; all may change them too.
export async function runRecommend(id: string, before: View | null, scope: OptimizeScope = 'keep_mine') {
  try {
    const j = await mutateJourney(id, 'planning', 'recommend', { scope })
    const r = { ...(j.result as { view: View; proposal: { status: 'accepted' | 'fallback'; diagnostics: string[]; changed?: boolean; before?: OptimizeParts; after?: OptimizeParts } }), revision: j.revision }
    const p = r.proposal
    const base = p.before ? p.before.travel_min : before && before.variants.length ? (before.state.chosen_variant ? travelOf(before) : before.variants[0].metrics.travel_min) : travelOf(r.view)
    setOptimized(id, { status: p.status, before: base, after: p.after ? p.after.travel_min : travelOf(r.view), diagnostics: p.diagnostics, seen: false,
      changed: p.changed, parts: p.before && p.after ? { before: p.before, after: p.after } : undefined })
    return r
  } catch (e) {
    if (e instanceof JourneyError) throw e // the caller tells a busy / failing server from a plain "no better layout"
    return null
  }
}
