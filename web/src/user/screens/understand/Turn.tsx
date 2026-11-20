import { useEffect, useRef, useState, type CSSProperties } from 'react'
import type { Card, ChatPlaces, Deck, DeckAnswers, DeckIssue, ResultBlock, Step, WebSource } from '../../tu/types'
import { tidyText } from '../../../data/placeName'
import { useAccount } from '../../account'
import { BotAvatar, Icon } from '../../ui/icons'
import { AskSheet, PhotoStage } from './Ask'
import { CardView, type Answer } from './Cards'
import { DeckIssues } from './Deck'
import { Block } from './Blocks'
import { PlaceStage } from './Places'
import { info } from '../../lib'
import { openPlace } from '../../ui/PlaceSheet'
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

// What is slow is said, not hidden: a step that has run a while shows its seconds, and a cold start of the search says so.
const COLD = ' · đang khởi động'
const cold = (label: string) => (label.includes(COLD) ? label.slice(label.indexOf(COLD) + 3) : '')

function headline(steps: Step[], live: boolean, secs: number, sources: WebSource[], since: (id: string) => number) {
  if (!live) return `Đã xử lý trong ${secs < 60 ? `${secs} giây` : `${Math.floor(secs / 60)} phút ${secs % 60} giây`}`
  if (steps.some((s) => s.id.startsWith('web') && s.status === 'run')) return sources.length ? `Đang tìm kiếm ${sources.length} trang web` : 'Đang tìm kiếm trên web'
  const now = [...steps].reverse().find((s) => s.status === 'run')
  if (!now) return steps.length ? 'Đang soạn câu trả lời' : 'Đang đọc tin nhắn của bạn'
  const wait = since(now.id)
  return `${doing(now.label)}${wait >= 4 ? ` (${wait} giây)` : ''}`
}

// Every step the server reports is shown, the moment it starts (reading the message, each lookup, each wait on the web or the
// search), so the person always sees what the assistant is doing. Open while it works, folded to one quiet line once the turn ends.
function Steps({ steps, sources, live, secs }: { steps: Step[]; sources: WebSource[]; live: boolean; secs: number }) {
  const shown = steps
  const [manual, setManual] = useState<boolean | null>(null) // null: follow the turn (open while it runs, folded after); a click decides
  const open = manual ?? live
  const began = useRef(new Map<string, number>())
  const [, tick] = useState(0)
  useEffect(() => {
    if (!live) return
    const t = window.setInterval(() => tick((n) => n + 1), 1000)
    return () => window.clearInterval(t)
  }, [live])
  for (const s of steps) {
    if (s.status === 'run' && !began.current.has(s.id)) began.current.set(s.id, Date.now())
    if (s.status !== 'run') began.current.delete(s.id)
  }
  const since = (id: string) => Math.round((Date.now() - (began.current.get(id) ?? Date.now())) / 1000)
  if (!live && !shown.length) return null // nothing worth opening once the turn is over
  return (
    <div className={`tg-cx__think ${open ? 'is-open' : ''} ${live ? 'is-run' : ''}`}>
      <button type="button" className="tg-cx__think-h" aria-expanded={open && shown.length > 0} onClick={() => setManual(!open)}>
        <span className={live ? 'tg-cx__shimmer' : ''} role="status" aria-atomic="true">{headline(steps, live, secs, sources, since)}</span>
        {live && <span className="tg-dots" aria-hidden="true"><i /><i /><i /></span>}
        {shown.length > 0 && <Icon name="chevronDown" size={15} className="tg-cx__chev" />}
      </button>
      <div className="tg-cx__think-b"><div>
        <ol className="tg-cx__steps">
          {shown.map((s) => (
            <li key={s.id} className={`is-${s.status}`}>
              {(() => {
                const at = s.label.indexOf(' · ')
                const note = cold(s.label)
                const head = at < 0 ? s.label : s.label.slice(0, at)
                const said = at < 0 || note ? '' : s.label.slice(at + 3)
                return <><b>{head}{s.status === 'run' && since(s.id) >= 4 ? ` · ${since(s.id)} giây` : ''}</b>{said && <span className="tg-cx__said">{said}</span>}{note && <span className="tg-cx__said">{note}</span>}</>
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

// The person's own face beside their lines: their photo, else the first letter of their name.
function MeAvatar() {
  const account = useAccount()
  const initial = (account?.guest ? '' : (account?.name || account?.email || '').trim()[0]) || ''
  return <span className="tg-cx__me" aria-hidden="true">
    {account?.avatar ? <img src={account.avatar} alt="" referrerPolicy="no-referrer" /> : initial ? initial.toLocaleUpperCase('vi-VN') : <Icon name="user" size={18} />}
  </span>
}

export function Turn({ m, busy, onAnswer, onDeck, onText, onPhoto, onLike, last = false, openCard = 0 }: { m: Msg; busy: boolean; onAnswer: (m: Msg, ...a: Parameters<Answer>) => void; onDeck: (m: Msg, answers: DeckAnswers, shown: string) => void; onText: (text: string) => void; onPhoto: () => void; onLike: (id: string, on: boolean) => void; last?: boolean; openCard?: number }) {
  if (m.who === 'me')
    return (
      <li className="tg-cx__m is-me">
        <div className={`tg-cx__bub ${m.photo ? 'is-img' : ''}`}>
          {m.photo && <img src={m.photo} alt="Ảnh bạn gửi" />}
          {m.text && <p>{m.text}</p>}
          {m.files?.length ? <p className="tg-cx__files">{m.files.map((n) => <span key={n}><Icon name="clip" size={13} />{n}</span>)}</p> : null}
        </div>
        <MeAvatar />
      </li>
    )
  const secs = Math.max(1, Math.round(((m.t1 ?? Date.now()) - m.t0) / 1000))
  const waiting = m.live && !m.say && !m.steps.length
  const tab = m.card?.kind === 'deck' ? m.card.tabs[0] : undefined // its question is only the fallback: the assistant's own line leads
  // the names of the reply's own places, which the words then link to
  const named = (m.places ?? []).flatMap((r) => r.cards.map((c) => ({ id: c.id, name: c.name ?? info(c.id)?.name ?? '' })))
  return (
    <li className="tg-cx__m is-bot" aria-busy={m.live}>
      <BotAvatar size={36} live={m.live} />
      <div className="tg-cx__stack">
        {(m.steps.length > 0 || waiting) && <Steps steps={m.steps} sources={m.sources} live={m.live} secs={secs} />}
        {(m.say || tab?.question) && (
          <div className="tg-cx__say">
            {m.say && <Rich text={tidyText(m.say)} places={named} onPlace={(id, el) => openPlace(id, el)} />}
            {tab?.question && !m.say && <p className="tg-cx__say-ask">{tab.question}</p>}
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
            ? // a photo card of a new aspect is offered under the reply, never opened over it: the user taps it (or says yes)
            <PhotoStage key={JSON.stringify(m.card)} deck={m.card} busy={busy} openSignal={openCard} autoOpen={tab!.kind !== 'drill' && !m.blocks?.some(b => b.kind === 'tags') && !m.places?.length} onAnswer={(answers, shown) => onDeck(m, answers, shown)} onText={onText} />
            // the open question floats over the blurred chat once the turn has finished; an older one waits for the newest
            : last && !m.live ? <AskSheet key={JSON.stringify(m.card)} deck={m.card} busy={busy} issues={m.issues} onAnswer={(answers, shown) => onDeck(m, answers, shown)} onText={onText} /> : null)
          : <CardView card={m.card} busy={busy} onAnswer={(input, shown) => onAnswer(m, input, shown)} onPhoto={onPhoto} />)}
        {(!m.card || m.answered) && <DeckIssues issues={m.issues ?? []} />}
      </div>
    </li>
  )
}
