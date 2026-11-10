import * as Dialog from '@radix-ui/react-dialog'
import { useEffect, useRef, useState } from 'react'
import { reducedMotion } from '../lib'
import { Icon } from './icons'

// "Khám phá 3D" tab of the place sheet (docs/Role_Web_Functional_Design.md §6). The tab itself is only a poster and one
// button: pressing it "dives" into a full-page viewer (the sheet fades under a cream veil, the poster grows to the whole
// window while drifting closer, then the live model crossfades in) and Back plays the same dive in reverse into the poster.
// The model runs in a same-origin iframe built by web/scripts/build_space3d.mjs: its scene owns the whole window, and
// removing the frame frees the GPU. The tab exists only for a place in /space3d/index.json.

let models: Promise<Record<string, string>> | undefined
const loadModels = () => (models ??= fetch('/space3d/index.json').then((r) => r.json() as Promise<Record<string, string>>).catch(() => ({} as Record<string, string>)))

// The model of this place, or null while unknown and for a place without one.
export function useSpace3d(id: string): string | null {
  const [slug, setSlug] = useState<string | null>(null)
  useEffect(() => {
    let on = true
    setSlug(null)
    void loadModels().then((all) => { if (on) setSlug(all[id] ?? null) })
    return () => { on = false }
  }, [id])
  return slug
}

// The tab button that was pressed (its rect), left for the Space3d that mounts next: choosing the tab dives at once, the
// poster card below is only what Back lands on (and a way to go in again).
let pending: DOMRect | null = null
export const diveFrom = (rect: DOMRect) => { pending = rect }

export function Space3d({ slug, name }: { slug: string; name: string }) {
  const stage = useRef<HTMLButtonElement>(null)
  const [origin, setOrigin] = useState<DOMRect | null>(() => { const r = pending; pending = null; return r })
  const [diving, setDiving] = useState(origin !== null)
  // Where Back lands: the poster card when it is on screen, else the tab button.
  const target = () => {
    const s = stage.current?.getBoundingClientRect()
    if (s && s.bottom > 0 && s.top < innerHeight) return s
    return document.querySelector('.tg-ps__tabs [aria-selected="true"]')?.getBoundingClientRect() ?? s ?? null
  }
  // Warm the poster's neighbours: the viewer's data is tiny, and the dive starts loading the frame at once.
  useEffect(() => { void fetch(`/space3d/places/${slug}.json`).catch(() => undefined) }, [slug])
  return (
    <div className="tg-s3">
      <h3>Khám phá 3D</h3>
      <p className="tg-pano__note">
        <Icon name="info" size={16} />
        <span>Mô hình minh họa dựng từ ảnh thực tế của nơi này. Tỷ lệ và chi tiết chỉ để tham khảo, có thể khác ngoài đời.</span>
      </p>
      <button type="button" className="tg-s3__stage" ref={stage} onClick={() => { setOrigin(stage.current?.getBoundingClientRect() ?? null); setDiving(true) }} aria-label={`Bước vào mô hình 3D của ${name}`}>
        <img className="tg-s3__poster" src={`/space3d/posters/${slug}.webp`} alt="" />
        <span className="tg-s3__cta"><Icon name="cube" size={18} /> Bước vào mô hình 3D</span>
      </button>
      {diving && <Dive slug={slug} name={name} from={origin} rect={target} onDone={() => setDiving(false)} />}
    </div>
  )
}

// in     the poster (the model's own overview) grows from the tab's card to the window and drifts slightly closer
//        while the sheet behind fades under a cream veil; the frame starts loading at once
// wait   the poster holds (still drifting) with a small "opening" note until the model has drawn its first frame
// reveal the live model crossfades in over the poster, settling from a slight zoom
// open   the model; only the Back button and the place name float on it
// out    Back: the model fades back into the poster and the window shrinks into the card again
type Phase = 'in' | 'wait' | 'reveal' | 'open' | 'out'
const GROW_MS = 760
const REVEAL_MS = 650
const OUT_MS = 680
const GIVE_UP_MS = 30000

const boxVars = (r: DOMRect | null) => (r ? { '--l': `${r.left}px`, '--t': `${r.top}px`, '--w': `${r.width}px`, '--h': `${r.height}px` } : {}) as React.CSSProperties

function Dive({ slug, name, from, rect, onDone }: { slug: string; name: string; from: DOMRect | null; rect: () => DOMRect | null; onDone: () => void }) {
  const calm = reducedMotion()
  const [phase, setPhase] = useState<Phase>('in')
  const [state, setState] = useState<'wait' | 'ready' | 'error'>('wait')
  const [box, setBox] = useState(() => from ?? rect())
  const leaving = useRef(false)

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
    return () => removeEventListener('popstate', onPop)
  }, [])

  useEffect(() => {
    const frame = () => document.querySelector<HTMLIFrameElement>('.tg-s3v__frame')?.contentWindow
    const onMessage = (e: MessageEvent) => {
      if (e.origin !== location.origin || e.source !== frame()) return
      if (e.data?.type === 'space3d:ready') setState('ready')
      if (e.data?.type === 'space3d:error') setState('error')
      if (e.data?.type === 'space3d:back') back()
    }
    addEventListener('message', onMessage)
    return () => removeEventListener('message', onMessage)
  }, [])

  // The entrance: in → wait once the poster fills the window, then reveal as soon as the model has drawn.
  useEffect(() => {
    const a = setTimeout(() => setPhase((p) => (p === 'in' ? 'wait' : p)), calm ? 0 : GROW_MS)
    const c = setTimeout(() => setState((s) => (s === 'wait' ? 'error' : s)), GIVE_UP_MS)
    return () => { clearTimeout(a); clearTimeout(c) }
  }, [])
  useEffect(() => {
    if (phase === 'wait' && state === 'ready') setPhase('reveal')
    if (phase === 'wait' && state === 'error') setPhase('open')
  }, [phase, state])
  useEffect(() => {
    if (phase === 'reveal') { const t = setTimeout(() => setPhase('open'), calm ? 0 : REVEAL_MS); return () => clearTimeout(t) }
    if (phase === 'out') { const t = setTimeout(onDone, calm ? 0 : OUT_MS); return () => clearTimeout(t) }
  }, [phase])

  const shown = state === 'error' ? 'error' : state === 'ready' ? 'ready' : 'wait'
  return (
    <Dialog.Root open onOpenChange={(o) => !o && back()}>
      <Dialog.Portal>
        <Dialog.Content
          className="tg tg-s3v"
          data-phase={phase}
          data-state={shown}
          style={boxVars(box)}
          aria-describedby={undefined}
          onOpenAutoFocus={(e) => { e.preventDefault(); (e.currentTarget as HTMLElement).focus({ preventScroll: true }) }}
          onCloseAutoFocus={(e) => e.preventDefault()}
        >
          <Dialog.Title className="tg-sr">{`Mô hình 3D của ${name}`}</Dialog.Title>
          <div className="tg-s3v__veil" />
          <div className="tg-s3v__world"><img src={`/space3d/posters/${slug}.webp`} alt="" /></div>
          {shown !== 'error' && <iframe className="tg-s3v__frame" title={`Mô hình 3D của ${name}`} src={`/space3d/viewer.html?place=${slug}&host=full`} allow="fullscreen" />}
          <div className="tg-s3v__say" role="status">
            {shown === 'error'
              ? 'Máy này chưa mở được mô hình 3D. Bạn vẫn xem được nơi này ở phần Hình ảnh.'
              : <><i aria-hidden="true" />Đang mở mô hình 3D…</>}
          </div>
          <div className="tg-s3v__chrome">
            <button type="button" className="tg-s3v__back" onClick={back}><Icon name="arrowLeft" size={18} /> Quay lại</button>
            <p className="tg-s3v__name"><small>Khám phá 3D</small>{name}</p>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
