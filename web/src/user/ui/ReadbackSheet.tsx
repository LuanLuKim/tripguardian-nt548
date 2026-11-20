import * as Dialog from '@radix-ui/react-dialog'
import { useEffect, useRef, useState } from 'react'
import { JourneyError, mutateJourney, readJourney } from '../journey'
import type { View as DecisionView } from '../pd/types'
import { getSession } from '../tu/api'
import type { Deck, DeckIssue, Readback, ReadbackLine, TurnInput, Understanding } from '../tu/types'
import { openAssistant } from '../store'
import { GateAsk } from './Gate'
import { Icon } from './icons'
import { ticketEditors } from './Ticket'

const TITLES: Record<ReadbackLine['tab'], string> = { trip: 'Ngày đi', companions: 'Đi với', mobility: 'Phương tiện', care: 'Lưu ý', pace: 'Nhịp độ', budget: 'Ngân sách', lodging: 'Nơi ở', more: 'Thêm' }
const ORDER: ReadbackLine['tab'][] = ['trip', 'companions', 'mobility', 'lodging', 'pace', 'budget', 'care', 'more']
// the line as the trip says it: no "Mặc định:" / "Mình đoán:" lead (where a fact came from is not the person's business here)
const tidy = (text: string) => { const t = text.replace(/^(Mặc định|Tự kiểm|Mình đoán|Bạn nói)\s*:\s*/i, ''); return t.charAt(0).toUpperCase() + t.slice(1) }

// The trip summary (owner 2026-11-18): one row per topic, what the plan will be built on, plainly; no "bạn nói / mình đoán /
// mặc định" tags. A line that needs a second look carries a small warning sign. Each row opens the trip ticket's editor.
function TripSummary({ lines, u, busy, onEdit }: { lines: ReadbackLine[]; u: Understanding | null; busy: boolean; onEdit: (target: string, value: string | null) => void }) {
  const groups = ORDER.map(tab => ({ tab, lines: lines.filter(l => l.tab === tab) })).filter(g => g.lines.length)
  const [open, setOpen] = useState<string | null>(null)
  const editors = u ? ticketEditors(u, onEdit) : null
  return <section className="tg-gt__sum" aria-label="Tóm tắt chuyến đi">
    <dl>{groups.map(({ tab, lines: rows }) => {
      const editor = editors && tab !== 'care' && tab !== 'more' ? editors[tab] : null
      const editing = open === tab
      return <div key={tab} className={`${rows.some(l => l.kind === 'check') ? 'is-check' : ''} ${editing ? 'is-editing' : ''}`}>
        <dt>{TITLES[tab]}</dt>
        <dd>{rows.map((l, k) => <span key={k}>{l.kind === 'check' && <Icon name="warn" size={14} aria-label="Cần xem lại" />}{tidy(l.text)}</span>)}</dd>
        {editor && <button type="button" className="tg-gt__sum-edit" aria-expanded={editing} disabled={busy} onClick={() => setOpen(editing ? null : tab)}>{editing ? <><Icon name="check" size={14} />Xong</> : <><Icon name="edit" size={14} />Sửa</>}</button>}
        {editor && editing && <fieldset className="tg-gt__sum-editor" disabled={busy}>{editor}</fieldset>}
      </div>
    })}</dl>
  </section>
}

export function ReadbackSheet({ id, initial, missing: initialMissing, onClose, onAdvance, onView }: {
  id: string; initial: Readback; missing: string[]
  onClose: () => void; onAdvance: () => Promise<boolean>; onView: (view: DecisionView) => void
}) {
  const [missing, setMissing] = useState(initial.missing ?? initialMissing)
  const [deck, setDeck] = useState<Deck | null>(initial.deck ?? null)
  const [lines, setLines] = useState<ReadbackLine[]>(initial.lines ?? [])
  const [issues, setIssues] = useState<DeckIssue[]>([])
  const [busy, setBusy] = useState(false)
  const working = useRef(false)
  const [error, setError] = useState<string | null>(null)
  const [u, setU] = useState<Understanding | null>(null)
  const loadU = () => { getSession(id).then(v => setU(v.understanding), () => {}) }
  useEffect(() => { loadU() }, [id]) // eslint-disable-line react-hooks/exhaustive-deps
  const replace = (next: Readback, needed = next.missing ?? []) => {
    setMissing(needed)
    setLines(next.lines ?? [])
    setDeck(needed.length ? next.deck ?? null : null)
    return needed
  }
  const update = async (input: TurnInput) => {
    if (working.current) return
    working.current = true
    setBusy(true); setError(null); setIssues([])
    const origin = location.pathname + location.search
    try {
      const result = await mutateJourney(id, 'decision', 'trip', input, {
        deck_issues: (data: { issues: DeckIssue[] }) => setIssues(data.issues),
      })
      if (origin !== location.pathname + location.search) return
      const resultView = (result.result as { view?: DecisionView })?.view
      if (resultView) onView(resultView)
      // The gate read is authoritative even when incomplete display groups have no understanding.readback.
      const next = await readJourney<Readback>(id, 'trip/readback')
      if (origin !== location.pathname + location.search) return
      replace(next) // answering never moves on by itself: the summary shows, and the user presses "Tiếp tục đến lịch trình"
      loadU()
    } catch (e) {
      if (origin !== location.pathname + location.search) return
      if (e instanceof JourneyError && e.status === 409 && e.readback) replace(e.readback, e.missing)
      else setError('Chưa lưu được thông tin. Bạn thử lại nhé.')
    } finally { working.current = false; setBusy(false) }
  }
  const edit = async () => {
    if (working.current) return
    working.current = true; setBusy(true); setError(null)
    // The chat is beside the lists: what is wrong is said there, the journey stays on Lựa chọn.
    try { onClose(); openAssistant(true) }
    finally { working.current = false; setBusy(false) }
  }
  return <Dialog.Root open onOpenChange={open => { if (!open && !busy) onClose() }}>
    <Dialog.Portal>
      <Dialog.Overlay className="tg-gt__veil" />
      <Dialog.Content className="tg tg-gt is-ask is-fan" aria-describedby={deck?.tabs.length ? undefined : 'gate-description'} onOpenAutoFocus={e => { const front = document.querySelector<HTMLElement>('.tg-gt__front'); if (front) { e.preventDefault(); front.focus({ preventScroll: true }) } }} onCloseAutoFocus={e => { e.preventDefault(); document.querySelector<HTMLButtonElement>('.tg-bar .tg-btn--primary')?.focus() }}>
        <div className="tg-gt__paper" />
        <Dialog.Close className="tg-gt__x" disabled={busy} aria-label="Đóng"><Icon name="x" size={16} /></Dialog.Close>
        {deck?.tabs.length ? <GateAsk key={JSON.stringify(deck)} deck={deck} busy={busy} issues={issues} error={error}
          onAnswer={(answers, text) => update({ kind: 'deck', answers, ...(text ? { text } : {}) })} onOther={edit} />
          : <div className="tg-gt__page tg-gt__fan">
            <Dialog.Title className="tg-gt__heading">{missing.length ? 'Cần thêm thông tin chuyến đi' : lines.length ? 'Tóm tắt chuyến đi' : 'Tiếp tục đến lịch trình'}</Dialog.Title>
            <Dialog.Description id="gate-description" className="tg-gt__sub">{missing.length ? 'Bạn mở Tìm hiểu để bổ sung ngày đi hoặc lưu ý sức khỏe, ăn uống nhé.' : 'Lịch trình được xếp theo những điều này. Bấm Sửa ở dòng muốn đổi.'}</Dialog.Description>
            {!missing.length && lines.length > 0 && <TripSummary lines={lines} u={u} busy={busy} onEdit={(target, value) => { void update({ kind: 'edit', target, value }) }} />}
            {error && <p className="tg-gt__err" role="alert">{error}</p>}
            <footer className="tg-gt__foot">
              {missing.length > 0 ? <button type="button" className="tg-gt__link" disabled={busy} onClick={edit}><Icon name="edit" size={16} />Mở Tìm hiểu</button> : <span />}
              {!missing.length && <button type="button" className="tg-gt__go" disabled={busy} onClick={async () => { setBusy(true); try { await onAdvance() } finally { setBusy(false) } }}>Tiếp tục đến lịch trình<Icon name="arrow" size={18} /></button>}
            </footer>
          </div>}
      </Dialog.Content>
    </Dialog.Portal>
  </Dialog.Root>
}
