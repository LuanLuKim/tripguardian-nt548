import { useState, type CSSProperties } from 'react'
import type { WebSource } from '../../tu/types'
import { Icon } from '../../ui/icons'

// The pages a reply read, as one quiet pill under its words ("site +2"); a tap lists them. A letter on a colour stands in for
// the site's icon, so the chat asks no third-party service about which sites it read.

const label = (domain: string) => domain.replace(/^www\./, '')
const safe = (s: WebSource) => /^https?:\/\//i.test(s.url)

export function SourceMark({ domain }: { domain: string }) {
  const hue = [...domain].reduce((h, c) => (h * 31 + c.charCodeAt(0)) % 360, 7)
  return <i className="tg-src__mark" style={{ '--h': hue } as CSSProperties} aria-hidden="true">{label(domain).charAt(0).toUpperCase()}</i>
}

// One page, as a small chip at the end of the sentence it backs: a tap opens the page.
export function SourceChip({ source }: { source: WebSource }) {
  if (!safe(source)) return null
  return <a className="tg-src__chip" href={source.url} target="_blank" rel="noopener noreferrer" title={source.title || label(source.domain)}>
    <SourceMark domain={source.domain} /><span>{label(source.domain)}</span>
  </a>
}

export function Sources({ sources }: { sources: WebSource[] }) {
  const [open, setOpen] = useState(false)
  const list = sources.filter(safe)
  if (!list.length) return null
  return <div className="tg-src">
    <button type="button" className="tg-src__pill" aria-expanded={open} onClick={() => setOpen(o => !o)}>
      <SourceMark domain={list[0].domain} />
      <span>{label(list[0].domain)}</span>
      {list.length > 1 && <em>+{list.length - 1}</em>}
    </button>
    {open && <ul className="tg-src__list" aria-label="Nguồn đã đọc">
      {list.map(s => <li key={s.url}>
        <a href={s.url} target="_blank" rel="noopener noreferrer">
          <SourceMark domain={s.domain} />
          <span><b>{s.title || label(s.domain)}</b><small>{label(s.domain)}</small></span>
          <Icon name="external" size={14} />
        </a>
      </li>)}
    </ul>}
  </div>
}
