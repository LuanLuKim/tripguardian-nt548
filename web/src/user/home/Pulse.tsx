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
// One dated event may sit above them. No "xem thêm": what is not worth the rail is not drawn (owner, 2026-11-04).
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
function ranked(b: Bulletin): Item[] {
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
const whyOf = (it: Item) => (it.kind === 'trend' ? it.signal : WHY[it.signal_kind ?? '']) || 'Đang được nhắc nhiều'

const daysTo = (iso: string, day: string | null) => Math.round((Date.parse(iso) - Date.parse(day ?? new Date().toISOString().slice(0, 10))) / 86_400_000)

// A dated event (a holiday, or a claim the corpus holds as confirmed) still ahead; month-only claims are only "tham khảo".
function pinned(b: Bulletin): Item | null {
  const today = new Date().toISOString().slice(0, 10)
  return items(b, 'event').find((e) => e.on && daysTo(e.on, today) >= 0 && daysTo(e.on, today) <= EVENT_DAYS) ?? null
}

const open = (it: Item, e: { currentTarget: HTMLElement }) => { if (it.place_id) openPlace(it.place_id, e.currentTarget.querySelector('figure') ?? e.currentTarget) }

function Meta({ id }: { id: string }) {
  const p = info(id)
  const bits = [p?.category, p?.rating ? `★ ${p.rating.toFixed(1)}` : null].filter(Boolean)
  return bits.length ? <small className="tg-pulse__meta">{bits.join(' · ')}</small> : null
}

function Why({ it }: { it: Item }) {
  return <span className="tg-pulse__why"><Icon name={it.rising && it.kind !== 'trend' ? 'trendUp' : 'flame'} size={13} />{whyOf(it)}</span>
}

function Lead({ it }: { it: Item }) {
  return (
    <li className="tg-pulse__lead" style={{ '--i': 0 } as CSSProperties}>
      <button type="button" onClick={(e) => open(it, e)} aria-label={`Hạng 1: ${it.title}`}>
        <PlacePhoto id={it.place_id!} name={it.title} eager sizes="320px" />
        <span className="tg-pulse__shade" aria-hidden="true" />
        <b className="tg-pulse__rank" aria-hidden="true">1</b>
        <span className="tg-pulse__cap">
          <Why it={it} />
          <strong title={it.title}>{it.title}</strong>
          <Meta id={it.place_id!} />
        </span>
      </button>
    </li>
  )
}

function Row({ it, n }: { it: Item; n: number }) {
  return (
    <li className="tg-pulse__row" style={{ '--i': n - 1 } as CSSProperties}>
      <button type="button" onClick={(e) => open(it, e)} aria-label={`Hạng ${n}: ${it.title}`}>
        <span className="tg-pulse__th"><PlacePhoto id={it.place_id!} name={it.title} sizes="120px" /><b aria-hidden="true">{n}</b></span>
        <span className="tg-pulse__tx">
          <strong title={it.title}>{it.title}</strong>
          <Meta id={it.place_id!} />
          <Why it={it} />
        </span>
      </button>
    </li>
  )
}

// One dated event: its day in a small tile and how long is left.
function Event({ it }: { it: Item }) {
  const iso = it.on!
  const left = daysTo(iso, new Date().toISOString().slice(0, 10))
  const body = (
    <>
      <span className="tg-pulse__date" aria-hidden="true"><b>{Number(iso.slice(8, 10))}</b><small>Th{Number(iso.slice(5, 7))}</small></span>
      <span className="tg-pulse__tx"><strong title={it.title}>{it.title}</strong><small>{left === 0 ? 'Hôm nay' : left === 1 ? 'Ngày mai' : `Còn ${left} ngày`} · {dm(iso)}</small></span>
    </>
  )
  return <div className="tg-pulse__event">{it.place_id ? <button type="button" onClick={(e) => open(it, e)}>{body}</button> : <div>{body}</div>}</div>
}

export function Pulse({ b }: { b: Bulletin }) {
  useSnapshot() // photos and ratings come from the web's snapshot once it lands
  const shown = ranked(b).filter((it) => it.place_id && info(it.place_id)?.photos.length).slice(0, SHOWN)
  const event = pinned(b)
  if (!shown.length && !event) return null
  return (
    <div className="tg-hm__trend tg-pulse" data-tour="trending">
      <div className="tg-hm__thead">
        <h2><Icon name="flame" size={18} />Trending</h2>
        <p>{b.stale && b.day ? `Chưa làm mới từ ${dm(b.day)}` : 'Đà Lạt đang được nhắc tới tuần này'}</p>
      </div>
      {event && <Event it={event} />}
      <ol className="tg-pulse__list">
        {shown[0] && <Lead it={shown[0]} />}
        {shown.slice(1).map((it, i) => <Row key={it.id} it={it} n={i + 2} />)}
      </ol>
    </div>
  )
}
