import { useState, type ReactNode } from 'react'
import { Icon } from '../ui/icons'

// The picture of an event or a season post as the leaf of a wall calendar: the leaves are stacked, the first on top, and turning one lifts its
// bottom edge up and over the binding to show the next picture beneath. Each leaf carries its own caption, so the page it shows is always
// the one that is read. A post with a single picture has no controls and no turn.
export type Leaf = { key: string; picture: ReactNode; caption: ReactNode }

export function FlipPoster({ leaves }: { leaves: Leaf[] }) {
  const [at, setAt] = useState(0)
  const n = leaves.length
  const turn = (d: number) => setAt((a) => (a + d + n) % n)
  return (
    <figure className={`tg-ev__poster ${n > 1 ? 'is-flip' : ''}`} onClick={n > 1 ? () => turn(1) : undefined}>
      {leaves.map((l, k) => (
        <div key={l.key} className={`tg-ev__leaf ${k < at ? 'is-turned' : ''}`} style={{ zIndex: n - k }}>
          {l.picture}
          <figcaption>{l.caption}</figcaption>
        </div>
      ))}
      {n > 1 && <div className="tg-ev__turn" onClick={(e) => e.stopPropagation()}>
        <button type="button" onClick={() => turn(-1)} aria-label="Ảnh trước"><Icon name="chevronLeft" size={16} /></button>
        <span aria-live="polite">{at + 1} / {n}</span>
        <button type="button" onClick={() => turn(1)} aria-label="Ảnh sau"><Icon name="chevronRight" size={16} /></button>
      </div>}
    </figure>
  )
}

// The wire loops along the top edge of the page.
export const Binding = () => <div className="tg-ev__rings" aria-hidden="true">{Array.from({ length: 9 }, (_, k) => <i key={k} />)}</div>
