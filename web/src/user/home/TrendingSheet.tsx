import * as Dialog from '@radix-ui/react-dialog'
import type { ReactNode } from 'react'
import { Icon } from '../ui/icons'
import type { Bulletin } from './Pulse'
import { TrendingChart } from './Trending'
import '../css/trending.css'

// The chart behind the "Xếp hạng" button, opened over the page the person is on instead of leaving it: the page behind blurs, the chart rises over it.
// The route /trending (home/Trending.tsx) shows the same chart for a direct link.
// A place opened from a row (the sheet of ui/PlaceSheet.tsx, in the URL as ?place=) lies over this sheet: Esc and clicks then belong to it, not to this one.
const placeOpen = () => new URLSearchParams(location.search).has('place')
const keep = (e: { preventDefault: () => void }) => { if (placeOpen()) e.preventDefault() }
export function TrendingSheet({ b, children }: { b: Bulletin; children: ReactNode }) {
  return (
    <Dialog.Root>
      <Dialog.Trigger asChild>{children}</Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="tg tg-trs__veil" />
        <Dialog.Content className="tg tg-home tg-trs" aria-describedby={undefined} onEscapeKeyDown={keep} onInteractOutside={keep}>
          <Dialog.Title className="tg-trs__title">Xu hướng Đà Lạt</Dialog.Title>
          <Dialog.Close className="tg-trs__x" aria-label="Đóng bảng xếp hạng"><Icon name="x" size={18} /></Dialog.Close>
          <div className="tg-tr tg-trc"><TrendingChart b={b} /></div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
