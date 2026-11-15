import { navigate } from '../../router'
import { fmtTime, useAnalytics, type PersonDetail } from '../analytics'
import { ago, fmtDate, fmtDay, initials, LOGIN, STEPS, TYPE, who } from './Users'

// One person (docs/Role_Web_Functional_Design.md §3.9): account, how far they got, what they used, every journey
// (replay in Phiên chuyến đi), feedback and the latest events. Admin reads all of it; nothing here writes.
const STAGE: Record<string, string> = { trip: 'Hiểu chuyến', decision: 'Chọn nơi', planning: 'Lịch trình' }
const KEYS = ['signup', 'journey', 'compiled', 'chose', 'confirm', 'feedback', 'again']
const MOBILITY: Record<string, string> = { motorbike: 'Xe máy', car: 'Ô tô', walk: 'Không xe riêng' }
const COMPANIONS: Record<string, string> = { solo: 'Một mình', partner: 'Người yêu', friends: 'Bạn bè', kids: 'Có trẻ nhỏ', parents: 'Bố mẹ' }
const SCORE: Record<string, string> = { fit: 'Hợp', clear: 'Rõ', confident: 'Tin', realistic: 'Thực tế' }

export function UserDetail({ id }: { id: string }) {
  const { data: p, error } = useAnalytics<PersonDetail>(`users/${id}`)
  const back = <button className="a-btn a-btn--ghost" onClick={() => navigate('/admin/users')}>Về danh sách</button>
  if (!p) return <div className="a-page"><header className="a-head"><div><h1>Người dùng</h1></div>{back}</header><section className="a-card"><p className="a-muted">{error === 'not found' ? 'Không có người dùng này.' : error ?? 'Đang tải…'}</p></section></div>
  const lastStep = STEPS[p.furthest]
  return (
    <div className="a-page users">
      <header className="a-head">
        <div className="u-who u-who--big">
          <span className={`u-avatar u-avatar--${p.type}`} aria-hidden="true">{initials(p)}</span>
          <div>
            <h1>{who(p)}</h1>
            <p>
              {[TYPE[p.type], p.type === 'account' ? LOGIN[p.login] : null, p.email, p.nickname ? `@${p.nickname}` : null].filter(Boolean).join(' · ')}
              {p.test && <em className="u-tag">tài khoản thử</em>}{p.status !== 'active' && <em className="u-tag u-tag--bad">{p.status === 'deleted' ? `đã xóa ${fmtDate(p.deleted_at)}` : p.status}</em>}
            </p>
            <p className="a-small">Tham gia {fmtDate(p.created_at)} · hoạt động cuối {ago(p.last_seen)} · đăng nhập cuối {fmtTime(p.last_login_at)} · <code>{p.id}</code></p>
          </div>
        </div>
        {back}
      </header>

      <div className="tiles">
        <div className="tile"><span>Hành trình</span><b>{p.journeys}</b><small>{p.confirmed} đã chốt lịch</small></div>
        <div className="tile"><span>Ngày có hoạt động</span><b>{p.active_days}</b><small>tới bước “{lastStep}”</small></div>
        <div className={`tile${p.errors ? ' tile--warn' : ''}`}><span>Lỗi / fallback gặp phải</span><b>{p.errors}</b><small>{p.errors_in_range} trong 30 ngày qua</small></div>
        <div className="tile"><span>Phản hồi sau chuyến</span><b>{p.feedback}</b><small>{p.min_score == null ? 'chưa chấm' : `điểm thấp nhất ${p.min_score}`}</small></div>
      </div>

      <div className="u-grid u-grid--wide">
        <section className="a-card">
          <h2>Hoạt động 26 tuần qua</h2>
          <Calendar days={p.daily} />
          <h3 className="u-h3">Các bước đã tới</h3>
          <ol className="u-reached">
            {KEYS.map((k, i) => <li key={k} className={p.reached.includes(k) ? 'is-on' : ''}><span aria-hidden="true">{p.reached.includes(k) ? '✓' : i + 1}</span>{STEPS[i]}</li>)}
          </ol>
        </section>
        <section className="a-card">
          <h2>Hồ sơ và đồng ý</h2>
          <dl className="u-dl">
            <dt>Điều khoản</dt><dd>{p.profile.terms ? `đã đồng ý bản ${p.profile.terms}` : 'chưa'}</dd>
            <dt>Nhớ cho lần sau</dt><dd>{p.profile.remember ? 'bật' : 'tắt'}</dd>
            <dt>Phương tiện quen</dt><dd>{p.profile.usual_mobility ? MOBILITY[p.profile.usual_mobility] ?? p.profile.usual_mobility : '—'}</dd>
            <dt>Thường đi cùng</dt><dd>{p.profile.usual_companions ? COMPANIONS[p.profile.usual_companions] ?? p.profile.usual_companions : '—'}</dd>
            <dt>Thành phố nhà</dt><dd>{p.profile.home_city ?? '—'}</dd>
            <dt>Ảnh đại diện</dt><dd>{p.profile.avatar ? 'có' : 'không'}</dd>
          </dl>
          <h3 className="u-h3">Cá nhân, xã hội, trong chuyến</h3>
          <dl className="u-dl">
            <dt>Đã lưu</dt><dd>{p.counts.saved} mục</dd>
            <dt>Bạn bè</dt><dd>{p.counts.friends}</dd>
            <dt>Tin nhắn đã gửi</dt><dd>{p.counts.messages}{p.counts.shared ? `, ${p.counts.shared} kèm lịch trình` : ''}</dd>
            <dt>Chuyến đã lưu (Hôm nay)</dt><dd>{p.counts.trips} · {p.counts.checkins} check-in</dd>
            <dt>Thông báo</dt><dd>{p.counts.notified} đã gửi · {p.counts.opened} đã mở</dd>
          </dl>
        </section>
      </div>

      <div className="u-grid u-grid--wide">
        <section className="a-card">
          <h2>Hành trình ({p.journey_list.length})</h2>
          {!p.journey_list.length ? <p className="a-muted">Chưa có hành trình nào.</p> : (
            <div className="u-scroll">
              <table className="a-table a-table--compact u-people">
                <thead><tr><th>Hành trình</th><th>Bước</th><th>Tạo</th><th>Cập nhật</th><th className="num">Lỗi</th><th className="num">Điểm</th></tr></thead>
                <tbody>
                  {p.journey_list.map((j) => (
                    <tr key={j.id} tabIndex={0} onClick={() => navigate(`/admin/sessions/${j.id}`)} onKeyDown={(e) => { if (e.key === 'Enter') navigate(`/admin/sessions/${j.id}`) }}>
                      <td><code>{j.id}</code></td>
                      <td>{j.confirmed ? <span className="u-tag u-tag--ok">Đã chốt</span> : STAGE[j.stage] ?? j.stage}</td>
                      <td className="nowrap">{fmtTime(j.created_at)}</td>
                      <td className="nowrap">{ago(j.updated_at)}</td>
                      <td className={`num${j.errors ? ' u-bad' : ''}`}>{j.errors || '—'}</td>
                      <td className={`num${j.min_score != null && j.min_score <= 2 ? ' u-bad' : ''}`}>{j.min_score ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="a-small">Bấm một dòng để phát lại ở Phiên chuyến đi.</p>
        </section>
        <section className="a-card">
          <h2>Tính năng đã dùng</h2>
          <ul className="u-used">
            {p.features.map((f) => <li key={f.key} className={f.uses ? '' : 'is-zero'}><span>{f.label}</span><b>{f.uses ? f.uses.toLocaleString('vi-VN') : '—'}</b></li>)}
          </ul>
        </section>
      </div>

      <div className="u-grid u-grid--wide">
        <section className="a-card">
          <h2>Sự kiện gần nhất</h2>
          {!p.events.length ? <p className="a-muted">Không có.</p> : (
            <div className="u-scroll u-scroll--tall">
              <table className="a-table a-table--compact">
                <tbody>
                  {p.events.map((e, i) => {
                    const bad = 'error' in e.props || e.props.path === 'fallback'
                    return (
                      <tr key={i} className={bad ? 'a-note--bad' : ''}>
                        <td className="nowrap">{fmtTime(e.at)}</td>
                        <td className="nowrap"><code>{e.name}</code></td>
                        <td className="a-small">{Object.entries(e.props).filter(([k]) => k !== 'revision').map(([k, v]) => `${k}=${typeof v === 'object' ? JSON.stringify(v) : v}`).join(' ').slice(0, 160)}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>
        <section className="a-card">
          <h2>Phản hồi ({p.feedback_list.length})</h2>
          {!p.feedback_list.length ? <p className="a-muted">Chưa gửi phản hồi nào.</p> : (
            <ul className="u-feedback">
              {p.feedback_list.map((f, i) => (
                <li key={i}>
                  <p className="a-small">{fmtTime(f.at)} · <button className="a-link" onClick={() => navigate(`/admin/sessions/${f.journey_id}`)}>{f.journey_id}</button></p>
                  <div className="u-chips">{Object.entries(f.scores).map(([k, v]) => <code key={k} className={v <= 2 ? 'is-bad' : ''}>{SCORE[k] ?? k} {v}</code>)}</div>
                  {f.more_search_for?.length ? <p className="a-small">Còn phải tìm ở ngoài: {f.more_search_for.join(', ')}</p> : null}
                  {f.note && <blockquote>{f.note}</blockquote>}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  )
}

// 26 weeks × 7 days, Monday first; colour is the day's event count, every cell also says it in its label.
function Calendar({ days }: { days: { day: string; n: number }[] }) {
  const by = new Map(days.map((d) => [d.day, d.n]))
  const today = new Date(Date.now() + 7 * 3_600_000)
  const dow = (today.getUTCDay() + 6) % 7
  const start = new Date(today.getTime() - (25 * 7 + dow) * 86_400_000)
  const max = Math.max(1, ...days.map((d) => d.n))
  const cols: { day: string; n: number; future: boolean }[][] = []
  for (let w = 0; w < 26; w++) {
    cols.push([])
    for (let d = 0; d < 7; d++) {
      const t = new Date(start.getTime() + (w * 7 + d) * 86_400_000)
      const key = t.toISOString().slice(0, 10)
      cols[w].push({ day: key, n: by.get(key) ?? 0, future: t > today })
    }
  }
  const active = days.filter((d) => d.n).length
  const peak = days.reduce<{ day: string; n: number } | null>((a, b) => (!a || b.n > a.n ? b : a), null)
  return (
    <>
      <div className="u-cal" role="img" aria-label={`${active} ngày có hoạt động trong 26 tuần`}>
        {cols.map((c, w) => (
          <div key={w}>
            {c.map((d) => (
              <i key={d.day} title={`${fmtDay(d.day)}: ${d.n} sự kiện`}
                className={d.future ? 'is-future' : d.n ? '' : 'is-zero'} style={d.n ? { ['--v' as string]: 0.18 + 0.82 * Math.sqrt(d.n / max) } : undefined} />
            ))}
          </div>
        ))}
      </div>
      <p className="a-small">{active} ngày có hoạt động{peak?.n ? `, nhiều nhất ${fmtDay(peak.day)} (${peak.n} sự kiện)` : ''}. Ô đậm hơn = nhiều sự kiện hơn.</p>
    </>
  )
}
