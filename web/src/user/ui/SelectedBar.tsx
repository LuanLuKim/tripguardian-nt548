import * as Dialog from '@radix-ui/react-dialog'
import { useEffect, useState } from 'react'
import { fmtMin, fmtVnd, info } from '../lib'
import { useDecision } from '../pd/decision'
import type { Diff, PreviewVariant } from '../pd/types'
import { PlacePhoto } from './common'
import { openPlace } from './PlaceSheet'
import { Icon } from './icons'

export type BarLevel = 'building' | 'ready'

// The cheapest schedule the background build found for the current selection.
const bestOf = (vs: PreviewVariant[]) => [...vs].sort((a, b) => a.metrics.travel_min - b.metrics.travel_min)[0] ?? null

// Planning handles feasibility; this bar only summarizes the user's selection.
export function useBar() {
  const { preview } = useDecision()
  const best = 'plan' in preview && preview.plan ? bestOf(preview.plan.variants) : null
  const level: BarLevel = preview.status === 'building' ? 'building' : 'ready'
  return { level, best }
}

export function SelectedBar(_props: { onRelax?: () => void }) {
  const { view, diff, act, busy, toPlan, error } = useDecision()
  const { level, best } = useBar()
  const [open, setOpen] = useState(false)
  const [shown, setShown] = useState<Diff | null>(null)
  const f = view?.feasibility
  useEffect(() => {
    if (!diff?.text) return
    setShown(diff)
    const t = setTimeout(() => setShown(null), 7000)
    return () => clearTimeout(t)
  }, [diff])
  if (!view || !f || !view.selected.length) return null
  const t = f.totals
  const names = new Map([...view.groups.flatMap((g) => g.cards), ...view.unverified.cards].map((c) => [c.id, c.name]))
  // A chosen place may sit outside the groups on screen (a stay, a place from chat): the corpus still knows its name.
  const nameOf = (id: string) => names.get(id) ?? info(id)?.name ?? ''
  // Lựa chọn never stops or nudges the user: too many or too few places is dealt with in Lịch trình.
  const canGo = view.selected.length > 0 && !busy
  const go2plan = async () => { setOpen(false); await toPlan() }
  return (
    <>
      <div className="tg-barwrap">
        {shown && (
          <p className="tg-diff" role="status"><Icon name="bolt" size={15} />{shown.text}.{shown.scope && <button type="button" className="tg-diff__undo" disabled={busy} onClick={() => act({ type: 'undo' })}>Hoàn tác</button>}</p>
        )}
        {error && <p className="tg-diff is-bad" role="alert"><Icon name="warn" size={15} />{error}</p>}
        <div className={`tg-bar is-${level}`} role="region" aria-label="Đã chọn">
          <button type="button" className="tg-bar__main" onClick={() => setOpen(true)} aria-haspopup="dialog">
            <span className="tg-bar__status"><i />Đã chọn {view.selected.length} nơi</span>
            {level === 'building' ? (
              <span className="tg-bar__skel" aria-busy="true"><span className="tg-skel" style={{ width: 120 }} /><span className="tg-skel" style={{ width: 90 }} /><span className="tg-skel" style={{ width: 110 }} /></span>
            ) : (
              <span className="tg-bar__stats">
                <span><b className="tg-mono">{t.places}</b> nơi</span>
                <span><b className="tg-mono">{fmtMin(t.visit)}</b> tham quan</span>
                <span>≈ <b className="tg-mono">{fmtMin(best ? best.metrics.travel_min : t.travel)}</b> đi lại</span>
                {best && <span>{best.metrics.cost_vnd ? <>~<b className="tg-mono">{fmtVnd(best.metrics.cost_vnd)}</b>{best.metrics.cost_unknown > 0 && <em> · một phần chưa có giá</em>}</> : <em>Chưa có giá</em>}</span>}
              </span>
            )}
            <Icon name="chevronUp" size={18} />
          </button>
          <button type="button" className="tg-btn tg-btn--primary" disabled={!canGo} onClick={go2plan}>
            {busy ? 'Đang xếp…' : 'Lập lịch'}<Icon name="arrow" size={18} />
          </button>
        </div>
      </div>
      <Dialog.Root open={open} onOpenChange={setOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="tg tg-overlay" />
          <Dialog.Content className="tg tg-listpanel" aria-describedby={undefined}>
            <header><Dialog.Title>Đã chọn {view.selected.length} nơi</Dialog.Title><Dialog.Close className="tg-icon-btn" aria-label="Thu gọn"><Icon name="chevronDown" size={20} /></Dialog.Close></header>
            <ul>
              {view.selected.map((id) => {
                const isLocked = view.locked.includes(id)
                const name = nameOf(id)
                if (!name) return null // never show a raw id
                return (
                  <li key={id}>
                    <PlacePhoto id={id} name={name} className="tg-listpanel__ph" />
                    <div><button type="button" className="tg-link tg-listpanel__name" onClick={() => { setOpen(false); openPlace(id) }}>{name}</button>
                      {view.chunks && view.chunks.length > 1 && <label className="tg-week-choice tg-faint">Tuần ghé <select aria-label={`Tuần ghé ${name}`} disabled={busy} value={view.chunk_assignments?.[id] ?? 0} onChange={(e) => act({ type: 'move_chunk', place_id: id, chunk: Number(e.target.value) })}>{view.chunks.map((chunk) => <option key={chunk.id} value={chunk.id}>Tuần {chunk.id + 1} · ngày {chunk.start_day}–{chunk.end_day} · {chunk.places.length} nơi</option>)}</select></label>}
                    </div>
                    <button type="button" className={`tg-icon-btn ${isLocked ? 'is-on' : ''}`} disabled={busy} onClick={() => act({ type: isLocked ? 'unlock' : 'lock', place_id: id })} aria-pressed={isLocked} aria-label={isLocked ? 'Bỏ khóa' : 'Khóa'}><Icon name={isLocked ? 'lock' : 'unlock'} size={18} /></button>
                    <button type="button" className="tg-icon-btn" disabled={busy} onClick={() => act({ type: 'drop', place_id: id })} aria-label={`Bỏ ${name}`}><Icon name="x" size={18} /></button>
                  </li>
                )
              })}
            </ul>
            <footer><span className="tg-faint">Giờ giấc và đường đi là ước tính.{f.known_days ? ` Chuyến đi có ${fmtMin(t.available)}.` : ' Chưa biết số ngày.'}</span><button type="button" className="tg-btn tg-btn--primary" disabled={!canGo} onClick={go2plan}>Chọn chỗ ở và lập lịch <Icon name="arrow" size={18} /></button></footer>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </>
  )
}
