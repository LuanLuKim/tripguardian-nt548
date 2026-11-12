import { useEffect, useState, type CSSProperties } from 'react'
import { useSnapshot } from '../../data/store'
import { info } from '../lib'
import { openPlace } from '../ui/PlaceSheet'
import { PlacePhoto } from '../ui/common'
import { Icon } from '../ui/icons'
import '../css/pulse.css'

// Trending (docs/CORPUS.md §Nhịp, "Hạng xu hướng"): the bulletin comes from GET /api/harness/pulse. The rail is a short,
// photo-led list: the few places that rank highest (one score from the server, no counts shown), each a real photo, a name and
// one word for why it is rising. Places without a photo the rules allow are skipped (a trend with no picture is not a card).
// A dated event ranks in the same list by how near it is. No "xem thêm": what is not worth the rail is not drawn (owner, 2026-11-04).
type Source = { type: string; label: string; url?: string; date?: string }
export type Item = {
  id: string; kind: string; title: string; text: string; place_id: string | null; sources: Source[]
  // Short fields added by the server (src/corpus/pulse/render.py `_short`); absent on an older harness.
  signal?: string; signal_kind?: string; count?: number | null; score?: number | null; window_days?: number | null; newest?: string | null
  on?: string | null; rising?: boolean; reference?: boolean
}
export type Bulletin = { city: string; generated_at: string | null; day: string | null; stale: boolean; sections: { kind: string; title: string; items: Item[] }[] }

const SHOWN = 4 // one lead and three rows
const EVENT_DAYS = 45 // an event further away is not news yet
const dm = (iso: string) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`

// null while loading, when the job never ran, the call fails or no place is trending: the page then keeps what it showed before the bulletin.
const hasTrend = (b: Bulletin) => b.sections?.some((s) => (s.kind === 'trend' || s.kind === 'hot' || s.kind === 'top') && s.items.some((it) => it.place_id))

export function usePulse(): Bulletin | null {
  const [b, setB] = useState<Bulletin | null>(null)
  useEffect(() => {
    let live = true
    fetch('/api/harness/pulse').then((r) => (r.ok ? r.json() : null)).then((j: Bulletin | null) => { if (live && j && hasTrend(j)) setB(j) }, () => {})
    return () => { live = false }
  }, [])
  return b
}

const items = (b: Bulletin, kind: string) => b.sections.find((s) => s.kind === kind)?.items ?? []

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

const daysTo = (iso: string, day: string | null) => Math.round((Date.parse(iso) - Date.parse(day ?? new Date().toISOString().slice(0, 10))) / 86_400_000)

// A dated event (a holiday, or a claim the corpus holds as confirmed) still ahead; month-only claims are only "tham khảo".
function pinned(b: Bulletin): Item | null {
  const today = new Date().toISOString().slice(0, 10)
  return items(b, 'event').find((e) => e.on && daysTo(e.on, today) >= 0 && daysTo(e.on, today) <= EVENT_DAYS) ?? null
}

// One ranking for everything notable in Đà Lạt, by a 0-100 trending level. A place's level is the server's score (TikTok authors,
// review jump, rising rating, sites that name it). An event has no crowd to count, so its level is how close it is: 100 on the day,
// 3 less for every day away, so it climbs the list as it nears and drops out of the top when it is far.
const EVENT_STEP = 3
const levelOf = (it: Item, today: string) => (it.kind === 'event' ? Math.max(0, 100 - EVENT_STEP * daysTo(it.on!, today)) : it.score ?? 0)
// Flames show the level without a number: 3 from 40 up, 2 from 30, otherwise 1.
const flames = (level: number) => (level >= 40 ? 3 : level >= 30 ? 2 : 1)

const open = (it: Item, e: { currentTarget: HTMLElement }) => { if (it.place_id) openPlace(it.place_id, e.currentTarget.querySelector('figure') ?? e.currentTarget) }

// One row: photo (or a calendar for an event) flush left with its rank, name on one line ("…" when long), kind and rating (or the
// days left), and the visible reason with its flames.
function Row({ it, n, level }: { it: Item; n: number; level: number }) {
  const event = it.kind === 'event'
  const p = !event && it.place_id ? info(it.place_id) : undefined
  const left = event ? daysTo(it.on!, new Date().toISOString().slice(0, 10)) : 0
  const meta = event
    ? `Sự kiện · ${left === 0 ? 'Hôm nay' : left === 1 ? 'Ngày mai' : `còn ${left} ngày`} (${dm(it.on!)})`
    : [p?.category, p?.rating ? `★ ${p.rating.toFixed(1)}` : null].filter(Boolean).join(' · ')
  const why = event ? 'Sắp diễn ra' : whyOf(it)
  const body = (
    <>
      <figure className="tg-pulse__th">
        {event ? <span className="tg-pulse__cal" aria-hidden="true"><Icon name="calendar" size={26} /></span> : <PlacePhoto id={it.place_id!} name={it.title} eager={n === 1} sizes="140px" />}
        <b aria-hidden="true">{n}</b>
      </figure>
      <span className="tg-pulse__tx">
        <strong title={it.title}>{it.title}</strong>
        {meta && <small>{meta}</small>}
        <span className="tg-pulse__why" aria-hidden="true">{Array.from({ length: flames(level) }, (_, k) => <Icon key={k} name="flame" size={12} />)}{why}</span>
      </span>
    </>
  )
  return (
    <li className="tg-pulse__row" style={{ '--i': n - 1 } as CSSProperties}>
      {event && !it.place_id
        ? <div className="tg-pulse__btn" aria-label={`Hạng ${n}: ${it.title}. ${why}`}>{body}</div>
        : <button type="button" className="tg-pulse__btn" onClick={(e) => open(it, e)} aria-label={`Hạng ${n}: ${it.title}. ${why}`}>{body}</button>}
    </li>
  )
}

export function Pulse({ b }: { b: Bulletin }) {
  useSnapshot() // photos and ratings come from the web's snapshot once it lands
  const today = new Date().toISOString().slice(0, 10)
  const event = pinned(b)
  const places = ranked(b).filter((it) => it.place_id && info(it.place_id)?.photos.length)
  const shown = [...places, ...(event ? [event] : [])].map((it) => ({ it, level: levelOf(it, today) })).sort((x, y) => y.level - x.level).slice(0, SHOWN)
  if (!shown.length) return null
  return (
    <div className="tg-hm__trend tg-pulse" data-tour="trending">
      <div className="tg-hm__thead">
        <h2><Icon name="flame" size={18} />Trending</h2>
        <p>{b.stale && b.day ? `Chưa làm mới từ ${dm(b.day)}` : 'Đà Lạt đang được nhắc tới tuần này'}</p>
      </div>
      <ol className="tg-pulse__list">
        {shown.map(({ it, level }, i) => <Row key={it.id} it={it} n={i + 1} level={level} />)}
      </ol>
    </div>
  )
}
