import * as Popover from '@radix-ui/react-popover'
import { useEffect, useMemo, useRef, useState, type FocusEvent, type KeyboardEvent, type MouseEvent, type PointerEvent } from 'react'
import { info, dateRange } from '../lib'
import { keptTripSummaries, tripSummaries } from '../pd/api'
import type { TripSummary } from '../pd/types'
import { useTrip } from '../trip'
import { go, PlacePhoto } from '../ui/common'
import { Icon } from '../ui/icons'
import { tripTitle } from './dialogs'

const WEEK = ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN']
const ymd = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const at = (iso: string) => new Date(`${iso}T00:00:00`)
const dayLabel = (d: Date) => `${WEEK[(d.getDay() + 6) % 7]} ${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}`
const DAY_MS = 86_400_000
const LONG_DAY = ['Thứ hai', 'Thứ ba', 'Thứ tư', 'Thứ năm', 'Thứ sáu', 'Thứ bảy', 'Chủ nhật']

// What the server knows of a day (GET /api/harness/calendar): its public holiday and a forecast while Open-Meteo has one.
// A day without a figure simply has none: no weather is drawn beyond the forecast, and a holiday is only what the CalendarDay view lists.
type Wx = { rain_prob: number; rain_mm: number | null; tmin_c: number | null; tmax_c: number | null; gust_kmh: number | null; storm: boolean | null }
// `normal` is the month's long-run figures for a day the forecast does not reach: it is shown as such, never as a forecast.
type Normal = { tmax_c?: number; tmin_c?: number; rain_prob?: number; years?: number }
type DayInfo = { holiday?: string; weather?: Wx; normal?: Normal }
const monthCache = new Map<string, Record<string, DayInfo>>()
function useMonthDays(year: number, month: number): Record<string, DayInfo> {
  const key = ymd(new Date(year, month, 1))
  const [days, setDays] = useState<Record<string, DayInfo>>(() => monthCache.get(key) ?? {})
  useEffect(() => {
    const hit = monthCache.get(key)
    if (hit) { setDays(hit); return }
    setDays({})
    let live = true
    const to = ymd(new Date(year, month + 1, 0))
    fetch(`/api/harness/calendar?from=${key}&to=${to}`).then((r) => (r.ok ? r.json() : null)).then((j: { days?: Record<string, DayInfo> } | null) => {
      if (!live || !j?.days) return
      monthCache.set(key, j.days)
      setDays(j.days)
    }, () => {})
    return () => { live = false }
  }, [key, year, month])
  return days
}

// One picture and one phrase per forecast. Only the rain figures are known, so a dry day is "ít mưa", never "nắng".
type Sky = 'sun' | 'cloud' | 'rain' | 'storm'
function sky(w: Wx): { icon: Sky; word: string } {
  if (w.storm) return { icon: 'storm', word: 'Có dông' }
  if (w.rain_prob >= 0.6 || (w.rain_mm ?? 0) >= 8) return { icon: 'rain', word: 'Mưa' }
  if (w.rain_prob >= 0.3) return { icon: 'cloud', word: 'Có thể mưa' }
  return { icon: 'sun', word: 'Ít mưa' }
}
const temps = (w: Wx) => (w.tmin_c != null && w.tmax_c != null ? `${w.tmin_c}–${w.tmax_c}°C` : null)
const wxText = (w: Wx) => [sky(w).word + (sky(w).icon === 'sun' ? '' : ` ${Math.round(w.rain_prob * 100)}%`), temps(w)].filter(Boolean).join(' · ')

// The trips the calendar marks: locked (confirmed) ones that have not ended. Only a locked trip is a plan the person is going on.
type Upcoming = { t: TripSummary; from: Date; to: Date }
function upcoming(list: TripSummary[] | null, today: Date): Upcoming[] {
  return (list ?? []).flatMap((t) => {
    if (!t.confirmed || !t.start_date) return []
    const from = at(t.start_date)
    if (Number.isNaN(+from)) return []
    const to = new Date(from.getFullYear(), from.getMonth(), from.getDate() + Math.max(1, t.days ?? 1) - 1)
    return to >= new Date(today.getFullYear(), today.getMonth(), today.getDate()) ? [{ t, from, to }] : []
  })
}

// A month, Monday first. Today is ringed; the dates of the trip being made (start + days) are marked only when the trip really has them.
// A locked trip still ahead is drawn dark on its days; rest the pointer on one of them and a small card says which trip it is.
export function MiniCalendar({ start, days }: { start: string | null; days: number | null }) {
  const now = new Date()
  const first = start ? new Date(`${start}T00:00:00`) : null
  const [at0, setAt] = useState(() => new Date((first && !Number.isNaN(+first) ? first : now).getFullYear(), (first && !Number.isNaN(+first) ? first : now).getMonth(), 1))
  const lead = (at0.getDay() + 6) % 7 // blanks before the 1st
  const count = new Date(at0.getFullYear(), at0.getMonth() + 1, 0).getDate()
  const from = first && !Number.isNaN(+first) ? ymd(first) : null
  const to = from && days && days > 0 ? ymd(new Date(first!.getFullYear(), first!.getMonth(), first!.getDate() + days - 1)) : from
  const today = ymd(now)
  const move = (d: number) => setAt(new Date(at0.getFullYear(), at0.getMonth() + d, 1))
  const info = useMonthDays(at0.getFullYear(), at0.getMonth())
  const cells = [...Array(lead).fill(null), ...Array.from({ length: count }, (_, i) => i + 1)]

  const [list, setList] = useState<TripSummary[] | null>(keptTripSummaries)
  useEffect(() => { let live = true; tripSummaries().then((l) => { if (live) setList(l) }, () => {}); return () => { live = false } }, [])
  const trips = useMemo(() => upcoming(list, now), [list]) // eslint-disable-line react-hooks/exhaustive-deps
  const byDay = useMemo(() => {
    const m = new Map<string, Upcoming>()
    for (const u of trips) for (let d = new Date(u.from); d <= u.to; d.setDate(d.getDate() + 1)) if (!m.has(ymd(d))) m.set(ymd(d), u)
    return m
  }, [trips])

  // The card shown on a day: its forecast / holiday and, on a locked trip's days, the trip as well.
  const [tip, setTip] = useState<{ key: string; trip?: Upcoming } | null>(null)
  const anchor = useRef<{ getBoundingClientRect: () => DOMRect }>({ getBoundingClientRect: () => new DOMRect() })
  const timer = useRef(0)
  useEffect(() => () => clearTimeout(timer.current), [])
  const show = (key: string, trip: Upcoming | undefined, el: HTMLElement) => { clearTimeout(timer.current); anchor.current = { getBoundingClientRect: () => el.getBoundingClientRect() }; setTip({ key, trip }) }
  const hide = () => { clearTimeout(timer.current); timer.current = window.setTimeout(() => setTip(null), 160) }
  const hold = () => clearTimeout(timer.current)

  return (
    <section className="tg-cal" data-tour="calendar" aria-label="Lịch">
      <header>
        <h3 aria-live="polite">Tháng {at0.getMonth() + 1}, {at0.getFullYear()}</h3>
        <span>
          <button type="button" aria-label="Tháng trước" onClick={() => move(-1)}><Icon name="chevronLeft" size={14} /></button>
          <button type="button" className="is-next" aria-label="Tháng sau" onClick={() => move(1)}><Icon name="chevronRight" size={14} /></button>
        </span>
      </header>
      <div className="tg-cal__grid" role="grid">
        {WEEK.map((w) => <b key={w} role="columnheader">{w}</b>)}
        {cells.map((n, i) => {
          if (n === null) return <i key={`b${i}`} />
          const key = ymd(new Date(at0.getFullYear(), at0.getMonth(), n))
          const edge = key === from || key === to
          const mid = from && to && key > from && key < to
          const go1 = byDay.get(key)
          const di = info[key]
          const cls = `${key === today ? 'is-today' : ''} ${edge ? 'is-edge' : ''} ${mid ? 'is-mid' : ''} ${go1 ? 'is-go' : ''} ${go1 && ymd(go1.from) === key ? 'is-go-start' : ''} ${go1 && ymd(go1.to) === key ? 'is-go-end' : ''} ${di?.holiday ? 'is-holiday' : ''} has-day`
          const say = [go1 ? `${tripTitle(go1.t)} đã chốt lịch` : null, di?.holiday ?? null, di?.weather ? wxText(di.weather) : (di?.normal ? 'chưa có dự báo, đây là trung bình nhiều năm' : null)].filter(Boolean).join(', ')
          const marks = di?.holiday && <i className="tg-cal__star" aria-hidden="true"><Icon name="star" size={11} /></i>
          // Every day opens a card on hover, focus or tap: its forecast and holiday when it has them, otherwise a plain "no forecast".
          return <span key={key} role="gridcell" tabIndex={0} className={cls} aria-current={key === today ? 'date' : undefined} aria-label={`${n}: ${say || (key < today ? 'đã qua' : 'chưa có dự báo')}`}
            onPointerEnter={(e: PointerEvent<HTMLElement>) => show(key, go1, e.currentTarget)} onPointerLeave={hide} onFocus={(e: FocusEvent<HTMLElement>) => show(key, go1, e.currentTarget)} onBlur={hide}
            onClick={(e: MouseEvent<HTMLElement>) => show(key, go1, e.currentTarget)}
            onKeyDown={(e: KeyboardEvent) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); show(key, go1, e.currentTarget as HTMLElement) } else if (e.key === 'Escape') setTip(null) }}>{n}{marks}</span>
        })}
      </div>
      <Popover.Root open={!!tip} onOpenChange={(o) => { if (!o) setTip(null) }}>
        <Popover.Anchor virtualRef={anchor} />
        <Popover.Portal>
          <Popover.Content className="tg tg-home tg-cal__card" side="left" align="center" sideOffset={12} collisionPadding={14} onOpenAutoFocus={(e) => e.preventDefault()} onPointerEnter={hold} onPointerLeave={hide}>
            {tip && <DayCard iso={tip.key} d={info[tip.key] ?? {}} past={tip.key < today} />}
            {tip?.trip && <TripTip u={tip.trip} now={now} />}
          </Popover.Content>
        </Popover.Portal>
      </Popover.Root>
    </section>
  )
}

// The few things that say which trip this is: the best-rated place as a photo, the dates and how far away, and the best places in it.
function TripTip({ u, now }: { u: Upcoming; now: Date }) {
  const { dispatch } = useTrip()
  const { t } = u
  const ranked = [...new Set(t.places)].map((id) => ({ id, p: info(id) })).sort((a, b) => (b.p?.rating ?? 0) - (a.p?.rating ?? 0))
  const cover = ranked.find((x) => x.p?.photos.length)?.id ?? ranked[0]?.id
  const left = Math.round((+u.from - +new Date(now.getFullYear(), now.getMonth(), now.getDate())) / DAY_MS)
  const when = left > 0 ? (left === 1 ? 'Ngày mai đi' : `Còn ${left} ngày`) : 'Đang trong chuyến'
  const open = () => {
    dispatch({ type: 'reset' })
    dispatch({ type: 'set', patch: { journeyId: t.id, decisionId: t.id, planningId: t.id } })
    go('/plan')
  }
  return (
    <button type="button" className="tg-cal__tip" onClick={open}>
      <span className="tg-cal__cover">{cover ? <PlacePhoto id={cover} sizes="260px" /> : null}<b>{when}</b></span>
      <strong>{tripTitle(t)}</strong>
      <small>{[`${dayLabel(u.from)}${t.days && t.days > 1 ? ` → ${dayLabel(u.to)}` : ''}`, t.people ? `${t.people} người` : null].filter(Boolean).join(' · ') || dateRange(t.start_date, t.days)}</small>
      {ranked.length > 0 && <ul aria-label="Nơi đáng chú ý">
        {ranked.slice(0, 3).map(({ id, p }) => p ? <li key={id}><span>{p.name}</span>{p.rating ? <em>★ {p.rating.toFixed(1)}</em> : null}</li> : null)}
        {t.places.length > 3 && <li className="is-more">+{t.places.length - 3} nơi nữa</li>}
      </ul>}
      <i>Xem lịch<Icon name="arrow" size={13} /></i>
    </button>
  )
}

// The day pointed at, as a flat weather card in the colour of its sky: the label and the high on the left, the date and place on
// the right, layered shapes in the corner, then the figures the forecast really has. The forecast is daily, so there is no hourly row.
function DayCard({ iso, d, past }: { iso: string; d: DayInfo; past: boolean }) {
  const day = at(iso)
  const w = d.weather
  const n = w ? undefined : d.normal
  const kind = w ? sky(w) : (n?.rain_prob != null ? sky({ rain_prob: n.rain_prob, rain_mm: null, tmin_c: null, tmax_c: null, gust_kmh: null, storm: null }) : null)
  const high = w?.tmax_c ?? n?.tmax_c ?? null
  const stats = (w ? [
    w.tmin_c != null ? { k: 'Thấp nhất', v: `${w.tmin_c}°` } : null,
    { k: 'Khả năng mưa', v: `${Math.round(w.rain_prob * 100)}%` },
    w.rain_mm != null ? { k: 'Lượng mưa', v: `${w.rain_mm} mm` } : null,
    w.gust_kmh != null ? { k: 'Gió giật', v: `${w.gust_kmh} km/h` } : null,
  ] : [
    n?.tmin_c != null ? { k: 'Thấp nhất', v: `${n.tmin_c}°` } : null,
    n?.rain_prob != null ? { k: 'Ngày có mưa', v: `${Math.round(n.rain_prob * 100)}%` } : null,
  ]).filter((x): x is { k: string; v: string } => !!x)
  return (
    <div className="tg-cal__wxc" data-sky={kind?.icon ?? 'none'}>
      <SkyScene kind={kind?.icon ?? 'none'} />
      <div className="tg-cal__wxc-top">
        <div className="tg-cal__wxc-l">
          <span className="tg-cal__wxc-k">{kind ? <><Icon name={kind.icon} size={15} />{n ? `Thường ${kind.word.toLowerCase()}` : kind.word}</> : (past ? 'Đã qua' : 'Chưa có dự báo')}</span>
          <p className="tg-cal__wxc-t" aria-label={high != null ? `${n ? 'Thường cao' : 'Cao nhất'} ${high} độ C` : undefined}>{high != null ? <>{Math.round(high)}<sup>°</sup></> : <span>–</span>}</p>
        </div>
        <p className="tg-cal__wxc-w"><b>{LONG_DAY[(day.getDay() + 6) % 7]}</b><span>{String(day.getDate()).padStart(2, '0')}/{String(day.getMonth() + 1).padStart(2, '0')}/{day.getFullYear()}</span><span>Đà Lạt</span></p>
      </div>
      {d.holiday && <p className="tg-cal__wxc-h"><i aria-hidden="true"><Icon name="star" size={11} /></i>{d.holiday}</p>}
      {stats.length > 0 && <dl className="tg-cal__wxc-s">{stats.map((x) => <div key={x.k}><dt>{x.k}</dt><dd>{x.v}</dd></div>)}</dl>}
      {n && <p className="tg-cal__wxc-n">{past ? 'Đã qua' : 'Chưa có dự báo'} · trung bình nhiều năm</p>}
    </div>
  )
}

// Flat layered shapes in the card's top-right corner, like a sticker sheet: circles for the sun, waves for cloud and rain, a bolt for storm.
function SkyScene({ kind }: { kind: Sky | 'none' }) {
  return (
    <svg className="tg-cal__wxc-art" viewBox="0 0 256 120" preserveAspectRatio="xMaxYMin slice" aria-hidden="true">
      {kind === 'none' && <>
        <circle cx="256" cy="-10" r="120" fill="#7d8594" /><circle cx="256" cy="-10" r="78" fill="#8e96a4" />
      </>}
      {kind === 'sun' && <>
        <circle cx="256" cy="-10" r="132" fill="#f79b7a" /><circle cx="256" cy="-10" r="92" fill="#fbb978" /><circle cx="256" cy="-10" r="34" fill="#ffd23d" />
      </>}
      {kind === 'cloud' && <>
        <path d="M110 0h146v120H190c-30-14-6-34-40-48-26-10-34-34-40-72Z" fill="#4eb2d6" />
        <path d="M150 0h106v96c-30 6-48-8-62-28-12-18-30-22-44-44Z" fill="#6fc9d9" />
        <path d="M196 0h60v54c-22 6-38-6-48-20-6-10-10-20-12-34Z" fill="#93dbd9" />
      </>}
      {kind === 'rain' && <>
        <path d="M96 0h160v120h-70c-26-16-6-40-40-52-22-8-52-30-50-68Z" fill="#3b566f" />
        <path d="M150 0h106v92c-30 4-52-10-66-28-12-16-30-22-40-64Z" fill="#2a3f55" />
        <path d="M200 0h56v50c-20 4-36-8-44-22-6-10-10-18-12-28Z" fill="#1b2a3a" />
      </>}
      {kind === 'storm' && <>
        <circle cx="250" cy="-6" r="132" fill="#2a3a78" /><circle cx="250" cy="-6" r="92" fill="#35479a" />
        <path d="M244 6 234 24h8l-5 14 15-20h-8l6-12Z" fill="#ffd23d" />
        {[[120, 18], [150, 40], [96, 62], [170, 82], [132, 96], [70, 30]].map(([x, y], i) => <circle key={i} cx={x} cy={y} r="1.6" fill="#ffd23d" opacity="0.8" />)}
      </>}
    </svg>
  )
}
