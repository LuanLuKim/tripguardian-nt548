import { useEffect, useState } from 'react'
import { isDated, offerAge, readJourneyWay, readStayOffers, type Journey, type Offer, type WayOption } from '../../booking'
import { track } from '../../events'
import { fmtMin, fmtVnd } from '../../lib'
import { Icon, type IconName } from '../../ui/icons'
import '../../css/wayin.css'
import '../../css/fixes.css'

// "Đường tới Đà Lạt" / "Đường về": the ways from home to the city (GET /api/harness/journey), the road ones timed by the map,
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

// A leg's end as the backend names it: 'origin' / 'centre' / an airport code / a station name.
const spot = (x: string) => (x === 'origin' ? 'chỗ bạn' : x === 'centre' ? 'trung tâm Đà Lạt' : /^[A-Z]{3}$/.test(x) ? `sân bay ${x}` : x)

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

function Card({ o, i, fastest }: { o: WayOption; i: number; fastest: boolean }) {
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
      {dated.length > 0 && <DatedOffers list={dated} />}
      {links.length > 0 && <div className="tg-wy__offers">{links.slice(0, 3).map((x) => <BuyButton key={x.offer_id} offer={x} />)}</div>}
    </li>
  )
}

export function WayIn({ lat, lng, originText, date, way, destLat, destLng }: {
  lat: number | null | undefined; lng: number | null | undefined; originText?: string | null; date?: string | null; way: 'inbound' | 'outbound'; destLat?: number | null; destLng?: number | null
}) {
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
  const city = way === 'inbound' ? 'Đường tới Đà Lạt' : 'Đường về'
  if (!ready) return null // the origin is asked in its own row above Đến Đà Lạt (Overview)
  if (!got || got.key !== key) return <div className="tg-wy" aria-busy="true"><h4>{city}</h4><p className="tg-wy__note">TripGuardian đang tìm cách đi cho bạn.</p><ul className="tg-wy__list">{[0, 1, 2].map((i) => <li key={i} className="tg-wy__card is-skel"><span className="tg-skel" /></li>)}</ul></div>
  if (!got.data) return <div className="tg-wy"><h4>{city}</h4><p className="tg-wy__note">{text ? noData : 'Chưa tải được các cách đi lúc này. Lịch trình vẫn dùng được, bạn thử lại sau nhé.'}</p></div>
  const options = got.data.options
  if (!options.length) return <div className="tg-wy"><h4>{city}</h4><p className="tg-wy__note">{noData}</p></div>
  const fastest = options.filter((o) => o.feasible === true && o.minutes != null).sort((a, b) => a.minutes! - b.minutes!)[0]
  return (
    <div className="tg-wy">
      
      <h4>{city}{got.data.day && <small>ngày {got.data.day.slice(8, 10)}/{got.data.day.slice(5, 7)}</small>}</h4>
      <ul className="tg-wy__list">{options.map((o, i) => <Card key={o.mode} o={o} i={i} fastest={o === fastest} />)}</ul>
      <p className="tg-wy__note">Giờ đường bộ là ước tính theo bản đồ. Giá và chuyến lấy từ trang đặt vé, bấm vào để xem bản mới nhất.</p>
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
