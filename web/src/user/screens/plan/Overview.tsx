import type { ReactNode } from 'react'
import { dayLabel, fmtMin, info } from '../../lib'
import type { ItineraryDay, Robustness, Variant } from '../../planning/types'
import { PlacePhoto } from '../../ui/common'
import { Icon, type IconName } from '../../ui/icons'
import { TripMap } from './TripMap'
import { dayAreas, placeName, ROBUST_TAG, shortDate, visits, wayName } from './shared'

// Mẫu docs/design/mock/designs/itinerary (màn tổng quan): the whole trip on one map, then the journey top to bottom —
// arrival, where to sleep, one card per day, departure. A day opens on its own screen.

// How the traveller comes and goes; an unknown way gets a neutral pin, never a plane.
const WAY_ICON: Record<string, IconName> = { plane: 'plane', bus: 'bus', self: 'car' }
const wayIcon = (how?: string | null): IconName => WAY_ICON[how ?? ''] ?? 'pin'

const ROBUST_CLS: Record<string, string> = { solid: 'hi', feasible: 'mid', fragile: 'lo' }

function Row({ icon, title, sub, children }: { icon: IconName; title: string; sub: string; children: ReactNode }) {
  return (
    <div className="tg-it-row">
      <div className="tg-it-row__label"><span><Icon name={icon} size={20} /></span><div><b>{title}</b><small>{sub}</small></div></div>
      <div className="tg-it-row__body">{children}</div>
    </div>
  )
}

export function Overview({ onPlaces, fill, arrivalFill, origin, lodgingGhost, days, variant, robustness, summary, travelMin, visitMin, droppedCount, lodgingName, hasHotel, arriveHow, leaveHow, wayIn, wayOut, stayOffer, notices, after, delta, sameAs, footer, onDay, onChangeVariant, onHotel, onDropped, onWhy, onOpen }: {
  onPlaces?: () => void // back to the schedule map on Lựa chọn: the schedule in detail is a step inside it
  fill?: ReactNode; arrivalFill?: ReactNode; origin?: ReactNode; lodgingGhost?: ReactNode; days: ItineraryDay[]; variant: Variant | null; robustness?: Robustness; summary: { title: string; text: string; wait: boolean }; travelMin: number; visitMin: number; droppedCount: number
  lodgingName: string | null; hasHotel: boolean; arriveHow?: string | null; leaveHow?: string | null; wayIn?: ReactNode; wayOut?: ReactNode; stayOffer?: ReactNode; notices: ReactNode; after: ReactNode; delta: string | null; sameAs: string | null; footer: ReactNode
  onDay: (i: number) => void; onChangeVariant: () => void; onHotel: () => void; onDropped: () => void; onWhy: () => void; onOpen: (id: string) => void
}) {
  const ids = days.flatMap((d) => visits(d).map((it) => it.place_id!))
  const first = days[0]
  const last = days[days.length - 1]
  const range = days.length > 1 ? `${shortDate(first?.date, 1)} – ${shortDate(last?.date, days.length)}` : shortDate(first?.date, 1)
  const label = variant ? wayName(variant) : 'Lịch trình'
  return (
    <>
      <div className="tg-it-crumb">
        <button type="button" className="tg-it-crumb__back" aria-label="Quay lại chọn phương án" onClick={onChangeVariant}><Icon name="arrowLeft" size={18} /></button>
        {onPlaces ? <button type="button" className="tg-it-crumb__up" onClick={onPlaces} title="Về bản đồ lịch trình ở Lựa chọn"><Icon name="map" size={15} />Bản đồ lịch trình</button> : <span>Chuyến đi của bạn</span>}<Icon name="chevronRight" size={14} /><strong>Lịch trình chi tiết</strong>
        <div className="tg-it-crumb__right"><span>Đang xem: {label}</span><button type="button" className="tg-it-textbtn" onClick={onChangeVariant}>Xem phương án khác</button></div>
      </div>
      <main className="tg-it-ov">
        <TripMap groups={days.map((d) => visits(d).map((it) => it.place_id!))} title="Bản đồ cả chuyến" className="is-banner" labels={false} onOpen={onOpen}>
          <span className="tg-it-map__city"><Icon name="pin" size={14} />Đà Lạt</span>
          <button type="button" className="tg-it-map__open" onClick={() => onDay(0)}>Xem lịch &amp; bản đồ <Icon name="arrow" size={15} /></button>
          <span className="tg-it-map__note">Đường nối minh họa thứ tự · không phải chỉ đường</span>
        </TripMap>
        {notices}
        <Row icon="pin" title={`Ngày 1–${days.length}`} sub={range}>
          <div className="tg-it-intro">
            <h1 className={`tg-it-intro__title${summary.wait ? ' is-wait' : ''}`}>{summary.title}</h1>
            <p className={summary.wait ? 'is-wait' : undefined} aria-live="polite">{summary.text}</p>
            {variant && variant.id !== 'main' && variant.tradeoff && <p className="tg-it-intro__trade tg-faint">Đánh đổi: {variant.tradeoff}{sameAs ? ` · Cùng lịch với ${sameAs}.` : ''}</p>}
            {delta && <p className="tg-it-intro__trade tg-faint">{delta}</p>}
            <ul className="tg-it-facts">
              <li><Icon name="route" size={15} />≈ {fmtMin(travelMin)} di chuyển</li>
              <li><Icon name="clock" size={15} />≈ {fmtMin(visitMin)} tham quan</li>
              {robustness && <li>{robustness.reasons.length
                ? <button type="button" className={`tg-robust is-${ROBUST_CLS[robustness.level]}`} onClick={onWhy}>{ROBUST_TAG[robustness.level] ?? robustness.label}</button>
                : <b className={`tg-robust is-${ROBUST_CLS[robustness.level]}`}>{ROBUST_TAG[robustness.level] ?? robustness.label}</b>}</li>}
            </ul>
            <div className="tg-it-plan"><span><Icon name="check" size={14} />{label} · {ids.length} nơi trong lịch</span>{droppedCount > 0 && <button type="button" className="tg-it-textbtn" onClick={onDropped}>{droppedCount} nơi tạm bỏ <Icon name="chevronRight" size={14} /></button>}</div>
          </div>
        </Row>
        {origin && <Row icon="home" title="Điểm xuất phát" sub="Trước khi đến Đà Lạt">{origin}</Row>}
        <Row icon={wayIcon(arriveHow)} title="Đến Đà Lạt" sub={shortDate(first?.date, 1)}>
          {arrivalFill}
          <div className="tg-it-transit"><span><Icon name={wayIcon(arriveHow)} size={16} /><b>Di chuyển đến Đà Lạt</b></span><span>{first ? `Lịch ngày đầu bắt đầu lúc ${first.window[0]}` : 'Chưa có thông tin chuyến đến'}</span></div>
          {wayIn}
        </Row>
        <Row icon="bed" title="Chỗ nghỉ" sub={days.length > 1 ? `${days.length - 1} đêm` : 'Không nghỉ đêm'}>
          <div className="tg-it-transit"><span><Icon name="bed" size={16} /><b>{hasHotel && lodgingName ? lodgingName : 'Chưa chọn chỗ nghỉ'}</b></span><button type="button" className="tg-it-textbtn" onClick={onHotel}>{hasHotel ? 'Đổi chỗ nghỉ' : 'Chọn chỗ nghỉ'} <Icon name="chevronRight" size={14} /></button></div>
          <div className="tg-reveal"><div>{lodgingGhost}</div></div>
          {stayOffer}
        </Row>
        {fill && <Row icon="sliders" title="Thông tin chuyến" sub="Thêm để lịch hợp hơn">{fill}</Row>}
        <Row icon="calendar" title="Lịch trình" sub={`Ngày 1–${days.length}`}>
          <div className="tg-it-days">
            {days.map((d, i) => {
              const stops = visits(d)
              const cover = stops[0]?.place_id
              const l = dayLabel(d.date)
              return (
                <button key={d.day} type="button" className="tg-it-daycard" style={{ ['--i' as string]: i }} onClick={() => onDay(i)}>
                  {cover && info(cover) ? <PlacePhoto id={cover} name={placeName(cover)} className="tg-it-daycard__ph" /> : <span className="tg-it-daycard__ph tg-photo tg-photo__ph" />}
                  <div>
                    <div className="tg-it-daymeta"><span className="tg-it-pill">Ngày {d.day}</span><span>{l ? `${l.wd} · ${shortDate(d.date)}` : d.weekday || 'Chưa có ngày'}</span><span>·</span><span>{stops.length} điểm dừng</span></div>
                    <h3>{dayAreas(d).join(' · ') || 'Ngày tự do'}</h3>
                    <p>{stops.map((it) => it.name ?? placeName(it.place_id!)).join(' · ') || 'Nghỉ, tự khám phá hoặc thêm nơi'}</p>
                  </div>
                  <Icon name="chevronRight" size={16} />
                </button>
              )
            })}
          </div>
        </Row>
        <Row icon={wayIcon(leaveHow)} title="Rời Đà Lạt" sub={shortDate(last?.date, days.length)}>
          <div className="tg-it-transit"><span><Icon name={wayIcon(leaveHow)} size={16} /><b>Di chuyển về</b></span><span>{last ? `Lịch ngày cuối kết thúc lúc ${last.window[1]}` : 'Chưa có thông tin chuyến về'}</span></div>
          {wayOut}
        </Row>
        {after}
      </main>
      {footer}
    </>
  )
}
