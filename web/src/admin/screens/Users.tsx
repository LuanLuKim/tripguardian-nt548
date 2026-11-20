import { useLayoutEffect, useMemo, useRef, useState } from 'react'
import { match, navigate, usePath } from '../../router'
import { Icon } from '../../ui/bits'
import { pct, useAnalytics, type Day, type Feature, type PersonRow, type PersonType, type UsersOverview } from '../analytics'
import { UserDetail } from './UserDetail'

// Người dùng (docs/Role_Web_Functional_Design.md §3.9, docs/ANALYTICS.md §5): who uses the product, how far each
// person gets, where they stop and which features nobody touches. Read-only; no thresholds until a real baseline.
const RANGES = [['7', '7 ngày'], ['30', '30 ngày'], ['90', '90 ngày'], ['all', 'Từ đầu']] as const
export type Range = (typeof RANGES)[number][0]
export const TYPE: Record<PersonType, string> = { account: 'Tài khoản', guest: 'Khách' }
export const LOGIN: Record<PersonRow['login'], string> = { google: 'Google', password: 'Email', both: 'Google + email', none: 'Đăng nhập thử' }
export const STEPS = ['Có tài khoản', 'Tạo hành trình', 'Trip hiểu xong', 'Chọn ≥ 1 nơi', 'Chốt lịch', 'Gửi phản hồi', 'Lập chuyến ở ngày khác']
const SEGMENTS = [
  ['', 'Mọi người'], ['new', 'Mới trong kỳ'], ['active', 'Hoạt động trong kỳ'], ['no_journey', 'Chưa tạo hành trình'],
  ['no_confirm', 'Có hành trình, chưa chốt'], ['one_day', 'Chỉ hoạt động 1 ngày'], ['error', 'Có lỗi / fallback'], ['low_feedback', 'Chấm ≤ 2 điểm'],
] as const
type Segment = (typeof SEGMENTS)[number][0]
const KEEP = (r: PersonRow, s: Segment) =>
  s === '' ? true
    : s === 'new' ? r.new_in_range
      : s === 'active' ? r.active_in_range
        : s === 'no_journey' ? r.type === 'account' && r.journeys === 0 && r.furthest === 0
          : s === 'no_confirm' ? r.furthest >= 1 && r.confirmed === 0 && r.furthest < 4
            : s === 'one_day' ? r.active_days === 1
              : s === 'error' ? r.errors > 0
                : r.min_score != null && r.min_score <= 2

const DAY = 86_400_000
const iso = (d: Date) => new Date(d.getTime() + 7 * 3_600_000).toISOString().slice(0, 10)
export function rangeOf(r: Range): { from?: string } {
  if (r === 'all') return { from: '2026-01-01' }
  return { from: iso(new Date(Date.now() - (Number(r) - 1) * DAY)) }
}
export const fmtDay = (s: string) => `${s.slice(8, 10)}/${s.slice(5, 7)}`
export const fmtDate = (s: string | null | undefined) => (s ? new Date(s).toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: '2-digit' }) : '—')
export function ago(s: string | null | undefined) {
  if (!s) return '—'
  const m = (Date.now() - new Date(s).getTime()) / 60_000
  if (m < 60) return `${Math.max(1, Math.round(m))} phút trước`
  if (m < 60 * 24) return `${Math.round(m / 60)} giờ trước`
  if (m < 60 * 24 * 45) return `${Math.round(m / 1440)} ngày trước`
  return fmtDate(s)
}
export const who = (r: Pick<PersonRow, 'name' | 'email' | 'type' | 'id'>) => r.name || r.email || `${TYPE[r.type]} ${r.id.slice(0, 6)}`
export const initials = (r: Pick<PersonRow, 'name' | 'email' | 'type' | 'id'>) =>
  (r.name || r.email || '').split(/[\s@.]+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join('').toUpperCase() || (r.type === 'account' ? '?' : 'K')

export function Users() {
  const path = usePath()
  const m = match(path, '/admin/users/:id')
  return m ? <UserDetail id={m.id} /> : <Overview />
}

function Overview() {
  const [range, setRange] = useState<Range>('90')
  const [test, setTest] = useState(false)
  const [segment, setSegment] = useState<Segment>('')
  const table = useRef<HTMLElement>(null)
  const f = { ...rangeOf(range), test: test ? '1' : undefined }
  const { data, error } = useAnalytics<UsersOverview>('users', f)
  const list = useAnalytics<PersonRow[]>('users/list', f)
  const focus = (s: Segment) => {
    setSegment(s)
    table.current?.scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' })
  }
  return (
    <div className="a-page users">
      <header className="a-head">
        <div>
          <ViewSwitch on="users" />
          <h1>Người dùng</h1>
          <p>Ai đang dùng, đi tới đâu, dừng ở đâu và tính năng nào chưa ai chạm tới. Số từ sự kiện thật, chỉ đọc.</p>
        </div>
        <RangeBar range={range} setRange={setRange} test={test} setTest={setTest} />
      </header>
      {!data ? <section className="a-card"><p className="a-muted">{error ? `Chưa đọc được số liệu (${error}). Chạy python -m analytics serve (./run.sh start).` : 'Đang tải…'}</p></section> : (
        <>
          <p className="a-small u-range">
            Kỳ {fmtDay(data.range[0])}/{data.range[0].slice(2, 4)} – {fmtDay(data.range[1])}/{data.range[1].slice(2, 4)}, so với kỳ ngay trước cùng độ dài.
            {' '}Tài khoản là người đăng nhập Google hoặc email{test ? ', gồm cả tài khoản thử' : ', không gồm tài khoản thử (@test.local, @example.com)'}.
          </p>
          <Kpis d={data} />
          <div className="u-grid u-grid--wide">
            <div className="u-col">
              <Activity days={data.daily} />
              <Ladder rungs={data.ladder} />
            </div>
            <Gaps d={data} onSegment={focus} />
          </div>
          <div className="u-grid u-grid--wide">
            <Cohorts d={data} />
            <Profile d={data} />
          </div>
          <Features list={data.features} active={data.kpis.active_accounts.n} />
        </>
      )}
      <section className="a-card" ref={table} aria-label="Danh sách người dùng">
        <People rows={list.data} error={list.error} segment={segment} setSegment={setSegment} />
      </section>
    </div>
  )
}

export function RangeBar({ range, setRange, test, setTest }: { range: Range; setRange: (r: Range) => void; test: boolean; setTest: (t: boolean) => void }) {
  return (
    <div className="a-toolbar">
      <div className="seg" role="radiogroup" aria-label="Khoảng thời gian">
        {RANGES.map(([k, l]) => <button key={k} role="radio" aria-checked={range === k} onClick={() => setRange(k)}>{l}</button>)}
      </div>
      <label className="u-check"><input type="checkbox" checked={test} onChange={(e) => setTest(e.target.checked)} /> Gồm tài khoản thử</label>
    </div>
  )
}

// The two halves of the people dashboard: who uses the product, and what they like.
export function ViewSwitch({ on }: { on: 'users' | 'trends' }) {
  return (
    <nav className="u-switch" aria-label="Bảng điều khiển người dùng">
      <button className={on === 'users' ? 'is-on' : ''} aria-current={on === 'users' ? 'page' : undefined} onClick={() => navigate('/admin/users')}>Người dùng</button>
      <button className={on === 'trends' ? 'is-on' : ''} aria-current={on === 'trends' ? 'page' : undefined} onClick={() => navigate('/admin/trends')}>Xu hướng tiêu dùng</button>
    </nav>
  )
}

function Delta({ k }: { k: { n: number; prev: number | null } }) {
  if (k.prev == null) return null
  const d = k.n - k.prev
  return <em className="u-delta" title={`Kỳ trước: ${k.prev}`}>{d === 0 ? 'bằng kỳ trước' : `${d > 0 ? '▲' : '▼'} ${Math.abs(d).toLocaleString('vi-VN')} so với kỳ trước`}</em>
}

function Kpi({ label, k, sub, tone, n }: { label: string; k?: { n: number; prev: number | null }; n?: number; sub?: string; tone?: 'warn' }) {
  return (
    <div className={`tile u-kpi${tone ? ` tile--${tone}` : ''}`}>
      <span>{label}</span>
      <b>{(k?.n ?? n ?? 0).toLocaleString('vi-VN')}</b>
      {k && <Delta k={k} />}
      {sub && <small>{sub}</small>}
    </div>
  )
}

function Kpis({ d }: { d: UsersOverview }) {
  const k = d.kpis
  return (
    <div className="tiles u-kpis">
      <Kpi label="Tài khoản" n={k.accounts.n} sub={`+${k.new_accounts.n} mới trong kỳ · ${k.guests_alive} khách đang mở`} />
      <Kpi label="Tài khoản hoạt động" k={k.active_accounts} sub={`${pct(k.accounts.n ? k.active_accounts.n / k.accounts.n : null)} số tài khoản`} />
      <Kpi label="Quay lại ≥ 2 ngày" n={k.returning.n} sub={`${pct(k.active_accounts.n ? k.returning.n / k.active_accounts.n : null)} người hoạt động trong kỳ`} />
      <Kpi label="Phiên khách mới" k={k.guest_sessions} sub={`${k.guest_adopted.n} đăng nhập để giữ chuyến (${pct(k.guest_sessions.n ? k.guest_adopted.n / k.guest_sessions.n : null)})`} />
      <Kpi label="Hành trình tạo mới" k={k.journeys} sub={`${k.confirmed.n.toLocaleString('vi-VN')} lượt chốt lịch, cả khách`} />
      <Kpi label="Tài khoản gặp lỗi / fallback" n={k.with_errors.n} sub={`trên ${k.active_accounts.n} tài khoản hoạt động`} tone={k.with_errors.n ? 'warn' : undefined} />
    </div>
  )
}

// ---------- activity over time ----------

const SERIES = [
  ['journeys', 'Hành trình tạo', 'bar'],
  ['confirmed', 'Lượt chốt lịch', 'bar-in'],
  ['accounts', 'Tài khoản hoạt động', 'line'],
  ['guests', 'Phiên khách mới', 'dash'],
] as const

function niceMax(v: number) {
  const p = 10 ** Math.floor(Math.log10(v))
  return [1, 2, 2.5, 5, 10].map((m) => m * p).find((x) => x >= v) ?? v
}

function Activity({ days }: { days: Day[] }) {
  const box = useRef<HTMLDivElement>(null)
  const [w, setW] = useState(720)
  const [hi, setHi] = useState<number | null>(null)
  const [asTable, setAsTable] = useState(false)
  useLayoutEffect(() => {
    const el = box.current
    if (!el) return
    const ro = new ResizeObserver(([e]) => setW(Math.max(320, e.contentRect.width)))
    ro.observe(el)
    return () => ro.disconnect()
  }, [asTable])
  if (!days.length) return <section className="a-card"><h2>Hoạt động theo ngày</h2><p className="a-muted">Chưa có sự kiện trong kỳ.</p></section>
  const H = 232, L = 36, R = 10, T = 14, B = 26
  const max = niceMax(Math.max(1, ...days.flatMap((d) => [d.accounts, d.guests, d.journeys])))
  const iw = w - L - R, ih = H - T - B, step = iw / days.length
  const x = (i: number) => L + step * i + step / 2
  const y = (v: number) => T + ih - (v / max) * ih
  const bw = Math.max(1.5, Math.min(18, step * 0.62))
  const path = (k: 'accounts' | 'guests') => days.map((d, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(d[k]).toFixed(1)}`).join('')
  const every = Math.max(1, Math.ceil(days.length / Math.max(2, Math.floor(iw / 64))))
  const peak = days.reduce((a, b) => (b.journeys > a.journeys ? b : a), days[0])
  const sum = (k: keyof Omit<Day, 'day'>) => days.reduce((a, d) => a + d[k], 0)
  const cur = hi == null ? null : days[hi]
  const pick = (clientX: number) => {
    const r = box.current?.getBoundingClientRect()
    if (!r) return
    setHi(Math.max(0, Math.min(days.length - 1, Math.floor((clientX - r.left - L) / step))))
  }
  return (
    <section className="a-card u-activity">
      <div className="u-card-head">
        <h2>Hoạt động theo ngày</h2>
        <button className="a-link a-small" onClick={() => setAsTable((t) => !t)}>{asTable ? 'Xem biểu đồ' : 'Xem dạng bảng'}</button>
      </div>
      <ul className="u-legend">
        {SERIES.map(([k, l, kind]) => <li key={k}><i className={`u-mark u-mark--${kind}`} />{l} <b>{sum(k).toLocaleString('vi-VN')}</b></li>)}
      </ul>
      {asTable ? (
        <div className="u-scroll">
          <table className="a-table a-table--compact">
            <thead><tr><th>Ngày</th>{SERIES.map(([k, l]) => <th key={k} className="num">{l}</th>)}</tr></thead>
            <tbody>{[...days].reverse().map((d) => <tr key={d.day}><td>{fmtDay(d.day)}</td>{SERIES.map(([k]) => <td key={k} className="num">{d[k]}</td>)}</tr>)}</tbody>
          </table>
        </div>
      ) : (
        <div
          className="u-chart"
          ref={box}
          tabIndex={0}
          aria-label={`Biểu đồ ${days.length} ngày. Dùng mũi tên trái phải để đọc từng ngày.`}
          onPointerMove={(e) => pick(e.clientX)}
          onPointerLeave={() => setHi(null)}
          onBlur={() => setHi(null)}
          onKeyDown={(e) => {
            if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
              e.preventDefault()
              setHi((h) => Math.max(0, Math.min(days.length - 1, (h ?? days.length) + (e.key === 'ArrowLeft' ? -1 : 1))))
            }
          }}
        >
          <svg width={w} height={H} role="img" aria-label={`Ngày đông nhất ${fmtDay(peak.day)}: ${peak.journeys} hành trình`}>
            {[0, 0.5, 1].map((t) => (
              <g key={t}>
                <line className="u-grid-line" x1={L} x2={w - R} y1={y(max * t)} y2={y(max * t)} />
                <text className="u-axis" x={L - 6} y={y(max * t) + 4} textAnchor="end">{Math.round(max * t)}</text>
              </g>
            ))}
            {days.map((d, i) => (
              <g key={d.day} className={hi === i ? 'is-hi' : ''}>
                {hi === i && <rect className="u-hover" x={x(i) - step / 2} y={T} width={step} height={ih} />}
                <rect className="u-bar" x={x(i) - bw / 2} y={y(d.journeys)} width={bw} height={Math.max(0, T + ih - y(d.journeys))} rx={Math.min(3, bw / 3)} />
                <rect className="u-bar-in" x={x(i) - bw / 2} y={y(d.confirmed)} width={bw} height={Math.max(0, T + ih - y(d.confirmed))} rx={Math.min(3, bw / 3)} />
                {i % every === 0 && <text className="u-axis" x={x(i)} y={H - 8} textAnchor="middle">{fmtDay(d.day)}</text>}
              </g>
            ))}
            <path className="u-line" d={path('accounts')} />
            <path className="u-line u-line--dash" d={path('guests')} />
            {cur && hi != null && (
              <>
                <circle className="u-dot" cx={x(hi)} cy={y(cur.accounts)} r={4} />
                <circle className="u-dot u-dot--dash" cx={x(hi)} cy={y(cur.guests)} r={4} />
              </>
            )}
          </svg>
          {cur && hi != null && (
            <div className="u-tip" style={{ left: Math.min(w - 190, Math.max(0, x(hi) + 12)) }} role="status">
              <b>{fmtDay(cur.day)}</b>
              {SERIES.map(([k, l, kind]) => <span key={k}><i className={`u-mark u-mark--${kind}`} />{l}<em>{cur[k]}</em></span>)}
            </div>
          )}
        </div>
      )}
      <p className="a-small">Ngày đông nhất {fmtDay(peak.day)}: {peak.journeys} hành trình. Hành trình và lượt chốt gồm cả khách; khách đã bị dọn không còn gắn với người nên không có đường "khách hoạt động".</p>
    </section>
  )
}

// ---------- gaps: facts sorted by how many people they touch; links lead to the people or the screen to act on ----------

type Gap = { key: string; tone?: 'bad' | 'warn'; title: string; n?: number; of?: number; chips?: string[]; act?: { label: string; go: () => void } }

function Gaps({ d, onSegment }: { d: UsersOverview; onSegment: (s: Segment) => void }) {
  const g = d.gaps
  const list: Gap[] = [
    { key: 'errors', tone: 'bad', title: 'tài khoản hoạt động gặp lỗi hoặc fallback', n: g.errors.n, of: g.errors.of, chips: g.errors.top.map((t) => `${t.name} ×${t.n}`), act: { label: 'Xem những người này', go: () => onSegment('error') } },
    { key: 'never_confirm', tone: 'warn', title: 'người có hành trình nhưng chưa chốt lịch lần nào', n: g.never_confirm.n, of: g.never_confirm.of, act: { label: 'Xem danh sách', go: () => onSegment('no_confirm') } },
    { key: 'never_journey', title: 'tài khoản chưa tạo hành trình nào', n: g.never_journey.n, of: g.never_journey.of, act: { label: 'Xem danh sách', go: () => onSegment('no_journey') } },
    { key: 'one_day', title: 'người chỉ hoạt động đúng một ngày rồi không quay lại', n: g.one_day.n, of: g.one_day.of, act: { label: 'Xem danh sách', go: () => onSegment('one_day') } },
    { key: 'low_feedback', tone: 'warn', title: 'người từng chấm ≤ 2 điểm sau chuyến', n: g.low_feedback.n, of: g.low_feedback.of, act: { label: 'Xem danh sách', go: () => onSegment('low_feedback') } },
    { key: 'guests', title: `phiên khách trong kỳ đăng nhập để giữ chuyến`, n: g.guests.n, of: g.guests.of },
    { key: 'no_prior', title: 'tài khoản chưa có gì để cá nhân hóa (phương tiện, đi cùng ai, nhớ hồ sơ)', n: g.no_prior.n, of: g.no_prior.of },
    { key: 'search', title: 'lần tìm nơi theo tên không ra kết quả', n: g.search_misses.n, act: { label: 'Mở Insights', go: () => navigate('/admin/insights') } },
  ]
  const shown = list.filter((x) => x.n)
  const quiet = list.length - shown.length
  return (
    <section className="a-card u-gaps">
      <h2>Tín hiệu cần chú ý</h2>
      <p className="a-small">Sự thật đếm được, chưa có ngưỡng. Bấm để mở đúng nhóm người ở bảng dưới.</p>
      <ul>
        {shown.map((x) => (
          <li key={x.key} className={x.tone ? `is-${x.tone}` : ''}>
            <p>
              <b>{x.n!.toLocaleString('vi-VN')}{x.of != null && <small> / {x.of.toLocaleString('vi-VN')}</small>}</b> {x.title}
            </p>
            {x.of ? <span className="u-meter" role="img" aria-label={pct(x.n! / x.of)}><i style={{ width: `${Math.min(100, (x.n! / x.of) * 100)}%` }} /></span> : null}
            {x.chips?.length ? <div className="u-chips">{x.chips.map((c) => <code key={c}>{c}</code>)}</div> : null}
            {x.act && <button className="a-link a-small" onClick={x.act.go}>{x.act.label} <Icon name="next" size={12} /></button>}
          </li>
        ))}
        {g.unused.length > 0 && (
          <li className="is-warn">
            <p><b>{g.unused.length}</b> tính năng chưa ai dùng trong kỳ</p>
            <div className="u-chips">{g.unused.map((u) => <code key={u}>{u}</code>)}</div>
          </li>
        )}
      </ul>
      {quiet > 0 && <p className="a-small a-muted">{quiet} tín hiệu khác đang bằng 0.</p>}
    </section>
  )
}

// ---------- activation ladder (per person) and weekly retention ----------

function Ladder({ rungs }: { rungs: UsersOverview['ladder'] }) {
  const top = rungs[0]?.n || 0
  const seq = rungs.slice(1, -1).filter((r) => r.kept != null)
  const worst = seq.length ? seq.reduce((a, b) => ((b.kept ?? 1) < (a.kept ?? 1) ? b : a)) : null
  return (
    <section className="a-card">
      <h2>Mỗi người đi tới đâu</h2>
      <p className="a-small">{top} tài khoản tạo trong kỳ; mỗi bước tính một lần mỗi người, tới bất kỳ lúc nào sau đó. Khác Phân tích › Phễu (đếm theo hành trình).</p>
      {!top ? <p className="a-muted">Không có tài khoản mới trong kỳ. Chọn khoảng dài hơn.</p> : (
        <ol className="u-ladder">
          {rungs.map((r, i) => (
            <li key={r.key} className={`${worst?.key === r.key ? 'is-worst' : ''}${i === rungs.length - 1 ? ' is-extra' : ''}`}>
              <span className="u-ladder__label">{r.label}</span>
              <span className="u-ladder__bar"><i style={{ width: `${(r.n / top) * 100}%` }} /></span>
              <b>{r.n}</b>
              <small>{pct(r.n / top)}</small>
              <small className="u-ladder__kept">{r.kept == null ? '' : `giữ ${pct(r.kept)}`}</small>
            </li>
          ))}
        </ol>
      )}
      {worst && <p className="a-small">Rơi nhiều nhất ở bước <b>{worst.label}</b>: chỉ {pct(worst.kept)} người của bước trước đi tiếp. “Lập chuyến ở ngày khác” tính trên người đã tạo hành trình.</p>}
    </section>
  )
}

function Cohorts({ d }: { d: UsersOverview }) {
  const weeks = d.cohorts
  return (
    <section className="a-card">
      <h2>Giữ chân theo tuần đăng ký</h2>
      <p className="a-small">Mỗi hàng là các tài khoản đăng ký cùng tuần; ô = phần trăm có hoạt động ở tuần thứ k sau đó (T0 là tuần đăng ký). Không theo bộ lọc thời gian.</p>
      {!weeks.length ? <p className="a-muted">Chưa có tài khoản.</p> : (
        <div className="u-scroll">
          <table className="u-cohort">
            <thead><tr><th>Tuần</th><th className="num">Người</th>{weeks[0].cells.map((_, k) => <th key={k} className="num">T{k}</th>)}</tr></thead>
            <tbody>
              {weeks.map((c) => (
                <tr key={c.week}>
                  <th scope="row">{fmtDay(c.week)}</th>
                  <td className="num">{c.size}</td>
                  {c.cells.map((v, k) => (
                    <td key={k} className={v == null ? 'is-none' : v > 0.45 ? 'is-dark' : ''} style={v == null ? undefined : { ['--v' as string]: v }} title={v == null ? 'Chưa tới' : `${Math.round(v * c.size)} / ${c.size} người`}>
                      {v == null ? '' : pct(v)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

// ---------- features and profile ----------

function Features({ list, active }: { list: Feature[]; active: number }) {
  const groups = [...new Set(list.map((f) => f.group))]
  const most = Math.max(1, active)
  return (
    <section className="a-card">
      <h2>Tính năng được dùng</h2>
      <p className="a-small">Số tài khoản đã dùng trong kỳ, trên {active} tài khoản hoạt động; lượt dùng gồm cả khách. Xếp theo luồng sản phẩm.</p>
      <div className="u-features">
        {groups.map((g) => (
          <div key={g}>
            <h3>{g}</h3>
            <ul>
              {list.filter((f) => f.group === g).map((f) => (
                <li key={f.key} className={!f.people && !f.uses ? 'is-zero' : ''}>
                  <span>{f.label}</span>
                  <span className="u-ladder__bar"><i style={{ width: `${Math.min(100, (f.people / most) * 100)}%` }} /></span>
                  <b>{f.people}</b>
                  <small>{!f.people && !f.uses ? 'chưa ai dùng' : f.uses == null ? 'người' : `người · ${f.uses.toLocaleString('vi-VN')} lượt`}</small>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </section>
  )
}

function Profile({ d }: { d: UsersOverview }) {
  const p = d.profile
  const LOGINS = [['google', 'Google', 'var(--ink)'], ['password', 'Email', 'var(--violet)'], ['both', 'Cả hai', 'var(--ok)'], ['none', 'Đăng nhập thử', 'var(--cov-part)']] as const
  const rows: [string, number][] = [
    ['Đã đồng ý điều khoản', p.terms], ['Có ảnh đại diện', p.fields.avatar], ['Có nickname (kết bạn được)', p.fields.nickname],
    ['Bật "nhớ cho lần sau"', p.remember], ['Phương tiện quen dùng', p.fields.usual_mobility], ['Thường đi cùng ai', p.fields.usual_companions], ['Thành phố nhà', p.fields.home_city],
  ]
  return (
    <section className="a-card">
      <h2>Tài khoản và hồ sơ</h2>
      <p className="a-small">Trên {p.of} tài khoản (không tính tài khoản đã xóa).</p>
      <h3 className="u-h3">Cách đăng nhập</h3>
      <div className="stack" role="img" aria-label={LOGINS.map(([k, l]) => `${l} ${p.login[k]}`).join(', ')}>
        {LOGINS.filter(([k]) => p.login[k]).map(([k, l, c]) => <i key={k} title={`${l}: ${p.login[k]}`} style={{ flexGrow: p.login[k], background: c }} />)}
      </div>
      <ul className="legend">{LOGINS.filter(([k]) => p.login[k]).map(([k, l, c]) => <li key={k}><i style={{ background: c }} />{l} <b>{p.login[k]}</b></li>)}</ul>
      <h3 className="u-h3">Hồ sơ đã điền</h3>
      <ul className="u-fill">
        {rows.map(([l, n]) => (
          <li key={l} className={n ? '' : 'is-zero'}>
            <span>{l}</span>
            <span className="u-ladder__bar"><i style={{ width: `${p.of ? (n / p.of) * 100 : 0}%` }} /></span>
            <b>{n}</b>
            <small>{pct(p.of ? n / p.of : null)}</small>
          </li>
        ))}
      </ul>
      <p className="a-small">Phương tiện và người đi cùng là prior của Trip; trống thì mỗi chuyến bắt đầu như người mới.</p>
    </section>
  )
}

// ---------- the people table ----------

type SortKey = 'who' | 'created_at' | 'last_seen' | 'active_days' | 'journeys' | 'confirmed' | 'furthest' | 'errors' | 'min_score'
const COLS: [SortKey, string, boolean][] = [
  ['who', 'Người dùng', false], ['created_at', 'Tham gia', false], ['last_seen', 'Hoạt động cuối', false], ['active_days', 'Ngày hoạt động', true],
  ['journeys', 'Hành trình', true], ['confirmed', 'Đã chốt', true], ['furthest', 'Tiến độ', false], ['errors', 'Lỗi', true], ['min_score', 'Điểm thấp nhất', true],
]
const PAGE = 50

function People({ rows, error, segment, setSegment }: { rows?: PersonRow[]; error?: string; segment: Segment; setSegment: (s: Segment) => void }) {
  const [q, setQ] = useState('')
  const [type, setType] = useState<'' | PersonType>('')
  const [sort, setSort] = useState<{ k: SortKey; desc: boolean }>({ k: 'last_seen', desc: true })
  const [shown, setShown] = useState(PAGE)
  const all = rows ?? []
  const counts = useMemo(() => Object.fromEntries((['account', 'guest'] as const).map((t) => [t, all.filter((r) => r.type === t).length])), [all])
  const out = useMemo(() => {
    const f = q.trim().toLowerCase()
    const val = (r: PersonRow): string | number => (sort.k === 'who' ? who(r).toLowerCase() : sort.k === 'min_score' ? (r.min_score ?? 99) : (r[sort.k] ?? ''))
    return all
      .filter((r) => (!type || r.type === type) && KEEP(r, segment) && (!f || [r.name, r.email, r.nickname, r.id].some((s) => s?.toLowerCase().includes(f))))
      .sort((a, b) => {
        const x = val(a), y = val(b)
        return (x < y ? -1 : x > y ? 1 : 0) * (sort.desc ? -1 : 1)
      })
  }, [all, q, type, segment, sort])
  const open = (r: PersonRow) => navigate(`/admin/users/${r.id}`)
  return (
    <>
      <div className="u-card-head">
        <h2>Danh sách người dùng</h2>
        <span className="a-small">{out.length.toLocaleString('vi-VN')} / {all.length.toLocaleString('vi-VN')} người</span>
      </div>
      <div className="a-toolbar u-people-tools">
        <input className="a-search" type="search" placeholder="Tìm tên, email, @nickname, id" aria-label="Tìm người dùng" value={q} onChange={(e) => (setQ(e.target.value), setShown(PAGE))} />
        <div className="seg" role="radiogroup" aria-label="Loại">
          <button role="radio" aria-checked={type === ''} onClick={() => setType('')}>Tất cả<small>{all.length}</small></button>
          {(['account', 'guest'] as const).filter((t) => counts[t]).map((t) => <button key={t} role="radio" aria-checked={type === t} onClick={() => setType(t)}>{TYPE[t]}<small>{counts[t]}</small></button>)}
        </div>
        <select className="a-search" aria-label="Nhóm" value={segment} onChange={(e) => (setSegment(e.target.value as Segment), setShown(PAGE))}>
          {SEGMENTS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>
      </div>
      {!rows ? <p className="a-muted">{error ? `Chưa đọc được (${error}).` : 'Đang tải…'}</p> : out.length === 0 ? <p className="a-empty">Không có ai khớp bộ lọc.</p> : (
        <div className="u-scroll">
          <table className="a-table u-people">
            <thead>
              <tr>
                {COLS.map(([k, l, num]) => (
                  <th key={k} className={num ? 'num' : ''} aria-sort={sort.k === k ? (sort.desc ? 'descending' : 'ascending') : 'none'}>
                    <button className="u-sort" onClick={() => setSort((s) => ({ k, desc: s.k === k ? !s.desc : k !== 'who' }))}>
                      {l}{sort.k === k && <span aria-hidden="true">{sort.desc ? ' ↓' : ' ↑'}</span>}
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {out.slice(0, shown).map((r) => (
                <tr key={r.id} tabIndex={0} onClick={() => open(r)} onKeyDown={(e) => { if (e.key === 'Enter') open(r) }}>
                  <td>
                    <div className="u-who">
                      <span className={`u-avatar u-avatar--${r.type}`} aria-hidden="true">{initials(r)}</span>
                      <span>
                        <b>{who(r)}</b>
                        <small>
                          {TYPE[r.type]}{r.type === 'account' ? ` · ${LOGIN[r.login]}` : ''}{r.nickname ? ` · @${r.nickname}` : ''}
                          {r.test && <em className="u-tag">thử</em>}{r.status !== 'active' && <em className="u-tag u-tag--bad">{r.status === 'deleted' ? 'đã xóa' : r.status}</em>}
                        </small>
                      </span>
                    </div>
                  </td>
                  <td className="nowrap">{fmtDate(r.created_at)}</td>
                  <td className="nowrap" title={r.last_seen ?? ''}>{ago(r.last_seen)}</td>
                  <td className="num">{r.active_days}</td>
                  <td className="num">{r.journeys}</td>
                  <td className="num">{r.confirmed || '—'}</td>
                  <td><Steps at={r.furthest} /></td>
                  <td className={`num${r.errors ? ' u-bad' : ''}`}>{r.errors || '—'}</td>
                  <td className={`num${r.min_score != null && r.min_score <= 2 ? ' u-bad' : ''}`}>{r.min_score ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {out.length > shown && <button className="a-btn a-btn--ghost u-more" onClick={() => setShown((s) => s + PAGE)}>Xem thêm {Math.min(PAGE, out.length - shown)} người</button>}
    </>
  )
}

export function Steps({ at }: { at: number }) {
  return (
    <span className="u-steps" role="img" aria-label={`Tới bước ${STEPS[at]}`} title={STEPS[at]}>
      {STEPS.map((s, i) => <i key={s} className={i <= at ? 'is-on' : ''} />)}
      <small>{STEPS[at]}</small>
    </span>
  )
}
