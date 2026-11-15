import * as Dialog from '@radix-ui/react-dialog'
import * as Popover from '@radix-ui/react-popover'
import { useEffect, useMemo, useState } from 'react'
import { tripTitle } from '../../home/dialogs'
import { deleteTrip, tripSummaries } from '../../pd/api'
import type { TripSummary } from '../../pd/types'
import { Icon } from '../../ui/icons'

// Name chats after their first message; older journeys fall back to their place and days. Metadata stays in the tooltip.
// A trip that went on to Lựa chọn without a typed word is a trip, not a new chat: it is named after the city and its picks.
// A chat that kept places (stepped back to the chat from Lựa chọn) is not a new chat: it never carries that name.
const chatName = (t: TripSummary) => t.title || (t.days ? tripTitle(t)
  : t.stage !== 'trip' || t.places.length ? `${tripTitle(t)}${t.places.length ? ` · ${t.places.length} nơi` : ''}` : 'Cuộc trò chuyện mới')

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

export function History({ active, busy, collapsed, onToggle, onNew, onOpen }: { active: string | null; busy: boolean; collapsed: boolean; onToggle: () => void; onNew: () => void; onOpen: (trip: TripSummary) => void }) {
  const [list, setList] = useState<TripSummary[] | null>(null)
  const [error, setError] = useState(false)
  const [query, setQuery] = useState('')
  const [searching, setSearching] = useState(false)
  const closeSearch = () => { setQuery(''); setSearching(false) }
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
  const kept = list?.filter(t => t.id === active || !isBlank(t)) ?? []
  const shown = kept
  const found = q ? kept.filter(t => chatName(t).toLocaleLowerCase('vi-VN').includes(q)) : kept
  // Time groups when the harness sent times; one plain group otherwise. The list keeps the harness order (newest first).
  const timed = shown.some(t => ageInDays(t.updated_at, now) !== null)
  const pinned = pins.map(id => shown.find(t => t.id === id)).filter((t): t is TripSummary => !!t)
  const unpinned = shown.filter(t => !pins.includes(t.id))
  const groups = [...(pinned.length ? [{ key: 'pinned', label: 'Đã ghim', items: pinned }] : []), ...(timed
    ? GROUPS.map(g => ({ key: g.key, label: g.label, items: unpinned.filter(t => { const age = ageInDays(t.updated_at, now); return age !== null && g.has(age) }) })).filter(g => g.items.length)
    : unpinned.length ? [{ key: 'all', label: 'Chuyến của bạn', items: unpinned }] : [])]
  const open = (t: TripSummary) => { closeSearch(); onOpen(t) }
  // Search is a centred palette over the page (like the assistant apps): new chat first, then recent chats, filtered as you type.
  const palette = (
    <Dialog.Root open={searching} onOpenChange={o => { if (!o) closeSearch() }}>
      <Dialog.Portal>
        <Dialog.Overlay className="tg-history__veil" />
        <Dialog.Content className="tg tg-find" aria-describedby={undefined}>
          <Dialog.Title className="tg-sr">Tìm trong lịch sử</Dialog.Title>
          <div className="tg-find__top">
            <input autoFocus value={query} onChange={e => setQuery(e.target.value)} placeholder="Tìm kiếm…" aria-label="Tìm trong lịch sử" />
            <Dialog.Close className="tg-find__x" aria-label="Đóng"><Icon name="x" size={20} /></Dialog.Close>
          </div>
          <div className="tg-find__list">
            {!q && <button type="button" className="tg-find__row" disabled={busy} onClick={() => { closeSearch(); onNew() }}><Icon name="edit" size={20} /><span>Cuộc trò chuyện mới</span></button>}
            <h3 className="tg-find__label">{q ? 'Kết quả' : 'Trò chuyện gần đây'}</h3>
            {!list && !error ? <p className="tg-find__none">Đang tải…</p>
              : error ? <p className="tg-find__none">Chưa tải được lịch sử.</p>
              : found.length === 0 ? <p className="tg-find__none">{q ? `Không có chuyến nào khớp “${query.trim()}”.` : 'Những chuyến bạn bắt đầu sẽ nằm ở đây.'}</p>
              : found.map(t => <div key={t.id} className={`tg-find__item ${t.id === active ? 'is-active' : ''}`}>
                <button type="button" className="tg-find__row" disabled={busy} onClick={() => open(t)}><Icon name="chat" size={20} /><span>{chatName(t)}</span>{t.confirmed && <small>Đã chốt</small>}</button>
                <button type="button" className="tg-find__del" aria-label={`Xóa cuộc trò chuyện: ${chatName(t)}`} title="Xóa cuộc trò chuyện" disabled={busy} onClick={() => { setRemoveError(false); setRemoving(t) }}><Icon name="x" size={18} /></button>
              </div>)}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
  // One confirmation for both ways to delete (the row's menu and the search palette's cross), in the folded strip too.
  const confirm = (
    <Dialog.Root open={!!removing} onOpenChange={o => { if (!o && !removeBusy) setRemoving(null) }}>
      <Dialog.Portal>
        <Dialog.Overlay className="tg-history__veil is-top" />
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
  )

  // Folded: the column is gone; three small icons float at the top-left of the chat (open, new chat, search).
  if (collapsed) return (
    <>
      <div className="tg-history__float" role="toolbar" aria-label="Lịch sử chat">
        <button type="button" className="tg-history__ic" aria-label="Mở thanh bên" title="Mở thanh bên" onClick={onToggle}><Icon name="sidebar" size={19} /></button>
        <button type="button" className="tg-history__ic" aria-label="Cuộc trò chuyện mới" title="Cuộc trò chuyện mới" disabled={busy} onClick={onNew}><Icon name="edit" size={19} /></button>
        <button type="button" className="tg-history__ic" aria-label="Tìm kiếm" title="Tìm kiếm" onClick={() => setSearching(true)}><Icon name="search" size={19} /></button>
      </div>
      {palette}
      {confirm}
    </>
  )
  return (
    <aside className="tg-history" aria-label="Lịch sử chat">
      <header className="tg-history__head">
        <h2 className="tg-history__brand">Trò chuyện</h2>
        <div className="tg-history__tools">
          <button type="button" className="tg-history__ic" aria-label="Tìm kiếm" title="Tìm kiếm" onClick={() => setSearching(true)}><Icon name="search" size={19} /></button>
          <button type="button" className="tg-history__ic" aria-label="Đóng thanh bên" title="Đóng thanh bên" onClick={onToggle}><Icon name="sidebar" size={19} /></button>
        </div>
      </header>
      <button type="button" className="tg-history__new" disabled={busy} onClick={onNew}><Icon name="edit" size={18} />Cuộc trò chuyện mới</button>
      {palette}
      <div className="tg-history__list">
        {error ? <div className="tg-history__empty" role="status"><Icon name="warn" size={20} /><p>Chưa tải được lịch sử.</p><button type="button" className="tg-link" onClick={() => setRetry(n => n + 1)}>Thử lại</button></div>
          : !list ? <div className="tg-history__skeleton" role="status" aria-label="Đang tải lịch sử">{[0, 1, 2, 3, 4].map(i => <span key={i} aria-hidden="true"><i /></span>)}</div>
          : shown.length === 0 ? <div className="tg-history__empty"><Icon name="compass" size={20} /><p>Những chuyến bạn bắt đầu sẽ nằm ở đây.</p></div>
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
      {confirm}
      <footer className="tg-history__foot"><Icon name="lock" size={14} /><span>Mỗi chuyến đi, một câu chuyện riêng.</span></footer>
    </aside>
  )
}
