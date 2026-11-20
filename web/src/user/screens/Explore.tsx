import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { impression } from '../events'
import { useDecision } from '../pd/decision'
import type { Card, Group, SearchResult } from '../pd/types'
import { searchList } from '../pd/api'
import { useBegin } from '../home/dialogs'
import { useStarting } from '../startTrip'
import { openAssistant, setUi, toggleCmp, useUi } from '../store'
import { WaitLine } from '../ui/SlowHint'
import '../css/fixes.css'
import { useTrip } from '../trip'
import { AssistantFloat, AssistantPinned } from '../ui/Assistant'
import { ArtHills, Empty, go, PlacePhoto } from '../ui/common'
import { openPlace } from '../ui/PlaceSheet'
import { Icon, type IconName } from '../ui/icons'
import { PlaceCard } from '../ui/PlaceCard'
import { areaOf, browseCards, compareFor, ExploreBar, ExploreSide, inAreas, isFiltered, NO_BROWSE, type Browse } from '../ui/ExploreSide'
import { info } from '../lib'
import { Pager } from '../ui/Pager'
import { SelectedBar } from '../ui/SelectedBar'
import { SplitPlan, useSplit, ViewSwitch } from '../ui/SplitPlan'
import { warmMap } from './plan/TripMap'
import { reducedMotion, useStagedList } from '../ui/useStagedList'
import { Page, useTitle } from '../ui/Shell'
import { LongTripWarning } from '../ui/LongTripWarning'
import { LODGING_TAB, LodgingPanel, LodgingSearchResults, useLodgingList, useStayCards } from './Lodging'

const NO_CARDS: Card[] = []
const ALL_STEP = 48 // Tất cả shows this many at a time; "Xem thêm" shows the next ones
const ALL_TAB = 'all' // every group at once: the first page of each, best first

// The rules that hid places, one plain sentence each. The server words a hard filter as «Điều kiện “<what> = | ≠ <value>”» (the user's own
// condition): "≠ có" is "no <what>", so it reads "Bỏ N nơi <what>". A place closed on every day of the trip needs no line: closed places are closed.
export function limitLines(rules: { rule: string; label: string; count: number }[]) {
  return rules.flatMap((r) => {
    if (r.rule === 'closed_all_trip_days') return []
    const m = /^Điều kiện “(.+) (=|≠) (.+)”$/.exec(r.label)
    // `reason` is what the row says after "<count> nơi bị bỏ": the thing those places have (or lack) that the user's condition rules out.
    if (!m) return [{ ...r, reason: r.label.toLowerCase(), text: `Bỏ ${r.count} nơi: ${r.label.toLowerCase()}` }]
    const [, what, op, value] = m
    const [reason, text] = (op === '≠' && value === 'có') || (op === '=' && value === 'không') ? [what, `Bỏ ${r.count} nơi ${what}`]
      : (op === '=' && value === 'có') || (op === '≠' && value === 'không') ? [`bạn chỉ giữ nơi ${what}`, `Chỉ giữ nơi ${what}, bỏ ${r.count} nơi còn lại`]
      : op === '=' ? [`bạn chỉ giữ nơi ${what} ${value}`, `Chỉ giữ nơi ${what} ${value}, bỏ ${r.count} nơi còn lại`]
      : [`${what} ${value}`, `Bỏ ${r.count} nơi ${what} ${value}`]
    return [{ ...r, reason, text }]
  })
}
// Every tab starts with its own icon, the stay tab's bed included, so the row reads as one.
const TAB_ICONS: Record<string, IconName> = { meal: 'utensils', snack: 'smile', cafe: 'coffee', chill: 'coffee', nature: 'sun', garden: 'tree', camping: 'flame', sights: 'pin', culture: 'flag', fun: 'zap', night: 'moon', spa: 'heart', market: 'ticket' }
// To see or relax a limit the user talks to the chat beside the lists (it reads and changes the trip; the lists follow).
export function useEditTicket() {
  return () => openAssistant(true)
}

export function Explore() {
  useTitle('Lựa chọn')
  const { trip } = useTrip()
  const { view, error, act, busy, reload, more, loadingMore } = useDecision()
  const tab = useUi((u) => u.tab)
  const cmp = useUi((u) => u.cmp)
  const [dropFor, setDropFor] = useState<Card | null>(null)
  const asst = useUi((u) => u.assistant)
  const editTicket = useEditTicket()
  const starting = useStarting()
  const begin = useBegin()
  const split = useSplit()
  // The map beside the list opens without waiting: its code, style and connection are read while the page is idle.
  useEffect(() => {
    const ric = window.requestIdleCallback ?? ((f: () => void) => window.setTimeout(f, 800))
    const id = ric(() => warmMap())
    return () => (window.cancelIdleCallback ?? clearTimeout)(id)
  }, [])
  // The cards are rows while the map is beside them (it is the width they have), photos otherwise.
  const layout = split.open ? 'list' : 'grid'
  const [hotPlace, setHotPlace] = useState<string | null>(null) // the place under the pointer in the list: its dot on the map
  const pinned = asst.open && asst.pinned && !split.open // the chat pins beside the grid only while the schedule is not beside it
  const groups = useMemo(() => view?.groups.filter((g) => g.id !== 'anchors' && (g.cards.length || g.total)) ?? [], [view?.groups])
  const needsLodging = Boolean(view?.lodging) // one lodging per trip: the tab is always there (to pick, or to change)
  const lodgingList = useLodgingList(needsLodging)
  const stayTotal = needsLodging ? lodgingList.opts?.total ?? 0 : 0
  // Tất cả: the first page of every group, best first, and the stays (their own list, after Decision's) with them.
  const allGroup = useMemo<Group | null>(() => {
    if (groups.length < 2) return null
    const seen = new Map<string, Card>()
    groups.forEach((g) => g.cards.forEach((c) => { if (!seen.has(c.id)) seen.set(c.id, c) }))
    return { id: ALL_TAB, label: 'Tất cả', total: groups.reduce((n, g) => n + g.total, 0) + stayTotal, cards: [...seen.values()].sort((a, b) => b.score - a.score) }
  }, [groups, stayTotal])
  const tabs = allGroup ? [allGroup, ...groups] : groups
  const current = tabs.find((g) => g.id === tab) ?? tabs[0] // opens on Tất cả
  const onLodging = needsLodging && tab === LODGING_TAB
  const onAll = current?.id === ALL_TAB
  const stays = useMemo(() => (onAll && needsLodging ? lodgingList.opts?.candidates ?? [] : []), [onAll, needsLodging, lodgingList.opts])
  const stay = useStayCards()
  useEffect(() => { current?.cards.forEach((c, i) => impression(c.id, c.group ?? current.id, i + 1)) }, [current?.id, current?.cards.length]) // eslint-disable-line react-hooks/exhaustive-deps
  const onCmp = toggleCmp
  const goCompare = (ids: string[]) => go(`/explore/compare/${ids.map(encodeURIComponent).join(',')}`)
  // The header count moved (a chat wish, an edited ticket): show by how much next to it.
  const listed = view ? view.groups.filter((g) => g.id !== 'anchors').reduce((n, g) => n + g.total, 0) : null
  const lastListed = useRef<number | null>(null)
  const [listMove, setListMove] = useState<{ key: number; delta: number } | null>(null)
  useEffect(() => {
    if (listed === null) return
    const before = lastListed.current
    lastListed.current = listed
    if (before !== null && before !== listed) setListMove({ key: Date.now(), delta: listed - before })
  }, [listed])
  // Tabs whose list changed in the last rebuild while the user looked elsewhere: "+N mới" until they open it.
  const [fresh, setFresh] = useState<Record<string, number>>({})
  const loaded = useRef(false) // the first view is no change: nothing on it is "mới"
  useEffect(() => {
    if (!view) return
    if (!loaded.current) { loaded.current = true; return }
    const ch = view.change ?? {}
    setFresh((f) => {
      const next = { ...f }
      for (const [g, c] of Object.entries(ch)) if (c.added > 0 && g !== current?.id) next[g] = c.added
      return next
    })
  }, [view?.change]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (current?.id === ALL_TAB && Object.keys(fresh).length) setFresh({}); else if (current && fresh[current.id]) setFresh(({ [current.id]: _, ...rest }) => rest) }, [current?.id, fresh]) // eslint-disable-line react-hooks/exhaustive-deps
  const { items, replacing } = useStagedList(current?.id ?? '', current?.cards ?? NO_CARDS, current ? view?.change?.[current.id] : undefined)

  // The filter column and the sort act on the page on screen; another group starts clean (its areas are not this one's).
  const [browse, setBrowse] = useState<Browse>(NO_BROWSE)
  useEffect(() => { setBrowse((b) => (isFiltered(b) ? { ...NO_BROWSE, sort: b.sort } : b)) }, [current?.id])
  const shownItems = useMemo(() => {
    if (!isFiltered(browse) && browse.sort === 'rank') return items
    const order = new Map(browseCards(current?.cards ?? NO_CARDS, browse).map((c, i) => [c.id, i]))
    return items.filter((x) => order.has(x.card.id)).sort((a, b) => order.get(a.card.id)! - order.get(b.card.id)!)
  }, [items, browse, current?.cards])
  // The grid: Decision's cards, then (on Tất cả) the stays; any other order than "Hợp nhất" mixes them by that order.
  const [shownCount, setShownCount] = useState(ALL_STEP)
  useEffect(() => { setShownCount(ALL_STEP) }, [current?.id, browse])
  const rows = useMemo(() => {
    const out: ({ kind: 'pc'; id: string; name: string; stars: number; x: (typeof shownItems)[number] } | { kind: 'stay'; id: string; name: string; stars: number; c: (typeof stays)[number] })[] = [
      ...shownItems.map((x) => ({ kind: 'pc' as const, id: x.card.id, name: x.card.name, stars: info(x.card.id)?.rating ?? -1, x })),
      ...stays.filter((c) => inAreas(browse, info(c.id)?.area ?? c.area ?? null)).map((c) => ({ kind: 'stay' as const, id: c.id, name: c.name, stars: info(c.id)?.rating ?? c.rating ?? -1, c })),
    ]
    const cmp = compareFor(browse.sort)
    return cmp && stays.length ? out.sort(cmp) : out
  }, [shownItems, stays, browse])

  // Kept cards that moved slide from where they were (FLIP) instead of jumping.
  const gridRef = useRef<HTMLDivElement>(null)
  const rects = useRef(new Map<string, DOMRect>())
  useLayoutEffect(() => {
    const el = gridRef.current
    if (!el) return
    const cards = [...el.querySelectorAll<HTMLElement>('[data-place]')]
    if (!reducedMotion())
      cards.forEach((n) => {
        const old = rects.current.get(n.dataset.place!)
        const r = n.getBoundingClientRect()
        if (old && (Math.abs(old.left - r.left) > 2 || Math.abs(old.top - r.top) > 2))
          n.animate([{ transform: `translate(${old.left - r.left}px, ${old.top - r.top}px)` }, { transform: 'none' }], { duration: 280, easing: 'cubic-bezier(.2,.8,.2,1)' })
      })
    rects.current = new Map(cards.map((n) => [n.dataset.place!, n.getBoundingClientRect()]))
  }, [shownItems])

  // A tab is cut into pages; the user picks one and the grid starts again from its top.
  const goPage = (n: number) => {
    if (!current) return
    void more(current.id, n).then(() => gridRef.current?.scrollIntoView({ behavior: reducedMotion() ? 'auto' : 'smooth', block: 'start' }))
  }

  // Typed words search every tab by name, kind or tab; the answer follows the list as it changes (a pick, a chat).
  const [query, setQuery] = useState('')
  const [found, setFound] = useState<SearchResult | null>(null)
  const searching = query.trim().length >= 2
  useEffect(() => {
    if (!searching || !trip.decisionId || onLodging) { setFound(null); return }
    let live = true
    const t = setTimeout(() => { searchList(trip.decisionId!, query.trim()).then((r) => { if (live) setFound(r) }, () => { if (live) setFound(null) }) }, 300)
    return () => { live = false; clearTimeout(t) }
  }, [query, searching, onLodging, trip.decisionId, view?.version, view?.selected.length]) // eslint-disable-line react-hooks/exhaustive-deps

  // A trip being made (the home's button, an old chat moving on) shows the lists' shape meanwhile; with none, one tap makes it.
  if (!trip.decisionId && !starting)
    return (
      <>
        <Page narrow><Empty art={<ArtHills />} title="Chưa có chuyến nào đang chọn" body={error ?? 'Mình gợi ý ngay những nơi nổi bật nhất, bạn chọn và trò chuyện để lọc thêm.'} action={<button type="button" className="tg-btn tg-btn--primary" onClick={() => begin({})}><Icon name="compass" size={18} /> Khám phá nơi muốn đến</button>} /></Page>
      </>
    )
  if (!view)
    return (
      <>
        <Page>
          {error ? (
            <Empty art={<ArtHills />} title="Chưa tải được gợi ý" body={`${error} Lựa chọn của bạn vẫn còn nguyên.`} action={<button type="button" className="tg-btn tg-btn--primary" onClick={reload}><Icon name="refresh" size={18} /> Thử lại</button>} />
          ) : (
            <>
              <WaitLine text="Đang chuẩn bị gợi ý cho chuyến của bạn…" />
              <div className="tg-grid" aria-busy="true">{Array.from({ length: 6 }, (_, i) => <div key={i} className="tg-skel-card"><div className="tg-skel" /><div><span className="tg-skel tg-skel-line" style={{ width: '70%' }} /><span className="tg-skel tg-skel-line" style={{ width: '90%' }} /><span className="tg-skel tg-skel-line" style={{ width: '55%' }} /></div></div>)}</div>
            </>
          )}
        </Page>
      </>
    )

  const anchors = view.groups.find((g) => g.id === 'anchors')?.cards ?? []
  const total = groups.reduce((n, g) => n + g.total, 0) + anchors.length
  const limits = limitLines(view.excluded.by_rule)
  const q = view.pending
  const question = q && (
    <div key="ask" className="tg-narrow" aria-live="polite">
      <b>{q.text}</b>
      {q.chips.map((c) => <button key={c.id} type="button" className="tg-chip" disabled={busy} onClick={() => act({ type: 'answer', qid: q.qid, chip: c.id })}>{c.label}</button>)}
      {q.reason && <span className="tg-faint tg-narrow__why">Vì sao hỏi: {q.reason}</span>}
    </div>
  )
  return (
    <>
      <Page className="tg-page--bleed">
        <div className={`tg-xlayout ${pinned ? 'is-pinned' : ''}`}>
          <div className="tg-xmain">
            <header className="tg-xhead"><h1>Gợi ý cho chuyến của bạn</h1><ViewSwitch open={split.open} onChange={(map) => { if (map !== split.open) split.toggle() }} /></header>

            <LongTripWarning days={view.days.length} />

            {view.filter && view.filter.active.length > 0 && (
              <div className="tg-xfilter" role="group" aria-label="Bộ lọc">
                <b>Đang lọc</b>
                {view.filter.active.map((f) => <span key={`${f.key}=${f.value}`} className="tg-chip tg-chip--soft">{f.label}</span>)}
                <span className="tg-faint">{view.filter.hidden} nơi đang ẩn</span>
                <button type="button" className="tg-link" disabled={busy} onClick={() => act({ type: 'unfilter' })}>Bỏ lọc</button>
              </div>
            )}

            {total === 0 ? (
              <Empty art={<ArtHills />} title="Giới hạn hiện tại loại hết các nơi" body="Nới một giới hạn để mình gợi ý lại; mình không tự bỏ giới hạn của bạn." action={<button type="button" className="tg-btn tg-btn--primary" onClick={editTicket}>Xem và nới giới hạn</button>} />
            ) : (
              <>
                {total - anchors.length > 0 && total - anchors.length < 4 && <div className="tg-narrow"><b>Chỉ còn {total - anchors.length} nơi hợp.</b><span className="tg-muted">Nới một giới hạn để có thêm lựa chọn?</span><button type="button" className="tg-link" onClick={editTicket}>Xem giới hạn</button></div>}
                {anchors.length > 0 && (
                  <section className="tg-req" aria-labelledby="tg-req-h">
                    <div><h2 id="tg-req-h">Nơi bắt buộc đến</h2><p>Mình xếp cả chuyến quanh các nơi này.</p></div>
                    <div className="tg-req__row">{anchors.map((c) => <button key={c.id} type="button" className="tg-req__row" onClick={(e) => openPlace(c.id, e.currentTarget.querySelector('figure'))}><PlacePhoto id={c.id} name={c.name} /><span><b>{c.name}</b><br /><small className="tg-muted">{c.area ?? c.category}</small></span></button>)}</div>
                  </section>
                )}
                <div className="tg-xbrowse">
                  <ExploreSide
                    query={query} setQuery={setQuery}
                    searchLabel={onLodging ? 'Tìm nơi lưu trú' : 'Tìm địa điểm trong mọi nhóm'}
                    searchHint={onLodging ? 'Tìm chỗ ở' : 'Tìm nơi'}
                    groups={tabs} currentId={current?.id} onLodging={onLodging} fresh={fresh} icons={TAB_ICONS}
                    onPick={(id) => setUi({ tab: id })}
                    lodging={needsLodging ? { total: lodgingList.opts?.total ?? null, waiting: !lodgingList.failed, done: Boolean(view.lodging?.chosen || view.lodging?.booked) } : null}
                    onPickLodging={() => setUi({ tab: LODGING_TAB })}
                    areaNames={searching ? [] : [...(current?.cards ?? NO_CARDS).map(areaOf), ...stays.map((c) => info(c.id)?.area ?? c.area ?? null)]} browse={browse} setBrowse={setBrowse}
                    limits={limits} onRelax={editTicket}
                  />
                  <div className="tg-xbrowse__main">
                    {searching && onLodging ? <LodgingSearchResults q={query.trim()} onClear={() => setQuery('')} /> : searching ? <SearchResults q={query.trim()} found={found} groups={groups} cmp={cmp} onCmp={onCmp} onDrop={setDropFor} pinned={pinned} onClear={() => setQuery('')} /> : <>
                    {!onLodging && current && current.cards.length > 0 && <ExploreBar label={current.label} total={current.total} shown={rows.length} onPage={current.cards.length + stays.length} partial={current.id === ALL_TAB} delta={listMove} browse={browse} setBrowse={setBrowse} />}
                    {onLodging ? <LodgingPanel list={lodgingList} /> : !current || current.cards.length === 0 ? (
                      <>
                        {question}
                        <Empty art={<ArtHills />} title="Chưa có nơi nào ở nhóm này" body="Thử nhóm khác, hoặc nới giới hạn để có thêm lựa chọn." />
                      </>
                    ) : rows.length === 0 ? (
                      <Empty art={<ArtHills />} title="Không có nơi nào khớp bộ lọc" body="Bỏ bớt một bộ lọc, hoặc xem trang khác của nhóm này." action={<button type="button" className="tg-btn tg-btn--ghost" onClick={() => setBrowse((b) => ({ ...NO_BROWSE, sort: b.sort }))}>Xóa bộ lọc</button>} />
                    ) : (
                      <div ref={gridRef} className={`tg-grid ${pinned ? 'is-two' : ''} ${layout === 'list' ? 'is-list' : ''} ${replacing ? 'is-replacing' : ''}`} key={current.id} onPointerOver={(e) => { const id = (e.target as HTMLElement).closest<HTMLElement>('[data-place]')?.dataset.place ?? null; if (split.open && id !== hotPlace) setHotPlace(id) }} onPointerLeave={() => setHotPlace(null)}>
                        {(onAll ? rows.slice(0, shownCount) : rows).flatMap((r, i) => {
                          const out = [r.kind === 'pc' ? <PlaceCard key={r.id} c={r.x.card} phase={r.x.phase} order={r.x.i} onDrop={setDropFor} cmp={cmp.includes(r.id)} onCmp={onCmp} /> : stay.render(r.c, i)]
                          if (i === Math.min(4, Math.min(rows.length, onAll ? shownCount : rows.length) - 1) && question) out.push(question)
                          return out
                        })}
                      </div>
                    )}
                    {onAll && !onLodging && rows.length > 0 && (
                      <div className="tg-xmore">
                        {rows.length > shownCount
                          ? <button type="button" className="tg-btn tg-btn--ghost" onClick={() => setShownCount((n) => n + ALL_STEP)}>Xem thêm {Math.min(ALL_STEP, rows.length - shownCount)} nơi</button>
                          : <p className="tg-faint">Đã hiện {rows.length} nơi. Chọn một nhóm bên trái để xem tiếp.</p>}
                      </div>
                    )}
                    {!onLodging && current && current.id !== ALL_TAB && current.cards.length > 0 && <Pager label={current.label} total={current.total} page={current.page ?? 0} pages={current.pages ?? 1} from={(current.offset ?? 0) + 1} to={(current.offset ?? 0) + current.cards.length} busy={loadingMore === current.id} onPage={goPage} />}
                    </>}
                  </div>
                </div>
                {view.unverified.count > 0 && (
                  <details className="tg-unverified" open={view.unverified.open}>
                    <summary><Icon name="info" size={16} /> Chưa xác minh được điều kiện của bạn ({view.unverified.count})</summary>
                    <p>Chưa đủ bằng chứng để nói các nơi này hợp với điều kiện bạn đặt. Tự kiểm tra trước nếu muốn chọn.</p>
                    <div className={`tg-grid ${pinned ? 'is-two' : ''}`}>{view.unverified.cards.map((c) => <PlaceCard key={c.id} c={c} onDrop={setDropFor} cmp={cmp.includes(c.id)} onCmp={onCmp} />)}</div>
                  </details>
                )}
              </>
            )}
          </div>
          {pinned && <AssistantPinned />}
        </div>
      </Page>

      {cmp.length >= 2 && <button type="button" className="tg-btn tg-btn--primary tg-float-cmp" onClick={() => goCompare(cmp)}><Icon name="swap" size={18} /> So sánh {cmp.length} nơi</button>}
      <SelectedBar />
      {split.open && <SplitPlan hot={hotPlace} onHot={setHotPlace} onClose={split.close} />}
      <AssistantFloat pinAllowed={!split.open} />
      {stay.dialog}
      <DropSheet card={dropFor} onClose={() => setDropFor(null)} />
    </>
  )
}

// What the search box found: places of every tab, best first, each with its tab; then named places the lists do not hold, and why.
function SearchResults({ q, found, groups, cmp, onCmp, onDrop, pinned, onClear }: { q: string; found: SearchResult | null; groups: Group[]; cmp: string[]; onCmp: (id: string) => void; onDrop: (c: Card) => void; pinned: boolean; onClear: () => void }) {
  if (!found || found.q !== q) return <p className="tg-busy" role="status"><i /> Đang tìm “{q}”…</p>
  const label = (id?: string | null) => groups.find((g) => g.id === id)?.label
  return (
    <section className="tg-xfound" aria-live="polite">
      <p className="tg-xfound__head">{found.total ? <><b>{found.total} nơi</b> khớp “{q}”{found.total > found.cards.length ? `, hiện ${found.cards.length} nơi hợp nhất` : ''}, xếp từ hợp nhất.</> : <>Không có nơi nào trong gợi ý khớp “{q}”. Thử một chữ ngắn hơn, bỏ dấu, hoặc tên loại nơi như “cà phê”, “chợ”.</>} <button type="button" className="tg-link" onClick={onClear}>Xóa tìm kiếm</button></p>
      {found.cards.length > 0 && (
        <div className={`tg-grid ${pinned ? 'is-two' : ''}`}>
          {found.cards.map((c) => (
            <div key={c.id} className="tg-xfound__item">
              {label(c.group) && <span className="tg-xfound__tab">{label(c.group)}</span>}
              <PlaceCard c={c} onDrop={onDrop} cmp={cmp.includes(c.id)} onCmp={onCmp} />
            </div>
          ))}
        </div>
      )}
      {found.outside.length > 0 && (
        <div className="tg-xfound__out">
          <h3>Không nằm trong gợi ý</h3>
          <ul>{found.outside.map((o) => <li key={o.id}><button type="button" className="tg-link" onClick={(e) => openPlace(o.id, e.currentTarget)}>{o.name}</button><span className="tg-muted"> · {o.reasons.join('; ')}</span></li>)}</ul>
        </div>
      )}
    </section>
  )
}

export function DropSheet({ card, onClose, after }: { card: Card | { id: string; name: string } | null; onClose: () => void; after?: () => void }) {
  const { act } = useDecision()
  const sent = useRef<string | null>(null)
  useEffect(() => {
    if (!card) { sent.current = null; return }
    if (sent.current === card.id) return
    sent.current = card.id
    onClose()
    void act({ type: 'drop', place_id: card.id }).then(ok => { if (ok) after?.() })
  }, [card, act, onClose, after])
  return null
}
