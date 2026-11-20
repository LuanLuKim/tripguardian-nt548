import type { PointerEvent } from 'react'
import { Icon, Logo } from '../ui/icons'

// How the bunny feels on the sign-in screen. The mood comes from what the visitor is doing (docs/Role_Web_Functional_Design.md §2.1):
// idle (nothing special), wait (request in flight), shy / peek (password field focused / shown), curious (something is
// missing or taken), sad (the server said no), happy (signed in), mail (a code was sent: holds an envelope). Each mood is its own picture of the same bunny
// (public/img/bunny: idle, happy, wait, sad, curious are cut from the owner's sheet by web/scripts/cut_mascot_sheet.py, the rest made by web/scripts/gen_mascot_moods.py) that cross-fades in; the motion on top (sway, wobble,
// hop) and the bubbles live in css/auth.css and stop under reduced motion.
export type Mood = 'idle' | 'wait' | 'shy' | 'peek' | 'curious' | 'sad' | 'happy' | 'mail'
export type Pet = { mood: Mood; say: string }
export const CALM: Pet = { mood: 'idle', say: '' }

// The mascot leans toward the pointer (CSS vars read by .tg-auth__pet).
function look(e: PointerEvent<HTMLElement>) {
  const r = e.currentTarget.getBoundingClientRect()
  const x = ((e.clientX - r.left) / r.width - 0.5) * 2
  const y = ((e.clientY - r.top) / r.height - 0.5) * 2
  e.currentTarget.style.setProperty('--lx', `${(x * 14).toFixed(1)}px`)
  e.currentTarget.style.setProperty('--ly', `${(y * 8).toFixed(1)}px`)
}
function unlook(e: PointerEvent<HTMLElement>) {
  e.currentTarget.style.setProperty('--lx', '0px')
  e.currentTarget.style.setProperty('--ly', '0px')
}

const MOODS: Mood[] = ['idle', 'wait', 'shy', 'peek', 'curious', 'sad', 'happy', 'mail']
const PICS = Object.fromEntries(MOODS.map((m) => [m, `/img/bunny/${m}.webp?v=2`])) as Record<Mood, string>

// The product's logo (the shared `Logo`, ink on transparent) with an optional tagline under it.
export function Brand({ tagline = false }: { tagline?: boolean }) {
  return (
    <div className="tg-brand">
      <Logo size={tagline ? 84 : 60} />
      {tagline && <i className="tg-brand__tag">Chuyến đi của bạn, theo cách bạn chọn.</i>}
    </div>
  )
}
export function AuthMascot({ pet }: { pet: Pet }) {
  const { mood, say } = pet
  return (
    <aside className="tg-auth__art" aria-hidden="true">
      <div className="tg-auth__scene" data-mood={mood} onPointerMove={look} onPointerLeave={unlook}>
        <Brand tagline />
        <span className="tg-auth__tile tg-auth__tile--map"><Icon name="map" size={26} /></span>
        <span className="tg-auth__tile tg-auth__tile--plan"><Icon name="calendar" size={26} /><Icon name="check" size={14} className="tg-auth__tick-on" /></span>
        <span className="tg-auth__shadow" />
        <div className="tg-auth__pet">
          {(say || mood === 'wait') && (
            <p className="tg-auth__say" key={mood + say}>
              {mood === 'wait' ? <span className="tg-auth__dots"><i /><i /><i /></span> : say}
            </p>
          )}
          <div className="tg-auth__body">
            {(Object.keys(PICS) as Mood[]).map((m) => <img key={m} className={m === mood ? 'is-on' : undefined} src={PICS[m]} alt="" decoding="async" />)}
            <svg viewBox="0 0 720 720" focusable="false">
              <g transform="translate(600 120)"><g className="tg-pet__ask"><circle r="38" /><text textAnchor="middle" y="19">?</text></g></g>
            </svg>
          </div>
        </div>
      </div>
    </aside>
  )
}
