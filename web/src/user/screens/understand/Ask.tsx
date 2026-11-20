import { createContext, useContext, useEffect, useId, useLayoutEffect, useReducer, useRef, useState, type CSSProperties, type Dispatch, type KeyboardEvent, type ReactNode, type RefObject, type SetStateAction } from 'react'
import { createPortal } from 'react-dom'
import type { Deck, DeckAnswers, DeckIssue, Option, Tab } from '../../tu/types'
import { CardImg, preloadPhotos } from '../../ui/common'
import { Icon, type IconName } from '../../ui/icons'
import { DeckIssues, ExtraInputs, TAB_ICON, TripInputs, useDeckForm } from './Deck'

// The chat's one question (docs/UI_SPEC_USER_WEB.md Trang 3). The question itself is a line of the chat (Turn); the
// card under it is a short numbered list like an assistant's quick question: at most three options, a fourth row to
// type another answer. A single choice with nothing else to fill sends at once. A photo question opens a stage over
// the blurred screen so the user looks at the places, not the chat.

const reduced = () => matchMedia('(prefers-reduced-motion: reduce)').matches

// The chat column's slot for the open question (Understand.tsx): the sheet sits there, over the composer, the chat
// blurred behind it. Without a slot (another screen) the question stays a card in the chat.
export const AskDock = createContext<HTMLElement | null>(null)

// The open question as a sheet, like an assistant's quick question: header chip, the question, numbered options, a row to
// type another answer, Bỏ qua and Gửi. Nothing here is compulsory: "Để sau" (or Esc, or a click on the blurred chat)
// folds it to one line above the composer, and the user can keep typing; a tap on that line brings it back.
export function AskSheet(props: Parameters<typeof AskCard>[0]) {
  const dock = useContext(AskDock)
  const [open, setOpen] = useState(true)
  const [leaving, setLeaving] = useState(false)
  const panel = useRef<HTMLDivElement>(null)
  const id = useId()
  const tab = props.deck.tabs[0]
  useEffect(() => { if (open) panel.current?.focus({ preventScroll: true }) }, [open])
  if (!tab) return null
  if (!dock) return <AskCard {...props} />
  const later = () => {
    if (reduced()) { setOpen(false); return }
    setLeaving(true)
    window.setTimeout(() => { setLeaving(false); setOpen(false) }, 180)
  }
  const normal = tab.options.filter(o => !['other', 'skip'].includes(o.id))
  const hint = !normal.length ? 'Nhập hoặc chọn' : tab.multi ? 'Chọn bao nhiêu cũng được' : 'Chọn một'
  if (!open) return <button type="button" className="tg-asks__pill" onClick={() => setOpen(true)}>
    <Icon name={TAB_ICON[tab.qid] ?? 'sparkle'} size={15} />
    <span><b>{tab.header}</b>Câu hỏi đang chờ, bạn trả lời lúc nào cũng được</span>
    <em>Trả lời<Icon name="chevronUp" size={14} /></em>
  </button>
  return createPortal(<>
    <div className={`tg-asks__veil ${leaving ? 'is-leaving' : ''}`} aria-hidden="true" onClick={later} />
    <div ref={panel} className={`tg tg-asks ${leaving ? 'is-leaving' : ''}`} role="dialog" aria-modal="false" aria-labelledby={`${id}-q`} tabIndex={-1}
      onKeyDown={e => { if (e.key === 'Escape') { e.preventDefault(); later() } }}>
      <header className="tg-asks__top">
        <span className="tg-asks__chip"><Icon name={TAB_ICON[tab.qid] ?? 'sparkle'} size={14} />{tab.header}</span>
        <span className="tg-asks__hint">{hint}</span>
        <button type="button" className="tg-asks__later" onClick={later} aria-label="Để sau, thu gọn câu hỏi">Để sau<Icon name="chevronDown" size={15} /></button>
      </header>
      <h3 id={`${id}-q`} className="tg-asks__q">{tab.question}</h3>
      {tab.why && <p className="tg-asks__why">{tab.why}</p>}
      <AskCard {...props} bare />
    </div>
  </>, dock)
}

export function AskCard({ deck, busy, issues = [], onAnswer, onText, bare = false }: {
  deck: Deck; busy: boolean; issues?: DeckIssue[]
  onAnswer: (answers: DeckAnswers, shown: string) => void
  onText: (text: string) => void
  bare?: boolean // inside the sheet, which already shows the header and the question
}) {
  const form = useDeckForm(deck, 0)
  const { tab, selected, choose, answers } = form
  const [typed, setTyped] = useState('')
  const [sent, setSent] = useState<string | null>(null)
  const root = useRef<HTMLElement>(null)
  if (!tab) return null
  const normal = tab.options.filter(o => !['other', 'skip'].includes(o.id))
  const grouped = tab.qid === 'trip' && tab.kind === 'required'
  const instant = !tab.multi && !grouped && !tab.inputs.length // one tap answers it
  // a row to type another answer only makes sense next to options: a card that asks only for a number, a date or a stay has none
  const canOther = tab.options.some(o => o.id === 'other') && normal.length > 0
  const canSkip = tab.options.some(o => o.id === 'skip')
  const reasons = tab.options.filter(o => o.prefilled && selected.includes(o.id) && o.because).map(o => o.because)
  const pick = (o: Option) => {
    if (busy || sent) return
    if (instant) {
      setSent(o.id)
      window.setTimeout(() => onAnswer({ [tab.qid]: [o.id] }, o.label), reduced() ? 0 : 180) // the row confirms before the turn starts
      return
    }
    choose(o)
  }
  const other = () => {
    const text = typed.trim()
    if (!text || busy) return
    setTyped('')
    onText(text)
  }
  const keys = (e: KeyboardEvent<HTMLElement>) => {
    if ((e.target as HTMLElement).tagName === 'INPUT') return
    const n = Number(e.key)
    if (n >= 1 && n <= normal.length) { e.preventDefault(); pick(normal[n - 1]) }
    if (n === normal.length + 1 && canOther) { e.preventDefault(); root.current?.querySelector<HTMLInputElement>('.tg-qa__other input')?.focus() }
  }
  const chips = (options: Option[]) => <div className="tg-qa__chips">{options.map(o => <button type="button" key={o.id} className={`tg-qa__chip ${selected.includes(o.id) ? 'is-on' : ''}`} disabled={busy} aria-pressed={selected.includes(o.id)} onClick={() => choose(o)}>{o.prefilled && <span aria-label="Mình đoán">✎ </span>}{o.label}</button>)}</div>
  return <section ref={root} className={`tg-qa ${bare ? 'is-bare' : ''} ${busy ? 'is-waiting' : ''} ${sent ? 'is-sent' : ''}`} data-deck-qid={tab.qid} aria-label={tab.header} onKeyDown={keys}>
    {!bare && <header className="tg-qa__head">
      <Icon name={TAB_ICON[tab.qid] ?? 'sparkle'} size={16} />
      <b>{tab.header}</b>
      <span>{!normal.length ? 'Nhập hoặc chọn' : tab.multi ? 'Chọn một hoặc nhiều' : grouped ? 'Chọn hoặc nhập' : 'Chọn một'}</span>
    </header>}
    {grouped && <div className="tg-qa__fill"><TripInputs form={form} busy={busy} chips={chips} /></div>}
    <ol className="tg-qa__list" role="list">
      {!grouped && normal.map((o, i) => {
        const on = sent === o.id || selected.includes(o.id)
        return <li key={o.id} style={{ '--i': i } as CSSProperties}>
          <button type="button" className={`tg-qa__opt ${on ? 'is-on' : ''}`} disabled={busy || !!sent} aria-pressed={on} onClick={() => pick(o)}>
            <kbd aria-hidden="true">{i + 1}</kbd>
            <span className="tg-qa__txt"><b>{o.prefilled && <span className="tg-qa__guess" aria-label="Mình đoán">✎</span>}{o.label}</b>{o.description && <small>{o.description}</small>}</span>
            <span className="tg-qa__tick" aria-hidden="true"><Icon name="check" size={14} strokeWidth={2.4} /></span>
          </button>
        </li>
      })}
      {canOther && <li className="tg-qa__other" style={{ '--i': grouped ? 0 : normal.length } as CSSProperties}>
        <kbd aria-hidden="true">{grouped ? '✎' : normal.length + 1}</kbd>
        <input type="text" value={typed} disabled={busy || !!sent} placeholder="Khác: gõ câu trả lời của bạn…" aria-label="Câu trả lời khác"
          onChange={e => setTyped(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.nativeEvent.isComposing) { e.preventDefault(); other() } }} />
        <button type="button" className="tg-qa__send" disabled={busy || !typed.trim()} aria-label="Gửi câu trả lời khác" onClick={other}><Icon name="send" size={16} /></button>
      </li>}
    </ol>
    {!grouped && <ExtraInputs form={form} busy={busy} send={onAnswer} />}
    {!!reasons.length && <p className="tg-qa__why">✎ {Array.from(new Set(reasons)).join(' · ')}</p>}
    <DeckIssues issues={issues} />
    {(canSkip || !instant) && <footer className="tg-qa__foot">
      {canSkip && <button type="button" className="tg-qa__skip" disabled={busy || !!sent} onClick={() => { setSent('skip'); onAnswer({ [tab.qid]: ['skip'] }, 'Bỏ qua') }}>Bỏ qua</button>}
      {!instant && <button type="button" className="tg-btn tg-btn--primary tg-qa__go" disabled={busy || !Object.keys(answers).length} onClick={() => onAnswer(answers, shownOf(tab, form.selected, form.fields))}>Gửi <Icon name="arrow" size={16} /></button>}
    </footer>}
  </section>
}

// What the user filled in, as the line the answered card folds into.
function shownOf(tab: Tab, selected: string[], fields: Record<string, string>) {
  const day = (d: string) => d.slice(8, 10) + '/' + d.slice(5, 7)
  const parts = tab.options.filter(o => selected.includes(o.id) && !/^(start|end)\./.test(o.id)).map(o => o.label)
  if (fields.dateFrom && fields.dateTo) parts.unshift(`${day(fields.dateFrom)} – ${day(fields.dateTo)}`)
  if (fields['trip.start']) parts.push(`bắt đầu ${fields['trip.start']}`)
  if (fields['trip.end']) parts.push(`xong ${fields['trip.end']}`)
  if (fields['companions.people']) parts.push(`${fields['companions.people']} người`)
  if (fields['budget.amount']) parts.push(`${fields['budget.amount']} triệu`)
  if (fields.lodging) parts.push(JSON.parse(fields.lodging).text)
  return parts.join(' · ') || tab.header
}

// The photo stage, shared by a photo question (PhotoStage) and the assistant's places (understand/Places.tsx): a ring
// of photo cards over the blurred screen, the middle one in front.
let stagesOpen = 0 // a stage may open over another (a place card's clips): the screen stays blurred until the last one closes
export function useStage(initial: boolean) {
  const [open, setOpen] = useState(initial)
  const [leaving, setLeaving] = useState(false)
  // The screen behind is blurred by filtering the app root: backdrop-filter on the veil is dropped by some browsers.
  useEffect(() => {
    if (!open) return
    stagesOpen++
    document.documentElement.classList.add('tg-stage-open')
    return () => { if (--stagesOpen === 0) document.documentElement.classList.remove('tg-stage-open') }
  }, [open])
  const close = (then?: () => void) => {
    if (reduced()) { setOpen(false); then?.(); return }
    setLeaving(true)
    window.setTimeout(() => { setLeaving(false); setOpen(false); then?.() }, 220) // leaving is quicker than arriving
  }
  return { open, setOpen, leaving, close }
}

// Arrows turn the ring, Escape closes, Space / Enter act on the front card; Tab stays inside the stage.
export function stageKeys(e: KeyboardEvent<HTMLDivElement>, panel: RefObject<HTMLDivElement | null>, count: number,
  setAt: Dispatch<SetStateAction<number>>, close: () => void, act: (key: string) => void) {
  if ((e.target as HTMLElement).tagName === 'INPUT') return
  if (e.key === 'Escape') { e.preventDefault(); close() }
  if (e.key === 'ArrowRight') { e.preventDefault(); setAt(i => (i + 1) % count) }
  if (e.key === 'ArrowLeft') { e.preventDefault(); setAt(i => (i - 1 + count) % count) }
  if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); act(e.key) }
  if (e.key === 'Tab') {
    const items = [...(panel.current?.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled)') ?? [])]
    if (!items.length) return
    const i = items.indexOf(document.activeElement as HTMLElement)
    const next = e.shiftKey ? (i <= 0 ? items.length - 1 : i - 1) : (i === items.length - 1 ? 0 : i + 1)
    e.preventDefault(); items[next].focus()
  }
}

export function StageFrame({ leaving, kicker, kickerIcon = 'image', question, why, crumbs, closeLabel = 'Để sau', onBack, onClose, onKeyDown, panel, children }: {
  leaving: boolean; kicker?: string; kickerIcon?: IconName; question?: string; why?: string | null; crumbs?: ReactNode; closeLabel?: string; onBack?: () => void
  onClose: () => void; onKeyDown: (e: KeyboardEvent<HTMLDivElement>) => void
  panel: RefObject<HTMLDivElement | null>; children: ReactNode
}) {
  useEffect(() => {
    const last = document.activeElement as HTMLElement | null
    panel.current?.focus()
    return () => last?.focus?.()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps
  return createPortal(<div className={`tg tg-stage-overlay ${leaving ? 'is-leaving' : ''}`} onKeyDown={onKeyDown}>
    <div className="tg-stage__veil" aria-hidden="true" onClick={() => onClose()} />
    <div ref={panel} className="tg-stage__panel" role="dialog" aria-modal="true" aria-labelledby={question ? 'tg-stage-q' : undefined} aria-label={question ? undefined : 'Gợi ý'} tabIndex={-1}>
      <header className="tg-stage__head">
        {onBack && <button type="button" className="tg-stage__back" aria-label="Quay lại" onClick={onBack}><Icon name="chevronLeft" size={18} /></button>}
        {kicker && <span className="tg-stage__kicker"><Icon name={kickerIcon} size={15} />{kicker}</span>}
        {crumbs}
        {question && <h3 id="tg-stage-q">{question}</h3>}
        {why && <p>{why}</p>}
        <button type="button" className="tg-stage__x" aria-label={closeLabel} title={closeLabel} onClick={() => onClose()}><Icon name="x" size={18} /></button>
      </header>
      {children}
    </div>
  </div>, document.body)
}

// deck: drawn as a pile (there is more inside); badge / extra: small things over the photo; loading: a shimmer while its children load
export interface StageCard { id: string; photo: string | null; alt: string; title: string; line: ReactNode; on: boolean; pick: ReactNode; pickLabel: string
  deck?: boolean; badge?: ReactNode; extra?: ReactNode; loading?: boolean
  media?: ReactNode } // media: what fills the photo slot instead of `photo` (an event's poster, which may be another site's picture or none)

export function StageRing({ cards, at, setAt, busy, label, multi, tree, reach = 2, prevLabel, nextLabel, hint, onFront, onPick }: {
  cards: StageCard[]; at: number; setAt: Dispatch<SetStateAction<number>>; busy: boolean; label: string; multi?: boolean
  tree?: { phase: 'idle' | 'leave'; dir: 'down' | 'up' } // the tag stage: a level swaps for the next with a short fold and fan
  reach?: number // how many cards on each side of the front one are drawn
  prevLabel: string; nextLabel: string; hint?: string; onFront: (i: number) => void; onPick: (i: number) => void
}) {
  const ring = useRef<HTMLDivElement>(null)
  const n = cards.length
  // The row is a circle: the last card stands left of the first. Each card shows once, so what the stage holds is what
  // its line in the chat counts ("4 kiểu" is four cards); with fewer cards than places the row is simply shorter.
  const total = n
  // The wall's position is counted in whole cards that never wrap, so a turn is always one step and a card keeps its own place.
  const wall = useRef(at)
  const was = useRef(at)
  if (was.current !== at && n > 0) {
    let step = (((at - was.current) % n) + n) % n
    if (step > n / 2) step -= n
    wall.current += step
    was.current = at
  }
  const [, redraw] = useReducer((x: number) => x + 1, 0)
  // Bringing a card to the front moves the wall by what separates them on screen, whichever way round the circle is shorter.
  const bring = (v: number, d: number) => { wall.current += d; was.current = v % n; setAt(v % n); redraw() }
  const gap = (v: number) => {
    const r = (((v - wall.current) % total) + total) % total
    return r > total / 2 ? r - total : r
  }
  // A card that wraps from one end of the circle to the other jumps instead of sweeping across the front.
  const prev = useRef<number[]>([])
  useLayoutEffect(() => { prev.current = Array.from({ length: total }, (_, v) => gap(v)) })
  // The mouse wheel turns the row one card per notch; a short rest between turns keeps a trackpad from racing through.
  useEffect(() => {
    const el = ring.current
    if (!el) return
    let rest = 0, sum = 0
    const turn = (e: WheelEvent) => {
      e.preventDefault()
      sum += Math.abs(e.deltaX) > Math.abs(e.deltaY) ? e.deltaX : e.deltaY
      const now = performance.now()
      if (Math.abs(sum) < 40 || now < rest) return
      const step = Math.sign(sum) // read now: the updater below runs later, after sum is reset
      setAt(i => (i + step + n) % n)
      sum = 0; rest = now + 260
    }
    el.addEventListener('wheel', turn, { passive: false })
    return () => el.removeEventListener('wheel', turn)
  }, [n, setAt])
  return <>
    <div ref={ring} className={`tg-stage__ring ${tree ? 'is-tree' : ''}`} data-phase={tree?.phase} data-dir={tree?.dir} role="listbox" aria-label={label} aria-multiselectable={multi}>
      {Array.from({ length: total }, (_, v) => {
        const i = v % n, c = cards[i], d = gap(v)
        const jump = prev.current[v] !== undefined && Math.abs(d - prev.current[v]) > total / 2
        return <div key={c.id} role="option" aria-selected={c.on} className={`tg-stage__card ${d === 0 ? 'is-front' : ''} ${jump ? 'is-jump' : ''} ${c.on ? 'is-on' : ''} ${c.deck ? 'is-deck' : ''} ${c.loading ? 'is-loading' : ''}`}
          style={{ '--d': d, '--a': Math.abs(d), '--n': v, ...(Math.abs(d) > reach ? { '--far': 'hidden' } : {}) } as CSSProperties}
          onClick={() => (d === 0 ? onFront(i) : bring(v, d))}>
          <div className="tg-stage__photo">{c.media ? c.media : c.photo ? <CardImg src={c.photo} alt={c.alt} draggable={false} /> : <span>Chưa có ảnh</span>}{c.badge}{c.extra}</div>
          <div className="tg-stage__body">
            <b>{c.title}</b>
            {c.line}
          </div>
          <button type="button" className="tg-stage__pick" tabIndex={d === 0 ? 0 : -1} aria-label={c.pickLabel} aria-pressed={c.on} disabled={busy}
            onClick={e => { e.stopPropagation(); bring(v, d); onPick(i) }}>{c.pick}</button>
        </div>
      })}
      {n > 1 && <button type="button" className="tg-stage__nav is-prev" aria-label={prevLabel} onClick={() => setAt((at - 1 + n) % n)}><Icon name="chevronLeft" size={20} /></button>}
      {n > 1 && <button type="button" className="tg-stage__nav is-next" aria-label={nextLabel} onClick={() => setAt((at + 1) % n)}><Icon name="chevronRight" size={20} /></button>}
    </div>
    {cards.length <= 14 && <div className="tg-stage__dots" aria-hidden="true">{cards.map((c, i) => <i key={c.id} className={`${i === at ? 'is-at' : ''} ${c.on ? 'is-on' : ''}`} />)}</div>}
    {hint && <p className="tg-stage__hint"><span className="tg-stage__mouse"><Icon name="mouse" size={18} /></span>{hint} · {at + 1}/{cards.length}</p>}
  </>
}

// A photo question: real places of each kind on cards, the middle one in front, the screen behind blurred.
export function PhotoStage({ deck, busy, onAnswer, onText, autoOpen = true, openSignal = 0 }: {
  deck: Deck; busy: boolean; autoOpen?: boolean
  openSignal?: number // changes when the user said yes to the offered card in words: it opens like a tap
  onAnswer: (answers: DeckAnswers, shown: string) => void
  onText: (text: string) => void
}) {
  const tab = deck.tabs[0]
  const options = tab.options.filter(o => !['other', 'skip'].includes(o.id))
  useEffect(() => preloadPhotos(options.map(o => o.photo?.url)), [deck]) // eslint-disable-line react-hooks/exhaustive-deps
  const { open, setOpen, leaving, close } = useStage(autoOpen)
  useEffect(() => { if (openSignal) setOpen(true) }, [openSignal]) // eslint-disable-line react-hooks/exhaustive-deps
  const [at, setAt] = useState(() => Math.max(0, Math.floor((options.length - 1) / 2)))
  const [chosen, setChosen] = useState<string[]>(() => options.filter(o => o.prefilled).map(o => o.id))
  const [typed, setTyped] = useState('')
  const panel = useRef<HTMLDivElement>(null)
  const opener = useRef<HTMLButtonElement>(null)
  const toggle = (id: string) => setChosen(c => c.includes(id) ? c.filter(x => x !== id) : tab.multi ? [...c, id] : [id])
  const send = (answers: DeckAnswers, shown: string) => { close(); onAnswer(answers, shown) }
  const keys = (e: KeyboardEvent<HTMLDivElement>) => stageKeys(e, panel, options.length, setAt, () => close(), () => { if (options[at]) toggle(options[at].id) })
  const cards: StageCard[] = options.map(o => {
    const on = chosen.includes(o.id)
    return { id: o.id, photo: o.photo?.url ?? null, alt: o.photo?.name ?? '', title: o.label, on,
      line: <small><Icon name="pin" size={13} />{o.count !== null ? `${o.count.toLocaleString('vi-VN')} nơi` : 'Nơi thật'}{o.photo?.name ? ` · ${o.photo.name}` : ''}</small>,
      pick: <Icon name={on ? 'check' : 'plus'} size={18} strokeWidth={2.2} />, pickLabel: on ? `Bỏ chọn ${o.label}` : `Chọn ${o.label}` }
  })
  const summary = <button ref={opener} type="button" className="tg-stage__reopen" disabled={busy} onClick={() => setOpen(true)}>
    <span className="tg-stage__thumbs" aria-hidden="true">{options.slice(0, 3).map(o => o.photo ? <CardImg key={o.id} src={o.photo.url} alt="" /> : <i key={o.id} />)}</span>
    <span><b>{tab.header}</b><small>{options.length} kiểu nơi có ảnh thật · bấm để xem</small></span>
    <Icon name="chevronRight" size={18} />
  </button>
  return <>
    {summary}
    {open && <StageFrame leaving={leaving} kicker={tab.question ? tab.header : undefined} question={tab.question || tab.header} why={tab.why} onClose={() => close()} onKeyDown={keys} panel={panel}>
      <StageRing cards={cards} at={at} setAt={setAt} busy={busy} label="Các kiểu nơi" multi={tab.multi} prevLabel="Kiểu trước" nextLabel="Kiểu sau"
        hint="Lăn chuột hoặc dùng ← → để xoay · bấm thẻ giữa để chọn" onFront={i => toggle(options[i].id)} onPick={i => toggle(options[i].id)} />
      <footer className="tg-stage__foot">
        {tab.options.some(o => o.id === 'other') && <label className="tg-stage__other">
          <input type="text" value={typed} placeholder="Khác: tả kiểu bạn thích…" disabled={busy} onChange={e => setTyped(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && typed.trim() && !e.nativeEvent.isComposing) { e.preventDefault(); close(); onText(typed.trim()) } }} />
        </label>}
        {tab.options.some(o => o.id === 'skip') && <button type="button" className="tg-btn tg-btn--ghost" disabled={busy} onClick={() => send({ [tab.qid]: ['skip'] }, 'Bỏ qua')}>Bỏ qua</button>}
        {typed.trim()
          ? <button type="button" className="tg-btn tg-btn--primary" disabled={busy} onClick={() => { close(); onText(typed.trim()) }}>Gửi ý của bạn <Icon name="send" size={16} /></button>
          : <button type="button" className="tg-btn tg-btn--primary" disabled={busy || !chosen.length} onClick={() => send({ [tab.qid]: chosen }, options.filter(o => chosen.includes(o.id)).map(o => o.label).join(' · '))}>
            {chosen.length ? `Chọn ${chosen.length} kiểu` : 'Chọn ít nhất một'} <Icon name="check" size={16} />
          </button>}
      </footer>
    </StageFrame>}
  </>
}
