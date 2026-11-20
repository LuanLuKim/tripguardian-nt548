import type { DishBlock, ResultBlock, ServiceRow, ServicesBlock } from '../../tu/types'
import { fold } from '../../search'
import { SubtagBlock } from '../../tags/Subtags'
import { ClipsLine } from './Clips'
import { PlaceStage } from './Places'
import { Trends } from './Trends'

// Dish results open place cards; evidence and external links belong in the place sheet.

function Dish({ block, busy, onLike }: { block: DishBlock; busy: boolean; onLike: (id: string, on: boolean) => void }) {
  const dish = block.places.flatMap(p => p.evidence).map(e => e.dish).find(d => d && fold(d) === fold(block.dish)) ?? block.dish
  return <section className="tg-cx-dish" aria-label={`Quán có món ${dish}`}>
    <PlaceStage row={{ ids: block.places.map(p => p.id), why: `Quán có món “${dish}”`, cards: block.cards }} busy={busy} autoOpen={false} onLike={onLike} />
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

export function Block({ block, busy, autoOpen, onLike }: { block: ResultBlock; busy: boolean; autoOpen?: boolean; onLike: (id: string, on: boolean) => void }) {
  if (block.kind === 'tags') return <SubtagBlock block={block} autoOpen={autoOpen} onLike={onLike} />
  if (block.kind === 'trends') return <Trends block={block} busy={busy} onLike={onLike} />
  if (block.kind === 'clips') return <ClipsLine block={block} busy={busy} onLike={onLike} />
  return block.kind === 'dish' ? <Dish block={block} busy={busy} onLike={onLike} /> : <Services block={block} />
}
