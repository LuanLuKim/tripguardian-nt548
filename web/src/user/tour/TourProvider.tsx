import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useAccount } from '../account'
import { usePath } from '../../router'
import { Tour } from './Tour'
import type { Kind } from './steps'

export type TourApi = { start: () => void; stop: () => void; active: boolean }
const Ctx = createContext<TourApi>({ start: () => {}, stop: () => {}, active: false })
export const useTour = () => useContext(Ctx)

// Only signed-in people (members and guests) reach the screens the tour points at; a guest hears an invitation where a feature needs an account.
const kindOf = (account: ReturnType<typeof useAccount>): Kind => (account?.guest ? 'guest' : 'member')

// The tour never starts by itself: a button calls start(). It lives above the screens so it survives the page changes it causes.
export function TourProvider({ children }: { children: ReactNode }) {
  const kind = kindOf(useAccount())
  const [run, setRun] = useState<{ kind: Kind; i: number } | null>(null)
  const start = useCallback(() => setRun({ kind, i: 0 }), [kind])
  const stop = useCallback(() => setRun(null), [])
  useEffect(() => { if (run && run.kind !== kind) setRun(null) }, [kind, run])

  // Everyone sees it on their first visit: a new account, and every guest (a guest session is a new identity each time). "Seen" is
  // remembered per account in this browser from the moment it starts, so a reload mid-tour does not start it again.
  const account = useAccount()
  const home = usePath().split('?')[0].replace(/\/$/, '') === '/app'
  useEffect(() => {
    if (!account || account.needs_consent || run || !home) return
    const key = `tg-tour-seen:${account.id}`
    let seen = false
    try { seen = localStorage.getItem(key) === '1' } catch { /* storage blocked: show it, it is harmless */ }
    if (seen) return
    const t = window.setTimeout(() => {
      try { localStorage.setItem(key, '1') } catch { /* ignore */ }
      setRun({ kind, i: 0 })
    }, 1200)
    return () => clearTimeout(t)
  }, [account?.id, account?.needs_consent, home, run, kind]) // eslint-disable-line react-hooks/exhaustive-deps
  const api = useMemo(() => ({ start, stop, active: !!run }), [start, stop, run])
  return (
    <Ctx.Provider value={api}>
      {children}
      {run && <Tour kind={run.kind} i={run.i} onStep={(i) => setRun({ kind: run.kind, i })} onStop={stop} />}
    </Ctx.Provider>
  )
}
