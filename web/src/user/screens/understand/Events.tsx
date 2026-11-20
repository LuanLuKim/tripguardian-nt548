import { useRef, useState, type KeyboardEvent } from 'react'
import { tidyText } from '../../../data/placeName'
import { daysTo, leftText, localDay } from '../../home/EventPost'
import { info } from '../../lib'
import type { ChatPlace, TrendRow } from '../../tu/types'
import { CardImg } from '../../ui/common'
import { Icon } from '../../ui/icons'
import { openPlace } from '../../ui/PlaceSheet'
import { StageFrame, StageRing, stageKeys, useStage, type StageCard } from './Ask'

// What is on, as cards on the same photo stage as the places (docs/UI_SPEC_USER_WEB.md): a poster, the event's name, when and where, how
// far away it is, and one sentence of what happens. Everything comes from the trends block's own row (the corpus's dated event); the
// round button opens the page it was read from, the front card opens the venue when it is a place we know.

const dm = (iso: string) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`

// The poster: the event's own picture (another site's, so no referrer is sent), else the venue's photo, else a warm calendar tile with the day.
function Poster({ r, venue }: { r: TrendRow; venue?: ChatPlace }) {
  const [broken, setBroken] = useState(false)
  if (r.image && !broken) return <img src={r.image} alt="" decoding="async" referrerPolicy="no-referrer" draggable={false} onError={() => setBroken(true)} />
  const own = venue?.photos[0] ?? (venue ? info(venue.id)?.photos[0]?.src : undefined)
  if (own) return <CardImg src={own} alt="" draggable={false} />
  return <span className="tg-evc__cal" aria-hidden="true"><Icon name="calendar" size={40} />{r.on && <b>{dm(r.on)}</b>}</span>
}

function eventCard(r: TrendRow, venue: ChatPlace | undefined, today: string): StageCard {
  const title = tidyText(r.title)
  const left = r.on ? leftText(daysTo(r.on, today)) : null
  const credit = r.image && r.image_from ? r.image_from : null
  return {
    id: `${r.title}|${r.on ?? ''}`, photo: null, alt: title, title, on: false,
    media: <Poster r={r} venue={venue} />,
    badge: r.hot ? <span className="tg-stage__badge is-hot"><Icon name="flame" size={13} />Đang hot</span> : null,
    extra: credit ? <small className="tg-evc__credit">Ảnh: {credit}</small> : null,
    line: <>
      <small><Icon name="calendar" size={13} />{tidyText(r.meta ?? '') || (r.on ? dm(r.on) : 'Sắp diễn ra')}</small>
      {left && <small className="tg-evc__left"><Icon name="clock" size={13} />{left}</small>}
      {r.text && <small className="tg-evc__sum">{tidyText(r.text)}</small>}
    </>,
    pick: <Icon name="external" size={18} strokeWidth={2.2} />,
    pickLabel: r.source ? `Mở trang nói về ${title}` : `Xem ${title}`,
  }
}

export function EventStage({ rows, cards, heading }: { rows: TrendRow[]; cards: Map<string, ChatPlace>; heading: string }) {
  const { open, setOpen, leaving, close } = useStage(false)
  const [at, setAt] = useState(0)
  const panel = useRef<HTMLDivElement>(null)
  if (!rows.length) return null
  const today = localDay()
  const venueOf = (r: TrendRow) => cards.get(r.see?.[0] ?? '')
  const view = (i: number) => {
    const v = venueOf(rows[i])
    if (v) close(() => openPlace(v.id))
    else if (rows[i].source) window.open(rows[i].source!.url, '_blank', 'noopener,noreferrer')
  }
  const source = (i: number) => { if (rows[i].source) window.open(rows[i].source!.url, '_blank', 'noopener,noreferrer') }
  const keys = (e: KeyboardEvent<HTMLDivElement>) => stageKeys(e, panel, rows.length, setAt, () => close(), () => view(at))
  const stage = rows.map(r => eventCard(r, venueOf(r), today))
  const names = rows.slice(0, 2).map(r => tidyText(r.title)).join(', ')
  return <>
    <button type="button" className="tg-stage__reopen" onClick={() => setOpen(true)}>
      <span className="tg-stage__thumbs" aria-hidden="true">{rows.slice(0, 3).map((r, i) => {
        const own = r.image ?? venueOf(r)?.photos[0]
        return own ? <img key={i} src={own} alt="" loading="lazy" decoding="async" referrerPolicy="no-referrer" onError={e => { e.currentTarget.style.visibility = 'hidden' }} /> : <i key={i} />
      })}</span>
      <span><b>{heading}</b><small>{rows.length} sự kiện · {names}{rows.length > 2 ? '…' : ''}</small></span>
      <Icon name="chevronRight" size={18} />
    </button>
    {open && <StageFrame leaving={leaving} kicker={`${rows.length} sự kiện`} question={heading} onClose={() => close()} onKeyDown={keys} panel={panel}>
      <StageRing cards={stage} at={at} setAt={setAt} busy={false} label="Sự kiện sắp diễn ra" prevLabel="Sự kiện trước" nextLabel="Sự kiện sau"
        hint="Lăn chuột hoặc dùng ← → để xoay · bấm thẻ giữa để xem nơi diễn ra" onFront={view} onPick={source} />
      <footer className="tg-stage__foot">
        <p className="tg-stage__note">Giờ giấc có thể thay đổi, kiểm tra lại trang gốc trước khi đi.</p>
        <button type="button" className="tg-btn tg-btn--primary" onClick={() => close()}>Xong <Icon name="check" size={16} /></button>
      </footer>
    </StageFrame>}
  </>
}
