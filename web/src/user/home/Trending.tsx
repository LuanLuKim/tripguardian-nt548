import { useState, type CSSProperties } from 'react'
import { useSnapshot } from '../../data/store'
import { info } from '../lib'
import { openPlace } from '../ui/PlaceSheet'
import { Empty, ArtHills, Busy, go, PlacePhoto } from '../ui/common'
import { Icon } from '../ui/icons'
import { Page, useTitle } from '../ui/Shell'
import { EventPost, EventThumb, daysTo, leftText, localDay, venueOf } from './EventPost'
import { monthsOf } from './SeasonPost'
import { HotTag } from './HotTag'
import { items, nextEvents, ranked, Row, usePulseStatus, whyOf, type Bulletin, type Item } from './Pulse'
import '../css/trending.css'

// The chart of what Đà Lạt is talking about now (the page behind the "Xếp hạng" button of the home Trending card): the places that rank
// highest, the next dated events, and the seasons the city is in. Same data and same rules as the card (docs/CORPUS.md §Nhịp): one score from the
// server shown as flames, no counts; a place with no photo the rules allow is not a card; an event opens its post.
const dm = (iso: string) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`
const cap = (s: string) => s[0].toUpperCase() + s.slice(1)
const flames = (level: number) => (level >= 40 ? 3 : level >= 30 ? 2 : 1)
const open = (it: Item, e: { currentTarget: HTMLElement }) => { if (it.place_id) openPlace(it.place_id, e.currentTarget.querySelector('figure') ?? e.currentTarget) }

function Why({ it }: { it: Item }) {
  return <span className="tg-tr__why">{Array.from({ length: flames(it.score ?? 0) }, (_, k) => <Icon key={k} name="flame" size={13} />)}{whyOf(it)}</span>
}

// The first three: one large card and two beside it, the name over the photo.
function Podium({ top }: { top: Item[] }) {
  return (
    <ol className="tg-tr__podium">
      {top.map((it, i) => {
        const p = info(it.place_id!)
        const meta = [p?.category, p?.rating ? `★ ${p.rating.toFixed(1)}` : null].filter(Boolean).join(' · ')
        return (
          <li key={it.id} className={`tg-tr__top is-${i + 1}`}>
            <button type="button" onClick={(e) => open(it, e)} aria-label={`Hạng ${i + 1}: ${it.title}. ${whyOf(it)}`}>
              <PlacePhoto id={it.place_id!} name={it.title} eager sizes={i === 0 ? '640px' : '360px'} />
              <b className="tg-tr__rank" aria-hidden="true">{i + 1}</b>
              <span className="tg-tr__cap">
                <strong>{it.title}</strong>
                {meta && <small>{meta}</small>}
                <Why it={it} />
              </span>
            </button>
          </li>
        )
      })}
    </ol>
  )
}

function EventCard({ it, n, today }: { it: Item; n: number; today: string }) {
  const venue = venueOf(it)
  const when = it.text.includes(' · ') ? it.text.slice(0, it.text.indexOf(' · ')) : it.text
  return (
    <li>
      <b className="tg-tr__n" aria-hidden="true">{n}</b>
      <EventPost it={it} today={today}>
        <button type="button" className="tg-tr__ev" aria-label={`${it.title}. ${when}. Xem chi tiết`}>
          <figure><EventThumb it={it} sizes="360px" /><span>{when}</span></figure>
          <strong>{it.title}</strong>
          {venue && <small><Icon name="pin" size={13} />{venue}</small>}
          <em>{leftText(it.on ? daysTo(it.on, today) : 0)}</em>
          <HotTag it={it} />
        </button>
      </EventPost>
    </li>
  )
}

function SeasonCard({ it, n }: { it: Item; n: number }) {
  const see = (it.see ?? []).filter((id) => info(id)).slice(0, 3)
  return (
    <li className="tg-tr__season">
      <b className="tg-tr__n" aria-hidden="true">{n}</b>
      {it.image && <figure><img src={it.image} alt="" loading="lazy" decoding="async" referrerPolicy="no-referrer" onError={(e) => { e.currentTarget.parentElement?.classList.add('is-empty'); e.currentTarget.remove() }} /></figure>}
      <div>
        <span className="tg-tr__chip">{monthsOf(it)}</span><HotTag it={it} />
        <h3>{cap(it.title)}</h3>
        {it.summary && <p>{it.summary}</p>}
        {see.length > 0 && <div className="tg-tr__see"><small>Nơi nên ghé</small>{see.map((id) => <button key={id} type="button" onClick={(e) => openPlace(id, e.currentTarget)}>{info(id)!.name}<Icon name="arrow" size={12} /></button>)}</div>}
      </div>
    </li>
  )
}

// The chart itself, shared by the page at /trending and the sheet that opens over the home page from the "Xếp hạng" button. One ranking per tab
// (hot places, the season people are talking about, upcoming events), so a page holds one list at a time. Same data and rules as the home card.
type Tab = 'place' | 'season' | 'event'
const TABS = [['place', 'Địa điểm hot', 'flame'], ['season', 'Mùa', 'sun'], ['event', 'Sự kiện sắp tới', 'calendar']] as const

export function TrendingChart({ b }: { b: Bulletin }) {
  useSnapshot()
  const [at, setAt] = useState<Tab | null>(null)
  const today = localDay()
  const places = ranked(b).filter((it) => it.place_id && info(it.place_id)?.photos.length).sort((x, y) => (y.score ?? 0) - (x.score ?? 0)).slice(0, 10)
  const events = nextEvents(b, today, 10)
  const seasons = items(b, 'season').filter((s) => s.image || s.summary).slice(0, 10)
  const have = { place: places, season: seasons, event: events }
  const tabs = TABS.filter(([id]) => have[id].length)
  const cur = tabs.find(([id]) => id === at) ?? tabs[0]
  const updated = b.generated_at ? dm(b.generated_at) : b.day ? dm(b.day) : null
  // The tab picks the ranking on the left, in full; the one after it in the tab order sits on the right in smaller cards, and its heading opens it.
  const next = tabs.length > 1 ? tabs[(tabs.indexOf(cur) + 1) % tabs.length] : null
  const SUB: Record<Tab, string> = {
    place: 'Xếp theo điểm xu hướng: càng nhiều nguồn cùng nhắc tới, càng lên cao.',
    season: 'Những thứ chỉ đẹp vào đúng mùa, và nơi nên ghé để thấy chúng.',
    event: 'Xếp theo ngày gần nhất. Bấm vào một sự kiện để xem chi tiết.',
  }
  const board = (id: Tab, side: boolean) => {
    const [, label, icon] = TABS.find(([t]) => t === id)!
    return (
      <section className={`tg-tr__panel ${side ? 'is-side' : ''}`} key={`${id}:${side}`} role={side ? undefined : 'tabpanel'} aria-label={label}>
        <h2 className="tg-tr__h"><Icon name={icon} size={19} />{label}{side && <button type="button" onClick={() => setAt(id)} aria-label={`Xem bảng ${label}`}>Xem<Icon name="arrow" size={13} /></button>}</h2>
        {!side && <p className="tg-tr__sub">{SUB[id]}</p>}
        {id === 'place' && <>
          {!side && <Podium top={places.slice(0, 3)} />}
          <ol className="tg-pulse__list tg-tr__rows" start={side ? 1 : 4}>{(side ? places : places.slice(3)).map((it, i) => <Row key={it.id} it={it} n={i + (side ? 1 : 4)} level={it.score ?? 0} today={today} />)}</ol>
        </>}
        {id === 'season' && <ol className="tg-tr__seasons">{seasons.map((it, i) => <SeasonCard key={it.id} it={it} n={i + 1} />)}</ol>}
        {id === 'event' && <ol className="tg-tr__events">{events.map((it, i) => <EventCard key={it.id} it={it} n={i + 1} today={today} />)}</ol>}
      </section>
    )
  }
  return (
    <>
      <header className="tg-tr__head">
        <p className="tg-kicker">Bảng xếp hạng</p>
        <h1>Đà Lạt đang hot gì?</h1>
        <p>Gộp từ video TikTok, đánh giá Google Maps và các trang web của những ngày gần đây{updated ? `. Cập nhật ${updated}${b.stale ? ', chưa làm mới sau đó' : ''}` : ''}.</p>
        {tabs.length > 1 && <div className="tg-pulse__tabs tg-tr__tabs" role="tablist" aria-label="Bảng xếp hạng" style={{ '--n': tabs.length, '--at': tabs.indexOf(cur) } as CSSProperties}>
          {tabs.map(([id, label, icon]) => <button key={id} type="button" role="tab" aria-selected={id === cur[0]} onClick={() => setAt(id)}><Icon name={icon} size={15} />{label}</button>)}
        </div>}
      </header>

      {cur && <div className="tg-tr__cols">
        {board(cur[0], false)}
        {next && board(next[0], true)}
      </div>}
    </>
  )
}

export function Trending() {
  useTitle('Xu hướng Đà Lạt')
  useSnapshot()
  const { b, done } = usePulseStatus()
  if (!b) return <Page className="tg-tr tg-trc">{done ? <Empty art={<ArtHills />} title="Chưa có bảng xếp hạng" body="Bản tin xu hướng chưa được làm mới. Bạn quay lại sau nhé." action={<button type="button" className="tg-btn tg-btn--primary" onClick={() => go('/')}>Về Dành cho bạn</button>} /> : <Busy text="Đang tải xu hướng…" />}</Page>
  return <Page className="tg-tr tg-trc"><TrendingChart b={b} /></Page>
}
