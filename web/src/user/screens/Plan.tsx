import * as Dialog from '@radix-ui/react-dialog'
import { useEffect, useMemo, useState } from 'react'
import { VEHICLE_LABEL } from '../../data/store'
import { enterStage, json, type JourneyView } from '../journey'
import { primeDecision } from '../pd/api'
import { fromSearchInput } from '../tu/adapter'
import type { SearchInput } from '../tu/types'
import { BUSY_TEXT, isStaleText } from '../journeyErrors'
import { fmtMin, fmtVnd, info } from '../lib'
import { usePlanning } from '../planning/planning'
import type { Action, Diff } from '../planning/types'
import { setOptimized, useUi } from '../store'
import { fmtRange, useRides } from '../rides'
import { useTrip } from '../trip'
import { ArtRoute, Busy, Empty, go } from '../ui/common'
import { AssistantFloat } from '../ui/Assistant'
import { Icon } from '../ui/icons'
import { Page, useTitle } from '../ui/Shell'
import { LongTripWarning } from '../ui/LongTripWarning'
import { candidatesOf, type Candidate } from './plan/candidates'
import { Choose } from './plan/Choose'
import { DayView } from './plan/DayView'
import { Journey } from './plan/Journey'
import { Overview } from './plan/Overview'
import { FillRows, FillSheet, OriginRow, TripDates, useFill, useTripEdit } from './plan/fill'
import { Find } from './plan/Find'
import { usePlanSummary } from './plan/summary'
import { LodgingPicker } from './plan/pickers'
import { useRoutes } from './plan/useRoutes'
import { KeepAll, Lodging, LodgingGhost, Optimize } from './plan/parts'
import { costText, MEAL_LABEL, openPlace, placeName, ROBUST_TAG, visits, wayName } from './plan/shared'
import { EveBanner, useEve } from './plan/EveBanner'
import { StayOffer, WayIn, WayPeek } from './plan/WayIn'
import { LodgingCost, lodgingBasis } from './plan/LodgingCost'
import '../css/fixes.css'

// docs/UI_SPEC_USER_WEB.md Trang 8, layout from docs/design/mock/designs/itinerary: choose a way → overview → one screen per day
// (+ a screen to swap or add a place). Times and routes are estimates and say so; warnings sit on the stop they concern.
// Lịch trình takes actions and, through the assistant panel (ui/Assistant.tsx), typed messages: docs/PLANNING.md. A turn that changes
// the plan leaves one new version, which the provider accepts like an act's.

const SCOPE_TEXT: Record<Diff['scope'], string> = {
  none: '',
  relayout: 'Đã xếp lại một vài ngày bị ảnh hưởng',
  variant: 'Đã xếp lại cả chuyến theo thay đổi này',
  lodging_home: 'Đã đổi chỗ nghỉ, giờ di chuyển được tính lại',
  lodging_fetch: 'Đã tìm lại danh sách chỗ ở',
}
const VIOLATION: Record<string, string> = { meal_missing: 'Chưa chừa đủ thời gian cho bữa ăn.', meal_window: 'Chưa xếp được bữa ăn vào khung giờ riêng.', hours: 'Giờ ghé nằm ngoài giờ mở cửa.', timed: 'Giờ ghé chưa khớp khung giờ cần thiết.', overlap: 'Có hoạt động trùng giờ.', day_window: 'Lịch vượt khung giờ của ngày.', travel: 'Chưa đủ thời gian di chuyển.', long_leg: 'Chặng đi vượt giới hạn đã chọn.', anchor: 'Chưa xếp được nơi bắt buộc.', budget: 'Chi phí đã biết vượt ngân sách.', duplicate: 'Địa điểm bị xếp trùng.', hard: 'Chưa đáp ứng yêu cầu bắt buộc.', hazard: 'Điều kiện ngày này không cho phép ghé an toàn.' }

const LEFTOVER = { hours: 'giờ mở cửa không khớp với lịch', time: 'không còn đủ thời gian', search_incomplete: 'chưa kiểm tra xong' } as const

type Screen = 'overview' | 'day'

export function Plan() {
  useTitle('Lịch trình')
  const { trip, dispatch } = useTrip()
  const { view, diff, error, busy, act, previewAct, editPreview, dismissPreview, confirm, optimize } = usePlanning()
  const [peeking, setPeeking] = useState(false) // a preview can take several seconds on the server: say so meanwhile
  const preview = async (a: Action) => { setPeeking(true); try { return await previewAct(a) } finally { setPeeking(false) } }
  const optimized = useUi((u) => (trip.planningId ? u.optimized[trip.planningId] : undefined))
  const fill = useFill(trip.decisionId ?? trip.planningId, trip.planningId)
  const replan = useTripEdit((trip.decisionId ?? trip.planningId) ?? '', () => setPicker(false)) // a saved place outside the selection: choose it, build the plan again
  const [screen, setScreen] = useState<Screen>('overview')
  const [changing, setChanging] = useState(false) // "Đổi phương án": the choice screen again, over a plan that already exists
  const [picked, setDayIdx] = useState<number | null>(null) // null: the first day that has a stop
  const [swapFor, setSwapFor] = useState<string | null>(null) // the place a swap replaces; null: add one
  const [picker, setPicker] = useState(false) // the list of places that slides in to add or swap
  const [ghostFor, setGhostFor] = useState<string | null>(null) // the suggestion whose "+" opened the list: it leads the list
  const [lodgingOpen, setLodgingOpen] = useState(false)
  const [review, setReview] = useState(false) // the whole trip as one route, the last look before the plan is locked
  const [dropAsk, setDropAsk] = useState<string | null>(null)
  const [pickAsk, setPickAsk] = useState<string | null>(null) // another way chosen while a hand-made order exists
  const [optAsk, setOptAsk] = useState(false) // "Tối ưu lịch" while the user has moved places or ordered a day themselves
  const [warnAsk, setWarnAsk] = useState(false) // confirming a plan that still carries warnings: the user decides
  const [droppedOpen, setDroppedOpen] = useState(false)
  const [whyOpen, setWhyOpen] = useState(false) // why the plan is tight or sits close to the clock: the details behind the one-line warning
  const [costOpen, setCostOpen] = useState(false)
  const [opt, setOpt] = useState(false)
  const [confirmed, setConfirmed] = useState(false) // the trip already has a confirmed plan: this screen then edits it, it does not confirm it again
  useEffect(() => {
    const id = trip.journeyId
    if (!id) return
    let live = true
    setConfirmed(false)
    fetch(`/api/harness/sessions/${id}?view=0`).then(json<JourneyView>).then((journey) => {
      if (!live) return
      const input = journey.outputs.trip as SearchInput | undefined
      if (input) dispatch({ type: 'set', patch: fromSearchInput(input) })
      setConfirmed(Boolean(journey.outputs.planning))
    }, () => {})
    return () => { live = false }
  }, [trip.journeyId, dispatch])
  const eve = useEve(trip.journeyId ?? null) // D.3: tomorrow's pending changes on the confirmed plan
  useEffect(() => { window.scrollTo(0, 0) }, [screen, changing, view?.state.chosen_variant])
  // The server's per-person request limit (429) lifts within a minute: try again by itself, gently, instead of leaving a dead end.
  useEffect(() => {
    if (view || error !== BUSY_TEXT) return
    const t = window.setTimeout(() => location.reload(), 30000)
    return () => clearTimeout(t)
  }, [view, error])
  useEffect(() => { if (screen !== 'day') setPicker(false) }, [screen]) // the place list lives on the day screen only
  // The road of each day is read apart from the plan; it is read again whenever the stops, their order or the lodging change.
  const routeKey = `${view?.state.lodging_id ?? ''}|${(view?.itinerary ?? []).map((x) => x.items.filter((it) => it.kind === 'visit').map((it) => it.place_id).join(',')).join('|')}`
  const routes = useRoutes(trip.planningId, routeKey, (screen === 'day' || review) && !!view?.itinerary)
  const variant = useMemo(() => view?.active_variant ?? view?.variants.find((v) => v.id === view.state.chosen_variant) ?? null, [view])
  // Ride-hailing between stops (Grab / Be / Xanh SM) when the trip has no vehicle of its own: it came by coach or plane, or
  // gets around by taxi / Grab, or has not said. Driving in or riding a motorbike in the city needs no ride.
  const ctx = trip.searchInput?.context
  const ownWheels = ctx?.arrival_mode === 'self' || ctx?.mobility === 'motorbike' || (ctx?.mobility === 'car' && ctx?.driver !== 'hired') || ctx?.mobility === 'walk'
  const sumDays = view?.itinerary ?? variant?.itinerary ?? []
  const sumStops = sumDays.map((x) => visits(x).map((it) => it.place_id).join(',')).join('|')
  const sumCount = sumDays.reduce((n, x) => n + visits(x).length, 0)
  const summary = usePlanSummary(view?.variants.length ? trip.planningId : null, sumStops.replace(/[|,]/g, ''), { title: `Chuyến đi Đà Lạt của bạn`, text: `${sumDays.length} ngày, ${sumCount} nơi. Mở từng ngày để xem, đổi hoặc thêm nơi muốn ghé.` })
  const rides = useRides(view?.itinerary ?? variant?.itinerary ?? [], !!view && !!ctx && !ownWheels, trip.people)
  // Back to Chọn nơi opens at once: the screen paints the list it showed last time while the journey steps back to that stage in the
  // background (pd/api primeDecision hands the screen that same read; a failure is reported by Chọn nơi itself).
  const back = (to: string) => {
    if (trip.planningId) primeDecision(trip.planningId, enterStage(trip.planningId, 'decision'))
    go(to)
  }
  // Where the trip starts is its own row (Điểm xuất phát, OriginRow: typed in place); how it gets to the city is asked under Đến Đà Lạt.
  // Where the user sleeps is picked here, in the list that slides in from the right.
  const toLodging = () => setLodgingOpen(true)

  if (!trip.planningId)
    return (
      <>
        <Page narrow><Empty art={<ArtRoute />} title="Chưa có lịch trình" body="Bạn chọn nơi ở bước Lựa chọn rồi bấm Lập lịch để TripGuardian xếp chuyến đi nhé." action={<button type="button" className="tg-btn tg-btn--primary" onClick={() => go('/explore')}>Lựa chọn</button>} /></Page>
      </>
    )
  if (!view)
    return (
      <>
        <Page>
          {error ? <Empty art={<ArtRoute />} title="Chưa tải được lịch trình" body={error === BUSY_TEXT ? `${error} Mình sẽ tự thử lại sau ít giây.` : error} action={isStaleText(error)
            ? <button type="button" className="tg-btn tg-btn--primary" onClick={() => go('/trips')}>Về chuyến của tôi</button>
            : <button type="button" className="tg-btn tg-btn--primary" onClick={() => location.reload()}><Icon name="refresh" size={18} /> Thử lại</button>} /> : (
            <>
              <Busy text="Đang xếp lịch… chỗ nghỉ có thể đến sau ~10 giây" />
              <div className="tg-it-skel" aria-busy="true">
                {Array.from({ length: 3 }, (_, i) => <span key={i} className="tg-skel" style={{ height: 360, borderRadius: 22 }} />)}
              </div>
            </>
          )}
        </Page>
      </>
    )
  if (!view.variants.length)
    return (
      <>
        <Page narrow>
          <Empty art={<ArtRoute />} title="Chưa xếp được lịch" body={view.back_to_decision?.places.length ? `Vướng ở: ${view.back_to_decision.places.map((id) => info(id)?.name ?? id).join(', ')}. Bỏ hoặc đổi nơi này rồi xem lại.` : 'Các nơi đã chọn chưa đủ để xếp thành lịch trình.'} action={<button type="button" className="tg-btn tg-btn--primary" onClick={() => back('/explore')}>Chọn lại địa điểm</button>} />
          {view.warnings.length > 0 && <ul className="tg-notes">{view.warnings.map((w, i) => <li key={i}><Icon name="warn" size={14} /><span>{w.text}</span></li>)}</ul>}
        </Page>
      </>
    )

  const hasHotel = Boolean(view.state.lodging_touched && view.state.lodging_id)
  const pickVariant = async (id: string) => {
    if (id === view.state.chosen_variant) { setChanging(false); setScreen('overview'); return }
    if (view.state.chosen_variant && Object.keys(view.state.order_override ?? {}).length && pickAsk !== id) { setPickAsk(id); return }
    setPickAsk(null)
    if (await act({ type: 'pick_variant', id })) { setChanging(false); setDayIdx(null); setScreen('overview') }
  }
  if (!view.state.chosen_variant || changing) return (
    <>
      <Choose variants={view.variants} keepAll={view.keep_all} overload={view.overload} locked={view.state.locked} current={view.state.chosen_variant} busy={busy} hasHotel={hasHotel}
        onBack={() => back('/explore')} onHotel={toLodging} onPick={(id) => { void pickVariant(id) }} onCancel={view.state.chosen_variant ? () => setChanging(false) : undefined} />
      <Dialog.Root open={!!pickAsk} onOpenChange={(o) => { if (!o) setPickAsk(null) }}>
        <Dialog.Portal><Dialog.Overlay className="tg tg-overlay" /><Dialog.Content className="tg tg-it-dlg" aria-describedby={undefined}>
          <header><Dialog.Title>Dùng lịch của phương án này?</Dialog.Title><Dialog.Close className="tg-icon-btn" aria-label="Đóng"><Icon name="x" size={18} /></Dialog.Close></header>
          <p>Thứ tự ghé bạn đã sắp trong từng ngày sẽ được đặt lại theo phương án mới. Nơi bạn đã bỏ, đã đổi ngày hoặc đã khóa vẫn giữ nguyên.</p>
          <footer><button type="button" className="tg-btn tg-btn--ghost" onClick={() => setPickAsk(null)}>Quay lại</button><button type="button" className="tg-btn tg-btn--primary" disabled={busy} onClick={() => pickAsk && void pickVariant(pickAsk)}>Dùng phương án này</button></footer>
        </Dialog.Content></Dialog.Portal>
      </Dialog.Root>
    </>
  )

  const days = view.itinerary ?? variant?.itinerary ?? []
  const dayIdx = Math.min(picked ?? Math.max(0, days.findIndex((x) => visits(x).length > 0)), Math.max(0, days.length - 1))
  const d = days[dayIdx]
  const places = days.reduce((n, x) => n + visits(x).length, 0)
  const travel = view.travel_load ? view.travel_load.reduce((n, x) => n + x.travel_min, 0) : variant?.metrics.travel_min ?? 0
  const metrics = view.metrics ?? variant?.metrics
  const robustness = view.robustness ?? variant?.robustness
  const vehicle = trip.vehicle ? VEHICLE_LABEL[trip.vehicle].toLowerCase() : ''
  const lodgingName = view.lodging.candidates.find((c) => c.id === view.state.lodging_id)?.name ?? ((view.state.lodging_point?.text as string | undefined) || null)
  const editId = (trip.decisionId ?? trip.planningId) ?? '' // the journey a trip edit made from Lịch trình goes to
  const origin = trip.searchInput?.context.origin ?? null // where the trip starts: the way in and back is timed from here
  // Where the way in ends: the chosen lodging (a corpus place, or the user's own address); none yet -> the city centre
  const lp = view.state.lodging_point
  const lodgingAt = hasHotel ? (info(view.state.lodging_id!) ?? (typeof lp?.lat === 'number' && typeof lp?.lng === 'number' ? { lat: lp.lat, lng: lp.lng } : null)) : null
  const better = optimized?.status === 'accepted' && (optimized.changed ?? optimized.after < optimized.before)
  const planDropped = (variant?.dropped_by_plan ?? []).filter((x) => (view.state.plan_dropped ?? []).includes(x.place_id))
  const userDropped = view.state.dropped.filter((x) => !planDropped.some((p) => p.place_id === x.place_id))
  const droppedCount = planDropped.length + userDropped.length
  const warned = !!view.violations?.length || variant?.confirmable === false // a warning is never a gate: the user may confirm anyway
  const onConfirm = async () => { if (warned && !warnAsk) { setWarnAsk(true); return } setWarnAsk(false); setReview(true) }
  const finish = async () => { if (await confirm()) go('/done') }
  const openDay = (i: number) => { setDayIdx(i); setScreen('day') }
  const startSwap = (place: string | null) => { setSwapFor(place); setGhostFor(null); setPicker(true) }
  const ghostItems = (view.ghosts ?? []).filter((g) => g.day === dayIdx).flatMap((g) => g.items)
  const candidates = (() => {
    const base = candidatesOf(view, variant, days, swapFor)
    const inPlanNow = new Set(days.flatMap((x) => visits(x).map((it) => it.place_id!)))
    const fromGhost: Candidate[] = ghostItems.filter((g, i) => !inPlanNow.has(g.place_id) && !base.some((c) => c.id === g.place_id) && ghostItems.findIndex((x) => x.place_id === g.place_id) === i) // one row per place, though it fits several gaps
      .map((g) => ({ id: g.place_id, name: info(g.place_id)?.name ?? g.name, from: 'backup', why: `Hợp khoảng trống này · ≈ ${g.detour_min} phút đi thêm`, forThis: false, warnings: g.note ? [{ code: 'ghost', text: g.note } as never] : undefined }))
    const all = [...fromGhost, ...base]
    return ghostFor ? [...all.filter((c) => c.id === ghostFor), ...all.filter((c) => c.id !== ghostFor)] : all
  })()
  const pickCandidate = async (c: Candidate) => {
    if (!d) return
    const day = d.day - 1
    setPicker(false)
    await preview(swapFor ? { type: 'swap', place: swapFor, with: c.id } : c.from === 'backup' ? { type: 'add_from_backup', place: c.id, day } : { type: 'move_place', place: c.id, day })
  }

  const note = error
    ? <p className="tg-it-diff is-bad" role="alert"><Icon name="warn" size={15} />{error}</p>
    : diff && SCOPE_TEXT[diff.scope]
      ? <p className="tg-it-diff" role="status"><Icon name="bolt" size={15} />{SCOPE_TEXT[diff.scope]}<button type="button" disabled={busy} onClick={() => act({ type: 'undo' })}>Hoàn tác</button></p>
      : null
  const confirmButton = confirmed && !diff
    ? <span className="tg-it-confirmed" role="status"><Icon name="check" size={16} /> Kế hoạch đã chốt</span>
    : <button type="button" className="tg-btn tg-btn--primary" disabled={busy} onClick={onConfirm}>{confirmed ? 'Chốt lại thay đổi' : 'Chốt kế hoạch này'} <Icon name="arrow" size={18} /></button>

  const notices = (
    <div className="tg-it-notices">
      {!confirmed && editId && <TripDates id={editId} start={trip.startDate || null} days={trip.days} />}
      {eve.state && <EveBanner {...eve} state={eve.state} times={days.length ? { arrive: days[0].window[0], leave: days[days.length - 1].window[1], ...(days.length > 1 ? { start: days[1].window[0], end: days[0].window[1] } : {}) } : null} />}
      {view.warnings.filter((w) => w.code === 'restricted_place').map((w, i) => <div key={`rp${i}`} className="tg-it-note is-attention" role="status"><Icon name="warn" size={18} /><span>{w.text}</span></div>)}
      <LongTripWarning days={days.length} />
      {view.overload && <div className="tg-it-note is-attention" role="status"><Icon name="warn" size={18} /><b>{view.overload.text}</b><button type="button" className="tg-it-textbtn" onClick={() => setWhyOpen(true)}>Xem lý do <Icon name="chevronRight" size={14} /></button></div>}
      {better && !optimized.seen && (
        <div className="tg-it-note is-good" role="status"><Icon name="sparkle" size={20} /><div><b>Mình đã tìm được cách xếp tốt hơn</b><p>{optimized.before > optimized.after ? `Giảm khoảng ${fmtMin(optimized.before - optimized.after)} di chuyển` : 'Các ngày đều và đúng giờ đẹp hơn'} mà không đổi chỗ ở, nhịp độ hay nơi đã khóa.</p></div><button type="button" className="tg-btn tg-btn--primary tg-btn--sm" onClick={() => setOpt(true)}>Xem đề xuất</button></div>
      )}
      {warned && !view.violations?.length && <div className="tg-it-note is-attention" role="status"><Icon name="warn" size={18} /><span>Phương án này còn điểm chưa đạt yêu cầu. Bạn vẫn có thể chốt, hoặc chọn phương án khác và sửa lịch.</span></div>}
      {!!view.violations?.length && <div className="tg-it-note is-attention" role="status"><Icon name="warn" size={18} /><ul>{view.violations.map((v, i) => <li key={i}>{v.day !== null ? `Ngày ${v.day + 1} · ` : ''}{v.place_id ? `${info(v.place_id)?.name ?? v.place_id}: ` : ''}{VIOLATION[v.kind] ?? 'Lịch còn một điểm cần lưu ý.'}</li>)}</ul></div>}
    </div>
  )
  const delta = variant?.delta_vs_selection ? `So với danh sách đã chọn: ${variant.delta_vs_selection.places > 0 ? '+' : ''}${variant.delta_vs_selection.places} nơi · Di chuyển ${variant.delta_vs_selection.travel_min === null ? 'chưa so được' : `${variant.delta_vs_selection.travel_min > 0 ? '+' : ''}${variant.delta_vs_selection.travel_min} phút`} · Chi phí địa điểm đã biết ${variant.delta_vs_selection.cost_vnd === null ? 'chưa so được' : `${variant.delta_vs_selection.cost_vnd > 0 ? '+' : ''}${fmtVnd(variant.delta_vs_selection.cost_vnd)}`}` : null
  const sameAs = variant?.same_as?.length ? variant.same_as.map((id) => view.variants.find((v) => v.id === id)?.label ?? id).join(', ') : null

  const overviewFooter = (
    <div className="tg-it-foot">
      <div className="tg-it-foot__in">
        <div className="tg-it-foot__costs">
        <div className="tg-it-foot__cost">
          <span>Chi phí địa điểm đã biết</span><b>{metrics ? (metrics.cost_vnd ? `≈ ${fmtVnd(metrics.cost_vnd)}` : 'Chưa có giá') : '—'}</b><span>{variant?.lodging_budget ? "chưa gồm di chuyển" : "chưa gồm chỗ nghỉ, di chuyển"}</span>
          <button type="button" className="tg-it-textbtn" aria-label="Chi phí này gồm gì" onClick={() => setCostOpen(true)}><Icon name="info" size={16} /></button>
        </div>
        <LodgingCost budget={variant?.lodging_budget} />
        {rides.ready && (() => { const b = rides.chosen ?? rides.cheapest(); const t = b ? rides.total(b) : null; return t && b ? <div className="tg-it-foot__cost"><span>Gọi xe ({rides.brands[b].name})</span><b>{fmtRange(t.lo, t.hi)}</b><span>ước tính cả chuyến</span></div> : null })()}
        </div>
        <div className="tg-it-foot__acts">{confirmButton}<button type="button" className="tg-btn tg-btn--soft" onClick={() => openDay(dayIdx)}>Xem lịch từng ngày <Icon name="arrow" size={18} /></button></div>
      </div>
    </div>
  )
  // A place the user moved or a day they ordered themselves: ask before the search may change it (like pickAsk).
  const ownEdits = Object.keys(view.state.assignment ?? {}).length > 0 || Object.keys(view.state.order_override ?? {}).length > 0
  const runOptimize = async (scope: 'keep_mine' | 'all') => { setOptAsk(false); setOpt(true); await optimize(scope) }
  const dayFooter = (
    <div className="tg-it-status">
      <span>{places} nơi trong lịch{droppedCount > 0 ? ` · ${droppedCount} tạm bỏ` : ''}</span>
      <div>
        <button type="button" className="tg-btn tg-btn--ghost tg-btn--sm" disabled={busy} onClick={() => { if (ownEdits) setOptAsk(true); else void runOptimize('all') }}><Icon name="sparkle" size={15} /> {busy ? 'Đang xếp…' : 'Tối ưu lịch'}</button>
        {confirmButton}
      </div>
    </div>
  )
  const extras = (
    <>
      <Lodging onChange={toLodging} />
      <section className="tg-sidecard" aria-labelledby="tg-nt-h">
        <h2 id="tg-nt-h"><Icon name="info" size={18} /> Lưu ý cả chuyến</h2>
        {view.warnings.length === 0 && !(variant?.warnings.length) ? <p className="tg-faint">Chưa có lưu ý nào.</p> : <ul className="tg-notes">{[...view.warnings, ...(variant?.warnings ?? [])].slice(0, 6).map((w, i) => <li key={i}><Icon name="warn" size={14} /><span>{w.text}</span></li>)}</ul>}
      </section>
      {!!variant?.checklist?.length && (
        <section className="tg-sidecard" aria-labelledby="tg-cl-h">
          <h2 id="tg-cl-h"><Icon name="check" size={18} /> Chuẩn bị trước khi đi</h2>
          <ul className="tg-checklist">{variant.checklist.map((c, i) => <li key={i}><Icon name={c.kind === 'scam' ? 'warn' : 'check'} size={14} /><span><small className="tg-faint">Ngày {c.day} · </small>{c.text}</span></li>)}</ul>
        </section>
      )}
    </>
  )

  if (review) return (
    <Journey days={days} routes={routes} origin={origin?.text ?? null} lodging={hasHotel ? lodgingName : null} arriveHow={trip.searchInput?.context.frame?.arrive?.how ?? trip.searchInput?.context.arrival_mode} leaveHow={trip.searchInput?.context.frame?.leave?.how ?? trip.searchInput?.context.arrival_mode}
      travelMin={travel} warned={warned} busy={busy} error={error} confirmed={confirmed} onBack={() => setReview(false)} onFinish={() => { void finish() }} />
  )
  return (
    <>
      {peeking && !editPreview ? <div className="tg-it-toast"><p className="tg-it-diff" role="status"><span className="tg-dots"><i /><i /><i /></span>Đang xem trước thay đổi…</p></div>
        : note && <div className="tg-it-toast">{note}</div>}
      {fill.deck && fill.open && (trip.decisionId ?? trip.planningId) && <FillSheet id={(trip.decisionId ?? trip.planningId)!} deck={fill.deck} qid={fill.open} onClose={() => { fill.setOpen(null); fill.refresh() }} />}
      <AssistantFloat stage="planning" onOpenDay={(n) => openDay(Math.min(Math.max(0, n - 1), Math.max(0, days.length - 1)))} />
      {screen === 'overview' && <Overview onPlaces={() => { try { localStorage.setItem('tg.split', '1') } catch { /* the map opens closed */ } back('/explore') }} fill={fill.deck?.tabs.some((t) => t.qid !== 'arrival') ? <FillRows id={editId} deck={fill.deck} except="arrival" onOpen={fill.setOpen} onSaved={fill.refresh} /> : null}
        arrivalFill={fill.deck?.tabs.some((t) => t.qid === 'arrival') ? <FillRows id={editId} deck={fill.deck} only="arrival" onOpen={fill.setOpen} onSaved={fill.refresh} peek={(mode) => <WayPeek mode={mode} lat={origin?.lat} lng={origin?.lng} originText={origin?.text} date={days[0]?.date} destLat={lodgingAt?.lat} destLng={lodgingAt?.lng} people={trip.people} />} /> : null}
        origin={<OriginRow id={editId} current={origin?.text || null} />} lodgingGhost={<LodgingGhost />} days={days} variant={variant} robustness={robustness} summary={summary} travelMin={travel} visitMin={metrics?.visit_min ?? 0} droppedCount={droppedCount}
        lodgingName={lodgingName} hasHotel={hasHotel} wayIn={<WayIn lat={origin?.lat} lng={origin?.lng} originText={origin?.text} date={days[0]?.date} way="inbound" destLat={lodgingAt?.lat} destLng={lodgingAt?.lng} people={trip.people} />} wayOut={<WayIn lat={origin?.lat} lng={origin?.lng} originText={origin?.text} date={days[days.length - 1]?.date} way="outbound" destLat={lodgingAt?.lat} destLng={lodgingAt?.lng} people={trip.people} />}
        stayOffer={hasHotel ? <StayOffer fid={view.state.lodging_id} checkIn={days[0]?.date ?? null} nights={Math.max(1, days.length - 1)} /> : null} arriveHow={trip.searchInput?.context.frame?.arrive?.how ?? trip.searchInput?.context.arrival_mode} leaveHow={trip.searchInput?.context.frame?.leave?.how ?? trip.searchInput?.context.arrival_mode} notices={notices} footer={overviewFooter} delta={delta} sameAs={sameAs}
        after={view.keep_all ? <KeepAll variant={view.keep_all} busy={busy} onPick={(id) => act({ type: 'pick_variant', id })} /> : null} onDay={openDay} onChangeVariant={() => setChanging(true)} onHotel={toLodging}
        onDropped={() => setDroppedOpen(true)} onWhy={() => setWhyOpen(true)} onOpen={openPlace} />}
      {screen === 'day' && d && <DayView days={days} dayIdx={dayIdx} week={Math.floor(dayIdx / 7)} onDay={setDayIdx} busy={busy} locked={view.state.locked}
        durationRange={view.duration_range} durationOverrides={view.state.visit_duration_override ?? {}} cond={view.day_conditions?.find((c) => c.day === d.day)} tips={view.crowd_tips ?? []}
        vehicle={vehicle} rides={rides} extras={extras} footer={dayFooter} summary={variant ? wayName(variant) : 'Lịch trình'} route={routes?.find((r) => r.day === d.day) ?? null}
        ghosts={view.ghosts ?? []} onAddGhost={(place) => { setSwapFor(null); setGhostFor(place); setPicker(true) }}
        side={picker && d ? <Find day={d} replacing={swapFor} candidates={candidates} inPlan={new Set(days.flatMap((x) => visits(x).map((it) => it.place_id!)))} people={trip.people} busy={busy || replan.busy}
          onClose={() => setPicker(false)} onPick={(c) => { void pickCandidate(c) }} onAddOutside={(place) => { void replan.run([{ kind: 'select', place }]) }} onOpen={openPlace} /> : null}
        onBack={() => setScreen('overview')} onOpen={openPlace} onSwap={startSwap} onDrop={setDropAsk}
        onMoveDay={(place, day) => { void act({ type: 'move_place', place, day }) }} onReorder={(day, order) => act({ type: 'reorder', day, order })}
        onDuration={(place, minutes) => { void preview({ type: 'set_visit_duration', place, minutes }) }} />}
      <LodgingPicker open={lodgingOpen} onClose={() => setLodgingOpen(false)} />

      <Dialog.Root open={optAsk} onOpenChange={(o) => { if (!o) setOptAsk(false) }}>
        <Dialog.Portal><Dialog.Overlay className="tg tg-overlay" /><Dialog.Content className="tg tg-it-dlg" aria-describedby={undefined}>
          <header><Dialog.Title>Tối ưu cả những chỗ bạn đã tự sắp?</Dialog.Title><Dialog.Close className="tg-icon-btn" aria-label="Đóng"><Icon name="x" size={18} /></Dialog.Close></header>
          <p>Bạn đã tự đổi ngày hoặc tự sắp thứ tự ở một số chỗ. Mình có thể chỉ xếp lại phần còn lại, hoặc xếp lại cả lịch cho ít đi xe nhất. Nơi đã khóa luôn giữ nguyên, và bạn luôn quay lại được lịch cũ.</p>
          <footer><button type="button" className="tg-btn tg-btn--ghost" disabled={busy} onClick={() => void runOptimize('keep_mine')}>Giữ chỗ tôi đã sắp</button><button type="button" className="tg-btn tg-btn--primary" disabled={busy} onClick={() => void runOptimize('all')}>Tối ưu cả lịch</button></footer>
        </Dialog.Content></Dialog.Portal>
      </Dialog.Root>
      <Optimize open={opt} onClose={() => { setOpt(false); if (trip.planningId && optimized) setOptimized(trip.planningId, { ...optimized, seen: true }) }} onUndo={async () => { await act({ type: 'undo' }); if (trip.planningId) setOptimized(trip.planningId, null); setOpt(false) }} busy={busy} />

      <Dialog.Root open={!!editPreview} onOpenChange={(open) => { if (!open) dismissPreview() }}>
        <Dialog.Portal><Dialog.Overlay className="tg tg-overlay" /><Dialog.Content className="tg tg-listpanel tg-edit-preview" aria-describedby={undefined}>
          <header><Dialog.Title>Xem trước thay đổi</Dialog.Title><Dialog.Close className="tg-icon-btn" aria-label="Đóng"><Icon name="x" size={18} /></Dialog.Close></header>
          {editPreview?.action.type === 'set_visit_duration' && <p className="tg-it-note is-attention" role="status"><Icon name="warn" size={16} /> Thay thời lượng có thể đổi giờ ghé, bữa ăn và thời gian đệm. Kiểm tra lịch bên dưới trước khi áp dụng.</p>}
          <p>Đi lại {editPreview?.delta.travel_min == null ? 'chưa so được' : `${editPreview.delta.travel_min > 0 ? '+' : ''}${fmtMin(editPreview.delta.travel_min)}`} · Tham quan {editPreview?.delta.visit_min == null ? 'chưa so được' : `${editPreview.delta.visit_min > 0 ? '+' : ''}${fmtMin(editPreview.delta.visit_min)}`} · Số nơi {editPreview?.delta.places ?? '—'}</p>
          {!!editPreview?.violations.length && <ul className="tg-notes">{editPreview.violations.map((v, i) => <li key={i}><Icon name="warn" size={14} /><span>{VIOLATION[v.kind] ?? 'Lịch còn xung đột cần xử lý.'}</span></li>)}</ul>}
          {editPreview?.action.type === 'set_visit_duration' && editPreview.view.itinerary?.map(day => <section key={day.day} className="tg-backup"><b>Ngày {day.day}</b>{day.items.filter(item => item.kind === 'visit' || item.kind === 'meal_free').map((item, i) => <span key={i}>{item.start}–{item.end} · {item.kind === 'meal_free' ? MEAL_LABEL[item.name ?? ''] : item.name}</span>)}</section>)}
          {!!editPreview?.make_room.length && <div className="tg-backup"><b>Cách tạo chỗ trống</b><span>Chọn một đề xuất đã được kiểm tra; máy chủ không tự bỏ nơi.</span>{editPreview.make_room.map((a: Action, i: number) => <button key={i} type="button" className="tg-btn tg-btn--soft tg-btn--sm" disabled={busy} onClick={async () => await preview(a)}>Xem cách này</button>)}</div>}
          {!editPreview?.confirmable && <p className="tg-faint">Lịch sau thay đổi chưa thể chốt. Máy chủ sẽ kiểm tra lại khi chốt.</p>}
          <footer><button type="button" className="tg-btn tg-btn--ghost" onClick={() => dismissPreview()}>Để sau</button><button type="button" className="tg-btn tg-btn--primary" disabled={busy || !editPreview || (editPreview.action.type === 'set_visit_duration' && !editPreview.confirmable)} onClick={async () => { if (!editPreview) return; await act({ ...editPreview.action, _preview_token: editPreview.token }); dismissPreview(); }}>Áp dụng thay đổi đã xem</button></footer>
        </Dialog.Content></Dialog.Portal>
      </Dialog.Root>

      <Dialog.Root open={warnAsk} onOpenChange={(o) => { if (!o) setWarnAsk(false) }}>
        <Dialog.Portal><Dialog.Overlay className="tg tg-overlay" /><Dialog.Content className="tg tg-it-dlg" aria-describedby={undefined}>
          <header><Dialog.Title>Chốt kế hoạch còn cảnh báo?</Dialog.Title><Dialog.Close className="tg-icon-btn" aria-label="Đóng"><Icon name="x" size={18} /></Dialog.Close></header>
          <p>Mình chỉ báo để bạn biết, quyết định là của bạn.</p>
          {!!view.violations?.length && <ul className="tg-notes">{view.violations.map((v, i) => <li key={i}><Icon name="warn" size={14} /><span>{v.day !== null ? `Ngày ${v.day + 1} · ` : ''}{v.place_id ? `${info(v.place_id)?.name ?? v.place_id}: ` : ''}{VIOLATION[v.kind] ?? 'Lịch còn một điểm cần lưu ý.'}</span></li>)}</ul>}
          <footer><button type="button" className="tg-btn tg-btn--ghost" onClick={() => setWarnAsk(false)}>Xem lại lịch</button><button type="button" className="tg-btn tg-btn--primary" disabled={busy} onClick={() => { void onConfirm() }}>Vẫn chốt</button></footer>
        </Dialog.Content></Dialog.Portal>
      </Dialog.Root>

      <Dialog.Root open={!!dropAsk} onOpenChange={(o) => { if (!o) setDropAsk(null) }}>
        <Dialog.Portal><Dialog.Overlay className="tg tg-overlay" /><Dialog.Content className="tg tg-it-dlg" aria-describedby={undefined}>
          <header><Dialog.Title>Bỏ {dropAsk ? placeName(dropAsk) : ''} khỏi ngày {d?.day}?</Dialog.Title><Dialog.Close className="tg-icon-btn" aria-label="Đóng"><Icon name="x" size={18} /></Dialog.Close></header>
          <p>Nơi này vẫn nằm trong danh sách tạm bỏ để bạn có thể thêm lại. Lịch ngày này được xếp lại, và bạn hoàn tác được.</p>
          <footer><button type="button" className="tg-btn tg-btn--ghost" onClick={() => setDropAsk(null)}>Giữ lại</button><button type="button" className="tg-btn tg-btn--primary" disabled={busy} onClick={async () => { if (dropAsk) await act({ type: 'drop_place', place: dropAsk }); setDropAsk(null) }}>Tạm bỏ nơi này</button></footer>
        </Dialog.Content></Dialog.Portal>
      </Dialog.Root>

      <Dialog.Root open={droppedOpen} onOpenChange={setDroppedOpen}>
        <Dialog.Portal><Dialog.Overlay className="tg tg-overlay" /><Dialog.Content className="tg tg-it-dlg" aria-describedby={undefined}>
          <header><Dialog.Title>{droppedCount} nơi tạm bỏ</Dialog.Title><Dialog.Close className="tg-icon-btn" aria-label="Đóng"><Icon name="x" size={18} /></Dialog.Close></header>
          <ul className="tg-it-droplist">
            {planDropped.map((x) => <li key={x.place_id}><div><b>{x.name}</b><small>{x.text}</small></div></li>)}
            {userDropped.map((x) => <li key={x.place_id}><div><b>{placeName(x.place_id)}</b><small>Bạn đã tạm bỏ nơi này</small></div></li>)}
          </ul>
        </Dialog.Content></Dialog.Portal>
      </Dialog.Root>

      <Dialog.Root open={whyOpen} onOpenChange={setWhyOpen}>
        <Dialog.Portal><Dialog.Overlay className="tg tg-overlay" /><Dialog.Content className="tg tg-it-dlg" aria-describedby={undefined}>
          <header><Dialog.Title>Vì sao lịch như vậy</Dialog.Title><Dialog.Close className="tg-icon-btn" aria-label="Đóng"><Icon name="x" size={18} /></Dialog.Close></header>
          {view.overload && <section className="tg-it-why">
            <h3>{view.overload.text}</h3>
            <p>Cần khoảng {fmtMin(view.overload.needed)}, lịch có khoảng {fmtMin(view.overload.available)} cho {view.overload.selection_places} nơi.{view.overload.estimated ? ' Đây là ước lượng.' : ''}</p>
            {!!view.overload.leftover_reasons?.length && <ul>{view.overload.leftover_reasons.map((x) => <li key={x.place_id}><b>{x.name}</b>: {LEFTOVER[x.reason]}</li>)}</ul>}
          </section>}
          {!!robustness?.reasons.length && <section className="tg-it-why">
            <h3>Lịch {ROBUST_TAG[robustness.level]?.toLowerCase() ?? robustness.label.toLowerCase()}</h3>
            <ul>{robustness.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>
          </section>}
        </Dialog.Content></Dialog.Portal>
      </Dialog.Root>

      <Dialog.Root open={costOpen} onOpenChange={setCostOpen}>
        <Dialog.Portal><Dialog.Overlay className="tg tg-overlay" /><Dialog.Content className="tg tg-it-dlg" aria-describedby={undefined}>
          <header><Dialog.Title>Chi phí tham khảo</Dialog.Title><Dialog.Close className="tg-icon-btn" aria-label="Đóng"><Icon name="x" size={18} /></Dialog.Close></header>
          <p><b>{metrics?.cost_vnd ? `≈ ${fmtVnd(metrics.cost_vnd)}` : 'Chưa có giá'}</b> cho các nơi đã có giá trong lịch. Giá từng nơi là khoảng giá đã biết, chưa phải báo giá.</p>
          <ul className="tg-it-costlist">
            {!!metrics && metrics.cost_unknown > 0 && <li>{metrics.cost_unknown} nơi chưa có giá nên chưa tính.</li>}
            {!!metrics?.meal_cost_unknown && <li>{metrics.meal_cost_unknown} bữa tự chọn chưa tính giá.</li>}
            {metrics?.transport_cost_vnd == null && <li>Chưa tính chi phí di chuyển.</li>}
            {!!metrics?.extras_max_vnd && <li>Có thể thêm tới {fmtVnd(metrics.extras_max_vnd)} cho trò chơi, thuê đồ.</li>}
            <li>{variant?.lodging_budget?.total_vnd != null ? `Chỗ nghỉ tính riêng: ≈ ${fmtVnd(variant.lodging_budget.total_vnd)} (${lodgingBasis(variant.lodging_budget)}).` : 'Chưa gồm chỗ nghỉ.'}</li>
            <li>Chưa gồm chuyến đến, về.</li>
          </ul>
          {variant && <p className="tg-faint">Phương án {wayName(variant)}: {costText(variant)}.</p>}
        </Dialog.Content></Dialog.Portal>
      </Dialog.Root>
    </>
  )
}
