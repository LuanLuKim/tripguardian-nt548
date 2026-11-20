import { createRoot } from 'react-dom/client'
import { BackupCard } from './parts'
import { GhostSlot } from './GhostSlot'
import { TripProvider } from '../../trip'
import type { Backups, Ghost } from '../../planning/types'
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
const backups: Backups = { places: [{ day: 2, place_id: 'original', name: 'Điểm trong lịch', reasons: ['rain'], text: 'Mưa', none_text: null, alternatives: [
  { id: 'backup', name: 'Dự phòng mẫu', minutes_rough: 8, for_this: true, reason: null, warnings },
] }], on_delay: [] }
const ghosts: Ghost[] = [{ day: 1, kind: 'lunch', start: 720, end: 780, items: [
  { place_id: 'ghost', name: 'Gợi ý bữa trưa mẫu', price_vnd: null, detour_min: 4, ...(warnings?.length ? { note: 'chưa rõ có cho mang thú cưng không' } : {}) },
] }, { day: 0, kind: 'free', start: 600, end: 660, items: [{ place_id: 'other-day', name: 'Nơi của ngày khác', price_vnd: null, detour_min: 3, note: 'Không được hiện ngày này' }] }]
createRoot(document.getElementById('root')!).render(<TripProvider><div className="tg" style={{ padding: 32, maxWidth: 440 }}>
  {ghosts.filter(g => g.day === 1).map(g => <GhostSlot key={g.kind} slot={g} day={2} busy={state === 'busy'} onAdd={() => {}} onOpen={() => {}} />)}
  <BackupCard b={backups} day={2} busy={state === 'busy'} onSwap={(place, id) => { Object.assign(window, { __action: { place, id } }) }} />
</div></TripProvider>)
