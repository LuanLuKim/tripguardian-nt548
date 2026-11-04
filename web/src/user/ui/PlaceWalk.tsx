import * as Dialog from '@radix-ui/react-dialog'
import { useCallback, useEffect, useState, type KeyboardEvent } from 'react'
import type { Cover } from '../../data/store'
import { reducedMotion } from '../lib'
import { Icon } from './icons'
import '../css/walk.css'

// "Đi một vòng" (spec E.2 tier 1): the place's scene photos in the order a visitor meets them, entrance, then the main
// part, then the details. Only photos the scene labels vouch for (no person, not blurry): a Cover that has no `scene`
// is never part of the walk. Clips are not in this tier (their frames carry no person label yet).

const ORDER = ['exterior', 'view', 'interior', 'room', 'amenity', 'food', 'drink', 'menu', 'bathroom', 'other']
const LABEL: Record<string, string> = {
  exterior: 'Bên ngoài', view: 'Cảnh xung quanh', interior: 'Bên trong', room: 'Phòng nghỉ', amenity: 'Tiện ích', food: 'Món ăn',
  drink: 'Đồ uống', menu: 'Thực đơn', bathroom: 'Phòng tắm', other: 'Một góc khác',
}
const PART: Record<string, string> = {
  exterior: 'Lối vào', view: 'Lối vào', interior: 'Khu chính', room: 'Khu chính', amenity: 'Chi tiết', food: 'Chi tiết', drink: 'Chi tiết',
  menu: 'Chi tiết', bathroom: 'Chi tiết', other: 'Chi tiết',
}
export const MIN_STEPS = 3
const AUTO_MS = 3800

// One photo per scene, entrance first. Fewer than MIN_STEPS scenes: no walk (the gallery is enough).
export function walkOf(covers: Cover[]): Cover[] {
  const by = new Map<string, Cover>()
  for (const c of covers) if (c.scene && ORDER.includes(c.scene) && !by.has(c.scene)) by.set(c.scene, c)
  const steps = ORDER.map((s) => by.get(s)).filter((c): c is Cover => !!c)
  return steps.length >= MIN_STEPS ? steps : []
}

export function PlaceWalk({ name, steps, onClose }: { name: string; steps: Cover[]; onClose: () => void }) {
  const [at, setAt] = useState(0)
  const [play, setPlay] = useState(!reducedMotion())
  const last = steps.length - 1
  const go = useCallback((n: number) => setAt(Math.max(0, Math.min(last, n))), [last])
  useEffect(() => {
    if (!play) return
    if (at >= last) { setPlay(false); return }
    const t = setTimeout(() => setAt((n) => Math.min(last, n + 1)), AUTO_MS)
    return () => clearTimeout(t)
  }, [play, at, last])
  const key = (e: KeyboardEvent) => {
    if (e.key === 'ArrowRight') { setPlay(false); go(at + 1) } else if (e.key === 'ArrowLeft') { setPlay(false); go(at - 1) } else if (e.key === ' ') { e.preventDefault(); setPlay((p) => !p) } else return
    e.stopPropagation()
  }
  const cur = steps[at]
  const scene = cur.scene ?? 'other'
  return (
    <Dialog.Root open onOpenChange={(o) => { if (!o) onClose() }}>
      <Dialog.Portal>
        <Dialog.Overlay className="tg tg-overlay" />
        <Dialog.Content className="tg tg-walk" aria-describedby={undefined} onKeyDown={key}>
          <header>
            <Dialog.Title>Đi một vòng quanh {name}</Dialog.Title>
            <Dialog.Close className="tg-icon-btn" aria-label="Đóng"><Icon name="x" size={18} /></Dialog.Close>
          </header>
          <div className="tg-walk__stage" aria-live="polite">
            {steps.map((s, i) => <img key={s.src} src={s.src} alt={i === at ? `${name}: ${LABEL[s.scene ?? 'other']}` : ''} aria-hidden={i !== at} className={i === at ? 'is-on' : ''} draggable={false} />)}
            <div className="tg-walk__cap"><small>{PART[scene]}{cur.year ? ` · ảnh ${cur.year}` : ''}</small><b>{LABEL[scene]}</b></div>
          </div>
          <footer>
            <button type="button" className="tg-icon-btn" aria-label="Ảnh trước" disabled={at === 0} onClick={() => { setPlay(false); go(at - 1) }}><Icon name="arrowLeft" size={18} /></button>
            <ol className="tg-walk__dots" aria-label="Các điểm dừng">
              {steps.map((s, i) => <li key={s.src}><button type="button" className={i === at ? 'is-on' : i < at ? 'is-past' : ''} aria-label={`${i + 1}. ${LABEL[s.scene ?? 'other']}`} aria-current={i === at} onClick={() => { setPlay(false); go(i) }} /></li>)}
            </ol>
            <button type="button" className="tg-icon-btn" aria-label="Ảnh sau" disabled={at === last} onClick={() => { setPlay(false); go(at + 1) }}><Icon name="arrow" size={18} /></button>
            <button type="button" className="tg-btn tg-btn--ghost tg-btn--sm" onClick={() => { if (at >= last) { setAt(0); setPlay(true) } else setPlay((p) => !p) }}>{play ? 'Tạm dừng' : at >= last ? 'Đi lại từ đầu' : 'Tự chạy'}</button>
          </footer>
          <p className="tg-walk__hint">← → để đổi chỗ · Dấu cách để dừng · Ảnh Google Maps, đã lọc ảnh có người</p>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
