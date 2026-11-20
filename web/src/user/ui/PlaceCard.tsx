import type { CSSProperties } from 'react'
import { fmtRange, info } from '../lib'
import { useDecision } from '../pd/decision'
import type { Card } from '../pd/types'
import { useWarm } from '../../data/store'
import { toggleSaved, useUi } from '../store'
import { CardTags, cardTags } from './CardTags'
import { PlacePhoto } from './common'
import { HeartFill, Icon } from './icons'
import { openPlace, warmSheet } from './PlaceSheet'

// One suggestion: why it fits, what it costs, how sure we are. Every main action works by click and keyboard;
// hover only reveals the secondary row earlier.
export function PlaceCard({ c, onDrop, cmp, onCmp, warn, phase = 'stay', order = 0 }: { c: Card; onDrop: (c: Card) => void; cmp: boolean; onCmp: (id: string) => void; warn?: string; phase?: 'stay' | 'enter' | 'leave'; order?: number }) {
  const { act, busy, view } = useDecision()
  useWarm([c.id]) // a card on screen: its evidence comes next, for when the sheet opens
  const p = info(c.id)
  const saved = useUi((u) => u.saved.includes(c.id))
  const flash = useUi((u) => u.flashId === c.id)
  const tags = cardTags(c, warn) // short lợi / hại tags; the whole sentences are in their tooltips and on the sheet
  return (
    <article className={`tg-pc tg-pc--lite ${c.chosen ? 'is-sel' : ''} ${c.locked ? 'is-lock' : ''} ${warn ? 'is-warn' : ''} ${c.status === 'unverified' ? 'is-dim' : ''} ${flash ? 'tg-flash' : ''} is-${phase}`} style={{ '--i': order } as CSSProperties} data-place={c.id} aria-hidden={phase === 'leave' || undefined}>
      <div className="tg-pc__media">
        <button type="button" className="tg-pc__open" onPointerEnter={() => warmSheet(c.id)} onFocus={() => warmSheet(c.id)} onClick={(e) => openPlace(c.id, e.currentTarget.querySelector('figure'))} aria-label={`Xem chi tiết ${c.name}`}>
          <PlacePhoto id={c.id} name={c.name} credit />
          <span className="tg-pc__shade" />
        </button>
        {c.top && <span className="tg-tag tg-pc__top" title="Một trong những nơi hợp chuyến của bạn nhất, đã chọn sao cho khác nhau">Hợp nhất</span>}
        <button type="button" className={`tg-pc__save ${saved ? 'is-on' : ''}`} onClick={() => toggleSaved(c.id, c.name)} aria-pressed={saved} aria-label={saved ? `Bỏ yêu thích ${c.name}` : `Yêu thích ${c.name}`} title="Lưu vào Yêu thích để xem lại sau; dùng Thêm vào chuyến để chọn nơi xếp lịch">{saved ? <HeartFill size={18} /> : <Icon name="heart" size={18} />}</button>
        {c.chosen && <span className="tg-pc__chk" aria-hidden="true"><Icon name="check" size={14} strokeWidth={2.4} /></span>}
        {(c.anchor || c.locked) && <span className="tg-pc__lock" title={c.anchor ? 'Bạn nói nhất định đến' : 'Đã khóa'}><Icon name="lock" size={14} /> {c.anchor ? 'Bắt buộc' : 'Đã khóa'}</span>}
      </div>
      <div className="tg-pc__body">
        <p className="tg-pc__meta tg-faint">
          <span className="tg-pc__area"><Icon name="pin" size={13} /><span className="tg-pc__t">{p?.area ?? c.area ?? 'Đà Lạt'}{c.suggested ? ' · gợi ý thêm' : ''}</span></span>
        </p>
        <h3 className="tg-pc__name" title={c.name}>{c.name}</h3>
        <p className="tg-pc__sub tg-faint">
          <span className="tg-pc__t" title={c.category ?? undefined}>{c.category ?? 'Địa điểm'}</span>
          {c.visit && <span className="tg-pc__t2" title="Ước tính"><Icon name="clock" size={13} />{fmtRange(c.visit.short, c.visit.long)}</span>}
          {p?.rating ? <span className="tg-pc__rate tg-mono" title="Điểm trên Google Maps"><Icon name="star" size={13} />{p.rating.toFixed(1)}</span> : null}
        </p>
        <CardTags tags={tags} />
          {c.chosen && view?.chunks && view.chunks.length > 1 && <label className="tg-week-choice tg-faint">Tuần ghé <select aria-label={`Tuần ghé ${c.name}`} value={view.chunk_assignments?.[c.id] ?? 0} disabled={busy} onChange={(e) => act({ type: 'move_chunk', place_id: c.id, chunk: Number(e.target.value) })}>{view.chunks.map((chunk) => <option key={chunk.id} value={chunk.id}>Tuần {chunk.id + 1} · {chunk.places.length} nơi</option>)}</select></label>}
        <div className="tg-pc__act">
          <div className="tg-pc__more" role="group" aria-label={`Thao tác với ${c.name}`}>
            <button type="button" className={`tg-pc__ic ${c.locked ? 'is-on' : ''}`} disabled={busy} onClick={() => act({ type: c.locked ? 'unlock' : 'lock', place_id: c.id })} aria-pressed={c.locked} title={c.locked ? 'Bỏ khóa' : 'Khóa: luôn giữ nơi này'} aria-label={c.locked ? 'Bỏ khóa' : 'Khóa'}><Icon name={c.locked ? 'lock' : 'unlock'} size={17} /></button>
            <button type="button" className={`tg-pc__ic ${cmp ? 'is-on' : ''}`} onClick={() => onCmp(c.id)} aria-pressed={cmp} title="So sánh với nơi khác" aria-label="So sánh"><Icon name="swap" size={17} /></button>
            {!c.chosen && <button type="button" className="tg-pc__ic" onClick={() => onDrop(c)} title="Bỏ nơi này" aria-label="Bỏ"><Icon name="x" size={17} /></button>}
          </div>
          {c.chosen ? (
            <button type="button" className="tg-btn tg-btn--sm tg-btn--soft" disabled={busy || c.anchor} onClick={() => onDrop(c)} title={c.anchor ? 'Nơi bạn nói nhất định đến' : 'Bấm để bỏ khỏi danh sách'} aria-pressed="true"><Icon name="check" size={16} /> Đã chọn</button>
          ) : (
            <button type="button" className="tg-btn tg-btn--sm tg-btn--primary" disabled={busy} onClick={() => act({ type: 'select', place_id: c.id })} aria-pressed="false" title="Đưa nơi này vào chuyến để xếp lịch"><Icon name="plus" size={16} /> Thêm</button>
          )}
        </div>
      </div>
    </article>
  )
}
