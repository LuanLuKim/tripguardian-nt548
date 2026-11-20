import { useCallback, useEffect, useRef, useState } from 'react'
import { prefetch as prefetchSpace3d } from '../ui/Space3d'
import { Icon } from '../ui/icons'

// Landing, below the story: the 3D models of famous places and the two storytelling films (docs/UI_SPEC_LANDING.md §2).
// Nothing heavy loads until the visitor shows intent, so the landscape keeps the connection while the first screen is read:
//   - a 3D tile: on hover / focus the viewer script, the place data and the poster are fetched; the press then opens a frame
//     that shows the tile's poster until the scene has drawn (`space3d:ready`), so there is never a black or empty window;
//   - the Langbiang film: a <video> with its poster and preload="none"; hover, focus, touch or resting on the card
//     (>= 60% in view for 1 s) switches it to preload="auto", so the first seconds are buffered when Play is pressed;
//   - the interactive film: a cross-origin page with its own loading bar. Hover / focus / touch builds the frame ahead,
//     hidden, so by the press its bar has finished; it is dropped after WARM_MS if nobody opens it, and always on close
//     (which also stops its sound).

// Places shown: slug in /space3d/index.json (poster `/space3d/posters/<slug>.webp`), name, what the visitor sees inside.
// The first is the large tile. The section shows only places the server really has a model for.
const MODELS: [string, string, string][] = [
  ['gadalat', 'Ga Đà Lạt', 'Quảng trường, sảnh ga, sân ga, toa gỗ'],
  ['linhphuoc', 'Chùa Linh Phước', 'Mặt tiền, rồng khảm sành, tháp chuông, Quan Âm'],
  ['conga', 'Nhà thờ Con Gà', 'Tháp con gà, thân nhà thờ, bên trong'],
  ['dinh3', 'Dinh III', 'Mặt tiền, hiên, vườn, bên trong dinh'],
  ['dalatpalace', 'Dalat Palace', 'Mặt tiền, hành lang, sảnh bên trong'],
  ['hoxuanhuong', 'Hồ Xuân Hương', 'Cầu đỏ, thuyền thiên nga, đường dạo'],
  ['truclam', 'Thiền viện Trúc Lâm', 'Tam quan, chánh điện, lầu chuông, vườn thông'],
  ['cadasa', 'Biệt thự Cadasa', 'Biệt thự cổ: sảnh, mái ngói cam, nội thất'],
  ['caudat', 'Cầu Đất', 'Lối đất đỏ qua đồi trà, nhìn ra thung lũng'],
  ['chuatau', 'Chùa Tàu', 'Sân chùa, tượng Phật, chính điện'],
]
const FILM_SITE = 'https://storytelling-ho-than-tho.vercel.app/'
const WARM_MS = 120_000 // a built-ahead film frame nobody opened is dropped after this
const HOVER_MS = 150
const READY_FALLBACK_MS = 12_000 // show the 3D frame anyway if the scene never reports

type Open = { kind: '3d'; slug: string; name: string } | { kind: 'play' } | null

// Warm only with room to spare: not on Save-Data, not on a 2G / 3G line.
function mayWarm() {
  const c = (navigator as Navigator & { connection?: { saveData?: boolean; effectiveType?: string } }).connection
  return !c?.saveData && !/^(slow-2g|2g|3g)$/.test(c?.effectiveType ?? '')
}

// Spread on an element: runs `fn` once the pointer rests on it for HOVER_MS, or at focus / touch / press.
function onIntent(fn: () => void) {
  let timer: number | undefined
  const now = () => { clearTimeout(timer); fn() }
  return {
    onPointerEnter: () => { clearTimeout(timer); timer = window.setTimeout(now, HOVER_MS) },
    onPointerLeave: () => clearTimeout(timer),
    onPointerDown: now,
    onFocus: now,
  }
}

export function Showcase({ onOpen }: { onOpen?: (open: boolean) => void }) {
  const [shown, setShown] = useState<Record<string, string> | null>(null) // /space3d/index.json: id → slug
  const [open, setOpen] = useState<Open>(null)
  const [filmWarm, setFilmWarm] = useState(false) // the interactive film's frame exists (hidden until opened)
  const [ready, setReady] = useState(false) // the open 3D scene has drawn its first frame
  const [started, setStarted] = useState(false) // Langbiang: Play was pressed (native controls take over)
  const [buffering, setBuffering] = useState(false)
  const opener = useRef<HTMLElement | null>(null)
  const video = useRef<HTMLVideoElement>(null)
  const clipCard = useRef<HTMLElement>(null)
  const grid = useRef<HTMLDivElement>(null)
  const frame3d = useRef<HTMLIFrameElement>(null)
  const warmTimer = useRef<number>(0)
  const muted = useRef(false) // just closed: focus returning to the poster must not build the frame again

  useEffect(() => {
    let on = true
    fetch('/space3d/index.json').then((r) => r.json() as Promise<Record<string, string>>).then((all) => { if (on) setShown(all) }).catch(() => undefined)
    return () => { on = false }
  }, [])
  const have = new Set(Object.values(shown ?? {}))
  const models = MODELS.filter(([slug]) => have.has(slug))

  // The viewer script (1 MB, immutable) is fetched when the gallery is about to come into view, so the first press never waits for it.
  useEffect(() => {
    const el = grid.current, first = models[0]?.[0]
    if (!el || !first || !mayWarm()) return
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { prefetchSpace3d(first); io.disconnect() } }, { rootMargin: '700px 0px' })
    io.observe(el)
    return () => io.disconnect()
  }, [models.length]) // eslint-disable-line react-hooks/exhaustive-deps

  // Langbiang: from "nothing" to "first seconds buffered" before the press.
  const warmClip = useCallback(() => {
    const v = video.current
    if (!v || v.dataset.warm || !mayWarm()) return
    v.dataset.warm = '1'
    v.preload = 'auto'
    v.load()
  }, [])
  useEffect(() => {
    const el = clipCard.current
    if (!el) return
    let timer = 0
    const io = new IntersectionObserver(([e]) => {
      clearTimeout(timer)
      if (e.isIntersecting) timer = window.setTimeout(warmClip, 1000)
    }, { threshold: 0.6 })
    io.observe(el)
    return () => { clearTimeout(timer); io.disconnect() }
  }, [warmClip])
  const playClip = () => {
    const v = video.current
    if (!v) return
    setStarted(true)
    setBuffering(v.readyState < 3)
    void v.play().catch(() => setStarted(false))
  }

  // The interactive film: frame built ahead (hidden), dropped if unused.
  const warmFilm = useCallback(() => {
    if (muted.current || !mayWarm()) return
    setFilmWarm(true)
    clearTimeout(warmTimer.current)
    warmTimer.current = window.setTimeout(() => setFilmWarm(false), WARM_MS)
  }, [])
  useEffect(() => () => clearTimeout(warmTimer.current), [])
  // keep the dns / tls for the film host ready as soon as the section exists
  useEffect(() => {
    const link = document.createElement('link')
    link.rel = 'preconnect'
    link.href = new URL(FILM_SITE).origin
    document.head.appendChild(link)
    return () => link.remove()
  }, [])

  // A full-window frame is open: the page stops scrolling under it; Esc or the model's own Back button closes it.
  const close = useCallback(() => {
    setOpen(null)
    setFilmWarm(false) // unmounting the film frame stops its sound and frees its memory
    clearTimeout(warmTimer.current)
    muted.current = true
    opener.current?.focus()
    window.setTimeout(() => { muted.current = false }, 600)
  }, [])
  useEffect(() => {
    onOpen?.(!!open)
    if (!open) return
    setReady(false)
    video.current?.pause()
    const key = (e: KeyboardEvent) => { if (e.key === 'Escape') close() }
    const msg = (e: MessageEvent) => {
      if (e.origin !== location.origin || e.source !== frame3d.current?.contentWindow) return
      const type = (e.data as { type?: string } | null)?.type
      if (type === 'space3d:back') close()
      else if (type === 'space3d:ready' || type === 'space3d:error') setReady(true)
    }
    const fallback = window.setTimeout(() => setReady(true), READY_FALLBACK_MS)
    addEventListener('keydown', key)
    addEventListener('message', msg)
    return () => { clearTimeout(fallback); removeEventListener('keydown', key); removeEventListener('message', msg) }
  }, [open]) // eslint-disable-line react-hooks/exhaustive-deps

  const launch = (o: Open, el: HTMLElement) => { opener.current = el; setOpen(o) }
  const playing3d = open?.kind === '3d' ? open : null
  const filmOpen = open?.kind === 'play'

  return (
    <>
      {models.length > 0 && (
        <section className="tg-l6" id="tg-3d" aria-labelledby="tg-3d-h">
          <div className="tg-l__head">
            <p className="tg-kicker">Khám phá 3D</p>
            <h2 id="tg-3d-h">Đi một vòng trước khi đến.</h2>
            <p className="tg-muted">{Object.keys(shown ?? {}).length} nơi nổi tiếng của Đà Lạt đã có mô hình 3D dựng từ ảnh và vị trí thật. Bấm một nơi để xoay, phóng to, đi vào bên trong.</p>
          </div>
          <div className="tg-l6__grid" ref={grid}>
            {models.map(([slug, name, note], i) => (
              <button key={slug} type="button" className={`tg-l6__tile t${i}`} onClick={(e) => launch({ kind: '3d', slug, name }, e.currentTarget)} aria-label={`Mở mô hình 3D ${name}`} {...onIntent(() => mayWarm() && prefetchSpace3d(slug))}>
                <img src={`/space3d/posters/${slug}.webp`} alt="" loading={i < 5 ? 'eager' : 'lazy'} decoding="async" />
                <span className="tg-l6__cube"><Icon name="cube" size={16} />3D</span>
                <span className="tg-l6__cap"><b>{name}</b><small>{note}</small></span>
              </button>
            ))}
          </div>
          <p className="tg-faint tg-l6__note">TripGuardian chỉ dựng cho nơi đặc biệt, đẹp hoặc nổi tiếng. Chỗ nào thiếu dữ liệu thì được vẽ thêm cho liền mạch, nên mô hình để hình dung, không thay cho đánh giá thật ở trang của từng nơi.</p>
        </section>
      )}

      <section className="tg-l7" id="tg-films" aria-labelledby="tg-films-h">
        <div className="tg-l__head">
          <p className="tg-kicker">Chuyện kể Đà Lạt</p>
          <h2 id="tg-films-h">Mỗi nơi đều có một câu chuyện.</h2>
          <p className="tg-muted">Hai truyền thuyết của Đà Lạt, kể bằng tranh thủy mặc và giọng đọc tiếng Việt. Tự bước vào câu chuyện, hoặc ngồi xem một phim.</p>
        </div>
        <div className="tg-l7__row">
          <article className="tg-l7__card" {...onIntent(warmFilm)}>
            <div className="tg-l7__media">
              <button type="button" className="tg-l7__poster" onClick={(e) => { warmFilm(); launch({ kind: 'play' }, e.currentTarget) }} aria-label="Chơi phim tương tác Mùa xuân không về"><img src="/media/landing/ho-than-tho-poster.webp" alt="" loading="lazy" decoding="async" /><span className="tg-l7__play"><Icon name="play" size={26} /></span></button>
            </div>
            <div className="tg-l7__body">
              <p className="tg-kicker">Phim tương tác · bạn quyết định</p>
              <h3>Mùa xuân không về</h3>
              <p className="tg-muted">Truyền thuyết Hồ Than Thở, kể ở ngôi thứ nhất. Bạn là Hoàng Tùng, chọn đường đi ở những lúc câu chuyện cần bạn. Khoảng 9 phút, có tiếng, nên bật loa.</p>
              <a className="tg-l7__ext" href={FILM_SITE} target="_blank" rel="noreferrer">Mở ở tab mới <Icon name="external" size={14} /></a>
            </div>
          </article>
          <article className="tg-l7__card" ref={clipCard} {...onIntent(warmClip)}>
            <div className="tg-l7__media">
              <video ref={video} src="/media/landing/langbiang.mp4" poster="/media/landing/langbiang-poster.webp" preload="none" playsInline controls={started} onWaiting={() => setBuffering(true)} onPlaying={() => setBuffering(false)} onCanPlay={() => setBuffering(false)} onEnded={() => setStarted(false)} />
              {!started && <button type="button" className="tg-l7__poster tg-l7__cover" onClick={playClip} aria-label="Xem phim Langbiang"><span className="tg-l7__play"><Icon name="play" size={26} /></span></button>}
              {started && buffering && <span className="tg-l7__wait" role="status">Đang tải phim…</span>}
            </div>
            <div className="tg-l7__body">
              <p className="tg-kicker">Phim · 1 phút 26</p>
              <h3>Langbiang</h3>
              <p className="tg-muted">Truyền thuyết Langbiang: chuyện tình K’Lang – K’Biang đã hóa thành núi, theo bản kể sử thi K’Ho. Tranh thủy mặc, giọng đọc, có phụ đề.</p>
            </div>
          </article>
        </div>
      </section>

      {playing3d && (
        <div className="tg-l8" role="dialog" aria-modal="true" aria-label={`Mô hình 3D ${playing3d.name}`} style={{ backgroundImage: `url(/space3d/posters/${playing3d.slug}.webp)` }}>
          <iframe ref={frame3d} className={ready ? 'is-ready' : ''} title={`Mô hình 3D ${playing3d.name}`} src={`/space3d/viewer.html?place=${encodeURIComponent(playing3d.slug)}&host=full`} allow="fullscreen" />
          {!ready && <p className="tg-l8__wait" role="status">Đang dựng {playing3d.name}…</p>}
          <button type="button" className="tg-l8__x" onClick={close} autoFocus><Icon name="x" size={18} />Đóng</button>
        </div>
      )}
      {(filmWarm || filmOpen) && (
        <div className="tg-l8 tg-l8--film" data-on={filmOpen ? 'true' : 'false'} role={filmOpen ? 'dialog' : undefined} aria-modal={filmOpen || undefined} aria-hidden={filmOpen ? undefined : true} aria-label="Phim tương tác Mùa xuân không về" style={{ backgroundImage: 'url(/media/landing/ho-than-tho-poster.webp)' }}>
          <iframe title="Phim tương tác Mùa xuân không về" src={FILM_SITE} allow="autoplay; fullscreen" tabIndex={filmOpen ? 0 : -1} />
          <button type="button" className="tg-l8__x" onClick={close} autoFocus={filmOpen} tabIndex={filmOpen ? 0 : -1}><Icon name="x" size={18} />Đóng</button>
        </div>
      )}
    </>
  )
}
