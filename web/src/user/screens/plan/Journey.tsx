import { useEffect, useId, useLayoutEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import { dayLabel, fmtMin, info, toMin } from '../../lib'
import type { ItineraryDay } from '../../planning/types'
import { PlacePhoto } from '../../ui/common'
import { Icon, type IconName } from '../../ui/icons'
import { Page } from '../../ui/Shell'
import type { MapDayRoute } from './useRoutes'
import { BLOCK, MEAL_LABEL, dayAreas, placeName, shortDate, visits } from './shared'
import '../../css/journey.css'

// The last look before a plan is locked (chủ dự án 13/11/2026), drawn as a route infographic: one white panel per day, the day's
// stops as photo cards hung above and below a dashed route that winds through them, and a dashed link from the last stop of a
// day, through the night at the lodging, to the first stop of the next day. Read-only on purpose: changing a stop is the day
// screens' job, so "Quay lại sửa" goes there and "Chốt hành trình" locks the plan.

const WAY: Record<string, { label: string; icon: IconName }> = { plane: { label: 'Máy bay', icon: 'plane' }, bus: { label: 'Xe khách', icon: 'bus' }, self: { label: 'Tự đi', icon: 'car' } }
const MODE: Record<string, string> = { motorbike: 'xe máy', car: 'ô tô', walk: 'đi bộ', bus: 'xe khách', taxi: 'taxi' }

type Leg = { min: number; mode: string | null } | null
type Stop =
  | { kind: 'stop'; key: string; id: string; name: string; start: string; end: string; leg: Leg; no: number }
  | { kind: 'block'; key: string; label: string; icon: IconName; start: string; end: string; leg: Leg }
  | { kind: 'point'; key: string; label: string; name: string; icon: IconName; at: string; leg: Leg }
interface Day { day: ItineraryDay; stops: Stop[] }

// Exactly what the day screen shows, in its order: where the day opens, the stops and the free / rest / meal blocks between them
// (a first day that lands before check-in leaves its bags at the lodging first: that is a "rest" block), where the day closes.
function daysOf(days: ItineraryDay[], routes: MapDayRoute[] | null, lodging: string | null): Day[] {
  return days.map((d, i) => {
    const stops: Stop[] = []
    const route = routes?.find((r) => r.day === d.day)
    const first = d.items[0], last = d.items[d.items.length - 1]
    let leg = null as Leg
    let no = 0
    const hasVisit = d.items.some((it) => it.kind === 'visit' && it.place_id)
    if (hasVisit) stops.push({ kind: 'point', key: `d${d.day}-in`, label: 'Xuất phát', name: route?.start.name ?? (i > 0 && lodging ? lodging : 'Điểm xuất phát'), icon: i > 0 || route?.start.home ? 'bed' : 'home', at: first?.start ?? d.window[0], leg: null })
    for (const [k, it] of d.items.entries()) {
      if (it.kind === 'travel') {
        const min = it.road_min ?? Math.max(0, toMin(it.end) - toMin(it.start))
        leg = { min: (leg?.min ?? 0) + min, mode: it.mode ? MODE[it.mode] ?? null : leg?.mode ?? null }
      } else if (it.kind === 'visit' && it.place_id) {
        stops.push({ kind: 'stop', key: `d${d.day}-${k}`, id: it.place_id, name: it.name ?? placeName(it.place_id), start: it.start, end: it.end, leg, no: ++no })
        leg = null
      } else if (hasVisit) {
        const home = it.kind === 'rest' && (it.note === 'drop_bags' || it.note === 'home')
        const label = home ? (it.note === 'drop_bags' ? 'Ghé chỗ ở gửi đồ' : 'Về chỗ ở nghỉ') : (it.kind === 'meal_free' ? MEAL_LABEL[it.name ?? ''] : null) ?? BLOCK[it.kind] ?? it.kind
        stops.push({ kind: 'block', key: `d${d.day}-${k}`, label, icon: home || it.kind === 'rest' ? 'bed' : it.kind === 'meal_free' ? 'utensils' : it.kind === 'free' ? 'coffee' : 'clock', start: it.start, end: it.end, leg })
        leg = null
      }
    }
    if (hasVisit) stops.push({ kind: 'point', key: `d${d.day}-out`, label: 'Kết thúc ngày', name: route?.end.name ?? (i < days.length - 1 && lodging ? lodging : 'Điểm kết thúc'), icon: i < days.length - 1 || route?.end.home ? 'bed' : 'flag', at: last?.end ?? d.window[1], leg })
    return { day: d, stops }
  })
}

// ---- geometry: all in pixels of the route's width, so a card keeps its size whatever the screen ----
const CARD_H = 144          // room for a photo card above or below the route
const BLOCK_H = 60          // and for a free-time block, which is a low strip
const GAP = 26              // from a dot to its card
const WAVE = 10             // the route dips to a card's side: dots of cards above sit lower, dots of cards below sit higher
const BULGE = 70            // how far the route swings out at the end of a row to turn back into the next
const LINK_H = 150          // the link through a night
const END_H = 84            // the link to the trip's first / from its last stop

interface Pt { x: number; y: number; up: boolean; row: number }

// The stops go along rows of up to 7 (5 on a narrow window, 3 on a phone), the next row coming back the other way (a snake), so the route never jumps
// across the panel. A day with fewer stops uses fewer columns, so one stop sits in the middle; a row only reserves room for the
// sides that have a card (the area name takes the other side).
function place(stops: Stop[], w: number) {
  const n = stops.length
  const high = (k: number) => (stops[k].kind === 'stop' ? CARD_H : BLOCK_H)
  const cols = Math.max(1, Math.min(w < 520 ? 3 : w >= 840 ? 7 : 5, n))
  const colW = w / cols
  let off = 0
  const rows = Array.from({ length: Math.ceil(n / cols) }, (_, r) => {
    const ks = Array.from({ length: Math.min(n, (r + 1) * cols) - r * cols }, (_, i) => r * cols + i)
    const tall = (side: number) => Math.max(0, ...ks.filter((k) => k % 2 === side).map(high))
    const above = tall(0) ? tall(0) + GAP : 40
    const h = above + WAVE * 2 + (tall(1) ? tall(1) + GAP : 34)
    const row = { mid: off + above + WAVE }
    off += h
    return row
  })
  const pts: Pt[] = Array.from({ length: n }, (_, k) => {
    const row = Math.floor(k / cols)
    const c = k % cols
    const up = k % 2 === 0
    return { x: ((row % 2 ? cols - 1 - c : c) + 0.5) * colW, y: rows[row].mid + (up ? WAVE : -WAVE), up, row }
  })
  let d = ''
  pts.forEach((p, k) => {
    if (!k) { d = `M${p.x} ${p.y}`; return }
    const q = pts[k - 1]
    if (q.row === p.row) { const h = (p.x - q.x) / 2; d += ` C${q.x + h} ${q.y} ${p.x - h} ${p.y} ${p.x} ${p.y}` }
    else { const s = q.row % 2 ? -BULGE : BULGE; d += ` C${q.x + s} ${q.y} ${p.x + s} ${p.y} ${p.x} ${p.y}` }
  })
  return { pts, d, cols, colW, h: Math.max(off, 1) }
}

function usePanel() {
  const list = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(900)
  useEffect(() => {
    const root = list.current
    if (!root) return
    setWidth(root.clientWidth)
    if (typeof ResizeObserver !== 'function') return
    const size = new ResizeObserver(() => setWidth(root.clientWidth))
    size.observe(root)
    return () => size.disconnect()
  }, [])
  return { list, width }
}

const legText = (leg: Leg, wide: boolean) => (leg && leg.min > 0 ? `≈ ${fmtMin(leg.min)}${wide && leg.mode ? ` ${leg.mode}` : ''}` : null)

export function Journey({ days, routes, origin, lodging, arriveHow, leaveHow, travelMin, warned, busy, error, confirmed, onBack, onFinish }: {
  days: ItineraryDay[]; routes: MapDayRoute[] | null; origin: string | null; lodging: string | null; arriveHow?: string | null; leaveHow?: string | null; travelMin: number
  warned: boolean; busy: boolean; error: string | null; confirmed: boolean; onBack: () => void; onFinish: () => void
}) {
  const first = days[0], last = days[days.length - 1]
  const places = days.reduce((n, d) => n + visits(d).length, 0)
  const range = days.length > 1 ? `${shortDate(first?.date, 1)} – ${shortDate(last?.date, days.length)}` : shortDate(first?.date, 1)
  const plan = useMemo(() => daysOf(days, routes, lodging), [days, routes, lodging])
  const { list, width } = usePanel()
  const pad = width < 520 ? 20 : 44
  const w = Math.max(160, width - pad * 2)
  const wide = w >= 520
  const laid = useMemo(() => plan.map((x) => place(x.stops, w)), [plan, w])
  const arrive = WAY[arriveHow ?? '']?.label, leave = WAY[leaveHow ?? '']?.label
  useEffect(() => { // each panel and link draws itself in as the page scrolls to it
    const root = list.current
    if (!root || typeof IntersectionObserver !== 'function' || matchMedia('(prefers-reduced-motion: reduce)').matches) return
    root.classList.add('is-live')
    const seen = new IntersectionObserver((entries) => entries.forEach((e) => { if (e.isIntersecting) { e.target.classList.add('is-in'); seen.unobserve(e.target) } }), { rootMargin: '0px 0px -8% 0px' })
    root.querySelectorAll('.tg-jx__seen').forEach((el) => seen.observe(el))
    return () => seen.disconnect()
  }, [plan])
  // The link between two days runs down the side of the panels: out of the last dot of a day on the side it ends on, into the first
  // dot of the next day from the left gutter, so the line never crosses a card or a title.
  const gutter = pad / 2
  const exitLeft = (i: number) => { const pts = laid[i]?.pts; return !!pts?.length && pad + pts[pts.length - 1].x < width / 2 }
  const exitAt = (i: number) => (exitLeft(i) ? gutter : width - gutter)
  return (
    <Page className="tg-jr tg-jx">
      <section className="tg-jx__stage" aria-label="Hành trình">
        <header className="tg-jx__head">
          <h1>Hành trình Đà Lạt của bạn</h1>
          <p>Bước cuối trước khi chốt · lịch trình · tổng quan hành trình</p>
          <ul className="tg-jx__facts">
            <li><Icon name="calendar" size={15} />{days.length} ngày{range ? ` · ${range}` : ''}</li>
            <li><Icon name="pin" size={15} />{places} nơi</li>
            {travelMin > 0 && <li><Icon name="route" size={15} />≈ {fmtMin(travelMin)} di chuyển</li>}
            {lodging && <li><Icon name="bed" size={15} />{lodging}</li>}
          </ul>
        </header>
        <div className="tg-jx__flow" ref={list} style={{ '--pad': `${pad}px` } as CSSProperties}>
          <div className="tg-jx__end">
            <span className="tg-jx__ic"><Icon name="home" size={17} /></span>
            <div><b>{origin ? `Xuất phát từ ${origin}` : 'Điểm xuất phát'}</b><small>{arrive ? `Tới Đà Lạt bằng ${arrive.toLowerCase()}` : 'Bắt đầu hành trình'}</small></div>
          </div>
          {plan.map((x, i) => (
            <div key={x.day.day} className="tg-jx__block">
              <Link h={END_H} width={width} from={i === 0 ? width / 2 : exitAt(i - 1)} to={gutter} night={i > 0 ? { title: lodging ? `Nghỉ đêm tại ${lodging}` : 'Nghỉ đêm', h: LINK_H } : null} />
              <DayPanel x={x} g={laid[i]} pad={pad} w={w} wide={wide} exitLeft={exitLeft(i)} />
            </div>
          ))}
          <Link h={END_H} width={width} from={exitAt(plan.length - 1)} to={width / 2} />
          <div className="tg-jx__end">
            <span className="tg-jx__ic"><Icon name="flag" size={17} /></span>
            <div><b>{origin ? `Về ${origin}` : 'Kết thúc chuyến đi'}</b><small>{[leave ? `Đi ${leave.toLowerCase()}` : null, last ? `rời Đà Lạt lúc ${last.window[1]}` : null].filter(Boolean).join(' · ')}</small></div>
          </div>
        </div>
      </section>
      {error && <p className="tg-it-diff is-bad" role="alert"><Icon name="warn" size={15} />{error}</p>}
      {warned && <p className="tg-jr__warn" role="status"><Icon name="warn" size={16} />Lịch còn điểm cần lưu ý. Mình chỉ báo để bạn biết, quyết định là của bạn.</p>}
      <footer className="tg-jx__foot">
        <button type="button" className="tg-btn tg-btn--ghost" disabled={busy} onClick={onBack}><Icon name="arrowLeft" size={18} /> Quay lại sửa</button>
        <button type="button" className="tg-btn tg-btn--primary" disabled={busy} onClick={onFinish}>{busy ? 'Đang chốt…' : confirmed ? 'Chốt lại hành trình' : 'Chốt hành trình'} <Icon name="check" size={18} /></button>
      </footer>
    </Page>
  )
}

// The dashed link between two panels (or between the trip's ends and a panel): it comes out of the bottom of the one above (where
// DayPanel's own line leaves the day's last dot) and goes into the top of the one below (where it runs on to the day's first dot).
// Through a night it carries the lodging.
function Link({ h, width, from, to, night }: { h: number; width: number; from: number; to: number; night?: { title: string; h: number } | null }) {
  const H = night ? night.h : h
  const mid = H / 2
  const d = `M${from} 0 C${from} ${mid} ${to} ${mid} ${to} ${H}`
  return (
    <div className="tg-jx__link tg-jx__seen" style={{ height: H }}>
      <svg viewBox={`0 0 ${width} ${H}`} width={width} height={H} aria-hidden="true"><path d={d} className="tg-jx__dash" /></svg>
      {night && <>
        <p className="tg-jx__night" style={{ top: mid, left: (from + to) / 2 }}><Icon name="bed" size={15} />{night.title}</p>
      </>}
    </div>
  )
}

function DayPanel({ x, g, pad, w, wide, exitLeft }: { x: Day; g: ReturnType<typeof place>; pad: number; w: number; wide: boolean; exitLeft: boolean }) {
  const id = useId().replace(/\W/g, '')
  const panel = useRef<HTMLElement>(null)
  const route = useRef<HTMLDivElement>(null)
  const [at, setAt] = useState<{ top: number; height: number } | null>(null) // where the route sits in the panel, for the line through it
  useLayoutEffect(() => { if (panel.current) setAt({ top: route.current?.offsetTop ?? 0, height: panel.current.offsetHeight }) }, [g, w, pad, x])
  const d = x.day
  const l = dayLabel(d.date)
  const count = visits(d).length
  const road = d.items.reduce((n, it) => n + (it.kind === 'travel' ? it.road_min ?? Math.max(0, toMin(it.end) - toMin(it.start)) : 0), 0)
  return (
    <section ref={panel} className="tg-jx__panel tg-jx__seen" aria-labelledby={`jx${id}`} style={{ '--pad': `${pad}px` } as CSSProperties}>
      <header className="tg-jx__phead">
        <div>
          <h2 id={`jx${id}`}>Ngày {d.day}</h2>
          <p>{[l ? `${l.wd} · ${l.dm}` : d.weekday || shortDate(d.date, d.day), dayAreas(d).join(' · ') || 'Ngày tự do'].join(' · ')}</p>
        </div>
        <ul>
          <li>{count} điểm dừng</li>
          {road > 0 && <li>≈ {fmtMin(road)} di chuyển</li>}
          <li className="tg-mono">{d.window[0]} → {d.window[1]}</li>
        </ul>
      </header>
      {at && <Through g={g} pad={pad} w={w} top={at.top} height={at.height} exitLeft={exitLeft} none={!x.stops.length} />}
      {!x.stops.length ? <p className="tg-jx__free">Ngày tự do: nghỉ ngơi hoặc tự khám phá.</p> : (
        <div className="tg-jx__route" ref={route} style={{ height: g.h, width: w }}>
          <svg viewBox={`-60 -20 ${w + 120} ${g.h + 40}`} width={w + 120} height={g.h + 40} aria-hidden="true">
            <defs>
              <mask id={`m${id}`} maskUnits="userSpaceOnUse" x={-60} y={-20} width={w + 120} height={g.h + 40}>
                <path d={g.d} className="tg-jx__draw" pathLength={1} />
              </mask>
            </defs>
            <path d={g.d} className="tg-jx__dash" mask={`url(#m${id})`} />
          </svg>
          <ol>
            {x.stops.map((s, k) => {
              const p = g.pts[k]
              const prev = g.pts[k - 1]
              const same = prev && prev.row === p.row
              const pill = legText(s.leg, wide)
              const card = Math.min(176, g.colW * 2 - 14)
              const slotH = s.kind === 'stop' ? CARD_H : BLOCK_H
              const around = { '--k': k } as CSSProperties
              return (
                <li key={s.key} style={around}>
                  {pill && k > 0 && <span className="tg-jx__leg" style={same ? { left: (prev.x + p.x) / 2, top: (prev.y + p.y) / 2 } : { left: prev.x + (prev.row % 2 ? -1 : 1) * BULGE * 0.75, top: (prev.y + p.y) / 2 }}>{pill}</span>}
                  <span className={`tg-jx__dot ${s.kind === 'stop' ? '' : s.kind === 'point' ? 'is-point' : 'is-block'}`} style={{ left: p.x, top: p.y }} aria-hidden="true">{s.kind === 'stop' ? s.no : s.kind === 'point' ? <Icon name={s.icon} size={13} /> : null}</span>
                  <div className={`tg-jx__slot is-${p.up ? 'up' : 'down'}`} style={{ left: Math.min(Math.max(p.x, card / 2), w - card / 2), top: p.up ? p.y - GAP - slotH : p.y + GAP, width: card, height: slotH }}>
                    <StopCard s={s} />
                  </div>
                  {s.kind === 'stop' && info(s.id)?.area && <span className="tg-jx__area" style={{ left: p.x, top: p.up ? p.y + 16 : p.y - 36 }}>{info(s.id)?.area}</span>}
                </li>
              )
            })}
          </ol>
        </div>
      )}
    </section>
  )
}

// The line of the link carried through the panel: from its top edge down the left gutter into the day's first dot, and from the
// day's last dot out to the gutter on the side it ends and down to the bottom edge. A day with no stops is one straight line.
function Through({ g, pad, w, top, height, exitLeft, none }: { g: ReturnType<typeof place>; pad: number; w: number; top: number; height: number; exitLeft: boolean; none: boolean }) {
  const width = w + pad * 2
  const gi = pad / 2
  let d = `M${gi} 0 L${gi} ${height}`
  if (!none && g.pts.length) {
    const a = g.pts[0], z = g.pts[g.pts.length - 1]
    const ay = top + a.y, zy = top + z.y
    const gx = exitLeft ? gi : width - gi
    const dir = exitLeft ? -1 : 1
    d = `M${gi} 0 L${gi} ${Math.max(0, ay - 56)} C${gi} ${ay} ${pad + a.x - 70} ${ay} ${pad + a.x} ${ay}`
    d += ` M${pad + z.x} ${zy} C${pad + z.x + dir * 70} ${zy} ${gx} ${zy} ${gx} ${Math.min(height, zy + 56)} L${gx} ${height}`
  }
  return <svg className="tg-jx__through" viewBox={`0 0 ${width} ${height}`} width={width} height={height} aria-hidden="true"><path d={d} className="tg-jx__dash" /></svg>
}

function StopCard({ s }: { s: Stop }) {
  if (s.kind === 'point') return <div className="tg-jx__card is-point"><small>{s.label} · <time className="tg-mono">{s.at}</time></small><b>{s.name}</b></div>
  if (s.kind === 'block') return <div className="tg-jx__card is-block"><Icon name={s.icon} size={15} /><b>{s.label}</b><time className="tg-mono">{s.start}–{s.end}</time></div>
  const p = info(s.id)
  const stay = toMin(s.end) - toMin(s.start)
  return (
    <div className="tg-jx__card">
      {p ? <PlacePhoto id={s.id} name={s.name} className="tg-jx__ph" sizes="180px" /> : <span className="tg-jx__ph tg-photo tg-photo__ph" aria-hidden="true" />}
      <b>{s.name}</b>
      <time className="tg-mono">{s.start}–{s.end}</time>
      {stay > 0 && <small>Ở lại ≈ {fmtMin(stay)}</small>}
    </div>
  )
}
