import { useState } from 'react'
import { createRoot } from 'react-dom/client'
import { JourneyError, mutateJourney } from '../../journey'
import type { Readback } from '../../tu/types'
import { ReadbackSheet } from '../ReadbackSheet'
import '../../css/tokens.css'
import '../../css/base.css'
import '../../css/ask.css'
import '../../css/gate.css'

// The planning gate dialog over a stubbed journey API (scripts/test_planning_gate_ui.mjs routes the requests).
function Fixture() {
  const [gate, setGate] = useState<{ readback: Readback; missing: string[] } | null>(null)
  const [planned, setPlanned] = useState(false)
  const advance = async () => {
    try { await mutateJourney('gate-test', 'decision', 'advance'); setGate(null); setPlanned(true); return true }
    catch (e) { if (e instanceof JourneyError && e.readback) { setGate({ readback: e.readback, missing: e.missing ?? [] }); return false } throw e }
  }
  return <main className="tg">
    {planned ? <h1>Lịch trình sẵn sàng</h1> : <button onClick={advance}>Tiếp tục đến lịch trình</button>}
    {gate && <ReadbackSheet id="gate-test" initial={gate.readback} missing={gate.missing} onClose={() => setGate(null)} onAdvance={advance} onView={() => {}} />}
  </main>
}
createRoot(document.getElementById('root')!).render(<Fixture />)
