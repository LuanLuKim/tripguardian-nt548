// Posts about places ("Bài viết"): the store behind the search, the results page, the reader and the composer.
// There is no harness route for posts yet, so this keeps them in this browser (localStorage) next to a few sample posts
// (`demo: true`, shown with a "Bài mẫu" tag) and the editorial posts TripGuardian wrote from the corpus
// (/data/posts.json, `editorial: true`, web/scripts/export_posts.py). A post always points at a place that exists in the snapshot: a sample whose place
// is missing from it is not shown, and the composer only offers places the snapshot has.
import { useSyncExternalStore } from 'react'
import { placeById } from '../../data/store'
import { info } from '../lib'
import { fold } from '../search'
import { FEATURED } from './featured'

export type Block = { t: 'p' | 'h' | 'q'; text: string } | { t: 'img'; src: string; cap: string } | { t: 'tour'; title: string; ids: string[] } // tour: a gallery of the places that have a 3D model
export type UserBlock = Exclude<Block, { t: 'tour' }> // what the composer makes: no gallery block
export type Vis = 'public' | 'friends' | 'me'
export const REACTS = [
  { k: 'like', label: 'Thích' },
  { k: 'love', label: 'Yêu thích' },
  { k: 'haha', label: 'Haha' },
  { k: 'wow', label: 'Wow' },
  { k: 'sad', label: 'Buồn' },
  { k: 'thanks', label: 'Hữu ích' },
] as const
export type ReactKey = (typeof REACTS)[number]['k']
export interface Facts { when: string; who: string; how: string; cost: string }
export interface Comment { id: string; name: string; text: string; at: number; mine?: boolean; reply?: boolean; likes: number }
export interface Post {
  id: string
  placeId: string
  title: string
  blocks: Block[]
  tags: string[]
  author: string
  mine?: boolean
  at: number
  vis: Vis
  facts: Partial<Facts>
  reacts: Partial<Record<ReactKey, number>>
  comments: Comment[]
  demo?: boolean
  editorial?: boolean // written by TripGuardian from the corpus' evidence (corpus intro posts); never a person
  featured?: boolean // pinned above the others, drawn as a banner (community/featured.ts)
  sources?: { domain: string; url?: string; title?: string }[]
  reviewCount?: number
  consent?: boolean // the author lets TripGuardian learn from this public post (kept for the harness to honour once posts live there)
}
export interface Draft { placeId: string | null; title: string; blocks: UserBlock[]; tags: string[]; vis: Vis; facts: Partial<Facts>; consent: boolean; at: number }

// ---------- sample posts ----------

const DAPHU = '0x31716dd936f3374d:0x273b69e7fc5479a2'
const CAUDAT = '0x317116dda7eb76c3:0x653f7aed2c2bff4e'
const PANORAMA = '0x317111f95f49005b:0x80d8908e8687507b'
const HXH = '0x31711321284ed77f:0x7752634a02e162e9'
const MONGMO = '0x317112bcf31cf46b:0x237bdec53ed852e3'
const CHODEM = '0x317113ff4e41e7c3:0x21cff9ad21a7243c'

const MIN = 60_000
const ago = (min: number) => Date.now() - min * MIN
const c = (id: string, name: string, text: string, min: number, likes = 0, reply = false): Comment => ({ id, name, text, at: ago(min), likes, reply })

const SEED: Post[] = [
  {
    id: 'demo-daphu-1', placeId: DAPHU, demo: true, author: 'Linh Trần', at: ago(4), vis: 'public',
    title: 'Dậy 4h30 để thấy biển mây Đa Phú, có đáng không?',
    tags: ['săn mây', 'đồi đa phú', 'sáng sớm'],
    facts: { when: 'Cuối tháng 10', who: '2 người', how: 'Xe máy', cost: '~ 120.000đ' },
    reacts: { love: 9, like: 11, wow: 4 },
    blocks: [
      { t: 'p', text: 'Mình không phải người dậy sớm. Báo thức 4h30 reo lần thứ ba thì mình bắt đầu hỏi lại mình: biển mây mà ai cũng khoe, rốt cuộc có đáng đánh đổi một giấc ngủ không?' },
      { t: 'img', src: 'cover:0', cap: 'Mây tràn lên đồi lúc 5h25' },
      { t: 'p', text: 'Đường lên đồi tối và hơi dốc, đèn xe chỉ soi được vài mét sương. Nhưng đến khoảng 5h20, khi mình vừa đứng yên ở rìa đồi thông, lớp mây bắt đầu tràn lên từ phía thung lũng, chậm đến mức phải nhìn một lúc mới nhận ra nó đang di chuyển.' },
      { t: 'q', text: 'Mình quên mất cái lạnh trong khoảng mười phút. Rồi mặt trời lên, và mọi thứ ngả sang màu mật ong.' },
      { t: 'img', src: 'cover:1', cap: 'Lối đi giữa rừng thông, khoảng 5h40' },
      { t: 'p', text: 'Lời khuyên nhỏ: mang áo gió dày hơn bạn nghĩ, đến sớm hơn giờ mặt trời mọc ít nhất 40 phút, và đừng kỳ vọng nếu đêm trước trời quang hoàn toàn. Hôm mình đi, độ ẩm cao nên mây dày; một bạn đi hôm sau thì chỉ thấy sương mỏng.' },
    ],
    comments: [
      c('d1a', 'Khánh Huyền', 'Cảm ơn bạn, mình đang phân vân giữa Đa Phú và Cầu Đất. Đi xe máy lên có khó không?', 2880, 3),
      c('d1b', 'Linh Trần', 'Đường dốc nhưng đi chậm thì ổn, nhớ bật đèn vì sương dày.', 2800, 5, true),
      c('d1c', 'Hoàng Nam', 'Tuần trước mình lên đúng giờ này mà chỉ thấy sương. Chắc phải xem độ ẩm đêm trước như bài của anh Khôi.', 5760, 2),
    ],
  },
  {
    id: 'demo-daphu-2', placeId: DAPHU, demo: true, author: 'Minh Khôi', at: ago(120), vis: 'public',
    title: 'Ba lần săn mây thất bại và lần thứ tư',
    tags: ['săn mây', 'kinh nghiệm', 'đồi đa phú'],
    facts: { when: 'Tháng 11', who: 'Đi một mình', how: 'Xe máy' },
    reacts: { like: 24, thanks: 17 },
    blocks: [
      { t: 'p', text: 'Cả ba lần đầu mình đều đi hôm trời quang, không có gì ngoài sương mỏng. Lần thứ tư mình xem dự báo độ ẩm đêm trước rồi mới quyết định, và đó là lần duy nhất mây thật sự có mặt.' },
      { t: 'h', text: 'Mình kiểm tra gì trước khi đi' },
      { t: 'p', text: 'Độ ẩm buổi tối trên 85%, trời không mưa lớn, gió nhẹ. Nếu đêm trước trời quang và khô thì mình ngủ tiếp, không cố.' },
      { t: 'img', src: 'cover:2', cap: 'Lần thứ tư: mây dày đến mức che mất cả rìa đồi' },
    ],
    comments: [c('d2a', 'Thu Hà', 'Mẹo kiểm tra độ ẩm hay quá, mình sẽ thử.', 600, 4)],
  },
  {
    id: 'demo-daphu-3', placeId: DAPHU, demo: true, author: 'Thu Hà', at: ago(1440), vis: 'friends',
    title: 'Đồi Đa Phú cho người ngại dậy sớm',
    tags: ['đi cùng gia đình', 'đồi đa phú'],
    facts: { when: 'Cuối tuần', who: '4 người', how: 'Ô tô' },
    reacts: { love: 12 },
    blocks: [
      { t: 'p', text: 'Có người nói phải 4h sáng, thật ra mình lên lúc 6h kém vẫn kịp thấy mây còn đọng ở chân đồi. Bố mẹ mình đi cùng và vẫn ổn, chỉ cần mang thêm áo ấm.' },
      { t: 'img', src: 'cover:3', cap: '' },
    ],
    comments: [],
  },
  {
    id: 'demo-caudat-1', placeId: CAUDAT, demo: true, author: 'Bảo Ngọc', at: ago(4320), vis: 'public',
    title: 'Một sáng thứ Tư ở đồi chè Cầu Đất',
    tags: ['săn mây', 'đồi chè', 'cầu đất'],
    facts: { when: 'Giữa tuần', who: '2 người', how: 'Xe máy' },
    reacts: { love: 18 },
    blocks: [
      { t: 'p', text: 'Đi giữa tuần nên gần như không có ai. Mây thấp, chè xanh mướt, mình ngồi uống trà nóng đến gần 8h mà không phải nhường chỗ chụp ảnh cho ai.' },
      { t: 'img', src: 'cover:0', cap: 'Những luống chè lúc 6h30' },
      { t: 'q', text: 'Có những nơi chỉ cần đến đúng ngày thường là đã khác hẳn.' },
    ],
    comments: [c('c1a', 'An Phương', 'Giữa tuần quả là lựa chọn đúng, cuối tuần ở đây rất đông.', 4000, 2)],
  },
  {
    id: 'demo-caudat-2', placeId: CAUDAT, demo: true, author: 'Đức Vĩnh', at: ago(7200), vis: 'public',
    title: 'Đi Cầu Đất bằng xe máy: đoạn nào cần chú ý',
    tags: ['xe máy', 'cầu đất', 'hậu cần'],
    facts: { when: 'Tháng 10', who: '1 người', how: 'Xe máy' },
    reacts: { like: 9 },
    blocks: [
      { t: 'p', text: 'Đường đèo buổi sáng còn sương, mình đi chậm và bật đèn. Ghi lại vài chỗ mình thấy cần để ý: các khúc cua gắt, đoạn đường ướt khi sương chưa tan, và nên đổ đầy xăng trước khi rời trung tâm.' },
      { t: 'img', src: 'cover:1', cap: '' },
    ],
    comments: [],
  },
  {
    id: 'demo-panorama-1', placeId: PANORAMA, demo: true, author: 'An Phương', at: ago(10080), vis: 'public',
    title: 'Săn mây Panorama: bài học về giờ đến',
    tags: ['săn mây', 'cầu đất', 'sáng sớm'],
    facts: { when: 'Cuối tuần', who: '3 người' },
    reacts: { like: 5, wow: 2 },
    blocks: [
      { t: 'p', text: 'Đến lúc 6h30 thì mây đã tan quá nửa. Lần sau mình sẽ đến trước giờ mặt trời mọc, vì mây đẹp nhất là lúc trời mới hửng.' },
      { t: 'img', src: 'cover:0', cap: '' },
    ],
    comments: [c('p1a', 'Gia Bảo', 'Mình cũng đến muộn mất nửa tiếng, tiếc quá.', 9000, 1)],
  },
  {
    id: 'demo-hxh-1', placeId: HXH, demo: true, author: 'Gia Bảo', at: ago(2880), vis: 'public',
    title: 'Một vòng hồ lúc 6 giờ sáng',
    tags: ['đi bộ', 'hồ xuân hương', 'sáng sớm'],
    facts: { when: 'Tháng 11', who: '2 người', how: 'Đi bộ' },
    reacts: { love: 14, like: 8 },
    blocks: [
      { t: 'p', text: 'Hồ lúc sáng sớm yên hơn mình tưởng. Vài người chạy bộ, vài người ngồi cà phê ven hồ, mặt nước còn mỏng sương. Đi hết một vòng chậm rãi mất khoảng một tiếng rưỡi.' },
      { t: 'img', src: 'cover:0', cap: 'Mặt hồ khoảng 6h15' },
      { t: 'p', text: 'Nếu chỉ có một buổi ở Đà Lạt, mình sẽ dành buổi sáng này thay cho một điểm tham quan đông người.' },
    ],
    comments: [],
  },
  {
    id: 'demo-hxh-2', placeId: HXH, demo: true, author: 'Khánh Huyền', at: ago(14400), vis: 'public',
    title: 'Đạp vịt hay đi bộ quanh hồ?',
    tags: ['hồ xuân hương', 'đi cùng bạn bè'],
    facts: { when: 'Cuối tuần', who: '5 người' },
    reacts: { haha: 6, like: 7 },
    blocks: [
      { t: 'p', text: 'Nhóm mình tranh cãi mãi rồi chia đôi: ba người đạp vịt, hai người đi bộ rồi gặp nhau ở bên kia hồ. Cách này vừa đủ vui vừa không ai phải nhường.' },
    ],
    comments: [],
  },
  {
    id: 'demo-mongmo-1', placeId: MONGMO, demo: true, author: 'Hoàng Nam', at: ago(20160), vis: 'public',
    title: 'Đồi Mộng Mơ cuối tuần: nên đi giờ nào',
    tags: ['đồi mộng mơ', 'chụp ảnh'],
    facts: { when: 'Cuối tuần', who: '2 người', how: 'Ô tô' },
    reacts: { like: 10 },
    blocks: [
      { t: 'p', text: 'Cuối tuần nơi này khá đông vào buổi chiều. Mình đến lúc nắng bắt đầu xiên, ánh sáng đẹp và bớt người hơn hẳn so với giữa trưa.' },
      { t: 'img', src: 'cover:0', cap: '' },
    ],
    comments: [],
  },
  {
    id: 'demo-chodem-1', placeId: CHODEM, demo: true, author: 'Thu Hà', at: ago(30240), vis: 'public',
    title: 'Chợ đêm Đà Lạt: ăn gì trước, mua gì sau',
    tags: ['chợ đêm', 'ăn uống'],
    facts: { when: 'Tháng 10', who: '3 người', how: 'Đi bộ' },
    reacts: { love: 7, like: 5 },
    blocks: [
      { t: 'p', text: 'Mình đi một vòng không mua gì để xem trước, rồi mới quay lại ăn. Cách này giúp mình bớt mua nhầm hàng đầu tiên gặp.' },
      { t: 'img', src: 'cover:0', cap: '' },
    ],
    comments: [],
  },
]

// ---------- the store ----------

interface State {
  mine: Post[]
  reacted: Record<string, ReactKey>
  comments: Record<string, Comment[]>
  saved: string[]
  draft: Draft | null
}
const KEY = 'tg.posts.v1'
const EMPTY: State = { mine: [], reacted: {}, comments: {}, saved: [], draft: null }
let state: State = load()
const subs = new Set<() => void>()

function load(): State {
  try {
    const raw = typeof localStorage === 'undefined' ? null : localStorage.getItem(KEY)
    return raw ? { ...EMPTY, ...JSON.parse(raw) } : EMPTY
  } catch { return EMPTY }
}
// false when the browser refuses the write (storage full): the caller tells the user instead of losing the post silently.
function set(patch: Partial<State>): boolean {
  const next = { ...state, ...patch }
  let ok = true
  try { localStorage.setItem(KEY, JSON.stringify(next)) } catch { ok = false }
  if (ok) { state = next; cache = null; subs.forEach((f) => f()) }
  return ok
}
const subscribe = (cb: () => void) => { subs.add(cb); return () => { subs.delete(cb) } }
addEventListener('storage', (e) => { if (e.key === KEY) { state = load(); cache = null; subs.forEach((f) => f()) } })

export const useStore = () => useSyncExternalStore(subscribe, () => state)

// ---------- selectors ----------

// Editorial posts: read once; until they land (or when the file is missing) the screen shows the others.
interface EditorialRow { id: string; placeId: string; title: string; tags: string[]; blocks: Block[]; sources?: Post['sources']; review_count?: number; author: string; at: string }
let editorial: Post[] = []
if (typeof fetch !== 'undefined') {
  fetch('/data/posts.json')
    .then((r) => (r.ok ? r.json() : { posts: [] }))
    .then((d: { posts?: EditorialRow[] }) => {
      editorial = (d.posts ?? []).map((p) => ({
        id: p.id, placeId: p.placeId, title: p.title, tags: p.tags, blocks: p.blocks, author: p.author || 'TripGuardian',
        at: Date.parse(p.at) || Date.now(), vis: 'public' as const, facts: {}, reacts: {}, comments: [], editorial: true,
        sources: p.sources, reviewCount: p.review_count,
      }))
      state = { ...state } // a new snapshot, so useStore readers render the new posts
      cache = null
      subs.forEach((f) => f())
    })
    .catch(() => {})
}

let cache: { state: State; posts: Post[] } | null = null
// Every post the viewer can read: the samples whose place is in the snapshot, then their own, newest first.
export function posts(s: State = state): Post[] {
  if (cache && cache.state === s) return cache.posts
  const seeds = [...SEED, ...editorial, FEATURED].filter((p) => placeById(p.placeId))
  const all = [...seeds, ...s.mine.filter((p) => placeById(p.placeId))].map((p) => ({ ...p, comments: [...p.comments, ...(s.comments[p.id] ?? [])] }))
  all.sort((a, b) => b.at - a.at)
  cache = { state: s, posts: all }
  return all
}
export const postById = (id: string) => posts().find((p) => p.id === id)
export const postsOf = (placeId: string) => posts().filter((p) => p.placeId === placeId)

export const reactionTotal = (p: Post, s: State = state) => Object.values(p.reacts).reduce((a, n) => a + (n ?? 0), 0) + (s.reacted[p.id] ? 1 : 0)
export const topReacts = (p: Post, s: State = state): ReactKey[] => {
  const n = { ...p.reacts } as Record<string, number>
  const mine = s.reacted[p.id]
  if (mine) n[mine] = (n[mine] ?? 0) + 1
  return Object.entries(n).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]).slice(0, 3).map(([k]) => k as ReactKey)
}

// A word-for-word read of a post, for the search.
const textOf = (p: Post) => fold([p.title, ...p.blocks.map((b) => (b.t === 'img' ? b.cap : b.t === 'tour' ? b.title : b.text)), ...p.tags, info(p.placeId)?.name ?? ''].join(' '))
// Whole words, so "săn" does not find "sáng". While typing (`live`) the last word may still be unfinished: a prefix of one.
const wordsIn = (hay: string, t: string[], live: boolean) => {
  const words = hay.split(' ')
  return t.length > 0 && t.every((w, i) => words.some((x) => x === w || (live && i === t.length - 1 && x.startsWith(w))))
}
export const matchesPost = (p: Post, q: string, live = false) => wordsIn(textOf(p), fold(q).split(' ').filter(Boolean), live)

export interface PlaceHit { placeId: string; posts: Post[]; comments: number; name: boolean }
// Places that have posts, matched by their own name or by what their posts say; name matches first, then the most posts.
export function searchPlaces(q: string, live = false): PlaceHit[] {
  const fq = fold(q)
  if (!fq) return []
  const byPlace = new Map<string, PlaceHit>()
  for (const p of posts()) {
    const byName = wordsIn(fold(info(p.placeId)?.name ?? ''), fq.split(' '), live)
    if (!byName && !matchesPost(p, q, live)) continue
    const hit = byPlace.get(p.placeId) ?? { placeId: p.placeId, posts: [], comments: 0, name: false }
    hit.name ||= byName
    byPlace.set(p.placeId, hit)
  }
  // Every post of a matched place is part of it, so the counts on the card are the place's, not only the matching ones.
  const out = [...byPlace.values()].map((h) => ({ ...h, posts: postsOf(h.placeId), comments: postsOf(h.placeId).reduce((n, p) => n + p.comments.length, 0) }))
  return out.sort((a, b) => Number(b.name) - Number(a.name) || b.posts.length - a.posts.length)
}

export interface TopicHit { tag: string; count: number }
export function searchTopics(q: string, live = false): TopicHit[] {
  const fq = fold(q)
  if (!fq) return []
  const n = new Map<string, number>()
  for (const p of posts()) for (const t of p.tags) n.set(t, (n.get(t) ?? 0) + 1)
  return [...n.entries()].filter(([t]) => { const ft = fold(t); return ft === fq || wordsIn(ft, fq.split(' '), live) || (` ${fq} `).includes(` ${ft} `) }).map(([tag, count]) => ({ tag, count })).sort((a, b) => b.count - a.count)
}
export function popularTags(limit = 8): string[] {
  const n = new Map<string, number>()
  for (const p of posts()) for (const t of p.tags) n.set(t, (n.get(t) ?? 0) + 1)
  return [...n.entries()].sort((a, b) => b[1] - a[1]).slice(0, limit).map(([t]) => t)
}

// ---------- writes ----------

export const reactTo = (id: string, k: ReactKey | null) => {
  const reacted = { ...state.reacted }
  if (k) reacted[id] = k
  else delete reacted[id]
  set({ reacted })
}
export const comment = (id: string, name: string, text: string, reply = false) =>
  set({ comments: { ...state.comments, [id]: [...(state.comments[id] ?? []), { id: `m${Date.now().toString(36)}`, name, text, at: Date.now(), mine: true, likes: 0, reply }] } })
export const togglePostSaved = (id: string) => set({ saved: state.saved.includes(id) ? state.saved.filter((x) => x !== id) : [...state.saved, id] })
export const saveDraft = (draft: Draft | null) => set({ draft })
export const publish = (p: Omit<Post, 'id' | 'at' | 'reacts' | 'comments' | 'mine' | 'demo'>) => {
  const post: Post = { ...p, id: `u${Date.now().toString(36)}`, at: Date.now(), reacts: {}, comments: [], mine: true }
  return set({ mine: [post, ...state.mine], draft: null }) ? post : null
}

// ---------- shared presentation helpers ----------

export function when(at: number) {
  const m = Math.max(0, Math.round((Date.now() - at) / MIN))
  if (m < 1) return 'Vừa đăng'
  if (m < 60) return `${m} phút trước`
  const h = Math.round(m / 60)
  if (h < 24) return `${h} giờ trước`
  const d = Math.round(h / 24)
  if (d === 1) return 'Hôm qua'
  if (d < 7) return `${d} ngày trước`
  if (d < 30) return `${Math.round(d / 7)} tuần trước`
  return new Date(at).toLocaleDateString('vi-VN')
}
export const initialsOf = (name: string) => name.trim().split(/\s+/).slice(-2).map((w) => w[0]).join('').toUpperCase() || '?'
// "cover:2" is the n-th photo of the post's place; anything else is the picture itself (a data: URL the author added).
export function srcOf(p: Pick<Post, 'placeId'>, src: string) {
  if (!src.startsWith('cover:')) return src
  const photos = info(p.placeId)?.photos ?? []
  return photos.length ? photos[Number(src.slice(6)) % photos.length].src : ''
}
export const photosOf = (p: Post) => {
  const own = p.blocks.flatMap((b) => (b.t === 'img' ? [{ src: srcOf(p, b.src), cap: b.cap }] : [])).filter((x) => x.src)
  if (own.length) return own
  const cover = srcOf(p, 'cover:0')
  return cover ? [{ src: cover, cap: '' }] : []
}
export const excerptOf = (p: Post, n = 150) => {
  const t = p.blocks.find((b) => b.t === 'p')
  const s = t && t.t !== 'img' && t.t !== 'tour' ? t.text.replace(/\*+/g, '') : ''
  return s.length > n ? `${s.slice(0, n).replace(/\s+\S*$/, '')}…` : s
}
export const readMinutes = (p: Post) => Math.max(1, Math.round(p.blocks.reduce((n, b) => n + (b.t === 'img' || b.t === 'tour' ? 0 : b.text.split(/\s+/).length), 0) / 200))
export const VIS: Record<Vis, string> = { public: 'Công khai', friends: 'Bạn bè', me: 'Chỉ mình tôi' }
export const FACT_LABELS: [keyof Facts, string][] = [['when', 'Đi ngày'], ['who', 'Đi cùng'], ['how', 'Phương tiện'], ['cost', 'Chi phí']]
