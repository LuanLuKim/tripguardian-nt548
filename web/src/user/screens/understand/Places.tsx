import { useRef, useState, type KeyboardEvent } from 'react'
import { useSnapshot } from '../../../data/store'
import { info } from '../../lib'
import type { ChatPlace, ChatPlaces } from '../../tu/types'
import { CardImg } from '../../ui/common'
import { HeartFill, Icon } from '../../ui/icons'
import { openPlace } from '../../ui/PlaceSheet'
import { StageFrame, StageRing, stageKeys, useStage, type StageCard } from './Ask'

// One place on the photo stage: the front card opens the place sheet, the round button is Thích (a want, no model call).
export function placeCard(c: ChatPlace, on: boolean): StageCard {
  const p = info(c.id)
  const name = c.name ?? p?.name ?? 'Nơi này'
  const rating = c.rating ?? p?.rating ?? null
  const kind = [c.category ?? p?.category, rating ? `★ ${rating.toFixed(1)}` : null].filter(Boolean).join(' · ')
  return { id: c.id, photo: c.photos[0] ?? p?.photos[0]?.src ?? null, alt: name, title: name, on,
    line: <>
      <small><Icon name="pin" size={13} />{kind || 'Nơi thật'}</small>
      <small>{c.hours_today ? `Hôm nay ${c.hours_today}` : 'Chưa có giờ mở'}</small>
    </>,
    pick: on ? <HeartFill size={18} /> : <Icon name="heart" size={18} strokeWidth={2.2} />,
    pickLabel: on ? `Bỏ thích ${name}` : `Thích ${name}` }
}

// What the list is about, in words the user can read at a glance: the line the assistant wrote for it, else the kind of
// place the cards share ("Quán cà phê"), else a plain line. Never a count or a mention of where the data came from.
export function placesTitle(row: ChatPlaces): string {
  const said = row.why.trim()
  if (said) return said
  const count = new Map<string, number>()
  for (const c of row.cards) {
    const kind = (c.category ?? info(c.id)?.category ?? '').trim()
    if (kind) count.set(kind, (count.get(kind) ?? 0) + 1)
  }
  const kinds = [...count].sort((a, b) => b[1] - a[1])
  const share = (n: number) => kinds.slice(0, n).reduce((t, [, k]) => t + k, 0) / row.cards.length
  if (kinds.length && share(1) >= 0.6) return `${kinds[0][0]} hợp với chuyến này`
  if (kinds.length > 1 && share(2) >= 0.8) return `${kinds[0][0]} và ${kinds[1][0].toLowerCase()} hợp với chuyến này`
  return 'Nơi hợp với chuyến này'
}

// The places the assistant found (src/trip/api/engine.py kind places), on the same photo stage as a photo question:
// the round button is Thích (a want, no model call), the front card opens the place sheet. The stage never opens by
// itself: the chat shows one line with the first photos and the user taps it (autoOpen is for the decision assistant).
export function PlaceStage({ row, busy, autoOpen = false, onLike }: {
  row: ChatPlaces; busy: boolean; autoOpen?: boolean; onLike: (id: string, on: boolean) => void
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
  const cards: StageCard[] = places.map(c => placeCard(c, c.liked))
  if (!places.length) return null
  const title = placesTitle(row)
  const names = cards.slice(0, 2).map(c => c.title).join(', ')
  return <>
    <button type="button" className="tg-stage__reopen" disabled={busy} onClick={() => setOpen(true)}>
      <span className="tg-stage__thumbs" aria-hidden="true">{cards.slice(0, 3).map(c => c.photo ? <CardImg key={c.id} src={c.photo} alt="" /> : <i key={c.id} />)}</span>
      <span><b>{title}</b><small>{places.length} nơi · {names}{places.length > 2 ? '…' : ''}</small></span>
      <Icon name="chevronRight" size={18} />
    </button>
    {open && <StageFrame leaving={leaving} kicker={`${places.length} nơi`} question={title} onClose={() => close()} onKeyDown={keys} panel={panel}>
      <StageRing cards={cards} at={at} setAt={setAt} busy={busy} label="Các nơi gợi ý" prevLabel="Nơi trước" nextLabel="Nơi sau"
        hint="Lăn chuột hoặc dùng ← → để xoay · bấm thẻ giữa để xem" onFront={view} onPick={like} />
      <footer className="tg-stage__foot">
        <p className="tg-stage__note">Bấm tim để lưu nơi bạn thích, mình ưu tiên chúng khi chọn nơi.</p>
        <button type="button" className="tg-btn tg-btn--primary" onClick={() => close()}>Xong <Icon name="check" size={16} /></button>
      </footer>
    </StageFrame>}
  </>
}
