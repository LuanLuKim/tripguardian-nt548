import { useMemo, useState } from 'react'
import { prefLabel } from '../../data/labels'
import type { Group, Snapshot } from '../../data/types'
import { navigate } from '../../router'
import { themeOf } from '../../user/home/themes'
import { pct, useAnalytics, type Count, type TrendPlace, type Trends as TrendsData } from '../analytics'
import { fmtDay, RangeBar, rangeOf, type Range, ViewSwitch } from './Users'

// Xu hướng tiêu dùng (docs/Role_Web_Functional_Design.md §3.10, docs/ANALYTICS.md §6): which places people look at,
// pick, like and put in confirmed plans, how they plan, what they ask Trip for. Counts of journeys, never a score.
const METRICS = [
  ['chosen', 'Được chọn'], ['planned', 'Vào lịch đã chốt'], ['viewed', 'Được xem chi tiết'], ['liked', 'Được thích / lưu'],
  ['rising', 'Đang lên'], ['dropped', 'Bị bỏ'],
] as const
type Metric = (typeof METRICS)[number][0]
const GROUPS: ['' | Group, string][] = [['', 'Mọi nhóm'], ['sight', 'Tham quan'], ['food', 'Ăn uống'], ['shop', 'Mua sắm'], ['other', 'Khác']]
const GROUP_VI: Record<string, string> = { sight: 'Tham quan', food: 'Ăn uống', shop: 'Mua sắm', other: 'Khác' }
const COMPANIONS: Record<string, string> = { solo: 'Một mình', partner: 'Cặp đôi', friends: 'Bạn bè', kids: 'Có trẻ nhỏ', parents: 'Bố mẹ', coworkers: 'Đồng nghiệp', pet: 'Thú cưng' }
const MOBILITY: Record<string, string> = { car: 'Ô tô', motorbike: 'Xe máy', walk: 'Không xe riêng' }
const PURPOSE: Record<string, string> = { photo: 'Chụp ảnh', relax: 'Nghỉ ngơi', food_culture: 'Ẩm thực, văn hóa', bond: 'Gắn kết', adventure: 'Khám phá', nature: 'Thiên nhiên' }
const LIKED: Record<string, string> = { chill: 'Chill, thư thả', meal: 'Ăn uống', nature: 'Thiên nhiên', sights: 'Tham quan' }
const REASON: Record<string, string> = { far: 'Xa', crowded: 'Đông', pricey: 'Đắt', visited: 'Đã đến rồi', none: 'Không nói lý do' }
const WEEKDAY = ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN']
const PAGE = 15

const value = (p: TrendPlace, m: Metric) =>
  m === 'liked' ? p.liked + p.saved : m === 'rising' ? p.recent - p.before : p[m]

export function Trends({ snap }: { snap: Snapshot }) {
  const [range, setRange] = useState<Range>('90')
  const [test, setTest] = useState(false)
  const { data, error } = useAnalytics<TrendsData>('trends', { ...rangeOf(range), test: test ? '1' : undefined })
  const byId = useMemo(() => new Map(snap.places.map((p) => [p.id, p])), [snap])
  return (
    <div className="a-page users">
      <header className="a-head">
        <div>
          <ViewSwitch on="trends" />
          <h1>Xu hướng tiêu dùng</h1>
          <p>Nơi được quan tâm, lịch nhiều người lập và điều khách tìm. Mỗi số là số hành trình, không phải điểm có trọng số.</p>
        </div>
        <RangeBar range={range} setRange={setRange} test={test} setTest={setTest} />
      </header>
      {!data ? <section className="a-card"><p className="a-muted">{error ? `Chưa đọc được số liệu (${error}). Chạy python -m analytics serve (./run.sh start).` : 'Đang tải… lần đầu sau khi server khởi động có thể mất vài giây.'}</p></section> : (
        <>
          <Rising data={data} byId={byId} />
          <Places data={data} byId={byId} />
          <div className="u-grid u-grid--wide">
            <Plans data={data} />
            <When data={data} />
          </div>
          <Intent data={data} />
          <div className="u-grid">
            <Words data={data} />
            <section className="a-card">
              <h2>Vì sao khách bỏ một nơi</h2>
              <p className="a-small">Lý do khi bấm bỏ ở Chọn nơi, trong kỳ.</p>
              <Bars rows={data.drop_reasons} label={(k) => REASON[k] ?? k} />
            </section>
          </div>
        </>
      )}
    </div>
  )
}

type ById = Map<string, Snapshot['places'][number]>
const nameOf = (p: { place_id: string; name: string | null }, byId: ById) => byId.get(p.place_id)?.name ?? p.name ?? p.place_id
const open = (id: string) => navigate(`/admin/places/${encodeURIComponent(id)}`)

// Candidates for Trending: interest (view, choose, like, open outside) in the last 7 days against the 7 before.
function Rising({ data, byId }: { data: TrendsData; byId: ById }) {
  const up = data.places.filter((p) => p.recent > p.before).sort((a, b) => b.recent - b.before - (a.recent - a.before)).slice(0, 5)
  return (
    <section className="a-card t-rising">
      <div className="u-card-head">
        <h2>Đang lên 7 ngày qua</h2>
        <span className="a-small">từ {fmtDay(data.recent_from)}, so với 7 ngày trước đó</span>
      </div>
      {!up.length ? <p className="a-muted">Chưa nơi nào được quan tâm hơn tuần trước.</p> : (
        <ol>
          {up.map((p, i) => {
            const pl = byId.get(p.place_id)
            return (
              <li key={p.place_id}>
                <button onClick={() => open(p.place_id)}>
                  <span className="t-rank">{i + 1}</span>
                  <b>{nameOf(p, byId)}</b>
                  <small>{[pl ? GROUP_VI[pl.group] : null, pl?.category].filter(Boolean).join(' · ') || '—'}</small>
                  <span className="t-up">▲ {p.recent - p.before}<small> {p.before} → {p.recent} hành trình</small></span>
                </button>
              </li>
            )
          })}
        </ol>
      )}
      <p className="a-small">Quan tâm = xem chi tiết, chọn, thích hoặc mở Maps / TikTok. Ứng viên để đối chiếu với khối Trending ở trang chủ của người dùng.</p>
    </section>
  )
}

function Places({ data, byId }: { data: TrendsData; byId: ById }) {
  const [metric, setMetric] = useState<Metric>('chosen')
  const [group, setGroup] = useState<'' | Group>('')
  const [shown, setShown] = useState(PAGE)
  const rows = useMemo(
    () => data.places.filter((p) => (!group || byId.get(p.place_id)?.group === group) && value(p, metric) > 0)
      .sort((a, b) => value(b, metric) - value(a, metric)),
    [data, byId, metric, group],
  )
  const top = Math.max(1, ...rows.map((p) => value(p, metric)))
  const groupShare = useMemo(() => {
    const out: Record<string, number> = {}
    for (const p of data.places) {
      const g = GROUP_VI[byId.get(p.place_id)?.group ?? ''] ? byId.get(p.place_id)!.group : 'other'
      out[g] = (out[g] ?? 0) + p.chosen
    }
    return out
  }, [data, byId])
  const chosenAll = Object.values(groupShare).reduce((a, b) => a + b, 0)
  return (
    <section className="a-card">
      <div className="u-card-head">
        <h2>Nơi được quan tâm</h2>
        <span className="a-small">{rows.length} nơi</span>
      </div>
      <p className="a-small">Bấm một nơi để mở trang Địa điểm. "Tỉ lệ chọn" = trong các hành trình đã thấy thẻ, bao nhiêu hành trình chọn nơi đó. Cột Chọn gồm cả chọn qua trò chuyện, không cần thấy thẻ.</p>
      <div className="a-toolbar u-people-tools">
        <div className="seg" role="radiogroup" aria-label="Xếp theo">{METRICS.map(([k, l]) => <button key={k} role="radio" aria-checked={metric === k} onClick={() => (setMetric(k), setShown(PAGE))}>{l}</button>)}</div>
        <div className="seg" role="radiogroup" aria-label="Nhóm">{GROUPS.map(([k, l]) => <button key={k} role="radio" aria-checked={group === k} onClick={() => (setGroup(k), setShown(PAGE))}>{l}</button>)}</div>
      </div>
      {chosenAll > 0 && (
        <div className="t-share">
          <span className="a-small">Lượt chọn theo nhóm</span>
          <div className="stack" role="img" aria-label={Object.entries(groupShare).map(([g, n]) => `${GROUP_VI[g]} ${n}`).join(', ')}>
            {Object.entries(groupShare).filter(([, n]) => n).map(([g, n]) => <i key={g} className={`t-g t-g--${g}`} title={`${GROUP_VI[g]}: ${n}`} style={{ flexGrow: n }} />)}
          </div>
          <ul className="legend">{Object.entries(groupShare).filter(([, n]) => n).map(([g, n]) => <li key={g}><i className={`t-g t-g--${g}`} />{GROUP_VI[g]} <b>{pct(n / chosenAll)}</b></li>)}</ul>
        </div>
      )}
      {!rows.length ? <p className="a-empty">Chưa có nơi nào cho cách xếp này trong kỳ.</p> : (
        <div className="u-scroll">
          <table className="a-table u-people t-places">
            <thead>
              <tr>
                <th>#</th><th>Nơi</th><th>{METRICS.find(([k]) => k === metric)![1]}</th>
                <th className="num">Thấy thẻ</th><th className="num">Xem</th><th className="num">Chọn</th><th className="num">Tỉ lệ chọn</th>
                <th className="num">Thích</th><th className="num">Lưu</th><th className="num">Vào lịch</th><th className="num">Bị bỏ</th><th className="num">7 ngày</th>
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, shown).map((p, i) => {
                const pl = byId.get(p.place_id)
                const v = value(p, metric)
                return (
                  <tr key={p.place_id} tabIndex={0} onClick={() => open(p.place_id)} onKeyDown={(e) => { if (e.key === 'Enter') open(p.place_id) }}>
                    <td className="num a-muted">{i + 1}</td>
                    <td><b>{nameOf(p, byId)}</b><small>{[pl ? GROUP_VI[pl.group] : null, pl?.category, pl?.rating ? `★ ${pl.rating}` : null].filter(Boolean).join(' · ') || 'không có trong snapshot'}</small></td>
                    <td><div className="t-barcell"><span className="u-ladder__bar"><i style={{ width: `${(v / top) * 100}%` }} /></span><b>{metric === 'rising' ? `+${v}` : v}</b></div></td>
                    <td className="num">{p.shown || '—'}</td>
                    <td className="num">{p.viewed || '—'}</td>
                    <td className="num">{p.chosen || '—'}</td>
                    <td className="num">{p.shown ? pct(p.chosen_seen / p.shown) : '—'}</td>
                    <td className="num">{p.liked || '—'}</td>
                    <td className="num">{p.saved || '—'}</td>
                    <td className="num">{p.planned || '—'}</td>
                    <td className={`num${p.dropped ? ' u-bad' : ''}`}>{p.dropped || '—'}</td>
                    <td className="num t-trend">{p.recent === p.before ? '—' : p.recent > p.before ? `▲ ${p.recent - p.before}` : `▼ ${p.before - p.recent}`}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
      {rows.length > shown && <button className="a-btn a-btn--ghost u-more" onClick={() => setShown((s) => s + PAGE)}>Xem thêm {Math.min(PAGE, rows.length - shown)} nơi</button>}
    </section>
  )
}

function Bars({ rows, label, max = 8, of }: { rows: Count[]; label?: (k: string) => string; max?: number; of?: number }) {
  if (!rows.length) return <p className="a-muted a-small">Chưa có.</p>
  const top = Math.max(1, ...rows.map((r) => r.n))
  const total = of ?? rows.reduce((a, r) => a + r.n, 0)
  return (
    <ul className="u-fill t-bars">
      {rows.slice(0, max).map((r) => (
        <li key={String(r.key)}>
          <span title={String(r.key)}>{label ? label(String(r.key)) : String(r.key)}</span>
          <span className="u-ladder__bar"><i style={{ width: `${(r.n / top) * 100}%` }} /></span>
          <b>{r.n}</b>
          <small>{pct(total ? r.n / total : null)}</small>
        </li>
      ))}
    </ul>
  )
}

function Plans({ data }: { data: TrendsData }) {
  const p = data.plans
  const hourTop = Math.max(1, ...p.hours.map((h) => h.n))
  return (
    <section className="a-card">
      <h2>Lịch nhiều người lập</h2>
      <p className="a-small">{p.trips} lịch đã chốt trong kỳ, {p.stops} điểm dừng. Lịch của hành trình thử tự động không tính.</p>
      <div className="t-facts">
        <div><span>Dài</span><b>{p.days[0] ? `${p.days[0].key} ngày` : '—'}</b><small>phổ biến nhất</small></div>
        <div><span>Nơi mỗi ngày</span><b>{p.per_day_median ?? '—'}</b><small>trung vị</small></div>
        <div><span>Chốt trước chuyến</span><b>{p.lead_median == null ? '—' : `${p.lead_median} ngày`}</b><small>trung vị</small></div>
      </div>
      <h3 className="u-h3">Giờ tới nơi trong lịch</h3>
      <div className="t-hours" role="img" aria-label={p.hours.filter((h) => h.n).map((h) => `${h.key} giờ: ${h.n}`).join(', ')}>
        {p.hours.map((h) => (
          <span key={h.key} title={`${h.key}:00 – ${h.n} điểm dừng`}>
            <i style={{ height: `${(h.n / hourTop) * 100}%` }} />
            <small>{h.key % 3 === 2 ? `${h.key}h` : ''}</small>
          </span>
        ))}
      </div>
      <div className="u-grid t-pairs">
        <div>
          <h3 className="u-h3">Hay được xếp cùng một chuyến</h3>
          <Pairs rows={p.pairs} sep="+" />
        </div>
        <div>
          <h3 className="u-h3">Hay đi liền nhau</h3>
          <Pairs rows={p.chains} sep="→" />
        </div>
      </div>
    </section>
  )
}

function Pairs({ rows, sep }: { rows: TrendsData['plans']['pairs']; sep: string }) {
  if (!rows.length) return <p className="a-muted a-small">Chưa có cặp nào lặp lại ở ≥ 2 lịch.</p>
  return (
    <ol className="t-pairlist">
      {rows.slice(0, 6).map((r) => (
        <li key={r.a + r.b}>
          <button className="a-link" onClick={() => open(r.a)}>{r.a_name ?? r.a}</button> <span className="a-muted">{sep}</span> <button className="a-link" onClick={() => open(r.b)}>{r.b_name ?? r.b}</button>
          <b>{r.n} lịch</b>
        </li>
      ))}
    </ol>
  )
}

function When({ data }: { data: TrendsData }) {
  const i = data.intent
  const months = [...i.months].sort((a, b) => String(a.key).localeCompare(String(b.key)))
  const wd = WEEKDAY.map((d, k) => ({ key: d, n: i.start_weekday.find((x) => Number(x.key) === k)?.n ?? 0 }))
  const planDays = WEEKDAY.map((d, k) => ({ key: d, n: data.plans.weekdays[k] ?? 0 }))
  return (
    <section className="a-card">
      <h2>Khi nào khách đi</h2>
      <p className="a-small">Ngày đi người dùng tự nói khi kể chuyến ({i.journeys} hành trình trong kỳ).</p>
      <h3 className="u-h3">Tháng đi</h3>
      <Bars rows={months.map((m) => ({ key: `${String(m.key).slice(5, 7)}/${String(m.key).slice(0, 4)}`, n: m.n }))} max={8} />
      <h3 className="u-h3">Ngày bắt đầu chuyến</h3>
      <Bars rows={wd} max={7} />
      <h3 className="u-h3">Ngày có điểm dừng trong lịch đã chốt</h3>
      <Bars rows={planDays} max={7} />
    </section>
  )
}

function Intent({ data }: { data: TrendsData }) {
  const i = data.intent
  const blocks: [string, Count[], ((k: string) => string)?][] = [
    ['Đi cùng ai', i.companions, (k) => COMPANIONS[k] ?? k],
    ['Số người', i.people, (k) => `${k} người`],
    ['Số ngày', i.days, (k) => `${k} ngày`],
    ['Phương tiện', i.mobility, (k) => MOBILITY[k] ?? k],
    ['Ngân sách mỗi người', i.budget],
    ['Mục đích', i.purpose, (k) => PURPOSE[k] ?? k],
    ['Sở thích nói ra', i.interests, prefLabel],
    ['Kiểu đã thích', i.groups, (k) => LIKED[k] ?? k],
    ['Loại nơi muốn tới', i.kinds],
    ['Món muốn ăn', i.dishes],
    ['Cảm hứng, khung cảnh', i.vibes],
  ]
  return (
    <section className="a-card">
      <h2>Khách muốn gì</h2>
      <p className="a-small">Từ yêu cầu Trip đã hiểu của {i.journeys} hành trình tạo trong kỳ; chỉ tính điều người dùng nói hoặc hồ sơ cho, không tính giá trị mặc định. Phần trăm trên số lần nhắc trong từng khối.</p>
      <div className="t-intent">
        {blocks.map(([title, rows, label]) => (
          <div key={title}>
            <h3 className="u-h3">{title}</h3>
            <Bars rows={rows} label={label} max={6} />
          </div>
        ))}
      </div>
    </section>
  )
}

function Words({ data }: { data: TrendsData }) {
  return (
    <section className="a-card">
      <h2>Chủ đề và từ khóa</h2>
      <h3 className="u-h3">Chủ đề trang chủ được mở</h3>
      <Bars rows={data.themes} label={(k) => themeOf(k)?.tab ?? k} />
      <h3 className="u-h3">Tìm nơi theo tên</h3>
      {!data.searches.length ? <p className="a-muted a-small">Chưa có.</p> : (
        <div className="u-chips t-words">
          {data.searches.slice(0, 20).map((s) => <code key={s.q} className={s.misses ? 'is-bad' : ''} title={s.misses ? `${s.misses} lần không ra kết quả` : ''}>{s.q} ×{s.n}</code>)}
        </div>
      )}
      <p className="a-small">Ô đỏ: có lần không ra kết quả, nên đưa vào danh sách cần crawl (Insights).</p>
    </section>
  )
}
