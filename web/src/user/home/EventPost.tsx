import * as Dialog from '@radix-ui/react-dialog'
import { useMemo, useState, type ReactNode } from 'react'
import { useSnapshot } from '../../data/store'
import { DAY_NAMES, info } from '../lib'
import { PlacePhoto } from '../ui/common'
import { Icon, Logo } from '../ui/icons'
import { openPlace } from '../ui/PlaceSheet'
import { Binding, FlipPoster, type Leaf } from './FlipPoster'
import { endOf, type Item } from './Pulse'
import '../css/event.css'

// An event of the Trending bulletin as a small post: the poster (the article's picture, or the venue's photo), the headline over it, then a
// notebook page with what the corpus holds about the event. Every sentence is built from the event's own fields (title, dates, venue, the
// one-line summary the server read from the article, its sources); nothing is added that the bulletin does not say. The quick facts (how
// far away, how many days, which weekday) are counted from its dates; the venue card is the place's own data when the venue is a place we know.

// A page's markup is not part of a sentence: "- **Mùa khô**: …" reads as "Mùa khô: …" (the server cleans it too; an older snapshot may still carry it).
export const plain = (t: string) => t.replace(/\*\*|__|`/g, '').replace(/^\s*(?:[-*+•]|#{1,6}|\d+[.)])\s+/gm, '').replace(/\[([^\]]*)\]\([^)]*\)/g, '$1').replace(/\s+/g, ' ').trim()

export const daysTo = (iso: string, day: string | null) => Math.round((Date.parse(iso) - Date.parse(day ?? new Date().toISOString().slice(0, 10))) / 86_400_000)
export const localDay = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}` }

// "16–20/11 · Quảng trường Lâm Viên" -> when "16–20/11", venue "Quảng trường Lâm Viên".
const cut = (it: Item) => { const k = it.text.indexOf(' · '); return k < 0 ? { when: it.text, venue: '' } : { when: it.text.slice(0, k), venue: it.text.slice(k + 3).trim() } }
// "2026-12-19", "2026-12-31" -> "19–31/12"; one day -> "19/12".
const shortDays = (a: string, b: string) => { const d = (x: string) => `${Number(x.slice(8))}/${Number(x.slice(5, 7))}`; return a === b ? d(a) : a.slice(5, 7) === b.slice(5, 7) ? `${Number(a.slice(8))}–${d(b)}` : `${d(a)}–${d(b)}` }
export const venueOf = (it: Item) => cut(it).venue
export const whenOf = (it: Item) => cut(it).when

// "16–20/11" -> "từ 16 đến 20/11", "20/11, 17:00" -> "ngày 20/11 lúc 17:00", "Ngày 24/11" -> "ngày 24/11"; anything else is said as it is.
function saidWhen(raw: string) {
  const m = /^(?:ngày\s*)?(\d{1,2}(?:\/\d{1,2})?)(?:\s*[–-]\s*(\d{1,2}\/\d{1,2}))?(?:,\s*(\d{1,2}:\d{2}))?$/i.exec(raw.trim())
  if (!m) return raw
  const [, a, b, hour] = m
  return `${b ? `từ ${a} đến ${b}` : `ngày ${a}`}${hour ? ` lúc ${hour}` : ''}`
}
export const leftText = (left: number) => (left <= 0 ? 'Đang diễn ra' : left === 1 ? 'Ngày mai' : `Còn ${left} ngày`)
// How many days the event lasts, counted from its dates (1 when it ends the day it starts).
export function spanDays(it: Item): number {
  const last = endOf(it)
  return it.on && last ? daysTo(last, it.on) + 1 : 1
}

// The venue as a place we know (a name that matches exactly), so its photo can stand in for a missing poster and the post can open it.
// "Quảng trường Lâm Viên, phường Xuân Hương – Đà Lạt", "Mây Lang Thang | Đà Lạt", "… (phường …)": the place is the part before the comma, bar or bracket.
// A venue we do not hold, listed on its organiser's own site ("Mây Heritage" on maylangthang.com.vn): the organiser is the place whose name
// is that site's name ("Mây Lang Thang"). Six letters at least, so a short word never stands for a brand.
const squash = (s: string) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/đ/gi, 'd').toLowerCase().replace(/[^a-z0-9]/g, '')
const brandOf = (url?: string | null) => { try { return url ? new URL(url).hostname.replace(/^www\./, '').split('.')[0] : '' } catch { return '' } }
export function useEventPlace(it: Item, enabled = true) {
  const { snap } = useSnapshot()
  const venue = venueOf(it).toLowerCase()
  const head = venue.split(/[,|(]/)[0].trim()
  const brands = [...new Set(it.sources.map((s) => brandOf(s.url)).filter((b) => b.length >= 6))].join(' ')
  return useMemo(() => {
    if (!enabled || !snap) return undefined
    const named = venue ? snap.places.find((p) => { const n = p.name.toLowerCase(); return n === venue || n === head }) : undefined
    if (named || !brands) return named
    const own = brands.split(' ')
    return snap.places.find((p) => own.includes(squash(p.name)))
  }, [enabled, venue, head, brands, snap])
}

// The picture of an event: the article's own (a hotlink: no referrer sent, credited by its site in the tooltip), else the venue's photo when
// the venue is a place we know, else a warm calendar tile. A picture that fails to load falls to the next one.
export function EventThumb({ it, sizes = '140px' }: { it: Item; sizes?: string }) {
  const [broken, setBroken] = useState(false)
  const credit = typeof it.image_from === 'string' ? it.image_from : it.image_from?.domain
  const place = useEventPlace(it, !it.image || broken)
  if (it.image && !broken) return <img src={it.image} alt="" loading="lazy" decoding="async" referrerPolicy="no-referrer" title={credit ? `Ảnh: ${credit}` : undefined} onError={() => setBroken(true)} />
  if (place && info(place.id)?.photos.length) return <PlacePhoto id={place.id} name={it.title} sizes={sizes} />
  return <span className="tg-pulse__cal" aria-hidden="true"><Icon name="calendar" size={26} /></span>
}

export function EventPost({ it, today, children }: { it: Item; today: string; children: ReactNode }) {
  const [open, setOpen] = useState(false)
  const { when, venue } = cut(it)
  const place = useEventPlace(it, open)
  const left = it.on ? daysTo(it.on, today) : 0
  const web = it.sources.filter((s) => s.type === 'web_document')
  const lines = [
    it.summary && plain(it.summary),
    `${it.title} diễn ra ${saidWhen(when)}${venue ? `, tại ${venue}` : ''}.`,
  ].filter((x): x is string => !!x)
  const credit = typeof it.image_from === 'string' ? it.image_from : it.image_from?.domain
  const span = spanDays(it)
  const chips = [
    { icon: 'clock' as const, text: leftText(left) },
    ...(it.hot ? [{ icon: 'flame' as const, text: `Đang hot${it.hot_note ? ` · ${it.hot_note}` : ''}`, hot: true }] : []),
    ...(span > 1 ? [{ icon: 'calendar' as const, text: `Kéo dài ${span} ngày` }] : []),
    ...(it.on ? [{ icon: 'sun' as const, text: `Bắt đầu ${DAY_NAMES[new Date(`${it.on}T00:00`).getDay()]}` }] : []),
  ]
  const pi = place ? info(place.id) : null
  // The poster, then the venue's own photos when the venue is a place we know (the first is the poster itself when the event has no picture).
  const more = place && pi ? Array.from({ length: Math.min(pi.photos.length, 3) }, (_, k) => k).slice(it.image ? 0 : 1) : []
  const leaves: Leaf[] = [
    { key: 'poster', picture: <EventThumb it={it} sizes="520px" />, caption: <><em>{when}</em><Dialog.Title>{it.title}</Dialog.Title></> },
    ...more.map((k) => ({ key: `v${k}`, picture: <PlacePhoto id={place!.id} i={k} name={place!.name} sizes="520px" />, caption: <><em>Địa điểm</em><strong>{place!.name}</strong></> })),
  ]
  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>{children}</Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="tg tg-overlay" />
        <Dialog.Content className="tg tg-home tg-ev" aria-describedby={undefined}>
          <Dialog.Close className="tg-ev__x" aria-label="Đóng"><Icon name="x" size={18} /></Dialog.Close>
          <article className="tg-ev__paper">
            <Binding />
            <div className="tg-ev__top">
              <p className="tg-ev__brand"><Logo size={20} />TripGuardian · Sự kiện Đà Lạt</p>
              <FlipPoster leaves={leaves} />
            </div>
            <div className="tg-ev__bottom">
              <ul className="tg-ev__chips" aria-label="Thông tin nhanh">{chips.map((c) => <li key={c.text} className={'hot' in c ? 'is-hot' : undefined}><Icon name={c.icon} size={13} />{c.text}</li>)}</ul>
              {lines.map((t, k) => <p key={k} className={k === 0 ? 'tg-ev__lead' : undefined}>{t}</p>)}
              <dl className="tg-ev__facts">
                <div><dt><Icon name="calendar" size={16} />Thời gian</dt><dd>{when}</dd></div>
                {venue && <div><dt><Icon name="pin" size={16} />Địa điểm</dt><dd>{venue}</dd></div>}
                {!!it.parts?.length && <div><dt><Icon name="rows" size={16} />Chương trình</dt><dd><ul className="tg-ev__parts">{it.parts.map((p) => <li key={p.name}><b>{shortDays(p.start, p.end)}{p.time ? ` · ${p.time}` : ''}</b> {p.name}</li>)}</ul></dd></div>}
                {it.sources.length > 0 && <div><dt><Icon name="link" size={16} />Nguồn</dt><dd>{it.sources.map((s, k) => s.url ? <a key={k} href={s.url} target="_blank" rel="noreferrer noopener">{s.label}<Icon name="external" size={12} /></a> : <span key={k}>{s.label}</span>)}</dd></div>}
              </dl>
              {place && <button type="button" className="tg-ev__venue" onClick={(e) => { setOpen(false); openPlace(place.id, e.currentTarget) }}>
                <span className="tg-ev__vph">{pi?.photos.length ? <PlacePhoto id={place.id} name={place.name} sizes="120px" /> : <Icon name="pin" size={20} />}</span>
                <span><strong>{place.name}</strong><small>{[pi?.category, pi?.rating ? `★ ${pi.rating.toFixed(1)}` : null, pi?.area].filter(Boolean).join(' · ') || 'Địa điểm trên bản đồ'}</small></span>
                <em>Xem nơi này<Icon name="arrow" size={13} /></em>
              </button>}
              {web.length > 0 && <small>Tổng hợp từ các trang trên. Giờ giấc có thể thay đổi, kiểm tra lại nguồn trước khi đi.{credit ? ` Ảnh: ${credit}.` : ''}</small>}
            </div>
          </article>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
