import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { useSnapshot } from '../../data/store'
import { go } from '../ui/common'
import { Icon } from '../ui/icons'
import { info } from '../lib'
import { searchPlaces, searchTopics, useStore } from './data'
import { hubHref, PlacePic, Rating } from './parts'
import '../css/posts.css'

const PLACES_SHOWN = 3
const TOPICS_SHOWN = 3
const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1)

type Row = { key: string; run: () => void }

// The search of the posts. Short on purpose (docs/design/mock/designs/search-blog): the places that have posts, with the one or
// two facts that make someone click (a photo, the name, the rating, how many posts), then the topics. It does not complete what is
// typed: Enter opens the results for the exact words.
// On the home page the same box also plans trips: `onType` follows the text and `onEnter` takes Enter (the trip chat), with a last row
// saying so; the places and topics still open the posts.
interface Props { value: string; onType?: (v: string) => void; onEnter?: (v: string) => void; placeholder?: string; tour?: string; className?: string }
export function PostSearch({ value, onType, onEnter, placeholder = 'Tìm địa điểm, chủ đề, bài viết', tour, className = '' }: Props) {
  const store = useStore()
  const { snap } = useSnapshot() // places and posts are known once the snapshot is in
  const [text, setText] = useState(value)
  const [open, setOpen] = useState(false)
  const [hi, setHi] = useState(-1)
  const box = useRef<HTMLDivElement>(null)
  const input = useRef<HTMLInputElement>(null)
  const list = useId()
  useEffect(() => { setText(value) }, [value])
  useEffect(() => {
    const away = (e: PointerEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false) }
    addEventListener('pointerdown', away)
    return () => removeEventListener('pointerdown', away)
  }, [])
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      const el = document.activeElement
      if (e.key === '/' && !(el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement || (el as HTMLElement | null)?.isContentEditable) && !document.querySelector('[role="dialog"]')) { e.preventDefault(); input.current?.focus() }
    }
    addEventListener('keydown', key)
    return () => removeEventListener('keydown', key)
  }, [])

  const q = text.trim()
  const places = useMemo(() => (q ? searchPlaces(q, true) : []), [q, store, snap])
  const topics = useMemo(() => (q ? searchTopics(q, true) : []), [q, store, snap])
  const shownPlaces = places.slice(0, PLACES_SHOWN)
  const shownTopics = topics.slice(0, TOPICS_SHOWN)
  const more = places.length - shownPlaces.length
  const submit = (v = q) => { setOpen(false); go(hubHref({ q: v })) }
  const plan = () => { setOpen(false); onEnter?.(q) }

  const rows: Row[] = [
    ...shownPlaces.map((h) => ({ key: `p:${h.placeId}`, run: () => { setOpen(false); go(hubHref({ q, place: h.placeId })) } })),
    ...shownTopics.map((t) => ({ key: `t:${t.tag}`, run: () => { setText(t.tag); onType?.(t.tag); submit(t.tag) } })),
    ...(onEnter && q ? [{ key: 'plan', run: plan }] : []),
  ]
  const idOf = (i: number) => `${list}-${i}`
  const show = open && q.length > 0
  const empty = show && !places.length && !topics.length && !onEnter

  return (
    <div className={`tg-bp-search ${className}`} ref={box} data-tour={tour}>
      <form className={`tg-bp-search__box ${show ? 'is-open' : ''}`} role="search" onSubmit={(e) => { e.preventDefault(); if (hi >= 0 && rows[hi]) rows[hi].run(); else if (q) (onEnter ? plan() : submit()) }}>
        <Icon name="search" size={17} />
        <label className="tg-sr" htmlFor={`${list}-in`}>Tìm địa điểm và bài viết</label>
        <input
          id={`${list}-in`} ref={input} value={text} maxLength={120} autoComplete="off" spellCheck={false} placeholder={placeholder}
          role="combobox" aria-expanded={show} aria-controls={list} aria-autocomplete="list" aria-activedescendant={hi >= 0 ? idOf(hi) : undefined}
          onFocus={() => setOpen(true)}
          onChange={(e) => { setText(e.target.value); onType?.(e.target.value); setOpen(true); setHi(-1) }}
          onKeyDown={(e) => {
            if (e.key === 'Escape') { if (show) { setOpen(false); e.stopPropagation() } else input.current?.blur() }
            else if (e.key === 'ArrowDown' && rows.length) { e.preventDefault(); setOpen(true); setHi((i) => (i + 1) % rows.length) }
            else if (e.key === 'ArrowUp' && rows.length) { e.preventDefault(); setHi((i) => (i <= 0 ? rows.length - 1 : i - 1)) }
          }}
        />
        {text ? <button type="button" className="tg-bp-search__x" aria-label="Xóa" onClick={() => { setText(''); onType?.(''); setHi(-1); input.current?.focus(); if (value && !onType) go('/posts') }}><Icon name="x" size={13} /></button> : <kbd aria-hidden="true">/</kbd>}
      </form>

      {show && (
        <div className="tg-bp-dd" id={list} role="listbox" aria-label="Kết quả tìm">
          {empty && <p className="tg-bp-dd__none">Chưa có bài viết nào khớp “{q}”. Nhấn Enter để xem tất cả, hoặc <button type="button" onClick={() => go('/posts/new')}>viết bài đầu tiên</button>.</p>}
          {shownPlaces.length > 0 && (
            <section>
              <header><h2>Địa điểm</h2>{more > 0 && <button type="button" onClick={() => submit()}>Xem {more} nơi khác</button>}</header>
              {shownPlaces.map((h, i) => {
                const p = info(h.placeId)
                return (
                  <button key={h.placeId} id={idOf(i)} type="button" role="option" aria-selected={hi === i} className={`tg-bp-dd__row ${hi === i ? 'is-hi' : ''}`} onMouseEnter={() => setHi(i)} onClick={rows[i].run}>
                    <span className="tg-bp-dd__ph"><PlacePic id={h.placeId} /></span>
                    <span className="tg-bp-dd__tx"><b>{p?.name}</b><small><Rating value={p?.rating} />{p?.rating ? ' · ' : ''}{p?.area}</small></span>
                    <span className="tg-bp-dd__n">{h.posts.length} bài</span>
                  </button>
                )
              })}
            </section>
          )}
          {shownTopics.length > 0 && (
            <section>
              <header><h2>Chủ đề</h2></header>
              {shownTopics.map((t, j) => {
                const i = shownPlaces.length + j
                return (
                  <button key={t.tag} id={idOf(i)} type="button" role="option" aria-selected={hi === i} className={`tg-bp-dd__row ${hi === i ? 'is-hi' : ''}`} onMouseEnter={() => setHi(i)} onClick={rows[i].run}>
                    <span className="tg-bp-dd__ph is-tag"><Icon name="flame" size={20} /></span>
                    <span className="tg-bp-dd__tx"><b>{cap(t.tag)}</b><small>{t.count} bài viết</small></span>
                  </button>
                )
              })}
            </section>
          )}
          {onEnter && q && (() => {
            const i = rows.length - 1
            return (
              <section>
                <button id={idOf(i)} type="button" role="option" aria-selected={hi === i} className={`tg-bp-dd__row ${hi === i ? 'is-hi' : ''}`} onMouseEnter={() => setHi(i)} onClick={plan}>
                  <span className="tg-bp-dd__ph is-tag"><Icon name="sparkle" size={20} /></span>
                  <span className="tg-bp-dd__tx"><b>Lên chuyến đi “{q}”</b><small>Nhấn Enter để kể cho trợ lý</small></span>
                </button>
              </section>
            )
          })()}
        </div>
      )}
    </div>
  )
}
