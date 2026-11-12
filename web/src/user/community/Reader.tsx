import { Fragment, useEffect, useRef, useState, type ReactNode } from 'react'
import { useSnapshot } from '../../data/store'
import { useAccount } from '../account'
import { info } from '../lib'
import { toast } from '../store'
import { go } from '../ui/common'
import { Icon } from '../ui/icons'
import { useTitle } from '../ui/Shell'
import {
  comment, FACT_LABELS, photosOf, postById, postsOf, reactionTotal, reactTo, readMinutes, REACTS, srcOf, togglePostSaved, topReacts, useStore, when, type Block, type Post, type ReactKey,
} from './data'
import { Avatar, Demo, hubHref, Pic, postHref, ReactIcon, Visibility, writeHref } from './parts'
import '../css/posts.css'

// **bold** and *italic* are the only marks the composer writes.
export function Inline({ text }: { text: string }): ReactNode {
  return text.split(/(\*\*[^*]+\*\*|\*[^*\n]+\*)/g).map((part, i) =>
    part.startsWith('**') && part.endsWith('**') && part.length > 4 ? <strong key={i}>{part.slice(2, -2)}</strong>
      : part.startsWith('*') && part.endsWith('*') && part.length > 2 ? <em key={i}>{part.slice(1, -1)}</em>
        : <Fragment key={i}>{part}</Fragment>)
}

const FACT_ICON = { when: 'calendar', who: 'users', how: 'route', cost: 'wallet' } as const

export function PostPage({ id }: { id: string }) {
  useSnapshot()
  const store = useStore()
  const post = postById(id)
  useTitle(post?.title ?? 'Bài viết')
  useEffect(() => { document.querySelector('.tg-hf__main')?.scrollTo({ top: 0 }) }, [id])
  if (!post || !info(post.placeId)) {
    return (
      <div className="tg-pr tg-pr--gone">
        <p className="tg-pr__kick">Bài viết</p>
        <h1>Không tìm thấy bài viết này</h1>
        <p>Bài có thể đã bị xóa, hoặc chỉ người viết mới xem được.</p>
        <button type="button" className="tg-bp-btn is-dark" onClick={() => go('/posts')}>Về trang bài viết</button>
      </div>
    )
  }
  return <Article post={post} saved={store.saved.includes(post.id)} />
}

function Article({ post, saved }: { post: Post; saved: boolean }) {
  const place = info(post.placeId)!
  const imgs = post.blocks.flatMap((b, i) => (b.t === 'img' && srcOf(post, b.src) ? [{ i, src: srcOf(post, b.src), cap: b.cap }] : []))
  const hero = imgs[0]
  const body = post.blocks.filter((_, i) => i !== hero?.i)
  const [zoom, setZoom] = useState<number | null>(null)
  const others = postsOf(post.placeId).filter((p) => p.id !== post.id).slice(0, 4)
  const facts = FACT_LABELS.filter(([k]) => post.facts[k])
  const firstP = body.findIndex((b) => b.t === 'p')
  const open = (src: string) => { const k = imgs.findIndex((x) => x.src === src); if (k >= 0) setZoom(k) }
  const copy = () => {
    const url = `${location.origin}/app/posts/${encodeURIComponent(post.id)}`
    navigator.clipboard?.writeText(url).then(() => toast('Đã chép liên kết bài viết'), () => toast('Không chép được liên kết'))
  }
  const save = () => { togglePostSaved(post.id); toast(saved ? 'Đã bỏ lưu bài' : 'Đã lưu bài') }

  return (
    <article className="tg-pr">
      <div className="tg-pr__bar">
        <button type="button" className="tg-bp-back" onClick={() => (history.length > 1 ? history.back() : go('/posts'))}><Icon name="arrowLeft" size={16} />Quay lại</button>
        <span className="tg-pr__where"><button type="button" onClick={() => go(hubHref({ place: post.placeId }))}>{place.name}</button><i aria-hidden="true">›</i><b>{post.title}</b></span>
        <div className="tg-pr__tools">
          <button type="button" className={`tg-bp-ib ${saved ? 'is-on' : ''}`} aria-pressed={saved} aria-label={saved ? 'Bỏ lưu bài' : 'Lưu bài'} title={saved ? 'Bỏ lưu bài' : 'Lưu bài'} onClick={save}><Icon name="bookmark" size={18} style={saved ? { fill: 'currentColor' } : undefined} /></button>
          <button type="button" className="tg-bp-ib" aria-label="Sao chép liên kết" title="Sao chép liên kết" onClick={copy}><Icon name="link" size={18} /></button>
        </div>
      </div>

      <div className="tg-pr__col">
        <header className="tg-pr__head">
          <p className="tg-pr__kick"><button type="button" onClick={() => go(hubHref({ place: post.placeId }))}>{place.name}</button>{post.tags[0] && <><i>·</i>{post.tags[0]}</>}{post.demo && <Demo />}</p>
          <h1>{post.title}</h1>
          <div className="tg-pr__by">
            <Avatar name={post.author} size={44} me={post.mine} />
            <span><b>{post.author}</b><small>{when(post.at)} · {readMinutes(post)} phút đọc · <Visibility vis={post.vis} /></small></span>
            {facts.length > 0 && <ul className="tg-pr__facts" aria-label="Chi tiết chuyến đi">{facts.map(([k, label]) => <li key={k} title={label}><Icon name={FACT_ICON[k]} size={14} />{post.facts[k]}</li>)}</ul>}
          </div>
        </header>

        {hero && (
          <figure className="tg-pr__hero">
            <button type="button" onClick={() => open(hero.src)} aria-label="Xem ảnh lớn"><Pic src={hero.src} alt={hero.cap || post.title} eager /></button>
            {imgs.length > 1 && <span className="tg-pr__count"><Icon name="image" size={13} />{imgs.length} ảnh</span>}
            {hero.cap && <figcaption>{hero.cap}</figcaption>}
          </figure>
        )}

        <div className="tg-pr__body">
          {body.map((b, i) => <BlockView key={i} b={b} post={post} lead={i === firstP} onOpen={open} />)}
        </div>
        {post.tags.length > 0 && <ul className="tg-pr__tags">{post.tags.map((t) => <li key={t}><button type="button" onClick={() => go(hubHref({ q: t }))}>#{t.replace(/\s+/g, '')}</button></li>)}</ul>}
      </div>

      <div className="tg-pr__band">
        <Reactions post={post} onShare={copy} saved={saved} onSave={save} />
        <div className={`tg-pr__cols ${others.length ? '' : 'is-solo'}`}>
          <Comments post={post} />
          {others.length > 0 && <aside className="tg-pr__side" aria-label="Bài khác về nơi này">
            {others.length > 0 && (
              <div className="tg-pr__others">
                <h2>Bài khác về {place.name}</h2>
                <ul>{others.map((p) => (
                  <li key={p.id}><a href={`/app${postHref(p.id)}`} onClick={(e) => { if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return; e.preventDefault(); go(postHref(p.id)) }}>
                    <span><Pic src={photosOf(p)[0]?.src ?? ''} /></span><span><b>{p.title}</b><small>{p.author} · {when(p.at)}</small></span>
                  </a></li>
                ))}</ul>
                <button type="button" className="tg-bp-btn" onClick={() => go(writeHref(post.placeId))}><Icon name="edit" size={15} />Viết bài về nơi này</button>
              </div>
            )}
          </aside>}
        </div>
      </div>
      {zoom !== null && <Lightbox items={imgs} at={zoom} onClose={() => setZoom(null)} onGo={setZoom} />}
    </article>
  )
}

function BlockView({ b, post, lead, onOpen }: { b: Block; post: Post; lead: boolean; onOpen: (src: string) => void }) {
  if (b.t === 'h') return <h2><Inline text={b.text} /></h2>
  if (b.t === 'q') return <blockquote><Inline text={b.text} /></blockquote>
  if (b.t === 'img') {
    const src = srcOf(post, b.src)
    return src ? <figure><button type="button" onClick={() => onOpen(src)} aria-label="Xem ảnh lớn"><Pic src={src} alt={b.cap} /></button>{b.cap && <figcaption>{b.cap}</figcaption>}</figure> : null
  }
  return <p className={lead && b.text.length > 80 ? 'is-lead' : undefined}><Inline text={b.text} /></p>
}

export function Lightbox({ items, at, onClose, onGo }: { items: { src: string; cap: string }[]; at: number; onClose: () => void; onGo: (i: number) => void }) {
  const it = items[at]
  const step = (d: number) => onGo((at + d + items.length) % items.length)
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { e.stopPropagation(); onClose() }
      else if (e.key === 'ArrowLeft') step(-1)
      else if (e.key === 'ArrowRight') step(1)
    }
    addEventListener('keydown', key, true)
    return () => removeEventListener('keydown', key, true)
  })
  return (
    <div className="tg-bp-lb" role="dialog" aria-modal="true" aria-label="Xem ảnh" onClick={onClose}>
      <img src={it.src} alt={it.cap} onClick={(e) => e.stopPropagation()} />
      {it.cap && <p onClick={(e) => e.stopPropagation()}>{it.cap}</p>}
      <button type="button" className="tg-bp-lb__x" aria-label="Đóng" onClick={onClose}><Icon name="x" size={20} /></button>
      {items.length > 1 && (
        <>
          <button type="button" className="tg-bp-lb__n is-l" aria-label="Ảnh trước" onClick={(e) => { e.stopPropagation(); step(-1) }}><Icon name="chevronLeft" size={22} /></button>
          <button type="button" className="tg-bp-lb__n is-r" aria-label="Ảnh sau" onClick={(e) => { e.stopPropagation(); step(1) }}><Icon name="chevronRight" size={22} /></button>
          <span className="tg-bp-lb__c">{at + 1} / {items.length}</span>
        </>
      )}
    </div>
  )
}

function Reactions({ post, onShare, saved, onSave }: { post: Post; onShare: () => void; saved: boolean; onSave: () => void }) {
  const s = useStore()
  const mine = s.reacted[post.id] as ReactKey | undefined
  const [pick, setPick] = useState(false)
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined)
  const total = reactionTotal(post, s)
  const label = REACTS.find((r) => r.k === mine)?.label ?? 'Thích'
  const set = (k: ReactKey | null) => { reactTo(post.id, k); setPick(false) }
  useEffect(() => {
    if (!pick) return
    const close = (e: Event) => { if (!(e.target as HTMLElement).closest('.tg-pr__react')) setPick(false) }
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') setPick(false) }
    addEventListener('pointerdown', close)
    addEventListener('keydown', esc)
    return () => { removeEventListener('pointerdown', close); removeEventListener('keydown', esc) }
  }, [pick])
  return (
    <div className="tg-pr__react">
      <div className="tg-pr__sum">
        <span className="tg-pr__rs">{topReacts(post, s).map((k) => <ReactIcon key={k} k={k} size={22} />)}</span>
        <span>{total === 0 ? 'Hãy là người đầu tiên thả cảm xúc' : mine ? (total === 1 ? 'Bạn' : `Bạn và ${total - 1} người khác`) : `${total} người đã thả cảm xúc`}</span>
      </div>
      {pick && (
        <div className="tg-pr__picker" role="menu" aria-label="Thả cảm xúc">
          {REACTS.map((r) => <button key={r.k} type="button" role="menuitem" data-l={r.label} aria-label={r.label} onClick={() => set(r.k)}><ReactIcon k={r.k} size={30} /></button>)}
        </div>
      )}
      <div className="tg-pr__acts">
        <span className="tg-pr__split">
          <button type="button" className={`tg-pr__act ${mine ? 'is-on' : ''}`} aria-pressed={!!mine}
            onClick={() => (mine ? set(null) : set('like'))}
            onPointerEnter={(e) => { if (e.pointerType === 'mouse') timer.current = setTimeout(() => setPick(true), 350) }} onPointerLeave={() => clearTimeout(timer.current)}
            onContextMenu={(e) => { e.preventDefault(); setPick(true) }}>
            {mine ? <ReactIcon k={mine} size={20} /> : <Icon name="heart" size={19} />}{label}
          </button>
          <button type="button" className="tg-pr__act is-caret" aria-label="Chọn cảm xúc khác" aria-expanded={pick} onClick={() => setPick((v) => !v)}><Icon name="smile" size={19} /></button>
        </span>
        <button type="button" className="tg-pr__act" onClick={() => document.getElementById('tg-pr-cm')?.focus()}><Icon name="chat" size={19} />{post.comments.length} bình luận</button>
        <button type="button" className="tg-pr__act" onClick={onShare}><Icon name="link" size={19} />Chia sẻ</button>
        <button type="button" className={`tg-pr__act ${saved ? 'is-on' : ''}`} aria-pressed={saved} onClick={onSave}><Icon name="bookmark" size={19} style={saved ? { fill: 'currentColor' } : undefined} />{saved ? 'Đã lưu' : 'Lưu bài'}</button>
      </div>
    </div>
  )
}

function Comments({ post }: { post: Post }) {
  const account = useAccount()
  const name = account?.name || 'Bạn'
  const [text, setText] = useState('')
  const send = () => {
    const t = text.trim()
    if (!t) return
    if (comment(post.id, name, t)) setText('')
    else toast('Bộ nhớ trình duyệt đã đầy, chưa lưu được bình luận')
  }
  return (
    <section className="tg-pr__cm" aria-label="Bình luận">
      <h2>Bình luận</h2>
      <div className="tg-pr__say">
        <Avatar name={name} size={40} me />
        <label className="tg-sr" htmlFor="tg-pr-cm">Viết bình luận</label>
        <textarea id="tg-pr-cm" value={text} rows={1} maxLength={1000} placeholder={`Viết bình luận cho ${post.author}…`} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); send() } }} />
        <button type="button" className="tg-bp-btn is-dark" disabled={!text.trim()} onClick={send}>Gửi</button>
      </div>
      <ul>
        {[...post.comments].sort((a, b) => a.at - b.at).map((c) => (
          <li key={c.id} className={c.reply ? 'is-reply' : undefined}>
            <Avatar name={c.name} size={c.reply ? 34 : 40} me={c.mine} />
            <div><div className="tg-pr__bub"><b>{c.name}{c.name === post.author && <em>tác giả</em>}</b><small>{when(c.at)}</small><p>{c.text}</p></div></div>
          </li>
        ))}
      </ul>
    </section>
  )
}
