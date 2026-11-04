import type { PointerEvent } from 'react'

// How the acorn feels on the sign-in screen. The mood comes from what the visitor is doing (docs/Role_Web_Functional_Design.md §Đăng nhập):
// idle (nothing special), wait (request in flight), shy / peek (password field focused / shown), curious (something is
// missing or taken), sad (the server said no), happy (signed in), mail (a code was sent: holds an envelope). Each mood is its own picture of the same acorn
// (public/img/auth/mood, made by web/scripts/gen_mascot_moods.py) that cross-fades in; the motion on top (sway, wobble,
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

const PICS: Record<Mood, string> = {
  idle: '/img/auth/acorn_greet.webp',
  wait: '/img/auth/mood/wait.webp', shy: '/img/auth/mood/shy.webp', peek: '/img/auth/mood/peek.webp',
  curious: '/img/auth/mood/curious.webp', sad: '/img/auth/mood/sad.webp', happy: '/img/auth/mood/happy.webp', mail: '/img/auth/mood/mail.webp',
}
export function AuthMascot({ pet }: { pet: Pet }) {
  const { mood, say } = pet
  return (
    <aside className="tg-auth__art" aria-hidden="true">
      <div className="tg-auth__scene" data-mood={mood} onPointerMove={look} onPointerLeave={unlook}>
        <span className="tg-auth__cloud tg-auth__cloud--a" /><span className="tg-auth__cloud tg-auth__cloud--b" />
        <span className="tg-auth__hill" />
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
