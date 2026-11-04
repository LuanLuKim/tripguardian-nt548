import { useState } from 'react'
import { createRoot } from 'react-dom/client'
import { TripProvider } from '../trip'
import { DecisionProvider, useDecision } from './decision'
import { DropSheet } from '../screens/Explore'
import { SelectedBar } from '../ui/SelectedBar'
import { Block } from '../screens/understand/Blocks'
import type { DishBlock } from '../tu/types'
import '../css/tokens.css'
import '../css/base.css'
import '../css/explore.css'
import '../css/sheet.css'
import '../css/bar.css'
import '../css/understand.css'

const state = new URLSearchParams(location.search).get('case') ?? 'drop'
const dish: DishBlock = { kind: 'dish', dish: 'lau ga la e', cards: [{ id: 'one', name: 'Quán mẫu kiểm thử', category: null, area: null, rating: null, reviews: null, photos: [], hours_today: null, price: null, liked: false }], places: [{ id: 'one', evidence: [{ source: 'menu_photo', dish: state === 'dish-unmatched' ? 'Lẩu gà nấm' : 'Lẩu Gà Lá É', price_vnd: 200000 }] }] }
function Selection() {
  const { view, act } = useDecision()
  const [drop, setDrop] = useState<{ id: string; name: string } | null>(null)
  return <>
    <h1>Lựa chọn của bạn</h1>
    <p data-testid="selection">{view?.selected.join(',')}</p>
    <button type="button" className="tg-btn" disabled={!view} onClick={() => { if (state === 'counts') void act({ type: 'drop', place_id: 'one' }); else setDrop({ id: 'one', name: 'Bánh Căn Nhỏ' }) }}>Bỏ Bánh Căn Nhỏ</button>
    <button type="button" className="tg-btn" onClick={() => void act({ type: 'undo' })}>Hoàn tác</button>
    <DropSheet card={drop} onClose={() => setDrop(null)} />
    <SelectedBar />
  </>
}
createRoot(document.getElementById('root')!).render(<TripProvider><div className="tg" style={{ padding: 32 }}>
  {state.startsWith('dish') ? <Block block={dish} busy={false} onLike={() => {}} /> : <DecisionProvider><Selection /></DecisionProvider>}
</div></TripProvider>)
