import type { ReactNode } from 'react'

// The assistant's words with the little structure a reply may carry: paragraphs, "- " / "1. " lists, "## " headings and
// **bold**. Built as elements (never as HTML), so a reply can not inject markup.

// `places`: the places the reply's own cards hold; their names in the words become buttons that open the place (the reply leads
// the eye to them instead of describing them at length). Longest names first, so "Hồ Xuân Hương" wins over "Hồ".
export type Named = { id: string; name: string }
const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
function linked(s: string, places: Named[], onPlace?: (id: string, el: HTMLElement) => void): ReactNode[] {
  const named = places.filter((p) => p.name && p.name.length >= 3).sort((a, b) => b.name.length - a.name.length)
  if (!named.length || !onPlace) return [s]
  const re = new RegExp(`(${named.map((p) => esc(p.name)).join('|')})`, 'g')
  return s.split(re).map((part, i) => {
    const hit = i % 2 === 1 ? named.find((p) => p.name === part) : undefined
    return hit ? <button key={i} type="button" className="tg-rich__place" onClick={(e) => onPlace(hit.id, e.currentTarget)}>{part}</button> : part
  })
}

const bold = (s: string, places: Named[] = [], onPlace?: (id: string, el: HTMLElement) => void): ReactNode[] =>
  s.split(/(\*\*[^*\n]+\*\*)/).flatMap((part, i) => (part.length > 4 && part.startsWith('**') && part.endsWith('**')
    ? [<strong key={i}>{linked(part.slice(2, -2), places, onPlace)}</strong>] : linked(part, places, onPlace).map((x, k) => (typeof x === 'string' ? x : <span key={`${i}-${k}`}>{x}</span>))))

export function Rich({ text, places = [], onPlace }: { text: string; places?: Named[]; onPlace?: (id: string, el: HTMLElement) => void }) {
  const out: ReactNode[] = []
  let list: { ordered: boolean; items: string[] } | null = null
  const flush = () => {
    if (!list) return
    const items = list.items.map((x, i) => <li key={i}>{bold(x, places, onPlace)}</li>)
    out.push(list.ordered ? <ol key={out.length}>{items}</ol> : <ul key={out.length}>{items}</ul>)
    list = null
  }
  for (const raw of text.split('\n')) {
    const line = raw.trim()
    const item = /^(?:[-*•]|(\d+)[.)])\s+(.+)$/.exec(line)
    if (item) {
      const ordered = item[1] !== undefined
      if (list && list.ordered !== ordered) flush()
      list = list ?? { ordered, items: [] }
      list.items.push(item[2])
      continue
    }
    flush()
    const head = /^#{1,4}\s+(.+)$/.exec(line)
    if (head) out.push(<h4 key={out.length}>{bold(head[1], places, onPlace)}</h4>)
    else if (line) out.push(<p key={out.length}>{bold(line, places, onPlace)}</p>)
  }
  flush()
  return <>{out}</>
}
