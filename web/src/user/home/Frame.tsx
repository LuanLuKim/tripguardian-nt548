import { useEffect, useState, type CSSProperties, type ReactNode } from 'react'
import { signOut, useAccount } from '../account'
import { tripSummaries } from '../pd/api'
import { useDecision } from '../pd/decision'
import { loadLibrary, useUi } from '../store'
import { hasTrip, STEPS, stepOf, useTrip, type StepId } from '../trip'
import { go, Link, PlacePhoto } from '../ui/common'
import { Icon, Logo, type IconName } from '../ui/icons'
import { useFlowNav } from '../ui/Shell'
import { Who } from './Who'
import { HomeDialogs, openCreate } from './dialogs'

// The app frame of every page that is not a step of the trip flow (docs/design/mock/designs/homepage):
// a sidebar card | the page (friends and your activity drop down from the icon in its top corner), and the trip in progress along the bottom while it is not yet confirmed.
export function Frame({ path, children }: { path: string; children: ReactNode }) {
  const account = useAccount()
  useEffect(() => { if (account && !account.needs_consent) void loadLibrary() }, [account?.id]) // eslint-disable-line react-hooks/exhaustive-deps
  const bar = useUnfinishedTrip()
  return (
    <div className="tg-home tg-hf">
      <div className={`tg-hf__app ${bar ? 'has-bar' : ''}`}>
        <div className="tg-hf__ws">
          <Sidebar path={path} />
          <div className="tg-hf__mid">
            {children}
            {path !== '' && <Who compact className="tg-hf__corner" />}
          </div>
        </div>
        {bar && <JourneyBar />}
        {path === '' && <button type="button" className="tg-hf__new" data-tour="new-trip" onClick={() => openCreate()}><Icon name="plus" size={20} />Tạo chuyến đi</button>}
      </div>
      <HomeDialogs />
    </div>
  )
}

// The bar is the trip being made: it shows only while the server lists this trip and its itinerary is not confirmed.
// A trip the server does not know (cleared, or the server not answering) is not a trip the user has: no bar.
function useUnfinishedTrip() {
  const { trip } = useTrip()
  const [show, setShow] = useState(false)
  useEffect(() => {
    const id = trip.journeyId
    if (!hasTrip(trip) || !id) { setShow(false); return }
    let alive = true
    tripSummaries().then((l) => { if (alive) setShow(l.some((t) => t.id === id && !t.confirmed)) }, () => { if (alive) setShow(false) })
    return () => { alive = false }
  }, [trip.journeyId, trip.decisionId, trip.planningId]) // eslint-disable-line react-hooks/exhaustive-deps
  return show
}

const NAV: { to: string; label: string; icon: IconName }[] = [
  { to: '/', label: 'Dành cho bạn', icon: 'home' },
  { to: '/trips', label: 'Chuyến của tôi', icon: 'map' },
  { to: '/posts', label: 'Bài viết', icon: 'article' },
  { to: '/saved', label: 'Đã lưu', icon: 'heart' },
  { to: '/recent', label: 'Đã xem gần đây', icon: 'clock' },
]
// The three steps of a trip, on the screens of the trip flow only (the chat, Lựa chọn, place pages, Lịch trình, Hoàn tất):
// the user flips between them at once. Pages of the frame (home, trips, saved…) do not show them; the bar at the bottom leads back.
const FLOW: { id: StepId; label: string; icon: IconName }[] = [
  { id: 'understand', label: 'Trò chuyện', icon: 'chat' },
  { id: 'explore', label: 'Lựa chọn', icon: 'grid' },
  { id: 'plan', label: 'Lịch trình', icon: 'calendar' },
]
const FLOW_PATHS = ['/understand', '/explore', '/plan', '/done']
const onStep = (path: string, id: StepId) => (id === 'understand' ? path === '/understand' : id === 'explore' ? path.startsWith('/explore') : path === '/plan' || path === '/done')

const ACCOUNT_NAV: { to: string; label: string; icon: IconName }[] = [
  { to: '/profile', label: 'Cài đặt', icon: 'settings' },
  { to: '/support', label: 'Hỗ trợ', icon: 'info' },
]

// The same sidebar beside the screens of the trip flow (Lựa chọn, place pages, Lịch trình, Hoàn tất), so it never disappears after the homepage.
export function FlowSide({ path }: { path: string }) {
  const account = useAccount()
  useEffect(() => { if (account && !account.needs_consent) void loadLibrary() }, [account?.id]) // eslint-disable-line react-hooks/exhaustive-deps
  return <div className="tg-home tg-flowside"><Sidebar path={path} /></div>
}

// The sidebar is a slim rail of icons (after Pinterest's): the name of each button shows as a tooltip on hover or focus.
// Three blocks (new trip · places and trips · settings and support), the logo above them and sign-out alone at the bottom.
export function Sidebar({ path }: { path: string }) {
  const saved = useUi((u) => u.saved.length)
  const account = useAccount()
  const guest = !!account?.guest
  const { trip } = useTrip()
  const flow = useFlowNav(path)
  const item = (n: { to: string; label: string; icon: IconName }) => {
    const on = n.to === '/' ? path === '' : path.startsWith(n.to)
    return (
      <li key={n.to}>
        <Link to={n.to} className={`tg-hf__item ${on ? 'is-on' : ''}`} data-tour={`nav-${n.to === '/' ? 'home' : n.to.slice(1)}`} data-tip={n.label} aria-label={n.label} aria-current={on ? 'page' : undefined}>
          <Icon name={n.icon} size={26} />
          {n.to === '/saved' && saved > 0 && <b className="tg-hf__count" aria-label={`${saved} mục`}>{saved > 99 ? '99+' : saved}</b>}
        </Link>
      </li>
    )
  }
  return (
    <nav className="tg-hf__side" aria-label="Điều hướng chính">
      <Link to="/" className="tg-hf__logo" aria-label="Về Khám phá"><Logo size={19} /></Link>
      <div className="tg-hf__mids">
        {FLOW_PATHS.some((x) => path.startsWith(x)) && (
          <ul className="tg-hf__blk tg-hf__nav" aria-label="Chuyến đang lập">
            {FLOW.map((f) => {
              const on = onStep(path, f.id)
              // A step the trip has not reached yet cannot open: Lựa chọn needs what the chat handed on, Lịch trình needs a pick.
              const off = !on && ((f.id === 'explore' && !hasTrip(trip)) || (f.id === 'plan' && !trip.decisionId && !trip.planningId))
              const tip = off ? `${f.label} · kể chuyến đi trước đã` : f.label
              return (
                <li key={f.id}>
                  <button type="button" className={`tg-hf__item ${on ? 'is-on' : ''}`} data-tour={`nav-${f.id}`} data-tip={tip} aria-label={tip} aria-current={on ? 'page' : undefined} aria-disabled={off || undefined} aria-busy={flow.going === f.id || undefined} onClick={() => { if (!off && !on) void flow.goTo(f.id) }}>
                    <Icon name={f.icon} size={26} />
                  </button>
                </li>
              )
            })}
          </ul>
        )}
        <ul className="tg-hf__blk tg-hf__nav">{NAV.map(item)}</ul>
        <ul className="tg-hf__blk tg-hf__nav">{ACCOUNT_NAV.map(item)}</ul>
      </div>
      <div className="tg-hf__foot">
        {guest
          ? <Link to="/login" className="tg-hf__item" data-tip="Đăng nhập" aria-label="Đăng nhập"><Icon name="user" size={26} /></Link>
          : <button type="button" className="tg-hf__item" data-tip="Đăng xuất" aria-label="Đăng xuất" onClick={() => { void signOut() }}><Icon name="logout" size={26} /></button>}
      </div>
    </nav>
  )
}

function JourneyBar() {
  const { trip } = useTrip()
  const { view } = useDecision()
  const step = stepOf(trip)
  const ctx = trip.searchInput?.context
  const selected = view?.selected ?? trip.selected
  return (
    <footer className="tg-hf__bar" aria-label="Chuyến đang lập" style={{ '--tg-prog': `${((step.index + 0.5) / STEPS.length) * 100}%` } as CSSProperties}>
      <button type="button" className="tg-hf__trip" onClick={() => go(step.path)}>
        <span className="tg-hf__ring">{selected[0] ? <PlacePhoto id={selected[0]} /> : <img src="/img/home/lake.jpg" alt="" />}</span>
        <span><strong>Đà Lạt{ctx?.days ? ` ${ctx.days} ngày` : ''}</strong><small>{[ctx?.people ? `${ctx.people} người` : null, `${selected.length} nơi đã chọn`, `Đang ở ${step.label}`].filter(Boolean).join(' · ')}</small></span>
      </button>
      <span className="tg-hf__bact">
        <Link to="/saved" className="tg-hb-icon" aria-label="Xem mục đã lưu"><Icon name="heart" size={16} /></Link>
        <button type="button" className="tg-hb-go" onClick={() => go(step.path)}>Đi tiếp<Icon name="arrow" size={15} /></button>
      </span>
    </footer>
  )
}
