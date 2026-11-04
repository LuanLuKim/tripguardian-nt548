import type { ReactNode } from 'react'
import { useTour } from './TourProvider'

// The ways in to the tour. Nothing starts it by itself.
// Found in Cài đặt (and in Hỗ trợ) for people who want to see it again; the first visit starts it by itself (TourProvider).
export function TourButton({ className = '', children }: { className?: string; children?: ReactNode }) {
  const { start } = useTour()
  return <button type="button" className={className} onClick={start}>{children}</button>
}
