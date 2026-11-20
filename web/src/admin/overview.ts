import { useEffect, useState } from 'react'
import type { ReviewItem, Snapshot } from '../data/types'
import { early } from './prefetch'

// What the overview screen draws (web/scripts/export_snapshot.py admin_overview): a few hundred KB, so the first screen
// does not wait for the 40 MB admin snapshot the other screens read.
export interface Overview {
  asOf: string
  build: Snapshot['build']
  system: Snapshot['system']
  counts: { places: number; experience: number; features: number; withVideos: number; byStatus: Record<string, number> }
  review: Pick<ReviewItem, 'id' | 'kind' | 'placeId' | 'feature'>[]
  placeNames: Record<string, string>
}

let cache: Promise<Overview> | null = null

function load(): Promise<Overview> {
  cache ??= early('overview', '/data/admin-overview.json')
    .then((r) => {
      if (r.status === 401) window.dispatchEvent(new Event('tg-admin-401'))
      if (!r.ok) throw new Error(`overview ${r.status}`)
      return r.json() as Promise<Overview>
    })
    .catch((e) => {
      cache = null // a failed read is tried again on the next visit
      throw e
    })
  return cache
}

export function useOverview() {
  const [state, setState] = useState<{ ov?: Overview; error?: string }>({})
  useEffect(() => {
    let live = true
    load().then((ov) => live && setState({ ov }), (e: Error) => live && setState({ error: e.message }))
    return () => {
      live = false
    }
  }, [])
  return state
}
