import { useEffect, useState } from 'react'
import { readRoutes } from '../../planning/api'
import type { DayRoute } from '../../planning/types'

type MapPoint = { lat: number; lng: number }
export type MapDayRoute = DayRoute & { start: DayRoute['start'] & { mapPoint?: MapPoint }; end: DayRoute['end'] & { mapPoint?: MapPoint } }

// The drawn path of each day, read apart from the plan so an edit never waits for the routing source.
// `key` changes whenever the itinerary does (order, days, lodging); until the new paths arrive the map keeps the
// old line only if it still belongs to the same itinerary, otherwise it falls back to the dashed sketch.
export function useRoutes(planningId: string | null, key: string, on: boolean) {
  const [got, setGot] = useState<{ planningId: string; key: string; days: MapDayRoute[] } | null>(null)
  useEffect(() => {
    if (!planningId || !on) return
    let live = true
    readRoutes(planningId).then((r) => {
      if (!live) return
      // An arbitrary lodging/entry may not be in the place catalog. Reuse only a route endpoint evidenced for
      // the same node in this response, so a day with missing road geometry can still sketch its home legs.
      const anchors = new Map<string, MapPoint>()
      for (const day of r.days) for (const side of ['start', 'end'] as const) {
        const coords = day.route?.coords
        const point = side === 'start' ? coords?.[0] : coords?.[coords.length - 1]
        if (day[side].id && point) anchors.set(day[side].id, { lat: point[0], lng: point[1] })
      }
      const days = r.days.map((day) => {
        const endpoint = (side: 'start' | 'end') => {
          const coords = day.route?.coords
          const own = side === 'start' ? coords?.[0] : coords?.[coords.length - 1]
          return { ...day[side], mapPoint: own ? { lat: own[0], lng: own[1] } : day[side].id ? anchors.get(day[side].id) : undefined }
        }
        return { ...day, start: endpoint('start'), end: endpoint('end') }
      })
      setGot({ planningId, key, days })
    }).catch(() => { if (live) setGot({ planningId, key, days: [] }) })
    return () => { live = false }
  }, [planningId, key, on])
  return got && got.planningId === planningId && got.key === key ? got.days : null
}
