import * as Dialog from '@radix-ui/react-dialog'
import { useState, type CSSProperties } from 'react'
import { fmtMin, fmtVnd, info } from '../../lib'
import { usePlanning } from '../../planning/planning'
import type { Backups, CrowdTip, DayConditions } from '../../planning/types'
import { useUi } from '../../store'
import { useTrip } from '../../trip'
import { lodgingSuggest } from '../../tu/api'
import type { LodgingHit } from '../../tu/types'
import { PlacePhoto } from '../../ui/common'
import { PlaceInput } from '../../ui/PlaceInput'
import { CountUp } from '../../ui/CountUp'
import { Icon } from '../../ui/icons'
import { BLOCK, costText, openPlace, ROBUST_TAG } from './shared'

// Side cards, notices and dialogs of the itinerary screens (screens/Plan.tsx, screens/plan/*).

export const ADVISORY: Record<string, string> = { storm: 'bão / dông', flood: 'ngập lụt', landslide: 'sạt lở', fire: 'cháy', road_closed: 'đường bị chặn', other: 'khác' }

export function KeepAll({ variant, busy, onPick }: { variant: NonNullable<import('../../planning/types').View['keep_all']>; busy: boolean; onPick: (id: string) => void }) {
  return <details className="tg-sidecard"><summary>Giữ tất cả · Đối chiếu danh sách ban đầu</summary>
    <p>{variant.kept?.length ?? variant.metrics.places} nơi · ≈{fmtMin(variant.metrics.travel_min)} di chuyển · {costText(variant)}{variant.metrics.cost_unknown ? ` + ${variant.metrics.cost_unknown} nơi chưa có giá` : ''} · {ROBUST_TAG[variant.robustness.level] ?? variant.robustness.label}</p>
    <p className="tg-faint">Cùng điểm xuất phát của lịch gốc. Chi phí địa điểm đã biết; thời gian đi lại là ước lượng.</p>
    {variant.violations.map((v, i) => <p key={i}>{v.detail}</p>)}
    {variant.itinerary.map(d => <div key={d.day}><b>Ngày {d.day}</b><ol>{d.items.map((it, i) => <li key={i}>{it.start}–{it.end} · {it.name ?? it.note ?? BLOCK[it.kind] ?? 'Di chuyển'}</li>)}</ol></div>)}
    <button type="button" className="tg-btn tg-btn--soft" disabled={busy || !variant.confirmable} onClick={() => onPick(variant.id)}>Chọn Giữ tất cả</button>
    {!variant.confirmable && <p className="tg-faint">Lịch gốc còn lỗi nên chưa thể chọn để chốt.</p>}
  </details>
}

// Facts about the date, from live sources and hand-entered notices; no notice is not the same as "all clear".
// max: how many lines show before "Xem thêm"; a warning is never folded away.
export function Conditions({ c, tips, max }: { c: DayConditions | undefined; tips: CrowdTip[]; max?: number }) {
  const [all, setAll] = useState(false)
  const items: { icon: 'rain' | 'cloud' | 'users' | 'calendar' | 'warn' | 'info' | 'clock'; text: string; warn: boolean }[] = []
  if (c) {
    if (c.weather !== 'none') {
      const what = [c.storm ? 'dông' : '', c.rain_mm ? `mưa ~${Math.round(c.rain_mm)} mm` : '', c.gust_kmh ? `gió giật ~${Math.round(c.gust_kmh)} km/h` : ''].filter(Boolean).join(', ')
      items.push({ icon: 'rain', text: `${c.weather === 'severe' ? 'Thời tiết rất xấu' : c.weather_cause ? c.weather_cause[0].toUpperCase() + c.weather_cause.slice(1) : 'Mưa lớn hoặc dông'}${what ? ` (${what})` : ''}`, warn: true })
    } else items.push({ icon: 'cloud', text: c.rain_mm === null ? 'Chưa có số liệu thời tiết cho ngày này' : 'Dự báo không có mưa lớn', warn: false })
    for (const a of c.advisories) items.push({ icon: 'warn', text: `Thông báo ${ADVISORY[a.kind] ?? a.kind}: ${a.note || 'xem nguồn'} (${a.source})`, warn: true })
    if (c.crowd !== 'normal') items.push({ icon: 'users', text: `${c.crowd === 'peak' ? 'Rất đông' : 'Đông hơn thường'}: ${c.crowd_reasons.join(', ')}`, warn: true })
    if (c.day_type !== 'weekday') items.push({ icon: 'calendar', text: c.day_type === 'holiday' ? 'Ngày lễ' : 'Cuối tuần', warn: c.day_type === 'holiday' })
    if (c.closure_risk) items.push({ icon: 'warn', text: `Dịp ${c.closure_risk}: nhiều quán đóng cửa hoặc đổi giờ, gọi xác nhận trước`, warn: true })
    if (c.crowd !== 'normal') tips.slice(0, 2).forEach((t) => items.push({ icon: 'clock', text: t.text, warn: false }))
  }
  if (!c || (!c.advisories.length && c.crowd === 'normal' && !c.closure_risk)) items.push({ icon: 'info', text: 'Chưa có thông báo hay sự kiện ghi nhận cho ngày này (không có nghĩa là chắc chắn bình thường).', warn: false })
  let room = max ?? items.length
  const shown = all || max === undefined ? items : items.filter((x) => (x.warn ? true : room-- > 0))
  const folded = items.length - shown.length
  return (
    <div className="tg-cond" aria-label="Điều kiện ngày">
      <ul>{shown.map((x, i) => <li key={`${i}:${x.text}`} className={x.warn ? 'is-warn' : ''}><Icon name={x.icon} size={16} />{x.text}</li>)}</ul>
      {(folded > 0 || (all && max !== undefined && items.length > max)) && <button type="button" className="tg-link" aria-expanded={all} onClick={() => setAll((v) => !v)}>{all ? 'Thu gọn' : `Xem thêm ${folded} ghi chú`}</button>}
    </div>
  )
}

export function VisitDuration({ place, name, minutes, bounds, manual, disabled, onPreview }: {
  place: string; name: string; minutes: number; bounds?: [number, number]; manual: boolean;
  disabled: boolean; onPreview: (place: string, minutes: number | null) => void
}) {
  const [value, setValue] = useState(String(minutes))
  if (!bounds) return null
  const valid = Number.isInteger(Number(value)) && Number(value) >= bounds[0] && Number(value) <= bounds[1]
  return <details className="tg-duration">
    <summary className="tg-link">{manual ? 'Thời lượng đã chỉnh' : 'Chỉnh thời lượng'}</summary>
    <p className="tg-faint">Ước lượng theo lựa chọn và nhịp chuyến đi. Chỉnh tay có thể ảnh hưởng các giờ ghé và bữa ăn.</p>
    <form onSubmit={e => { e.preventDefault(); if (valid && !disabled) onPreview(place, Number(value)) }}>
      <label>Thời gian ở {name} (phút)<input type="number" min={bounds[0]} max={bounds[1]} step="1" required value={value} disabled={disabled} onChange={e => setValue(e.target.value)} /></label>
      <div className="tg-duration__actions">
        {[30, 60, 90, 150].filter(n => n >= bounds[0] && n <= bounds[1]).map(n => <button key={n} type="button" className="tg-btn tg-btn--soft tg-btn--sm" disabled={disabled} aria-pressed={Number(value) === n} onClick={() => setValue(String(n))}>{n} phút</button>)}
        <button type="submit" className="tg-btn tg-btn--primary tg-btn--sm" disabled={disabled || !valid}>Xem ảnh hưởng</button>
        {manual && <button type="button" className="tg-link" disabled={disabled} onClick={() => onPreview(place, null)}>Dùng lại ước lượng</button>}
      </div>
      {!valid && <p className="tg-faint" role="status">Nhập số phút nguyên từ {bounds[0]} đến {bounds[1]}.</p>}
    </form>
  </details>
}

// No lodging picked: the plan is still laid out (days start at the first stop), the user is told and decides.
// The trip has no lodging yet: Lịch trình (not Lựa chọn) suggests a few of the stays Planning ranked for it, each
// picked here in one tap (pick_lodging); "Xem tất cả" opens the full list on Lựa chọn's Chỗ ở tab.
export function NoHotel({ onHotel }: { onHotel: () => void }) {
  const { view, act, busy } = usePlanning()
  const lod = view?.lodging
  const picks = lod?.candidates.slice(0, 3) ?? []
  return (
    <section className="tg-it-stays" aria-labelledby="tg-it-stays-h">
      <div className="tg-it-stays__head">
        <h3 id="tg-it-stays-h"><Icon name="bed" size={17} /> Gợi ý chỗ ở cho chuyến này</h3>
        <button type="button" className="tg-link" onClick={onHotel}>Xem tất cả chỗ ở</button>
      </div>
      <p className="tg-faint">Mỗi ngày bắt đầu và kết thúc ở chỗ ở; chọn một chỗ để lịch tính đường đi sáng và tối. Chưa chọn cũng không sao.</p>
      {lod?.status === 'pending' ? <p className="tg-faint" role="status">Đang tìm chỗ ở hợp với chuyến…</p>
        : picks.length === 0 ? <p className="tg-faint">Chưa có gợi ý chỗ ở cho chuyến này. Bạn tìm chỗ ở trong "Xem tất cả chỗ ở".</p>
        : (
          <ul className="tg-it-stays__list">
            {picks.map((c) => (
              <li key={c.id} className="tg-it-stay">
                {info(c.id) ? <PlacePhoto id={c.id} name={c.name} className="tg-it-stay__ph" /> : <span className="tg-it-stay__ph" aria-hidden="true"><Icon name="bed" size={22} /></span>}
                <div className="tg-it-stay__b">
                  <b>{c.name}</b>
                  <span className="tg-faint">{[c.rating ? `★ ${c.rating.toFixed(1)}` : null, c.price_vnd ? `${fmtVnd(c.price_vnd)}/đêm` : 'Chưa có giá', c.avg_min != null ? `≈ ${fmtMin(c.avg_min)} tới các nơi đã chọn` : null].filter(Boolean).join(' · ')}</span>
                  {c.fit?.[0] && <span className="tg-it-stay__why"><Icon name="check" size={13} /> {c.fit[0].text}</span>}
                </div>
                <button type="button" className="tg-btn tg-btn--primary tg-btn--sm" disabled={busy} onClick={() => { void act({ type: 'pick_lodging', id: c.id }) }}>Chọn</button>
              </li>
            ))}
          </ul>
        )}
    </section>
  )
}

// Where to sleep, while none is chosen: the stays Planning ranked for the trip, as a row of cards across the whole frame (up to
// eight). "Chọn" picks one (pick_lodging); the photo opens the place. A suggestion, not a choice: nothing changes until the
// user picks, and not picking is fine.
const STAYS_SHOWN = 8
// Where to sleep, shown when the pointer rests on the lodging row: a search by name, then the stays that fit the chosen places.
export function LodgingGhost() {
  const { view, act, busy } = usePlanning()
  const lod = view?.lodging
  const chosen = view?.state.lodging_id
  const picks = (lod?.candidates ?? []).filter((c) => c.id !== chosen).slice(0, STAYS_SHOWN)
  const [searching, setSearching] = useState(false) // something is typed: the results take the stage, the suggestions step back
  return (
    <section className={`tg-ghost tg-staygrid${searching ? ' is-searching' : ''}`} aria-label="Gợi ý chỗ nghỉ">
      <header>
        <Icon name="sparkle" size={14} />
        <b>Gợi ý · Chỗ nghỉ</b>
        {picks.length > 0 && <small>{picks.length} chỗ hợp với các nơi đã chọn</small>}
      </header>
      <PlaceInput<LodgingHit> label="Tìm chỗ nghỉ" placeholder="Tìm chỗ nghỉ theo tên" icon="bed" disabled={busy} fetcher={lodgingSuggest}
        row={(h) => ({ key: h.id ?? `${h.lat},${h.lng}`, icon: 'bed', photoId: h.kind === 'corpus' && h.id ? h.id : undefined, name: h.text, sub: [h.rating ? `★ ${h.rating.toFixed(1)}` : null, h.address].filter(Boolean).join(' · '), rating: null })}
        onQuery={(q) => setSearching(q.trim().length >= 2)} onPick={(h) => { setSearching(false); void act(h.kind === 'corpus' && h.id ? { type: 'pick_lodging', id: h.id } : { type: 'set_lodging', text: h.text, lat: h.lat, lng: h.lng }) }} />
      {lod?.status === 'pending' ? <p className="tg-faint" role="status">Đang tìm chỗ nghỉ hợp với chuyến…</p>
        : picks.length === 0 ? <p className="tg-faint">Chưa có gợi ý. Bạn thử tìm theo tên ở ô trên.</p>
        : (
          <ul>
            {picks.map((c, i) => (
              <li key={c.id} style={{ '--i': i } as CSSProperties}>
                <button type="button" className="tg-staygrid__ph" aria-label={`Xem chi tiết ${c.name}`} onClick={() => openPlace(c.id)}><PlacePhoto id={c.id} name="" sizes="260px" /></button>
                <div className="tg-staygrid__txt">
                  <strong title={c.name}>{c.name}</strong>
                  <small>{[c.rating ? `★ ${c.rating.toFixed(1)}` : null, c.price_vnd ? `${fmtVnd(c.price_vnd)}/đêm` : 'Chưa có giá'].filter(Boolean).join(' · ')}</small>
                  {c.avg_min != null && <small>≈ {fmtMin(c.avg_min)} tới các nơi đã chọn</small>}
                </div>
                <button type="button" className="tg-btn tg-btn--primary tg-btn--sm" disabled={busy} aria-label={`Chọn ${c.name}`} onClick={() => { void act({ type: 'pick_lodging', id: c.id }) }}><Icon name="plus" size={15} />Chọn</button>
              </li>
            ))}
          </ul>
        )}
    </section>
  )
}

export function Lodging({ onChange }: { onChange: () => void }) {
  const { view, busy } = usePlanning()
  if (!view) return null
  const point = view.state.lodging_point
  const placeId = typeof point?.place_id === 'string' ? point.place_id : null
  const name = view.state.lodging_id ? String(point?.text ?? view.lodging.candidates.find((c) => c.id === view.state.lodging_id)?.name ?? 'Chỗ ở đã chọn') : 'Chưa chọn chỗ ở'

  return (
    <section className="tg-sidecard" aria-labelledby="tg-lod-h">
      <h2 id="tg-lod-h"><Icon name="bed" size={18} /> Chỗ nghỉ đêm</h2>
      {placeId && info(placeId) && <PlacePhoto id={placeId} name={name} className="tg-sidecard__ph" />}
      <p><b>{name}</b><br /><small className="tg-faint">Mỗi ngày bắt đầu và kết thúc ở đây. Giá là tham khảo.</small></p>
      <button type="button" className="tg-link" disabled={busy} onClick={onChange}>{view.state.lodging_id ? 'Đổi chỗ ở' : 'Chọn chỗ ở'}</button>
    </section>
  )
}

// Backups of the day on screen: a stand-in for a place that may fail (rain, hours) and what to drop first when late.
export function BackupCard({ b, day, busy, onSwap }: { b: Backups | undefined; day: number; busy: boolean; onSwap: (place: string, w: string) => void | Promise<void> }) {
  const items = b?.places.filter((x) => x.day === day && x.alternatives.length > 0) ?? [] // a place with no stand-in has nothing to offer here
  const late = b?.on_delay.find((x) => x.day === day)
  if (!items.length && !late) return null
  return (
    <section className="tg-sidecard" aria-labelledby="tg-bk-h">
      <h2 id="tg-bk-h"><Icon name="shield" size={18} /> Phương án dự phòng · Ngày {day}</h2>
      {items.slice(0, 3).map((x) => (
        <div key={x.place_id} className="tg-backup">
          <b>{x.text ? `${x.name}: nếu ${x.text.toLowerCase()}` : x.name}</b>
          {x.alternatives.slice(0, 2).map((a) => <div key={a.id} className="tg-backup">
            <button type="button" className="tg-btn tg-btn--soft tg-btn--sm" disabled={busy} onClick={() => onSwap(x.place_id, a.id)}>Thay bằng {a.name}{a.minutes_rough ? ` (≈${a.minutes_rough}′)` : ''}</button>
            {a.warnings?.map((w, i) => <small key={i} className="tg-faint">{w.text}</small>)}
          </div>)}
        </div>
      ))}
      {late && <div className="tg-backup"><b>Bị trễ</b><span>Bỏ {late.name} trước, giữ phần còn lại</span></div>}
      <p className="tg-faint tg-sidecard__mini">Chỉ thay khi bạn bấm chọn.</p>
    </section>
  )
}

// "Tối ưu lịch": the server's search (no model), kept only when it passes the checks, is better and never drives more.
// A card in the middle of the screen with the verdict first: how much travel it saves (before / after as two bars), what
// else got better, why it is safe, one button.
export function Optimize({ open, onClose, onUndo, busy }: { open: boolean; onClose: () => void; onUndo: () => void; busy: boolean }) {
  const { trip } = useTrip()
  const o = useUi((u) => (trip.planningId ? u.optimized[trip.planningId] : undefined))
  const better = o?.status === 'accepted' && (o.changed ?? o.after < o.before)
  const saved = o ? o.before - o.after : 0
  const b = o?.parts?.before, a = o?.parts?.after
  const gains = b && a ? [
    a.problems < b.problems && `Bớt ${b.problems - a.problems} chỗ vướng giờ mở cửa hoặc khung ngày`,
    a.meals_missed < b.meals_missed && 'Đủ bữa hơn',
    a.spread_min + 15 <= b.spread_min && 'Các ngày đều tay hơn, không ngày nào quá nặng',
    a.time_penalty + 5 <= b.time_penalty && 'Nhiều nơi được ghé đúng giờ đẹp hơn',
    a.pace_excess < b.pace_excess && 'Số nơi mỗi ngày đúng nhịp bạn chọn hơn',
  ].filter((x): x is string => !!x) : []
  const tone = !o ? 'wait' : better ? 'good' : o.status === 'accepted' ? 'calm' : 'info'
  const title = !o ? 'Đang thử xếp lại…' : better ? 'Mình xếp lại được tốt hơn' : o.status === 'accepted' ? 'Lịch hiện tại đã khá gọn' : 'Giữ lịch hiện tại'
  return (
    <Dialog.Root open={open} onOpenChange={(v) => !v && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="tg tg-overlay" />
        <Dialog.Content className={`tg tg-optim is-${tone}`} aria-describedby={undefined}>
          <Dialog.Close className="tg-icon-btn tg-optim__x" aria-label="Đóng"><Icon name="x" size={20} /></Dialog.Close>
          <span className="tg-optim__ic" aria-hidden="true">{!o ? <span className="tg-dots"><i /><i /><i /></span> : <Icon name={better ? 'sparkle' : o.status === 'accepted' ? 'check' : 'info'} size={26} />}</span>
          <p className="tg-optim__tag">Đề xuất tối ưu</p>
          <Dialog.Title>{title}</Dialog.Title>
          {o && better && (
            <>
              {saved > 0 && (
                <>
                  <div className="tg-optim__bars" role="img" aria-label={`Di chuyển giảm từ ${fmtMin(o.before)} xuống ${fmtMin(o.after)}`}>
                    <div><span>Trước</span><i style={{ width: '100%' }} /><b className="tg-mono">{fmtMin(o.before)}</b></div>
                    <div className="is-after"><span>Sau</span><i style={{ width: `${Math.max(8, Math.round((o.after / o.before) * 100))}%` }} /><b><CountUp from={o.before} to={o.after} render={fmtMin} /></b></div>
                  </div>
                  <p className="tg-optim__save">Tiết kiệm khoảng <b>{fmtMin(saved)}</b> di chuyển, tính cả đường đi về chỗ ở</p>
                </>
              )}
              <ul className="tg-optim__why">
                {gains.map((g) => <li key={g}><Icon name="sparkle" size={15} />{g}.</li>)}
                <li><Icon name="check" size={15} />Chia lại ngày theo khu và xếp lại thứ tự để bớt quay đầu, không đi xe nhiều hơn lịch cũ.</li>
                <li><Icon name="check" size={15} />Đã qua kiểm tra giờ mở cửa, bữa ăn, nơi đã khóa và giới hạn của bạn.</li>
                <li><Icon name="shield" size={15} />Không đổi chỗ ở, nhịp độ, nơi đã khóa hay tập địa điểm.</li>
              </ul>
            </>
          )}
          {o && !better && <p className="tg-optim__msg">{o.status === 'accepted' ? `Lịch hiện tại đã là cách xếp tốt nhất mình tìm được: không cách nào bớt đi xe, đều ngày hơn hay đúng giờ đẹp hơn mà vẫn qua kiểm tra. Lịch chỉ mất ${fmtMin(o.after)} di chuyển.` : 'Cách xếp mới chưa qua được kiểm tra hoặc không tốt hơn, nên mình giữ lịch bạn đang có. Lịch của bạn không bị thay đổi.'}</p>}
          <div className="tg-optim__acts">{better && <button type="button" className="tg-btn tg-btn--ghost" disabled={busy} onClick={onUndo}>Giữ lịch cũ</button>}<button type="button" className="tg-btn tg-btn--primary" onClick={onClose}>{better ? 'Giữ cách xếp mới' : 'Đã hiểu'} <Icon name="check" size={18} /></button></div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
