import { useEffect, useState, type ReactNode } from 'react'
import { enterStage, requestStageEntry, type Stage } from '../journey'
import { primeDecision } from '../pd/api'
import { useDecision } from '../pd/decision'
import { STEPS, useTrip, type StepId } from '../trip'
import { go } from './common'

const STAGE_OF: Record<StepId, Stage> = { understand: 'trip', explore: 'decision', plan: 'planning' }
const stepIndex = (path: string) => (path.startsWith('/explore') ? 1 : path.startsWith('/plan') ? 2 : path.startsWith('/done') ? STEPS.length : -1) // /done (feedback) comes after the last step

// The way between Lựa chọn and Lịch trình (the sidebar's two buttons). A finished step is a way back: the journey on the server steps back
// with it (never forward). A later step is a way ahead: from Lựa chọn the chosen places go to Planning first; otherwise its page opens and says what it still needs.
export function useFlowNav(path: string) {
  const { trip } = useTrip()
  const { view, toPlan } = useDecision()
  const [going, setGoing] = useState<StepId | null>(null) // the step clicked while the server steps the journey back: it shows at once
  const at = stepIndex(path)
  const goTo = async (target: StepId) => {
    if (going) return
    const to = STEPS.find((s) => s.id === target)!
    const ahead = STEPS.findIndex((s) => s.id === target) > at
    if (ahead || at < 0) {
      if (target === 'plan' && at === 1 && view?.selected.length) void toPlan()
      else go(to.path)
      return
    }
    setGoing(target)
    try {
      const id = trip.journeyId
      if (id) {
        const origin = location.pathname + location.search
        const stage = STAGE_OF[target]
        try {
          const current = await enterStage(id, stage)
          if (origin !== location.pathname + location.search) return
          if (stage === 'decision') primeDecision(id, current)
          if (stage === 'trip') requestStageEntry(id, 'trip')
        } catch {
          /* the target screen shows the connection error itself */
        }
        if (origin !== location.pathname + location.search) return
      }
      go(to.path)
    } finally { setGoing(null) }
  }
  return { goTo, going, at }
}

export function Page({ children, className = '', narrow = false }: { children: ReactNode; className?: string; narrow?: boolean }) {
  return <div className={`tg-page ${narrow ? 'is-narrow' : ''} ${className}`}>{children}</div>
}

export function useTitle(t: string) {
  useEffect(() => { document.title = `${t} · TripGuardian` }, [t])
}
