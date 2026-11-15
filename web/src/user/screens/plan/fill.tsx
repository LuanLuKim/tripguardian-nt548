import { useCallback, useEffect, useRef, useState } from 'react'
import { mutateJourney, readJourney } from '../../journey'
import { primePlanning } from '../../planning/api'
import { usePlanning } from '../../planning/planning'
import type { DecisionOutput } from '../../pd/types'
import { useTrip } from '../../trip'
import { fromSearchInput } from '../../tu/adapter'
import { geoSearch } from '../../tu/api'
import type { Deck, DeckIssue, GeoHit, Readback, SearchInput, TurnInput } from '../../tu/types'
import { Icon } from '../../ui/icons'
import { PlaceInput } from '../../ui/PlaceInput'
import { DeckIssues, ExtraInputs, TAB_ICON, useDeckForm } from '../understand/Deck'
import { SidePanel } from './panels'

// The optional groups of the trip (who goes, how they move, pace, budget) that are still empty. Lịch trình runs without them;
// the user fills one in here when they want the plan to fit it, and the plan is built again from the new answer.

export function useFill(id: string | null, plan: string | null) {
  const [deck, setDeck] = useState<Deck | null>(null)
  const [open, setOpen] = useState<string | null>(null)
  useEffect(() => {
    if (!id) return
    let live = true
    readJourney<Readback>(id, 'trip/readback').then(rb => { if (live) setDeck(rb.fill ?? null) }, () => { if (live) setDeck(null) })
    return () => { live = false }
  }, [id, plan]) // the plan is built again after an answer: read what is still empty
  return { deck, open, setOpen }
}

// `only` / `except`: the way to the city is asked in its own row (Đến Đà Lạt), the rest under Thông tin chuyến.
export function FillRows({ deck, onOpen, only, except }: { deck: Deck; onOpen: (qid: string) => void; only?: string; except?: string }) {
  return <>{deck.tabs.filter(t => (!only || t.qid === only) && t.qid !== except).map(t => <div className="tg-it-transit" key={t.qid}>
    <span><Icon name={TAB_ICON[t.qid] ?? 'info'} size={16} /><b>{t.header}</b></span>
    <button type="button" className="tg-it-textbtn" onClick={() => onOpen(t.qid)}>{t.qid === 'arrival' ? 'Chọn' : 'Thêm'}</button>
  </div>)}</>
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

// Where the trip starts (from home): a place typed like on a map. It only times the way to Đà Lạt; how the trip gets there is
// asked under Đến Đà Lạt (FillSheet, `arrival`).
export function RouteSheet({ id, current, onClose }: { id: string; current: string | null; onClose: () => void }) {
  const edit = useTripEdit(id, onClose)
  const [origin, setOrigin] = useState<GeoHit | null>(null)
  const save = () => {
    if (!origin) return
    void edit.run([{ kind: 'edit', target: 'origin', value: JSON.stringify({ text: origin.text, lat: origin.lat, lng: origin.lng, province: origin.province }) }])
  }
  return <SidePanel open onClose={onClose} busy={edit.busy} kicker="Điểm xuất phát" title="Bạn khởi hành từ đâu?"
    footer={<>
      {edit.error && <span className="tg-side__err" role="alert">{edit.error}</span>}
      <button type="button" className="tg-btn tg-btn--primary" disabled={edit.busy || !origin} onClick={save}>{edit.busy ? 'Đang xếp lại lịch…' : 'Xong'} <Icon name="check" size={18} /></button>
    </>}>
    <section className="tg-side__field">
      <p className="tg-side__ctx">Nơi bạn khởi hành từ nhà, ví dụ TP. Hồ Chí Minh hoặc một địa chỉ. Mình tính đường và giờ tới Đà Lạt từ đây.</p>
      {current && !origin && <small className="tg-side__picked"><Icon name="home" size={14} /> Hiện tại: {current}</small>}
      <PlaceInput<GeoHit> label="Nơi bạn khởi hành" placeholder="Thành phố, quận hoặc địa chỉ" icon="home" autoFocus disabled={edit.busy} fetcher={geoSearch} row={(g) => ({ key: `${g.lat},${g.lng}`, icon: 'pin', name: g.text, sub: g.address })} onPick={setOrigin} />
      {origin && <small className="tg-side__picked"><Icon name="check" size={14} /> Xuất phát từ {origin.text}</small>}
    </section>
  </SidePanel>
}
