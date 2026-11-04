import { createRoot } from 'react-dom/client'
import { useState } from 'react'
import { Board } from './Board'
import type { Understanding } from '../../tu/types'
import '../../css/tokens.css'
import '../../css/base.css'
import '../../css/shell.css'
import '../../css/explore.css'
import '../../css/bar.css'
import '../../css/assistant.css'
import '../../css/disc.css'
import '../../css/sheet.css'
import '../../css/understand.css'
import '../../css/chat.css'
import '../../css/ask.css'
import '../../css/screens.css'
import '../../css/auth.css'
import '../../css/plan.css'
import '../../css/itinerary.css'
import '../../css/landing.css'
import '../../css/app.css'
import '../../css/today.css'
import '../../css/memory.css'
import '../../css/home.css'
import '../../css/tags.css'
import '../../css/motion.css'
import '../../css/blog.css'
import '../../css/gate.css'
import '../../css/workspace.css'
import '../../css/tour.css'

function Fixture() {
  const [soft, setSoft] = useState([{ target: 'soft:scenic_view=present', key: 'scenic_view=present', feature: 'scenic_view', value: 'present', context: {}, weight: 'love' as const, mark: false, like: null }])
  const u = { required: [{ key: 'care', title: 'Lưu ý', label: 'Lưu ý', done: false }], trip: [], soft, total: 20, hard: [], anchors: [], signals: [], unmapped: [], purpose: null } as unknown as Understanding
  return <div className="tg tg-workspace" style={{ display: 'block' }}><div className="tg-cx__body" style={{ display: 'flex', width: 410, height: 940 }}><Board discovery={new URLSearchParams(location.search).get('discovery') !== 'off'} u={u} busy={false} preview={new Set()} onShow={() => {}} onOpen={() => {}} onEdit={() => setSoft([])} /></div></div>
}
createRoot(document.getElementById('root')!).render(<Fixture />)
