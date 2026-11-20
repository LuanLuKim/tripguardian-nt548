import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { useAccount } from '../account'
import { track } from '../events'
import { JourneyError, mutateJourney } from '../journey'
import { useDecision } from '../pd/decision'
import { AskDock } from '../screens/understand/Ask'
import { shrink } from '../screens/understand/Composer'
import { botMsg, Turn, type Msg } from '../screens/understand/Turn'
import { resumeTrip, startTrip, useStarting } from '../startTrip'
import { openAssistant, toggleSaved } from '../store'
import type { ChangedDay } from '../planning/types'
import { TagEnvContext } from '../tags/env'
import { useTrip } from '../trip'
import { getSession } from '../tu/api'
import type { Card, Deck, DeckAnswers, Handlers, TurnInput, View } from '../tu/types'
import { Icon } from './icons'

// THE chat of TripGuardian (docs/Role_Web_Functional_Design.md §6): beside Lựa chọn and on the home page, one conversation per trip.
// Every message goes to decision.trip; the harness sends what acts on the lists (a pick, a drop, a filter, a place on screen, why one is
// missing) to Decision's assistant and everything else to Trip's (discovery, events, trends, what a place is like, dates, who goes,
// photos, stays), so the answer is as rich as the old chat screen's: tag stages, photo cards, questions, place cards, quick replies.
// When the trip moves, the lists are rebuilt and arrive as `view` after the reply. On the home page the first message starts the trip.

// The welcome of an empty chat (the old chat screen's canvas): four ways to start. A tap writes its line in the message box, the user
// still sends it (or changes it).
const STARTERS = [
  { img: '/img/home/cloud.jpg', a: 'Săn', b: 'mây', note: 'Dậy sớm, đồi cao, bình minh trên núi.', seed: 'Mình muốn săn mây và ngắm bình minh, đi chậm và yên tĩnh.' },
  { img: '/img/home/cafe.jpg', a: 'Sống', b: 'chậm', note: 'Ít điểm, nhiều quán cà phê và đi dạo.', seed: 'Mình muốn sống chậm, ít điểm đến, nhiều quán cà phê đẹp.' },
  { img: '/img/home/lake.jpg', a: 'Cả nhà', b: 'cùng đi', note: 'Dễ đi, có chỗ cho trẻ và người lớn tuổi.', seed: 'Mình đi cùng gia đình có trẻ nhỏ và người lớn tuổi, cần lịch trình nhẹ nhàng.' },
  { img: '/img/home/pine.jpg', a: 'Ăn cho', b: 'đã', note: 'Quán ngon, đồ nướng, chợ đêm.', seed: 'Mình muốn ăn cho đã: quán ngon, đồ nướng và chợ đêm.' },
]

const logs = new Map<string, Msg[]>() // what each trip's chat showed, so another screen paints it at once
let seq = 0
const key = () => `c${++seq}`
// "có", "ừ xem thử": a yes to the photo card just offered opens it, without a model call
const YES = /^(có|ừ|ừm|uh|ok|oke|okay|được|đc|yes|muốn|xem|cho xem)( (chứ|nha|nhé|luôn|đi|thử|nào|với|ạ|xem|coi))*[\s!.]*$/
const isOpen = (c: Card | Deck | null) => !!c && (c.kind === 'deck' || (c.qid !== 'conversation' && c.qid !== 'frame'))

// The trip's transcript (Trip's turns) -> the chat, when this browser has not shown it yet.
function fromTranscript(v: View): Msg[] {
  const out: Msg[] = []
  for (const t of v.transcript) {
    const lastBot = out[out.length - 1]
    if (t.role === 'user') out.push({ key: key(), who: 'me', text: t.text })
    else if ((t.kind === 'places' || t.kind === 'replies' || t.kind === 'block') && lastBot?.who === 'bot') {
      if (t.kind === 'places') lastBot.places = [...(lastBot.places ?? []), { ids: t.ids ?? [], why: t.why ?? '', cards: t.cards ?? [] }]
      else if (t.kind === 'block') { if (t.block) lastBot.blocks = [...(lastBot.blocks ?? []), t.block] }
      else lastBot.replies = t.options ?? []
    } else if (t.text && t.turn > 0 && t.kind !== 'done') out.push(botMsg(key(), { say: t.text }))
  }
  const tail = out[out.length - 1]
  if (isOpen(v.card)) { if (tail?.who === 'bot' && !tail.card) tail.card = v.card; else out.push(botMsg(key(), { card: v.card })) }
  return out
}

// `plan`: the chat on Lịch trình. Its turns go to planning.trip (the schedule's assistant, or Trip for discovery); a turn that changed
// days lists them under the reply with a way to open each; a heart saves the place (Lịch trình has no list to add it to).
// `head`: the panel's header, drawn by the chat so it can hold "Trò chuyện mới" (null while there is nothing to start again from).
export type PlanChat = { chat: (input: TurnInput, h: Record<string, ((d: any) => void) | undefined>) => Promise<{ days?: ChangedDay[] } | null>; onOpenDay?: (day: number) => void } // eslint-disable-line @typescript-eslint/no-explicit-any
export function TripChat({ placeholder, ask, plan, head }: { placeholder: string; ask?: { text: string; n: number } | null; plan?: PlanChat; head?: (newChat: (() => void) | null) => ReactNode }) {
  const account = useAccount()
  const name = account?.guest ? '' : account?.name?.trim() ?? ''
  const input = useRef<HTMLInputElement>(null)
  const { trip, dispatch } = useTrip()
  const decision = useDecision()
  const starting = useStarting()
  const jid = trip.decisionId ?? trip.planningId // one conversation per trip, on every screen
  const [days, setDays] = useState<Record<string, ChangedDay[]>>({}) // the days a Lịch trình turn changed, by reply
  const [msgs, setMsgs] = useState<Msg[]>(() => (jid && logs.get(jid)) || [])
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [text, setText] = useState('')
  const [openCard, setOpenCard] = useState({ key: '', n: 0 })
  const [dock, setDock] = useState<HTMLDivElement | null>(null)
  const flying = useRef(false)
  const queued = useRef<{ input: TurnInput; mine: Msg | null }[]>([])
  const drain = useRef<() => void>(() => {})
  const end = useRef<HTMLDivElement>(null)
  const photoPick = useRef<HTMLInputElement>(null)
  const shown = useRef(jid)

  // Another trip on screen: its own chat, from what this browser kept or from the server's transcript. A trip the chat's own first
  // message just started (the home page) keeps the conversation already on screen.
  const all = useRef(msgs)
  all.current = msgs
  const before = useRef(jid)
  useEffect(() => {
    const was = before.current
    before.current = jid
    shown.current = jid
    if (!jid) { setMsgs([]); return }
    if (!was && all.current.length) return
    const kept = logs.get(jid)
    setMsgs(kept ?? [])
    if (kept) return
    let live = true
    getSession(jid).then((v) => { if (live && !logs.has(jid)) { const m = fromTranscript(v); logs.set(jid, m); setMsgs(m) } }, () => {})
    return () => { live = false }
  }, [jid])
  useEffect(() => { if (jid && shown.current === jid && !msgs.some((m) => m.who === 'bot' && m.live)) logs.set(jid, msgs) }, [jid, msgs])
  useEffect(() => { end.current?.scrollIntoView({ block: 'end', behavior: 'smooth' }) }, [msgs])

  const patchBot = (k: string, fn: (m: Extract<Msg, { who: 'bot' }>) => Partial<Extract<Msg, { who: 'bot' }>>) =>
    setMsgs((ms) => ms.map((m) => (m.key === k && m.who === 'bot' ? { ...m, ...fn(m) } : m)))

  // The trip this chat talks about: the one on screen, else one started (or moved on from the chat stage) now.
  const ensure = useCallback(async () => {
    if (trip.decisionId) return trip.decisionId
    return trip.journeyId ? resumeTrip(dispatch, trip.journeyId) : startTrip(dispatch, {})
  }, [trip.decisionId, trip.journeyId, dispatch])

  const send = useCallback(async (input: TurnInput, mine: Msg | null): Promise<boolean> => {
    flying.current = true
    setBusy(true)
    setNotice(null)
    const bot = key()
    setMsgs((ms) => [...ms, ...(mine ? [mine] : []), botMsg(bot, { live: true })])
    let said = ''
    try {
      const h: Handlers & { view?: (r: { view: import('../pd/types').View; diff?: import('../pd/types').Diff }) => void } = {
        progress: (d) => patchBot(bot, () => ({ steps: d.steps, ...(d.sources?.length ? { sources: d.sources } : {}) })),
        say: (d) => { said = d.replace !== undefined ? d.replace : said + (d.delta ?? ''); patchBot(bot, () => ({ say: said })) },
        card: (c) => patchBot(bot, () => ({ card: isOpen(c) ? c : null })),
        deck_issues: (d) => patchBot(bot, () => ({ issues: d.issues })),
        places: (d) => patchBot(bot, (m) => ({ places: [...(m.places ?? []), d] })),
        block: (d) => patchBot(bot, (m) => ({ blocks: [...(m.blocks ?? []), d] })),
        replies: (d) => patchBot(bot, () => ({ replies: d.options })),
        view: (r) => { if (!plan) decision.accept(r.view, r.diff ?? null) },
        error: (e) => setNotice(e.message),
      }
      if (plan) {
        const diff = await plan.chat(input, h as Record<string, ((d: any) => void) | undefined>) // eslint-disable-line @typescript-eslint/no-explicit-any
        if (diff?.days?.length) setDays((d) => ({ ...d, [bot]: diff.days! }))
        return true
      }
      const id = await ensure()
      await mutateJourney(id, 'decision', 'trip', input, h as Record<string, ((d: any) => void) | undefined>) // eslint-disable-line @typescript-eslint/no-explicit-any
      return true
    } catch (e) {
      if (e instanceof JourneyError && e.detail === 'health_hint_open') setNotice('Bạn trả lời câu lưu ý về sức khỏe trước nhé, rồi mình gợi ý nơi.')
      else if (input.kind === 'explored' && e instanceof JourneyError && e.status >= 400 && e.status < 500) setMsgs((ms) => ms.filter((m) => m.key !== bot))
      else setNotice('Chưa trả lời được lúc này, bạn thử lại sau ít giây nhé.')
      return false
    } finally {
      flying.current = false
      setBusy(false)
      window.setTimeout(() => drain.current(), 0)
      setMsgs((ms) => ms.flatMap((m) => (m.key !== bot || m.who !== 'bot' ? [m] : !m.say && !m.card && !m.steps.length && !m.places?.length && !m.blocks?.length ? [] : [{ ...m, live: false, t1: Date.now() }])))
    }
  }, [ensure, decision, plan]) // eslint-disable-line react-hooks/exhaustive-deps

  const enqueue = (input: TurnInput, mine: Msg | null = null) => { queued.current.push({ input, mine }); if (!flying.current) drain.current() }
  drain.current = () => { const next = queued.current.shift(); if (next) void send(next.input, next.mine) }

  const say = (t: string) => {
    const line = t.trim()
    if (!line || busy) return
    const tail = msgs[msgs.length - 1]
    if (YES.test(line.toLowerCase()) && tail?.who === 'bot' && !tail.answered && tail.card?.kind === 'deck' && tail.card.tabs[0]?.kind === 'drill') { setOpenCard({ key: tail.key, n: Date.now() }); return }
    void send({ kind: 'text', text: line }, { key: key(), who: 'me', text: line })
  }
  // The home's words, a theme, the tags picked on "Khám phá nơi muốn đến", a place sheet's "why not": said once the trip is on screen.
  useEffect(() => {
    if (!jid || !trip.startText || busy) return
    const t = trip.startText
    dispatch({ type: 'set', patch: { startText: null } })
    openAssistant(true)
    say(t)
  }, [jid, trip.startText]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (ask?.text) say(ask.text) }, [ask?.n]) // eslint-disable-line react-hooks/exhaustive-deps

  const answer = (m: Msg, input: { chips?: string[]; value?: string | null }, shown: string) => {
    if (busy || m.who !== 'bot' || !m.card || m.card.kind === 'deck') return
    patchBot(m.key, () => ({ answered: shown }))
    void send({ kind: 'answer', qid: m.card.qid, chips: input.chips ?? [], value: input.value ?? null }, null)
  }
  const answerDeck = async (m: Msg, answers: DeckAnswers, shown: string) => {
    if (busy || m.who !== 'bot') return
    patchBot(m.key, () => ({ answered: shown }))
    if (!(await send({ kind: 'deck', answers }, null))) patchBot(m.key, () => ({ answered: null }))
  }
  const pickedPhoto = async (f: File | undefined) => {
    if (photoPick.current) photoPick.current.value = ''
    if (!f) return
    try {
      const url = await shrink(f)
      void send({ kind: 'image', value: url }, { key: key(), who: 'me', text: '', photo: url })
    } catch { setNotice('Ảnh này mình không mở được, bạn thử ảnh JPG hoặc PNG khác nhé.') }
  }
  // A heart on a place the chat showed puts it in the trip (Lựa chọn's "Thêm vào chuyến"); the mark shows at once on every card of it.
  const like = (id: string, on: boolean, stage = false) => {
    setMsgs((ms) => ms.map((m) => (m.who === 'bot' && m.places ? { ...m, places: m.places.map((r) => ({ ...r, cards: r.cards.map((c) => (c.id === id ? { ...c, liked: on } : c)) })) } : m)))
    track('place_like', { place_id: id, value: on ? 'on' : 'off', from: stage ? 'tag_stage' : 'chat' })
    if (plan) { void toggleSaved(id); return }
    const a = { type: on ? 'select' as const : 'drop' as const, place_id: id }
    void ensure().then((jid): Promise<unknown> => (jid === trip.decisionId ? decision.act(a) : mutateJourney(jid, 'decision', 'act', a))).catch(() => setNotice('Chưa thêm được nơi này, bạn thử lại nhé.'))
  }
  const tagEnv = {
    sid: jid, like: (id: string, on: boolean) => like(id, on, true),
    wish: (sig: string, path: string, on: boolean) => enqueue({ kind: 'wish', qid: sig, target: path, value: on ? 'on' : 'off' }),
    explore: (sig: string, chips: string[], shown: string) => enqueue({ kind: 'explored', qid: sig, chips }, { key: key(), who: 'me', text: `Mình chọn: ${shown}` }),
  }
  const waiting = busy || starting

  // "Trò chuyện mới": every assistant of the trip starts its history over after a mark the server keeps with a copy of this chat's
  // words (harness new_chat, docs/AGENT_HARNESS.md §4); once it is saved the chat opens on its welcome again. The trip itself (what
  // was told, the places, the schedule) stays. Nothing to start over from, or a reply on its way: the button is greyed.
  const [clearing, setClearing] = useState(false)
  const fresh = async () => {
    if (waiting || clearing || !msgs.length) return
    const clear = () => { queued.current = []; setMsgs([]); setDays({}); setNotice(null); setText(''); if (jid) logs.set(jid, []); input.current?.focus({ preventScroll: true }) }
    if (!jid) { clear(); return }
    const messages = msgs.flatMap((m) => {
      const text = (m.who === 'me' ? m.text : m.say ?? '').trim().slice(0, 2000)
      return text ? [{ role: m.who === 'me' ? 'user' : 'bot', text }] : []
    }).slice(-200)
    setClearing(true)
    try { await mutateJourney(jid, plan ? 'planning' : 'decision', 'new_chat', { messages }); clear() }
    catch { setNotice('Chưa mở được trò chuyện mới, bạn thử lại sau ít giây nhé.') }
    finally { setClearing(false) }
  }

  return (
    <>
      {head?.(waiting || clearing || !msgs.length ? null : () => void fresh())}
      <div className="tg-asst__log tg-tchat" role="log" aria-live="polite">
        {msgs.length === 0 && <section className="tg-welcome tg-tchat__welcome" aria-label="Bắt đầu trò chuyện">
          <h3>Chào {name || 'bạn'},<br />bạn muốn đi đâu, làm gì?</h3>
          <p>Cứ nói tự nhiên, mình sẽ cùng bạn lên ý tưởng cho chuyến đi thật hợp.</p>
          <ul className="tg-welcome__cards" aria-label="Gợi ý để bắt đầu">
            {STARTERS.map((c) => (
              <li key={c.a}><button type="button" disabled={waiting} onClick={() => { setText(c.seed); input.current?.focus() }}>
                <img src={c.img} alt="" loading="lazy" />
                <b>{c.a} <em>{c.b}</em></b>
                <span>{c.note}</span>
              </button></li>
            ))}
          </ul>
        </section>}
        {msgs.length > 0 && <ol className="tg-cx__log" aria-label="Trò chuyện về chuyến đi">
          <TagEnvContext.Provider value={tagEnv}><AskDock.Provider value={dock}>
            {msgs.map((m, i) => [
              <Turn key={m.key} m={m} busy={busy} onAnswer={answer} onDeck={answerDeck} onText={say} onPhoto={() => photoPick.current?.click()} onLike={like} last={i === msgs.length - 1} openCard={openCard.key === m.key ? openCard.n : 0} />,
              days[m.key] && plan?.onOpenDay ? (
                <li key={`${m.key}-days`} className="tg-msg__days-row">
                  <ul className="tg-msg__days" aria-label="Các ngày đã đổi">
                    {days[m.key].map((d) => (
                      <li key={d.day}><button type="button" className="tg-chday" onClick={() => plan.onOpenDay?.(d.day)}>
                        <span className="tg-chday__head"><b>Ngày {d.day} đã đổi</b><span>Xem ngày này</span></span>
                        {d.stops.length ? <ol>{d.stops.map((st) => <li key={st.id}><time>{st.start}</time><span>{st.name}</span></li>)}</ol> : <span className="tg-chday__empty">Ngày này giờ không còn nơi nào.</span>}
                      </button></li>
                    ))}
                  </ul>
                </li>
              ) : null,
            ])}
          </AskDock.Provider></TagEnvContext.Provider>
        </ol>}
        {starting && !msgs.length && <p className="tg-busy" role="status"><i /> Đang mở chuyến của bạn…</p>}
        {notice && <p className="tg-alert" role="alert"><Icon name="warn" size={16} /> {notice}</p>}
        <div ref={end} />
      </div>
      <div ref={setDock} className="tg-asks__dock" />
      <input ref={photoPick} type="file" accept="image/*" hidden onChange={(e) => void pickedPhoto(e.target.files?.[0])} />
      <form className={`tg-asst__in ${waiting ? 'is-busy' : ''}`} onSubmit={(e) => { e.preventDefault(); say(text); setText('') }}>
        <button type="button" className="tg-asst__ph" onClick={() => photoPick.current?.click()} disabled={waiting} aria-label="Gửi ảnh một nơi bạn thích" title="Gửi ảnh một nơi bạn thích"><Icon name="image" size={18} /></button>
        <label className="tg-sr" htmlFor="tg-asst-in">Nói với mình</label>
        <input ref={input} id="tg-asst-in" className="tg-line-input" value={text} maxLength={1000} onChange={(e) => setText(e.target.value)} placeholder={placeholder} autoComplete="off" />
        <button type="submit" className="tg-send" disabled={waiting || !text.trim()} aria-label="Gửi"><Icon name="send" size={18} /></button>
      </form>
    </>
  )
}
