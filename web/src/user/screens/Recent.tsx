import { info } from '../lib'
import { useWarm } from '../../data/store'
import { useUi } from '../store'
import { ArtCup, Empty, go, PlacePhoto } from '../ui/common'
import { Page, useTitle } from '../ui/Shell'
import { openPlace } from '../ui/PlaceSheet'
import type { Opened } from '../store'

const DAY = 86_400_000
const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()

// "Hôm nay" / "Hôm qua" / "dd/mm" for the day a place was opened.
function dayLabel(iso: string, now: Date) {
  const at = new Date(iso)
  const age = Math.round((startOfDay(now) - startOfDay(at)) / DAY)
  return age <= 0 ? 'Hôm nay' : age === 1 ? 'Hôm qua' : at.toLocaleDateString('vi-VN', { day: 'numeric', month: 'numeric' })
}

// Places this account opened lately (from its own usage events, newest first), one photo card each, grouped by day.
export function Recent() {
  useTitle('Đã xem gần đây')
  const recent = useUi((u) => u.recent).filter((r) => r.kind === 'place' && info(r.id))
  useWarm(recent.map((r) => r.id))
  const now = new Date()
  const days: { label: string; items: Opened[] }[] = []
  for (const r of recent) {
    const label = dayLabel(r.at, now)
    const last = days[days.length - 1]
    if (last?.label === label) last.items.push(r)
    else days.push({ label, items: [r] })
  }
  const hour = (iso: string) => new Date(iso).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })
  return (
    <Page>
      <header className="tg-head" data-tour="page-head"><div><p className="tg-kicker">Thư viện của bạn</p><h1>Đã xem gần đây</h1><p>Những nơi bạn vừa mở, mới nhất ở trên cùng.</p></div></header>
      {recent.length === 0 ? <Empty art={<ArtCup />} title="Chưa xem nơi nào" body="Mở chi tiết một địa điểm, nó sẽ hiện ở đây để bạn quay lại." action={<button type="button" className="tg-btn tg-btn--primary" onClick={() => go('/')}>Về Dành cho bạn</button>} /> : (
        <div className="tg-rcs">
          {days.map((d) => (
            <section key={d.label} aria-label={d.label}>
              <h2 className="tg-rcs__day">{d.label}<b>{d.items.length}</b></h2>
              <ul className="tg-rc-grid">
                {d.items.map((r) => {
                  const p = info(r.id)
                  return (
                    <li key={r.id}>
                      <button type="button" className="tg-rc" onClick={(e) => openPlace(r.id, e.currentTarget.querySelector('figure'))}>
                        <PlacePhoto id={r.id} name={p?.name} />
                        <span className="tg-rc__shade" aria-hidden="true" />
                        <time className="tg-rc__time" dateTime={r.at}>{hour(r.at)}</time>
                        <span className="tg-rc__b">
                          <b>{p?.name}</b>
                          <small>{[p?.category, p?.area].filter(Boolean).join(' · ')}</small>
                        </span>
                        {p?.rating ? <span className="tg-rc__star">★ {p.rating.toFixed(1)}</span> : null}
                      </button>
                    </li>
                  )
                })}
              </ul>
            </section>
          ))}
        </div>
      )}
    </Page>
  )
}
