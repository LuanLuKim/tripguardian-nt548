// The way in and out of the city: GET /api/harness/journey (options from home) and /api/harness/booking/offers (links and
// prices a provider states). Fields mirror src/journey/types.py and src/booking/types.py; null means "not known", never a guess.

export interface Offer {
  offer_id: string; provider: string; kind: 'coach' | 'flight' | 'stay'; mode: string
  url: string | null; price_vnd: number | null; price_unit: string | null; price_night_vnd: number | null
  available: boolean | null; observed_at: string | null; source: string | null; carrier: string | null
  depart_at: string | null; arrive_at: string | null; from_point: string | null; to_point: string | null
  stay_dates: [string, string] | null
  // Added by the flights crawl: kept optional, shown only when present.
  flight_no?: string | null; stops?: number | null; duration_min?: number | null; fetched_at?: string | null
}
export interface Leg {
  kind: 'drive' | 'transfer' | 'flight'; from_label: string; to_label: string; minutes: number | null
  distance_km: number | null; via?: string | null; coords: [number, number][] | null; source: string | null; fetched_at: string | null
}
export interface WayOption {
  mode: 'car' | 'motorbike' | 'bus' | 'plane'; feasible: boolean | null; reason: string; legs: Leg[]
  minutes: number | null; price_min_vnd: number | null; price_max_vnd: number | null; offers: Offer[]
  tradeoff?: string | null
}
export interface Journey {
  origin: [number, number]; dest: [number, number]; dest_is_centre: boolean; way: 'inbound' | 'outbound'; day: string | null
  options: WayOption[]
}

const get = async <T>(path: string, params: Record<string, string | number | undefined | null>): Promise<T> => {
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== '') q.set(k, String(v))
  const res = await fetch(`/api/harness/${path}?${q}`)
  if (!res.ok) throw new Error(`${path} ${res.status}`)
  return res.json()
}

export const readJourneyWay = (p: { lat: number; lng: number; date?: string | null; way: 'inbound' | 'outbound'; dest_lat?: number | null; dest_lng?: number | null }) =>
  get<Journey>('journey', p)
export const readStayOffers = (p: { fid: string; check_in: string; nights: number }) =>
  get<{ offers?: Offer[] }>('booking/offers', { kind: 'stay', ...p }).then((r) => r.offers ?? [])

// How old a crawled price is, in words ("vừa cập nhật", "3 giờ trước"); null when the offer states no time.
export const offerAge = (o: Pick<Offer, 'observed_at' | 'fetched_at'>, now = Date.now()): string | null => {
  const t = Date.parse(o.observed_at ?? o.fetched_at ?? '')
  if (Number.isNaN(t)) return null
  const h = Math.floor((now - t) / 3_600_000)
  if (h < 1) return 'vừa cập nhật'
  return h < 48 ? `${h} giờ trước` : `${Math.floor(h / 24)} ngày trước`
}
// An offer the provider states with a time or a price (a bare search link has neither).
export const isDated = (o: Offer) => Boolean(o.depart_at || o.price_vnd != null)
