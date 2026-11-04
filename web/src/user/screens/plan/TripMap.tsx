import { useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { mapsRouteLink } from '../../../data/store'
import { info } from '../../lib'
import type { DayRoute } from '../../planning/types'
import { Icon } from '../../ui/icons'
import type { Map as VectorMap, StyleSpecification } from 'maplibre-gl'

// The vector camera shares the existing Mercator projection with the route and DOM pins.
// The bundled zoom-12 OSM mosaic is only a native-resolution offline fallback.
const Z = { x: 3279, y: 1909, size: 256, n: 4096, cols: 5 }
const SIDE = Z.size * Z.cols
const STYLE_URL = 'https://tiles.openfreemap.org/styles/positron'

type Pt = { lat: number; lng: number }
const project = (p: Pt): [number, number] => {
  const lat = (p.lat * Math.PI) / 180
  return [((p.lng + 180) / 360 * Z.n - Z.x) * Z.size, ((1 - Math.asinh(Math.tan(lat)) / Math.PI) / 2 * Z.n - Z.y) * Z.size]
}
const unproject = ([x, y]: [number, number]): [number, number] => [
  (x / Z.size + Z.x) / Z.n * 360 - 180,
  Math.atan(Math.sinh(Math.PI * (1 - 2 * (y / Z.size + Z.y) / Z.n))) * 180 / Math.PI,
]
function localizeStyle(style: StyleSpecification): StyleSpecification {
  const [west, north] = unproject([0, 0]), [east, south] = unproject([SIDE, SIDE])
  for (const source of Object.values(style.sources)) {
    if (source.type === 'vector' || source.type === 'raster') source.bounds = [west, south, east, north]
  }
  for (const layer of style.layers) {
    if (layer.type === 'symbol' && layer.layout?.['text-field'] && /name/.test(JSON.stringify(layer.layout['text-field']))) {
      layer.layout['text-field'] = ['coalesce', ['get', 'name:vi'], ['get', 'name']]
    }
  }
  return style
}
const inside = ([x, y]: [number, number]) => x >= 0 && y >= 0 && x <= SIDE && y <= SIDE
const distance = (a: [number, number], b: [number, number]) => {
  const p = (n: number) => n * Math.PI / 180
  return 6371000 * 2 * Math.asin(Math.min(1, Math.sqrt(Math.sin(p(b[0] - a[0]) / 2) ** 2 + Math.cos(p(a[0])) * Math.cos(p(b[0])) * Math.sin(p(b[1] - a[1]) / 2) ** 2)))
}

let mosaic: Promise<HTMLCanvasElement> | null = null
function loadMosaic() {
  mosaic ??= new Promise((resolve) => {
    const c = document.createElement('canvas')
    c.width = c.height = SIDE
    const g = c.getContext('2d')!
    const jobs: Promise<void>[] = []
    for (let x = 0; x < Z.cols; x++) for (let y = 0; y < Z.cols; y++)
      jobs.push(new Promise((done) => {
        const im = new Image()
        im.onload = () => { g.drawImage(im, x * Z.size, y * Z.size); done() }
        im.onerror = () => done()
        im.src = `/img/map/${Z.x + x}-${Z.y + y}.png`
      }))
    void Promise.all(jobs).then(() => resolve(c))
  })
  return mosaic
}

export interface Stop { id: string; n: number }

// Floating labels: each takes the first side of its point (in the order given) where it neither covers a pin or an earlier label nor leaves the map.
type Rect = [number, number, number, number]
type Side = 'up' | 'down' | 'right' | 'left'
const hits = (a: Rect, b: Rect) => a[0] < b[2] && b[0] < a[2] && a[1] < b[3] && b[1] < a[3]
const labelW = (text: string) => Math.max(96, Math.min(230, text.length * 7 + 28))
function placeLabel(x: number, y: number, r: number, width: number, w: number, h: number, sides: Side[], taken: Rect[]) {
  const height = 52
  width = Math.min(width, w - 16)
  const gap = 10
  const spots = sides.map((side) => {
    const cx = Math.max(width / 2 + 8, Math.min(w - width / 2 - 8, x))
    const at = {
      up: { left: cx, top: y - r - gap, tx: '-50%', ty: '-100%', rect: [cx - width / 2, y - r - gap - height, cx + width / 2, y - r - gap] as Rect },
      down: { left: cx, top: y + r + gap, tx: '-50%', ty: '0', rect: [cx - width / 2, y + r + gap, cx + width / 2, y + r + gap + height] as Rect },
      right: { left: x + r + gap, top: y, tx: '0', ty: '-50%', rect: [x + r + gap, y - height / 2, x + r + gap + width, y + height / 2] as Rect },
      left: { left: x - r - gap, top: y, tx: '-100%', ty: '-50%', rect: [x - r - gap - width, y - height / 2, x - r - gap, y + height / 2] as Rect },
    }[side]
    const [x0, y0, x1, y1] = at.rect
    const inMap = x0 >= 6 && x1 <= w - 6 && y0 >= 58 && y1 <= h - 34
    return { ...at, ok: inMap && !taken.some((t) => hits(at.rect, t)) }
  })
  // Search nearby free rows as well: a crowded anchor must never force an overlapping label.
  const pick = spots.find((sp) => sp.ok) ?? (() => {
    const candidates: { rect: Rect; cost: number }[] = []
    for (let top = 60; top + height <= h - 44; top += 16) for (let left = 8; left + width <= w - 8; left += 16) {
      const rect: Rect = [left, top, left + width, top + height]
      if (!taken.some((t) => hits(rect, t))) candidates.push({ rect, cost: (left + width / 2 - x) ** 2 + (top + height / 2 - y) ** 2 })
    }
    return candidates.sort((a, b) => a.cost - b.cost)[0]
  })()
  if (!pick) return null
  taken.push(pick.rect)
  return { left: pick.rect[0], top: pick.rect[1], translate: 'none', width, height }
}

type Path = NonNullable<DayRoute['route']>

// Index of the path vertex nearest to each stop, never going back: where each leg of the road starts and ends.
function legStarts(path: Path, pts: [number, number][]) {
  const v = path.coords.map(([lat, lng]) => project({ lat, lng }))
  // Minimise the total snap error under the ordering constraint. A greedy nearest point can jump straight
  // to the return of a loop and leave no geometry for the intervening stops.
  let costs = v.map(() => 0)
  const parents: number[][] = []
  for (const [x, y] of pts) {
    let best = 0
    const row: number[] = []
    const next = v.map(([vx, vy], i) => {
      if (costs[i] < costs[best]) best = i
      row.push(best)
      return costs[best] + (vx - x) ** 2 + (vy - y) ** 2
    })
    parents.push(row)
    costs = next
  }
  let cursor = costs.reduce((best, cost, i) => cost < costs[best] ? i : best, 0)
  const at = pts.map(() => 0)
  for (let i = pts.length - 1; i >= 0; i--) { at[i] = cursor; cursor = parents[i][cursor] }
  return { v, at }
}

// groups: one list of place ids per line (a day); pins are numbered 1.. through all groups in order.
// routes: the road path of each group (null / missing: sketch). ends: names (and clock times) of the opening and closing point of a single day.
// soft: a paler base map, so the route and the pins carry the picture (the day view). notes: the second line of a stop's floating label.
export function TripMap({ groups, title, className = '', hot, onHot, onOpen, labels = true, soft = false, notes, routes, ends, children }: {
  groups: string[][]; title: string; className?: string; hot?: string | null; onHot?: (id: string | null) => void; onOpen?: (id: string) => void; labels?: boolean
  soft?: boolean; notes?: Record<string, string>
  routes?: (Path | null)[]; ends?: { start: string; end: string; startAt?: string; endAt?: string; startPoint?: Pt; endPoint?: Pt }; children?: ReactNode
}) {
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState<[number, number]>([0, 0])
  const drag = useRef<{ x: number; y: number; pan: [number, number] } | null>(null)
  const box = useRef<HTMLDivElement>(null)
  const canvas = useRef<HTMLCanvasElement>(null)
  const [tiles, setTiles] = useState<HTMLCanvasElement | null>(null)
  const [size, setSize] = useState<[number, number]>([0, 0])
  const [offline, setOffline] = useState(() => !navigator.onLine)
  const [wheelActive, setWheelActive] = useState(false)
  const [liveReady, setLiveReady] = useState(false)
  const [revealed, setRevealed] = useState(false)
  const base = useRef<HTMLDivElement>(null)
  const vector = useRef<VectorMap | null>(null)
  const panFrame = useRef(0)
  const nextPan = useRef<[number, number]>([0, 0])
  const dpr = window.devicePixelRatio || 1
  useEffect(() => { void loadMosaic().then(setTiles) }, [])
  useEffect(() => {
    const retry = () => setOffline(false)
    const disconnect = () => setOffline(true)
    window.addEventListener('online', retry)
    window.addEventListener('offline', disconnect)
    return () => {
      window.removeEventListener('online', retry)
      window.removeEventListener('offline', disconnect)
      cancelAnimationFrame(panFrame.current)
    }
  }, [])
  useLayoutEffect(() => {
    const el = box.current
    if (!el) return
    const read = () => setSize([el.clientWidth, el.clientHeight])
    read()
    const ro = new ResizeObserver(read)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const [w, h] = size
  const groupKey = groups.map(g => g.join(',')).join('|')
  const lines = useMemo(() => {
    let k = 0
    return groups.map((ids) => ids.flatMap((id) => { const p = info(id); return p ? [{ id, n: ++k, xy: project(p) }] : [] }))
  }, [groupKey])
  const all = lines.flat()
  const shown = all
  // the road of each line: its vertices, and where each stop sits on it
  const roads = useMemo(() => lines.map((line, i) => {
    const path = routes?.[i]
    return path && path.coords.length > 1 ? { path, ...legStarts(path, line.map((s) => s.xy)) } : null
  }), [lines, routes])
  const single = groups.length === 1 ? roads[0] : null
  const endPts: ([number, number] | null)[] = groups.length === 1 ? [ends?.startPoint ? project(ends.startPoint) : single?.v[0] ?? null, ends?.endPoint ? project(ends.endPoint) : single?.v[single.v.length - 1] ?? null] : []
  const hotAt = single ? lines[0].findIndex((s) => s.id === hot) : -1
  const out = all.filter((s) => !inside(s.xy)).length
  const fitBounds = useMemo(() => {
    let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity
    const include = ([x, y]: [number, number]) => { x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y) }
    for (const line of lines) for (const stop of line) include(stop.xy)
    for (const road of roads) if (road) for (const point of road.v) include(point)
    for (const point of endPts) if (point) include(point)
    return Number.isFinite(x0) ? [x0, x1, y0, y1] : [0, SIDE, 0, SIDE]
    // Bounds are independent of pan, zoom and tile fade frames.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lines, roads, endPts.flat().join(',')])
  // Fit up to OSM zoom 16; MapLibre uses a 512px world tile, so its zoom is one lower.
  let scale = Math.min(1, Math.max(w, h) / SIDE)
  let maxZoom = 1
  let ox = 0
  let oy = 0
  if (w && h) {
    const [x0, x1, y0, y1] = fitBounds
    const fit = Math.min(Math.max(60, w - (labels ? 300 : 100)) / Math.max(1, x1 - x0), Math.max(60, h - (soft ? 240 : 140)) / Math.max(1, y1 - y0))
    const fittedScale = Math.min(offline ? 1 : 16, fit)
    maxZoom = (offline ? 1 : 32) / fittedScale
    const fittedZoom = Math.min(zoom, maxZoom)
    scale = Math.min(offline ? 1 : 32, fittedScale * fittedZoom)
    ox = w / 2 - ((x0 + x1) / 2) * scale + (!offline || fittedZoom > 1 ? pan[0] : 0)
    oy = h / 2 - ((y0 + y1) / 2) * scale + (!offline || fittedZoom > 1 ? pan[1] : 0)
    const bound = (offset: number, length: number) => SIDE * scale <= length ? (length - SIDE * scale) / 2 : Math.max(length - SIDE * scale, Math.min(0, offset))
    ox = bound(ox, w)
    oy = bound(oy, h)
  }
  const currentZoom = Math.min(zoom, maxZoom)
  const at = (xy: [number, number]) => [ox + xy[0] * scale, oy + xy[1] * scale] as const
  const ready = offline ? !!tiles : liveReady
  const camera = useRef({ w, h, scale, ox, oy })
  camera.current = { w, h, scale, ox, oy }

  useEffect(() => {
    if (offline || !base.current || !w || !h) return
    const controller = new AbortController()
    setLiveReady(false)
    setRevealed(false)
    // Covers import, style, glyph and tile stalls; idle is the only initial reveal gate.
    const timeout = setTimeout(() => setOffline(true), 15000)
    let map: VectorMap | null = null
    const start = async () => {
      try {
        const [lib, worker] = await Promise.all([import('maplibre-gl'), import('maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url')])
        if (controller.signal.aborted) return
        const probe = document.createElement('canvas').getContext('webgl2')
        if (!probe) { setOffline(true); return }
        probe.getExtension('WEBGL_lose_context')?.loseContext()
        lib.setWorkerUrl(worker.default)
        const response = await fetch(STYLE_URL, { signal: controller.signal, credentials: 'omit' })
        if (!response.ok) throw new Error('Map style unavailable')
        const style = localizeStyle(await response.json() as StyleSpecification)
        if (controller.signal.aborted) return
        const c = camera.current
        map = new lib.Map({
          container: base.current!, style, interactive: false, attributionControl: false,
          center: unproject([(c.w / 2 - c.ox) / c.scale, (c.h / 2 - c.oy) / c.scale]),
          zoom: 11 + Math.log2(c.scale), maxZoom: 16, renderWorldCopies: false,
          maxTileCacheSize: 96, cancelPendingTileRequestsWhileZooming: true,
          fadeDuration: 0,
        })
        vector.current = map
        map.on('error', () => { if (!controller.signal.aborted) setOffline(true) })
        map.on('webglcontextlost', () => setOffline(true))
        map.on('idle', () => { clearTimeout(timeout); if (!controller.signal.aborted) { setLiveReady(true); setRevealed(true) } })
      } catch {
        if (!controller.signal.aborted) setOffline(true)
      }
    }
    void start()
    return () => { controller.abort(); clearTimeout(timeout); vector.current = null; map?.remove() }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [offline, !!w, !!h])

  useLayoutEffect(() => {
    const map = vector.current
    if (!map || offline) return
    map.resize()
    map.redraw()
  }, [w, h, offline])

  useLayoutEffect(() => {
    const map = vector.current
    if (!map || offline) return
    setLiveReady(false)
    const timeout = setTimeout(() => setOffline(true), 15000)
    const idle = () => clearTimeout(timeout)
    map.on('idle', idle)
    map.jumpTo({ center: unproject([(w / 2 - ox) / scale, (h / 2 - oy) / scale]), zoom: 11 + Math.log2(scale) })
    // Paint in this commit, not the next RAF: the route canvas and DOM pins have already moved.
    map.redraw()
    return () => { clearTimeout(timeout); map.off('idle', idle) }
  }, [w, h, scale, ox, oy, offline])

  useEffect(() => {
    const el = box.current
    if (!el) return
    const wheel = (event: WheelEvent) => {
      if (!wheelActive && !event.ctrlKey) return
      event.preventDefault()
      const next = Math.max(1, Math.min(maxZoom, currentZoom * (event.deltaY < 0 ? 1.2 : 1 / 1.2)))
      setZoom(next)
      if (next === 1) setPan([0, 0])
    }
    el.addEventListener('wheel', wheel, { passive: false })
    return () => el.removeEventListener('wheel', wheel)
  }, [wheelActive, maxZoom, currentZoom])

  useEffect(() => {
    const c = canvas.current
    if (!c || !w || !h) return
    c.width = w * dpr
    c.height = h * dpr
    const g = c.getContext('2d')!
    g.scale(dpr, dpr)
    const css = getComputedStyle(c)
    if (offline && tiles) {
      g.fillStyle = css.getPropertyValue('--tg-bg').trim()
      g.fillRect(0, 0, w, h)
      g.drawImage(tiles, ox, oy, SIDE * scale, SIDE * scale)
    }
    const ink = css.getPropertyValue('--tg-pine').trim()
    const brand = css.getPropertyValue('--tg-brand').trim() || ink
    g.lineCap = 'round'
    g.lineJoin = 'round'
    const trace = (pts: readonly (readonly [number, number])[]) => { g.beginPath(); pts.forEach(([x, y], i) => (i ? g.lineTo(x, y) : g.moveTo(x, y))); g.stroke() }
    lines.forEach((line, li) => {
      const road = roads[li]
      if (road) {
        const edge = css.getPropertyValue('--tg-surface').trim()
        const thick = soft ? 7 : 5
        const anchors = [li === 0 ? endPts[0] : null, ...line.map((s) => s.xy), li === 0 ? endPts[1] : null]
        const vertices = [0, ...road.at, road.v.length - 1]
        const near = (point: [number, number], i: number) => Math.hypot(point[0] - road.v[i][0], point[1] - road.v[i][1]) * 40075016.686 * Math.cos(road.path.coords[i][0] * Math.PI / 180) / (Z.n * Z.size) <= 150
        const sketch = (from: [number, number], to: [number, number]) => {
          g.strokeStyle = brand; g.lineWidth = 2.5; g.setLineDash([5, 6]); trace([at(from), at(to)])
        }
        for (let i = 1; i < anchors.length; i++) {
          const from = anchors[i - 1], to = anchors[i]
          if (!from || !to) continue
          const a = vertices[i - 1], b = vertices[i]
          if (b > a && near(from, a) && near(to, b)) {
            const part = road.v.slice(a, b + 1).map(at)
            const active = li === 0 && hotAt === i - 1
            g.setLineDash([])
            g.globalAlpha = hotAt >= 0 && !active ? 0.45 : 1
            g.strokeStyle = edge; g.lineWidth = thick + (active ? 7 : 4); trace(part)
            g.strokeStyle = brand; g.lineWidth = thick + (active ? 2 : 0); trace(part)
            g.globalAlpha = 1
            sketch(from, road.v[a]); sketch(road.v[b], to)
          } else sketch(from, to)
        }
        return
      }
      const pts = [...(li === 0 && endPts[0] ? [endPts[0]] : []), ...line.map((s) => s.xy), ...(li === 0 && endPts[1] ? [endPts[1]] : [])].map(at)
      if (pts.length < 2) return
      g.strokeStyle = brand
      g.lineWidth = 2.5
      g.setLineDash([5, 6])
      trace(pts)
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tiles, offline, soft, w, h, scale, ox, oy, hotAt, routes, endPts.flat().join(','), groupKey])

  useEffect(() => { setZoom(1); setPan([0, 0]); setWheelActive(false) }, [title, groupKey, offline])

  // pins and floating labels, in the order that wins a contested spot: the stop in focus, then the opening and closing point
  const taken: Rect[] = [...shown.map((s) => s.xy), ...endPts.filter((p): p is [number, number] => !!p)].map((xy) => { const [px, py] = at(xy); return [px - 23, py - 23, px + 23, py + 23] as Rect })
  taken.push([w - 64, h - 120, w, h])
  const focus = labels ? shown.find((s) => s.id === hot) : undefined
  const focusPos = focus && (() => {
    const [px, py] = at(focus.xy)
    const name = info(focus.id)?.name ?? ''
    const sub = notes?.[focus.id] ?? info(focus.id)?.category ?? 'Địa điểm'
    return placeLabel(px, py, 15, labelW(name.length > sub.length ? name : sub), w, h, ['up', 'down', 'right', 'left'], taken)
  })()
  const endCoords = single?.path.coords
  const startCoord = ends?.startPoint ? [ends.startPoint.lat, ends.startPoint.lng] as [number, number] : endCoords?.[0]
  const endCoord = ends?.endPoint ? [ends.endPoint.lat, ends.endPoint.lng] as [number, number] : endCoords?.[endCoords.length - 1]
  const roundTrip = startCoord && endCoord && distance(startCoord, endCoord) < 150
  const endTags = ends ? ([['start', endPts[0], roundTrip ? 'Xuất phát và về' : ends.start, roundTrip ? [ends.startAt, ends.endAt].filter(Boolean).join(' → ') : `Xuất phát${ends.startAt ? ` · ${ends.startAt}` : ''}`, ['up', 'left', 'right', 'down']], ['end', roundTrip ? null : endPts[1], ends.end, `Kết thúc ngày${ends.endAt ? ` · ${ends.endAt}` : ''}`, ['down', 'right', 'left', 'up']]] as const).flatMap(([k, xy, name, tag, sides]) => {
    if (!xy) return []
    const [px, py] = at(xy)
    const pos = placeLabel(px, py, 9, labelW(name.length > tag.length ? name : tag), w, h, [...sides], taken)
    return pos ? [{ k, px, py, name, tag, pos }] : []
  }) : []

  return (
    <div className={`tg-it-map ${!offline || currentZoom > 1 ? 'is-pannable' : ''} ${className}`} ref={box} role="group" aria-label={title} tabIndex={0}
      data-map-mode={offline ? 'offline' : 'live'} data-map-scale={scale} data-map-ready={ready} data-tile-zoom={offline ? 12 : 11 + Math.log2(scale)}
      onBlur={(e) => { if (!e.currentTarget.contains(e.relatedTarget)) setWheelActive(false) }} onPointerLeave={() => setWheelActive(false)}
      onPointerDown={(e) => { setWheelActive(true); if ((!offline || currentZoom > 1) && !(e.target as HTMLElement).closest('button, a')) { drag.current = { x: e.clientX, y: e.clientY, pan }; e.currentTarget.setPointerCapture(e.pointerId) } }}
      onPointerMove={(e) => { const d = drag.current; if (d) { nextPan.current = [d.pan[0] + e.clientX - d.x, d.pan[1] + e.clientY - d.y]; cancelAnimationFrame(panFrame.current); panFrame.current = requestAnimationFrame(() => setPan(nextPan.current)) } }}
      onPointerUp={() => { drag.current = null }} onPointerCancel={() => { drag.current = null }}>
      <div ref={base} className={`tg-it-basemap ${revealed && !offline ? 'is-ready' : ''}`} aria-hidden="true" />
      <canvas ref={canvas} aria-hidden="true" />
      {!ready && <span className="tg-it-map__status" role="status">Đang tải bản đồ…</span>}
      {offline && <button type="button" className="tg-it-map__status" onClick={() => { if (navigator.onLine) setOffline(false) }}>Bản đồ offline · Thử lại</button>}
      <div className="tg-it-pins">
        {shown.map((s) => {
          const [x, y] = at(s.xy)
          const on = hot === s.id
          return (
            <span key={`${s.id}-${s.n}`}>
              <button type="button" className={`tg-it-pin ${on ? 'is-hot' : ''}`} style={{ left: x, top: y }} aria-label={`${s.n}. ${info(s.id)?.name ?? s.id}`}
                onMouseEnter={() => onHot?.(s.id)} onMouseLeave={() => onHot?.(null)} onFocus={() => onHot?.(s.id)} onBlur={() => onHot?.(null)} onClick={() => onOpen?.(s.id)}>{s.n}</button>
              {focus && focusPos && focus.id === s.id && focus.n === s.n && <span className="tg-it-pin__label" style={focusPos}><b>{info(s.id)?.name}</b><small>{notes?.[s.id] ?? info(s.id)?.category ?? 'Địa điểm'}</small></span>}
            </span>
          )
        })}
      </div>
      {endTags.length > 0 && (
        <div className="tg-it-pins">
          {endTags.map((t) => (
            <span key={t.k}>
              <span className={`tg-it-end is-${t.k}`} style={{ left: t.px, top: t.py }} aria-hidden="true" />
              <span className="tg-it-callout" style={t.pos}><b>{t.name}</b><small>{t.tag}</small></span>
            </span>
          ))}
        </div>
      )}
      <div className="tg-it-zoom" role="group" aria-label="Thu phóng bản đồ">
        <button type="button" aria-label="Phóng to" disabled={currentZoom >= maxZoom} onClick={() => setZoom(Math.min(maxZoom, +(currentZoom * 1.4).toFixed(2)))}><Icon name="plus" size={18} /></button>
        <button type="button" aria-label="Thu nhỏ" disabled={currentZoom <= 1} onClick={() => { const z = Math.max(1, +(currentZoom / 1.4).toFixed(2)); setZoom(z); if (z === 1) setPan([0, 0]) }}><Icon name="minus" size={18} /></button>
      </div>
      {out > 0 && <span className="tg-it-map__out">{out} nơi nằm ngoài khu vực bản đồ</span>}
      <span className="tg-it-map__credit">{offline ? <>© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap contributors</a></> : <><a href="https://openfreemap.org" target="_blank" rel="noreferrer">OpenFreeMap</a> © <a href="https://openmaptiles.org" target="_blank" rel="noreferrer">OpenMapTiles</a> Data from <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a></>}</span>
      {children}
    </div>
  )
}

export function MapsLink({ ids }: { ids: string[] }) {
  const stops = ids.map((id) => info(id)).filter((p): p is NonNullable<typeof p> => !!p)
  if (stops.length < 2) return null
  return <a className="tg-it-chip" href={mapsRouteLink(stops)} target="_blank" rel="noreferrer">Google Maps <Icon name="external" size={13} /></a>
}
