import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { navigate, usePath } from '../../router'
import { openCreate } from '../home/dialogs'
import { placeMascot, type Rect, type Spot } from './place'
import { playCheer } from './sound'
import { chapters, flatten, type Kind, type Pose } from './steps'

// How the bunny looks in each pose: every picture is in public/img/bunny (idle, happy, wait, wow, sad, sleepy, love, point, curious are cut from the owner's
// sheet by web/scripts/cut_mascot_sheet.py; the rest come from web/scripts/gen_mascot_moods.py and gen_tour_mascot.py). All are drawn stacked and cross-fade, like AuthMascot.
const SRC: Record<Pose, string> = Object.fromEntries(
  (['idle', 'curious', 'wait', 'happy', 'shy', 'mail', 'sad', 'wow', 'wink', 'love', 'cheer', 'bow', 'point', 'point_up', 'walk_a', 'walk_b'] as const)
    .map((k) => [k, `/img/bunny/${k}.webp?v=2`])) as Record<Pose, string>
SRC.wave = SRC.idle // the idle bunny already waves hello
const WALK_MS = 520 // the walk to the next element
const THINK_MS = 420 // the "…" over its head before the words
const CELEBRATE_MS = 2200
const PAD = 8 // the lit hole is a little larger than the element
const CONFETTI = ['var(--tg-brand)', 'var(--tg-brand-soft)', 'var(--tg-ink)', 'var(--tg-sun)', '#fff']

const reduced = () => matchMedia('(prefers-reduced-motion: reduce)').matches
const rectOf = (el: Element): Rect => { const r = el.getBoundingClientRect(); return { x: r.x, y: r.y, w: r.width, h: r.height } }
const same = (a: Rect | null, b: Rect | null) => a === b || (!!a && !!b && a.x === b.x && a.y === b.y && a.w === b.w && a.h === b.h)
const pathOf = (p: string) => p.split('?')[0].replace(/\/$/, '') || '/'

export function Tour({ kind, i, onStep, onStop }: { kind: Kind; i: number; onStep: (i: number) => void; onStop: () => void }) {
  const flat = useMemo(() => flatten(chapters()), [])
  const { step, route } = flat[Math.min(i, flat.length - 1)]
  const path = usePath()
  const guest = kind === 'guest'

  const [rect, setRect] = useState<Rect | null>(null)
  const [resolved, setResolved] = useState(false) // the lit element of this stop has been looked for (found or not)
  const [phase, setPhase] = useState<'walk' | 'think' | 'say'>('think')
  const [frame, setFrame] = useState(0)
  const [walkLeft, setWalkLeft] = useState(false)
  const [celebrating, setCelebrating] = useState(false)
  const [burst, setBurst] = useState(0)
  const [size, setSize] = useState(140)
  const [view, setView] = useState({ w: innerWidth, h: innerHeight })
  const [barH, setBarH] = useState(110) // the control bar's height plus its margin: the mascot stays above it
  const petRef = useRef<HTMLDivElement>(null)
  const barRef = useRef<HTMLDivElement>(null)
  const goRef = useRef<HTMLButtonElement>(null)
  const blockRef = useRef<HTMLDivElement>(null)
  const held = useRef<Spot | null>(null) // where the bunny stands while the next stop is still being looked for
  const timers = useRef<number[]>([])
  const later = (fn: () => void, ms: number) => { timers.current.push(window.setTimeout(fn, ms)) }
  const clear = () => { timers.current.forEach(clearTimeout); timers.current = [] }

  // The page the stop lives on; moving there re-runs the look-up below because `path` changes.
  useEffect(() => {
    setResolved(false)
    clear()
    if (route && pathOf(path) !== route) { navigate(route); return }
    let tries = 0
    let t = 0
    const find = () => {
      if (!step.target) { setRect(null); setResolved(true); return }
      const el = document.querySelector(`[data-tour="${step.target}"]`)
      const r = el && rectOf(el)
      if (el && r && r.w > 0 && r.h > 0) {
        el.scrollIntoView({ block: 'nearest', inline: 'nearest' }) // only as far as needed to bring it into view
        setRect(rectOf(el))
        setResolved(true)
      } else if (++tries > 15) { setRect(null); setResolved(true) } // data not loaded or element hidden: say it without pointing
      else t = window.setTimeout(find, 100)
    }
    find()
    return () => clearTimeout(t)
  }, [i, path, route, step.target]) // eslint-disable-line react-hooks/exhaustive-deps

  // Keep the hole on the element while the page scrolls, resizes or re-renders.
  useEffect(() => {
    if (!resolved || !step.target) return
    const id = window.setInterval(() => {
      const el = document.querySelector(`[data-tour="${step.target}"]`)
      const r = el ? rectOf(el) : null
      setRect((prev) => (same(prev, r) ? prev : r))
    }, 150)
    const resize = () => setView({ w: innerWidth, h: innerHeight })
    addEventListener('resize', resize)
    return () => { clearInterval(id); removeEventListener('resize', resize) }
  }, [resolved, step.target])

  useEffect(() => {
    if (petRef.current) setSize(petRef.current.offsetWidth)
    if (barRef.current) setBarH(barRef.current.offsetHeight + 36)
  }, [])

  const spot = useMemo(() => placeMascot(rect, { w: view.w, h: view.h - barH }, size, size * 0.62, size * 1.25), [rect, view, size, barH])
  const shown = resolved ? spot : held.current ?? spot

  // The beat of a stop: walk (if it has to move), "…", then the words.
  useEffect(() => {
    if (!resolved) { setPhase('think'); return }
    const from = held.current
    const walk = from && !reduced() && Math.hypot(from.x - spot.x, from.y - spot.y) > 8 ? WALK_MS : 0
    if (from) setWalkLeft(spot.x < from.x)
    held.current = spot
    setPhase(walk ? 'walk' : 'think')
    later(() => setPhase('think'), walk)
    later(() => setPhase('say'), walk + (reduced() ? 250 : THINK_MS))
    return clear
  }, [resolved, i]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => clear, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (phase !== 'walk') return
    const id = window.setInterval(() => setFrame((f) => 1 - f), 180)
    return () => clearInterval(id)
  }, [phase])

  // Focus the main button of each stop so Enter / Space move on; give focus back at the end.
  useEffect(() => { goRef.current?.focus({ preventScroll: true }) }, [i, phase === 'say'])
  useEffect(() => {
    const was = document.activeElement as HTMLElement | null
    return () => was?.focus?.({ preventScroll: true })
  }, [])

  const go = (n: number) => { clear(); setCelebrating(false); onStep(Math.max(0, Math.min(flat.length - 1, n))) }
  const next = () => (i + 1 < flat.length ? go(i + 1) : onStop())
  const celebrate = () => {
    playCheer()
    setCelebrating(true)
    setBurst((b) => b + 1)
    later(() => { setCelebrating(false); next() }, reduced() ? 700 : CELEBRATE_MS)
  }
  const keys = useRef({ next, go, onStop, i, celebrating })
  keys.current = { next, go, onStop, i, celebrating }
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const k = keys.current
      if (e.key === 'Escape') { e.stopPropagation(); k.onStop() }
      else if (e.key === 'ArrowRight' && !k.celebrating) { e.preventDefault(); k.next() }
      else if (e.key === 'ArrowLeft' && !k.celebrating) { e.preventDefault(); k.go(k.i - 1) }
    }
    addEventListener('keydown', onKey, true)
    return () => removeEventListener('keydown', onKey, true)
  }, [])
  useEffect(() => { // the page behind stays where the stop put it
    const el = blockRef.current
    const stop = (e: Event) => e.preventDefault()
    el?.addEventListener('wheel', stop, { passive: false })
    return () => el?.removeEventListener('wheel', stop)
  }, [])

  const pointing = step.pose === 'point' || step.pose === 'point_up'
  const above = !!rect && rect.y + rect.h / 2 < shown.y + size * 0.35
  let pose: Pose = celebrating ? 'cheer' : step.pose
  if (!celebrating && pointing) pose = !rect ? 'curious' : above ? 'point_up' : 'point'
  if (phase === 'walk') pose = frame ? 'walk_b' : 'walk_a'
  const flip = phase === 'walk' ? walkLeft : pointing && !celebrating && !!rect && shown.side === 'left'
  const words = celebrating ? 'Hoan hô!' : guest && step.guestSay ? step.guestSay : step.say
  const edge = shown.x < size * 0.65 ? 'l' : shown.x + size > view.w - size * 0.65 ? 'r' : ''
  const hole = rect
    ? { transform: `translate(${rect.x - PAD}px, ${rect.y - PAD}px)`, width: rect.w + PAD * 2, height: rect.h + PAD * 2, borderRadius: 14 }
    : { transform: `translate(${view.w / 2}px, ${view.h / 2}px)`, width: 0, height: 0, borderRadius: 0 }
  const confetti = useMemo(() => Array.from({ length: burst ? 44 : 0 }, (_, n) => ({
    dx: (Math.random() - 0.5) * 520, dy: -(120 + Math.random() * 280), rot: Math.random() * 720 - 360, c: CONFETTI[n % CONFETTI.length], d: Math.random() * 0.25, w: 6 + Math.random() * 6,
  })), [burst])
  const cta = step.cta
  const label = cta === 'done' ? 'Xong' : cta === 'create' ? 'Tạo chuyến đi' : 'Tiếp'
  const primary = () => {
    if (cta === 'done') celebrate()
    else if (cta === 'create') { onStop(); openCreate() }
    else next()
  }
  const pics = useMemo(() => [...new Set<Pose>([...flat.map((f) => f.step.pose), 'walk_a', 'walk_b', 'cheer', 'point', 'point_up', 'curious'])], [flat])

  return createPortal(
    <div className="tg tg-tour" role="dialog" aria-modal="true" aria-label="Hướng dẫn cùng quả sồi" data-reduced={reduced() || undefined}>
      <div className="tg-tour__block" ref={blockRef} />
      <div className="tg-tour__hole" style={hole} data-empty={rect ? undefined : ''} aria-hidden="true" />
      {confetti.map((c, n) => (
        <i key={`${burst}-${n}`} className="tg-tour__bit" aria-hidden="true"
          style={{ left: shown.x + size / 2, top: shown.y + size / 3, width: c.w, height: c.w * 0.6, background: c.c, animationDelay: `${c.d}s`, '--dx': `${c.dx}px`, '--dy': `${c.dy}px`, '--rot': `${c.rot}deg` } as React.CSSProperties} />
      ))}
      <div className="tg-tour__pet" ref={petRef} data-edge={edge} data-phase={phase} data-celebrate={celebrating || undefined} style={{ transform: `translate(${shown.x}px, ${shown.y}px)` }}>
        {phase !== 'walk' && (
          <p className="tg-auth__say tg-tour__say" key={`${step.id}-${phase}-${celebrating}`} aria-live="polite">
            {phase === 'think' ? <span className="tg-auth__dots" aria-label="Đang nói"><i /><i /><i /></span> : words}
          </p>
        )}
        <span className="tg-tour__shadow" aria-hidden="true" />
        <div className="tg-tour__body" style={{ scale: flip ? '-1 1' : '1 1' }} aria-hidden="true">
          {pics.map((p) => <img key={p} className={p === pose ? 'is-on' : undefined} src={SRC[p]} alt="" decoding="async" />)}
        </div>
      </div>
      <div className="tg-tour__bar" ref={barRef}>
        <button type="button" className="tg-tour__skip" onClick={onStop}>Bỏ qua</button>
        <span className="tg-tour__gap" />
        {i > 0 && <button type="button" className="tg-btn tg-btn--ghost" disabled={celebrating} onClick={() => go(i - 1)}>Quay lại</button>}
        <button type="button" className="tg-btn tg-btn--primary" ref={goRef} disabled={celebrating} onClick={primary}>{label}</button>
      </div>
    </div>,
    document.body,
  )
}
