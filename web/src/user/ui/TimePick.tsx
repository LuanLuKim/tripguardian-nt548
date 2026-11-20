import * as Popover from '@radix-ui/react-popover'
import { useRef, useState } from 'react'

const pad = (n: number) => String(n).padStart(2, '0')
const HOURS = Array.from({ length: 24 }, (_, h) => h)
const MINUTES = [0, 15, 30, 45]

// A 24-hour time as one pill: the pill shows "14:00"; opening it gives the hours as a grid (day hours first in the eye, the
// small hours dimmed) and the minutes as four quarter chips, so a time is two taps and nothing is read from a long list.
// The value is "HH:MM". A minute that is not on the quarter (a time from the server) stays pickable as a fifth chip.
// hover: a mouse resting on the pill opens the picker by itself and leaving closes it; a click keeps it open (touch screens just tap).
export function TimePick({ value, onChange, label, disabled, hover = false }: { value: string; onChange: (v: string) => void; label: string; disabled?: boolean; hover?: boolean }) {
  const [open, setOpen] = useState(false)
  const timer = useRef<number | undefined>(undefined)
  const byHover = useRef(false) // opened by the pointer resting on it, not by a click: leaving closes it again
  const enter = (e: React.PointerEvent) => {
    if (!hover || disabled || e.pointerType !== 'mouse') return
    window.clearTimeout(timer.current)
    if (!open) timer.current = window.setTimeout(() => { byHover.current = true; setOpen(true) }, 120)
  }
  const leave = (e: React.PointerEvent) => {
    if (!hover || e.pointerType !== 'mouse') return
    window.clearTimeout(timer.current)
    if (open && byHover.current) timer.current = window.setTimeout(() => setOpen(false), 220)
  }
  const [h = '', m = ''] = value.split(':')
  const hour = h === '' ? null : Number(h)
  const minute = m === '' ? 0 : Number(m)
  const minutes = MINUTES.includes(minute) ? MINUTES : [...MINUTES, minute].sort((a, b) => a - b)
  return (
    <Popover.Root open={open} onOpenChange={(o) => { if (!o) byHover.current = false; setOpen(o) }}>
      <Popover.Trigger asChild>
        <button type="button" className="tg-tp" disabled={disabled} aria-label={`${label}: ${value || 'chưa chọn'}`} onPointerEnter={enter} onPointerLeave={leave}
          onClick={(e) => { if (byHover.current) { e.preventDefault(); byHover.current = false } }}>{value || '--:--'}</button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content className="tg tg-tp__pop" sideOffset={8} align="start" collisionPadding={12} onPointerEnter={enter} onPointerLeave={leave}
          onOpenAutoFocus={(e) => { if (byHover.current) e.preventDefault() }}>
          <p className="tg-tp__cap">Giờ</p>
          <div className="tg-tp__hours" role="listbox" aria-label={`${label}, giờ`}>
            {HOURS.map((x) => (
              <button key={x} type="button" role="option" aria-selected={hour === x} className={`${hour === x ? 'is-on' : ''} ${x < 5 ? 'is-late' : ''}`}
                onClick={() => onChange(`${pad(x)}:${pad(hour === null ? 0 : minute)}`)}>{pad(x)}</button>
            ))}
          </div>
          <p className="tg-tp__cap">Phút</p>
          <div className="tg-tp__mins" role="listbox" aria-label={`${label}, phút`}>
            {minutes.map((x) => (
              <button key={x} type="button" role="option" aria-selected={hour !== null && minute === x} className={hour !== null && minute === x ? 'is-on' : ''} disabled={hour === null}
                onClick={() => onChange(`${pad(hour ?? 0)}:${pad(x)}`)}>:{pad(x)}</button>
            ))}
          </div>
          <button type="button" className="tg-tp__done" onClick={() => setOpen(false)}>Xong</button>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  )
}
