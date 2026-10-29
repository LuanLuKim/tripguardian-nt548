import { featureLabel } from '../../../data/labels'
import { fmtMin } from '../../lib'
import type { View } from '../../planning/types'
import { Icon } from '../../ui/icons'
import { placeName } from './shared'
import '../../css/trust.css'

// How far the plan can be trusted (docs/PLANNING.md): what is estimated, where travel / weather / start-point facts came
// from and when, the usable time, and what the plan gave up. Every line comes from the view; a block with no data is hidden.

// Plain-language names of the data sources the backend reports; an unknown key is never shown raw (the "theo X" part is dropped).
const SOURCE: Record<string, string> = {
  osrm: 'dữ liệu đường bộ thực tế (OSRM)', 'open-meteo': 'dự báo Open-Meteo', climate: 'dữ liệu khí hậu nhiều năm', rough: 'khoảng cách đường chim bay',
}
const POINT: Record<string, string> = {
  user: 'vị trí do bạn nhập', corpus: 'vị trí lấy từ dữ liệu địa điểm của TripGuardian', nominatim: 'vị trí tra theo OpenStreetMap',
}
const UNPLACED: Record<string, string> = {
  no_record: 'chưa có dữ liệu địa điểm', not_plannable: 'không xếp được vào lịch', no_coordinates: 'chưa có tọa độ', no_visit_time: 'chưa rõ nên ghé bao lâu',
}
const by = (s: string) => (SOURCE[s] ? ` theo ${SOURCE[s]}` : '')
const at = (iso: string | null | undefined) => {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const p = (n: number) => String(n).padStart(2, '0')
  return ` · lấy lúc ${p(d.getHours())}:${p(d.getMinutes())} ${p(d.getDate())}/${p(d.getMonth() + 1)}`
}

export function TrustCard({ view }: { view: Pick<View, 'uncertainty' | 'provenance' | 'time_budget' | 'tradeoffs'> }) {
  const { uncertainty: u, provenance: pv, time_budget: tb, tradeoffs } = view
  const rows: { key: string; icon: 'route' | 'clock' | 'info' | 'pin' | 'rain'; text: string }[] = []
  if (tb && tb.total_minutes > 0) rows.push({ key: 'tb', icon: 'clock', text: `Thời gian dùng được khoảng ${fmtMin(tb.total_minutes)} trong ${tb.days} ngày (ngày đầu bắt đầu lúc đến nơi, ngày cuối kết thúc khi về).` })
  if (u?.estimated?.length) rows.push({ key: 'est', icon: 'info', text: 'Giờ di chuyển, thời lượng ghé và chi phí là ước lượng, không phải số chính xác.' })
  if (pv?.travel) {
    const rough = pv.travel.source === 'rough'
    rows.push({ key: 'tr', icon: 'route', text: rough
      ? 'Chưa lấy được đường thật, nên mọi thời gian đi lại đang ước lượng theo khoảng cách.'
      : `Thời gian đi lại${by(pv.travel.source)}${at(pv.travel.fetched_at)}${u && u.rough_pairs > 0 ? `; ${u.rough_pairs} chặng chưa có đường thật nên ước lượng theo khoảng cách` : ''}.` })
  }
  ;(pv?.weather ?? []).forEach((w, i) => rows.push({ key: `w${i}`, icon: 'rain', text: w.source === 'climate'
    ? 'Chưa có dự báo thật cho những ngày này, nên thời tiết dựa trên dữ liệu khí hậu nhiều năm.'
    : `Thời tiết${by(w.source)}${at(w.fetched_at)}; dự báo có thể đổi.` }))
  for (const [n, pt] of Object.entries(pv?.points ?? {})) {
    if (POINT[pt.source]) rows.push({ key: `p${n}`, icon: 'pin', text: `${pt.text}: ${POINT[pt.source]}${at(pt.fetched_at)}.` })
  }
  const gave = (tradeoffs ?? []).map((t) => t.kind === 'relaxed'
    ? `${placeName(t.place_id)}: bạn đồng ý nới ${t.features.map(featureLabel).join(', ')}.`
    : `${placeName(t.place_id)}: chưa xếp được (${UNPLACED[t.reason] ?? t.reason}).`)
  if (!rows.length && !gave.length) return null
  return (
    <section className="tg-sidecard tg-trustcard" aria-labelledby="tg-trust-h">
      <h2 id="tg-trust-h"><Icon name="info" size={18} /> Độ tin cậy của lịch</h2>
      {rows.length > 0 && <ul className="tg-trustcard__list">{rows.map((r) => <li key={r.key}><Icon name={r.icon} size={14} /><span>{r.text}</span></li>)}</ul>}
      {gave.length > 0 && <><h3 className="tg-trustcard__sub">Đã đánh đổi</h3><ul className="tg-trustcard__list is-warn">{gave.map((g, i) => <li key={i}><Icon name="warn" size={14} /><span>{g}</span></li>)}</ul></>}
    </section>
  )
}
