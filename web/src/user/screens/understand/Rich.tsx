import type { ReactNode } from 'react'

// The assistant's words with the little structure a reply may carry: paragraphs, "- " / "1. " lists, "## " headings and
// **bold**. Built as elements (never as HTML), so a reply can not inject markup.

const bold = (s: string): ReactNode[] =>
  s.split(/(\*\*[^*\n]+\*\*)/).map((part, i) => (part.length > 4 && part.startsWith('**') && part.endsWith('**') ? <strong key={i}>{part.slice(2, -2)}</strong> : part))

export function Rich({ text }: { text: string }) {
  const out: ReactNode[] = []
  let list: { ordered: boolean; items: string[] } | null = null
  const flush = () => {
    if (!list) return
    const items = list.items.map((x, i) => <li key={i}>{bold(x)}</li>)
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
    if (head) out.push(<h4 key={out.length}>{bold(head[1])}</h4>)
    else if (line) out.push(<p key={out.length}>{bold(line)}</p>)
  }
  flush()
  return <>{out}</>
}
