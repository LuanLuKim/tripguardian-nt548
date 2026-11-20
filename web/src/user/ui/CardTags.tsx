import type { Card } from '../pd/types'
import { cardLines } from './cardLines'
import { Hint } from './common'
import { Icon } from './icons'

// A card's lines as short tags of two kinds: *lợi* (what the place has going for it: a match, a facility, a pet-friendly yes) and *hại*
// (what to know before choosing: a trade-off, a doubt, something that does not match). Pet policy is a plain attribute, never a warning:
// "allowed" is a lợi, the rest is a grey note. The full sentence (with its count of people) is in the tooltip over the tag.
export interface Tag { kind: 'pro' | 'con' | 'note'; short: string; full: string }

const MAX = 30 // characters of a tag; longer ends in …
const TRAIL = [/,\s*điều bạn muốn tránh$/i, /\s*\(ước tính\)$/i, /[.;,\s]+$/]

// The claim without how many people said so: "Có chỗ đỗ xe, 12 người nhắc" -> "Có chỗ đỗ xe"; "Có bánh căn bạn muốn · theo menu" -> "Có bánh căn"; "Độ đông: đông" (the label repeats its value) -> "Đông".
const SOURCE = /\s·\s(?:theo|\d).*$/i // "· theo menu": where it was read is for the sheet
const WANTED = /\s+bạn (?:muốn|thích|tìm)$/i // "Có bánh căn bạn muốn": the card is already the user's list
const COUNT = /,?\s*(?:theo\s+)?\d+\s+người(?:\s+nhắc)?$/i
const plain = (x: string) => x.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
const upper = (x: string) => x.charAt(0).toUpperCase() + x.slice(1)
export function cleanTag(text: string): string {
  let s = text.trim().replace(COUNT, '').replace(SOURCE, '').replace(WANTED, '')
  const m = /^([^:]+):\s*([^:]+)$/.exec(s)
  if (m && plain(m[1]).includes(plain(m[2].trim()))) s = m[2].trim()
  return upper(s.replace(/[.;,\s]+$/, ''))
}

export function shortTag(text: string): string {
  let s = cleanTag(text)
  for (const r of TRAIL) s = s.replace(r, '')
  s = s.replace(/^Chưa rõ có\s+/i, 'Chưa rõ ').replace(/^Không hợp điều kiện của bạn:\s*/i, 'Không hợp: ').replace(/^Chưa xác minh:\s*/i, 'Chưa rõ: ')
    .replace(/^Gần (.+?), ≈(\d+) phút$/, 'Gần $1 · $2′').replace(/\s*≈\s*(\d+) phút$/, ' · $1′').replace(/;\s*/g, ', ')
  s = upper(s)
  if (s.length <= MAX) return s
  const cut = s.slice(0, MAX - 1)
  return cut.slice(0, Math.max(12, cut.lastIndexOf(' '))).replace(/[,\s]+$/, '') + '…'
}

const tag = (kind: Tag['kind'], text: string): Tag => ({ kind, full: cleanTag(text), short: shortTag(text) })
const unique = (tags: Tag[]) => tags.filter((t, i) => t.short && tags.findIndex((x) => x.short === t.short) === i)

export function cardTags(c: Card, warn?: string): Tag[] {
  const { why, trade, alerts, pets } = cardLines(c)
  const petOk = (t: string) => /^Cho mang/i.test(t)
  return unique([
    ...why.map((w) => tag('pro', w.text)),
    ...pets.filter((p) => petOk(p.text)).map((p) => tag('pro', p.text)),
    ...[trade, ...alerts, warn].filter((t): t is string => !!t).map((t) => tag('con', t)),
    ...pets.filter((p) => !petOk(p.text)).map((p) => tag('note', p.text)),
  ])
}

// Same two kinds for a stay: only what the stay's own record says against it (it has no "why" lines).
export function stayTags(cons: (string | null | undefined)[]): Tag[] {
  return unique(cons.filter((t): t is string => !!t).map((t) => tag('con', t)))
}

const ICON = { pro: 'check', con: 'warn', note: 'info' } as const

// One line, two chips: a lợi chip (green) and a hại chip (yellow). Each holds all its tags as short words set apart by commas, so the hại never
// drops out of the frame for want of room: the two share the line, and a chip that is too long ends in "…" (the tooltip over it has every
// tag whole, one per row, in a light card; the kind is its icon's colour, never a word). With no hại (or no lợi) the grey pet note takes the place.
function Tip({ tags }: { tags: Tag[] }) {
  return <ul className="tg-ctip">{tags.map((t) => <li key={t.kind + t.short} className={`is-${t.kind}`}><Icon name={ICON[t.kind]} size={14} strokeWidth={2.2} /><span>{t.full}</span></li>)}</ul>
}

const PER_CHIP = 4

export function CardTags({ tags }: { tags: Tag[] }) {
  if (!tags.length) return null
  const of = (k: Tag['kind']) => tags.filter((t) => t.kind === k).slice(0, PER_CHIP)
  const chips: { kind: Tag['kind']; tags: Tag[] }[] = (['pro', 'con'] as const).map((kind) => ({ kind, tags: of(kind) })).filter((g) => g.tags.length)
  if (chips.length < 2 && of('note').length) chips.push({ kind: 'note', tags: of('note') })
  return (
    <ul className="tg-ctags" aria-label="Điểm lợi và điểm hại">
      {chips.map((g) => (
        <li key={g.kind} className={`is-${g.kind}`}>
          <Hint tone="light" className={`tg-ctag is-${g.kind}`} label={<Tip tags={g.tags} />}>
            <Icon name={ICON[g.kind]} size={13} strokeWidth={2.2} /><span>{g.tags.map((t) => t.short).join(', ')}</span>
          </Hint>
        </li>
      ))}
    </ul>
  )
}
