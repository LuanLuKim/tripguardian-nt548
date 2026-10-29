import { useRef, useState, type KeyboardEvent } from 'react'
import { useSnapshot } from '../../../data/store'
import { info } from '../../lib'
import type { ChatPlaces } from '../../tu/types'
import { CardImg } from '../../ui/common'
import { HeartFill, Icon } from '../../ui/icons'
import { openPlace } from '../../ui/PlaceSheet'
import { StageFrame, StageRing, stageKeys, useStage, type StageCard } from './Ask'

// The places the assistant found (src/trip/api/engine.py kind places), on the same photo stage as a photo question:
// the round button is Thích (a want, no model call), the front card opens the place sheet. A new reply opens the
// stage at once; a resumed chat keeps it folded into the line that opens it again.
export function PlaceStage({ row, busy, autoOpen, onLike }: {
  row: ChatPlaces; busy: boolean; autoOpen: boolean; onLike: (id: string, on: boolean) => void
}) {
  useSnapshot() // the photos and ratings come from the web's snapshot once it lands
  const { open, setOpen, leaving, close } = useStage(autoOpen)
  const [at, setAt] = useState(0)
  const panel = useRef<HTMLDivElement>(null)
  const places = row.cards
  const view = (i: number) => close(() => openPlace(places[i].id))
  const like = (i: number) => onLike(places[i].id, !places[i].liked)
  const keys = (e: KeyboardEvent<HTMLDivElement>) => stageKeys(e, panel, places.length, setAt, () => close(),
    key => (key === 'Enter' ? view(at) : like(at)))
  const cards: StageCard[] = places.map(c => {
    const p = info(c.id)
    const name = c.name ?? p?.name ?? 'Nơi này'
    const rating = c.rating ?? p?.rating ?? null
    const kind = [c.category ?? p?.category, rating ? `★ ${rating.toFixed(1)}` : null].filter(Boolean).join(' · ')
    return { id: c.id, photo: c.photos[0] ?? p?.photos[0]?.src ?? null, alt: name, title: name, on: c.liked,
      line: <>
        <small><Icon name="pin" size={13} />{kind || 'Nơi thật'}</small>
        <small>{c.hours_today ? `Hôm nay ${c.hours_today}` : 'Chưa có giờ mở'}</small>
      </>,
      pick: c.liked ? <HeartFill size={18} /> : <Icon name="heart" size={18} strokeWidth={2.2} />,
      pickLabel: c.liked ? `Bỏ thích ${name}` : `Thích ${name}` }
  })
  if (!places.length) return null
  const title = row.why || `${places.length} nơi từ dữ liệu`
  return <>
    <button type="button" className="tg-stage__reopen" disabled={busy} onClick={() => setOpen(true)}>
      <span className="tg-stage__thumbs" aria-hidden="true">{cards.slice(0, 3).map(c => c.photo ? <CardImg key={c.id} src={c.photo} alt="" /> : <i key={c.id} />)}</span>
      <span><b>{title}</b><small>{places.length} nơi thật từ dữ liệu · bấm để xem</small></span>
      <Icon name="chevronRight" size={18} />
    </button>
    {open && <StageFrame leaving={leaving} kicker="Gợi ý từ dữ liệu" question={title} onClose={() => close()} onKeyDown={keys} panel={panel}>
      <StageRing cards={cards} at={at} setAt={setAt} busy={busy} label="Các nơi gợi ý" prevLabel="Nơi trước" nextLabel="Nơi sau"
        hint="Lăn chuột hoặc dùng ← → để xoay · bấm thẻ giữa để xem" onFront={view} onPick={like} />
      <footer className="tg-stage__foot">
        <p className="tg-stage__note">Bấm tim để lưu nơi bạn thích, mình ưu tiên chúng khi chọn nơi.</p>
        <button type="button" className="tg-btn tg-btn--primary" onClick={() => close()}>Xong <Icon name="check" size={16} /></button>
      </footer>
    </StageFrame>}
  </>
}
