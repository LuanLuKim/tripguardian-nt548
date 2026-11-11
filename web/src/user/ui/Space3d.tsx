import * as Dialog from '@radix-ui/react-dialog'
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { reducedMotion } from '../lib'
import { Icon } from './icons'

// "Khám phá 3D" tab of the place sheet (docs/Role_Web_Functional_Design.md §6). The tab itself is only a poster and one
// button: pressing it "dives" into a full-page viewer (the sheet fades under a cream veil, the poster grows to the whole
// window while drifting closer, then the live model crossfades in) and Back plays the same dive in reverse into the poster.
// The model runs in a same-origin iframe built by web/scripts/build_space3d.mjs: its scene owns the whole window, and
// removing the frame frees the GPU. The tab exists only for a place in /space3d/index.json.

let models: Promise<Record<string, string>> | undefined
const loadModels = () => (models ??= fetch('/space3d/index.json').then((r) => r.json() as Promise<Record<string, string>>).catch(() => ({} as Record<string, string>)))

// The model of this place, or null while unknown and for a place without one. A place with one gets its viewer script,
// data and poster fetched at once (into the HTTP cache: the script is immutable, the rest revalidates in the background),
// so a dive never waits on the network.
export function useSpace3d(id: string): string | null {
  const [slug, setSlug] = useState<string | null>(null)
  useEffect(() => {
    let on = true
    setSlug(null)
    void loadModels().then((all) => { if (on) setSlug(all[id] ?? null) })
    return () => { on = false }
  }, [id])
  useEffect(() => { if (slug) prefetch(slug) }, [slug])
  return slug
}

let viewerScript: Promise<void> | undefined
function prefetch(slug: string) {
  viewerScript ??= fetch('/space3d/viewer.html')
    .then((r) => r.text())
    .then((html) => { const src = html.match(/src="(viewer-[\w-]+\.js)"/)?.[1]; if (src) void fetch(`/space3d/${src}`) })
    .catch(() => undefined)
  void fetch(`/space3d/places/${slug}.json`).catch(() => undefined)
  new Image().src = `/space3d/posters/${slug}.webp`
}

// --- The warm model ------------------------------------------------------------------------------------------------
// Building a scene takes seconds of script, so the frame is started before the dive: on the first sign the user is going
// in (the 3D tab or the poster hovered a moment, focused or pressed), or once a sheet with a model has sat still for a
// while on a machine with cores to spare. A same-origin frame shares the page's main thread, which is why opening a sheet
// alone never starts one: the sheet would freeze while the person scrolls it. After Back the frame is kept, paused on the
// overview, for KEEP_MS, so going in again is instant. One frame at most; another place's replaces it.
// The frame lives in its own fixed layer on <body> from the start (moving an iframe in the DOM reloads it): the dive is a
// non-modal Radix dialog portalled into that same layer around it (CSS stacks frame above poster, buttons above frame).
// Non-modal because the frame sits outside the dialog's content: a modal one would pull focus back out of the model. Radix
// still stacks it over the sheet's dialog (the sheet's focus trap pauses, Esc and outside clicks go to the dive).
type FrameState = 'wait' | 'ready' | 'error'
type Warm = { slug: string; layer: HTMLDivElement; frame: HTMLIFrameElement; state: FrameState; drop?: number; changed: Set<() => void> }
let warm: Warm | null = null
let listening = false
let onBack: (() => void) | null = null // the dive on screen, for the frame's own Esc
const KEEP_MS = 90000
const HOVER_MS = 150
const IDLE_MS = 2000

function onFrameMessage(e: MessageEvent) {
  const w = warm
  if (!w || e.origin !== location.origin || e.source !== w.frame.contentWindow) return
  const type = (e.data as { type?: string } | null)?.type
  if (type === 'space3d:back') { onBack?.(); return }
  const next: FrameState | null = type === 'space3d:ready' ? 'ready' : type === 'space3d:error' ? 'error' : null
  if (!next || w.state !== 'wait') return
  w.state = next
  w.changed.forEach((f) => f())
}

function dropWarm() {
  if (!warm) return
  clearTimeout(warm.drop)
  warm.layer.remove() // the frame goes with it, and its WebGL context and GPU memory
  warm = null
}

export function warmSpace3d(slug: string): Warm {
  if (warm?.slug === slug && warm.state !== 'error') {
    clearTimeout(warm.drop)
    warm.drop = undefined
    return warm
  }
  dropWarm()
  if (!listening) { addEventListener('message', onFrameMessage); listening = true }
  const layer = document.createElement('div')
  layer.className = 'tg tg-s3v'
  layer.dataset.phase = 'warm'
  layer.setAttribute('aria-hidden', 'true')
  layer.tabIndex = -1
  const frame = document.createElement('iframe')
  frame.className = 'tg-s3v__frame'
  frame.title = 'Mô hình 3D'
  frame.allow = 'fullscreen'
  frame.src = `/space3d/viewer.html?place=${encodeURIComponent(slug)}&host=full&warm=1`
  layer.appendChild(frame)
  document.body.appendChild(layer)
  warm = { slug, layer, frame, state: 'wait', changed: new Set() }
  return warm
}
const tellFrame = (w: Warm, type: string) => w.frame.contentWindow?.postMessage({ type }, location.origin)

// After a dive: back to a hidden, paused frame on the overview, dropped if nobody goes in again soon.
function park(w: Warm) {
  if (warm !== w) return
  if (w.state === 'error') return dropWarm()
  tellFrame(w, 'space3d:hide')
  w.layer.dataset.phase = 'warm'
  delete w.layer.dataset.state
  w.layer.setAttribute('aria-hidden', 'true')
  clearTimeout(w.drop)
  w.drop = window.setTimeout(() => { if (warm === w) dropWarm() }, KEEP_MS)
}

// Warm on intent: hovering the 3D tab or poster a moment, focusing or pressing it. Spread on the element.
export function warmOnIntent(slug: string | null) {
  let timer: number | undefined
  const now = () => { clearTimeout(timer); if (slug) warmSpace3d(slug) }
  return {
    onPointerEnter: () => { clearTimeout(timer); timer = window.setTimeout(now, HOVER_MS) },
    onPointerLeave: () => clearTimeout(timer),
    onPointerDown: now,
    onFocus: now,
  }
}

// Warm while the person reads: a sheet with a model, still (no pointer, key, wheel or scroll) for IDLE_MS, on a machine
// with at least four cores, not on a metered connection. Leaving the sheet before then cancels it.
export function useWarmWhenIdle(slug: string | null) {
  useEffect(() => {
    const nav = navigator as Navigator & { connection?: { saveData?: boolean } }
    if (!slug || (nav.hardwareConcurrency ?? 0) < 4 || nav.connection?.saveData || reducedMotion()) return
    let timer = 0
    let idle = 0
    const arm = () => {
      clearTimeout(timer)
      timer = window.setTimeout(() => {
        const start = () => { if (!document.hidden) warmSpace3d(slug) }
        idle = typeof window.requestIdleCallback === 'function' ? requestIdleCallback(start, { timeout: 1500 }) : window.setTimeout(start, 0) as number
      }, IDLE_MS)
    }
    const events = ['pointermove', 'pointerdown', 'keydown', 'wheel', 'scroll'] as const
    events.forEach((e) => addEventListener(e, arm, { capture: true, passive: true }))
    arm()
    return () => {
      clearTimeout(timer)
      if (idle && typeof cancelIdleCallback === 'function') cancelIdleCallback(idle)
      events.forEach((e) => removeEventListener(e, arm, { capture: true }))
    }
  }, [slug])
}

// The tab button that was pressed (its rect), left for the Space3d that mounts next: choosing the tab dives at once, the
// poster card below is only what Back lands on (and a way to go in again).
let pending: DOMRect | null = null
export const diveFrom = (rect: DOMRect) => { pending = rect }

export function Space3d({ slug, name }: { slug: string; name: string }) {
  const stage = useRef<HTMLButtonElement>(null)
  const [origin, setOrigin] = useState<DOMRect | null>(() => { const r = pending; pending = null; return r })
  const [diving, setDiving] = useState(origin !== null)
  const intent = useMemo(() => warmOnIntent(slug), [slug])
  // Where Back lands: the poster card when it is on screen, else the tab button.
  const target = () => {
    const s = stage.current?.getBoundingClientRect()
    if (s && s.bottom > 0 && s.top < innerHeight) return s
    return document.querySelector('.tg-ps__tabs [aria-selected="true"]')?.getBoundingClientRect() ?? s ?? null
  }
  return (
    <div className="tg-s3">
      <h3>Khám phá 3D</h3>
      <p className="tg-pano__note">
        <Icon name="info" size={16} />
        <span>Mô hình minh họa dựng từ ảnh thực tế của nơi này. Tỷ lệ và chi tiết chỉ để tham khảo, có thể khác ngoài đời.</span>
      </p>
      <button type="button" className="tg-s3__stage" ref={stage} {...intent} onClick={() => { setOrigin(stage.current?.getBoundingClientRect() ?? null); setDiving(true) }} aria-label={`Bước vào mô hình 3D của ${name}`}>
        <img className="tg-s3__poster" src={`/space3d/posters/${slug}.webp`} alt="" />
        <span className="tg-s3__cta"><Icon name="cube" size={18} /> Bước vào mô hình 3D</span>
      </button>
      {diving && <Dive slug={slug} name={name} from={origin} rect={target} onDone={() => setDiving(false)} />}
    </div>
  )
}

// in     the poster (the model's own overview) grows from the tab's card to the window and drifts slightly closer
//        while the sheet behind fades under a cream veil; the frame is started now unless it was warmed already
// wait   the poster holds (still drifting) with a small "opening" note until the model has drawn its first frame
// reveal the live model crossfades in over the poster, settling from a slight zoom
// open   the model; only the Back button and the place name float on it
// out    Back: the model fades back into the poster and the window shrinks into the card again
type Phase = 'in' | 'wait' | 'reveal' | 'open' | 'out'
const GROW_MS = 760
const REVEAL_MS = 650
const OUT_MS = 680
const GIVE_UP_MS = 30000

function Dive({ slug, name, from, rect, onDone }: { slug: string; name: string; from: DOMRect | null; rect: () => DOMRect | null; onDone: () => void }) {
  const calm = reducedMotion()
  const w = useMemo(() => warmSpace3d(slug), [slug])
  const [phase, setPhase] = useState<Phase>('in')
  const [state, setState] = useState<FrameState>(w.state)
  const [box, setBox] = useState(() => from ?? rect())
  const leaving = useRef(false)
  const backButton = useRef<HTMLButtonElement>(null)

  const out = () => {
    if (leaving.current) return
    leaving.current = true
    setBox(rect())
    setPhase('out')
  }
  // Back = history back (the dive owns one history entry, so the browser's Back and the phone's gesture do the same).
  const back = () => {
    if (history.state?.tg3d) history.back()
    else out()
  }

  useEffect(() => {
    if (!history.state?.tg3d) history.pushState({ ...history.state, tg3d: 1 }, '', location.href)
    const onPop = () => { if (!history.state?.tg3d) out() }
    addEventListener('popstate', onPop)
    onBack = back
    return () => { removeEventListener('popstate', onPop); if (onBack === back) onBack = null }
  }, [])

  // The layer: on screen while the dive is on, the frame drawing again; parked (hidden, paused) when it ends.
  useEffect(() => {
    const sync = () => setState(w.state)
    w.changed.add(sync)
    sync()
    w.layer.removeAttribute('aria-hidden')
    tellFrame(w, 'space3d:show')
    return () => { w.changed.delete(sync); park(w) }
  }, [w])

  // The entrance: in → wait once the poster fills the window, then reveal as soon as the model has drawn.
  useEffect(() => {
    const a = setTimeout(() => setPhase((p) => (p === 'in' ? 'wait' : p)), calm ? 0 : GROW_MS)
    const c = setTimeout(() => setState((s) => (s === 'wait' ? 'error' : s)), GIVE_UP_MS)
    return () => { clearTimeout(a); clearTimeout(c) }
  }, [])
  useEffect(() => {
    if (phase === 'wait' && state === 'ready') setPhase('reveal')
    if (phase === 'wait' && state === 'error') setPhase('open')
    if (phase === 'open' && state === 'ready') w.frame.contentWindow?.focus() // keys reach the model
  }, [phase, state])
  useEffect(() => {
    if (phase === 'reveal') { const t = setTimeout(() => setPhase('open'), calm ? 0 : REVEAL_MS); return () => clearTimeout(t) }
    if (phase === 'out') { const t = setTimeout(onDone, calm ? 0 : OUT_MS); return () => clearTimeout(t) }
  }, [phase])

  const shown = state === 'error' ? 'error' : state === 'ready' ? 'ready' : 'wait'
  useLayoutEffect(() => {
    const l = w.layer
    l.dataset.phase = phase
    l.dataset.state = shown
    for (const [k, v] of Object.entries({ '--l': box?.left, '--t': box?.top, '--w': box?.width, '--h': box?.height }))
      if (v === undefined) l.style.removeProperty(k)
      else l.style.setProperty(k, `${v}px`)
  }, [phase, shown, box])

  return (
    <Dialog.Root open modal={false} onOpenChange={(o) => !o && back()}>
      <Dialog.Portal container={w.layer}>
        <Dialog.Content
          className="tg-s3v__ui"
          aria-describedby={undefined}
          onOpenAutoFocus={(e) => { e.preventDefault(); backButton.current?.focus({ preventScroll: true }) }}
          onCloseAutoFocus={(e) => e.preventDefault()}
          onInteractOutside={(e) => e.preventDefault()} // the model's frame is outside the content, and stays in the dive
        >
      <Dialog.Title className="tg-sr">{`Mô hình 3D của ${name}`}</Dialog.Title>
      <div className="tg-s3v__veil" />
      <div className="tg-s3v__world"><img src={`/space3d/posters/${slug}.webp`} alt="" /></div>
      <div className="tg-s3v__say" role="status">
        {shown === 'error'
          ? 'Máy này chưa mở được mô hình 3D. Bạn vẫn xem được nơi này ở phần Hình ảnh.'
          : <><i aria-hidden="true" />Đang mở mô hình 3D…</>}
      </div>
      <div className="tg-s3v__chrome">
        <button type="button" className="tg-s3v__back" ref={backButton} onClick={back}><Icon name="arrowLeft" size={18} /> Quay lại</button>
        <p className="tg-s3v__name"><small>Khám phá 3D</small>{name}</p>
      </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
