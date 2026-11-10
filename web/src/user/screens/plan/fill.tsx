import * as Dialog from '@radix-ui/react-dialog'
import { useCallback, useEffect, useRef, useState } from 'react'
import { enterStage, mutateJourney, readJourney, requestStageEntry } from '../../journey'
import { primePlanning } from '../../planning/api'
import type { DecisionOutput } from '../../pd/types'
import { useTrip } from '../../trip'
import type { Deck, DeckIssue, Readback } from '../../tu/types'
import { go } from '../../ui/common'
import { GateAsk } from '../../ui/Gate'
import { Icon } from '../../ui/icons'
import { TAB_ICON } from '../understand/Deck'

// The optional groups of the trip (who goes, how they move, pace, budget) that are still empty. Lịch trình runs without them;
// the user fills one in here when they want the plan to fit it, and the plan is built again from the new answer.
const COPY = { kicker: 'Cho lịch hợp hơn', heading: 'Thêm một thông tin cho chuyến đi', sub: 'Trả lời xong, mình xếp lại lịch theo điều này.' }

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

export function FillRows({ deck, onOpen }: { deck: Deck; onOpen: (qid: string) => void }) {
  return <>{deck.tabs.map(t => <div className="tg-it-transit" key={t.qid}>
    <span><Icon name={TAB_ICON[t.qid] ?? 'info'} size={16} /><b>{t.header}</b></span>
    <button type="button" className="tg-it-textbtn" onClick={() => onOpen(t.qid)}>Thêm</button>
  </div>)}</>
}

export function FillSheet({ id, deck, qid, onClose }: { id: string; deck: Deck; qid: string; onClose: () => void }) {
  const { dispatch } = useTrip()
  const [issues, setIssues] = useState<DeckIssue[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const working = useRef(false)
  const one = { ...deck, tabs: deck.tabs.filter(t => t.qid === qid) }
  const answer = useCallback(async (answers: Record<string, string | string[]>) => {
    if (working.current) return
    working.current = true
    setBusy(true); setError(null); setIssues([])
    let invalid = false
    try {
      await mutateJourney(id, 'decision', 'trip', { kind: 'deck', answers, at: 'plan' }, { deck_issues: (data: { issues: DeckIssue[] }) => { invalid = true; setIssues(data.issues) } })
      if (invalid) return
      // The answer changes what the plan is built from: build it again and let Lịch trình load the new one.
      const created = await mutateJourney(id, 'decision', 'advance')
      const out = created.outputs.decision as DecisionOutput
      dispatch({ type: 'set', patch: { selected: out.confirmed.map(c => c.id), locked: out.confirmed.filter(c => c.role !== 'selected').map(c => c.id), planningId: created.id } })
      primePlanning(created.id, created)
      onClose()
    } catch { setError('Chưa lưu được thông tin. Bạn thử lại nhé.') }
    finally { working.current = false; setBusy(false) }
  }, [id, dispatch, onClose])
  const edit = async () => {
    if (working.current) return
    working.current = true; setBusy(true)
    try { await enterStage(id, 'trip'); requestStageEntry(id, 'trip'); onClose(); go('/understand') }
    catch { setError('Chưa mở được Tìm hiểu. Bạn thử lại nhé.') }
    finally { working.current = false; setBusy(false) }
  }
  return <Dialog.Root open onOpenChange={open => { if (!open && !busy) onClose() }}>
    <Dialog.Portal>
      <Dialog.Overlay className="tg-gt__veil" />
      <Dialog.Content className="tg tg-gt is-ask is-fan">
        <div className="tg-gt__paper" />
        <Dialog.Close className="tg-gt__x" disabled={busy} aria-label="Đóng"><Icon name="x" size={16} /></Dialog.Close>
        <GateAsk deck={one} busy={busy} issues={issues} error={error} copy={COPY} onAnswer={answer} onOther={edit} />
      </Dialog.Content>
    </Dialog.Portal>
  </Dialog.Root>
}
