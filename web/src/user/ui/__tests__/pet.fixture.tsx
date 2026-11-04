import { createRoot } from 'react-dom/client'
import { PlaceCard } from '../PlaceCard'
import type { Card } from '../../pd/types'
import { loadSnapshot } from '../../../data/store'
import '../../css/tokens.css'
import '../../css/base.css'
import '../../css/explore.css'

const state = new URLSearchParams(location.search).get('case') || 'allowed'
const pet = state === 'allowed' ? { text: 'Cho mang thú cưng, theo 7 người', sid: 'pets' } : { text: 'Không cho mang thú cưng, theo 4 người', sid: 'pets' }
const card: Card = {
  id: 'fixture', name: 'Địa điểm mẫu', category: 'Quán cà phê', area: 'Đà Lạt', role: 'experience', group: 'food', status: 'main', score: 1, parts: {},
  why: [{ text: 'Không gian yên tĩnh', sid: 'noise' }, ...(state === 'allowed' ? [pet] : [])],
  tradeoffs: state === 'not_allowed' ? [pet] : state === 'other' ? [{ text: 'Cuối tuần đông', sid: 'crowd' }] : [],
  visit: null, location: { center: 'trung tâm', km: null, minutes: null }, price: null,
  confidence: { level: 'medium', reason: 'Dữ liệu mẫu' }, declined: false, depends_on_unknown: null,
  warnings: [], unverified: state === 'unknown' || state === 'mixed' ? ['Chưa rõ có cho mang thú cưng không'] : [],
  failed: state === 'not_allowed' ? ['Mang thú cưng: không cho phép'] : state === 'other' || state === 'mixed' ? ['Có chỗ đỗ xe: không'] : [],
  chosen: false, locked: false, anchor: false, alternatives: [], suggested: false, top: false,
}
await loadSnapshot()
createRoot(document.getElementById('root')!).render(<div className="tg" style={{ padding: 32, maxWidth: 440 }}><PlaceCard c={card} cmp={false} onCmp={() => {}} onDrop={() => {}} /></div>)
