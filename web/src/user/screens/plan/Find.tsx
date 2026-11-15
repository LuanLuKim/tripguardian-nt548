import { useEffect, useMemo, useRef, useState } from 'react'
import { info, priceText } from '../../lib'
import type { ItineraryDay } from '../../planning/types'
import { allPlaceIds } from '../../../data/store'
import { useUi } from '../../store'
import { PlacePhoto } from '../../ui/common'
import { Icon } from '../../ui/icons'
import type { Candidate } from './candidates'
import { norm, shortDate } from './shared'

// "Thêm trải nghiệm" / "Đổi" on a day (mẫu docs/design/mock/designs/itinerary, màn tìm nơi): search on top, filters on the
// left, places on the right. It opens in the map's half of the day screen, so the day being edited stays in sight on the left.
// "Thêm" / "Chọn thay thế" only asks for a preview of the change (Plan.tsx); the day is not touched until it is applied.
// The server swaps and adds only a place of the selection or of the checked backup pool; a saved place outside both is chosen
// in Lựa chọn first and the plan is built again (`onAddOutside`).

type Row = { c: Candidate; outside: boolean }
type Source = 'suggest' | 'saved' | 'all'
const STAY = /(khách sạn|homestay|hostel|resort|villa|nhà nghỉ|căn hộ|lưu trú|biệt thự)/i // where to sleep is picked apart
const SHOWN = 40 // rows drawn at once under "Tất cả"; typing or a kind narrows the rest

export function Find({ day, replacing, candidates, inPlan, people, busy, onClose, onPick, onAddOutside, onOpen }: {
  day: ItineraryDay; replacing: string | null; candidates: Candidate[]; inPlan: Set<string>; people: number | null; busy: boolean
  onClose: () => void; onPick: (c: Candidate) => void; onAddOutside: (id: string) => void; onOpen: (id: string) => void
}) {
  const saved = useUi((u) => u.saved)
  const [q, setQ] = useState('')
  const [source, setSource] = useState<Source>('suggest')
  const [more, setMore] = useState(1)
  const [cat, setCat] = useState('all')
  const box = useRef<HTMLInputElement>(null)
  useEffect(() => { box.current?.focus({ preventScroll: true }) }, [day.day, replacing])
  useEffect(() => {
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', esc)
    return () => window.removeEventListener('keydown', esc)
  }, [onClose])
  const savedRows = useMemo<Row[]>(() => saved.filter((id) => !inPlan.has(id) && info(id)).map((id) => {
    const c = candidates.find((x) => x.id === id)
    return c ? { c, outside: false } : { c: { id, name: info(id)!.name, from: 'selection', why: null, forThis: false }, outside: true }
  }), [saved, inPlan, candidates])
  // Tất cả: what the plan can take straight away, then saved places, then every other place of Đà Lạt in the catalog (best rated
  // first). A place outside the selection is chosen in Lựa chọn and the plan is built again, like a saved one.
  const allRows = useMemo<Row[]>(() => {
    if (source !== 'all') return []
    const seen = new Set<string>([...inPlan, ...candidates.map((c) => c.id), ...savedRows.map((r) => r.c.id)])
    const rest = allPlaceIds().filter((id) => !seen.has(id)).map((id) => info(id)).filter((p): p is NonNullable<typeof p> => !!p && !STAY.test(p.category ?? ''))
      .sort((a, b) => (b.rating ?? 0) - (a.rating ?? 0))
      .map((p): Row => ({ c: { id: p.id, name: p.name, from: 'selection', why: null, forThis: false }, outside: true }))
    return [...candidates.map((c) => ({ c, outside: false })), ...savedRows.filter((r) => !candidates.some((c) => c.id === r.c.id)), ...rest]
  }, [source, inPlan, candidates, savedRows])
  const rows: Row[] = source === 'saved' ? savedRows : source === 'all' ? allRows : candidates.map((c) => ({ c, outside: false }))
  const cats = useMemo(() => {
    const n = new Map<string, number>()
    for (const { c } of rows) { const k = info(c.id)?.category; if (k) n.set(k, (n.get(k) ?? 0) + 1) }
    return [...n.entries()].sort((a, b) => b[1] - a[1])
  }, [rows])
  const matches = rows.filter(({ c }) => (cat === 'all' || info(c.id)?.category === cat) && (!q || norm(`${c.name} ${info(c.id)?.category ?? ''} ${info(c.id)?.area ?? ''}`).includes(norm(q))))
  const hits = matches.slice(0, SHOWN * more)
  const target = replacing ? info(replacing)?.name ?? replacing : null
  const empty = source === 'saved'
    ? 'Bạn chưa lưu nơi nào ngoài lịch này. Bấm hình trái tim ở một nơi để lưu.'
    : candidates.length ? 'Không có nơi phù hợp với bộ lọc này. Thử đổi loại trải nghiệm hoặc từ khóa.' : 'Chưa còn nơi nào để thêm. Bạn chọn thêm nơi ở bước Lựa chọn.'
  return (
    <section className="tg-it-find is-pane" aria-labelledby="tg-it-find-h">
      <header className="tg-it-find__head">
        <div>
          <p>{replacing ? 'Đổi trải nghiệm' : 'Thêm trải nghiệm'}</p>
          <h2 id="tg-it-find-h">{target ? <>Thay <em>{target}</em></> : <>Thêm vào ngày {day.day}</>}</h2>
        </div>
        <button type="button" className="tg-icon-btn" aria-label="Đóng, về bản đồ" onClick={onClose}><Icon name="x" size={20} /></button>
      </header>
      <form className="tg-it-search" role="search" onSubmit={(e) => e.preventDefault()}>
        <Icon name="search" size={19} />
        <input ref={box} type="search" aria-label="Tìm trải nghiệm ở Đà Lạt" placeholder="Tìm trải nghiệm ở Đà Lạt" value={q} onChange={(e) => { setQ(e.target.value); setMore(1) }} />
        {q && <button type="button" className="tg-it-search__x" aria-label="Xóa ô tìm" onClick={() => setQ('')}><Icon name="x" size={16} /></button>}
      </form>
      <div className="tg-it-find__ctx">
        <span>{target ? <>Thay trong <strong>ngày {day.day} · {shortDate(day.date, day.day)}</strong></> : <>Thêm vào <strong>ngày {day.day} · {shortDate(day.date, day.day)}</strong></>}</span>
        <span>{matches.length} nơi</span>
      </div>
      <div className="tg-it-find__cols">
        <aside className="tg-it-filters">
          <div className="tg-it-fcard">
            <div className="tg-it-frow"><Icon name="pin" size={18} /><div><small>Điểm đến</small><b>Đà Lạt, Việt Nam</b></div></div>
            <div className="tg-it-frow"><Icon name="calendar" size={18} /><div><small>Ngày ghé</small><b>{shortDate(day.date, day.day)}</b></div></div>
            <div className="tg-it-frow"><Icon name="user" size={18} /><div><small>Đi cùng</small><b>{people ? `${people} người` : 'Chưa rõ số người'}</b></div></div>
          </div>
          <div className="tg-it-fcard" role="radiogroup" aria-label="Nguồn">
            <h3>Nguồn</h3>
            {([['all', 'Tất cả', null], ['suggest', 'Gợi ý', candidates.length], ['saved', 'Đã lưu', savedRows.length]] as const).map(([k, label, n]) => (
              <label key={k}><input type="radio" name="tg-it-src" checked={source === k} onChange={() => { setSource(k); setCat('all'); setMore(1) }} />{label}<small>{k === 'all' ? (source === 'all' ? rows.length : 'cả Đà Lạt') : n}</small></label>
            ))}
          </div>
          {cats.length > 1 && <div className={`tg-it-fcard ${cats.length > 10 ? 'is-long' : ''}`} role="radiogroup" aria-label="Loại trải nghiệm">
            <h3>Loại trải nghiệm</h3>
            {[['all', 'Tất cả', rows.length] as const, ...cats.map(([k, n]) => [k, k, n] as const)].map(([k, label, n]) => (
              <label key={k}><input type="radio" name="tg-it-cat" checked={cat === k} onChange={() => { setCat(k); setMore(1) }} />{label}<small>{n}</small></label>
            ))}
          </div>}
          <p className="tg-it-small">Gợi ý là nơi bạn đã chọn hoặc dự phòng đã kiểm tra. Nơi khác (đã lưu hoặc trong Tất cả) sẽ được chọn rồi lịch xếp lại.</p>
        </aside>
        <div className="tg-it-results" aria-live="polite">
          {hits.map(({ c, outside }, i) => {
            const p = info(c.id)
            const price = priceText(p?.price)
            return (
              <article key={c.id} className="tg-it-result" style={{ ['--i' as string]: i }}>
                <button type="button" className="tg-it-result__ph" aria-label={`Xem chi tiết ${c.name}`} onClick={() => onOpen(c.id)}><PlacePhoto id={c.id} name={c.name} sizes="200px" /></button>
                <div className="tg-it-result__copy">
                  <h3>{c.name}</h3>
                  <p>{[p?.category, p?.area].filter(Boolean).join(' · ')}</p>
                  <div className="tg-it-rate">{p?.rating != null && <><Icon name="star" size={15} /><b>{p.rating.toFixed(1)}</b>{p.reviews != null && <span>({p.reviews.toLocaleString('vi-VN')} đánh giá)</span>}</>}</div>
                  <div className="tg-it-result__meta">
                    {c.forThis && <b className="tg-tag">Hợp để thay {target}</b>}{' '}
                    {outside ? 'Chưa nằm trong lựa chọn: thêm sẽ chọn nơi này và xếp lại lịch.' : c.why ?? (c.from === 'selection' ? 'Nơi bạn đã chọn, đang chưa có trong lịch' : 'Dự phòng đã kiểm tra')}
                  </div>
                  {c.warnings?.map((w, j) => <p key={j} className="tg-it-result__warn"><Icon name="warn" size={13} />{w.text}</p>)}
                  <div className="tg-it-result__act">
                    <span className="tg-faint">{price ? `Giá tham khảo ${price}` : 'Chưa có giá xác nhận'}</span>
                    <button type="button" className="tg-btn tg-btn--primary tg-btn--sm" disabled={busy} aria-label={`${replacing && !outside ? 'Chọn thay thế' : 'Thêm vào lịch'}: ${c.name}`} onClick={() => (outside ? onAddOutside(c.id) : onPick(c))}>
                      <Icon name={replacing && !outside ? 'swap' : 'plus'} size={15} />{replacing && !outside ? 'Chọn thay thế' : 'Thêm vào lịch'}
                    </button>
                  </div>
                </div>
              </article>
            )
          })}
          {matches.length > hits.length && <button type="button" className="tg-btn tg-btn--soft tg-it-find__more" onClick={() => setMore((m) => m + 1)}>Xem thêm {Math.min(SHOWN, matches.length - hits.length)} nơi · còn {matches.length - hits.length}</button>}
          {!hits.length && <div className="tg-it-empty">{empty}</div>}
        </div>
      </div>
    </section>
  )
}
