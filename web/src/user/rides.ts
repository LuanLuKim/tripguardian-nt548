// Grab / Be / Xanh SM fares for the legs between stops: GET /api/harness/rides (src/journey/rides.py, table config/rides_tariffs.json).
// Estimates from each brand's published tariff, never a quote; a brand with no table for the city has no price here, not a guess.
// The user compares the brands on every leg and picks one brand and one kind of vehicle once: the choice holds for the whole trip.
import { useCallback, useEffect, useMemo, useState, useSyncExternalStore } from 'react'
import { info } from './lib'
import type { ItineraryDay } from './planning/types'

export interface RideQuote {
  brand: string; service: string | null; label: string; vehicle: 'motorbike' | 'car' | null; seats: number | null
  vnd_min: number | null; vnd_max: number | null; reason?: string
}
export interface RideLeg { km: number; minutes: number | null; region: string | null; region_name: string | null; quotes: RideQuote[] }
export interface RideBrand { name: string; source: string; as_of: string; note: string | null }
export interface RideData { legs: RideLeg[]; brands: Record<string, RideBrand> }
export type RideKind = 'bike' | 'car'
export interface RidePrice { brand: string; label: string; count: number; lo: number; hi: number }

interface Pref { brand: string | null; kind: RideKind | null }
const KEY = 'tg.ride.v1'
const readPref = (): Pref => {
  try { const p = JSON.parse(localStorage.getItem(KEY) ?? 'null'); if (p && typeof p === 'object') return { brand: typeof p.brand === 'string' ? p.brand : null, kind: p.kind === 'bike' || p.kind === 'car' ? p.kind : null } } catch { /* nothing stored */ }
  return { brand: null, kind: null }
}
let pref: Pref = readPref()
const subs = new Set<() => void>()
const setPref = (patch: Partial<Pref>) => {
  pref = { ...pref, ...patch }
  try { localStorage.setItem(KEY, JSON.stringify(pref)) } catch { /* private mode: lasts until reload */ }
  subs.forEach((f) => f())
}
const usePref = () => useSyncExternalStore((cb) => { subs.add(cb); return () => subs.delete(cb) }, () => pref)

// One leg = the travel items up to a visit; walked legs are not priced.
interface LegReq { id: string; day: number; km: number; minutes: number | null; lat: number; lng: number }
function legsOf(days: ItineraryDay[]): LegReq[] {
  const out: LegReq[] = []
  for (const d of days) {
    let km = 0, min = 0, ride = false
    for (const it of d.items) {
      if (it.kind === 'travel') { km += it.distance_km ?? 0; min += it.road_min ?? 0; ride = ride || (it.mode !== 'walk' && (it.distance_km ?? 0) > 0) }
      else if (it.kind === 'visit' && it.place_id) {
        const p = info(it.place_id)
        if (ride && km > 0 && p) out.push({ id: `${d.day}:${it.place_id}`, day: d.day, km, minutes: min || null, lat: p.lat, lng: p.lng })
        km = 0; min = 0; ride = false
      }
    }
  }
  return out
}

export const fmtK = (v: number) => `${Math.round(v / 1000)}k`
export const fmtRange = (lo: number, hi: number) => (fmtK(lo) === fmtK(hi) ? `≈ ${fmtK(lo)}` : `≈ ${fmtK(lo)}–${fmtK(hi)}`)

// A brand's price for the group on one leg: bikes one per person; cars the cheapest of the brand's services for the group
// (a 4-seat taxi, a saver car, two cars or one 7-seater, whichever costs least in total).
export function priceOf(quotes: RideQuote[], brand: string, kind: RideKind, people: number): RidePrice | null {
  const rows = quotes.filter((q) => q.brand === brand && q.service && q.vnd_min != null && q.vnd_max != null && q.vehicle === (kind === 'bike' ? 'motorbike' : 'car'))
  let best: RidePrice | null = null
  for (const q of rows) {
    const count = kind === 'bike' ? people : Math.max(1, Math.ceil(people / (q.seats ?? 1)))
    const p = { brand, label: q.label, count, lo: q.vnd_min! * count, hi: q.vnd_max! * count }
    if (!best || p.lo < best.lo) best = p
  }
  return best
}

// One transfer of a way in (home -> airport / station, airport / station -> lodging): the user's brand when it prices the leg,
// else the cheapest brand that does (named, so the user sees whose price it is); null when no brand prices it.
export interface LegPick extends RidePrice { name: string; fallback: boolean }
export function pickFor(leg: RideLeg, brands: Record<string, RideBrand>, brand: string | null, kind: RideKind, people: number): LegPick | null {
  const mine = brand && brands[brand] ? priceOf(leg.quotes, brand, kind, people) : null
  if (mine) return { ...mine, name: brands[brand!].name, fallback: false }
  const any = Object.keys(brands).map((b) => priceOf(leg.quotes, b, kind, people)).filter((p): p is RidePrice => !!p).sort((a, b) => a.lo - b.lo)[0]
  return any ? { ...any, name: brands[any.brand].name, fallback: !!brand } : null
}

// The brand and kind of vehicle the user picked (tg.ride.v1) for a group of `people`: the way in uses the same choice as the stops.
export function useRideChoice(people: number | null) {
  const p = usePref()
  const n = Math.min(Math.max(people ?? 1, 1), 20)
  return { brand: p.brand, kind: (p.kind ?? (n <= 2 ? 'bike' : 'car')) as RideKind, people: n }
}

// Why a brand has no price on a leg: no published table where the leg starts, or a table without this kind of vehicle.
export function missingOf(quotes: RideQuote[], brand: string): 'no_table' | 'no_kind' {
  return quotes.some((q) => q.brand === brand && q.service) ? 'no_kind' : 'no_table'
}

export function useRides(days: ItineraryDay[], on: boolean, people: number | null) {
  const p = usePref()
  const n = Math.min(Math.max(people ?? 1, 1), 20)
  const kind: RideKind = p.kind ?? (n <= 2 ? 'bike' : 'car')
  const legs = useMemo(() => (on ? legsOf(days) : []), [days, on])
  const key = legs.map((l) => `${l.km.toFixed(1)}:${l.minutes ?? ''}:${l.lat.toFixed(4)}:${l.lng.toFixed(4)}`).join(';')
  const [got, setGot] = useState<{ key: string; data: RideData | null } | null>(null)
  useEffect(() => {
    if (!key) return
    let live = true
    fetch(`/api/harness/rides?legs=${encodeURIComponent(key)}`).then((r) => (r.ok ? (r.json() as Promise<RideData>) : null))
      .then((data) => { if (live) setGot({ key, data }) }).catch(() => { if (live) setGot({ key, data: null }) })
    return () => { live = false }
  }, [key])
  const data = got && got.key === key ? got.data : null
  const brands = data?.brands ?? {}
  const byId = useMemo(() => new Map(legs.map((l, i) => [l.id, data?.legs[i] ?? null] as const)), [legs, data])
  const legFor = useCallback((day: number, place: string) => byId.get(`${day}:${place}`) ?? null, [byId])
  const rowsFor = useCallback((leg: RideLeg) => Object.keys(brands).map((b) => ({ brand: b, name: brands[b].name, price: priceOf(leg.quotes, b, kind, n), missing: missingOf(leg.quotes, b) })), [brands, kind, n])
  // A brand's total over some legs; null when it has no price on one of them (a partial total would understate it).
  const total = useCallback((brand: string, day?: number) => {
    let lo = 0, hi = 0, any = false
    for (const [i, l] of legs.entries()) {
      if (day != null && l.day !== day) continue
      const pr = data?.legs[i] ? priceOf(data.legs[i].quotes, brand, kind, n) : null
      if (!pr) return null
      lo += pr.lo; hi += pr.hi; any = true
    }
    return any ? { lo, hi } : null
  }, [legs, data, kind, n])
  const chosen = p.brand && brands[p.brand] ? p.brand : null
  const gaps = (day?: number) => {
    const out = { no_table: [] as string[], no_kind: [] as string[] }
    for (const b of Object.keys(brands)) {
      if (total(b, day)) continue
      const i = legs.findIndex((l, k) => (day == null || l.day === day) && data?.legs[k] && !priceOf(data.legs[k].quotes, b, kind, n))
      if (i >= 0 && data?.legs[i]) out[missingOf(data.legs[i].quotes, b)].push(brands[b].name)
    }
    return out
  }
  const cheapest = (day?: number) => Object.keys(brands).map((b) => ({ b, t: total(b, day) })).filter((x) => x.t).sort((a, b) => a.t!.lo - b.t!.lo)[0]?.b ?? null
  return {
    ready: !!data && legs.length > 0, brands, kind, people: n, chosen, legFor, rowsFor, total, cheapest, gaps,
    pickBrand: (b: string | null) => setPref({ brand: b }), pickKind: (k: RideKind) => setPref({ kind: k }),
  }
}
export type Rides = ReturnType<typeof useRides>
