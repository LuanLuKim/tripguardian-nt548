import * as Dialog from '@radix-ui/react-dialog'
import * as Popover from '@radix-ui/react-popover'
import { useEffect, useMemo, useRef, useState } from 'react'
import { tripTitle } from '../../home/dialogs'
import { deleteTrip, tripSummaries } from '../../pd/api'
import type { TripSummary } from '../../pd/types'
import { Icon } from '../../ui/icons'

// Name chats after their first message; older journeys fall back to their place and days. Metadata stays in the tooltip.
// A trip that went on to Lựa chọn without a typed word is a trip, not a new chat: it is named after the city and its picks.
const chatName = (t: TripSummary) => t.title || (t.days ? tripTitle(t)
  : t.stage !== 'trip' ? `${tripTitle(t)}${t.places.length ? ` · ${t.places.length} nơi` : ''}` : 'Cuộc trò chuyện mới')

const STAGE: Record<TripSummary['stage'], string> = { trip: 'Tìm hiểu', decision: 'Lựa chọn', planning: 'Lịch trình' }
const chatMeta = (t: TripSummary) => [t.days ? `${t.days} ngày` : null, t.people ? `${t.people} người` : null, t.places.length ? `${t.places.length} nơi` : null, t.confirmed ? 'Đã chốt' : STAGE[t.stage]].filter(Boolean).join(' · ')

// A chat nobody has typed in yet holds nothing to come back to: it stays out of the list unless it is the one open now.
const isBlank = (t: TripSummary) => !t.title && !t.days && !t.places.length && t.stage === 'trip'

// Pinned chats stay at the top of the list. They are remembered in this browser only (no account setting behind them yet).
const PINS = 'tg.history.pins'
const readPins = (): string[] => { try { const v = JSON.parse(localStorage.getItem(PINS) ?? '[]'); return Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string') : [] } catch { return [] } }
const writePins = (ids: string[]) => { try { localStorage.setItem(PINS, JSON.stringify(ids)) } catch { /* the pin lasts until the page closes */ } }

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
  const [searching, setSearching] = useState(false)
  const searchButton = useRef<HTMLButtonElement>(null)
  const closeSearch = () => { setQuery(''); setSearching(false); requestAnimationFrame(() => searchButton.current?.focus()) }
  const [retry, setRetry] = useState(0)
  const [pins, setPins] = useState(readPins)
  const [menu, setMenu] = useState<string | null>(null)
  const [removing, setRemoving] = useState<TripSummary | null>(null)
  const [removeError, setRemoveError] = useState(false)
  const [removeBusy, setRemoveBusy] = useState(false)
  const togglePin = (id: string) => { const next = pins.includes(id) ? pins.filter(x => x !== id) : [id, ...pins]; setPins(next); writePins(next); setMenu(null) }
  const remove = async (t: TripSummary) => {
    setRemoveBusy(true); setRemoveError(false)
    try {
      await deleteTrip(t.id)
      setList(old => old?.filter(x => x.id !== t.id) ?? old)
      if (pins.includes(t.id)) { const next = pins.filter(x => x !== t.id); setPins(next); writePins(next) }
      setRemoving(null)
      if (t.id === active) onNew()
    } catch { setRemoveError(true) }
    finally { setRemoveBusy(false) }
  }
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
  const pinned = pins.map(id => shown.find(t => t.id === id)).filter((t): t is TripSummary => !!t)
  const unpinned = shown.filter(t => !pins.includes(t.id))
  const groups = [...(pinned.length ? [{ key: 'pinned', label: 'Đã ghim', items: pinned }] : []), ...(timed
    ? GROUPS.map(g => ({ key: g.key, label: g.label, items: unpinned.filter(t => { const age = ageInDays(t.updated_at, now); return age !== null && g.has(age) }) })).filter(g => g.items.length)
    : unpinned.length ? [{ key: 'all', label: 'Chuyến của bạn', items: unpinned }] : [])]
  const open = (t: TripSummary) => { setQuery(''); onOpen(t) }
  return (
    <aside className="tg-history" aria-label="Lịch sử chat">
      <header className="tg-history__head">
        <h2 className="tg-sr">Lịch sử chat</h2>
        <button type="button" className="tg-history__new" disabled={busy} onClick={onNew}><Icon name="plus" size={18} />Cuộc trò chuyện mới</button>
      </header>
      {searching ? <label className="tg-history__search">
        <Icon name="search" size={17} />
        <input autoFocus value={query} onChange={e => setQuery(e.target.value)} onKeyDown={e => { if (e.key === 'Escape') closeSearch() }} placeholder="Tìm trong lịch sử" aria-label="Tìm trong lịch sử" />
        {query && <button type="button" className="tg-history__clear" aria-label="Xóa ô tìm" onClick={() => setQuery('')}><Icon name="x" size={14} /></button>}
      </label> : <button ref={searchButton} type="button" className="tg-history__new" onClick={() => setSearching(true)}><Icon name="search" size={17} />Tìm kiếm</button>}
      <div className="tg-history__list">
        {error ? <div className="tg-history__empty" role="status"><Icon name="warn" size={20} /><p>Chưa tải được lịch sử.</p><button type="button" className="tg-link" onClick={() => setRetry(n => n + 1)}>Thử lại</button></div>
          : !list ? <div className="tg-history__skeleton" role="status" aria-label="Đang tải lịch sử">{[0, 1, 2, 3, 4].map(i => <span key={i} aria-hidden="true"><i /></span>)}</div>
          : shown.length === 0 ? (q
            ? <div className="tg-history__empty" role="status"><Icon name="search" size={20} /><p>Không có chuyến nào khớp “{query.trim()}”.</p><button type="button" className="tg-link" onClick={() => setQuery('')}>Xóa ô tìm</button></div>
            : <div className="tg-history__empty"><Icon name="compass" size={20} /><p>Những chuyến bạn bắt đầu sẽ nằm ở đây.</p></div>)
          : groups.map(g => (
            <section key={g.key} className="tg-history__group" aria-label={g.label}>
              <h3 className="tg-history__label">{g.label}</h3>
              {g.items.map(t => {
                const name = chatName(t), on = pins.includes(t.id)
                return (
                  <div key={t.id} className={`tg-history__row ${menu === t.id ? 'is-menu' : ''}`}>
                    <button type="button" className={`tg-history__entry ${t.id === active ? 'is-active' : ''}`} aria-current={t.id === active ? 'true' : undefined} title={`${name}\n${chatMeta(t)}`} disabled={busy} onClick={() => open(t)}>
                      {on && <Icon name="thumbtack" size={13} aria-hidden="true" />}
                      <strong>{name}</strong>
                      {t.confirmed && <small>Đã chốt</small>}
                    </button>
                    <Popover.Root open={menu === t.id} onOpenChange={o => setMenu(o ? t.id : null)}>
                      <Popover.Trigger className="tg-history__more" aria-label={`Tùy chọn: ${name}`} disabled={busy}><Icon name="dots" size={18} /></Popover.Trigger>
                      <Popover.Portal>
                        <Popover.Content className="tg tg-history__menu" side="bottom" align="start" sideOffset={4} collisionPadding={12}>
                          <button type="button" onClick={() => togglePin(t.id)}><Icon name="thumbtack" size={16} />{on ? 'Bỏ ghim' : 'Ghim'}</button>
                          <button type="button" className="is-danger" onClick={() => { setMenu(null); setRemoveError(false); setRemoving(t) }}><Icon name="trash" size={16} />Xóa</button>
                        </Popover.Content>
                      </Popover.Portal>
                    </Popover.Root>
                  </div>
                )
              })}
            </section>
          ))}
      </div>
      <Dialog.Root open={!!removing} onOpenChange={o => { if (!o && !removeBusy) setRemoving(null) }}>
        <Dialog.Portal>
          <Dialog.Overlay className="tg-history__veil" />
          <Dialog.Content className="tg tg-history__confirm">
            <Dialog.Title>Xóa cuộc trò chuyện này?</Dialog.Title>
            <Dialog.Description>“{removing ? chatName(removing) : ''}” sẽ biến mất khỏi danh sách của bạn và không mở lại được.</Dialog.Description>
            {removeError && <p role="alert" className="tg-history__err">Chưa xóa được. Bạn thử lại nhé.</p>}
            <div>
              <button type="button" disabled={removeBusy} onClick={() => setRemoving(null)}>Hủy</button>
              <button type="button" className="is-danger" disabled={removeBusy} onClick={() => removing && remove(removing)}>{removeBusy ? 'Đang xóa…' : 'Xóa'}</button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
      <footer className="tg-history__foot"><Icon name="lock" size={14} /><span>Mỗi chuyến đi, một câu chuyện riêng.</span></footer>
    </aside>
  )
}
