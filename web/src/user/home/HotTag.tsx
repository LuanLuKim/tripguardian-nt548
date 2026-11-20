import { Icon } from '../ui/icons'
import type { Item } from './Pulse'

// "Đang hot": one badge for a place, a season and an event, by the one bar the server uses (src/corpus/pulse/render.py `hot_note`):
// clips by different authors lately for a place or a season, independent sites that report an event. The note is its tooltip, never the label.
export function HotTag({ it, className = '' }: { it: Pick<Item, 'hot' | 'hot_note'>; className?: string }) {
  if (!it.hot) return null
  return <span className={`tg-hot ${className}`} title={it.hot_note}><Icon name="flame" size={11} />Đang hot</span>
}
