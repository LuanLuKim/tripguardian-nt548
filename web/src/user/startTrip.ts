import { useSyncExternalStore } from 'react'
import { createJourney, JourneyError, loadJourneyState, mutateJourney, type JourneyView } from './journey'
import { primeDecision } from './pd/api'
import type { Action, TripState } from './trip'
import { fromSearchInput } from './tu/adapter'
import { sendTurn } from './tu/api'
import type { SearchInput } from './tu/types'

// There is no separate chat screen: a trip starts straight on Lựa chọn. The journey is created, compiled with whatever is known
// (unknowns ride along as unknowns: Trip's "show"), and stepped on to Place Decision; the chat beside the lists then refines it.
// One start at a time: the home's button, its search box, a theme and the home chat's first message all wait on the same one.

let starting: Promise<string> | null = null
const subs = new Set<() => void>()
const changed = () => subs.forEach((f) => f())
export const useStarting = () => useSyncExternalStore((f) => { subs.add(f); return () => { subs.delete(f) } }, () => !!starting)

type Dispatch = (a: Action) => void

// A journey still in the chat stage (a new one, or an old chat from before) moves on to Lựa chọn. Only an open health hint the user
// raised stops it: that question is answered in the chat, and the journey stays where it is.
async function toDecision(id: string): Promise<JourneyView> {
  try { return await mutateJourney(id, 'trip', 'advance') } catch (e) {
    if (!(e instanceof JourneyError && e.status === 409)) throw e
  }
  let ready = false
  await sendTurn(id, { kind: 'show' }, { done: () => { ready = true } })
  if (!ready) throw new JourneyError(409, 'health_hint_open')
  return mutateJourney(id, 'trip', 'advance')
}

function settle(dispatch: Dispatch, j: JourneyView) {
  const si = j.outputs?.trip as SearchInput | undefined
  dispatch({ type: 'set', patch: { ...(si ? fromSearchInput(si) : {}), journeyId: j.id, decisionId: j.id, planningId: null } })
  primeDecision(j.id, j)
}

function once(run: () => Promise<string>): Promise<string> {
  if (starting) return starting
  starting = run().finally(() => { starting = null; changed() })
  changed()
  return starting
}

// A new trip: the current one stays in Chuyến của tôi. `first` is said in the chat once the lists are there (the home's words, a theme,
// the tags picked on "Khám phá nơi muốn đến").
export function startTrip(dispatch: Dispatch, patch: Partial<Pick<TripState, 'experience' | 'startText'>> = {}): Promise<string> {
  dispatch({ type: 'reset' })
  dispatch({ type: 'set', patch })
  return once(async () => {
    const created = await createJourney(patch.experience ?? null, null)
    dispatch({ type: 'set', patch: { journeyId: created.id } })
    const j = await toDecision(created.id)
    settle(dispatch, j)
    return j.id
  })
}

// An existing journey opened at Lựa chọn: one still in the chat stage is stepped on first.
export function resumeTrip(dispatch: Dispatch, id: string): Promise<string> {
  return once(async () => {
    const state = await loadJourneyState(id)
    if (state.stage !== 'trip') { dispatch({ type: 'set', patch: { journeyId: id, decisionId: id, planningId: state.stage === 'planning' ? id : null } }); return id }
    const j = await toDecision(id)
    settle(dispatch, j)
    return j.id
  })
}

export const tripStarting = () => starting
