import { fmtVnd } from '../../lib'
import type { LodgingBudget } from '../../planning/types'
import { Icon } from '../../ui/icons'

// The lodging cost line of the plan's budget (src/planning/validate.py lodging_budget): its own line, apart from the places'
// spend. Over the lodging share of the budget is a warning, never a block. An unknown price says so instead of guessing.

const age = (h: number | null | undefined) => (h == null ? null : h < 1 ? 'vừa thấy' : h < 48 ? `thấy cách đây ${Math.round(h)} giờ` : `thấy cách đây ${Math.round(h / 24)} ngày`)

export function lodgingBasis(b: LodgingBudget): string {
  const n = b.nights[0]
  if (!n || n.price_vnd == null) return 'chưa có giá'
  const how = n.price_kind === 'dated' ? 'giá đúng ngày của chuyến' : 'giá tham khảo trên Google Maps, ngày khác'
  return [how, age(n.price_age_h)].filter(Boolean).join(', ')
}

export function LodgingCost({ budget }: { budget: LodgingBudget | null | undefined }) {
  if (!budget) return null
  const n = budget.nights[0]
  const nights = budget.nights.length
  const over = budget.over_budget === true
  return (
    <div className={`tg-it-foot__lodge${over ? ' is-over' : ''}`} role={over ? 'status' : undefined}>
      {over && <Icon name="warn" size={15} />}
      <span>Chỗ nghỉ</span>
      <b>{budget.total_vnd != null ? `≈ ${fmtVnd(budget.total_vnd)}` : 'Chưa có giá'}</b>
      <span>{n?.price_vnd != null ? `${nights} đêm × ${fmtVnd(n.price_vnd)} · ${lodgingBasis(budget)}` : 'Chưa biết giá đêm nên chưa tính'}</span>
      {over && budget.per_night_cap_vnd != null && n?.over_vnd != null && <em>Cao hơn phần ngân sách cho chỗ ở (~{fmtVnd(budget.per_night_cap_vnd)}/đêm) khoảng {fmtVnd(n.over_vnd)}/đêm. Lịch vẫn giữ nguyên.</em>}
    </div>
  )
}
