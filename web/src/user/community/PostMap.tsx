import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import type { Map as VectorMap, StyleSpecification } from 'maplibre-gl'
import { useAllPhotos } from '../../data/store'
import { Icon } from '../ui/icons'
import { Pic } from './parts'

// The map beside the results. Same base map as the itinerary (OpenFreeMap "positron" vector tiles, the pale grey-green one). It is bare
// until a place is in focus (hovered in the list, or opened): then that place's dot shows, in the brand colour, and the camera flies to
// it, so places that are far apart can still be seen one at a time. Click the dot to open the place. With no WebGL or no network the
// OSM mosaic the app ships (/img/map) stands in.
const STYLE_URL = 'https://tiles.openfreemap.org/styles/positron'
const Z = { x: 3279, y: 1909, size: 256, n: 4096, cols: 5 }
const SIDE = Z.size * Z.cols
const FOCUS_ZOOM = 15

export interface Pin { id: string; lat: number; lng: number; label: string; sub?: string }
// `photos`: pictures to show on the focused place instead of the place's own (the post under the pointer). At most three are ever shown.
interface Props { pins: Pin[]; focus: string | null; photos?: string[] | null; onHot: (id: string | null) => void; onPhotos: (srcs: string[], at: number) => void }
const FAN = 3

// The mark of the place in focus: its dot, its name, and up to three photo cards fanned above it (left card leaning left, middle
// upright, right leaning right). Nothing to click to get it: it is there while the place is in focus.
function Mark({ pin, photos, onHot, onPhotos, style }: { pin: Pin; photos?: string[] | null; onHot: Props['onHot']; onPhotos: Props['onPhotos']; style: React.CSSProperties }) {
  const own = useAllPhotos(pin.id)
  const srcs = (photos?.length ? photos : own.map((c) => c.src)).slice(0, FAN)
  return (
    <div className="tg-bp-pin is-on" style={style} onMouseEnter={() => onHot(pin.id)} onMouseLeave={() => onHot(null)}>
      {srcs.length > 0 && (
        <div className={`tg-bp-fan is-${srcs.length}`} key={srcs.join('|')}>
          {srcs.map((src, i) => (
            <button key={src} type="button" className={`tg-bp-fan__c is-${i}`} style={{ '--i': i } as React.CSSProperties} aria-label={`Xem ảnh ${i + 1} của ${pin.label}`} onClick={() => onPhotos(srcs, i)}>
              <Pic src={src} alt="" eager />
            </button>
          ))}
        </div>
      )}
      <span className="tg-bp-pin__dot" />
      <span className="tg-bp-pin__tag"><b>{pin.label}</b>{pin.sub && <small>{pin.sub}</small>}</span>
    </div>
  )
}

export function PostMap(props: Props) {
  const [offline, setOffline] = useState(() => !navigator.onLine)
  return (
    <div className="tg-bp-map">
      {offline ? <Mosaic {...props} /> : <Live {...props} onFail={() => setOffline(true)} />}
      <span className="tg-bp-map__credit">{offline ? '© OpenStreetMap contributors' : 'OpenFreeMap © OpenMapTiles · dữ liệu OpenStreetMap'}</span>
    </div>
  )
}

const fit = (pins: Pin[]): [[number, number], [number, number]] => [
  [Math.min(...pins.map((p) => p.lng)), Math.min(...pins.map((p) => p.lat))],
  [Math.max(...pins.map((p) => p.lng)), Math.max(...pins.map((p) => p.lat))],
]

function Live({ pins, focus, photos, onHot, onPhotos, onFail }: Props & { onFail: () => void }) {
  const box = useRef<HTMLDivElement>(null)
  const map = useRef<VectorMap | null>(null)
  const [ready, setReady] = useState(false)
  const [xy, setXy] = useState<Record<string, [number, number]>>({})
  const latest = useRef({ pins, focus })
  latest.current = { pins, focus }
  const key = pins.map((p) => p.id).join('|')

  const overview = (m: VectorMap, animate: boolean) => {
    const list = latest.current.pins
    if (!list.length) return
    if (list.length === 1) m.easeTo({ center: [list[0].lng, list[0].lat], zoom: FOCUS_ZOOM - 1, duration: animate ? 600 : 0 })
    else m.fitBounds(fit(list), { padding: { top: 90, bottom: 90, left: 80, right: 80 }, maxZoom: 13, duration: animate ? 700 : 0 })
  }
  const project = () => {
    const m = map.current
    if (!m) return
    const next: Record<string, [number, number]> = {}
    for (const p of latest.current.pins) { const q = m.project([p.lng, p.lat]); next[p.id] = [q.x, q.y] }
    setXy(next)
  }

  useEffect(() => {
    const el = box.current
    if (!el) return
    const abort = new AbortController()
    let m: VectorMap | null = null
    let frame = 0
    const timer = setTimeout(onFail, 15000)
    ;(async () => {
      try {
        const [lib, worker] = await Promise.all([import('maplibre-gl'), import('maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url')])
        if (abort.signal.aborted) return
        const probe = document.createElement('canvas').getContext('webgl2')
        if (!probe) { onFail(); return }
        probe.getExtension('WEBGL_lose_context')?.loseContext()
        lib.setWorkerUrl(worker.default)
        const res = await fetch(STYLE_URL, { signal: abort.signal, credentials: 'omit' })
        if (!res.ok) throw new Error('style')
        const style = (await res.json()) as StyleSpecification
        for (const layer of style.layers) {
          if (layer.type === 'symbol' && layer.layout?.['text-field'] && /name/.test(JSON.stringify(layer.layout['text-field']))) layer.layout['text-field'] = ['coalesce', ['get', 'name:vi'], ['get', 'name']]
        }
        if (abort.signal.aborted) return
        const list = latest.current.pins
        m = new lib.Map({
          container: el, style, attributionControl: false, renderWorldCopies: false, maxZoom: 17, minZoom: 8, dragRotate: false, pitchWithRotate: false, touchPitch: false, fadeDuration: 0,
          ...(list.length > 1 ? { bounds: fit(list), fitBoundsOptions: { padding: { top: 90, bottom: 90, left: 80, right: 80 }, maxZoom: 13 } } : { center: list[0] ? [list[0].lng, list[0].lat] as [number, number] : [108.44, 11.94] as [number, number], zoom: list[0] ? FOCUS_ZOOM - 1 : 11 }),
        })
        map.current = m
        m.on('webglcontextlost', onFail)
        const sync = () => { cancelAnimationFrame(frame); frame = requestAnimationFrame(project) }
        m.on('move', sync)
        m.on('resize', sync)
        m.on('load', () => { project(); setReady(true); clearTimeout(timer) })
      } catch {
        if (!abort.signal.aborted) onFail()
      }
    })()
    return () => { abort.abort(); clearTimeout(timer); cancelAnimationFrame(frame); map.current = null; m?.remove() }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // the box changes size with the window
  useLayoutEffect(() => {
    const el = box.current
    if (!el) return
    const ro = new ResizeObserver(() => map.current?.resize())
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  // a new result set: show all of it; a focused place: fly to it; the focus leaves: back to the overview
  const was = useRef<string | null>(null)
  useEffect(() => {
    const m = map.current
    if (!m || !ready) return
    const p = focus ? latest.current.pins.find((x) => x.id === focus) : null
    if (p) m.easeTo({ center: [p.lng, p.lat], zoom: Math.max(m.getZoom(), FOCUS_ZOOM), duration: 700, essential: false })
    else if (was.current || !focus) overview(m, !!was.current)
    was.current = focus
    project()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focus, key, ready])

  return (
    <>
      <div ref={box} className="tg-bp-live" />
      {!ready && <span className="tg-bp-map__status" role="status">Đang tải bản đồ…</span>}
      <div className="tg-bp-pins">
        {pins.filter((p) => p.id === focus).map((p) => xy[p.id] && <Mark key={p.id} pin={p} photos={photos} onHot={onHot} onPhotos={onPhotos} style={{ left: xy[p.id][0], top: xy[p.id][1], zIndex: 4 }} />)}
      </div>
      <div className="tg-bp-map__zoom" role="group" aria-label="Thu phóng bản đồ">
        <button type="button" aria-label="Phóng to" onClick={() => map.current?.zoomIn()}><Icon name="plus" size={18} /></button>
        <button type="button" aria-label="Thu nhỏ" onClick={() => map.current?.zoomOut()}><Icon name="minus" size={18} /></button>
      </div>
    </>
  )
}

// ---------- offline stand-in: the OSM zoom-12 mosaic ----------

const project = (lat: number, lng: number): [number, number] => {
  const r = (lat * Math.PI) / 180
  return [((lng + 180) / 360 * Z.n - Z.x) * Z.size, ((1 - Math.asinh(Math.tan(r)) / Math.PI) / 2 * Z.n - Z.y) * Z.size]
}
const inside = ([x, y]: [number, number]) => x >= 0 && y >= 0 && x <= SIDE && y <= SIDE
const TILES = Array.from({ length: Z.cols * Z.cols }, (_, i) => ({ x: i % Z.cols, y: Math.floor(i / Z.cols) }))

function Mosaic({ pins, focus, photos, onHot, onPhotos }: Props) {
  const box = useRef<HTMLDivElement>(null)
  const [size, setSize] = useState<[number, number]>([0, 0])
  const [view, setView] = useState({ zoom: 1, cx: SIDE / 2, cy: SIDE / 2 })
  const drag = useRef<{ x: number; y: number; cx: number; cy: number } | null>(null)
  const pts = useMemo(() => pins.map((p) => ({ ...p, xy: project(p.lat, p.lng) })).filter((p) => inside(p.xy)), [pins])
  const [w, h] = size
  useLayoutEffect(() => {
    const el = box.current
    if (!el) return
    const read = () => setSize([el.clientWidth, el.clientHeight])
    read()
    const ro = new ResizeObserver(read)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  const min = w && h ? Math.max(w, h) / SIDE : 0.4
  const bound = (c: number, len: number, z: number) => (SIDE * z <= len ? SIDE / 2 : Math.min(SIDE - len / (2 * z), Math.max(len / (2 * z), c)))
  const key = pts.map((p) => p.id).join('|')
  useEffect(() => {
    if (!w || !h || !pts.length) return
    const xs = pts.map((p) => p.xy[0]), ys = pts.map((p) => p.xy[1])
    const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys)
    const zoom = Math.min(3.4, Math.max(min, pts.length === 1 ? 2 : Math.min((w - 160) / Math.max(40, x1 - x0), (h - 180) / Math.max(40, y1 - y0), 2.4)))
    setView({ zoom, cx: bound((x0 + x1) / 2, w, zoom), cy: bound((y0 + y1) / 2, h, zoom) })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, !!w, !!h])
  useEffect(() => {
    const p = pts.find((x) => x.id === focus)
    if (p && w && h) setView((v) => { const z = Math.max(v.zoom, 2.2); return { zoom: z, cx: bound(p.xy[0], w, z), cy: bound(p.xy[1], h, z) } })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focus])
  const zoomBy = (k: number) => setView((v) => { const z = Math.min(3.4, Math.max(min, v.zoom * k)); return { zoom: z, cx: bound(v.cx, w, z), cy: bound(v.cy, h, z) } })
  useEffect(() => {
    const el = box.current
    if (!el) return
    const wheel = (e: WheelEvent) => { e.preventDefault(); zoomBy(Math.exp(-e.deltaY * 0.0016)) }
    el.addEventListener('wheel', wheel, { passive: false })
    return () => el.removeEventListener('wheel', wheel)
  })
  const { zoom, cx, cy } = view
  return (
    <div ref={box} className="tg-bp-mosaic" role="group" aria-label="Bản đồ các địa điểm"
      onPointerDown={(e) => { if ((e.target as HTMLElement).closest('button')) return; drag.current = { x: e.clientX, y: e.clientY, cx, cy }; e.currentTarget.setPointerCapture(e.pointerId) }}
      onPointerMove={(e) => { const d = drag.current; if (d) setView((v) => ({ ...v, cx: bound(d.cx - (e.clientX - d.x) / v.zoom, w, v.zoom), cy: bound(d.cy - (e.clientY - d.y) / v.zoom, h, v.zoom) })) }}
      onPointerUp={() => { drag.current = null }} onPointerCancel={() => { drag.current = null }}>
      <div className="tg-bp-mosaic__world" style={{ width: SIDE, height: SIDE, transform: `translate(${w / 2 - cx * zoom}px, ${h / 2 - cy * zoom}px) scale(${zoom})` }}>
        {TILES.map((t) => <img key={`${t.x}-${t.y}`} src={`/img/map/${Z.x + t.x}-${Z.y + t.y}.png`} alt="" draggable={false} style={{ left: t.x * Z.size, top: t.y * Z.size, width: Z.size, height: Z.size }} />)}
      </div>
      <div className="tg-bp-pins">
        {pts.filter((p) => p.id === focus).map((p) => <Mark key={p.id} pin={p} photos={photos} onHot={onHot} onPhotos={onPhotos} style={{ left: w / 2 + (p.xy[0] - cx) * zoom, top: h / 2 + (p.xy[1] - cy) * zoom, zIndex: 4 }} />)}
      </div>
      <div className="tg-bp-map__zoom" role="group" aria-label="Thu phóng bản đồ">
        <button type="button" aria-label="Phóng to" onClick={() => zoomBy(1.4)}><Icon name="plus" size={18} /></button>
        <button type="button" aria-label="Thu nhỏ" onClick={() => zoomBy(1 / 1.4)}><Icon name="minus" size={18} /></button>
      </div>
      {pins.length > pts.length && <span className="tg-bp-map__status">{pins.length - pts.length} nơi nằm ngoài khung bản đồ</span>}
    </div>
  )
}
