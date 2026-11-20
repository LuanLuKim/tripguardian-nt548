import { useEffect, useState } from 'react'
import { readJourney } from '../../journey'

// The heading of the overview: a title and a short summary of the plan, worded on the server (Planning `summary` read, the Agent role).
// Until the answer comes, or when it never does, a plain heading built from the plan stands in; it is asked again when the stops change.
export function usePlanSummary(planningId: string | null, key: string, plain: { title: string; text: string }) {
  const [got, setGot] = useState<{ key: string; title: string; text: string } | null>(null)
  useEffect(() => {
    if (!planningId || !key) return
    let live = true
    readJourney<{ title: string; text: string; source: string }>(planningId, 'planning/summary').then((r) => { if (live && r.source === 'agent') setGot({ key, title: r.title, text: r.text }) }, () => {})
    return () => { live = false }
  }, [planningId, key])
  const fresh = got?.key === key ? got : null
  return { title: fresh?.title ?? plain.title, text: fresh?.text ?? plain.text, wait: !fresh }
}
