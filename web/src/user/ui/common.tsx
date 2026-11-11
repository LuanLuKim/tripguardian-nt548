import * as Popover from '@radix-ui/react-popover'
import { useState, type ReactNode } from 'react'
import { useSnapshot, type Cover } from '../../data/store'
import { navigate } from '../../router'
import { info, type TrustLevel } from '../lib'
import { useUi } from '../store'
import { Icon } from './icons'

export const BASE = '/app'
export const href = (to: string) => (to === '/' ? BASE : BASE + to)
export const go = (to: string, opts?: { replace?: boolean }) => navigate(href(to), opts)
export const placeHref = (id: string) => `/explore/place/${encodeURIComponent(id)}`

export function Link({ to, children, className, onClick, ...rest }: { to: string; children: ReactNode; className?: string; onClick?: () => void } & Record<string, unknown>) {
  return (
    <a href={href(to)} className={className} {...rest} onClick={(e) => {
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return
      e.preventDefault()
      onClick?.()
      go(to)
    }}>{children}</a>
  )
}

// 480px WebP made by web/scripts/make_thumbs.py: /media/gmaps/<dir>/photos/x.jpg -> /media/thumb/gmaps/<dir>/photos/x.webp
export const THUMB_W = 480
export const thumbOf = (src: string) => (src.startsWith('/media/') ? src.replace('/media/', '/media/thumb/').replace(/\.jpe?g$/i, '.webp') : null)

// A card photo (Trip questions: a handful per screen, always on view): the 480px thumbnail, the original when the
// thumbnail is missing. Not lazy: a stage or deck that opens must not paint its pictures one by one.
export function CardImg({ src, alt, className, draggable }: { src: string; alt: string; className?: string; draggable?: boolean }) {
  const [fail, setFail] = useState(false)
  const thumb = thumbOf(src)
  return <img src={thumb && !fail ? thumb : src} alt={alt} className={className} draggable={draggable} decoding="async" onError={() => thumb && !fail && setFail(true)} />
}
// Fetch the pictures of a question while the user reads it, so they are in the cache when the card opens.
export function preloadPhotos(urls: (string | null | undefined)[]) {
  for (const u of new Set(urls)) if (u) new Image().src = thumbOf(u) ?? u
}

// Fetch a photo as Photo would show it at `sizes`, so it is in the cache when the screen that draws it opens.
export function warmPhoto(photo: Cover | undefined, sizes: string) {
  if (!photo) return
  const thumb = thumbOf(photo.src)
  const im = new Image()
  if (thumb && photo.w > THUMB_W) { im.sizes = sizes; im.srcset = `${thumb} ${THUMB_W}w, ${photo.src} ${photo.w}w` }
  im.src = thumb ?? photo.src
}

// The same, but it answers when the pictures are in (or failed, or `ms` ran out), so a screen can wait for them before it shows.
export function warmPhotos(urls: (string | null | undefined)[], ms: number): Promise<void> {
  const loads = [...new Set(urls)].flatMap((u) => (u ? [new Promise<void>((done) => { const im = new Image(); im.onload = im.onerror = () => done(); im.src = thumbOf(u) ?? u })] : []))
  return Promise.race([Promise.all(loads).then(() => {}), new Promise<void>((done) => setTimeout(done, ms))])
}

// The browser picks the thumbnail for small slots and the original for large or dense screens (`sizes`).
// A missing thumbnail falls back to the original, a missing original to the placeholder.
export function Photo({ photo, alt, className, credit = false, eager = false, sizes = '(max-width: 600px) 92vw, 320px' }: { photo: Cover | undefined; alt: string; className?: string; credit?: boolean; eager?: boolean; sizes?: string }) {
  const [failure, setFailure] = useState({ src: photo?.src, step: 0 })
  if (failure.src !== photo?.src) setFailure({ src: photo?.src, step: 0 })
  const fail = failure.src === photo?.src ? failure.step : 0
  const thumb = photo && fail === 0 ? thumbOf(photo.src) : null
  const wide = !!thumb && photo!.w > THUMB_W // narrower originals: the thumbnail is the same size, only lighter
  const missing = fail > 1 || !photo
  const label = photo ? 'Chưa tải được ảnh' : alt ? `Chưa có ảnh của ${alt}` : 'Chưa có ảnh'
  return (
    <figure className={`tg-photo ${className ?? ''}`}>
      {missing ? <div className="tg-photo__ph" role="img" aria-label={label} style={{ display: 'grid', placeItems: 'center', padding: '16px', textAlign: 'center', color: 'var(--tg-ink)' }}><span>{label}</span></div> : <img src={thumb ?? photo.src} srcSet={wide ? `${thumb} ${THUMB_W}w, ${photo.src} ${photo.w}w` : undefined} sizes={wide ? sizes : undefined} alt={alt} loading={eager ? 'eager' : 'lazy'} decoding="async" onError={() => setFailure({ src: photo.src, step: thumb ? 1 : 2 })} />}
      {credit && photo && !missing && <figcaption className="tg-photo__credit">Ảnh: {photo.credit}</figcaption>}
      {photo?.year && !missing && <small className="tg-photo__year" title="Ảnh cũ hơn 3 năm, chỉ dùng cho khung cảnh ngoài trời">Ảnh {photo.year}</small>}
    </figure>
  )
}
export function PlacePhoto({ id, i = 0, name, ...rest }: { id: string; i?: number; name?: string; className?: string; credit?: boolean; eager?: boolean; sizes?: string }) {
  useSnapshot() // screens that render before the snapshot (Hiểu chuyến đi) get the photo once it lands
  const p = info(id)
  const photos = p?.photos ?? []
  return <Photo photo={photos.length ? photos[i % photos.length] : undefined} alt={name ?? p?.name ?? ''} {...rest} />
}

// Opens on hover / focus AND on click, so touch and keyboard get the same explanation.
export function Hint({ label, children, side = 'top' }: { label: ReactNode; children: ReactNode; side?: 'top' | 'bottom' | 'left' | 'right' }) {
  const [open, setOpen] = useState(false)
  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <button type="button" className="tg-hint" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>{children}</button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content className="tg tg-pop" side={side} sideOffset={8} collisionPadding={12} onOpenAutoFocus={(e) => e.preventDefault()} onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
          {label}
          <Popover.Arrow className="tg-pop__arrow" />
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  )
}

export function Trust({ level, why }: { level: TrustLevel; why: string }) {
  return (
    <Hint label={<><b>Độ tin cậy: {level}.</b> {why}</>}>
      <span className={`tg-trust is-${level === 'Cao' ? 'hi' : level === 'Thấp' ? 'lo' : 'mid'}`}><i /><i /><i />{level}<Icon name="info" size={13} /></span>
    </Hint>
  )
}

export function Unconfirmed({ children = 'chưa xác nhận', why }: { children?: string; why: string }) {
  return <Hint label={why}><span className="tg-unconf"><Icon name="warn" size={13} />{children}</span></Hint>
}

export function Empty({ art, title, body, action }: { art: ReactNode; title: string; body: string; action?: ReactNode }) {
  return (
    <div className="tg-empty" role="status">
      <div className="tg-empty__art" aria-hidden="true">{art}</div>
      <h3>{title}</h3>
      <p className="tg-muted">{body}</p>
      {action}
    </div>
  )
}

export function Busy({ text }: { text: string }) {
  return <p className="tg-busy" role="status"><i /> {text}</p>
}

// A page that waits for data: the shape of the page to come, not a bare line of text.
export function Loading() {
  return (
    <div className="tg-load" role="status" aria-label="Đang tải dữ liệu Đà Lạt">
      <i className="tg-load__bar" />
      <div className="tg-load__row">{[0, 1, 2, 3].map((n) => <i key={n} className="tg-load__card" />)}</div>
      <div className="tg-load__row">{[0, 1, 2, 3].map((n) => <i key={n} className="tg-load__card" />)}</div>
    </div>
  )
}

export function Toast() {
  const note = useUi((u) => u.toast)
  if (!note) return null
  return <div className="tg-toast" role="status"><Icon name="heart" size={16} />{note}</div>
}

// The bunny reacts for empty / error states: it apologises when something went wrong, wonders when there is nothing yet.
function Bunny({ mood, say }: { mood: 'sad' | 'curious' | 'wait'; say: string }) {
  return (
    <div className="tg-bunny">
      <img src={`/img/bunny/${mood}.webp`} alt="" width={220} height={220} />
      <span className="tg-bunny__say">{say}</span>
    </div>
  )
}
export const ArtHills = () => <Bunny mood="sad" say="Xin lỗi bạn nhé!" />
export const ArtRoute = () => <Bunny mood="wait" say="Chờ chút…" />
export const ArtCup = () => <Bunny mood="curious" say="Hmm…" />
