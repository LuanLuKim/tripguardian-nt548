import { useEffect, useMemo, useRef, useState } from 'react'
import { info } from '../lib'
import { useDecision } from '../pd/decision'
import { TripMap, warmMap } from '../screens/plan/TripMap'
import { Icon } from './icons'
import { openPlace } from './PlaceSheet'
import { useBar } from './SelectedBar'
import '../css/split.css'

// Lựa chọn, split in two: the "Bản đồ" switch in the page header puts the schedule the current picks would get beside the list of places (the
// route's shape on a map, with a tab per day); "Lưới ảnh" puts the list back alone. It reads the background preview Decision already keeps for
// the "Đã chọn" bar, so nothing new is asked of the server and nothing here is the confirmed plan.
const KEY = 'tg.split'
const readOpen = () => { try { return localStorage.getItem(KEY) === '1' } catch { return false } }

export function useSplit() {
  const [open, setOpen] = useState(readOpen)
  const set = (v: boolean) => { setOpen(v); try { localStorage.setItem(KEY, v ? '1' : '0') } catch { /* private mode: the switch still works for this visit */ } }
  // The page makes room for the panel (padding and the "Đã chọn" bar follow the class).
  useEffect(() => {
    document.body.classList.toggle('tg-has-split', open)
    return () => document.body.classList.remove('tg-has-split')
  }, [open])
  return { open, toggle: () => set(!open), close: () => set(false) }
}

// The two views of the list hang from the top edge of the screen like a phone's notch: the photos alone, or rows beside the schedule map
// ("Bản đồ lịch trình"). The schedule in detail is a step inside the map ("Xem chi tiết lịch trình"), so the notch has nothing else.
export function ViewSwitch({ open, onChange }: { open: boolean; onChange: (map: boolean) => void }) {
  return (
    <nav className="tg-notch" aria-label="Cách xem các nơi">
      <button type="button" className={`tg-notch__step ${!open ? 'is-on' : ''}`} aria-pressed={!open} onClick={() => onChange(false)}><Icon name="grid" size={17} /><span>Lưới ảnh</span></button>
      <button type="button" className={`tg-notch__step ${open ? 'is-on' : ''}`} aria-pressed={open} onPointerEnter={warmMap} onFocus={warmMap} onClick={() => onChange(true)}><Icon name="map" size={17} /><span>Bản đồ lịch trình</span></button>
    </nav>
  )
}

// `hot` / `onHot`: the place under the pointer, in the list or on the map; the map names its stop.
export function SplitPlan({ hot, onHot, onClose }: { hot: string | null; onHot: (id: string | null) => void; onClose: () => void }) {
  const { preview, view, toPlan, busy } = useDecision()
  const { best: now } = useBar()
  // While the schedule is built again after a pick, the last one stays on screen instead of the map going blank.
  const kept = useRef(now)
  if (now) kept.current = now
  const best = now ?? kept.current
  const [dayIdx, setDay] = useState(0)
  const days = useMemo(() => (best?.places ?? []).map((ids) => ids.filter((id) => info(id))), [best])
  const total = days.reduce((n, d) => n + d.length, 0)
  useEffect(() => { if (dayIdx >= days.length && days.length) setDay(days.length - 1) }, [dayIdx, days.length])
  const at = Math.min(dayIdx, Math.max(0, days.length - 1))
  const picked = view?.selected.length ?? 0
  const building = preview.status === 'building'
  return (
    <aside className={`tg-split ${building ? 'is-building' : ''}`} aria-label="Lịch trình theo ngày trên bản đồ" aria-busy={building || undefined}>
      {/* The map is there from the first moment, over all of Đà Lạt; the picks' route fills it in as soon as the schedule exists. */}
      <div className="tg-split__map">
        <TripMap groups={[total > 0 ? days[at] : []]} title={total > 0 ? `Đường đi ngày ${at + 1}` : 'Bản đồ Đà Lạt'} hot={hot} onHot={onHot} onOpen={openPlace} />
      </div>
      {total > 0 ? (
        <>
          <div className="tg-split__tabs" role="tablist" aria-label="Chọn ngày">
            {days.map((ids, i) => (
              <button key={i} type="button" role="tab" aria-selected={i === at} className={i === at ? 'is-on' : ''} onClick={() => setDay(i)}>
                Ngày {i + 1}{i === at && <span> · {ids.length} điểm dừng</span>}
              </button>
            ))}
          </div>
          {building && <p className="tg-split__live" role="status"><i />Đang xếp lại theo lựa chọn của bạn…</p>}
        </>
      ) : (building || picked > 0) && (
        <p className="tg-split__live tg-split__hint" role="status">
          {building ? <><i />Đang xếp lịch từ {picked} nơi đã chọn…</>
            : 'Chưa xếp thử được lịch từ các nơi này. Bạn có thể thêm hoặc bớt nơi, hoặc bấm Lập lịch để xem chi tiết.'}
        </p>
      )}
      {picked > 0 && <button type="button" className="tg-split__full" onClick={() => void toPlan()} disabled={busy} aria-busy={busy || undefined}><Icon name="expand" size={16} />Xem chi tiết lịch trình</button>}
      <button type="button" className="tg-split__close" onClick={onClose} aria-label="Đóng bản đồ"><Icon name="x" size={18} /></button>
    </aside>
  )
}
