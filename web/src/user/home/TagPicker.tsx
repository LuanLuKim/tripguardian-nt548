import { useEffect, useState } from 'react'
import { CardImg } from '../ui/common'
import { Icon } from '../ui/icons'
import { loadSubs, loadTopics, type Sub, type Topic } from './tagTopics'
import '../css/tagpick.css'

// "Gu của chuyến": photo tiles for the tags, and under the open tile its subtags as chips. The text of the box stays the one
// source of truth: a pick adds its words as one comma-separated phrase (a second tap takes exactly that phrase out), so what the
// user reads is what is sent, and "Lẩu" never matches inside "Lẩu gà".
const parts = (text: string) => text.split(',').map((s) => s.trim()).filter(Boolean)
export const hasToken = (text: string, token: string) => parts(text).includes(token)
export const dropToken = (text: string, ...tokens: string[]) => parts(text).filter((p) => !tokens.includes(p)).join(', ')
export const toggleToken = (text: string, token: string) => (hasToken(text, token) ? dropToken(text, token) : [...parts(text), token].join(', '))

export function TagPicker({ text, setText }: { text: string; setText: (fn: (t: string) => string) => void }) {
  const [topics, setTopics] = useState<Topic[] | null>(null)
  const [open, setOpen] = useState<string | null>(null)
  const [known, setKnown] = useState<Record<string, Sub[]>>({}) // subtags seen so far, so a tile knows its subtags are picked
  useEffect(() => { let live = true; void loadTopics().then((t) => { if (live) setTopics(t) }); return () => { live = false } }, [])
  useEffect(() => {
    if (!open || known[open]) return
    let live = true
    void loadSubs(open).then((s) => { if (live) setKnown((k) => ({ ...k, [open]: s })) })
    return () => { live = false }
  }, [open, known])
  const words = (t: Topic) => [t.label, ...(known[t.ref] ?? []).map((s) => s.label)]
  const on = (t: Topic) => words(t).some((w) => hasToken(text, w))
  const current = topics?.find((t) => t.ref === open) ?? null
  const subs = current ? known[current.ref] : undefined
  const tap = (t: Topic) => {
    if (open === t.ref) { setText((x) => dropToken(x, ...words(t))); setOpen(null); return } // a second tap: out again
    setOpen(t.ref)
    if (!on(t)) setText((x) => toggleToken(x, t.label))
  }
  // A subtag says more than its tag ("Quán cà phê săn mây" over "Săn mây"): picking one takes the tag's own words out.
  const pick = (t: Topic, s: Sub) => setText((x) => toggleToken(dropToken(x, t.label), s.label))
  return (
    <section className="tg-tp" aria-label="Gu của chuyến">
      <h4 className="tg-tp__h">Chọn gu cho chuyến</h4>
      <ul className="tg-tp__grid">
        {(topics ?? Array.from({ length: 8 }, () => null)).map((t, i) => t ? (
          <li key={t.ref}>
            <button type="button" className={`tg-tp__tile ${open === t.ref ? 'is-open' : ''} ${on(t) ? 'is-on' : ''}`} aria-pressed={on(t)} aria-expanded={open === t.ref} onClick={() => tap(t)}>
              {t.cover ? <CardImg src={t.cover} alt="" /> : <i aria-hidden="true" />}
              <span className="tg-tp__shade" aria-hidden="true" />
              <span className="tg-tp__tick" aria-hidden="true"><Icon name="check" size={13} /></span>
              <span className="tg-tp__name">{t.label}</span>
            </button>
          </li>
        ) : <li key={i}><span className="tg-tp__tile is-wait" aria-hidden="true" /></li>)}
      </ul>
      {current && (
        <div className="tg-tp__subs" role="group" aria-label={`Kiểu của ${current.label}`}>
          <p>{subs === undefined ? 'Đang tìm các kiểu…' : subs.length ? <>Trong <b>{current.label}</b>, bạn thích kiểu nào?</> : <><b>{current.label}</b> đã được thêm vào chuyến.</>}</p>
          {subs?.length ? <div className="tg-tp__chips">{subs.map((s) => <button key={s.id} type="button" aria-pressed={hasToken(text, s.label)} onClick={() => pick(current, s)}>{hasToken(text, s.label) && <Icon name="check" size={13} />}{s.label}</button>)}</div> : null}
          {subs === undefined && <div className="tg-tp__chips" aria-hidden="true">{[104, 134, 118, 92].map((w) => <span key={w} className="is-wait" style={{ width: w }} />)}</div>}
        </div>
      )}
    </section>
  )
}
