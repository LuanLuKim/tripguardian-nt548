import type { PointerEvent } from 'react'
import { Icon } from '../ui/icons'

// How the bunny feels on the sign-in screen. The mood comes from what the visitor is doing (docs/Role_Web_Functional_Design.md §Đăng nhập):
// idle (nothing special), wait (request in flight), shy / peek (password field focused / shown), curious (something is
// missing or taken), sad (the server said no), happy (signed in), mail (a code was sent: holds an envelope). Each mood is its own picture of the same bunny
// (public/img/bunny: idle, happy, wait, sad are the owner's drawings, the rest made by web/scripts/gen_mascot_moods.py) that cross-fades in; the motion on top (sway, wobble,
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
const PICS = Object.fromEntries(MOODS.map((m) => [m, `/img/bunny/${m}.webp`])) as Record<Mood, string>

// The product's wordmark: a mountain line with a map pin over "TripGuardian". Drawn here (not a picture) so it stays sharp at any size.
export function Brand({ tagline = false }: { tagline?: boolean }) {
  return (
    <div className="tg-brand">
      <svg viewBox="0 0 220 56" width="150" aria-hidden="true" focusable="false">
        <path d="M6 50 C 42 44, 62 20, 84 12 C 100 22, 118 40, 150 44 C 176 47, 198 46, 214 40" />
        <g transform="translate(150 2)"><path d="M12 30 C 12 30 2 20 2 12.5 a10 10 0 0 1 20 0 C 22 20 12 30 12 30Z" className="tg-brand__pin" /><circle cx="12" cy="12.5" r="3.6" className="tg-brand__dot" /></g>
      </svg>
      <b className="tg-brand__name">TripGuardian</b>
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
