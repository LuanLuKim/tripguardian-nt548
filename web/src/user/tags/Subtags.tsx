import { useRef, useState } from 'react'
import { useSnapshot } from '../../data/store'
import type { ChatPlace, TagNode, TagsBlock } from '../tu/types'
import { useStage } from '../screens/understand/Ask'
import { CardImg } from '../ui/common'
import { Icon } from '../ui/icons'
import { useTagEnv } from './env'
import { pickKey, summary, TagStage, type Nav, type Pick } from './TagStage'
import { rootLevel, Tree } from './tree'

// tag -> subtag -> place (docs/TRIP_UNDERSTANDING.md §19): a reply with a tags block opens one photo stage for all three
// levels; the chat keeps this one line to open it again exactly where the user left, picks included. The backend decides
// the shape (labels, counts, covers, places); nothing is computed here. Picking never asks the model and never blocks.
export function SubtagBlock({ block, autoOpen, onLike }: {
  block: TagsBlock; autoOpen?: boolean; onLike: (id: string, on: boolean) => void
}) {
  useSnapshot() // photos and ratings of the cards come from the web's snapshot once it lands
  const env = useTagEnv()
  const { open, setOpen, leaving, close } = useStage(!!autoOpen)
  const [picks, setPicks] = useState<Pick[]>([])
  const tree = useRef<Tree>(null as unknown as Tree)
  if (!tree.current || tree.current.block !== block || tree.current.sid !== env.sid) tree.current = new Tree(env.sid, block)
  const nav = useRef<Nav>({ path: [], ats: {} })
  const sig = block.sig ?? ''
  const root = rootLevel(block)
  const set = (fn: (p: Pick[]) => Pick[]) => setPicks(fn)

  const add = (pick: Pick) => set(p => (p.some(x => x.key === pick.key) ? p : [...p, pick]))
  const drop = (key: string) => set(p => p.filter(x => x.key !== key))
  const place = (c: ChatPlace, via: string[]) => {
    const key = pickKey('place', c.id)
    const on = !picks.some(p => p.key === key)
    if (on) add({ key, kind: 'place', id: c.id, label: c.name ?? 'Nơi này', photo: c.photos[0] ?? null, via })
    else drop(key)
    if (env.sid) env.like(c.id, on)
    else onLike(c.id, on)
  }
  const kind = (n: TagNode, via: string[]) => {
    const key = pickKey('kind', n.ref)
    const on = !picks.some(p => p.key === key)
    if (on) add({ key, kind: 'kind', id: n.ref, label: n.label, photo: n.cover, via })
    else drop(key)
    env.wish(sig, n.ref, on)
  }
  const remove = (p: Pick) => {
    drop(p.key)
    if (p.kind === 'place') env.like(p.id, false)
    else env.wish(sig, p.id, false)
  }
  // What the server already holds (a place liked before, a kind wished before) joins the basket as its level is seen.
  const seen = (nodes: TagNode[], via: string[]) => {
    const fresh: Pick[] = []
    for (const n of nodes) {
      if (n.kind === 'place' && n.card?.liked) fresh.push({ key: pickKey('place', n.id!), kind: 'place', id: n.id!, label: n.label, photo: n.card.photos[0] ?? null, via })
      else if (n.wished && n.kind !== 'all') fresh.push({ key: pickKey('kind', n.ref), kind: 'kind', id: n.ref, label: n.label, photo: n.cover, via })
    }
    set(p => {
      const gone = new Set(p.map(x => x.key))
      const more = fresh.filter(f => !gone.has(f.key))
      return more.length ? [...p, ...more] : p
    })
  }
  const tags = block.level === 'tags'
  const covers = root.nodes.slice(0, 3).map(n => n.cover)
  const chosen = summary(picks)
  const head = block.title ?? (tags ? 'Chọn hướng bạn thích' : `${block.total} nơi hợp ý bạn, chia theo kiểu`)
  return <section className="tg-sub" aria-label="Các kiểu gợi ý">
    <button type="button" className="tg-stage__reopen tg-sub__row" onClick={() => setOpen(true)}>
      <span className="tg-stage__thumbs" aria-hidden="true">{covers.map((u, i) => (u ? <CardImg key={u} src={u} alt="" /> : <i key={i} />))}</span>
      <span><b>{head}</b><small>{chosen ? `${chosen} đã chọn · bấm để mở lại` : `${root.nodes.filter(n => n.kind !== 'all').length} ${tags ? 'hướng' : 'kiểu'} có ảnh thật · bấm để xem`}</small></span>
      <Icon name="chevronRight" size={18} />
    </button>
    {open && <TagStage tree={tree.current} nav={nav} picks={picks} leaving={leaving} kicker={tags ? 'Gợi ý theo hướng' : 'Các kiểu nơi'}
      close={then => close(then)} onPlace={place} onKind={kind} onRemove={remove} onSeen={seen} />}
  </section>
}
