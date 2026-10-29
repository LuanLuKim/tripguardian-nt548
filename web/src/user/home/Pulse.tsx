import { useEffect, useState, type CSSProperties } from 'react'
import { openPlace } from '../ui/PlaceSheet'
import { Icon } from '../ui/icons'
import '../css/pulse.css'

// Nhịp Đà Lạt (docs/CORPUS.md §Nhịp): the bulletin comes from GET /api/harness/pulse, words from the server's templates.
type Source = { type: string; label: string; url?: string; date?: string }
type Item = { id: string; kind: string; title: string; text: string; place_id: string | null; sources: Source[] }
export type Bulletin = { city: string; generated_at: string | null; day: string | null; stale: boolean; sections: { kind: string; title: string; items: Item[] }[] }

const TONES = ['#fbf6b8', '#d9f4ae', '#d2e5fb', '#fbdce5', '#e5def9']
const SHOWN = 3
const dm = (iso: string) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`

// null while loading and when the job never ran or the call fails: the page then keeps what it showed before the bulletin.
export function usePulse(): Bulletin | null {
  const [b, setB] = useState<Bulletin | null>(null)
  useEffect(() => {
    let live = true
    fetch('/api/harness/pulse').then((r) => (r.ok ? r.json() : null)).then((j: Bulletin | null) => { if (live && j && j.sections?.length) setB(j) }, () => {})
    return () => { live = false }
  }, [])
  return b
}

export function Pulse({ b }: { b: Bulletin }) {
  const [kind, setKind] = useState(b.sections[0].kind)
  const [more, setMore] = useState(false)
  const section = b.sections.find((s) => s.kind === kind) ?? b.sections[0]
  const items = more ? section.items : section.items.slice(0, SHOWN)
  return (
    <div className="tg-hm__trend tg-pulse">
      <div className="tg-hm__thead">
        <h2>Nhịp Đà Lạt</h2>
        <p>{b.stale && b.day ? `Chưa làm mới từ ${dm(b.day)}` : b.day ? `Cập nhật ${dm(b.day)}` : 'Điều đang diễn ra'}</p>
      </div>
      <div className="tg-pulse__tabs" role="tablist" aria-label="Nhóm tin">
        {b.sections.map((s) => (
          <button key={s.kind} type="button" role="tab" aria-selected={s.kind === section.kind} className="tg-pulse__tab"
            onClick={() => { setKind(s.kind); setMore(false) }}>{s.title}</button>
        ))}
      </div>
      <ol className="tg-hm__ideas" key={section.kind}>
        {items.map((it, i) => (
          <li key={it.id} className="tg-hm__idea tg-pulse__item" style={{ '--tone': TONES[i % TONES.length], '--i': i } as CSSProperties}>
            <div className="tg-hm__open">
              <span className="tg-hm__n" aria-hidden="true">{String(i + 1).padStart(2, '0')}</span>
              <span className="tg-hm__tx">
                {it.place_id
                  ? <button type="button" className="tg-pulse__name" onClick={(e) => openPlace(it.place_id!, e.currentTarget)}>{it.title}</button>
                  : <b className="tg-pulse__name">{it.title}</b>}
                <small className="tg-pulse__text">{it.text}</small>
                {it.sources.some((s) => s.url) && (
                  <small className="tg-pulse__src">
                    {it.sources.filter((s) => s.url).slice(0, 2).map((s, k) => (
                      <a key={k} href={s.url} target="_blank" rel="noopener noreferrer"><Icon name="chevronRight" size={11} />{s.label}{s.date ? ` ${dm(s.date)}` : ''}</a>
                    ))}
                  </small>
                )}
              </span>
            </div>
          </li>
        ))}
      </ol>
      {section.items.length > SHOWN && (
        <button type="button" className="tg-hb-link tg-pulse__more" onClick={() => setMore(!more)}>{more ? 'Thu gọn' : `Xem thêm ${section.items.length - SHOWN}`}</button>
      )}
    </div>
  )
}
