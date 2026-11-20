import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties } from 'react'
import { createPortal } from 'react-dom'
import { useSnapshot } from '../../data/store'
import { info } from '../lib'
import { openPlace } from '../ui/PlaceSheet'
import { PlacePhoto } from '../ui/common'
import { Icon, type IconName } from '../ui/icons'
import { EventPost, EventThumb, daysTo, leftText, localDay, spanDays, venueOf, whenOf } from './EventPost'
import { SeasonPost, SeasonThumb, monthsOf } from './SeasonPost'
import { HotTag } from './HotTag'
import { TrendingSheet } from './TrendingSheet'
import '../css/pulse.css'

// Trending (docs/CORPUS.md §Nhịp, "Hạng xu hướng"): the bulletin comes from GET /api/harness/pulse. The rail has three tabs: the next dated
// events (photo from the article that announced them), the places that rank highest (one score from the server, no counts shown), and the
// seasons the city is in. Each row is a rank, a round photo, a one-line name and one word for why it is rising. Places without a photo the
// rules allow are skipped (a trend with no picture is not a card). Five rows at most per tab, no "xem thêm" (owner, 2026-11-04 and
// 2026-11-16). With a mouse, pointing at a row opens a preview card beside the rail (the picture, a short summary); a click opens the detail.
type Source = { type: string; label: string; url?: string; date?: string }
export type Item = {
  id: string; kind: string; title: string; text: string; place_id: string | null; sources: Source[]
  // Short fields added by the server (src/corpus/pulse/render.py `_short`); absent on an older harness.
  signal?: string; signal_kind?: string; count?: number | null; score?: number | null; window_days?: number | null; newest?: string | null
  on?: string | null; rising?: boolean; reference?: boolean
  // "Đang hot" by the server's one bar (clips by different authors lately; for an event, sites that report it); `hot_note` says why, as a tooltip.
  hot?: boolean; hot_note?: string
  // An event also carries the article's picture (a hotlink, credited by its site) and a one-line summary.
  image?: string; image_from?: { url?: string; domain?: string } | string; summary?: string
  // A festival's programmes (its opening night, a flower space...), folded into it instead of listed as events of their own.
  parts?: { name: string; start: string; end: string; time: string; venue: string }[]
  // A season also lists the places worth seeing in it.
  see?: string[]
}
export type Bulletin = { city: string; generated_at: string | null; day: string | null; stale: boolean; sections: { kind: string; title: string; items: Item[] }[] }

const SHOWN = 5
const dm = (iso: string) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`

// null while loading, when the job never ran, the call fails or no place is trending: the page then keeps what it showed before the bulletin.
const hasTrend = (b: Bulletin) => b.sections?.some((s) => (s.kind === 'trend' || s.kind === 'hot' || s.kind === 'top') && s.items.some((it) => it.place_id))

// `done` turns true once the answer is in (or failed), so a page of its own can tell "still loading" from "nothing to show".
export function usePulseStatus(): { b: Bulletin | null; done: boolean } {
  const [st, setSt] = useState<{ b: Bulletin | null; done: boolean }>({ b: null, done: false })
  useEffect(() => {
    let live = true
    fetch('/api/harness/pulse').then((r) => (r.ok ? r.json() : null)).then((j: Bulletin | null) => { if (live) setSt({ b: j && hasTrend(j) ? j : null, done: true }) }, () => { if (live) setSt({ b: null, done: true }) })
    return () => { live = false }
  }, [])
  return st
}
export const usePulse = (): Bulletin | null => usePulseStatus().b

export const items = (b: Bulletin, kind: string) => b.sections.find((s) => s.kind === kind)?.items ?? []

// The server ranks (`trend`: one score over every signal). An older harness without that section: "đang hot" and
// "nhiều nguồn cùng nhắc" take turns, a place in both appearing once.
export function ranked(b: Bulletin): Item[] {
  const trend = items(b, 'trend')
  if (trend.length) return trend
  const top = items(b, 'top')
  const hot: Item[] = items(b, 'hot').map((h) => ({ ...h, rising: h.rising || top.some((t) => t.place_id === h.place_id && t.rising) }))
  const seen = new Set(hot.map((h) => h.place_id))
  const rest = top.filter((t) => !seen.has(t.place_id))
  const out: Item[] = []
  for (let i = 0; i < Math.max(hot.length, rest.length); i++) out.push(...[hot[i], rest[i]].filter((x): x is Item => !!x))
  return out
}

// One word for why a place is rising, never a count ("8 clip" says nothing to someone choosing where to go).
const WHY: Record<string, string> = { tiktok: 'Hot trên TikTok', reviews: 'Khách đang đổ về', rising: 'Điểm đang lên', web: 'Nhiều trang nhắc' }
export const whyOf = (it: Item) => (it.kind === 'trend' ? it.signal : WHY[it.signal_kind ?? '']) || 'Đang được nhắc nhiều'

// The last day of an event: its `signal` ends with the last date ("16–20/11", "30/11–02/12", "19/12"); the year follows the start.
export function endOf(e: Item): string {
  const m = /(\d{1,2})\/(\d{1,2})\s*$/.exec(e.signal ?? '')
  if (!m || !e.on) return e.on ?? ''
  const y = Number(e.on.slice(0, 4)) + (Number(m[2]) < Number(e.on.slice(5, 7)) ? 1 : 0)
  return `${y}-${m[2].padStart(2, '0')}-${m[1].padStart(2, '0')}`
}
// Dated events not yet over (a holiday, or a claim the corpus holds as confirmed), the nearest first; month-only claims are only "tham khảo".
export function nextEvents(b: Bulletin, today: string, limit = SHOWN): Item[] {
  return items(b, 'event').filter((e) => e.on && endOf(e) >= today).sort((x, y) => x.on!.localeCompare(y.on!)).slice(0, limit)
}

// A place's level is the server's score (TikTok authors, review jump, rising rating, sites that name it); flames show it without a number:
// 3 from 40 up, 2 from 30, otherwise 1.
const flames = (level: number) => (level >= 40 ? 3 : level >= 30 ? 2 : 1)

const open = (it: Item, e: { currentTarget: HTMLElement }) => { if (it.place_id) openPlace(it.place_id, e.currentTarget.querySelector('figure') ?? e.currentTarget) }

const cap = (t: string) => t[0].toUpperCase() + t.slice(1)
export type Hover = { it: Item; n: number; row: HTMLElement }

// One row: its rank, a round photo (or the event's / season's picture), name on one line (the tail fades when long), kind and rating (or the
// dates and venue, or the places worth seeing in a season), and the visible reason with its flames (an event: how many days away; a season: its months).
export function Row({ it, n, level, today, onHover }: { it: Item; n: number; level: number; today: string; onHover?: (h: Hover | null) => void }) {
  const event = it.kind === 'event'
  const season = it.kind === 'season'
  const p = !event && !season && it.place_id ? info(it.place_id) : undefined
  const left = event ? daysTo(it.on!, today) : 0
  // The line under the name: the venue of an event (its status and dates are tags / the label), the kind and rating of a place, the season's summary.
  const meta = season ? (it.see ?? []).map((id) => info(id)?.name).filter((x): x is string => !!x).slice(0, 2).join(', ') || (it.summary ?? '') : event ? venueOf(it) || whenOf(it) : [p?.category, p?.rating ? `★ ${p.rating.toFixed(1)}` : null].filter(Boolean).join(' · ')
  const title = season ? cap(it.title) : it.title
  const why = season ? monthsOf(it) : event ? leftText(left) : whyOf(it)
  const body = (
    <>
      <b className="tg-pulse__n" aria-hidden="true">{n}</b>
      <figure className="tg-pulse__th">
        {event ? <EventThumb it={it} /> : season ? <SeasonThumb it={it} /> : <PlacePhoto id={it.place_id!} name={it.title} eager={n === 1} sizes="140px" />}
      </figure>
      <span className="tg-pulse__tx">
        <strong>{title}</strong>
        {meta && <small>{meta}</small>}
        {(why || it.hot) && <span className="tg-pulse__tags" aria-hidden="true">
          {why && <span className={`tg-pulse__why ${event || season ? 'is-event' : ''}`}>{event ? <Icon name="calendar" size={12} /> : season ? <Icon name="sun" size={12} /> : Array.from({ length: flames(level) }, (_, k) => <Icon key={k} name="flame" size={12} />)}{why}</span>}
          {/* a place whose reason already says "Hot …" needs no second badge */}
          {!(why && !event && !season && /^Hot/.test(why)) && <HotTag it={it} />}
        </span>}
      </span>
    </>
  )
  const label = `${event ? 'Sự kiện' : season ? 'Mùa' : 'Hạng'} ${n}: ${title}. ${it.hot ? 'Đang hot. ' : ''}${event ? `${whenOf(it)}. ` : ''}${why}${event || season ? '. Xem chi tiết' : ''}`
  // An event and a season open their post; a place opens its sheet.
  return (
    <li className="tg-pulse__row" style={{ '--i': n - 1 } as CSSProperties}
      onPointerEnter={onHover ? (e) => { if (e.pointerType === 'mouse') onHover({ it, n, row: e.currentTarget }) } : undefined}
      onPointerLeave={onHover ? (e) => { if (e.pointerType === 'mouse') onHover(null) } : undefined}
      onFocus={onHover ? (e) => { if (e.target.matches(':focus-visible')) onHover({ it, n, row: e.currentTarget }) } : undefined}
      onBlur={onHover ? () => onHover(null) : undefined}>
      {event
        ? <EventPost it={it} today={today}><button type="button" className="tg-pulse__btn" aria-label={label}>{body}</button></EventPost>
        : season
          ? <SeasonPost it={it}><button type="button" className="tg-pulse__btn" aria-label={label}>{body}</button></SeasonPost>
          : <button type="button" className="tg-pulse__btn" onClick={(e) => open(it, e)} aria-label={label}>{body}</button>}
    </li>
  )
}

// The card that opens beside the rail while a row is pointed at (the reference "Top 5" card): the picture full-bleed, the rank large, the
// name, a short summary and the way in. Only what the bulletin and the place already say; it hides again on leave, scroll or click. A
// presentation of the row (keyboard and screen readers use the row itself), so it is hidden from them.
function Preview({ h, open, today, onEnter, onLeave }: { h: Hover; open: boolean; today: string; onEnter: () => void; onLeave: () => void }) {
  const ref = useRef<HTMLDivElement>(null)
  const wasOpen = useRef(false) // was the card showing when this row took over? then it glides there, else it appears in place
  const [pos, setPos] = useState<{ left: number; top: number; ny: number; glide: boolean } | null>(null)
  const { it, n } = h
  const event = it.kind === 'event'
  const season = it.kind === 'season'
  useLayoutEffect(() => {
    const card = ref.current
    const rail = h.row.closest('.tg-pulse__list')?.getBoundingClientRect()
    if (!card || !rail) return
    const row = h.row.getBoundingClientRect()
    const w = card.offsetWidth
    const gap = 0
    const left = rail.left - w - gap >= 8 ? rail.left - w - gap : rail.right + gap
    if (left + w > innerWidth - 8) { setPos(null); return }
    const hgt = card.offsetHeight
    const mid = row.top + row.height / 2
    const top = Math.min(Math.max(mid - hgt / 2, 8), Math.max(8, innerHeight - hgt - 8))
    setPos({ left, top, ny: Math.min(Math.max(mid - top, 28), hgt - 28), glide: wasOpen.current })
  }, [h])
  useEffect(() => { wasOpen.current = open }, [open, h])
  const p = !event && !season && it.place_id ? info(it.place_id) : null
  const left = event && it.on ? daysTo(it.on, today) : 0
  // At most three short lines, each with its icon: nothing here is a paragraph (the summary is in the detail one click away). An event: when (with the hour
  // when the bulletin gives one, and how many days it lasts), where, how far away.
  const facts: { icon: IconName; text: string }[] = event
    ? [{ icon: 'calendar', text: `${whenOf(it)}${spanDays(it) > 1 ? ` · ${spanDays(it)} ngày` : ''}` }, ...(venueOf(it) ? [{ icon: 'pin' as const, text: venueOf(it) }] : []), { icon: 'clock', text: leftText(left) }]
    : season
      ? [{ icon: 'sun', text: monthsOf(it) }, ...(it.hot_note ? [{ icon: 'flame' as const, text: `Đang hot · ${it.hot_note}` }] : []), ...((it.see ?? []).map((id) => info(id)?.name).filter((x): x is string => !!x).slice(0, 2).length ? [{ icon: 'pin' as const, text: (it.see ?? []).map((id) => info(id)?.name).filter((x): x is string => !!x).slice(0, 2).join(', ') }] : [])]
      : [...(p?.rating ? [{ icon: 'star' as const, text: `${p.rating.toFixed(1)}${p.reviews ? ` · ${p.reviews.toLocaleString('vi-VN')} đánh giá` : ''}` }] : []), { icon: 'flame', text: whyOf(it) }, ...(p?.area ? [{ icon: 'pin' as const, text: p.area }] : [])]
  return createPortal(
    <div ref={ref} className={`tg tg-home tg-pv ${open && pos ? 'is-in' : ''} ${pos?.glide ? 'is-glide' : ''}`} style={pos ? { left: pos.left, top: pos.top, '--ny': `${pos.ny}px` } as CSSProperties : undefined}
      aria-hidden="true" data-side={pos && pos.left > h.row.getBoundingClientRect().left ? 'r' : 'l'} onPointerEnter={onEnter} onPointerLeave={onLeave}>
      <div className="tg-pv__pic" key={`p${it.id}`}>
        {event ? <EventThumb it={it} sizes="320px" /> : season ? <SeasonThumb it={it} sizes="320px" /> : <PlacePhoto id={it.place_id!} name={it.title} sizes="320px" />}
      </div>
      <div className="tg-pv__body" key={`b${it.id}`}>
        <div className="tg-pv__head">
          <b className="tg-pv__n">{String(n).padStart(2, '0')}</b>
          <strong>{season ? cap(it.title) : it.title}</strong>
        </div>
        <ul>{facts.map((f) => <li key={f.icon}><Icon name={f.icon} size={14} /><span>{f.text}</span></li>)}</ul>
        <button type="button" tabIndex={-1} onClick={() => h.row.querySelector<HTMLElement>('.tg-pulse__btn')?.click()}>{event || season ? 'Xem chi tiết' : 'Xem nơi này'}</button>
      </div>
    </div>,
    document.body,
  )
}

type Tab = 'event' | 'place' | 'season'
const TABS: { id: Tab; label: string; sub: (stale: string | null) => string }[] = [
  { id: 'event', label: 'Sự kiện', sub: () => 'Sắp diễn ra ở Đà Lạt' },
  { id: 'place', label: 'Địa điểm', sub: (stale) => stale ?? 'Hot tuần này' },
  { id: 'season', label: 'Mùa', sub: () => 'Đang vào mùa' },
]
const TAB_ICON = { event: 'calendar', place: 'flame', season: 'sun' } as const

export function Pulse({ b }: { b: Bulletin }) {
  useSnapshot() // photos and ratings come from the web's snapshot once it lands
  const today = localDay()
  const events = nextEvents(b, today)
  const places = ranked(b).filter((it) => it.place_id && info(it.place_id)?.photos.length).sort((x, y) => (y.score ?? 0) - (x.score ?? 0)).slice(0, SHOWN)
  const seasons = items(b, 'season').filter((s) => s.image || s.summary).slice(0, SHOWN)
  const have = { event: events, place: places, season: seasons }
  const tabs = TABS.filter((t) => have[t.id].length)
  const [at, setAt] = useState<Tab | null>(null)
  const [dir, setDir] = useState(0) // which way the last tab switch went: the new rows slide in from that side
  const [hv, setHv] = useState<Hover | null>(null) // the row the card is on; kept after it hides so the card fades out in place
  const [open, setOpen] = useState(false)
  const timer = useRef(0)
  const cur = tabs.find((t) => t.id === at) ?? tabs[0]
  // Opens a moment after the pointer arrives (a sweep across the list does not flash cards), moves at once while it is open, and stays while the
  // pointer is on the card.
  const hover = (h: Hover | null) => {
    clearTimeout(timer.current)
    if (h) { if (open) { setHv(h) } else timer.current = window.setTimeout(() => { setHv(h); setOpen(true) }, 140) }
    else timer.current = window.setTimeout(() => setOpen(false), 160)
  }
  const hide = () => { clearTimeout(timer.current); setOpen(false) }
  useEffect(() => { addEventListener('scroll', hide, { capture: true, passive: true }); return () => { removeEventListener('scroll', hide, { capture: true }); clearTimeout(timer.current) } }, [])
  if (!cur) return null
  const stale = b.stale && b.day ? `Chưa làm mới từ ${dm(b.day)}` : null
  const rows = have[cur.id].map((it) => ({ it, level: cur.id === 'place' ? it.score ?? 0 : 0 }))
  return (
    <div className="tg-hm__trend tg-pulse" data-tour="trending" onClick={hide}>
      <div className="tg-hm__thead tg-pulse__head">
        <div>
          <h2><Icon name={TAB_ICON[cur.id]} size={18} key={cur.id} />Trending</h2>
          <p key={cur.id}>{cur.sub(stale)}</p>
        </div>
        <TrendingSheet b={b}><button type="button" className="tg-pulse__more" aria-label="Xem bảng xếp hạng xu hướng"><Icon name="trendUp" size={15} /><span>Xếp hạng</span></button></TrendingSheet>
      </div>
      {tabs.length > 1 && <div className="tg-pulse__tabs" role="tablist" aria-label="Loại xu hướng" style={{ '--n': tabs.length, '--at': tabs.indexOf(cur) } as CSSProperties}>
        {tabs.map((t) => <button key={t.id} type="button" role="tab" aria-selected={t.id === cur.id} onClick={() => { if (t.id === cur.id) return; hide(); setDir(tabs.indexOf(t) > tabs.indexOf(cur) ? 1 : -1); setAt(t.id) }}>{t.label}</button>)}
      </div>}
      <ol className="tg-pulse__list" role="tabpanel" style={{ '--dx': `${dir * 24}px`, '--dy': dir ? '0px' : '10px' } as CSSProperties}>
        {rows.map(({ it, level }, i) => <Row key={`${cur.id}:${it.id}`} it={it} n={i + 1} level={level} today={today} onHover={hover} />)}
      </ol>
      {hv && <Preview h={hv} open={open} today={today} onEnter={() => clearTimeout(timer.current)} onLeave={() => hover(null)} />}
    </div>
  )
}
