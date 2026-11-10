import * as Dialog from '@radix-ui/react-dialog'
import { useEffect, useMemo, useRef, useState, useSyncExternalStore, type CSSProperties } from 'react'
import { info } from '../lib'
import { whyNot } from '../pd/api'
import { useDecision } from '../pd/decision'
import { usePlanning } from '../planning/planning'
import type { ChangedDay } from '../planning/types'
import { clearMsgs, editMsg, dismissNudge, openAssistant, pinAssistant, pushMsg, toggleSaved, toast, useUi } from '../store'
import { mutateJourney } from '../journey'
import { useTrip } from '../trip'
import { searchPlaces } from '../tu/api'
import type { ChatPlaces } from '../tu/types'
import { PlaceStage } from '../screens/understand/Places'
import { onAsk as onAsk_, takeAsk } from './askAssistant'
import { PlacePhoto } from './common'
import '../css/fixes.css'
import { openPlace } from './PlaceSheet'
import { Icon } from './icons'
import '../css/plan-chat.css'

// The assistant of each stage keeps its own conversation: the chat log is one list, a message belongs to the stage that sent it
// (a message nobody tagged, such as the place sheet's "why not", is Lựa chọn's).
export type AssistantStage = 'decision' | 'planning'
const tag = (id: number, stage: AssistantStage) => { editMsg(id, { stage }); return id }

// The assistant's face: a soft, slowly turning orb (CSS only).
function Orb({ size = 36 }: { size?: number }) {
  return <span className="tg-orb" style={{ '--orb': `${size}px` } as CSSProperties} aria-hidden="true"><i /></span>
}
const HELLO: Record<AssistantStage, string> = { decision: 'Bạn muốn lọc thế nào?', planning: 'Bạn muốn đổi gì trong lịch?' }
const SUB: Record<AssistantStage, string> = { decision: 'Lọc nơi theo ý bạn', planning: 'Hỏi hoặc sửa lịch theo ý bạn' }

const PLAN_CHIPS = ['Dời một chỗ sang ngày khác', 'Thêm một chỗ ăn trưa', 'Vì sao xếp ngày 1 như vậy?', 'Ngày nào đi lại nhiều nhất?']
const CHIPS = ['Yên tĩnh hơn', 'Ít di chuyển hơn', 'Thêm một chỗ ăn trưa', 'Vì sao không gợi ý Langbiang?']
// "vì sao không gợi ý X" is answered from the data (why-not), not by the agent.
const WHY_NOT = /(?:vì sao|tại sao|sao)\s+(?:không|chưa)\s+(?:gợi ý|thấy|có)\s+(.+?)\s*\??$/i

// The place cards of a reply (the backend's `places` event), by message: the chat log itself keeps text and ids only.
const cardsOf = new Map<number, ChatPlaces>()
const cardSubs = new Set<() => void>()
let cardsVersion = 0
function setCards(msg: number, d: ChatPlaces) {
  cardsOf.set(msg, d)
  cardsVersion++
  cardSubs.forEach((l) => l())
}
// The days a Lịch trình turn changed (the backend's `diff.days`), by message.
const daysOf = new Map<number, ChangedDay[]>()
function setDays(msg: number, d: ChangedDay[]) {
  daysOf.set(msg, d)
  cardsVersion++
  cardSubs.forEach((l) => l())
}
function useCards() {
  useSyncExternalStore((l) => { cardSubs.add(l); return () => { cardSubs.delete(l) } }, () => cardsVersion)
  return cardsOf
}
function useCardsVersion() {
  return useSyncExternalStore((l) => { cardSubs.add(l); return () => { cardSubs.delete(l) } }, () => cardsVersion)
}

function useDecisionSend() {
  const { say, view, act } = useDecision()
  const { trip } = useTrip()
  const send = async (text: string) => {
    tag(pushMsg({ role: 'user', text }), 'decision')
    const why = WHY_NOT.exec(text)
    if (why && trip.decisionId) {
      const bot = tag(pushMsg({ role: 'bot', text: 'Mình tra trong dữ liệu…' }), 'decision')
      try {
        const hits = await searchPlaces(why[1])
        if (!hits.length) return editMsg(bot, { text: `Mình không thấy "${why[1]}" trong dữ liệu Đà Lạt của mình, nên không gợi ý được. Mình không đoán nơi khi chưa có dữ liệu.` })
        await explain(bot, hits[0].id, hits[0].name)
      } catch {
        editMsg(bot, { text: 'Chưa tra được, bạn thử lại sau nhé.' })
      }
      return
    }
    const bot = tag(pushMsg({ role: 'bot', text: '' }), 'decision')
    // The grid shows what changed; places a tool returned and the reply names come as cards.
    let last = ''
    await say(text, (soFar) => { last = soFar; editMsg(bot, { text: soFar }) }, (d) => { setCards(bot, d); editMsg(bot, { text: last }) })
  }
  // Why a place is not in the list, from the data (the place sheet asks this by id, the typed question by name).
  const explain = async (bot: number, id: string, fallback: string) => {
    const r = await whyNot(trip.decisionId!, id)
    const shown = view?.groups.some((g) => g.cards.some((c) => c.id === id))
    const name = r.name ?? fallback
    editMsg(bot, {
      text: shown ? `${name} đang có trong danh sách gợi ý.` : r.listed ? `${name}: ${r.reasons.join(' ')}.` : r.reasons.length ? `${name}: ${r.reasons.join(' ')} Mình không tự bỏ giới hạn; muốn thì bạn nới ở vé chuyến, mình nói rõ cái giá.` : `${name} chưa có lý do rõ để loại; có thể nó chỉ xếp sau những nơi hợp hơn.`,
      places: [id],
    })
  }
  const askWhyNot = async (id: string, name: string) => {
    if (!trip.decisionId) return
    tag(pushMsg({ role: 'user', text: `Vì sao không gợi ý ${name}?` }), 'decision')
    const bot = tag(pushMsg({ role: 'bot', text: 'Mình tra trong dữ liệu…' }), 'decision')
    try { await explain(bot, id, name) } catch { editMsg(bot, { text: 'Chưa tra được, bạn thử lại sau nhé.' }) }
  }
  const like = (id: string) => { act({ type: 'wishlist', place_id: id }) }
  return Object.assign(send, { askWhyNot, like })
}

// Lịch trình: one typed message goes to the planning assistant; the plan it leaves is shown by the screen itself (the provider
// accepts the new version), so the chat only carries the reply, the place cards and the days that changed.
function usePlanningSend() {
  const { say, busy } = usePlanning()
  const send = async (text: string) => {
    tag(pushMsg({ role: 'user', text }), 'planning')
    const bot = tag(pushMsg({ role: 'bot', text: '' }), 'planning')
    let last = ''
    const diff = await say(text, (soFar) => { last = soFar; editMsg(bot, { text: soFar }) }, (d) => { setCards(bot, d); editMsg(bot, { text: last }) })
    if (diff?.days?.length) setDays(bot, diff.days)
    if (!diff && !last) editMsg(bot, { text: 'Chưa trả lời được lượt này, lịch giữ nguyên. Bạn thử lại nhé.' })
  }
  return Object.assign(send, { busy })
}

interface BodyProps {
  stage: AssistantStage
  pinned: boolean
  inDialog?: boolean
  busy: boolean
  send: (text: string) => void | Promise<void>
  chips: string[]
  intro: string
  placeholder: string
  onLike: (id: string) => void
  canPin: boolean
  onOpenDay?: (day: number) => void
  onAsk?: (id: string, name: string) => void
}

export function Body({ stage, pinned, inDialog = false, busy: stageBusy, send, chips, intro, placeholder, onLike, canPin, onOpenDay, onAsk }: BodyProps) {
  const [sending, setSending] = useState(false)
  const sendingRef = useRef(false)
  const busy = stageBusy || sending
  const run = async (task: () => void | Promise<void>) => {
    if (sendingRef.current || resettingRef.current || stageBusy) return
    sendingRef.current = true
    setSending(true)
    try { await task() } finally { sendingRef.current = false; setSending(false) }
  }
  const all = useUi((u) => u.assistant.msgs)
  const msgs = useMemo(() => all.filter((m) => (m.stage ?? 'decision') === stage), [all, stage])
  const { trip } = useTrip()
  const [resetting, setResetting] = useState(false)
  const resettingRef = useRef(false)
  const newChat = async () => {
    const id = stage === 'decision' ? trip.decisionId : trip.planningId
    if (!id || busy || sendingRef.current || resettingRef.current || !msgs.length) return
    resettingRef.current = true
    setResetting(true)
    try {
      await mutateJourney(id, stage, 'new_chat', { messages: msgs.map(({ role, text }) => ({ role, text })) })
      clearMsgs(stage)
      for (const m of msgs) { cardsOf.delete(m.id); daysOf.delete(m.id) }
      setText('')
    } catch { toast('Chưa mở được cuộc trò chuyện mới, bạn thử lại nhé.') }
    finally { resettingRef.current = false; setResetting(false) }
  }
  const cards = useCards()
  const shown = useCardsVersion() // the place cards and changed days of a reply land after its text
  const [text, setText] = useState('')
  const endRef = useRef<HTMLDivElement>(null)
  useEffect(() => { endRef.current?.scrollIntoView({ block: 'end' }) }, [msgs, shown])
  // A place sheet asked "why not" about a place: answer it as soon as this chat is open.
  const ask = useRef(onAsk)
  ask.current = onAsk ? (id, name) => run(() => onAsk(id, name)) : undefined
  useEffect(() => {
    if (!ask.current) return
    const take = () => { const r = takeAsk(); if (r) ask.current?.(r.id, r.name) }
    take()
    return onAsk_(take)
  }, [])
  const submit = (t: string) => {
    if (!t.trim() || busy || resettingRef.current) return
    void run(() => send(t.trim()))
    setText('')
  }
  return (
    <>
      <header className="tg-asst__head">
        <Orb size={36} />
        <div className="tg-asst__who">{inDialog ? <Dialog.Title>Hỏi TripGuardian</Dialog.Title> : <h2>Hỏi TripGuardian</h2>}<small>{SUB[stage]}</small></div>
        <div className="tg-asst__ops">
          <button type="button" className="tg-link" disabled={busy || resetting || !msgs.length} onClick={() => { void newChat() }}>Cuộc trò chuyện mới</button>
          {canPin && <button type="button" className="tg-link" onClick={() => pinAssistant(!pinned)} aria-pressed={pinned}>{pinned ? 'Bỏ ghim' : 'Ghim'}</button>}
          <button type="button" className="tg-icon-btn" onClick={() => openAssistant(false)} aria-label="Thu lại"><Icon name="x" size={18} /></button>
        </div>
      </header>
      <div className="tg-asst__log" role="log" aria-live="polite">
        {msgs.length === 0 && <div className="tg-asst__hello">
          <Orb size={68} />
          <h3>{HELLO[stage]}</h3>
          <p className="tg-asst__intro">{intro}</p>
          <div className="tg-asst__quick" role="group" aria-label="Gợi ý câu hỏi">{chips.map((c) => <button key={c} type="button" className="tg-qchip" disabled={busy} onClick={() => submit(c)}>{c}</button>)}</div>
        </div>}
        {msgs.map((m) => (
          <div key={m.id} className={`tg-msg is-${m.role}`}>
            <p>{m.text || (m.role === 'bot' ? <span className="tg-typing" role="status" aria-label="Đang trả lời"><i /><i /><i /></span> : '')}</p>
            {cards.get(m.id) && <PlaceStage row={cards.get(m.id)!} busy={busy} autoOpen={stage === 'decision'} onLike={(id) => onLike(id)} />}
            {daysOf.get(m.id) && onOpenDay && (
              <ul className="tg-msg__days" aria-label="Các ngày đã đổi">
                {daysOf.get(m.id)!.map((d) => (
                  <li key={d.day}>
                    <button type="button" className="tg-chday" onClick={() => onOpenDay(d.day)}>
                      <span className="tg-chday__head"><b>Ngày {d.day} đã đổi</b><span>Xem ngày này</span></span>
                      {d.stops.length ? <ol>{d.stops.map((st) => <li key={st.id}><time>{st.start}</time><span>{st.name}</span></li>)}</ol> : <span className="tg-chday__empty">Ngày này giờ không còn nơi nào.</span>}
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {m.places && !cards.get(m.id) && <div className="tg-msg__chips">{m.places.map((id) => <button key={id} type="button" className="tg-pchip" onClick={() => openPlace(id)}>{!!info(id)?.photos?.length && <PlacePhoto id={id} className="tg-pchip__ph" />}{info(id)?.name ?? 'Xem nơi này'}</button>)}</div>}
          </div>
        ))}
        <div ref={endRef} />
      </div>
      {msgs.length > 0 && <div className="tg-asst__chips" role="group" aria-label="Gợi ý câu hỏi">{chips.map((c) => <button key={c} type="button" className="tg-chip" disabled={busy} onClick={() => submit(c)}>{c}</button>)}</div>}
      <form className={`tg-asst__in ${busy ? 'is-busy' : ''}`} onSubmit={(e) => { e.preventDefault(); submit(text) }}>
        <label className="tg-sr" htmlFor="tg-asst-in">Nói với mình</label>
        <input id="tg-asst-in" className="tg-line-input" value={text} maxLength={1000} onChange={(e) => setText(e.target.value)} placeholder={placeholder} autoComplete="off" />
        <button type="submit" className="tg-send" disabled={busy || !text.trim()} aria-label="Gửi"><Icon name="send" size={18} /></button>
      </form>
    </>
  )
}

function DecisionBody({ pinned, inDialog }: { pinned: boolean; inDialog?: boolean }) {
  const { busy } = useDecision()
  const send = useDecisionSend()
  return <Body stage="decision" pinned={pinned} inDialog={inDialog} busy={busy} send={send} chips={CHIPS} onLike={send.like} canPin onAsk={send.askWhyNot}
    intro='Nói điều bạn muốn đổi trong danh sách, ví dụ "bỏ mấy chỗ đông đi" hay "thêm một quán ăn tối gần hồ". Mọi thay đổi hiện ngay trên lưới và hoàn tác được.'
    placeholder="Ví dụ: yên tĩnh hơn đi" />
}

// The heart on a place card in Lịch trình saves the place to the user's list, the same list the place sheet's heart uses.
function PlanningBody({ inDialog, onOpenDay }: { inDialog?: boolean; onOpenDay?: (day: number) => void }) {
  const send = usePlanningSend()
  return <Body stage="planning" pinned={false} inDialog={inDialog} busy={send.busy} send={send} chips={PLAN_CHIPS} canPin={false} onLike={(id) => { void toggleSaved(id) }} onOpenDay={onOpenDay}
    intro='Hỏi về lịch này hoặc nói điều bạn muốn đổi, ví dụ "dời chỗ này sang ngày 2" hay "vì sao ghé hồ trước?". Một lượt đổi lịch hoàn tác được bằng một lần bấm.'
    placeholder="Ví dụ: thêm một quán cà phê chiều" />
}

export function AssistantPinned() {
  return <aside className="tg-asst is-pinned" aria-label="Trợ lý"><DecisionBody pinned /></aside>
}

const FAB = {
  decision: { label: 'Hỏi TripGuardian · lọc nơi theo ý bạn', aria: 'Hỏi TripGuardian: lọc địa điểm theo ý bạn' },
  planning: { label: 'Hỏi TripGuardian · sửa lịch theo ý bạn', aria: 'Hỏi TripGuardian: hỏi hoặc sửa lịch trình theo ý bạn' },
} as const

// Lựa chọn pins the chat beside the grid; Lịch trình has no side column, so there it always floats.
export function AssistantFloat({ stage = 'decision', onOpenDay }: { stage?: AssistantStage; onOpenDay?: (day: number) => void }) {
  const a = useUi((u) => u.assistant)
  const fab = FAB[stage]
  const float = stage === 'planning' || !a.pinned
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement
      if (e.key === '/' && !/INPUT|TEXTAREA/.test(t.tagName) && !t.isContentEditable) { e.preventDefault(); openAssistant(true) }
    }
    addEventListener('keydown', on)
    return () => removeEventListener('keydown', on)
  }, [])
  return (
    <>
      {!a.open && (
        <div className="tg-asst-fab">
          {a.nudge && <div className="tg-nudge" role="status"><span>{a.nudge}</span><button type="button" className="tg-link" onClick={() => openAssistant(true)}>Xem</button><button type="button" className="tg-icon-btn" onClick={dismissNudge} aria-label="Tắt gợi ý"><Icon name="x" size={16} /></button></div>}
          <button type="button" className="tg-fab" onClick={() => openAssistant(true)} aria-keyshortcuts="/" aria-label={fab.aria} title={`${fab.aria}  ( / )`}><Orb size={40} /><Icon name="sparkle" size={18} /><span className="tg-fab__label">{fab.label}</span>{a.nudge && <i className="tg-fab__dot" aria-hidden="true" />}</button>
        </div>
      )}
      {a.open && float && (
        <Dialog.Root open modal={false} onOpenChange={(o) => !o && openAssistant(false)}>
          <Dialog.Portal>
            <Dialog.Content className="tg tg-asst is-float" aria-describedby={undefined} onInteractOutside={(e) => e.preventDefault()} onOpenAutoFocus={(e) => { e.preventDefault(); document.getElementById('tg-asst-in')?.focus() }}>
              {stage === 'planning' ? <PlanningBody inDialog onOpenDay={onOpenDay} /> : <DecisionBody pinned={false} inDialog />}
            </Dialog.Content>
          </Dialog.Portal>
        </Dialog.Root>
      )}
    </>
  )
}
