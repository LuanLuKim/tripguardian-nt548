import { useState, type CSSProperties } from 'react'
import type { Card, ChatPlaces, Deck, DeckAnswers, DeckIssue, ResultBlock, Step, WebSource } from '../../tu/types'
import { tidyText } from '../../../data/placeName'
import { Icon } from '../../ui/icons'
import { AskCard, PhotoStage } from './Ask'
import { CardView, type Answer } from './Cards'
import { DeckIssues } from './Deck'
import { Block } from './Blocks'
import { PlaceStage } from './Places'
import { Rich } from './Rich'
import { SourceMark, Sources } from './Sources'

// A bot turn shows what it is doing (steps from the server's progress events: open while it works so the user sees how it
// reads the message, folded to one quiet line once the turn ends), its words, and at most one question.

export type Msg =
  | { key: string; who: 'me'; text: string; photo?: string; files?: string[] }
  | { key: string; who: 'bot'; say: string; steps: Step[]; sources: WebSource[]; card: Card | Deck | null; answered: string | null; issues?: DeckIssue[]
      live: boolean; t0: number; t1?: number; places?: ChatPlaces[]; blocks?: ResultBlock[]; replies?: string[] }

export const botMsg = (key: string, patch: Partial<Extract<Msg, { who: 'bot' }>> = {}): Msg =>
  ({ key, who: 'bot', say: '', steps: [], sources: [], card: null, answered: null, live: false, t0: Date.now(), ...patch })

// What the turn is doing, in one grey line like an assistant's, that changes as it goes: "Đang tìm kiếm 6 trang web", the
// step it is on ("Đang ghi nhận phương tiện di chuyển"), else "Đang suy nghĩ". Once the turn ends it is one quiet line
// ("Đã xử lý trong 13 giây"); a click opens the steps.
const doing = (label: string) => {
  const head = label.split(' · ')[0].trim()
  return /^đang /i.test(head) ? head : `Đang ${head.charAt(0).toLowerCase()}${head.slice(1)}`
}

function headline(steps: Step[], live: boolean, secs: number, sources: WebSource[]) {
  if (!live) return `Đã xử lý trong ${secs < 60 ? `${secs} giây` : `${Math.floor(secs / 60)} phút ${secs % 60} giây`}`
  if (steps.some((s) => s.id.startsWith('web') && s.status === 'run')) return sources.length ? `Đang tìm kiếm ${sources.length} trang web` : 'Đang tìm kiếm trên web'
  const shown = steps.filter(worth)
  const now = [...shown].reverse().find((s) => s.status === 'run') ?? shown.filter((s) => s.status === 'ok').at(-1)
  return now ? doing(now.label) : 'Đang suy nghĩ'
}

// What is worth showing of the server's progress: the interpretation (what it noted from the message, what it looks for, what it
// checks on the web, weather and distance) and not the plumbing every turn repeats ("read the message", "split the ideas", the
// generic "find places"). The header line says which step it is on.
const PLUMBING = new Set(['read', 'split', 'cues'])
const worth = (s: Step) => !PLUMBING.has(s.id) && !s.id.startsWith('find:')

function Steps({ steps, sources, live, secs }: { steps: Step[]; sources: WebSource[]; live: boolean; secs: number }) {
  const shown = steps.filter(worth)
  const [open, setOpen] = useState(false) // folded, live or done: the one line says enough; a click shows every step
  if (!live && !shown.length) return null // nothing worth opening once the turn is over
  return (
    <div className={`tg-cx__think ${open ? 'is-open' : ''} ${live ? 'is-run' : ''}`}>
      <button type="button" className="tg-cx__think-h" aria-expanded={open && shown.length > 0} onClick={() => setOpen((o) => !o)}>
        <span className={live ? 'tg-cx__shimmer' : ''} role="status" aria-atomic="true">{headline(steps, live, secs, sources)}</span>
        {shown.length > 0 && <Icon name="chevronDown" size={15} className="tg-cx__chev" />}
      </button>
      <div className="tg-cx__think-b"><div>
        <ol className="tg-cx__steps">
          {shown.map((s) => (
            <li key={s.id} className={`is-${s.status}`}>
              {(() => {
                const at = s.label.indexOf(' · ')
                return at < 0 ? <b>{s.label}</b> : <><b>{s.label.slice(0, at)}</b><span className="tg-cx__said">{s.label.slice(at + 3)}</span></>
              })()}
              {s.id.startsWith('web') && sources.length > 0 && (
                <span className="tg-cx__det">{sources.filter((x) => /^https?:\/\//i.test(x.url)).map((x, i) => <a key={x.url} className="tg-cx__tag" style={{ '--d': `${i * 120}ms` } as CSSProperties} href={x.url} target="_blank" rel="noopener noreferrer"><SourceMark domain={x.domain} />{x.domain.replace(/^www\./, '')}</a>)}</span>
              )}
            </li>
          ))}
        </ol>
      </div></div>
    </div>
  )
}

export function Turn({ m, busy, onAnswer, onDeck, onText, onPhoto, onLike, last = false }: { m: Msg; busy: boolean; onAnswer: (m: Msg, ...a: Parameters<Answer>) => void; onDeck: (m: Msg, answers: DeckAnswers, shown: string) => void; onText: (text: string) => void; onPhoto: () => void; onLike: (id: string, on: boolean) => void; last?: boolean }) {
  if (m.who === 'me')
    return (
      <li className="tg-cx__m is-me">
        <div className={`tg-cx__bub ${m.photo ? 'is-img' : ''}`}>
          {m.photo && <img src={m.photo} alt="Ảnh bạn gửi" />}
          {m.text && <p>{m.text}</p>}
          {m.files?.length ? <p className="tg-cx__files">{m.files.map((n) => <span key={n}><Icon name="clip" size={13} />{n}</span>)}</p> : null}
        </div>
      </li>
    )
  const secs = Math.max(1, Math.round(((m.t1 ?? Date.now()) - m.t0) / 1000))
  const waiting = m.live && !m.say && !m.steps.length
  const tab = m.card?.kind === 'deck' ? m.card.tabs[0] : undefined
  return (
    <li className="tg-cx__m is-bot" aria-busy={m.live}>
      <div className="tg-cx__stack">
        {m.steps.length > 0 && <Steps steps={m.steps} sources={m.sources} live={m.live} secs={secs} />}
        {waiting && <p className="tg-cx__say is-wait" role="status"><span className="tg-dots" aria-hidden="true"><i /><i /><i /></span><span className="tg-sr">Đang đọc</span></p>}
        {(m.say || tab) && (
          <div className="tg-cx__say">
            {m.say && <Rich text={tidyText(m.say)} />}
            {tab && <p className="tg-cx__say-ask">{tab.question}</p>}
          </div>
        )}
        {!m.live && m.sources.length > 0 && <Sources sources={m.sources} />}
        {/* a trends block lays its places out as rows: the read tools' card list would show them twice */}
        {!m.blocks?.some((b) => b.kind === 'trends') && m.places?.map((row, i) => <PlaceStage key={i} row={row} busy={busy} onLike={onLike} />)}
        {m.blocks?.map((b, i) => <Block key={i} block={b} busy={busy} onLike={onLike} />)}
        {last && m.replies && m.replies.length > 0 && (
          <div className="tg-cx-qr" role="group" aria-label="Trả lời nhanh">
            {m.replies.map((r) => <button key={r} type="button" className="tg-chip" disabled={busy} onClick={() => onText(r)}>{r}</button>)}
          </div>
        )}
        {m.card && m.card.kind !== 'deck' && m.card.text && m.card.qid !== 'conversation' && (
          <p className="tg-cx__q">{m.card.text}{m.card.reason && !m.answered && <small>Vì sao hỏi: {m.card.reason}</small>}</p>
        )}
        {m.card && (m.card.kind === 'deck' ? !!tab : m.card.qid !== 'conversation') && (m.answered
          ? <span className="tg-cx__done-row"><Icon name="check" size={15} />{m.answered}</span>
          : m.card.kind === 'deck' ? (tab!.visual
            ? <PhotoStage key={JSON.stringify(m.card)} deck={m.card} busy={busy} autoOpen={!m.blocks?.some(b => b.kind === 'tags') && !m.places?.length} onAnswer={(answers, shown) => onDeck(m, answers, shown)} onText={onText} />
            : <AskCard key={JSON.stringify(m.card)} deck={m.card} busy={busy} issues={m.issues} onAnswer={(answers, shown) => onDeck(m, answers, shown)} onText={onText} />)
          : <CardView card={m.card} busy={busy} onAnswer={(input, shown) => onAnswer(m, input, shown)} onPhoto={onPhoto} />)}
        {(!m.card || m.answered) && <DeckIssues issues={m.issues ?? []} />}
      </div>
    </li>
  )
}
