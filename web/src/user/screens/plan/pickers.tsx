import { fmtMin, fmtVnd, info, priceText } from '../../lib'
import { usePlanning } from '../../planning/planning'
import type { ItineraryDay } from '../../planning/types'
import { useUi } from '../../store'
import { lodgingSuggest } from '../../tu/api'
import type { Candidate } from './candidates'
import { PlacePanel, type PanelItem } from './panels'
import { shortDate } from './shared'

// The two lists of places Lịch trình opens from the right: where to sleep, and what to put in a day (add or swap).
// Each has a tab of the user's saved places next to the suggestions, and a search box.

const STAY = /(khách sạn|homestay|hostel|resort|villa|nhà nghỉ|căn hộ|lưu trú|biệt thự)/i
const stars = (r: number | null | undefined) => (r ? `★ ${r.toFixed(1)}` : null)

export function LodgingPicker({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { view, act, busy } = usePlanning()
  const saved = useUi((u) => u.saved)
  if (!view) return null
  const chosen = view.state.lodging_id
  const cands = view.lodging.candidates
  const take = async (action: Parameters<typeof act>[0]) => { if (await act(action)) onClose() }
  const action = (id: string, run: () => void): PanelItem['action'] => id === chosen
    ? { label: 'Đang chọn', icon: 'check', disabled: true, onClick: () => {} }
    : { label: chosen ? 'Đổi sang' : 'Chọn', icon: chosen ? 'swap' : 'plus', disabled: busy, onClick: run }
  const item = (c: (typeof cands)[number]): PanelItem => ({
    id: c.id, name: c.name,
    meta: [stars(c.rating), c.price_vnd ? `${fmtVnd(c.price_vnd)}/đêm` : 'Chưa có giá', c.avg_min != null ? `≈ ${fmtMin(c.avg_min)} tới các nơi đã chọn` : null].filter(Boolean).join(' · '),
    why: c.fit?.[0]?.text ?? c.why?.[0]?.text ?? null,
    action: action(c.id, () => { void take({ type: 'pick_lodging', id: c.id }) }),
  })
  const savedStays = saved.filter((id) => cands.some((c) => c.id === id) || STAY.test(info(id)?.category ?? ''))
  const savedItems = savedStays.map((id) => {
    const c = cands.find((x) => x.id === id)
    if (c) return item(c)
    const p = info(id)!
    return { id, name: p.name, meta: [stars(p.rating), p.area].filter(Boolean).join(' · '), action: action(id, () => { void take({ type: 'pick_lodging', id }) }) } satisfies PanelItem
  })
  return (
    <PlacePanel open={open} onClose={onClose} kicker="Chỗ nghỉ" title="Chọn chỗ nghỉ" placeholder="Tìm chỗ nghỉ theo tên, địa chỉ"
      context="Mỗi ngày bắt đầu và kết thúc ở chỗ nghỉ; chọn một chỗ để lịch tính đường đi sáng và tối."
      tabs={[
        { id: 'suggest', label: 'Gợi ý', items: cands.map(item), empty: view.lodging.status === 'pending' ? 'Đang tìm chỗ nghỉ hợp với chuyến…' : 'Chưa có gợi ý. Bạn thử tìm theo tên.' },
        { id: 'saved', label: 'Đã lưu', items: savedItems, empty: 'Bạn chưa lưu chỗ nghỉ nào. Bấm hình trái tim ở một chỗ nghỉ để lưu.' },
      ]}
      remote={async (q, signal) => (await lodgingSuggest(q, signal)).map((h) => ({
        id: h.id ?? `${h.lat},${h.lng}`, name: h.text, meta: [stars(h.rating), h.address].filter(Boolean).join(' · '),
        action: action(h.id ?? '', () => { void take(h.kind === 'corpus' && h.id ? { type: 'pick_lodging', id: h.id } : { type: 'set_lodging', text: h.text, lat: h.lat, lng: h.lng }) }),
      }))} />
  )
}

// Add a place to a day, or swap one for another. "Chọn" only asks for a preview of the change (Plan.tsx); the day is not touched
// until the preview is applied. The server swaps and adds only a place of the selection or of the checked backup pool; a saved
// place outside both is chosen in Lựa chọn first and the plan is built again (`onAddOutside`).
export function PlaceSwapPicker({ open, onClose, day, replacing, candidates, inPlan, busy, onPick, onAddOutside }: {
  open: boolean; onClose: () => void; day: ItineraryDay | undefined; replacing: string | null; candidates: Candidate[]; inPlan: Set<string>; busy: boolean
  onPick: (c: Candidate) => void; onAddOutside: (id: string) => void
}) {
  const saved = useUi((u) => u.saved)
  const target = replacing ? info(replacing)?.name ?? replacing : null
  const item = (c: Candidate): PanelItem => {
    const p = info(c.id)
    const price = priceText(p?.price)
    return {
      id: c.id, name: c.name,
      meta: [p?.category, p?.area, stars(p?.rating), price ? `≈ ${price}` : null].filter(Boolean).join(' · '),
      why: c.forThis ? `Hợp để thay ${target}` : c.why ?? (c.from === 'selection' ? 'Nơi bạn đã chọn, chưa có trong lịch' : 'Dự phòng đã kiểm tra'),
      warns: c.warnings?.map((w) => w.text),
      action: { label: replacing ? 'Đổi' : 'Thêm', icon: replacing ? 'swap' : 'plus', disabled: busy, onClick: () => onPick(c) },
    }
  }
  const savedItems = saved.filter((id) => !inPlan.has(id) && info(id)).map((id): PanelItem => {
    const c = candidates.find((x) => x.id === id)
    if (c) return item(c)
    const p = info(id)!
    return { id, name: p.name, meta: [p.category, p.area, stars(p.rating)].filter(Boolean).join(' · '), note: 'Chưa nằm trong lựa chọn của chuyến: thêm sẽ chọn nơi này và xếp lại lịch.', action: { label: 'Thêm', icon: 'plus', disabled: busy, onClick: () => onAddOutside(id) } }
  })
  return (
    <PlacePanel open={open} onClose={onClose} kicker={target ? 'Đổi trải nghiệm' : 'Thêm trải nghiệm'} title={target ? `Thay ${target}` : `Thêm vào ngày ${day?.day ?? ''}`} placeholder="Tìm nơi muốn ghé"
      context={day ? <>{target ? `Thay trong ngày ${day.day}` : `Ngày ${day.day} · ${shortDate(day.date, day.day)}`} · {candidates.length} nơi có thể đưa vào lịch</> : undefined}
      tabs={[
        { id: 'suggest', label: 'Gợi ý', items: candidates.map(item), empty: 'Chưa còn nơi nào để thêm. Bạn chọn thêm nơi ở bước Lựa chọn.' },
        { id: 'saved', label: 'Đã lưu', items: savedItems, empty: 'Bạn chưa lưu nơi nào ngoài lịch này. Bấm hình trái tim ở một nơi để lưu.' },
      ]} />
  )
}
