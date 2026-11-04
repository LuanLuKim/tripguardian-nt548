import { useEffect, useReducer, useRef, useState, type Dispatch, type KeyboardEvent, type SetStateAction } from 'react'
import type { ChatPlace, TagNode } from '../tu/types'
import { CardImg, preloadPhotos } from '../ui/common'
import { Icon } from '../ui/icons'
import { openPlace } from '../ui/PlaceSheet'
import { StageFrame, StageRing, stageKeys, type StageCard } from '../screens/understand/Ask'
import { placeCard } from '../screens/understand/Places'
import { photoOf, ROOT, Tree } from './tree'

// The tag stage (docs/TRIP_UNDERSTANDING.md §19): tags, subtags and places are three levels of one ring of big photo cards.
// A tap on a tag or subtag folds the ring into that card and fans its children out (no model call, no chat turn); Esc or
// Back goes up. What the user picked lives in the block (Subtags.tsx), so it survives closing and reopening.

export interface Pick { key: string; kind: 'place' | 'kind'; id: string; label: string; photo: string | null; via: string[] }
export interface Nav { path: string[]; ats: Record<string, number> }

const reduced = () => matchMedia('(prefers-reduced-motion: reduce)').matches
const wait = (ms: number) => new Promise<void>(r => window.setTimeout(r, ms))
export const pickKey = (kind: Pick['kind'], id: string) => `${kind === 'place' ? 'p' : 'k'}:${id}`
const startAt = (n: number) => (n > 1 && n <= 7 ? Math.floor((n - 1) / 2) : 0)

export function summary(picks: Pick[]) {
  const places = picks.filter(p => p.kind === 'place').length
  const kinds = picks.length - places
  return [places ? `${places} nơi` : '', kinds ? `${kinds} kiểu` : ''].filter(Boolean).join(', ')
}

export function TagStage({ tree, nav, picks, leaving, kicker, close, onPlace, onKind, onRemove, onSeen }: {
  tree: Tree; nav: { current: Nav }; picks: Pick[]; leaving: boolean; kicker: string; close: (then?: () => void) => void
  onPlace: (card: ChatPlace, via: string[]) => void
  onKind: (node: TagNode, via: string[]) => void
  onRemove: (pick: Pick) => void
  onSeen: (nodes: TagNode[], via: string[]) => void
}) {
  const [, tick] = useReducer((x: number) => x + 1, 0)
  const [phase, setPhase] = useState<'idle' | 'leave'>('idle')
  const [dir, setDir] = useState<'down' | 'up'>('down')
  const [loading, setLoading] = useState<string | null>(null)
  const [error, setError] = useState('')
  const panel = useRef<HTMLDivElement>(null)
  const path = nav.current.path
  const here = path.length ? path[path.length - 1] : ROOT
  const level = tree.get(here)
  const nodes = level?.nodes ?? []
  const at = Math.min(Math.max(0, nodes.length - 1), nav.current.ats[here] ?? startAt(nodes.length))
  const setAt: Dispatch<SetStateAction<number>> = v => {
    const next = typeof v === 'function' ? v(at) : v
    nav.current.ats[here] = Math.max(0, Math.min(nodes.length - 1, next))
    tick()
  }
  const front = nodes[at]
  const busy = phase === 'leave'

  // A level the user left open before the tree was rebuilt is read again; one already seen is there at once.
  useEffect(() => {
    if (level) return
    tree.load(here).then(tick, () => { nav.current.path = []; tick() })
  }, [here]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (level) onSeen(level.nodes, path) }, [level]) // eslint-disable-line react-hooks/exhaustive-deps
  // The card in front and its neighbours read their children now, so a tap never waits.
  useEffect(() => {
    for (const n of [nodes[at], nodes[at + 1], nodes[at - 1]]) {
      if (n && n.has_children) tree.load(n.ref).then(tick, () => {})
    }
    preloadPhotos(nodes.slice(Math.max(0, at - 2), at + 4).map(photoOf))
  }, [here, at, level]) // eslint-disable-line react-hooks/exhaustive-deps

  const swap = async (d: 'down' | 'up', change: () => void) => {
    setDir(d)
    if (!reduced()) { setPhase('leave'); await wait(d === 'down' ? 230 : 190) }
    change()
    setPhase('idle')
    tick()
  }
  const down = async (node: TagNode) => {
    if (busy || loading) return
    setError('')
    if (!tree.get(node.ref)) {
      setLoading(node.ref)
      try { await tree.load(node.ref) } catch { setError('Chưa mở được mục này, bạn thử lại nhé.'); setLoading(null); return }
      setLoading(null)
    }
    await swap('down', () => nav.current.path.push(node.ref))
  }
  const up = (to = path.length - 1) => {
    if (busy) return
    if (to < 0) { close(); return }
    setError('')
    swap('up', () => { nav.current.path = path.slice(0, to) })
  }
  const view = (c: ChatPlace) => close(() => openPlace(c.id))
  const wished = (n: TagNode) => picks.some(p => p.key === pickKey('kind', n.ref))
  const liked = (n: TagNode) => picks.some(p => p.key === pickKey('place', n.id!))
  const open = (n: TagNode | undefined) => { if (n) (n.kind === 'place' ? view(n.card!) : down(n)) }
  const choose = (n: TagNode | undefined) => {
    if (!n || busy) return
    if (n.kind === 'place') onPlace(n.card!, path)
    else if (n.kind !== 'all') onKind(n, path)
  }
  const inside = (n: TagNode) => picks.filter(p => p.via.includes(n.ref)).length
  const keys = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Backspace') { e.preventDefault(); up(); return }
    stageKeys(e, panel, nodes.length, setAt, () => up(), key => (key === 'Enter' ? open(front) : choose(front)))
  }

  const cards: StageCard[] = nodes.map((n, i) => {
    if (n.kind === 'place') return placeCard(n.card!, liked(n))
    const on = wished(n)
    const picked = inside(n)
    return {
      id: n.ref, photo: n.cover, alt: n.label, title: n.label, on, deck: true, loading: loading === n.ref,
      line: <>
        <small><Icon name="pin" size={13} />{n.count.toLocaleString('vi-VN')} nơi</small>
        <small>{n.kind === 'tag' ? 'Mở các kiểu bên trong' : n.kind === 'all' ? 'Mọi nơi của mục này' : 'Xem từng nơi'}</small>
      </>,
      badge: picked ? <span className="tg-stage__badge"><Icon name="check" size={12} strokeWidth={2.6} />{picked} đã chọn</span> : null,
      extra: n.kind === 'all' ? null : <button type="button" className={`tg-stage__wish ${on ? 'is-on' : ''}`} tabIndex={i === at ? 0 : -1} aria-pressed={on}
        onClick={e => { e.stopPropagation(); setAt(i); choose(n) }}><Icon name={on ? 'check' : 'plus'} size={14} strokeWidth={2.4} />{on ? 'Thích cả kiểu' : 'Thích cả kiểu này'}</button>,
      pick: <Icon name="chevronRight" size={20} strokeWidth={2.2} />, pickLabel: `Mở ${n.label}`,
    }
  })

  const crumbs = <nav className="tg-crumbs" aria-label="Bạn đang ở đâu">
    {[ROOT, ...path].map((ref, k) => {
      const name = k === 0 ? 'Tất cả' : tree.get(ref)?.label ?? '…'
      const last = k === path.length
      return <span key={ref || 'root'}>
        {k > 0 && <Icon name="chevronRight" size={12} />}
        {last ? <b aria-current="location">{name}</b> : <button type="button" onClick={() => up(k)}>{name}</button>}
      </span>
    })}
  </nav>
  const places = picks.filter(p => p.kind === 'place').length
  const why = error || (here === ROOT ? 'Chọn nhiều kiểu cũng được, mình gom lại cho bạn.' : `${level?.count.toLocaleString('vi-VN') ?? ''} nơi`)
  return <StageFrame leaving={leaving} kicker={kicker} question={level?.label ?? '…'} why={why} crumbs={crumbs} onBack={path.length ? () => up() : undefined}
    onClose={() => close()} onKeyDown={keys} panel={panel}>
    {level ? <StageRing key={here} cards={cards} at={at} setAt={setAt} busy={busy} label="Các lựa chọn" multi tree={{ phase, dir }}
      prevLabel="Thẻ trước" nextLabel="Thẻ sau" hint="← → xoay · Enter mở · Space chọn · Esc lên một cấp"
      onFront={i => open(nodes[i])} onPick={i => (nodes[i].kind === 'place' ? choose(nodes[i]) : open(nodes[i]))} />
      : <div className="tg-stage__ring is-tree" aria-busy="true" />}
    <footer className="tg-stage__foot tg-basket">
      <ul className="tg-basket__items" aria-label="Bạn đã chọn">
        {picks.map(p => <li key={p.key} className={p.kind === 'kind' ? 'is-kind' : ''}>
          {p.kind === 'place'
            ? <span className="tg-basket__thumb" title={p.label}>{p.photo ? <CardImg src={p.photo} alt={p.label} /> : <i />}</span>
            : <span className="tg-basket__kind"><Icon name="heart" size={12} />{p.label}</span>}
          <button type="button" aria-label={`Bỏ chọn ${p.label}`} onClick={() => onRemove(p)}><Icon name="x" size={11} strokeWidth={2.6} /></button>
        </li>)}
        {!picks.length && <li className="tg-basket__none">Bấm tim để lưu nơi bạn thích, hoặc “Thích cả kiểu này”. Không bắt buộc chọn.</li>}
      </ul>
      <button type="button" className="tg-btn tg-btn--primary" onClick={() => close()}>{picks.length ? `Xong · ${places ? `${places} nơi` : summary(picks)}` : 'Xong'} <Icon name="check" size={16} /></button>
    </footer>
  </StageFrame>
}
