import * as Dialog from '@radix-ui/react-dialog'
import { useEffect, useState, type ReactNode } from 'react'
import { info } from '../../lib'
import { PlacePhoto } from '../../ui/common'
import { Icon, type IconName } from '../../ui/icons'
import { norm, openPlace } from './shared'

// The panel that slides in from the right on Lịch trình: one frame (SidePanel) for a short question or a list of places
// (PlacePanel: tabs, a search box, a scrolling list). It replaces the pages and pop-ups that used to take the user off the schedule.

export function SidePanel({ open, onClose, kicker, title, children, footer, busy = false }: {
  open: boolean; onClose: () => void; kicker?: string; title: string; children: ReactNode; footer?: ReactNode; busy?: boolean
}) {
  return (
    <Dialog.Root open={open} onOpenChange={(o) => { if (!o && !busy) onClose() }}>
      <Dialog.Portal>
        <Dialog.Overlay className="tg tg-overlay" />
        <Dialog.Content className="tg tg-side" aria-describedby={undefined}>
          <header className="tg-side__head">
            <div>{kicker && <p>{kicker}</p>}<Dialog.Title>{title}</Dialog.Title></div>
            <Dialog.Close className="tg-icon-btn" aria-label="Đóng" disabled={busy}><Icon name="x" size={20} /></Dialog.Close>
          </header>
          <div className="tg-side__body">{children}</div>
          {footer && <footer className="tg-side__foot">{footer}</footer>}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

export interface PanelItem {
  id: string
  name: string
  meta?: string
  why?: string | null
  warns?: string[]
  note?: string // why this one cannot be taken from here
  action: { label: string; icon?: IconName; disabled?: boolean; onClick: () => void } | null
}
export interface PanelTab { id: string; label: string; items: PanelItem[]; empty: string }

export function PlacePanel({ open, onClose, kicker, title, context, tabs, placeholder, remote }: {
  open: boolean; onClose: () => void; kicker?: string; title: string; context?: ReactNode; tabs: PanelTab[]; placeholder: string
  remote?: (q: string, signal: AbortSignal) => Promise<PanelItem[]> // a search that reaches beyond the tabs; without it the typed words filter the tab
}) {
  const [tab, setTab] = useState(tabs[0]?.id ?? '')
  const [q, setQ] = useState('')
  const [found, setFound] = useState<{ q: string; items: PanelItem[]; failed: boolean } | null>(null)
  const text = q.trim()
  const searching = text.length >= 2
  useEffect(() => {
    if (!open) { setQ(''); setTab(tabs[0]?.id ?? '') }
  }, [open]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!searching || !remote) { setFound(null); return }
    const ctl = new AbortController()
    const t = setTimeout(() => {
      remote(text, ctl.signal).then((items) => setFound({ q: text, items, failed: false }), (e) => { if (e?.name !== 'AbortError') setFound({ q: text, items: [], failed: true }) })
    }, 250)
    return () => { clearTimeout(t); ctl.abort() }
  }, [text, searching]) // eslint-disable-line react-hooks/exhaustive-deps
  const current = tabs.find((t) => t.id === tab) ?? tabs[0]
  const items: PanelItem[] | null = searching
    ? remote ? (found?.q === text ? found.items : null) : tabs.flatMap((t) => t.items).filter((x, i, all) => all.findIndex((y) => y.id === x.id) === i && norm(`${x.name} ${x.meta ?? ''}`).includes(norm(text)))
    : current?.items ?? []
  const empty = searching ? (found?.failed ? 'Chưa tìm được lúc này, bạn thử lại sau ít phút.' : `Không thấy nơi nào khớp “${text}”.`) : current?.empty ?? ''
  return (
    <SidePanel open={open} onClose={onClose} kicker={kicker} title={title}>
      {context && <p className="tg-side__ctx">{context}</p>}
      <label className="tg-side__search">
        <Icon name="search" size={18} />
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder={placeholder} aria-label={placeholder} />
        {q && <button type="button" aria-label="Xóa ô tìm" onClick={() => setQ('')}><Icon name="x" size={15} /></button>}
      </label>
      {!searching && tabs.length > 1 && (
        <div className="tg-side__tabs" role="tablist">
          {tabs.map((t) => <button key={t.id} type="button" role="tab" aria-selected={current?.id === t.id} onClick={() => setTab(t.id)}>{t.label}<b>{t.items.length}</b></button>)}
        </div>
      )}
      <div className="tg-side__list" aria-live="polite">
        {items === null ? <p className="tg-busy" role="status"><i /> Đang tìm “{text}”…</p>
          : !items.length ? <p className="tg-side__empty">{empty}</p>
          : <ul>{items.map((x) => {
            const known = !!info(x.id)
            return (
              <li key={x.id}>
                <button type="button" className="tg-side__ph" aria-label={`Xem chi tiết ${x.name}`} disabled={!known} onClick={() => openPlace(x.id)}>
                  {known ? <PlacePhoto id={x.id} name={x.name} sizes="120px" /> : <span aria-hidden="true"><Icon name="pin" size={22} /></span>}
                </button>
                <div className="tg-side__txt">
                  <b>{x.name}</b>
                  {x.meta && <small>{x.meta}</small>}
                  {x.why && <span><Icon name="check" size={13} /> {x.why}</span>}
                  {x.warns?.map((w, i) => <em key={i}>{w}</em>)}
                  {x.note && <em className="is-note">{x.note}</em>}
                </div>
                {x.action && <button type="button" className="tg-btn tg-btn--primary tg-btn--sm" aria-label={`${x.action.label}: ${x.name}`} disabled={x.action.disabled} onClick={x.action.onClick}>{x.action.icon && <Icon name={x.action.icon} size={15} />}{x.action.label}</button>}
              </li>
            )
          })}</ul>}
      </div>
    </SidePanel>
  )
}
