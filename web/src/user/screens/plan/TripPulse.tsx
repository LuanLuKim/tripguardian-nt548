import { Pulse, usePulse } from '../../home/Pulse'

// Nhịp Đà Lạt beside the plan (and on Hôm nay): the same bulletin as Discover. The API items carry no date of their own,
// so nothing is filtered by the trip's dates; the bulletin says when it was last refreshed. Hidden when it is not there.
export function TripPulse() {
  const b = usePulse()
  return b ? <div className="tg-tripside"><Pulse b={b} /></div> : null
}
