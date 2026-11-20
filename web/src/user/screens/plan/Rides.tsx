import { fmtRange, type RideLeg, type Rides } from '../../rides'
import { Icon } from '../../ui/icons'
import '../../css/rides.css'

// Ride-hailing on the itinerary (rides.ts): one bar per day to pick the vehicle and brand for the whole trip, and on every
// leg a ghost row comparing the brands. Prices are estimates from each brand's published table; no table says so.

export function RideBar({ rides, day }: { rides: Rides; day: number }) {
  if (!rides.ready) return null
  const shown = rides.chosen ?? rides.cheapest(day)
  const t = shown ? rides.total(shown, day) : null
  const gaps = rides.gaps(day)
  const vehicle = rides.kind === 'bike' ? 'xe máy' : 'ô tô'
  return (
    <section className="tg-ride-bar" aria-label="Gọi xe giữa các điểm">
      <div className="tg-ride-bar__head">
        <span><Icon name="car" size={15} /><b>Gọi xe giữa các điểm</b></span>
        <div className="tg-ride-seg" role="radiogroup" aria-label="Loại xe">
          {(['bike', 'car'] as const).map((k) => <button key={k} type="button" role="radio" aria-checked={rides.kind === k} className={rides.kind === k ? 'is-on' : ''} onClick={() => rides.pickKind(k)}>{k === 'bike' ? 'Xe máy' : 'Ô tô'}</button>)}
        </div>
      </div>
      <p className="tg-ride-bar__sum">
        {t && shown ? <>Cả ngày với <b>{rides.brands[shown].name}</b> {fmtRange(t.lo, t.hi)}{rides.chosen ? ' · hãng bạn chọn' : ' · rẻ nhất'}</> : 'Chưa tính được tổng cước cho ngày này.'}
        {rides.chosen && <button type="button" className="tg-it-textbtn" onClick={() => rides.pickBrand(null)}>Bỏ chọn hãng</button>}
      </p>
      <small className="tg-ride-bar__note">Ước tính theo bảng giá hãng công bố, {rides.kind === 'bike' ? `${rides.people} xe máy` : `ô tô cho ${rides.people} người`}; chưa gồm giờ cao điểm, khuyến mãi.{gaps.no_kind.length ? ` ${gaps.no_kind.join(', ')} không có ${vehicle} ở đây.` : ''}{gaps.no_table.length ? ` ${gaps.no_table.join(', ')} chưa công bố bảng giá ở đây.` : ''}</small>
    </section>
  )
}

export function RideGhost({ rides, leg }: { rides: Rides; leg: RideLeg }) {
  const rows = rides.rowsFor(leg)
  const best = rows.filter((r) => r.price).sort((a, b) => a.price!.lo - b.price!.lo)[0]?.brand
  return (
    <div className="tg-ride" role="group" aria-label={`Gọi xe chặng ${leg.km} km`}>
      <span className="tg-ride__km">{leg.km} km</span>
      {rows.map((r) => r.price ? (
        <button key={r.brand} type="button" aria-pressed={rides.chosen === r.brand} title={`${r.price.label}${r.price.count > 1 ? ` × ${r.price.count}` : ''} · ước tính`}
          className={`tg-ride__chip${rides.chosen === r.brand ? ' is-on' : ''}${!rides.chosen && best === r.brand ? ' is-best' : ''}`}
          onClick={() => rides.pickBrand(rides.chosen === r.brand ? null : r.brand)}>
          <b>{r.name}</b><span>{fmtRange(r.price.lo, r.price.hi)}</span><small>{r.price.label.replace(`${r.name} · `, '')}{r.price.count > 1 ? ` × ${r.price.count}` : ''}</small>
        </button>
      ) : <span key={r.brand} className="tg-ride__chip is-none" title={r.missing === 'no_kind' ? `Hãng không có ${rides.kind === 'bike' ? 'xe máy' : 'ô tô'} ở khu vực này` : 'Hãng chưa công bố bảng giá ở khu vực này'}><b>{r.name}</b><span>{r.missing === 'no_kind' ? (rides.kind === 'bike' ? 'không có xe máy' : 'không có ô tô') : 'chưa có giá'}</span></span>)}
    </div>
  )
}
