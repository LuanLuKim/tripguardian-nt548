import { useRef, useState, type Dispatch, type KeyboardEvent, type SetStateAction } from 'react'
import * as Popover from '@radix-ui/react-popover'
import { info } from '../lib'
import { placesDelta } from '../tu/labels'
import type { Card, Group } from '../pd/types'
import { Icon, type IconName } from './icons'

// Lựa chọn as a filter column beside a grid: the groups of Decision (a server tab each), then what the page on screen can be cut by.
// Filters and sort act on the cards of the page shown (the server ranks and pages each group); the count line says so.

export type SortKey = 'rank' | 'rating' | 'az' | 'za'
export interface Browse { areas: string[]; sort: SortKey }
export const NO_BROWSE: Browse = { areas: [], sort: 'rank' }
export const SORTS: { id: SortKey; label: string }[] = [
  { id: 'rank', label: 'Hợp nhất' }, // the order Decision ranked them in, by its own score for this trip
  { id: 'rating', label: 'Đánh giá tốt nhất' },
  { id: 'az', label: 'Tên A → Z' },
  { id: 'za', label: 'Tên Z → A' },
]

export const isFiltered = (b: Browse) => b.areas.length > 0
export const areaOf = (c: Card) => info(c.id)?.area ?? c.area ?? null // the same order the card prints it in

// How two places compare under a sort. A place with no Google score comes after those that have one (unknown is not "bad").
// Array.sort is stable, so equal keys keep the server's rank; `rank` itself is no comparison at all.
export type Sortable = { name: string; stars: number }
export function compareFor(sort: SortKey): ((x: Sortable, y: Sortable) => number) | null {
  const byName = (x: Sortable, y: Sortable) => x.name.localeCompare(y.name, 'vi')
  return sort === 'rating' ? (x, y) => y.stars - x.stars : sort === 'az' ? byName : sort === 'za' ? (x, y) => byName(y, x) : null
}
const sortable = (c: Card): Sortable => ({ name: c.name, stars: info(c.id)?.rating ?? -1 })
export const inAreas = (b: Browse, area: string | null) => !b.areas.length || (area !== null && b.areas.includes(area))

export function browseCards(cards: Card[], b: Browse): Card[] {
  const out = cards.filter((c) => inAreas(b, areaOf(c)))
  const cmp = compareFor(b.sort)
  return cmp ? [...out].sort((x, y) => cmp(sortable(x), sortable(y))) : out
}

export function areaOptions(names: (string | null)[]) {
  const n = new Map<string, number>()
  names.forEach((a) => { if (a) n.set(a, (n.get(a) ?? 0) + 1) })
  return [...n.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], 'vi')).map(([name, count]) => ({ name, count }))
}

export interface SideLodging { total: number | null; waiting: boolean; done: boolean }

interface Props {
  query: string
  setQuery: (q: string) => void
  searchLabel: string
  searchHint: string
  groups: Group[]
  currentId: string | undefined
  onLodging: boolean
  fresh: Record<string, number>
  icons: Record<string, IconName>
  onPick: (id: string) => void
  lodging: SideLodging | null
  onPickLodging: () => void
  areaNames: (string | null)[] // the area of every place on screen: what the area list and its counts are made from
  browse: Browse
  setBrowse: Dispatch<SetStateAction<Browse>>
  limits: { rule: string; reason: string; count: number }[] // what the trip's own limits took out
  onRelax: () => void
}

export function ExploreSide(p: Props) {
  const areas = areaOptions(p.areaNames)
  const filterable = !p.onLodging && p.areaNames.length > 0
  const ids = p.groups.map((g) => g.id)
  const move = (e: KeyboardEvent, step: number) => {
    if (!ids.length) return
    e.preventDefault()
    const i = Math.max(0, ids.indexOf(p.currentId ?? ids[0]))
    p.onPick(ids[(i + step + ids.length) % ids.length])
  }
  const toggleArea = (a: string) => p.setBrowse((b) => ({ ...b, areas: b.areas.includes(a) ? b.areas.filter((x) => x !== a) : [...b.areas, a] }))
  return (
    <aside className="tg-xside" aria-label="Bộ lọc địa điểm">
      <section className="tg-xside__box">
        <h2 className="tg-xside__h">Tìm theo tên</h2>
        <label className="tg-xsearch">
          <Icon name="search" size={18} />
          <input type="search" value={p.query} onChange={(e) => p.setQuery(e.target.value)} onKeyDown={(e) => { if (e.key === 'Escape') p.setQuery('') }} placeholder={p.searchHint} aria-label={p.searchLabel} />
          {p.query && <button type="button" className="tg-xsearch__clear" aria-label="Xóa ô tìm" onClick={() => p.setQuery('')}><Icon name="x" size={16} /></button>}
        </label>
      </section>

      <section className="tg-xside__box">
        <h2 className="tg-xside__h" id="tg-xside-groups">Nhóm địa điểm</h2>
        <div className="tg-xside__list" role="tablist" aria-orientation="vertical" aria-labelledby="tg-xside-groups" onKeyDown={(e) => { if (e.key === 'ArrowDown' || e.key === 'ArrowRight') move(e, 1); else if (e.key === 'ArrowUp' || e.key === 'ArrowLeft') move(e, -1) }}>
          {p.groups.map((g) => {
            const on = !p.onLodging && p.currentId === g.id
            return (
              <button key={g.id} type="button" role="tab" aria-selected={on} tabIndex={on ? 0 : -1} className="tg-xopt" title={g.label} onClick={() => p.onPick(g.id)}>
                <span className="tg-xopt__mark" aria-hidden="true">{on && <Icon name="check" size={12} />}</span>
                <span className="tg-xopt__t">{g.label}</span>
                {p.fresh[g.id] ? <i className="tg-tab__new" aria-label={`${p.fresh[g.id]} nơi mới`}>+{p.fresh[g.id]}</i> : null}
                <b className="tg-xopt__n">{g.total}</b>
              </button>
            )
          })}
          {p.lodging && (
            <button type="button" role="tab" aria-selected={p.onLodging} tabIndex={p.onLodging ? 0 : -1} className="tg-xopt" onClick={p.onPickLodging}>
              <span className="tg-xopt__mark" aria-hidden="true">{p.onLodging && <Icon name="check" size={12} />}</span>
              <span className="tg-xopt__t">Nơi lưu trú</span>
              {p.lodging.done ? <Icon name="check" size={14} /> : null}
              {p.lodging.total ? <b className="tg-xopt__n">{p.lodging.total}</b> : p.lodging.waiting ? <b className="tg-tab__wait" aria-label="Đang đếm"><i /></b> : null}
            </button>
          )}
        </div>
      </section>

      {p.limits.length > 0 && (
        <section className="tg-xside__box">
          <h2 className="tg-xside__h">Giới hạn của bạn <span className="tg-xside__sub">đã loại {p.limits.reduce((n, r) => n + r.count, 0)} nơi</span></h2>
          <ul className="tg-xlim">
            {p.limits.map((r) => <li key={r.rule} title={r.reason}><Icon name="lock" size={14} /><span>{r.reason[0].toUpperCase() + r.reason.slice(1)}</span><b className="tg-xopt__n">{r.count}</b></li>)}
          </ul>
          <button type="button" className="tg-link tg-xlim__go" onClick={p.onRelax}>Nới giới hạn</button>
        </section>
      )}

      {filterable && areas.length > 1 && (
        <section className="tg-xside__box">
          <h2 className="tg-xside__h">Khu vực</h2>
          <div className="tg-xside__list is-scroll">
            {areas.map((a) => {
              const on = p.browse.areas.includes(a.name)
              return (
                <button key={a.name} type="button" role="checkbox" aria-checked={on} className="tg-xopt" title={a.name} onClick={() => toggleArea(a.name)}>
                  <span className="tg-xopt__mark" aria-hidden="true">{on && <Icon name="check" size={12} />}</span>
                  <span className="tg-xopt__t">{a.name}</span>
                  <b className="tg-xopt__n">{a.count}</b>
                </button>
              )
            })}
          </div>
        </section>
      )}


    </aside>
  )
}

// The sort as a menu of its own (the native <select> opens the browser's grey list): the label and the choice in one pill, the choices
// in a card under it with the one in use ticked. ↑ ↓ move, Enter picks, Esc closes; the pill keeps focus afterwards.
function SortMenu({ value, onChange }: { value: SortKey; onChange: (k: SortKey) => void }) {
  const [open, setOpen] = useState(false)
  const list = useRef<HTMLDivElement>(null)
  const now = SORTS.find((s) => s.id === value) ?? SORTS[0]
  const step = (e: KeyboardEvent, d: number) => {
    const items = [...(list.current?.querySelectorAll<HTMLElement>('[role=option]') ?? [])]
    if (!items.length) return
    e.preventDefault()
    const at = items.indexOf(document.activeElement as HTMLElement)
    items[(at + d + items.length) % items.length].focus()
  }
  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <button type="button" className="tg-xsort" aria-haspopup="listbox" aria-expanded={open}>
          <Icon name="sliders" size={16} /><span className="tg-xsort__l">Sắp xếp</span><span className="tg-xsort__v">{now.label}</span><Icon name="chevronDown" size={16} />
        </button>
      </Popover.Trigger>
      <Popover.Portal>
          <Popover.Content className="tg tg-xmenu" align="end" sideOffset={8} collisionPadding={12}
            onOpenAutoFocus={(e) => { e.preventDefault(); list.current?.querySelector<HTMLElement>('[aria-selected=true]')?.focus() }}>
            <div ref={list} role="listbox" aria-label="Sắp xếp các nơi đang hiện" onKeyDown={(e) => { if (e.key === 'ArrowDown') step(e, 1); else if (e.key === 'ArrowUp') step(e, -1) }}>
              {SORTS.map((s) => (
                <button key={s.id} type="button" role="option" aria-selected={s.id === value} tabIndex={s.id === value ? 0 : -1} className="tg-xmenu__opt" onClick={() => { onChange(s.id); setOpen(false) }}>
                  <span>{s.label}</span>{s.id === value && <Icon name="check" size={16} />}
                </button>
              ))}
            </div>
          </Popover.Content>
        </Popover.Portal>
    </Popover.Root>
  )
}

// Above the grid: how many, the filters that are on (each one removable), and the sort.
export function ExploreBar({ label, total, shown, onPage, partial, delta, browse, setBrowse }: { label: string; total: number; shown: number; onPage: number; partial: boolean; delta: { key: number; delta: number } | null; browse: Browse; setBrowse: Dispatch<SetStateAction<Browse>> }) {
  const on = isFiltered(browse)
  return (
    <div className="tg-xbar">
      <div className="tg-xbar__row">
        <p className="tg-xbar__n" aria-live="polite">{on ? <><b>{shown}</b> trong {onPage} nơi đang hiện</> : partial ? <><b>{total}</b> nơi hợp chuyến · hiện {onPage} nơi đầu, chọn một nhóm để xem hết</> : <><b>{total}</b> nơi · {label}</>}{delta && <span key={delta.key} className={`tg-xhead__delta tg-mono ${delta.delta < 0 ? 'is-down' : 'is-up'}`}>{placesDelta(delta.delta)}</span>}</p>
        <SortMenu value={browse.sort} onChange={(sort) => setBrowse((b) => ({ ...b, sort }))} />
      </div>
      {(on || browse.sort !== 'rank') && (
        <div className="tg-xbar__chips" role="group" aria-label="Bộ lọc đang bật">
          {browse.areas.map((a) => <button key={a} type="button" className="tg-xchip" onClick={() => setBrowse((b) => ({ ...b, areas: b.areas.filter((x) => x !== a) }))}>{a}<Icon name="x" size={13} /><span className="tg-sr">Bỏ lọc {a}</span></button>)}
          {browse.sort !== 'rank' && <span className="tg-xbar__note tg-faint">Chỉ xếp lại trong trang đang xem</span>}
          {on && <button type="button" className="tg-link tg-xbar__clear" onClick={() => setBrowse((b) => ({ ...NO_BROWSE, sort: b.sort }))}>Xóa bộ lọc</button>}
        </div>
      )}
    </div>
  )
}
