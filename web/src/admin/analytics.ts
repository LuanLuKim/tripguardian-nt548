// Private analytics server (`python -m analytics serve`, src/analytics; docs/ANALYTICS.md). Vite proxies /api/analytics.
import { useEffect, useState } from 'react'
import { early } from './prefetch'

export type Filters = { from?: string; to?: string; start_with?: string; app_version?: string }
export type Step = { key: string; label: string; journeys: number; kept: number | null; median_min: number | null; stopped: number; last_before_stop: [string, number][] }
export type Funnel = { range: [string, string]; top: { landing: number; cta: number; logins: number }; steps: Step[] }
export type DecisionNums = {
  acts: { action: string; n: number }[]
  drop_reasons: { reason: string; n: number }[]
  previews: { status: string; n: number }[]
  counts: { page_more: number; why_not: number; compare_open: number; outbound_click: number }
  ranks: { rank: number; shown: number; chosen: number }[]
  search_misses: { q: string; n: number }[]
  acts_per_journey_median: number | null
}
export type SessionRow = { id: string; stage: string; revision: number; created_at: string; updated_at: string; app_version: string | null; email: string | null; display_name: string | null; errors: number; min_score: number | null; confirmed: boolean; start_with: string | null }
export type Event = { at: string; source: string; name: string; props: Record<string, unknown>; app_version: string | null }
export type SessionDetail = {
  id: string; stage: string; revision: number; created_at: string; updated_at: string; app_version: string | null; email: string | null; name: string | null
  trip_transcript: { role: string; text: string; turn: number }[]
  decision_log: { action: Record<string, unknown>; at?: string }[]
  planning_log: { action: Record<string, unknown>; at?: string }[]
  receipts: { request_id: string; at: string | null; revision: number; stage: string; events: string[] }[]
  outputs: string[]; events: Event[]; feedback: { at: string; scores: Record<string, number>; more_search: boolean | null; more_search_for?: string[]; note: string }[]
}
export type Today = { day: string; journeys: number; confirmed: number; feedback: number; errors: number; fallbacks: number; active_users: number; new_users: number }

const qs = (f: Record<string, string | undefined>) => {
  const p = new URLSearchParams(Object.entries(f).filter((e): e is [string, string] => !!e[1]))
  return p.size ? `?${p}` : ''
}

async function read<T>(path: string, f: Record<string, string | undefined>): Promise<T> {
  const url = `/api/analytics/${path}${qs(f)}`
  const res = await (path === 'today' && !qs(f) ? early('today', url) : fetch(url))
  if (res.status === 401) window.dispatchEvent(new Event('tg-admin-401'))
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error ?? `HTTP ${res.status}`)
  return res.json()
}

// Today's row can be mounted twice in a row (the overview screen redraws when its numbers arrive): one read serves both.
let todayRead: { at: number; p: Promise<unknown> } | null = null

export function get<T>(path: string, f: Record<string, string | undefined> = {}): Promise<T> {
  if (path !== 'today' || qs(f)) return read<T>(path, f)
  if (!todayRead || Date.now() - todayRead.at > 5000) {
    const p = read<T>(path, f)
    todayRead = { at: Date.now(), p }
    p.catch(() => (todayRead = null))
  }
  return todayRead.p as Promise<T>
}

// { data, error } for one analytics read; reloads when `key` changes.
export function useAnalytics<T>(path: string, f: Record<string, string | undefined> = {}) {
  const key = path + qs(f)
  const [state, setState] = useState<{ key: string; data?: T; error?: string }>({ key })
  useEffect(() => {
    let live = true
    get<T>(path, f).then((data) => live && setState({ key, data }), (e: Error) => live && setState({ key, error: e.message }))
    return () => { live = false }
  }, [key]) // eslint-disable-line react-hooks/exhaustive-deps
  return state.key === key ? state : { key }
}

export const fmtTime = (s: string | null | undefined) => (s ? new Date(s).toLocaleString('vi-VN', { dateStyle: 'short', timeStyle: 'short' }) : '—')
export const pct = (x: number | null) => (x == null ? '—' : `${Math.round(x * 100)}%`)

// Người dùng (src/analytics/users.py): numbers per person, not per journey.
export type Kpi = { n: number; prev: number | null }
export type Day = { day: string; accounts: number; guests: number; journeys: number; confirmed: number }
export type Rung = { key: string; label: string; n: number; kept: number | null }
export type Cohort = { week: string; size: number; cells: (number | null)[] }
export type Feature = { key: string; label: string; group: string; uses: number | null; people: number }
type Share = { n: number; of: number }
export type UsersOverview = {
  range: [string, string]; test: boolean
  kpis: Record<'accounts' | 'new_accounts' | 'active_accounts' | 'returning' | 'guest_sessions' | 'guest_adopted' | 'journeys' | 'confirmed' | 'with_errors', Kpi> & { guests_alive: number }
  daily: Day[]; ladder: Rung[]; cohorts: Cohort[]; features: Feature[]
  profile: { of: number; login: Record<'google' | 'password' | 'both' | 'none', number>; fields: Record<'nickname' | 'avatar' | 'home_city' | 'usual_mobility' | 'usual_companions', number>; remember: number; terms: number }
  gaps: {
    never_journey: Share; never_confirm: Share; one_day: Share; guests: Share; low_feedback: Share; no_prior: Share
    errors: Share & { top: { name: string; n: number; people: number }[] }
    unused: string[]; search_misses: { n: number }
  }
}
export type PersonType = 'account' | 'guest'
export type PersonRow = {
  id: string; type: PersonType; status: string; test: boolean; email: string | null; name: string | null; nickname: string | null
  login: 'google' | 'password' | 'both' | 'none'; created_at: string; last_seen: string | null; active_days: number
  active_in_range: boolean; new_in_range: boolean; journeys: number; confirmed: number; furthest: number
  errors: number; errors_in_range: number; feedback: number; min_score: number | null
}
export type PersonDetail = PersonRow & {
  last_login_at: string | null; deleted_at: string | null
  profile: { home_city: string | null; usual_mobility: string | null; usual_companions: string | null; avatar: boolean; remember: boolean; terms: string | null }
  reached: string[]; features: { key: string; label: string; group: string; uses: number }[]
  counts: Record<'saved' | 'friends' | 'messages' | 'shared' | 'trips' | 'checkins' | 'notified' | 'opened', number>
  daily: { day: string; n: number }[]
  journey_list: { id: string; stage: string; revision: number; created_at: string; updated_at: string; confirmed: boolean; errors: number; min_score: number | null }[]
  feedback_list: { at: string; journey_id: string; scores: Record<string, number>; more_search_for: string[] | null; note: string }[]
  events: { at: string; name: string; journey_id: string | null; props: Record<string, unknown> }[]
}

// Xu hướng (src/analytics/trends.py): counts of journeys per place, plans, and what people ask Trip for.
export type Count = { key: string | number; n: number }
export type TrendPlace = {
  place_id: string; name: string | null; recent: number; before: number
  shown: number; viewed: number; chosen: number; liked: number; dropped: number; outbound: number; checked_in: number; saved: number; planned: number; chosen_seen: number
}
type Pair = { a: string; b: string; n: number; a_name: string | null; b_name: string | null }
export type Trends = {
  range: [string, string]; test: boolean; recent_from: string; places: TrendPlace[]
  plans: { trips: number; stops: number; days: Count[]; per_day_median: number | null; hours: { key: number; n: number }[]; weekdays: number[]; lead_median: number | null; pairs: Pair[]; chains: Pair[] }
  intent: Record<'companions' | 'people' | 'days' | 'mobility' | 'purpose' | 'budget' | 'months' | 'start_weekday' | 'interests' | 'groups' | 'kinds' | 'dishes' | 'vibes', Count[]> & { journeys: number }
  themes: Count[]; searches: { q: string; n: number; misses: number }[]; drop_reasons: Count[]
}
