import { useEffect, useState, type CSSProperties } from 'react'
import type { Card, ChatPlaces, Deck, DeckAnswers, DeckIssue, ResultBlock, Step, WebSource } from '../../tu/types'
import { tidyText } from '../../../data/placeName'
import { Icon } from '../../ui/icons'
import { AskCard, PhotoStage } from './Ask'
import { CardView, type Answer } from './Cards'
import { DeckIssues } from './Deck'
import { Block } from './Blocks'
import { PlaceStage } from './Places'

// A bot turn shows what it is doing (steps from the server's progress events: open while it works so the user sees how it
// reads the message, folded to one quiet line once the turn ends), its words, and at most one question.

export type Msg =
  | { key: string; who: 'me'; text: string; photo?: string; files?: string[] }
  | { key: string; who: 'bot'; say: string; steps: Step[]; sources: WebSource[]; card: Card | Deck | null; answered: string | null; issues?: DeckIssue[]
      live: boolean; t0: number; t1?: number; places?: ChatPlaces[]; blocks?: ResultBlock[]; replies?: string[] }

export const botMsg = (key: string, patch: Partial<Extract<Msg, { who: 'bot' }>> = {}): Msg =>
  ({ key, who: 'bot', say: '', steps: [], sources: [], card: null, answered: null, live: false, t0: Date.now(), ...patch })

// What the block is doing, in one line: how many things it has written down from the message so far, or what it
// reads. The count grows live as each item streams in (one line per kind, the user's own words on it). Once the turn
// ends it folds to one quiet line ("Đã xử lý trong 13 giây"), so the chat stays short; a click opens it again.
function headline(steps: Step[], live: boolean, secs: number) {
  const noted = steps.filter((s) => s.id.startsWith('rec:') || s.id.startsWith('dish:') || s.id.startsWith('kind:')).length
  if (!live) return `Đã xử lý trong ${secs < 60 ? `${secs} giây` : `${Math.floor(secs / 60)} phút ${secs % 60} giây`}`
  if (steps.some((s) => s.id.startsWith('web') && s.status === 'run')) return 'Đang tìm hiểu trên web'
  if (noted) return `Đang ghi nhận ${noted} ý từ tin nhắn`
  return steps.some((s) => s.id === 'split') ? 'Đang tách các ý trong tin nhắn' : 'Đang đọc tin nhắn'
}

// What is worth showing of the server's progress: the interpretation (what it noted from the message, what it looks for, what it
// checks on the web, weather and distance) and not the plumbing every turn repeats ("read the message", "split the ideas", the
// generic "find places"). The header still says which phase it is in.
const PLUMBING = new Set(['read', 'split', 'cues'])
const worth = (s: Step) => !PLUMBING.has(s.id) && !s.id.startsWith('find:')

function Steps({ steps, sources, live, secs }: { steps: Step[]; sources: WebSource[]; live: boolean; secs: number }) {
  const shown = steps.filter(worth)
  const [open, setOpen] = useState(true)
  useEffect(() => {
    if (live) return setOpen(true)
    const t = window.setTimeout(() => setOpen(false), 700)
    return () => window.clearTimeout(t)
  }, [live])
  if (!live && !shown.length) return null // nothing worth opening once the turn is over
  return (
    <div className={`tg-cx__think ${open ? 'is-open' : ''} ${live ? 'is-run' : ''}`}>
      <button type="button" className="tg-cx__think-h" aria-expanded={open && shown.length > 0} onClick={() => setOpen((o) => !o)}>
        {live && <span className="tg-cx__spark"><Icon name="sparkle" size={17} /></span>}
        <span className={live ? 'tg-cx__shimmer' : ''} role="status" aria-atomic="true">{headline(steps, live, secs)}</span>
        {shown.length > 0 && <Icon name="chevronDown" size={15} className="tg-cx__chev" />}
      </button>
      <div className="tg-cx__think-b"><div>
        <ol className="tg-cx__steps">
          {shown.map((s) => (
            <li key={s.id} className={`is-${s.status}`}>
              <i className="tg-cx__dot" aria-hidden="true" />
              {(() => {
                const at = s.label.indexOf(' · ')
                return at < 0 ? <b>{s.label}</b> : <><b>{s.label.slice(0, at)}</b><span className="tg-cx__said">{s.label.slice(at + 3)}</span></>
              })()}
              {s.id.startsWith('web') && sources.length > 0 && (
                <span className="tg-cx__det">{sources.map((x, i) => <a key={x.url} className="tg-cx__tag" style={{ '--d': `${i * 120}ms` } as CSSProperties} href={x.url} target="_blank" rel="noopener noreferrer">{x.domain}</a>)}</span>
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
            {m.say && <p>{tidyText(m.say)}</p>}
            {tab && <p className="tg-cx__say-ask">{tab.question}</p>}
          </div>
        )}
        {m.places?.map((row, i) => <PlaceStage key={i} row={row} busy={busy} autoOpen={m.live} onLike={onLike} />)}
        {m.blocks?.map((b, i) => <Block key={i} block={b} busy={busy} autoOpen={m.live} onLike={onLike} />)}
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
