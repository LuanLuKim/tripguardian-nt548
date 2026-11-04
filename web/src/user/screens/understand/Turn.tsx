import type { Card, ChatPlaces, Deck, DeckAnswers, DeckIssue, ResultBlock, Step, WebSource } from '../../tu/types'
import { Icon } from '../../ui/icons'
import { AskCard, PhotoStage } from './Ask'
import { CardView, type Answer } from './Cards'
import { DeckIssues } from './Deck'
import { Block } from './Blocks'
import { PlaceStage } from './Places'

// A bot turn shows its final words and at most one question; processing feedback is transient.

export type Msg =
  | { key: string; who: 'me'; text: string; photo?: string; files?: string[] }
  | { key: string; who: 'bot'; say: string; steps: Step[]; sources: WebSource[]; card: Card | Deck | null; answered: string | null; issues?: DeckIssue[]
      live: boolean; t0: number; t1?: number; places?: ChatPlaces[]; blocks?: ResultBlock[]; replies?: string[] }

export const botMsg = (key: string, patch: Partial<Extract<Msg, { who: 'bot' }>> = {}): Msg =>
  ({ key, who: 'bot', say: '', steps: [], sources: [], card: null, answered: null, live: false, t0: Date.now(), ...patch })

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
  const tab = m.card?.kind === 'deck' ? m.card.tabs[0] : undefined
  return (
    <li className="tg-cx__m is-bot" aria-busy={m.live}>
      <div className="tg-cx__stack">
        {m.live && <p className="tg-cx__say is-wait" role="status"><span className="tg-dots" aria-hidden="true"><i /><i /><i /></span><span className="tg-sr">Đang xử lý</span></p>}
        {(m.say || tab) && (
          <div className="tg-cx__say">
            {m.say && <p>{m.say}</p>}
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
