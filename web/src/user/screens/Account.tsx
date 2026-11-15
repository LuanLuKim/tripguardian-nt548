import { useEffect, useState } from 'react'
import { deleteAccount, refreshAccount, signOut, updateProfile, uploadAvatar, useAccount, type Companions, type Me, type Mobility } from '../account'
import { calendarDisconnect } from '../today'
import { track } from '../events'
import { enablePush, notificationLabel, loadPrefs, pushSupported, savePrefs, type Prefs } from '../notify'
import { placeById, useDetail } from '../../data/store'
import { featureLabel } from '../../data/labels'
import { dateRange, info } from '../lib'
import { deleteTrip, tripSummaries } from '../pd/api'
import { useDecision } from '../pd/decision'
import { useFriends } from '../social'
import type { TripSummary } from '../pd/types'
import { toast, toggleSaved, useUi } from '../store'
import { useTrip } from '../trip'
import { ArtCup, ArtHills, ArtRoute, Busy, Empty, go, Link, PlacePhoto } from '../ui/common'
import { Icon, type IconName } from '../ui/icons'
import { Page, useTitle } from '../ui/Shell'
import { openPlace } from '../ui/PlaceSheet'
import { openShare } from '../home/dialogs'
import { GuestNotice } from './Guest'
import { TourButton } from '../tour'

type Kind = 'planning' | 'confirmed' | 'done'
const STATUS: Record<Kind, string> = { planning: 'Đang lên kế hoạch · chưa chốt lịch', confirmed: 'Đã chốt', done: 'Đã đi' }

// A trip that went on to choosing places or to a schedule but is not locked yet is a plan in progress; a chat that never got
// that far stays in the chat history.
const inProgress = (t: TripSummary) => !t.confirmed && t.stage !== 'trip'
function kindOf(t: TripSummary): Kind {
  if (inProgress(t)) return 'planning'
  if (!t.start_date) return 'confirmed'
  const end = new Date(t.start_date + 'T00:00')
  end.setDate(end.getDate() + (t.days ?? 1))
  return end < new Date() ? 'done' : 'confirmed'
}

// Journeys of the signed-in account; the server answers with one summary line each.
export function Trips() {
  useTitle('Chuyến của tôi')
  const { trip, dispatch } = useTrip()
  const [list, setList] = useState<TripSummary[] | null>(null)
  const [err, setErr] = useState(false)
  const [tab, setTab] = useState<Kind>('planning')
  const account = useAccount()
  const member = !!account && !account.guest
  useEffect(() => {
    tripSummaries().then((all) => {
      const l = all.filter((t) => t.confirmed || inProgress(t))
      setList(l)
      const has = (k: Kind) => l.some((t) => kindOf(t) === k)
      setTab(has('planning') ? 'planning' : has('confirmed') ? 'confirmed' : has('done') ? 'done' : 'confirmed')
    }, () => setErr(true))
  }, [])
  const open = (t: TripSummary, to: string) => {
    dispatch({ type: 'reset' })
    // A plan in progress opens at the step it stopped on; a locked one has all its steps.
    const locked = t.confirmed
    dispatch({ type: 'set', patch: { journeyId: t.id, decisionId: t.id, planningId: locked || t.stage === 'planning' ? t.id : null } })
    go(to)
  }
  const [asking, setAsking] = useState<string | null>(null) // the trip waiting for the user's yes to be removed
  const [removing, setRemoving] = useState(false)
  const remove = (t: TripSummary) => {
    setRemoving(true)
    deleteTrip(t.id).then(() => {
      setList((l) => l && l.filter((x) => x.id !== t.id))
      try { localStorage.removeItem(`tg.journey.pending.${t.id}`) } catch { /* nothing stored */ }
      if (trip.journeyId === t.id) dispatch({ type: 'reset' })
      setAsking(null)
      toast('Đã xóa chuyến')
    }, () => toast('Chưa xóa được, bạn thử lại nhé')).finally(() => setRemoving(false))
  }
  const shown = (list ?? []).filter((t) => kindOf(t) === tab)
  return (
    <Page>
      <GuestNotice />
      <header className="tg-head" data-tour="page-head"><div><p className="tg-kicker">Chuyến của tôi</p><h1>Chuyến đi của bạn</h1><p>Các chuyến của tài khoản này, mở được trên mọi máy.</p></div></header>
      <div className="tg-tabs" role="tablist" aria-label="Trạng thái chuyến">
        {([['planning', 'Đang lên kế hoạch'], ['confirmed', 'Sắp đi'], ['done', 'Đã hoàn thành']] as const).map(([k, l]) => <button key={k} type="button" role="tab" aria-selected={tab === k} className="tg-tab" onClick={() => setTab(k)}>{l}{list && <b>{list.filter((t) => kindOf(t) === k).length}</b>}</button>)}
      </div>
      {err ? <Empty art={<ArtHills />} title="Chưa tải được danh sách chuyến" body="Máy chủ hành trình chưa trả lời. Thử lại sau ít phút." action={<button type="button" className="tg-btn tg-btn--primary" onClick={() => location.reload()}>Thử lại</button>} />
        : !list ? <Busy text="Đang tải các chuyến…" />
        : shown.length === 0 ? (
          <Empty art={tab === 'done' ? <ArtCup /> : <ArtRoute />} title={tab === 'planning' ? 'Chưa có chuyến nào đang lên kế hoạch' : tab === 'confirmed' ? 'Chưa có chuyến nào có lịch trình' : 'Chưa có chuyến nào hoàn thành'} body={tab === 'done' ? 'Đi xong chuyến đầu, nó sẽ nằm ở đây.' : tab === 'planning' ? 'Chuyến đã chọn nơi hoặc đã xếp lịch nhưng chưa chốt sẽ nằm ở đây. Các cuộc trò chuyện chưa chọn nơi vẫn ở Lịch sử chat.' : 'Chốt lịch một chuyến, nó sẽ nằm ở đây. Các cuộc trò chuyện dang dở vẫn ở Lịch sử chat.'} action={<button type="button" className="tg-btn tg-btn--primary" onClick={() => go('/')}>Về Khám phá</button>} />
        ) : (
          <div className="tg-trips">
            {shown.map((t) => {
              const k = kindOf(t)
              return (
                <article key={t.id} className="tg-trip">
                  {t.places[0] ? <PlacePhoto id={t.places[0]} className="tg-trip__ph" /> : <div className="tg-trip__ph tg-hero__img" aria-hidden="true" />}
                  <div className="tg-trip__body">
                    <span className={`tg-tag ${k === 'planning' ? 'is-planning' : ''}`}>{k === 'planning' && <Icon name="edit" size={12} />}{STATUS[k]}</span>
                    <h2>Đà Lạt{t.days ? ` ${t.days} ngày` : ''}</h2>
                    <p className="tg-mono tg-muted">{[dateRange(t.start_date, t.days) ?? 'Chưa chọn ngày', t.people ? `${t.people} người` : null, `${t.places.length} nơi`].filter(Boolean).join(' · ')}</p>
                    <div className="tg-trip__act">
                      {k === 'planning' && <button type="button" className="tg-btn tg-btn--primary tg-btn--sm" onClick={() => open(t, t.stage === 'planning' ? '/plan' : '/explore')}>Tiếp tục lên kế hoạch</button>}
                      {k === 'confirmed' && <><button type="button" className="tg-btn tg-btn--primary tg-btn--sm" onClick={() => open(t, '/plan')}>Xem lịch</button><button type="button" className="tg-link" onClick={() => open(t, '/plan')}>Sửa lại</button></>}
                      {k === 'done' && <><button type="button" className="tg-btn tg-btn--ghost tg-btn--sm" onClick={() => open(t, '/plan')}>Xem lại lịch</button><button type="button" className="tg-link" onClick={() => open(t, '/done')}>Phản hồi</button></>}
                      {member && <button type="button" className="tg-link" onClick={() => openShare(t)}><Icon name="send" size={14} /> Gửi cho bạn bè</button>}
                      {asking === t.id ? (
                        <span className="tg-trip__ask" role="alertdialog" aria-label="Xóa chuyến này?">Xóa chuyến này?<button type="button" className="tg-btn tg-btn--sm tg-del__yes" disabled={removing} onClick={() => remove(t)}>{removing ? 'Đang xóa…' : 'Xóa'}</button><button type="button" className="tg-link" disabled={removing} onClick={() => setAsking(null)}>Giữ lại</button></span>
                      ) : <button type="button" className="tg-trip__del" aria-label="Xóa chuyến này" title="Xóa chuyến này" onClick={() => setAsking(t.id)}><Icon name="trash" size={15} /></button>}
                    </div>
                  </div>
                </article>
              )
            })}
          </div>
        )}
    </Page>
  )
}

const GROUPS: [string, string][] = [['all', 'Tất cả'], ['sight', 'Tham quan & thiên nhiên'], ['food', 'Ăn uống & cà phê'], ['shop', 'Mua sắm']]

// Up to three things many people vouch for at this place, as short tags: served features (verified, 2+ voices) that
// read as a plus. Anything that is a downside or a neutral fact is left out.
const PLUS = new Set(['scenic_view', 'cloud_hunting', 'sunset_view', 'photo_spot', 'nature', 'flower_garden', 'heritage_architecture', 'cozy_decor', 'laptop_friendly', 'long_stay_chill', 'live_music', 'adventure_activity', 'hiking', 'animals', 'local_specialty_food', 'hands_on_workshop', 'pick_your_own', 'cultural_show', 'camping', 'spacious', 'outdoor_seating', 'kids_play_area', 'rest_benches', 'heater', 'hot_water', 'vegetarian_options'])
const GOOD: Record<string, string> = { 'food_quality:good': 'Đồ ăn ngon', 'drink_quality:good': 'Đồ uống ngon', 'service_attitude:good': 'Phục vụ tốt', 'service_quality:good': 'Phục vụ tốt', 'value_for_money:good': 'Đáng tiền', 'cleanliness:clean': 'Sạch sẽ', 'noise:quiet': 'Yên tĩnh' }
function tagsOf(id: string): string[] {
  const p = placeById(id)
  if (!p) return []
  const tags = p.features.filter((f) => f.status === 'VERIFIED' && f.n >= 2).sort((a, b) => b.n - a.n)
    .map((f) => (f.value === 'present' && PLUS.has(f.id) ? featureLabel(f.id) : GOOD[`${f.id}:${f.value}`]))
    .filter((t): t is string => !!t)
  return [...new Set(tags)].slice(0, 3)
}

export function Saved() {
  useTitle('Đã lưu')
  const saved = useUi((u) => u.saved)
  const { view, act, busy } = useDecision()
  const [f, setF] = useState('all')
  useDetail(saved) // the tags come from the evidence, which lands after the first paint
  const cards = new Map(view?.groups.flatMap((g) => g.cards).map((c) => [c.id, c]) ?? [])
  const items = saved.filter((id) => f === 'all' || info(id)?.group === f)
  const count = (k: string) => saved.filter((id) => k === 'all' || info(id)?.group === k).length
  const unsave = (id: string, name?: string) => { toggleSaved(id, name); toast('Đã xóa khỏi yêu thích') }
  return (
    <Page>
      <header className="tg-head" data-tour="page-head"><div><p className="tg-kicker">Đã lưu</p><h1>Địa điểm bạn đã lưu</h1><p>Lưu theo tài khoản, mở được trên mọi máy. Nơi đã lưu không tự vào lịch; thêm vào chuyến khi cần.</p></div></header>
      <div className="tg-tabs" role="tablist" aria-label="Nhóm">
        {GROUPS.map(([k, l]) => <button key={k} type="button" role="tab" aria-selected={f === k} className="tg-tab" onClick={() => setF(k)}>{l}<b>{count(k)}</b></button>)}
      </div>
      {items.length === 0 ? <Empty art={<ArtCup />} title="Chưa lưu nơi nào" body="Bấm trái tim trên thẻ địa điểm để lưu lại, rồi thêm vào chuyến khi cần." action={<button type="button" className="tg-btn tg-btn--primary" onClick={() => go(view ? '/explore' : '/')}>{view ? 'Xem gợi ý' : 'Về Khám phá'}</button>} /> : (
        <ul className="tg-rc-grid tg-rc-grid--saved">
          {items.map((id) => {
            const p = info(id)
            const c = cards.get(id)
            return (
              <li key={id} className="tg-rc-wrap">
                <button type="button" className="tg-rc" onClick={(e) => openPlace(id, e.currentTarget.querySelector('figure'))}>
                  <PlacePhoto id={id} name={p?.name} />
                  <span className="tg-rc__shade" aria-hidden="true" />
                  {p?.category && <span className="tg-rc__time">{p.category}</span>}
                  <span className="tg-rc__b">
                    <b>{p?.name ?? 'Nơi không còn trong dữ liệu'}</b>
                    <small>{[p?.area, tagsOf(id)[0]].filter(Boolean).join(' · ')}</small>
                  </span>
                  {p?.rating ? <span className="tg-rc__star">★ {p.rating.toFixed(1)}</span> : null}
                </button>
                <span className="tg-rc__act">
                  {c && <button type="button" className="tg-rc__btn" disabled={busy || c.chosen} onClick={() => act({ type: 'select', place_id: id })} aria-label={c.chosen ? 'Đã trong chuyến' : `Thêm vào chuyến: ${p?.name ?? ''}`} title={c.chosen ? 'Đã trong chuyến' : 'Thêm vào chuyến'}><Icon name={c.chosen ? 'check' : 'plus'} size={16} /></button>}
                  <button type="button" className="tg-rc__btn" onClick={() => unsave(id, p?.name)} aria-label={`Xóa khỏi yêu thích: ${p?.name ?? ''}`} title="Xóa khỏi yêu thích"><Icon name="trash" size={16} /></button>
                </span>
              </li>
            )
          })}
        </ul>
      )}
    </Page>
  )
}

const MOBILITY: [Mobility, string, IconName][] = [['motorbike', 'Xe máy', 'route'], ['car', 'Ô tô', 'map'], ['walk', 'Không dùng xe riêng', 'pin']]
const WHO: [Companions, string][] = [['solo', 'Đi một mình'], ['partner', 'Với người yêu'], ['friends', 'Với bạn bè'], ['kids', 'Với con nhỏ'], ['parents', 'Với bố mẹ']]
const FORM_ERR = (e: Error) => e.message.includes('too long') ? 'Có trường dài quá, rút gọn lại nhé.' : e.message === 'nickname is taken' ? 'Nickname này đã có người dùng.' : e.message.startsWith('nickname') ? 'Nickname 3–24 ký tự: chữ thường không dấu, số, dấu chấm, gạch dưới.' : 'Chưa lưu được, thử lại nhé.'

export function Account() {
  useTitle('Hồ sơ')
  const account = useAccount()
  const friends = useFriends(!!account && !account.guest)
  const savedN = useUi((u) => u.saved.length)
  const [trips, setTrips] = useState<TripSummary[] | null>(null)
  // The numbers are the server's, read again every half minute and when the tab comes back; a failed read keeps the
  // last numbers (or shows a dash), never a made-up zero.
  useEffect(() => {
    const pull = () => { if (document.visibilityState === 'visible') tripSummaries().then(setTrips, () => {}) }
    pull()
    const t = setInterval(pull, 30_000)
    document.addEventListener('visibilitychange', pull)
    return () => { clearInterval(t); document.removeEventListener('visibilitychange', pull) }
  }, [])
  if (!account) return null
  const planned = trips?.filter((t) => t.confirmed) ?? []
  const done = planned.filter((t) => kindOf(t) === 'done').length
  return (
    <Page>
      <header className="tg-head" data-tour="page-head"><div><p className="tg-kicker">Hồ sơ</p><h1>Hồ sơ của bạn</h1><p>Bạn bè thấy tên, nickname, giới thiệu và ảnh. Gu đi chơi chỉ là gợi ý ban đầu cho chuyến mới; điều bạn nói trong chuyến luôn thắng.</p></div></header>
      <section className="tg-card tg-me" aria-label="Tài khoản">
        <div className="tg-me__cover" aria-hidden="true" />
        <div className="tg-me__row">
          <AvatarPicker account={account} />
          <div className="tg-me__id">
            <b>{account.name || 'Bạn'}</b>
            <span className="tg-me__sub">{account.nickname && <>@{account.nickname} · </>}{account.email}</span>
            {account.bio && <p className="tg-me__bio">{account.bio}</p>}
          </div>
          <div className="tg-me__act">
            <TourButton className="tg-btn tg-btn--ghost tg-btn--sm">Xem lại hướng dẫn</TourButton>
            <button type="button" className="tg-btn tg-btn--ghost tg-btn--sm" onClick={() => { void signOut(); go('/login') }}><Icon name="logout" size={15} /> Đăng xuất</button>
          </div>
        </div>
        <dl className="tg-me__stats">
          <div><Icon name="suitcase" size={18} /><dd><Link to="/trips">{trips ? planned.length : '–'}</Link></dd><dt>Chuyến</dt></div>
          <div><Icon name="calendar" size={18} /><dd>{trips ? done : '–'}</dd><dt>Đã đi</dt></div>
          <div><Icon name="heart" size={18} /><dd><Link to="/saved">{savedN}</Link></dd><dt>Đã lưu</dt></div>
          <div><Icon name="users" size={18} /><dd>{friends ? friends.friends.length : '–'}</dd><dt>Bạn bè</dt></div>
        </dl>
      </section>
      <div className="tg-prof">
        <ProfileForm account={account} />
        <TasteCard account={account} />
      </div>
      <section className="tg-card tg-mem__link" aria-labelledby="tg-mem-h">
        <div><h2 id="tg-mem-h"><i aria-hidden="true"><Icon name="sparkle" size={16} /></i>Mình nhớ gì về bạn</h2><p className="tg-faint">Những điều mình rút ra sau các chuyến. Bạn xem, sửa, tạm dừng hay xóa từng dòng.</p></div>
        <Link to="/profile/memory" className="tg-btn tg-btn--soft tg-btn--sm">Mở danh sách</Link>
      </section>
      <NotifyPrefs />
      {account.calendar && <CalendarLink />}
      <DeleteAccount />
      <p className="tg-faint tg-prof__fine"><Icon name="shield" size={14} /> Điều bạn tự nói về sức khỏe hay ăn uống của chính mình chỉ được nhớ khi bạn bật “Nhớ cho lần sau”, và bạn xóa được bất cứ lúc nào. Không thu vị trí GPS.</p>
    </Page>
  )
}

function AvatarPicker({ account }: { account: Me }) {
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const pick = (file: File | undefined) => {
    if (!file) return
    if (file.size > 5 * 1024 * 1024) return setErr('Ảnh tối đa 5 MB.')
    setBusy(true); setErr(null)
    uploadAvatar(file).then(() => toast('Đã đổi ảnh đại diện'), () => setErr('Ảnh này chưa dùng được. Thử ảnh JPG, PNG hoặc WebP khác.')).finally(() => setBusy(false))
  }
  return (
    <div className="tg-avpick">
      <label className="tg-who__av tg-avpick__btn" title="Đổi ảnh đại diện" aria-busy={busy}>
        {account.avatar ? <img src={account.avatar} alt="" referrerPolicy="no-referrer" /> : <span>{(account.name || account.email || '?')[0].toUpperCase()}</span>}
        <input type="file" accept="image/jpeg,image/png,image/webp" className="tg-sr" aria-label="Đổi ảnh đại diện" disabled={busy} onChange={(e) => { pick(e.target.files?.[0]); e.target.value = '' }} />
        <i aria-hidden="true"><Icon name="plus" size={14} /></i>
      </label>
      {err && <small className="tg-auth__err" role="alert">{err}</small>}
    </div>
  )
}

// What friends see: name, nickname, a line about you. One small form.
function ProfileForm({ account }: { account: Me }) {
  const [name, setName] = useState(account.name)
  const [nick, setNick] = useState(account.nickname ?? '')
  const [bio, setBio] = useState(account.bio)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const dirty = name !== account.name || nick !== (account.nickname ?? '') || bio !== account.bio
  const save = () => {
    setBusy(true); setErr(null)
    updateProfile({ display_name: name, nickname: nick || null, bio }).then(() => toast('Đã lưu hồ sơ'), (e: Error) => setErr(FORM_ERR(e))).finally(() => setBusy(false))
  }
  return (
    <section className="tg-card tg-prof__c" aria-labelledby="tg-me-h">
      <h2 id="tg-me-h"><i aria-hidden="true"><Icon name="user" size={16} /></i>Bạn bè nhìn thấy</h2>
      <form className="tg-pform" onSubmit={(e) => { e.preventDefault(); save() }}>
        <label className="tg-auth__f"><span>Tên hiển thị</span><input className="tg-input" value={name} maxLength={60} onChange={(e) => setName(e.target.value)} autoComplete="name" /></label>
        <label className="tg-auth__f"><span>Nickname</span><input className="tg-input" value={nick} maxLength={24} onChange={(e) => setNick(e.target.value.toLowerCase())} placeholder="ví dụ: an.nguyen" autoComplete="nickname" /><small className="tg-faint">Bạn bè tìm và kết bạn bằng nickname.</small></label>
        <label className="tg-auth__f"><span>Giới thiệu ngắn</span><input className="tg-input" value={bio} maxLength={160} onChange={(e) => setBio(e.target.value)} placeholder="Ví dụ: Mê cà phê và săn mây" /></label>
        {err && <small className="tg-auth__err" role="alert">{err}</small>}
        <button type="submit" className="tg-btn tg-btn--primary tg-btn--sm" disabled={!dirty || busy}>{busy ? 'Đang lưu…' : 'Lưu'}</button>
      </form>
    </section>
  )
}

// Where the user usually starts, how they get around, who they go with: a prior for a new trip (shown as "từ hồ sơ"
// and replaced by anything said in the trip). A tap saves; tapping the chosen one again clears it.
function TasteCard({ account }: { account: Me }) {
  const [city, setCity] = useState(account.home_city ?? '')
  const [busy, setBusy] = useState(false)
  const save = (patch: Parameters<typeof updateProfile>[0], done?: string) => {
    setBusy(true)
    updateProfile(patch).then(() => { if (done) toast(done) }, (e: Error) => toast(FORM_ERR(e))).finally(() => setBusy(false))
  }
  return (
    <section className="tg-card tg-prof__c" aria-labelledby="tg-taste-h">
      <h2 id="tg-taste-h"><i aria-hidden="true"><Icon name="compass" size={16} /></i>Gu đi chơi của bạn</h2>
      <p className="tg-faint">Mình dùng để hỏi ít hơn khi bạn lên chuyến mới. Bạn vẫn đổi được ngay trong từng chuyến.</p>
      <div className="tg-taste">
        <form className="tg-taste__row" onSubmit={(e) => { e.preventDefault(); save({ home_city: city }, 'Đã lưu nơi xuất phát') }}>
          <label htmlFor="tg-city">Bạn hay xuất phát từ đâu?</label>
          <div className="tg-taste__line"><input id="tg-city" className="tg-input" value={city} maxLength={80} onChange={(e) => setCity(e.target.value)} placeholder="Ví dụ: Hồ Chí Minh" autoComplete="address-level2" /><button type="submit" className="tg-btn tg-btn--soft tg-btn--sm" disabled={busy || city === (account.home_city ?? '')}>Lưu</button></div>
        </form>
        <div className="tg-taste__row" role="group" aria-labelledby="tg-mob">
          <span id="tg-mob">Ở Đà Lạt bạn hay đi bằng</span>
          <div className="tg-basics__chips">{MOBILITY.map(([v, l, ic]) => <button key={v} type="button" className="tg-chip" aria-pressed={account.usual_mobility === v} disabled={busy} onClick={() => save({ usual_mobility: account.usual_mobility === v ? null : v })}><Icon name={ic} size={14} /> {l}</button>)}</div>
        </div>
        <div className="tg-taste__row" role="group" aria-labelledby="tg-who">
          <span id="tg-who">Bạn hay đi với ai</span>
          <div className="tg-basics__chips">{WHO.map(([v, l]) => <button key={v} type="button" className="tg-chip" aria-pressed={account.usual_companions === v} disabled={busy} onClick={() => save({ usual_companions: account.usual_companions === v ? null : v })}>{l}</button>)}</div>
        </div>
      </div>
    </section>
  )
}

function NotifyPrefs() {
  const [p, setP] = useState<Prefs | null>(null)
  const [busy, setBusy] = useState(false)
  useEffect(() => { loadPrefs().then(setP, () => {}); track('install_prompt_seen') }, [])
  if (!p) return null
  // Optimistic: the box changes at once; a failed save puts it back.
  const save = (patch: Parameters<typeof savePrefs>[0]) => {
    const before = p
    setP({ ...p, ...patch })
    setBusy(true)
    savePrefs(patch).then(setP, () => { setP(before); toast('Chưa lưu được, thử lại nhé') }).finally(() => setBusy(false))
  }
  const toggle = (k: string) => save({ enabled_kinds: p.enabled_kinds.includes(k) ? p.enabled_kinds.filter((x) => x !== k) : [...p.enabled_kinds, k] })
  return (
    <div className="tg-prof is-one">
      <section className="tg-card tg-prof__c" aria-labelledby="tg-np-h">
        <h2 id="tg-np-h"><i aria-hidden="true"><Icon name="bell" size={16} /></i>Thông báo</h2>
        <p className="tg-faint">{p.push_devices ? `Đang nhận trên ${p.push_devices} trình duyệt.` : 'Chưa bật trên trình duyệt nào; vẫn có trong Hộp thông báo.'} Không nhắn từ {p.quiet_start} đến {p.quiet_end}.</p>
        <div className="tg-npref">
          <label><input type="checkbox" checked={p.paused} disabled={busy} onChange={(e) => save({ paused: e.target.checked })} /> Tạm im mọi thông báo</label>
          {p.kinds.map((k) => <label key={k}><input type="checkbox" checked={p.enabled_kinds.includes(k)} disabled={busy || p.paused} onChange={() => toggle(k)} /> {notificationLabel(k)}</label>)}
        </div>
        {pushSupported() && Notification.permission === 'default' && <button type="button" className="tg-btn tg-btn--soft tg-btn--sm" onClick={async () => { const r = await enablePush(); if (r === 'granted') { toast('Đã bật thông báo'); loadPrefs().then(setP) } }}>Bật trên trình duyệt này</button>}
      </section>
    </div>
  )
}

function CalendarLink() {
  const [step, setStep] = useState<0 | 1>(0)
  const [drop, setDrop] = useState(false)
  const [busy, setBusy] = useState(false)
  const off = () => {
    setBusy(true)
    calendarDisconnect(drop).then(() => { toast('Đã ngắt Google Calendar'); return refreshAccount() }, () => toast('Chưa ngắt được, thử lại nhé')).finally(() => setBusy(false))
  }
  return (
    <section className="tg-card tg-del" aria-labelledby="tg-gcal-h">
      <div><h2 id="tg-gcal-h"><i aria-hidden="true"><Icon name="calendar" size={16} /></i>Google Calendar</h2><p className="tg-faint">Đã kết nối. TripGuardian chỉ ghi vào lịch riêng do nó tạo, và chỉ khi bạn xác nhận.</p></div>
      {step === 0 ? <button type="button" className="tg-btn tg-btn--ghost tg-btn--sm" onClick={() => setStep(1)}>Ngắt kết nối…</button> : (
        <div className="tg-del__confirm">
          <label className="tg-auth__check"><input type="checkbox" checked={drop} onChange={(e) => setDrop(e.target.checked)} /> <span>Xóa luôn các lịch TripGuardian trong Google Calendar</span></label>
          <div><button type="button" className="tg-btn tg-btn--sm tg-del__yes" disabled={busy} onClick={off}>Ngắt kết nối</button><button type="button" className="tg-btn tg-btn--ghost tg-btn--sm" onClick={() => setStep(0)}>Thôi</button></div>
        </div>
      )}
    </section>
  )
}

function DeleteAccount() {
  const [step, setStep] = useState<0 | 1>(0)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(false)
  const remove = () => {
    setBusy(true)
    deleteAccount().then(() => go('/login'), () => { setErr(true); setBusy(false) })
  }
  return (
    <section className="tg-card tg-del" aria-labelledby="tg-del-h">
      <div><h2 id="tg-del-h">Xóa tài khoản</h2><p className="tg-faint">Xóa hồ sơ, ảnh, liên kết Google Calendar và thông báo. Chuyến đi và số liệu sử dụng vẫn giữ để thống kê nhưng không còn gắn với bạn.</p></div>
      {step === 0 ? <button type="button" className="tg-btn tg-btn--ghost tg-btn--sm tg-del__go" onClick={() => setStep(1)}>Xóa tài khoản…</button> : (
        <div className="tg-del__confirm" role="alertdialog" aria-labelledby="tg-del-q">
          <p id="tg-del-q"><b>Xóa vĩnh viễn?</b> Không khôi phục được.</p>
          {err && <small className="tg-auth__err" role="alert">Chưa xóa được, thử lại nhé.</small>}
          <div><button type="button" className="tg-btn tg-btn--sm tg-del__yes" disabled={busy} onClick={remove}>{busy ? 'Đang xóa…' : 'Xóa vĩnh viễn'}</button><button type="button" className="tg-btn tg-btn--ghost tg-btn--sm" disabled={busy} onClick={() => setStep(0)}>Giữ tài khoản</button></div>
        </div>
      )}
    </section>
  )
}
