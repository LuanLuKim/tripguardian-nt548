import { useState, type CSSProperties } from 'react'
import { fmtClock, fmtVnd } from '../../lib'
import type { Ghost } from '../../planning/types'
import { PlacePhoto } from '../../ui/common'
import { Icon } from '../../ui/icons'
import { BLOCK, MEAL_LABEL } from './shared'

// One empty slot of a day (src/planning/ghosts.py): up to three real places that fit it, fanned out left to right like a hand of
// cards so every suggestion is in sight. A card is a small photo, the name and one line (detour, price). Pointing at a card brings it
// forward; tapping it opens the place; the round "+" on the card in front adds it to this day (add_from_backup). It is a
// suggestion, not a stop: nothing is on the timeline until the user adds it. The warning text (`note`) of the card in front is
// shown under the fan as sent.
export function GhostSlot({ slot, day, busy, onAdd, onOpen }: { slot: Ghost; day: number; busy: boolean; onAdd: (id: string) => void; onOpen: (id: string) => void }) {
  const [top, setTop] = useState(0)
  const n = slot.items.length
  const label = MEAL_LABEL[slot.kind] ?? BLOCK[slot.kind] ?? slot.kind
  const note = slot.items[top]?.note
  return (
    <section className="tg-ghost" aria-label={`Gợi ý cho ${label.toLowerCase()}, ${fmtClock(slot.start)} đến ${fmtClock(slot.end)}`}>
      <header>
        <Icon name="sparkle" size={14} />
        <b>Gợi ý · {label.replace(' (tự chọn)', '')}</b>
        <time className="tg-mono">{fmtClock(slot.start)}–{fmtClock(slot.end)}</time>
        <small>chưa có trong lịch</small>
      </header>
      <ul className={`tg-ghost__fan ${n === 1 ? 'is-one' : ''}`} style={{ '--n': n, '--cw': n === 1 ? '100%' : n === 2 ? '58%' : '46%' } as CSSProperties}>
        {slot.items.map((item, i) => {
          const chosen = i === top
          return (
            <li key={item.place_id} className={chosen ? 'is-front' : ''} style={{ '--i': i, '--d': Math.abs(i - top), '--side': Math.sign(i - top) } as CSSProperties} onMouseEnter={() => setTop(i)}>
              <span className="tg-ghost__bg" aria-hidden="true"><PlacePhoto id={item.place_id} name="" sizes="160px" /></span>
              <span className="tg-ghost__thumb">
                <PlacePhoto id={item.place_id} name="" sizes="240px" />
                <button type="button" className="tg-ghost__add" disabled={busy || !chosen} aria-label={`Thêm ${item.name}`} title={`Thêm vào ngày ${day}`} onClick={() => onAdd(item.place_id)}><Icon name="plus" size={16} /></button>
              </span>
              <button type="button" className="tg-ghost__open" aria-label={`Xem chi tiết ${item.name}`} onFocus={() => setTop(i)} onClick={() => (chosen ? onOpen(item.place_id) : setTop(i))} />
              <span className="tg-ghost__txt">
                <strong>{item.name}</strong>
                <small>≈ {item.detour_min} phút đi thêm · {item.price_vnd == null ? 'Chưa có giá' : item.price_vnd === 0 ? 'Miễn phí' : `≈ ${fmtVnd(item.price_vnd)}`}</small>
              </span>
            </li>
          )
        })}
      </ul>
      {note && <small className="tg-ghost__note">{note}</small>}
    </section>
  )
}
