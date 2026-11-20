import { useEffect, useState } from 'react'
import { isDated, offerAge, readJourneyWay, readStayOffers, type Journey, type Offer, type WayOption } from '../../booking'
import { track } from '../../events'
import { fmtMin, fmtVnd } from '../../lib'
import { pickFor, useRideChoice, type RideBrand } from '../../rides'
import { Icon, type IconName } from '../../ui/icons'
import '../../css/wayin.css'
import '../../css/fixes.css'

// "Phương tiện lên Đà Lạt" / "Phương tiện về": the ways from home to the city (GET /api/harness/journey), the road ones timed by the map,
// a coach or flight stated only as far as a provider states it. Anything unknown says "chưa rõ"; a buy button opens the provider's own page.

const MODE: Record<WayOption['mode'], { label: string; icon: IconName }> = {
  car: { label: 'Ô tô', icon: 'car' }, motorbike: { label: 'Xe máy', icon: 'bike' }, bus: { label: 'Xe khách', icon: 'bus' }, plane: { label: 'Máy bay', icon: 'plane' },
}
const REASON: Record<string, string> = {
  road: 'Đường bộ, giờ ước theo bản đồ',
  too_far: 'Quá xa để đi trọn một ngày',
  no_route: 'Chưa tính được đường đi',
  no_coach_region: 'Chưa có tuyến xe khách từ khu vực này',
  needs_date: 'Chọn ngày đi để xem chuyến',
  no_trips: 'Không thấy chuyến nào trong ngày này',
  trips: 'Có chuyến trong ngày',
  unchecked: 'Chưa kiểm được chuyến cụ thể, xem trên trang nhà xe',
  too_close: 'Gần quá, đi đường bộ tiện hơn',
  no_airport_near: 'Không có sân bay gần chỗ bạn',
  flights_unchecked: 'Chưa rõ chuyến bay, xem giá trên trang đặt vé',
  flights: 'Có chuyến bay trong ngày',
}
const STATUS = (f: boolean | null) => (f === true ? { text: 'Đi được', cls: 'is-yes' } : f === false ? { text: 'Không hợp', cls: 'is-no' } : { text: 'Chưa rõ', cls: 'is-unk' })
const hhmm = (iso: string | null) => (iso && /T\d\d:\d\d/.test(iso) ? iso.slice(11, 16) : null)
const safe = (u: string | null) => (u && /^https?:\/\//i.test(u) ? u : null)
const PROVIDER: Record<string, string> = { vexere: 'Vexere', google_flights: 'Google Flights', gtravel: 'Google Travel', tripcom: 'Trip.com' }

function offerLine(o: Offer) {
  const when = [hhmm(o.depart_at), hhmm(o.arrive_at)].filter(Boolean).join(' – ')
  const price = o.price_vnd ? fmtVnd(o.price_vnd) : null
  const stops = o.kind === 'flight' && o.stops === 0 ? 'bay thẳng' : o.stops ? `${o.stops} điểm dừng` : null
  return [o.carrier, o.flight_no, when, stops, price].filter(Boolean).join(' · ') || (PROVIDER[o.provider] ?? o.provider)
}

export function BuyButton({ offer, label }: { offer: Offer; label?: string }) {
  const url = safe(offer.url)
  if (!url) return null
  const text = label ?? offerLine(offer)
  const prov = PROVIDER[offer.provider] ?? offer.provider
  return (
    <a className="tg-btn tg-btn--soft tg-btn--sm tg-wy__buy" title={text} href={url} target="_blank" rel="noopener noreferrer"
      onClick={() => track('booking_click', { offer_id: offer.offer_id, provider: offer.provider, kind: offer.kind })}>
      <span>{text}</span>{prov && prov !== text && <small>{prov}</small>}<Icon name="external" size={14} />
    </a>
  )
}

// A leg's end as the backend names it: 'origin' / 'centre' / 'lodging' / an airport code / a station name.
const spot = (x: string) => (x === 'origin' ? 'chỗ bạn' : x === 'centre' ? 'trung tâm Đà Lạt' : x === 'lodging' ? 'chỗ ở' : /^[A-Z]{3}$/.test(x) ? `sân bay ${x}` : x)
const money = (lo: number, hi: number) => (fmtVnd(lo) === fmtVnd(hi) ? `≈ ${fmtVnd(lo)}` : `≈ ${fmtVnd(lo)} – ${fmtVnd(hi)}`)
type Choice = ReturnType<typeof useRideChoice>

// Door to door for a way that rides to a station or an airport: the ride there (priced in the province it starts in), the
// tickets for everyone, the ride from the city's airport or station to the lodging. One leg without a price: no total, and
// the line says which leg (a partial total would understate the way). Driving yourself is km and hours only.
function DoorToDoor({ o, brands, choice }: { o: WayOption; brands: Record<string, RideBrand> | undefined; choice: Choice }) {
  const [open, setOpen] = useState(false)
  if (!brands || !o.legs.some((l) => l.kind === 'transfer')) return null
  const n = choice.people
  const vehicle = choice.kind === 'bike' ? 'xe máy' : 'ô tô'
  const steps = o.legs.map((l) => {
    const where = `${spot(l.from_label)} → ${spot(l.to_label)}`
    if (l.kind === 'transfer') {
      const pick = l.rides ? pickFor(l.rides, brands, choice.brand, choice.kind, n) : null
      const km = l.distance_km ? `${Math.round(l.distance_km)} km` : null
      if (!pick) return { what: `Gọi xe ${where}`, sub: km, lo: null, hi: null, gap: l.rides ? `gọi ${vehicle} ở ${l.rides.region_name ?? 'nơi đón'}` : `đường ${where}` }
      const who = `${pick.name}${pick.fallback ? ' (rẻ nhất có giá)' : ''} · ${pick.label}${pick.count > 1 ? ` × ${pick.count}` : ''}`
      return { what: `Gọi xe ${where}`, sub: [km, who].filter(Boolean).join(' · '), lo: pick.lo, hi: pick.hi, gap: null }
    }
    const what = o.mode === 'plane' ? `Vé máy bay ${where}` : `Vé xe khách ${where}`
    if (o.price_min_vnd == null) return { what, sub: null, lo: null, hi: null, gap: o.mode === 'plane' ? 'vé máy bay' : 'vé xe khách' }
    return { what, sub: `vé rẻ nhất ${fmtVnd(o.price_min_vnd)} × ${n} người`, lo: o.price_min_vnd * n, hi: o.price_min_vnd * n, gap: null }
  })
  const gaps = steps.filter((x) => x.gap).map((x) => x.gap!)
  const lo = steps.reduce((t, x) => t + (x.lo ?? 0), 0)
  const hi = steps.reduce((t, x) => t + (x.hi ?? 0), 0)
  return (
    <div className="tg-wy__door">
      <button type="button" className="tg-wy__door-sum" aria-expanded={open} onClick={() => setOpen(!open)}>
        {gaps.length ? <span>Chưa ra tổng cửa tới cửa: thiếu giá {gaps.join(', ')}</span> : <span>Cửa tới cửa <b>{money(lo, hi)}</b> cho {n} người</span>}
        <Icon name={open ? 'chevronUp' : 'chevronDown'} size={16} />
      </button>
      {open && (
        <ol className="tg-wy__steps">
          {steps.map((x, i) => (
            <li key={i} className={x.gap ? 'is-gap' : undefined}>
              <div><b>{x.what}</b>{x.sub && <small>{x.sub}</small>}</div>
              <span>{x.lo != null ? money(x.lo, x.hi!) : 'Chưa có giá'}</span>
            </li>
          ))}
          <li className="tg-wy__steps-note"><small>Gọi xe ước theo bảng giá hãng công bố (chưa gồm giờ cao điểm, khuyến mãi); vé lấy từ trang đặt vé.</small></li>
        </ol>
      )}
    </div>
  )
}

const SHOWN = 4
const bySoon = (a: Offer, b: Offer) => (a.depart_at ?? '9').localeCompare(b.depart_at ?? '9') || (a.price_vnd ?? Infinity) - (b.price_vnd ?? Infinity)

// One dated coach / flight the backend returns: who, when, how many stops, price, how old, and the buy button.
function DatedRow({ o }: { o: Offer }) {
  const when = [hhmm(o.depart_at), hhmm(o.arrive_at)].filter(Boolean).join(' – ')
  const who = [o.carrier, o.flight_no].filter(Boolean).join(' ') || 'Chưa rõ hãng'
  const extra = o.kind === 'flight' ? (o.stops === 0 ? 'bay thẳng' : o.stops ? `${o.stops} điểm dừng` : null) : null
  const age = offerAge(o)
  const url = safe(o.url)
  return (
    <li className="tg-wy__row">
      <div className="tg-wy__who"><b>{who}</b><span>{[when || 'Chưa rõ giờ', extra, o.duration_min ? fmtMin(o.duration_min) : null].filter(Boolean).join(' · ')}</span></div>
      <div className="tg-wy__cost"><b>{o.price_vnd != null ? fmtVnd(o.price_vnd) : 'Chưa rõ giá'}</b><small>{[PROVIDER[o.provider] ?? o.provider, age].filter(Boolean).join(' · ')}</small></div>
      {url && (
        <a className="tg-btn tg-btn--soft tg-btn--sm" href={url} target="_blank" rel="noopener noreferrer"
          onClick={() => track('booking_click', { offer_id: o.offer_id, provider: o.provider, kind: o.kind })}>
          Đặt vé<Icon name="external" size={14} />
        </a>
      )}
    </li>
  )
}

function DatedOffers({ list }: { list: Offer[] }) {
  const [all, setAll] = useState(false)
  const rows = [...list].sort(bySoon)
  return (
    <>
      <ul className="tg-wy__rows">{(all ? rows : rows.slice(0, SHOWN)).map((o) => <DatedRow key={o.offer_id} o={o} />)}</ul>
      {rows.length > SHOWN && <button type="button" className="tg-wy__more" onClick={() => setAll(!all)}>{all ? 'Thu gọn' : `Xem thêm ${rows.length - SHOWN} chuyến`}</button>}
    </>
  )
}

function Card({ o, i, fastest, brands, choice }: { o: WayOption; i: number; fastest: boolean; brands: Record<string, RideBrand> | undefined; choice: Choice }) {
  const m = MODE[o.mode]
  const st = STATUS(o.feasible)
  // Road options show the whole distance. A coach or flight only drives to / from the station or airport, so say which stretch each km is.
  const road = o.mode === 'car' || o.mode === 'motorbike'
  const kms = road
    ? [Math.round(o.legs.reduce((n, l) => n + (l.distance_km ?? 0), 0))].filter((k) => k > 0).map((k) => `${k} km`)
    : o.legs.filter((l) => (l.distance_km ?? 0) > 0 && l.kind !== 'flight').map((l) => `${Math.round(l.distance_km!)} km từ ${spot(l.from_label)} tới ${spot(l.to_label)}`)
  const price = o.price_min_vnd != null ? (o.price_max_vnd != null && o.price_max_vnd !== o.price_min_vnd ? `${fmtVnd(o.price_min_vnd)} – ${fmtVnd(o.price_max_vnd)}` : fmtVnd(o.price_min_vnd)) : null
  const offers = o.offers.filter((x) => safe(x.url))
  const dated = o.offers.filter(isDated)
  const links = offers.filter((x) => !isDated(x))
  return (
    <li className={`tg-wy__card ${st.cls}${dated.length ? ' has-rows' : ''}`} style={{ ['--i' as string]: i }}>
      <header><span className="tg-wy__ic"><Icon name={m.icon} size={20} /></span><b>{m.label}</b><em>{st.text}</em></header>
      <div className="tg-wy__big">{o.minutes != null ? `≈ ${fmtMin(o.minutes)}` : <span className="tg-faint">Chưa rõ giờ</span>}{fastest && <i>Nhanh nhất</i>}</div>
      {!road && kms.length > 0 && <ul className="tg-wy__legs">{kms.map((k) => <li key={k}>{k}</li>)}</ul>}
      <p className="tg-wy__meta">{[...(road ? kms : []), o.legs.find((l) => l.via)?.via ? `qua ${o.legs.find((l) => l.via)!.via}` : null, price ? `${price}/vé` : null].filter(Boolean).join(' · ') || ' '}</p>
      <p className="tg-wy__why">{o.tradeoff || REASON[o.reason] || 'Chưa rõ'}</p>
      {!road && o.feasible !== false && <DoorToDoor o={o} brands={brands} choice={choice} />}
      {dated.length > 0 && <DatedOffers list={dated} />}
      {links.length > 0 && <div className="tg-wy__offers">{links.slice(0, 3).map((x) => <BuyButton key={x.offer_id} offer={x} />)}</div>}
    </li>
  )
}

export function WayIn({ lat, lng, originText, date, way, destLat, destLng, people }: {
  lat: number | null | undefined; lng: number | null | undefined; originText?: string | null; date?: string | null; way: 'inbound' | 'outbound'; destLat?: number | null; destLng?: number | null
  people?: number | null
}) {
  const choice = useRideChoice(people ?? null)
  const [got, setGot] = useState<{ key: string; data: Journey | null } | null>(null)
  const text = originText?.trim() || ''
  const key = `${lat}|${lng}|${text}|${date}|${way}|${destLat}|${destLng}`
  const ready = (typeof lat === 'number' && typeof lng === 'number') || !!text
  const noData = 'TripGuardian chưa có dữ liệu chuyến hoặc đường đi cho bạn.'
  useEffect(() => {
    if (!ready) return
    let live = true
    const params = { lat, lng, origin: text, date, way, dest_lat: destLat, dest_lng: destLng }
    readJourneyWay(params)
      .then((data) => { if (live) setGot({ key, data }) }).catch(() => { if (live) setGot({ key, data: null }) })
    return () => { live = false }
  }, [key, ready]) // eslint-disable-line react-hooks/exhaustive-deps
  const city = way === 'inbound' ? 'Phương tiện lên Đà Lạt' : 'Phương tiện về'
  if (!ready) return null // the origin is asked in its own row above Đến Đà Lạt (Overview)
  if (!got || got.key !== key) return <div className="tg-wy" aria-busy="true"><h4>{city}</h4><p className="tg-wy__note">TripGuardian đang tìm cách đi cho bạn.</p><ul className="tg-wy__list">{[0, 1, 2].map((i) => <li key={i} className="tg-wy__card is-skel"><span className="tg-skel" /></li>)}</ul></div>
  if (!got.data) return <div className="tg-wy"><h4>{city}</h4><p className="tg-wy__note">{text ? noData : 'Chưa tải được các cách đi lúc này. Lịch trình vẫn dùng được, bạn thử lại sau nhé.'}</p></div>
  const options = got.data.options
  if (!options.length) return <div className="tg-wy"><h4>{city}</h4><p className="tg-wy__note">{noData}</p></div>
  const fastest = options.filter((o) => o.feasible === true && o.minutes != null).sort((a, b) => a.minutes! - b.minutes!)[0]
  return (
    <div className="tg-wy">
      
      <h4>{city}{got.data.day && <small>ngày {got.data.day.slice(8, 10)}/{got.data.day.slice(5, 7)}</small>}</h4>
      <ul className="tg-wy__list">{options.map((o, i) => <Card key={o.mode} o={o} i={i} fastest={o === fastest} brands={got.data!.ride_brands} choice={choice} />)}</ul>
      <p className="tg-wy__note">Giờ đường bộ là ước tính theo bản đồ. Giá và chuyến lấy từ trang đặt vé, bấm vào để xem bản mới nhất.</p>
    </div>
  )
}

// What a mouse resting on "Máy bay" / "Xe khách" in the way-in row shows: that way's own card (times, prices, buy links), read the same
// way as WayIn. Nothing here is chosen; the tag itself is still one tap. Without a start point there is nothing to look up yet.
export function WayPeek({ mode, lat, lng, originText, date, destLat, destLng, people }: {
  mode: 'plane' | 'bus'; lat: number | null | undefined; lng: number | null | undefined; originText?: string | null; date?: string | null; destLat?: number | null; destLng?: number | null; people?: number | null
}) {
  const choice = useRideChoice(people ?? null)
  const text = originText?.trim() || ''
  const key = `${lat}|${lng}|${text}|${date}|${destLat}|${destLng}`
  const ready = (typeof lat === 'number' && typeof lng === 'number') || !!text
  const [got, setGot] = useState<{ key: string; data: Journey | null } | null>(null)
  useEffect(() => {
    if (!ready) return
    let live = true
    readJourneyWay({ lat, lng, origin: text, date, way: 'inbound', dest_lat: destLat, dest_lng: destLng })
      .then((data) => { if (live) setGot({ key, data }) }).catch(() => { if (live) setGot({ key, data: null }) })
    return () => { live = false }
  }, [key, ready]) // eslint-disable-line react-hooks/exhaustive-deps
  const o = got?.key === key ? got.data?.options.find((x) => x.mode === mode) : undefined
  return (
    <div className="tg-wy tg-wy--peek" aria-live="polite">
      {!ready ? <p className="tg-wy__note">Nhập điểm xuất phát ở trên để xem {mode === 'plane' ? 'chuyến bay' : 'xe khách'} phù hợp.</p>
        : !got || got.key !== key ? <p className="tg-wy__note">Đang tìm {mode === 'plane' ? 'chuyến bay' : 'xe khách'}…</p>
          : !o ? <p className="tg-wy__note">Chưa có {mode === 'plane' ? 'chuyến bay' : 'xe khách'} cho chặng này.</p>
            : <ul className="tg-wy__list"><Card o={o} i={0} fastest={false} brands={got.data!.ride_brands} choice={choice} /></ul>}
    </div>
  )
}

// A stay offer for the chosen lodging (GET /api/harness/booking/offers?kind=stay): a button only when a provider link exists.
export function StayOffer({ fid, checkIn, nights }: { fid: string | null; checkIn: string | null; nights: number }) {
  const [offers, setOffers] = useState<Offer[]>([])
  useEffect(() => {
    setOffers([])
    if (!fid || fid.startsWith('@') || !checkIn || nights < 1) return // '@home': the user's own lodging has no listing to price
    let live = true
    readStayOffers({ fid, check_in: checkIn, nights }).then((o) => { if (live) setOffers(o) }).catch(() => {})
    return () => { live = false }
  }, [fid, checkIn, nights])
  const o = offers.find((x) => safe(x.url))
  if (!o) return null
  const total = o.price_unit === 'stay_total' ? o.price_vnd : o.price_night_vnd != null ? o.price_night_vnd * nights : null
  return <BuyButton offer={o} label={total ? `Đặt phòng · ${fmtVnd(total)} cho ${nights} đêm` : 'Xem giá và đặt phòng'} />
}
