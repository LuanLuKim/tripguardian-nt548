import { useSnapshot } from '../../../data/store'
import { fmtVnd, info } from '../../lib'
import type { DishBlock, DishEvidence, ResultBlock, ServiceRow, ServicesBlock } from '../../tu/types'
import { Icon } from '../../ui/icons'
import { PlaceStage } from './Places'

// What a read tool found, shown as the backend returned it (src/trip/api/blocks.py): a dish -> the places that serve
// it with the evidence line of each, or a list of services (ATM, pharmacy, rental, coach station), never place
// cards. A field the backend did not send is not drawn.

const SOURCE: Record<DishEvidence['source'], string> = {
  menu_popular: 'Món nổi bật trong thực đơn của quán',
  name: 'Tên quán nói về món này',
  menu: 'Có trong thực đơn của quán',
  menu_photo: 'Đọc từ ảnh thực đơn',
  review_order: 'Khách đã gọi món này',
}

function Dish({ block, busy, onLike }: { block: DishBlock; busy: boolean; onLike: (id: string, on: boolean) => void }) {
  useSnapshot()
  const names = new Map(block.cards.map(c => [c.id, c.name]))
  return <section className="tg-cx-dish" aria-label={`Quán có món ${block.dish}`}>
    <PlaceStage row={{ ids: block.places.map(p => p.id), why: `Quán có món “${block.dish}”`, cards: block.cards }} busy={busy} autoOpen={false} onLike={onLike} />
    <ul className="tg-cx-dish__list">
      {block.places.map(p => {
        const maps = info(p.id)?.mapsUrl
        return <li key={p.id}>
          <b>{names.get(p.id) ?? info(p.id)?.name ?? 'Nơi này'}</b>
          {p.evidence.map((e, i) => <p key={i}>
            <span className="tg-cx-dish__src">{SOURCE[e.source] ?? e.source}</span>
            {e.dish && <> · {e.dish}</>}
            {e.section && <> ({e.section})</>}
            {e.price_vnd ? <> · <span className="tg-cx-dish__price">{fmtVnd(e.price_vnd)}</span></> : null}
            {e.n && e.n > 1 ? <> · {e.n} người nhắc</> : null}
            {e.quote && <q>{e.quote}</q>}
          </p>)}
          {maps && <a className="tg-link" href={maps} target="_blank" rel="noreferrer">Xem trên Google Maps <Icon name="external" size={13} /></a>}
        </li>
      })}
    </ul>
  </section>
}

const hoursOf = (h: ServiceRow['hours']) => (Array.isArray(h) ? h.join(' · ') : h)

function Services({ block }: { block: ServicesBlock }) {
  return <section className="tg-cx-svc" aria-label="Tiện ích và dịch vụ">
    <p className="tg-cx-svc__head">{block.anchor ? `Gần ${block.anchor}` : 'Tìm thấy'} · {block.found > block.rows.length ? `${block.rows.length}/${block.found}` : block.rows.length} nơi</p>
    <ul>
      {block.rows.map((r, i) => <li key={`${r.name}-${i}`}>
        <b>{r.name}</b>
        <small>{[r.kind, r.distance_km != null ? `${r.distance_km} km` : null, r.rating ? `★ ${r.rating.toFixed(1)}` : null, r.open_status].filter(Boolean).join(' · ')}</small>
        {r.address && <span>{r.address}</span>}
        {r.hours && <span>Giờ mở: {hoursOf(r.hours)}</span>}
        <span className="tg-cx-svc__links">
          {r.phone && <a className="tg-link" href={`tel:${r.phone.replace(/\s/g, '')}`}>{r.phone}</a>}
          {r.website && <a className="tg-link" href={r.website} target="_blank" rel="noreferrer">Trang web</a>}
          {r.maps_url && <a className="tg-link" href={r.maps_url} target="_blank" rel="noreferrer">Google Maps</a>}
        </span>
      </li>)}
    </ul>
    <small className="tg-cx-svc__src">{[...block.sources, block.crawled ? `thu thập ${block.crawled}` : null].filter(Boolean).join(' · ')} · số điện thoại và giờ mở có thể đã đổi</small>
  </section>
}

export function Block({ block, busy, onLike }: { block: ResultBlock; busy: boolean; autoOpen?: boolean; onLike: (id: string, on: boolean) => void }) {
  return block.kind === 'dish' ? <Dish block={block} busy={busy} onLike={onLike} /> : <Services block={block} />
}
