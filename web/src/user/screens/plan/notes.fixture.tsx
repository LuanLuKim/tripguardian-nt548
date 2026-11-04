import { createRoot } from 'react-dom/client'
import { TimeCard, BackupCard } from './parts'
import { candidatesOf } from './candidates'
import { Swap } from './Swap'
import { TripProvider } from '../../trip'
import type { Backups, Ghost, ItineraryDay, TimeRecommendation, View } from '../../planning/types'
import '../../css/tokens.css'
import '../../css/base.css'
import '../../css/plan.css'
import '../../css/itinerary.css'
import '../../css/bar.css'

const state = new URLSearchParams(location.search).get('case') ?? 'notes'
const warnings = state === 'none' ? undefined : state === 'empty' ? [] : [
  { code: 'pets_unknown', text: 'chưa rõ có cho mang thú cưng không' },
  { code: 'other', text: 'Giờ mở cửa <chưa xác minh> & cần kiểm tra' },
]
const day: ItineraryDay = { day: 2, date: null, weekday: 'Tue', window: ['08:00', '18:00'], method: 'fixture', items: [] }
const suggestions: TimeRecommendation[] = [{ kind: 'gap', day: 2, optional: true, text: 'Khoảng trống buổi chiều', alternatives: [
  { id: 'suggested', name: 'Gợi ý mẫu', activity: null, trial_visit: ['14:00', '15:00'], requires_relayout: false, cost_unknown: false, warnings },
] }]
const backups: Backups = { places: [{ day: 2, place_id: 'original', name: 'Điểm trong lịch', reasons: ['rain'], text: 'Mưa', none_text: null, alternatives: [
  { id: 'backup', name: 'Dự phòng mẫu', minutes_rough: 8, for_this: true, reason: null, warnings },
] }], on_delay: [] }
const ghosts: Ghost[] = [{ day: 1, kind: 'lunch', start: 720, end: 780, items: [
  { place_id: 'ghost', name: 'Gợi ý bữa trưa mẫu', price_vnd: null, detour_min: 4, ...(warnings?.length ? { note: 'chưa rõ có cho mang thú cưng không' } : {}) },
] }, { day: 0, kind: 'free', start: 600, end: 660, items: [{ place_id: 'other-day', name: 'Nơi của ngày khác', price_vnd: null, detour_min: 3, note: 'Không được hiện ngày này' }] }]
const onAdd = (id: string, day: number) => { Object.assign(window, { __action: { id, day } }) }
const view = { state: { dropped: [] }, backups, recommendations: suggestions } as unknown as View
createRoot(document.getElementById('root')!).render(<TripProvider><div className="tg" style={{ padding: 32, maxWidth: state === 'swap' ? 1000 : 440 }}>
  {state === 'swap' ? <Swap day={day} replacing={null} candidates={candidatesOf(view, null, [], null)} people={2} busy={false} onOverview={() => {}} onDay={() => {}} onOpen={() => {}} onMore={() => {}} onPick={c => onAdd(c.id, 2)} /> : <>
    <TimeCard day={2} itinerary={day} timing={[]} suggestions={state === 'ghost-only' ? [] : suggestions} ghosts={ghosts} busy={state === 'busy'} onAdd={onAdd} />
    <BackupCard b={backups} day={2} busy={state === 'busy'} onSwap={(place, id) => { Object.assign(window, { __action: { place, id } }) }} />
  </>}
</div></TripProvider>)
