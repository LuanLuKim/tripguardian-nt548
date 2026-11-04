import { createRoot } from 'react-dom/client'
import { TripProvider } from '../../trip'
import { Turn, botMsg } from './Turn'
import { Block } from './Blocks'
import type { DishBlock } from '../../tu/types'
import '../../css/tokens.css'
import '../../css/base.css'
import '../../css/understand.css'
import '../../css/ask.css'
import '../../css/sheet.css'

const mode = new URLSearchParams(location.search).get('case')
const dish: DishBlock = { kind: 'dish', dish: 'lau ga la e', cards: [{ id: 'one', name: 'Quán kiểm thử', category: null, area: null, rating: null, reviews: null, photos: [], hours_today: null, price: null, liked: false }], places: [{ id: 'one', evidence: [{ source: 'menu_photo', dish: 'Lẩu Gà Lá É', quote: 'LONG_MENU_EXCERPT bánh căn cà phê kem bơ và nhiều món khác', price_vnd: 200000 }] }] }
const m = botMsg('test', { live: mode === 'waiting', say: mode === 'waiting' ? '' : 'Bạn thích ngồi trong nhà hay ngoài trời?', steps: [{ id: 'split', label: 'Tách các ý…', status: 'ok' }, { id: 'rec:mobility', label: 'Ghi nhận phương tiện di chuyển', status: 'ok' }] })
createRoot(document.getElementById('root')!).render(<TripProvider><div className="tg" style={{ padding: 32 }}>
  {mode === 'dish' ? <Block block={dish} busy={false} onLike={() => {}} /> : <ul><Turn m={m} busy={mode === 'waiting'} onAnswer={() => {}} onDeck={() => {}} onText={() => {}} onPhoto={() => {}} onLike={() => {}} /></ul>}
</div></TripProvider>)
