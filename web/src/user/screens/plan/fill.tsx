import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { mutateJourney, readJourney } from '../../journey'
import { primePlanning } from '../../planning/api'
import { usePlanning } from '../../planning/planning'
import type { DecisionOutput } from '../../pd/types'
import { useTrip } from '../../trip'
import { fromSearchInput } from '../../tu/adapter'
import { geoSearch } from '../../tu/api'
import type { Deck, DeckAnswers, DeckIssue, GeoHit, Readback, SearchInput, TurnInput } from '../../tu/types'
import { Icon } from '../../ui/icons'
import { PlaceInput } from '../../ui/PlaceInput'
import { RangeCalendar } from '../../ui/Gate'
import { DeckIssues, ExtraInputs, TAB_ICON, useDeckForm } from '../understand/Deck'
import '../../css/fill.css'
import { SidePanel } from './panels'

// The optional groups of the trip (who goes, how they move, pace, budget) that are still empty. Lịch trình runs without them;
// the user fills one in here when they want the plan to fit it, and the plan is built again from the new answer.

export function useFill(id: string | null, plan: string | null) {
  const [deck, setDeck] = useState<Deck | null>(null)
  const [open, setOpen] = useState<string | null>(null)
  const [tick, setTick] = useState(0)
  useEffect(() => {
    if (!id) return
    let live = true
    readJourney<Readback>(id, 'trip/readback').then(rb => { if (live) setDeck(rb.fill ?? null) }, () => { if (live) setDeck(null) })
    return () => { live = false }
  }, [id, plan, tick]) // read again after an answer (the plan keeps its id when it is built again): what is still empty, what is chosen
  const refresh = useCallback(() => setTick(n => n + 1), [])
  return { deck, open, setOpen, refresh }
}

// `only` / `except`: the way to the city is asked in its own row (Đến Đà Lạt), the rest under Thông tin chuyến.
// Each row shows its short answers right away (on hover / focus; always on touch screens): one tap saves it and the plan is
// built again. What needs more than one tap (a head count, several answers, a scope) opens the full sheet ("Chi tiết").
const KEEP_SHEET = new Set(['trip', 'lodging'])
// The option of the way in that the trip already holds (the answer is kept: the row shows it chosen, not only that it was busy).
const isChosen = (qid: string, o: string, ctx?: { arrival_mode?: string | null; mobility?: string | null }) =>
  qid === 'arrival' && (o === 'plane' || o === 'bus' ? ctx?.arrival_mode === o : ctx?.arrival_mode === 'self' && ctx.mobility === (o === 'self_motorbike' ? 'motorbike' : o === 'self_car' ? 'car' : '?'))
export function FillRows({ id, deck, onOpen, only, except, peek, onSaved }: { id: string; deck: Deck; onOpen: (qid: string) => void; only?: string; except?: string; onSaved?: () => void; peek?: (mode: 'plane' | 'bus') => ReactNode }) {
  const edit = useTripEdit(id, () => { onSaved?.() })
  const ctx = useTrip().trip.searchInput?.context
  const [amount, setAmount] = useState('')
  const [looking, setLooking] = useState<'plane' | 'bus' | null>(null) // the way whose tickets a resting mouse is looking at
  const save = (answers: DeckAnswers) => { void edit.run([{ kind: 'deck', answers, at: 'plan' }]) }
  const answer = (qid: string, o: string): DeckAnswers => qid === 'companions' ? (o === 'people.prefilled' ? { companions: [o] } : { 'companions.who': [o] }) : qid === 'budget' ? (o === 'unlimited' ? { 'budget.unlimited': 'true' } : o === 'amount.prefilled' ? { budget: [o] } : { 'budget.scope': o }) : { [qid]: [o] }
  const millions = Number(amount.replace(',', '.'))
  return <>{deck.tabs.filter(t => (!only || t.qid === only) && t.qid !== except).map(t => {
    const opts = KEEP_SHEET.has(t.qid) ? [] : t.options.filter(o => !['other', 'skip'].includes(o.id) && !(t.qid === 'budget' && !['unlimited', 'amount.prefilled'].includes(o.id)))
    const chosen = opts.find(o => isChosen(t.qid, o.id, ctx))
    const more = KEEP_SHEET.has(t.qid) || t.multi || t.inputs.length > 0
    return <div className={`tg-it-transit tg-fill${opts.length ? ' has-opts' : ''}`} key={t.qid} aria-busy={edit.busy || undefined} onPointerLeave={() => setLooking(null)}>
      <div className="tg-fill__top">
        <span><Icon name={TAB_ICON[t.qid] ?? 'info'} size={16} /><b>{t.header}</b>{chosen ? <em className="tg-fill__chosen"><Icon name="check" size={13} />{chosen.label}</em> : opts.length > 0 && <small className="tg-fill__q">{t.question}</small>}</span>
        {edit.busy ? <small className="tg-fill__busy">Đang xếp lại lịch…</small>
          : (more || !opts.length) && <button type="button" className="tg-it-textbtn" onClick={() => onOpen(t.qid)}>{opts.length ? 'Chi tiết' : t.qid === 'arrival' ? 'Chọn' : 'Thêm'}</button>}
      </div>
      {(opts.length > 0 || t.qid === 'budget') && <div className="tg-fill__opts"><div>
        {opts.map(o => <button key={o.id} type="button" className={`tg-fill__chip${o.prefilled ? ' is-guess' : ''}${isChosen(t.qid, o.id, ctx) ? ' is-on' : ''}`} aria-pressed={isChosen(t.qid, o.id, ctx)} disabled={edit.busy} title={o.description || undefined} onPointerEnter={(e) => { if (peek && t.qid === 'arrival' && e.pointerType === 'mouse') setLooking(o.id === 'plane' || o.id === 'bus' ? o.id : null) }} onClick={() => { if (!isChosen(t.qid, o.id, ctx)) save(answer(t.qid, o.id)) }}>{o.label}{o.prefilled && <small>mình đoán</small>}</button>)}
        {t.qid === 'budget' && t.inputs.includes('amount') && <form className="tg-fill__amount" onSubmit={e => { e.preventDefault(); if (millions > 0) save({ 'budget.amount': String(Math.round(millions * 1_000_000)) }) }}>
          <input className="tg-input" inputMode="decimal" placeholder="Số tiền (triệu đồng)" aria-label="Ngân sách, triệu đồng" value={amount} disabled={edit.busy} onChange={e => setAmount(e.target.value)} />
          <button type="submit" className="tg-fill__chip is-go" disabled={edit.busy || !(millions > 0)}>Lưu</button>
        </form>}
      </div></div>}
      {peek && t.qid === 'arrival' && looking && <div className="tg-fill__peek">{peek(looking)}</div>}
      {edit.error && <span className="tg-side__err" role="alert">{edit.error}</span>}
      <DeckIssues issues={edit.issues.filter(i => i.key === t.qid || i.key.startsWith(`${t.qid}.`))} />
    </div>
  })}</>
}

// Where the trip starts (from home), typed right in its row like on a map (a street address works): picking a hit saves it,
// the way to Đà Lạt (WayIn) is timed from there, through the airport or coach station when the trip flies or rides a coach.
// A hit is kept with its full address ("Cà phê A, 12 Đường B, Phường C, Biên Hòa"), not just its short name: the row shows what was picked.
const fullText = (g: GeoHit) => (g.address && !g.address.toLowerCase().startsWith(g.text.toLowerCase()) ? (g.text ? `${g.text}, ${g.address}` : g.address) : g.address || g.text)
export function OriginRow({ id, current }: { id: string; current: string | null }) {
  const [editing, setEditing] = useState(false)
  const [clicked, setClicked] = useState(false) // opened by a click: it stays open, and takes the keyboard focus
  const edit = useTripEdit(id, () => { setEditing(false); setClicked(false) })
  const row = useRef<HTMLDivElement>(null)
  const timer = useRef<number | undefined>(undefined)
  const pick = (g: GeoHit) => { void edit.run([{ kind: 'edit', target: 'origin', value: JSON.stringify({ text: fullText(g), lat: g.lat, lng: g.lng, province: g.province }) }]) }
  const touch = typeof matchMedia === 'function' && matchMedia('(hover: none)').matches
  const typing = editing || (!current && touch) // the search box shows on hover, focus or a click; a touch screen has no hover, so it shows there while nothing is set
  // A mouse resting on the row opens the search box; leaving closes it again unless the user is typing in it.
  const enter = (e: React.PointerEvent) => {
    if (e.pointerType !== 'mouse' || edit.busy) return
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => setEditing(true), 120)
  }
  const leave = (e: React.PointerEvent) => {
    if (e.pointerType !== 'mouse') return
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => {
      const el = row.current
      if (!el || clicked || el.contains(document.activeElement) || el.querySelector('input')?.value) return
      setEditing(false)
    }, 250)
  }
  return <div ref={row} className={`tg-it-transit tg-origin${typing ? ' is-typing' : ''}`} aria-busy={edit.busy || undefined} onPointerEnter={enter} onPointerLeave={leave} onFocus={() => { if (!edit.busy) setEditing(true) }}>
    <div className="tg-fill__top" {...(!current ? { role: 'button', tabIndex: 0, onClick: () => { setEditing(true); setClicked(true) }, onKeyDown: (e: React.KeyboardEvent) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setEditing(true); setClicked(true) } } } : {})}>
      <span><Icon name="home" size={16} /><b>{current || 'Bạn khởi hành từ đâu?'}</b></span>
      {edit.busy ? <small className="tg-fill__busy">Đang xếp lại lịch…</small>
        : current && <button type="button" className="tg-it-textbtn" onClick={() => { const on = !(editing && clicked); setEditing(on); setClicked(on) }}>{editing && clicked ? 'Thôi' : 'Đổi'}</button>}
    </div>
    {typing && <div className="tg-origin__in">
      <PlaceInput<GeoHit> label="Địa chỉ xuất phát" placeholder="Số nhà, đường, quận hoặc thành phố" icon="home" autoFocus={clicked} disabled={edit.busy} fetcher={geoSearch} row={(g) => ({ key: `${g.lat},${g.lng}`, icon: 'pin', name: g.text, sub: g.address })} onPick={pick} />
      <small className="tg-faint">Mình tính đường từ đây ra sân bay, bến xe hoặc chạy thẳng lên Đà Lạt.</small>
    </div>}
    {edit.error && <span className="tg-side__err" role="alert">{edit.error}</span>}
  </div>
}

// One change to the trip made from Lịch trình: each input goes to the trip's questions, then the plan is built again from the new
// answers and Lịch trình loads it. `ok` is false while the server still has something to say about an answer (`issues`).
export type Step = TurnInput | { kind: 'select'; place: string } // a place chosen in Lựa chọn's list, then the plan is built again
export function useTripEdit(id: string, onDone: () => void) {
  const { dispatch } = useTrip()
  const { reload } = usePlanning()
  const [issues, setIssues] = useState<DeckIssue[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const working = useRef(false)
  const run = useCallback(async (inputs: Step[]) => {
    if (working.current) return
    working.current = true
    setBusy(true); setError(null); setIssues([])
    let invalid = false
    try {
      for (const input of inputs) {
        if (input.kind === 'select') await mutateJourney(id, 'decision', 'act', { type: 'select', place_id: input.place })
        else await mutateJourney(id, 'decision', 'trip', input, { deck_issues: (data: { issues: DeckIssue[] }) => { invalid = true; setIssues(data.issues) } })
        if (invalid) return
      }
      const created = await mutateJourney(id, 'decision', 'advance')
      const out = created.outputs.decision as DecisionOutput
      const input = created.outputs.trip as SearchInput | undefined
      dispatch({ type: 'set', patch: { ...(input ? fromSearchInput(input) : {}), selected: out.confirmed.map(c => c.id), locked: out.confirmed.filter(c => c.role !== 'selected').map(c => c.id), planningId: created.id } })
      primePlanning(created.id, created)
      reload() // the plan keeps the journey's id: without this Lịch trình goes on showing the plan it replaced
      onDone()
    } catch { setError('Chưa lưu được thông tin. Bạn thử lại nhé.') }
    finally { working.current = false; setBusy(false) }
  }, [id, dispatch, onDone, reload])
  return { run, busy, error, issues }
}

// One empty group of the trip as a vertical list of short answers in a panel from the right: tap to choose, "Xong" to save.
export function FillSheet({ id, deck, qid, onClose }: { id: string; deck: Deck; qid: string; onClose: () => void }) {
  const one: Deck = { ...deck, tabs: deck.tabs.filter(t => t.qid === qid) }
  const edit = useTripEdit(id, onClose)
  const form = useDeckForm(one, 0)
  const { tab, selected, choose, answers } = form
  if (!tab) return null
  const normal = tab.options.filter(o => !['other', 'skip'].includes(o.id))
  const notes = edit.issues.filter(i => i.key === tab.qid || i.key.startsWith(`${tab.qid}.`))
  return <SidePanel open onClose={onClose} busy={edit.busy} kicker="Cho lịch hợp hơn" title={tab.question}
    footer={<>
      {edit.error && <span className="tg-side__err" role="alert">{edit.error}</span>}
      <button type="button" className="tg-btn tg-btn--primary" disabled={edit.busy || !Object.keys(answers).length} onClick={() => { void edit.run([{ kind: 'deck', answers, at: 'plan' }]) }}>{edit.busy ? 'Đang xếp lại lịch…' : 'Xong'} <Icon name="check" size={18} /></button>
    </>}>
    {tab.why && <p className="tg-side__ctx">{tab.why}</p>}
    {tab.multi && <p className="tg-side__hint">Chọn được nhiều ý</p>}
    <ul className="tg-side__opts" role={tab.multi ? 'group' : 'radiogroup'} aria-label={tab.header}>
      {normal.map(o => <li key={o.id}>
        <button type="button" className={selected.includes(o.id) ? 'is-on' : ''} role={tab.multi ? undefined : 'radio'} aria-checked={tab.multi ? undefined : selected.includes(o.id)} aria-pressed={tab.multi ? selected.includes(o.id) : undefined} disabled={edit.busy} title={o.description || undefined} onClick={() => choose(o)}>
          <span>{o.label}{o.prefilled && <small>mình đoán</small>}</span><i aria-hidden="true">{selected.includes(o.id) && <Icon name="check" size={14} />}</i>
        </button>
      </li>)}
    </ul>
    <ExtraInputs form={form} busy={edit.busy} />
    <DeckIssues issues={notes} />
  </SidePanel>
}

// ---- the trip's days (owner 2026-11-18): no question before planning any more, so the dates live here, laid out like the
// trip's hours (Giờ trong chuyến). Without them the plan fills day 1 before day 2 and cannot check weekday opening hours. ----
const isoDay = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const plusDays = (day: string, n: number) => { const [y, m, d] = day.split('-').map(Number); return isoDay(new Date(y, m - 1, d + n)) }
const spanOf = (a: string, b: string) => { const [y1, m1, d1] = a.split('-').map(Number), [y2, m2, d2] = b.split('-').map(Number); return Math.round((new Date(y2, m2 - 1, d2).getTime() - new Date(y1, m1 - 1, d1).getTime()) / 86_400_000) + 1 }
const dayLabel = (day: string) => { const [y, m, d] = day.split('-').map(Number); return new Date(y, m - 1, d).toLocaleDateString('vi-VN', { weekday: 'short', day: 'numeric', month: 'numeric' }) }

export function TripDates({ id, start, days }: { id: string; start: string | null; days: number | null }) {
  const savedFrom = start || '', savedTo = start && days ? plusDays(start, days - 1) : ''
  const [range, setRange] = useState<{ from: string; to: string }>({ from: savedFrom, to: savedTo })
  const [open, setOpen] = useState(false)
  const edit = useTripEdit(id, () => setOpen(false))
  useEffect(() => { setRange({ from: savedFrom, to: savedTo }) }, [savedFrom, savedTo])
  const changed = (range.from !== savedFrom || range.to !== savedTo) && !!range.from && !!range.to
  const pick = (day: string) => setRange(r => !r.from || r.to ? { from: day, to: '' } : day < r.from ? { from: day, to: '' } : { from: r.from, to: day })
  const save = () => { void edit.run([{ kind: 'edit', target: 'start_date', value: range.from }, { kind: 'edit', target: 'days', value: String(spanOf(range.from, range.to)) }]) }
  const moments = [
    { key: 'from', icon: 'calendar' as const, label: 'Ngày đến', value: range.from, note: 'Ngày đầu của chuyến' },
    { key: 'to', icon: 'home' as const, label: 'Ngày về', value: range.to, note: range.from && range.to ? `${spanOf(range.from, range.to)} ngày ở Đà Lạt` : 'Ngày cuối của chuyến' },
  ]
  // a mouse resting on the card opens the calendar (like the hour pickers); leaving it closes again unless a day is half picked
  const hover = useRef<number | undefined>(undefined)
  const enter = (e: React.PointerEvent) => { if (e.pointerType !== 'mouse' || edit.busy) return; window.clearTimeout(hover.current); hover.current = window.setTimeout(() => setOpen(true), 150) }
  const leave = (e: React.PointerEvent) => { if (e.pointerType !== 'mouse') return; window.clearTimeout(hover.current); hover.current = window.setTimeout(() => { if (!changed && (!range.from || range.to)) setOpen(false) }, 350) }
  return <section className="tg-eve__times tg-dates" aria-label="Ngày đi" onPointerEnter={enter} onPointerLeave={leave}>
    <header><Icon name="calendar" size={18} /><h3>Ngày đi</h3></header>
    <div className="tg-eve__moments">
      {moments.map(m => <div key={m.key} className={`tg-eve__moment ${changed ? 'is-edited' : ''}`}>
        <span className="tg-eve__moment-ico" aria-hidden="true"><Icon name={m.icon} size={18} /></span>
        <div>
          <span className="tg-eve__moment-label">{m.label}</span>
          <button type="button" className="tg-dates__pick" aria-expanded={open} disabled={edit.busy} onClick={() => setOpen(o => !o)}>{m.value ? dayLabel(m.value) : 'Chọn ngày'}</button>
          <small>{m.note}</small>
        </div>
      </div>)}
    </div>
    {open && <div className="tg-dates__cal"><RangeCalendar from={range.from} to={range.to} busy={edit.busy} onPick={pick} /></div>}
    <footer>
      <p className="tg-faint" role="status">{edit.busy ? 'Đang xếp lại lịch theo ngày mới…' : changed ? 'Ngày mới chưa lưu.' : start ? 'Đổi ngày thì lịch được xếp lại, kiểm giờ mở cửa theo thứ trong tuần.' : 'Chưa có ngày: mình xếp đầy ngày 1 rồi mới sang ngày 2. Chọn ngày để kiểm giờ mở cửa theo thứ.'}</p>
      {changed && <button type="button" className="tg-btn tg-btn--primary tg-btn--sm tg-eve__save" disabled={edit.busy} onClick={save}>Lưu ngày</button>}
      {edit.error && <span className="tg-side__err" role="alert">{edit.error}</span>}
    </footer>
  </section>
}
