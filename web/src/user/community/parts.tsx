import { useEffect, useState } from 'react'
import { thumbOf } from '../ui/common'
import { Icon } from '../ui/icons'
import { info } from '../lib'
import { initialsOf, srcOf, VIS, type Post, type ReactKey } from './data'

export const postHref = (id: string) => `/posts/${encodeURIComponent(id)}`
export const hubHref = (o: { q?: string; place?: string } = {}) => {
  const p = new URLSearchParams()
  if (o.q) p.set('q', o.q)
  if (o.place) p.set('at', o.place) // not `place`: ?place= opens the place sheet
  const s = p.toString()
  return `/posts${s ? `?${s}` : ''}`
}
export const writeHref = (place?: string) => `/posts/new${place ? `?at=${encodeURIComponent(place)}` : ''}`

// A photo: the 480px thumbnail for the server's pictures, the original when that fails; an author's own picture is shown as it is.
export function Pic({ src, alt = '', className, eager = false }: { src: string; alt?: string; className?: string; eager?: boolean }) {
  const [shown, setShown] = useState(() => thumbOf(src) ?? src)
  useEffect(() => { setShown(thumbOf(src) ?? src) }, [src])
  if (!src) return <span className={`tg-bp-nopic ${className ?? ''}`} role="img" aria-label={alt || 'Chưa có ảnh'}><Icon name="image" size={22} /></span>
  return <img className={className} src={shown} alt={alt} loading={eager ? 'eager' : 'lazy'} decoding="async" onError={() => { if (shown !== src) setShown(src) }} />
}
export const PlacePic = ({ id, n = 0, className, eager }: { id: string; n?: number; className?: string; eager?: boolean }) =>
  <Pic src={srcOf({ placeId: id }, `cover:${n}`)} alt={info(id)?.name ?? ''} className={className} eager={eager} />

export const Avatar = ({ name, size = 28, me = false }: { name: string; size?: number; me?: boolean }) =>
  <span className={`tg-bp-av ${me ? 'is-me' : ''}`} style={{ width: size, height: size, fontSize: size * 0.38 }} aria-hidden="true">{initialsOf(name)}</span>

export const Rating = ({ value }: { value: number | null | undefined }) =>
  value ? <span className="tg-bp-rate"><Icon name="star" size={13} style={{ fill: 'currentColor' }} />{value.toFixed(1)}</span> : null

export const Visibility = ({ vis }: { vis: Post['vis'] }) => (
  <span className="tg-bp-vis"><Icon name={vis === 'public' ? 'link' : vis === 'friends' ? 'users' : 'lock'} size={13} />{VIS[vis]}</span>
)

export const Editorial = () => <span className="tg-bp-demo is-ed" title="Bài TripGuardian viết từ dữ liệu đã kiểm chứng: thông tin trong bài đều có nguồn">TripGuardian biên tập</span>
export const Demo = () => <span className="tg-bp-demo" title="Bài viết mẫu để xem giao diện, chưa phải của người dùng thật">Bài mẫu</span>

// The six reactions, drawn (no emoji font needed).
export function ReactIcon({ k, size = 20 }: { k: ReactKey; size?: number }) {
  const face = (c: string) => <circle cx="12" cy="12" r="12" fill={c} />
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" style={{ flex: 'none' }}>
      {k === 'like' && <>{face('#3b82f6')}<path fill="#fff" d="M6.5 10.5h2.4V18H6.5zM10.2 10.6l2.6-5c1.3 0 2.1 1 1.8 2.3l-.5 2.1h3.6a1.6 1.6 0 0 1 1.6 2l-1.1 4.7a1.8 1.8 0 0 1-1.7 1.3h-6.3z" /></>}
      {k === 'love' && <>{face('#e0245e')}<path fill="#fff" d="M12 18.2s-5.7-3.5-5.7-7.4a3.2 3.2 0 0 1 5.7-1.9 3.2 3.2 0 0 1 5.7 1.9c0 3.9-5.7 7.4-5.7 7.4z" /></>}
      {k === 'haha' && <>{face('#f7b928')}<path d="M7 9.8q1.4-1.6 2.8 0M14.2 9.8q1.4-1.6 2.8 0" stroke="#5b3a00" strokeWidth="1.5" fill="none" strokeLinecap="round" /><path d="M6.8 13h10.4a5.2 5.2 0 0 1-10.4 0z" fill="#5b3a00" /></>}
      {k === 'wow' && <>{face('#f7b928')}<circle cx="8.3" cy="10" r="1.5" fill="#5b3a00" /><circle cx="15.7" cy="10" r="1.5" fill="#5b3a00" /><ellipse cx="12" cy="16.2" rx="2.3" ry="3" fill="#5b3a00" /></>}
      {k === 'sad' && <>{face('#f7b928')}<circle cx="8.3" cy="10.2" r="1.4" fill="#5b3a00" /><circle cx="15.7" cy="10.2" r="1.4" fill="#5b3a00" /><path d="M8 17.2q4-3.4 8 0" stroke="#5b3a00" strokeWidth="1.6" fill="none" strokeLinecap="round" /></>}
      {k === 'thanks' && <>{face('#2f9e6e')}<path d="M7 12.5l3.2 3.2L17 8.8" stroke="#fff" strokeWidth="2.2" fill="none" strokeLinecap="round" strokeLinejoin="round" /></>}
    </svg>
  )
}
