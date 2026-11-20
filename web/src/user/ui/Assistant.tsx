import * as Dialog from '@radix-ui/react-dialog'
import { useCallback, useEffect, useRef, useState, type CSSProperties } from 'react'
import { createPortal } from 'react-dom'
import { usePlanning } from '../planning/planning'
import { dismissNudge, openAssistant, pinAssistant, useUi } from '../store'
import { TripChat } from './TripChat'
import { onAsk as onAsk_, takeAsk } from './askAssistant'
import '../css/fixes.css'
import { BotAvatar, Icon } from './icons'
import '../css/plan-chat.css'

// THE chat (TripChat) in the panel: Lựa chọn and the home page (decision), Lịch trình (planning). The stage only picks the header line
// and where the panel may stand (pinned beside the grid on Lựa chọn; on the footer bar on Lịch trình).
export type AssistantStage = 'decision' | 'planning'

const SUB: Record<AssistantStage, string> = { decision: 'Tìm thêm, gợi ý, lọc bớt', planning: 'Hỏi, đổi chỗ, thêm nơi' }

// Lựa chọn and the home page: THE chat (TripChat), under the same header as Lịch trình's. The place sheet's "Vì sao không gợi ý?" is asked in it.
export function DecisionBody({ pinned, inDialog, home = false }: { pinned: boolean; inDialog?: boolean; home?: boolean }) {
  const [ask, setAsk] = useState<{ text: string; n: number } | null>(null)
  useEffect(() => {
    const take = () => { const r = takeAsk(); if (r) setAsk({ text: `Vì sao không gợi ý ${r.name}?`, n: Date.now() }) }
    take()
    return onAsk_(take)
  }, [])
  return (
    <>
      <TripChat ask={ask} placeholder={home ? 'Ví dụ: tháng này có lễ hội gì?' : 'Ví dụ: yên tĩnh hơn đi'}
        head={(onNew) => <Head stage="decision" pinned={pinned} inDialog={inDialog} canPin={!home} sub={home ? 'Hỏi gì về Đà Lạt cũng được' : undefined} onNew={onNew} />} />
    </>
  )
}

// Every chat panel's header: "Trò chuyện mới" (greyed while the chat is empty or answering), pin (Lựa chọn), close.
function Head({ stage, pinned, inDialog, canPin, sub, onNew }: { stage: AssistantStage; pinned: boolean; inDialog?: boolean; canPin: boolean; sub?: string; onNew: (() => void) | null }) {
  return (
    <header className="tg-asst__head">
      <BotAvatar size={40} />
      <div className="tg-asst__who">{inDialog ? <Dialog.Title>Hỏi TripGuardian</Dialog.Title> : <h2>Hỏi TripGuardian</h2>}<small>{sub ?? SUB[stage]}</small></div>
      <div className="tg-asst__ops">
        <button type="button" className="tg-asst__new" onClick={onNew ?? undefined} disabled={!onNew} title="Trò chuyện mới: chuyến đi, nơi đã chọn và lịch trình vẫn giữ nguyên"><Icon name="plus" size={16} strokeWidth={2.2} /><span>Trò chuyện mới</span></button>
        {canPin && <button type="button" className="tg-asst__ic" onClick={() => pinAssistant(!pinned)} aria-pressed={pinned} aria-label={pinned ? 'Bỏ ghim' : 'Ghim cạnh danh sách'} title={pinned ? 'Bỏ ghim' : 'Ghim cạnh danh sách'}><Icon name="thumbtack" size={18} /></button>}
        <button type="button" className="tg-asst__ic" onClick={() => openAssistant(false)} aria-label="Thu lại" title="Thu lại"><Icon name="x" size={18} /></button>
      </div>
    </header>
  )
}

// Lịch trình: THE chat too (TripChat in plan mode): typed edits go to the schedule's assistant, discovery to Trip, all in one conversation.
function PlanningBody({ inDialog, onOpenDay }: { inDialog?: boolean; onOpenDay?: (day: number) => void }) {
  const { chat } = usePlanning()
  return (
    <>
      <TripChat plan={{ chat, onOpenDay }} placeholder="Ví dụ: thêm một quán cà phê chiều"
        head={(onNew) => <Head stage="planning" pinned={false} inDialog={inDialog} canPin={false} onNew={onNew} />} />
    </>
  )
}

export function AssistantPinned() {
  return <aside className="tg-asst is-pinned" aria-label="Trợ lý"><DecisionBody pinned /></aside>
}

const BAR = {
  decision: { label: 'Hỏi TripGuardian', aria: 'Hỏi TripGuardian: tìm thêm, gợi ý hoặc lọc bớt địa điểm' },
  planning: { label: 'Hỏi TripGuardian', aria: 'Hỏi TripGuardian: hỏi, sửa hoặc thêm nơi vào lịch trình' },
} as const

// The chat stands on the bottom edge in the right corner: a slim tab (the bunny and its name). Pointing at it
// (or focusing it) unrolls a small chat upwards from the edge; clicking the tab, typing in the chat or `/` keeps it open until it is closed.
// Lựa chọn can pin the chat beside the grid instead (then this tab folds away); Lịch trình has no side column, so there it always drops.
export function AssistantFloat({ stage = 'decision', onOpenDay, pinAllowed = true, home = false }: { stage?: AssistantStage; onOpenDay?: (day: number) => void; pinAllowed?: boolean; home?: boolean }) {
  const a = useUi((u) => u.assistant)
  const bar = BAR[stage]
  const [hover, setHover] = useState(false)
  const timer = useRef(0)
  const root = useRef<HTMLDivElement>(null)
  const pinnedHere = stage === 'decision' && !home && a.open && a.pinned && pinAllowed
  const shown = !pinnedHere && (a.open || hover)
  const point = useCallback((on: boolean) => {
    clearTimeout(timer.current)
    if (on) setHover(true)
    else timer.current = window.setTimeout(() => setHover(false), 380)
  }, [])
  useEffect(() => () => clearTimeout(timer.current), [])
  // Lịch trình has a fixed footer along the bottom: the tab stands on top of it.
  const [lift, setLift] = useState(0)
  useEffect(() => {
    if (stage !== 'planning') return
    const read = () => setLift(document.querySelector<HTMLElement>('.tg-it-foot')?.offsetHeight ?? 0)
    read()
    const t = window.setInterval(read, 600)
    addEventListener('resize', read)
    return () => { clearInterval(t); removeEventListener('resize', read) }
  }, [stage])
  useEffect(() => { if (!a.open) setHover(false) }, [a.open]) // closed from inside the chat: fold up now
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement
      if (e.key === '/' && !/INPUT|TEXTAREA/.test(t.tagName) && !t.isContentEditable) { e.preventDefault(); openAssistant(true) }
    }
    addEventListener('keydown', on)
    return () => removeEventListener('keydown', on)
  }, [])
  // Opened to stay (click, `/`, the place sheet's "why not"): the cursor goes to the message box.
  useEffect(() => { if (a.open && !pinnedHere) window.setTimeout(() => document.getElementById('tg-asst-in')?.focus({ preventScroll: true }), 120) }, [a.open, pinnedHere])
  if (pinnedHere) return null
  const keep = () => { if (!a.open) openAssistant(true) }
  return createPortal(
    <div
      ref={root}
      className={`tg tg-drop ${shown ? 'is-open' : ''} ${home ? 'is-home' : ''}`}
      style={lift ? { '--tg-drop-bottom': `${lift}px` } as CSSProperties : undefined}
      onPointerEnter={() => point(true)}
      onPointerLeave={() => point(false)}
      onFocus={() => setHover(true)}
      onBlur={(e) => { if (!a.open && !e.currentTarget.contains(e.relatedTarget as Node | null)) point(false) }}
      onKeyDown={(e) => { if (e.key === 'Escape' && shown) { openAssistant(false); setHover(false) } }}
    >
      <button type="button" className="tg-drop__bar" aria-expanded={shown} aria-controls="tg-drop-panel" aria-keyshortcuts="/" aria-label={bar.aria} title={`${bar.aria}  ( / )`} onClick={() => { if (a.open) { openAssistant(false); setHover(false) } else openAssistant(true) }}>
        <BotAvatar size={28} />
        <span className="tg-drop__label">{bar.label}</span>
        <Icon name="chevronUp" size={16} strokeWidth={2.4} />
        {a.nudge && !shown && <i className="tg-drop__dot" aria-hidden="true" />}
      </button>
      {a.nudge && !shown && <div className="tg-nudge tg-drop__nudge" role="status"><span>{a.nudge}</span><button type="button" className="tg-link" onClick={() => openAssistant(true)}>Xem</button><button type="button" className="tg-icon-btn" onClick={dismissNudge} aria-label="Tắt gợi ý"><Icon name="x" size={16} /></button></div>}
      <div className="tg-drop__body" inert={!shown}>
        <div className="tg-drop__clip">
          <section id="tg-drop-panel" className="tg-asst tg-drop__panel" aria-label="Hỏi TripGuardian" onFocusCapture={keep} onPointerDownCapture={keep}>
            {stage === 'planning' ? <PlanningBody onOpenDay={onOpenDay} /> : <DecisionBody pinned={false} home={home} />}
          </section>
        </div>
      </div>
    </div>,
    document.body,
  )
}
