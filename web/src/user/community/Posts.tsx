import { useMemo, useRef, useState } from 'react'
import { placeById, useDetail, useSnapshot } from '../../data/store'
import { query, usePath } from '../../router'
import { ranked, usePulse, whyOf } from '../home/Pulse'
import { info } from '../lib'
import { toggleSaved, useUi } from '../store'
import { go } from '../ui/common'
import { HeartFill, Icon } from '../ui/icons'
import { openPlace } from '../ui/PlaceSheet'
import { useTitle } from '../ui/Shell'
import { excerptOf, photosOf, postById, popularTags, posts, postsOf, reactionTotal, searchPlaces, useStore, when, type PlaceHit, type Post } from './data'
import { KnownFor, About, Intro, hasIntro } from '../ui/PlaceDetails'
import { Avatar, Demo, Editorial, hubHref, PlacePic, postHref, Pic, Rating, writeHref } from './parts'
import { PostMap, type Pin } from './PostMap'
import { PostSearch } from './Search'
import { Lightbox } from './Reader'
import '../css/posts.css'

// "Bài viết" (docs/design/mock/designs/search-blog): one screen. The places that have posts on the left (hover one and the map flies
// to it), the map on the right (click a dot for the place's details). A search narrows the list to the places it finds; a place opened
// shows its posts in the same column.
type Tab = 'places' | 'new' | 'mine'
const TABS: [Tab, string][] = [['places', 'Nơi nổi bật'], ['new', 'Bài mới'], ['mine', 'Của tôi']]

const hitOf = (placeId: string): PlaceHit => { const ps = postsOf(placeId); return { placeId, posts: ps, comments: ps.reduce((n, p) => n + p.comments.length, 0), name: false } }

export function Posts() {
  const params = query(usePath())
  const q = params.get('q')?.trim() ?? ''
  const at = params.get('at')
  const store = useStore()
  const pulse = usePulse()
  const [tab, setTab] = useState<Tab>('places')
  const [hot, setHot] = useState<string | null>(null)
  const [hotPost, setHotPost] = useState<string | null>(null) // the post under the pointer: the map shows its photos
  const [gallery, setGallery] = useState<{ srcs: string[]; at: number } | null>(null)
  const list = useRef<HTMLElement>(null)
  const leave = useRef<ReturnType<typeof setTimeout>>(undefined)
  useSnapshot()
  useTitle(q ? `“${q}” · Bài viết` : 'Bài viết')

  // The server's trending order first (it knows what is rising), then the places people react to most.
  const why = useMemo(() => {
    const m = new Map<string, string>()
    for (const it of pulse ? ranked(pulse) : []) if (it.place_id && !m.has(it.place_id)) m.set(it.place_id, whyOf(it))
    return m
  }, [pulse])
  const everyPlace = useMemo(() => {
    const order = [...why.keys()]
    const ids = [...new Set(posts(store).map((p) => p.placeId))].filter((id) => info(id))
    const score = (id: string) => (why.has(id) ? 1e6 - order.indexOf(id) : 0) + postsOf(id).reduce((s, p) => s + reactionTotal(p, store) + p.comments.length * 2, 0)
    return ids.sort((a, b) => score(b) - score(a)).map(hitOf)
  }, [store, why])

  const hits = useMemo(() => {
    if (!q) return everyPlace
    const found = searchPlaces(q)
    return at && !found.some((h) => h.placeId === at) ? [...found, hitOf(at)] : found
  }, [q, at, everyPlace, store]) // eslint-disable-line react-hooks/exhaustive-deps
  const active = at && hits.some((h) => h.placeId === at) ? at : null
  const shownPosts = useMemo(() => (tab === 'mine' ? posts(store).filter((p) => p.mine) : posts(store)), [tab, store])
  const showPosts = !q && !active && tab !== 'places'

  const pinIds = showPosts ? [...new Set(shownPosts.map((p) => p.placeId))] : hits.map((h) => h.placeId)
  const pins: Pin[] = useMemo(
    () => pinIds.flatMap((id) => { const p = info(id); return p ? [{ id, lat: p.lat, lng: p.lng, label: p.name, sub: `${postsOf(id).length} bài viết` }] : [] }),
    [pinIds.join('|'), store], // eslint-disable-line react-hooks/exhaustive-deps
  )
  const focus = hot ?? active
  const postPhotos = hotPost && postById(hotPost)?.placeId === focus ? photosOf(postById(hotPost)!).map((x) => x.src) : null

  // The focus lets go a moment after the pointer leaves, so it can travel from a card to its dot on the map and click it.
  const light = (id: string | null, post: string | null = null) => {
    clearTimeout(leave.current)
    if (id) { setHot(id); setHotPost(post) }
    else leave.current = setTimeout(() => { setHot(null); setHotPost(null) }, 450)
  }
  const card = (id: string) => list.current?.querySelector<HTMLElement>(`[data-place="${CSS.escape(id)}"]`)
  const detail = (id: string) => openPlace(id, card(id)?.querySelector('img') ?? null)
    const fromMap = (id: string | null) => light(id)
  const choose = (id: string | null) => go(hubHref({ q, place: id ?? undefined }))
  const heading = q ? (hits.length ? `${hits.length} nơi có bài viết về “${q}”` : 'Không có kết quả') : null

  return (
    <div className="tg-bp">
      <div className="tg-bp-res">
        <aside className="tg-bp-res__list" aria-label="Kết quả" ref={list}>
          <header className="tg-bp-top">
            <PostSearch value={q} />
            <button type="button" className="tg-bp-btn is-dark" onClick={() => go(writeHref(active ?? undefined))}><Icon name="edit" size={16} />Viết bài</button>
          </header>

          {active ? (
            <PlacePanel hit={hits.find((h) => h.placeId === active)!} q={q} onBack={() => choose(null)} onOpen={detail} onLight={light} />
          ) : (
            <>
              <div className="tg-bp-res__head">
                {heading ? <h1>{heading}</h1> : (
                  <div className="tg-bp-seg" role="group" aria-label="Xem theo">
                    {TABS.map(([k, label]) => <button key={k} type="button" aria-pressed={tab === k} onClick={() => { setTab(k); light(null) }}>{label}</button>)}
                  </div>
                )}
                {q && hits.length > 0 && <p>{hits.reduce((n, h) => n + h.posts.length, 0)} bài viết · rê chuột vào một nơi để xem trên bản đồ</p>}
              </div>

              {q && hits.length === 0 && (
                <div className="tg-bp-empty">
                  <b>Chưa có bài viết nào khớp “{q}”</b>
                  <p>Thử một từ ngắn hơn, hoặc chọn một chủ đề đang được viết nhiều:</p>
                  <div className="tg-bp-topics">{popularTags(6).map((t) => <button key={t} type="button" onClick={() => go(hubHref({ q: t }))}>#{t.replace(/\s+/g, '')}</button>)}</div>
                  <button type="button" className="tg-bp-btn" onClick={() => go('/posts')}>Xem mọi nơi</button>
                </div>
              )}

              {showPosts ? (
                shownPosts.length ? (
                  <ul className="tg-bp-rows is-feed" onMouseLeave={() => light(null)}>
                    {shownPosts.map((p) => <li key={p.id} data-place={p.placeId} onMouseEnter={() => light(p.placeId, p.id)}><PostRow post={p} place /></li>)}
                  </ul>
                ) : (
                  <div className="tg-bp-empty">
                    <b>{tab === 'mine' ? 'Bạn chưa viết bài nào' : 'Chưa có bài viết'}</b>
                    <p>Kể lại một nơi bạn đã đến, người sau sẽ cảm ơn bạn.</p>
                    <button type="button" className="tg-bp-btn is-dark" onClick={() => go(writeHref())}><Icon name="edit" size={16} />Viết bài đầu tiên</button>
                  </div>
                )
              ) : (
                <ul className="tg-bp-places" onMouseLeave={() => light(null)}>
                  {hits.map((h, i) => (
                    <li key={h.placeId} data-place={h.placeId} style={{ '--i': Math.min(i, 8) } as React.CSSProperties} onMouseEnter={() => light(h.placeId)}>
                      <PlaceCard hit={h} hot={hot === h.placeId} why={q ? undefined : why.get(h.placeId)} onOpen={() => choose(h.placeId)} onFocus={() => light(h.placeId)} />
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </aside>
        <div className="tg-bp-res__map">
          <PostMap pins={pins} focus={focus} photos={postPhotos} onHot={fromMap} onPhotos={(srcs, at) => setGallery({ srcs, at })} />
        </div>
      </div>
      {gallery && <Lightbox items={gallery.srcs.map((src) => ({ src, cap: '' }))} at={gallery.at} onClose={() => setGallery(null)} onGo={(at) => setGallery({ ...gallery, at })} />}
    </div>
  )
}

// One place: its photo, name, a line about it and the three numbers worth a click. It opens the place's posts.
function PlaceCard({ hit, hot, why, onOpen, onFocus }: { hit: PlaceHit; hot: boolean; why?: string; onOpen: () => void; onFocus: () => void }) {
  const p = info(hit.placeId)
  const saved = useUi((u) => u.saved.includes(hit.placeId))
  const latest = hit.posts[0]
  return (
    <article className={`tg-bp-pc ${hot ? 'is-hot' : ''}`}>
      <button type="button" className="tg-bp-pc__open" onClick={onOpen} onFocus={onFocus} aria-label={`Xem ${hit.posts.length} bài viết về ${p?.name}`}>
        <span className="tg-bp-pc__ph">
          <PlacePic id={hit.placeId} />
          {why && <span className="tg-bp-pc__why"><Icon name="flame" size={12} />{why}</span>}
        </span>
        <span className="tg-bp-pc__tx">
          <b>{p?.name}</b>
          <span className="tg-bp-pc__line">{[p?.category, p?.area].filter(Boolean).join(' · ')}{latest ? <> — “{latest.title}”</> : null}</span>
          <span className="tg-bp-chips">
            <span className="tg-bp-chip"><Icon name="edit" size={13} />{hit.posts.length} bài</span>
            <span className="tg-bp-chip"><Icon name="chat" size={13} />{hit.comments} bình luận</span>
            {p?.rating ? <span className="tg-bp-chip"><Icon name="star" size={13} style={{ fill: 'currentColor' }} />{p.rating.toFixed(1)}</span> : null}
          </span>
        </span>
      </button>
      <button type="button" className={`tg-bp-pc__save ${saved ? 'is-on' : ''}`} aria-pressed={saved} aria-label={saved ? `Bỏ lưu ${p?.name}` : `Lưu ${p?.name}`} onClick={() => toggleSaved(hit.placeId, p?.name)}>
        {saved ? <HeartFill size={18} /> : <Icon name="heart" size={18} />}
      </button>
    </article>
  )
}

// The posts of one place, in the column where the places were.
function PlacePanel({ hit, q, onBack, onOpen, onLight }: { hit: PlaceHit; q: string; onBack: () => void; onOpen: (id: string) => void; onLight: (placeId: string | null, post: string | null) => void }) {
  const p = info(hit.placeId)
  return (
    <div className="tg-bp-panel">
      <button type="button" className="tg-bp-back" onClick={onBack}><Icon name="arrowLeft" size={16} />{q ? `Kết quả “${q}”` : 'Tất cả các nơi'}</button>
      <div className="tg-bp-panel__hd" data-place={hit.placeId}>
        <span className="tg-bp-panel__ph"><PlacePic id={hit.placeId} eager /></span>
        <div>
          <h1>{p?.name}</h1>
          <p><Rating value={p?.rating} />{p?.rating ? ' · ' : ''}{[p?.category, p?.area].filter(Boolean).join(' · ')}</p>
        </div>
      </div>
      <div className="tg-bp-panel__act">
        <button type="button" className="tg-bp-btn" onClick={() => onOpen(hit.placeId)}>Xem chi tiết nơi này</button>
      </div>
      <Summary id={hit.placeId} />
      <h2 className="tg-bp-panel__n">{hit.posts.length ? `${hit.posts.length} bài viết` : 'Chưa có bài viết'}</h2>
      {hit.posts.length === 0 && <div className="tg-bp-empty"><b>Chưa ai viết về nơi này</b><p>Bạn có thể là người đầu tiên.</p></div>}
      <ul className="tg-bp-tiles">{hit.posts.map((post) => <li key={post.id}><PostTile post={post} onHover={(on) => onLight(on ? hit.placeId : null, on ? post.id : null)} /></li>)}</ul>
    </div>
  )
}

function PostRow({ post, place = false }: { post: Post; place?: boolean }) {
  const store = useStore()
  return (
    <a className="tg-bp-row" href={`/app${postHref(post.id)}`} onClick={(e) => { if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return; e.preventDefault(); go(postHref(post.id)) }}>
      <span className="tg-bp-row__ph"><Pic src={photosOf(post)[0]?.src ?? ''} /></span>
      <span className="tg-bp-row__tx">
        {place && <small className="tg-bp-row__pl"><Icon name="pin" size={12} />{info(post.placeId)?.name}</small>}
        <b>{post.title}</b>
        <small><Avatar name={post.author} size={18} />{post.author} · {when(post.at)}{post.demo && <Demo />}{post.editorial && <Editorial />}</small>
        <small className="tg-bp-row__st"><Icon name="heart" size={12} />{reactionTotal(post, store)}<Icon name="chat" size={12} />{post.comments.length}</small>
      </span>
    </a>
  )
}

// A post in the place's column: its photo, title, a taste of the text, who wrote it and what people did with it.
function PostTile({ post, onHover }: { post: Post; onHover: (on: boolean) => void }) {
  const store = useStore()
  const photos = photosOf(post)
  return (
    <a className="tg-bp-tile" onMouseEnter={() => onHover(true)} onMouseLeave={() => onHover(false)} onFocus={() => onHover(true)} onBlur={() => onHover(false)} href={`/app${postHref(post.id)}`} onClick={(e) => { if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return; e.preventDefault(); go(postHref(post.id)) }}>
      <span className="tg-bp-tile__ph"><Pic src={photos[0]?.src ?? ''} />{photos.length > 1 && <span className="tg-bp-tile__cnt"><Icon name="image" size={12} />{photos.length}</span>}</span>
      <span className="tg-bp-tile__tx">
        <b>{post.title}</b>
        <span>{excerptOf(post, 120)}</span>
        <small><Avatar name={post.author} size={20} />{post.author} · {when(post.at)}{post.demo && <Demo />}{post.editorial && <Editorial />}<span className="tg-bp-tile__st"><Icon name="heart" size={12} />{reactionTotal(post, store)}<Icon name="chat" size={12} />{post.comments.length}</span></small>
      </span>
    </a>
  )
}

// A short introduction to the place, to give a reader the gist before the posts: what it is, what it is known for, what visitors say.
// Made only of what is on record (the same lines the place sheet opens with) and one real line a visitor wrote; nothing is invented.
function Summary({ id }: { id: string }) {
  const [more, setMore] = useState(false)
  useDetail(id) // the place's evidence loads in the background; the text fills in when it lands
  const p = placeById(id)
  const quote = info(id)?.quotes[0]
  if (!p) return null
  return (
    <section className="tg-bp-sum" aria-label="Giới thiệu nơi này">
      <KnownFor p={p} />
      {hasIntro(p) ? (
        <div className="tg-bp-sum__intro"><Intro p={p} open={more} /></div>
      ) : (
        <div className={`tg-bp-sum__tx ${more ? 'is-open' : ''}`}><About p={p} area={info(id)?.area} /></div>
      )}
      {(!hasIntro(p) || (p.details?.intro?.story.length ?? 0) > 0) && (
        <button type="button" className="tg-bp-sum__more" aria-expanded={more} onClick={() => setMore((v) => !v)}>{more ? 'Thu gọn' : 'Đọc thêm'}</button>
      )}
      {quote && <blockquote>“{quote.text}”<small>Người đã đến</small></blockquote>}
    </section>
  )
}
