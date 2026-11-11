// How a place is named on screen. Google lists names the owners typed: all capitals, a tagline after a dash, hashtags,
// a Korean copy in brackets, a lower-case first letter. The corpus keeps the name as written; the user web shows this
// tidy form (a short name, capitalised, nothing cut mid-word). It never invents words: it only removes, re-cases and shortens.

const MAX = 44 // characters; longer names are cut at a word boundary
const NON_LATIN = /[\p{Script=Hangul}\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Thai}]/u
const lowerWord = new Set(['và', 'của', 'cho', 'ở', 'tại', 'the', 'of', 'and', '&'])

const letters = (s: string) => s.replace(/[^\p{L}]/gu, '')
const isUpper = (s: string) => { const l = letters(s); return l.length >= 3 && l === l.toLocaleUpperCase('vi-VN') }
const isLower = (s: string) => { const l = letters(s); return l.length >= 3 && l === l.toLocaleLowerCase('vi-VN') }
const cap = (w: string) => (w ? w.charAt(0).toLocaleUpperCase('vi-VN') + w.slice(1) : w)
// Capitals and lower case words alike become Title Case; a token with a digit (CS2, 2B) or with dots (A.B) keeps its shape.
const title = (s: string) => s.split(/(\s+)/).map((w, i) => (i % 2 || /\d|\./.test(w) ? w : (i > 0 && lowerWord.has(w.toLocaleLowerCase('vi-VN')) ? w.toLocaleLowerCase('vi-VN') : cap(w.toLocaleLowerCase('vi-VN'))))).join('')

// Two or more capital words in a row inside a mixed-case name ("Cá tầm Đà Lạt QUÁN ÁNH DƯƠNG") are shouting: Title Case them.
// A short ASCII word (KDL, BBQ, VIP) or a token with a digit is an acronym and stays.
const ACRONYM = /^[A-Z]{2,4}$|\d/
function retitleShouting(s: string) {
  const words = s.split(' ')
  const shout = (w: string) => !ACRONYM.test(w) && letters(w).length >= 2 && letters(w) === letters(w).toLocaleUpperCase('vi-VN')
  return words.map((w, i) => ((shout(w) && (shout(words[i - 1] ?? '') || shout(words[i + 1] ?? ''))) ? cap(w.toLocaleLowerCase('vi-VN')) : w)).join(' ')
}

export function displayName(raw: string): string {
  let s = raw.normalize('NFC')
  s = s.replace(/\([^)]*\)|\[[^\]]*]/g, (m) => (NON_LATIN.test(m) ? ' ' : m)) // a bracketed copy in another script
  s = s.replace(new RegExp(NON_LATIN.source, 'gu'), ' ')
  s = s.replace(/#\S+/g, ' ').replace(/[_]+/g, ' ')
  s = s.replace(/^[\s,;:.\-–—|/&]+/u, '')
  // A bracketed description after the name ("(Khách sạn trung tâm)", "(khu lưu trú …)") is dropped when a name stands before it.
  const bare = s.replace(/\s*\([^)]*\)?/g, ' ')
  if (letters(bare).length >= 4) s = bare
  // A tagline after a separator is not the name: "Mộc Hương spa - Dưỡng sinh", "QUÁN : Lẩu Nướng", "A | B", "A / B", "A -B", "A- B".
  const cut = s.search(/\s[-–—|/•·:]\s|\s[-–—](?=\S)|(?<=\S)[-–—]\s|\s:|:\s|\|/u)
  if (cut > 2) s = s.slice(0, cut)
  // A dot glued to the next word starts a new sentence: "CS2 .lẩu nướng", "tầm.Gà đồi", "stayDuong.dalat".
  const dot = s.search(/(?<=\p{Ll}{2})\.(?=\p{L})|\s\.(?=\p{L})/u)
  if (dot > 2) s = s.slice(0, dot)
  // Past about 28 characters a comma or a "chuyên …" tail is a description.
  if (s.length > 28) { const comma = s.indexOf(','); if (comma > 8) s = s.slice(0, comma) }
  s = s.replace(/\s+/g, ' ').replace(/[\s,;:.\-–—|/&]+$/u, '').replace(/^[\s,;:.\-–—|/]+/u, '').trim()
  if (!s) return raw.trim()
  if (isUpper(s) || isLower(s)) s = title(s)
  else s = cap(retitleShouting(s)) // a mixed name keeps its brand casing ("iPhone", "TripGuardian") but starts with a capital
  if (s.length > MAX) {
    const at = s.lastIndexOf(' ', MAX - 1)
    s = `${s.slice(0, at > 12 ? at : MAX - 1).replace(/[\s,;:.\-–—|/&]+$/u, '')}…`
  }
  return s
}

// Free text (an assistant's reply, a reason, a warning) quotes the corpus name. Every name that displayName changed is
// swapped back to its tidy form there too, longest first so a name never half-matches inside a longer one.
let swaps = new Map<string, string>()
let swapPattern: RegExp | null = null
export function setNameSwaps(pairs: [from: string, to: string][]) {
  swaps = new Map(pairs.filter(([from, to]) => from.length >= 6 && from !== to))
  const keys = [...swaps.keys()].sort((a, b) => b.length - a.length).map((k) => k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
  swapPattern = keys.length ? new RegExp(keys.join('|'), 'g') : null
}
export const tidyText = (s: string) => (swapPattern && s.length >= 6 ? s.replace(swapPattern, (m) => swaps.get(m) ?? m) : s)

// Google place ids look like 0x31…:0x…; any object that carries one (as `id` or `place_id`) and a `name` is a place.
const PLACE_ID = /^0x[0-9a-f]+:0x[0-9a-f]+$/
// Rewrites, in place, every place name and every quoted corpus name in a harness reply or event. Other `name` fields
// (people, tags) are left alone.
export function tidyPlaceNames<T>(value: T): T {
  if (typeof value === 'string') return tidyText(value) as T
  const walk = (v: unknown) => {
    if (!v || typeof v !== 'object') return
    if (Array.isArray(v)) { v.forEach((x, i) => { if (typeof x === 'string') v[i] = tidyText(x); else walk(x) }); return }
    const o = v as Record<string, unknown>
    const id = typeof o.place_id === 'string' ? o.place_id : typeof o.id === 'string' ? o.id : ''
    if (typeof o.name === 'string' && PLACE_ID.test(id)) o.name = displayName(o.name)
    for (const k in o) { const x = o[k]; if (typeof x === 'string') o[k] = tidyText(x); else walk(x) }
  }
  walk(value)
  return value
}
