import { useEffect, useMemo, useState } from 'react'
import { tripTitle } from '../../home/dialogs'
import { tripSummaries } from '../../pd/api'
import type { TripSummary } from '../../pd/types'
import { Icon } from '../../ui/icons'

// A chat is one line, named after its first message (like ChatGPT) and cut with "…" when it does not fit (the full text is the tooltip); a trip with no words yet, or one listed by an older harness, falls back to its place and days.
const chatName = (t: TripSummary) => t.title || (t.days ? tripTitle(t) : 'Cuộc trò chuyện mới')

// A chat nobody has typed in yet holds nothing to come back to: it stays out of the list unless it is the one open now.
const isBlank = (t: TripSummary) => !t.title && !t.days && !t.places.length && t.stage === 'trip'

const DAY = 86_400_000
const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()

// Whole calendar days between the chat's last save and now; null when the harness did not send a time (older build).
function ageInDays(iso: string | null | undefined, now: Date) {
  const at = iso ? new Date(iso) : null
  if (!at || Number.isNaN(at.getTime())) return null
  return Math.max(0, Math.round((startOfDay(now) - startOfDay(at)) / DAY))
}

const GROUPS = [
  { key: 'today', label: 'Hôm nay', has: (age: number) => age === 0 },
  { key: 'week', label: '7 ngày qua', has: (age: number) => age > 0 && age < 7 },
  { key: 'older', label: 'Cũ hơn', has: (age: number) => age >= 7 },
] as const

export function History({ active, busy, onNew, onOpen }: { active: string | null; busy: boolean; onNew: () => void; onOpen: (trip: TripSummary) => void }) {
  const [list, setList] = useState<TripSummary[] | null>(null)
  const [error, setError] = useState(false)
  const [query, setQuery] = useState('')
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    if (busy) return
    let alive = true
    setError(false)
    tripSummaries().then(items => { if (alive) setList(items) }).catch(() => { if (alive) setError(true) })
    return () => { alive = false }
  }, [active, busy, retry])
  const q = query.trim().toLocaleLowerCase('vi-VN')
  const now = useMemo(() => new Date(), [list])
  const shown = list?.filter(t => (t.id === active || !isBlank(t)) && chatName(t).toLocaleLowerCase('vi-VN').includes(q)) ?? []
  // Time groups when the harness sent times; one plain group otherwise. The list keeps the harness order (newest first).
  const timed = shown.some(t => ageInDays(t.updated_at, now) !== null)
  const groups = timed
    ? GROUPS.map(g => ({ key: g.key, label: g.label, items: shown.filter(t => { const age = ageInDays(t.updated_at, now); return age !== null && g.has(age) }) })).filter(g => g.items.length)
    : [{ key: 'all', label: 'Chuyến của bạn', items: shown }]
  const open = (t: TripSummary) => { setQuery(''); onOpen(t) }
  return (
    <aside className="tg-history" aria-label="Lịch sử chat">
      <header className="tg-history__head">
        <h2>Lịch sử chat</h2>
        <button type="button" className="tg-history__new" aria-label="Tạo chuyến đi mới" title="Tạo chuyến đi mới" disabled={busy} onClick={onNew}><Icon name="plus" size={23} /></button>
      </header>
      <label className="tg-history__search">
        <Icon name="search" size={17} />
        <input value={query} onChange={e => setQuery(e.target.value)} onKeyDown={e => { if (e.key === 'Escape') setQuery('') }} placeholder="Tìm trong lịch sử" aria-label="Tìm trong lịch sử" />
        {query && <button type="button" className="tg-history__clear" aria-label="Xóa ô tìm" onClick={() => setQuery('')}><Icon name="x" size={14} /></button>}
      </label>
      <div className="tg-history__list">
        {error ? <div className="tg-history__empty" role="status"><Icon name="warn" size={20} /><p>Chưa tải được lịch sử.</p><button type="button" className="tg-link" onClick={() => setRetry(n => n + 1)}>Thử lại</button></div>
          : !list ? <div className="tg-history__skeleton" role="status" aria-label="Đang tải lịch sử">{[0, 1, 2, 3, 4].map(i => <span key={i} aria-hidden="true"><i /><i /></span>)}</div>
          : shown.length === 0 ? (q
            ? <div className="tg-history__empty" role="status"><Icon name="search" size={20} /><p>Không có chuyến nào khớp “{query.trim()}”.</p><button type="button" className="tg-link" onClick={() => setQuery('')}>Xóa ô tìm</button></div>
            : <div className="tg-history__empty"><Icon name="compass" size={20} /><p>Những chuyến bạn bắt đầu sẽ nằm ở đây.</p></div>)
          : groups.map(g => (
            <section key={g.key} className="tg-history__group" aria-label={g.label}>
              <h3 className="tg-history__label">{g.label}</h3>
              {g.items.map(t => {
                return (
                  <button key={t.id} type="button" className={`tg-history__entry ${t.id === active ? 'is-active' : ''}`} aria-current={t.id === active ? 'true' : undefined} title={chatName(t)} disabled={busy} onClick={() => open(t)}>
                    <strong>{chatName(t)}</strong>
                  </button>
                )
              })}
            </section>
          ))}
      </div>
      <footer className="tg-history__foot"><Icon name="lock" size={14} /><span>Mỗi chuyến đi, một câu chuyện riêng.</span></footer>
    </aside>
  )
}
