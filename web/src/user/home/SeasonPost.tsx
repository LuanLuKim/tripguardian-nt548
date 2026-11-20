import * as Dialog from '@radix-ui/react-dialog'
import { useState, type ReactNode } from 'react'
import { PlacePhoto } from '../ui/common'
import { info } from '../lib'
import { Icon, Logo } from '../ui/icons'
import { openPlace } from '../ui/PlaceSheet'
import type { Item } from './Pulse'
import { plain } from './EventPost'
import { Binding, FlipPoster, type Leaf } from './FlipPoster'
import '../css/event.css'

// A season of the Trending bulletin as the same kind of post as an event (home/EventPost.tsx): the season's picture, its months, the summary
// the server wrote, and the places worth seeing in it (only places the snapshot knows). Nothing is added that the bulletin does not say.
const cap = (s: string) => s[0].toUpperCase() + s.slice(1)

// "Đang vào mùa · tháng 10–1" -> "Tháng 10–1": the status is the tab's own, only the months say something.
export const monthsOf = (it: Item) => cap((it.signal ?? '').replace(/^Đang vào mùa\s*·\s*/i, '').trim())

// The season's picture (the article's, a hotlink: no referrer sent); when it is missing or fails, the photo of the first place worth seeing, else a warm sun tile.
export function SeasonThumb({ it, sizes = '140px' }: { it: Item; sizes?: string }) {
  const [broken, setBroken] = useState(false)
  const first = (it.see ?? []).find((id) => info(id)?.photos.length)
  if (it.image && !broken) return <img src={it.image} alt="" loading="lazy" decoding="async" referrerPolicy="no-referrer" onError={() => setBroken(true)} />
  if (first) return <PlacePhoto id={first} name={it.title} sizes={sizes} />
  return <span className="tg-pulse__cal" aria-hidden="true"><Icon name="sun" size={26} /></span>
}

export function SeasonPost({ it, children }: { it: Item; children: ReactNode }) {
  const [open, setOpen] = useState(false)
  const see = (it.see ?? []).filter((id) => info(id))
  // The season's picture, then one photo of each place worth seeing in it (the first of them is already the picture when the season has none).
  const spots = see.filter((id) => info(id)!.photos.length).slice(it.image ? 0 : 1, 4)
  const leaves: Leaf[] = [
    { key: 'season', picture: <SeasonThumb it={it} sizes="520px" />, caption: <>{monthsOf(it) && <em>{monthsOf(it)}</em>}<Dialog.Title>{cap(it.title)}</Dialog.Title></> },
    ...spots.map((id) => ({ key: id, picture: <PlacePhoto id={id} name={info(id)!.name} sizes="520px" />, caption: <><em>Nơi nên ghé</em><strong>{info(id)!.name}</strong></> })),
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
              <p className="tg-ev__brand"><Logo size={20} />TripGuardian · Mùa Đà Lạt</p>
              <FlipPoster leaves={leaves} />
            </div>
            <div className="tg-ev__bottom">
              {monthsOf(it) && <ul className="tg-ev__chips" aria-label="Thông tin nhanh"><li><Icon name="sun" size={13} />{monthsOf(it)}</li>{it.hot && <li className="is-hot"><Icon name="flame" size={13} />Đang hot{it.hot_note ? ` · ${it.hot_note}` : ''}</li>}</ul>}
              {it.summary && <p className="tg-ev__lead">{plain(it.summary)}</p>}
              {see.length > 0 && <dl className="tg-ev__facts">
                <div><dt><Icon name="pin" size={16} />Nơi nên ghé</dt><dd>{see.map((id) => <button key={id} type="button" onClick={(e) => { setOpen(false); openPlace(id, e.currentTarget) }}>{info(id)!.name}<Icon name="arrow" size={13} /></button>)}</dd></div>
              </dl>}
              {(it.sources ?? []).length > 0 && <small>Tổng hợp từ {it.sources.map((s) => s.label).join(', ')}.</small>}
            </div>
          </article>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
