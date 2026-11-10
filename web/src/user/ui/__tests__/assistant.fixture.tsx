import { useState } from 'react'
import { createRoot } from 'react-dom/client'
import { Body, type AssistantStage } from '../Assistant'
import { TripProvider } from '../../trip'
import { pushMsg, useUi } from '../../store'
import '../../css/tokens.css'
import '../../css/base.css'
import '../../css/assistant.css'

localStorage.setItem('tg.trip.v1', JSON.stringify({ journeyId: '0123456789ab', decisionId: '0123456789ab', planningId: '0123456789ab' }))
pushMsg({ role: 'user', text: 'Decision question' })
pushMsg({ role: 'bot', text: 'Decision reply', stage: 'decision' })
pushMsg({ role: 'user', text: 'Planning question', stage: 'planning' })
pushMsg({ role: 'bot', text: 'Planning reply', stage: 'planning' })

function Fixture() {
  const [stage, setStage] = useState<AssistantStage>('decision')
  const [busy, setBusy] = useState(false)
  const messages = useUi(u => u.assistant.msgs)
  return <div className="tg">
    <button onClick={() => setStage(stage === 'decision' ? 'planning' : 'decision')}>Switch stage</button>
    <button onClick={() => setBusy(!busy)}>Toggle streaming</button>
    <output>{messages.length} messages</output>
    <div className="tg-asst"><Body stage={stage} busy={busy} pinned={false} send={() => {}} chips={[]} intro="Fixture" placeholder="Message" onLike={() => {}} canPin={false} /></div>
  </div>
}
createRoot(document.getElementById('root')!).render(<TripProvider><Fixture /></TripProvider>)
