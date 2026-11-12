import * as Dialog from '@radix-ui/react-dialog'
import { useRef, useState } from 'react'
import { enterStage, requestStageEntry, JourneyError, mutateJourney, readJourney } from '../journey'
import type { View as DecisionView } from '../pd/types'
import type { Deck, DeckIssue, Readback, ReadbackLine, TurnInput } from '../tu/types'
import { go } from './common'
import { GateAsk } from './Gate'
import { Icon } from './icons'

const MARKERS: Record<ReadbackLine['kind'], string> = { said: 'Bạn nói', guess: 'Mình đoán', default: 'Mặc định', check: 'Cần xem lại' }
const ORDER: ReadbackLine['kind'][] = ['check', 'said', 'guess', 'default']
// a line without the kind its chip already shows ("Mặc định: …"), first letter up
const tidy = (text: string) => { const t = text.replace(/^(Mặc định|Tự kiểm|Mình đoán|Bạn nói)\s*:\s*/i, ''); return t.charAt(0).toUpperCase() + t.slice(1) }

// The trip as TripGuardian has understood it, one row per thing written down, what needs a second look first.
function TripSummary({ lines }: { lines: ReadbackLine[] }) {
  const sorted = [...lines].sort((a, b) => ORDER.indexOf(a.kind) - ORDER.indexOf(b.kind))
  return <section className="tg-gt__sum" aria-label="Tóm tắt chuyến đi">
    <p className="tg-gt__sum-n"><b>{lines.length}</b> điều đã ghi nhận cho chuyến này</p>
    <ul>{sorted.map((line, i) => <li key={i} className={`is-${line.kind}`}><small>{MARKERS[line.kind]}</small><span>{tidy(line.text)}</span></li>)}</ul>
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
      if (!replace(next).length) await onAdvance()
    } catch (e) {
      if (origin !== location.pathname + location.search) return
      if (e instanceof JourneyError && e.status === 409 && e.readback) replace(e.readback, e.missing)
      else setError('Chưa lưu được thông tin. Bạn thử lại nhé.')
    } finally { working.current = false; setBusy(false) }
  }
  const edit = async () => {
    if (working.current) return
    working.current = true; setBusy(true); setError(null)
    try { await enterStage(id, 'trip'); requestStageEntry(id, 'trip'); onClose(); go('/understand') }
    catch { setError('Chưa mở được Tìm hiểu. Bạn thử lại nhé.') }
    finally { working.current = false; setBusy(false) }
  }
  return <Dialog.Root open onOpenChange={open => { if (!open && !busy) onClose() }}>
    <Dialog.Portal>
      <Dialog.Overlay className="tg-gt__veil" />
      <Dialog.Content className="tg tg-gt is-ask is-fan" aria-describedby={deck?.tabs.length ? undefined : 'gate-description'} onOpenAutoFocus={e => { const front = document.querySelector<HTMLElement>('.tg-gt__front'); if (front) { e.preventDefault(); front.focus({ preventScroll: true }) } }} onCloseAutoFocus={e => { e.preventDefault(); document.querySelector<HTMLButtonElement>('.tg-bar .tg-btn--primary')?.focus() }}>
        <div className="tg-gt__paper" />
        <Dialog.Close className="tg-gt__x" disabled={busy} aria-label="Đóng"><Icon name="x" size={16} /></Dialog.Close>
        {deck?.tabs.length ? <GateAsk key={JSON.stringify(deck)} deck={deck} busy={busy} issues={issues} error={error}
          onAnswer={answers => update({ kind: 'deck', answers })} onOther={edit} />
          : <div className="tg-gt__page tg-gt__fan">
            <Dialog.Title className="tg-gt__heading">{missing.length ? 'Cần thêm thông tin chuyến đi' : lines.length ? 'Mình sẽ xếp lịch theo những điều này' : 'Tiếp tục đến lịch trình'}</Dialog.Title>
            <Dialog.Description id="gate-description" className="tg-gt__sub">{missing.length ? 'Bạn mở Tìm hiểu để bổ sung ngày đi hoặc lưu ý sức khỏe, ăn uống nhé.' : 'Mình đã có đủ thông tin cần thiết để xếp lịch.'}</Dialog.Description>
            {!missing.length && lines.length > 0 && <TripSummary lines={lines} />}
            {error && <p className="tg-gt__err" role="alert">{error}</p>}
            <footer className="tg-gt__foot">
              <button type="button" className="tg-gt__link" disabled={busy} onClick={edit}><Icon name="edit" size={16} />Sửa trong Tìm hiểu</button>
              {!missing.length && <button type="button" className="tg-gt__go" disabled={busy} onClick={async () => { setBusy(true); try { await onAdvance() } finally { setBusy(false) } }}>Tiếp tục đến lịch trình<Icon name="arrow" size={18} /></button>}
            </footer>
          </div>}
      </Dialog.Content>
    </Dialog.Portal>
  </Dialog.Root>
}
