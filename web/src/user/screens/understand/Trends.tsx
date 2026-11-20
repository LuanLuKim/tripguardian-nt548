import { useState } from 'react'
import type { ChatPlace, TrendRow, TrendsBlock } from '../../tu/types'
import { tidyText } from '../../../data/placeName'
import { info } from '../../lib'
import { CardImg } from '../../ui/common'
import { Icon } from '../../ui/icons'
import { openPlace } from '../../ui/PlaceSheet'
import { EventStage } from './Events'
import { PlaceStage } from './Places'
import { SourceChip } from './Sources'

// What is on and in season, under the reply's short words (src/trip/api/blocks.py trends_block): numbered sections of rows,
// each a picture when there is one (the place's photo, a picture found for the season), a title, one short line, a sentence, the page it
// came from, and where to see a season (cards). The events are not rows: they are cards on the photo stage (Events.tsx), opened from one
// line. A section of places ends with the line that opens them as cards (never by itself).

const dm = (iso: string) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`

function Thumb({ r, card }: { r: TrendRow; card?: ChatPlace }) {
  const [broken, setBroken] = useState(false)
  const own = card?.photos[0] ?? (r.id ? info(r.id)?.photos[0]?.src : undefined)
  // no picture, or another site's picture that does not load: the row reads as a paragraph of the article (a day in a
  // grey box looked crude, owner 2026-11-13)
  if (own) return <figure className="tg-tr__img"><CardImg src={own} alt="" /></figure>
  if (!r.image || broken) return null
  return <figure className="tg-tr__img" title={r.image_from ? `Ảnh: ${r.image_from}` : undefined}>
    <img src={r.image} alt="" loading="lazy" decoding="async" referrerPolicy="no-referrer" onError={() => setBroken(true)} />
    {r.image_from && <figcaption>{r.image_from}</figcaption>}
  </figure>
}

// A season's places to see it at, an event's venue (corpus places): each opens its card
function SeeAt({ ids, label, cards }: { ids: string[]; label: string; cards: Map<string, ChatPlace> }) {
  const named = ids.map(id => ({ id, name: cards.get(id)?.name ?? info(id)?.name })).filter((x): x is { id: string; name: string } => !!x.name)
  if (!named.length) return null
  return <div className="tg-tr__see"><span>{label}</span>{named.map(x =>
    <button key={x.id} type="button" className="tg-tr__seebtn" onClick={() => openPlace(x.id)}>{tidyText(x.name)}</button>)}</div>
}

function Row({ r, card, kind, cards }: { r: TrendRow; card?: ChatPlace; kind: string; cards: Map<string, ChatPlace> }) {
  const title = tidyText(card?.name ?? r.title)
  const meta = r.meta ?? [card?.category, card?.area].filter(Boolean).join(' · ')
  return <li className="tg-tr__row">
    <Thumb r={r} card={card} />
    <div className="tg-tr__body">
      {r.id ? <button type="button" className="tg-tr__title" onClick={() => openPlace(r.id!)}>{title}</button>
        : r.source ? <a className="tg-tr__title" href={r.source.url} target="_blank" rel="noopener noreferrer">{title}</a>
        : <b className="tg-tr__title is-plain">{title}</b>}
      {r.hot && <span className="tg-hot" title={r.hot}><Icon name="flame" size={11} />Đang hot</span>}
      {meta && <small className="tg-tr__meta">{tidyText(meta)}</small>}
      {(r.text || r.source) && <p>{tidyText(r.text)}{r.source && <> <SourceChip source={r.source} /></>}</p>}
      {r.see?.length ? <SeeAt ids={r.see} label={kind === 'season' ? 'Ngắm ở' : 'Nơi diễn ra'} cards={cards} /> : null}
    </div>
  </li>
}

export function Trends({ block, busy, onLike }: { block: TrendsBlock; busy: boolean; onLike: (id: string, on: boolean) => void }) {
  const cards = new Map(block.cards.map(c => [c.id, c]))
  const numbered = block.sections.length > 1
  return <section className="tg-tr" aria-label="Đà Lạt dạo này">
    {block.sections.map((s, i) => {
      const places = s.rows.map(r => (r.id ? cards.get(r.id) : undefined)).filter((c): c is ChatPlace => !!c)
      return <div key={s.kind} className="tg-tr__sec">
        {s.kind === 'event' ? <EventStage rows={s.rows} cards={cards} heading={s.heading} /> : <>
        <h4>{numbered ? `${i + 1}. ` : ''}{s.heading}</h4>
        <ul>{s.rows.map((r, j) => <Row key={j} r={r} card={r.id ? cards.get(r.id) : undefined} kind={s.kind} cards={cards} />)}</ul>
        {places.length >= 2 && <PlaceStage row={{ ids: places.map(c => c.id), why: s.heading, cards: places }} busy={busy} onLike={onLike} />}
        </>}
      </div>
    })}
    <small className="tg-tr__asof">Nhịp Đà Lạt · cập nhật {dm(block.as_of)}</small>
  </section>
}
