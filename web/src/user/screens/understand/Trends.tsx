import type { ChatPlace, TrendRow, TrendsBlock } from '../../tu/types'
import { tidyText } from '../../../data/placeName'
import { info } from '../../lib'
import { CardImg } from '../../ui/common'
import { openPlace } from '../../ui/PlaceSheet'
import { PlaceStage } from './Places'
import { SourceChip } from './Sources'

// What is on and in season, under the reply's short words (src/trip/api/blocks.py trends_block): numbered sections of rows,
// each a picture when there is one (the place's photo, the event page's own picture), a title, one short line, a
// sentence and the page it came from. A section of places ends with the line that opens them as cards (never by itself).

const dm = (iso: string) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`

function Thumb({ r, card }: { r: TrendRow; card?: ChatPlace }) {
  const photo = card?.photos[0] ?? (r.id ? info(r.id)?.photos[0]?.src : undefined) ?? r.image
  // no picture: the row reads as a paragraph of the article (a day in a grey box looked crude, owner 2026-11-13)
  return photo ? <CardImg className="tg-tr__img" src={photo} alt="" /> : null
}

function Row({ r, card }: { r: TrendRow; card?: ChatPlace }) {
  const title = tidyText(card?.name ?? r.title)
  const meta = r.meta ?? [card?.category, card?.area].filter(Boolean).join(' · ')
  return <li className="tg-tr__row">
    <Thumb r={r} card={card} />
    <div className="tg-tr__body">
      {r.id ? <button type="button" className="tg-tr__title" onClick={() => openPlace(r.id!)}>{title}</button>
        : r.source ? <a className="tg-tr__title" href={r.source.url} target="_blank" rel="noopener noreferrer">{title}</a>
        : <b className="tg-tr__title is-plain">{title}</b>}
      {meta && <small className="tg-tr__meta">{tidyText(meta)}</small>}
      {(r.text || r.source) && <p>{tidyText(r.text)}{r.source && <> <SourceChip source={r.source} /></>}</p>}
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
        <h4>{numbered ? `${i + 1}. ` : ''}{s.heading}</h4>
        <ul>{s.rows.map((r, j) => <Row key={j} r={r} card={r.id ? cards.get(r.id) : undefined} />)}</ul>
        {places.length >= 2 && <PlaceStage row={{ ids: places.map(c => c.id), why: s.heading, cards: places }} busy={busy} onLike={onLike} />}
      </div>
    })}
    <small className="tg-tr__asof">Nhịp Đà Lạt · cập nhật {dm(block.as_of)}</small>
  </section>
}
