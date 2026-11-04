import { track } from '../events'
import '../css/contact.css'
import { Icon } from './icons'

// A place's phone and website as they came from the served record (Place.phone / Place.website). Missing → the caller
// renders nothing. Used by the place sheet's facts (ui/PlaceSheet.tsx) and the lodging card (screens/Lodging.tsx).

// Vietnamese numbers are stored as digits: "0263 3822 534" (landline, 0 + 3-digit area), "0856 627 867" (mobile), "1900 6778".
export function phoneText(raw: string): string {
  const d = raw.replace(/[^\d+]/g, '')
  if (/^0\d{10}$/.test(d)) return `${d.slice(0, 4)} ${d.slice(4, 8)} ${d.slice(8)}`
  if (/^0\d{9}$/.test(d)) return `${d.slice(0, 4)} ${d.slice(4, 7)} ${d.slice(7)}`
  if (/^1[89]00\d{4}$/.test(d)) return `${d.slice(0, 4)} ${d.slice(4)}`
  return raw.trim() // already written with spaces or a country code: shown as given
}

// tel: link that also dials from abroad: a leading 0 becomes +84.
export const telHref = (raw: string) => {
  const d = raw.replace(/[^\d+]/g, '')
  return `tel:${/^0\d{9,10}$/.test(d) ? `+84${d.slice(1)}` : d}`
}

// The domain of a website ("dalatpalace.vn"); a Facebook page is just "Facebook". null when it is not an http(s) link.
export function siteOf(raw: string): { href: string; label: string } | null {
  try {
    const u = new URL(/^https?:\/\//i.test(raw) ? raw : `https://${raw}`)
    if (!/^https?:$/.test(u.protocol)) return null
    const host = u.hostname.replace(/^(www|m|web)\./, '')
    return { href: u.href, label: /(^|\.)(facebook\.com|fb\.com|fb\.me)$/.test(host) ? 'Facebook' : host }
  } catch {
    return null
  }
}

type Props = { id: string; phone?: string | null; website?: string | null }

export function PhoneLink({ id, phone }: { id: string; phone?: string | null }) {
  if (!phone || !/\d{6}/.test(phone)) return null
  return (
    <a className="tg-link tg-contact" href={telHref(phone)} onClick={() => track('outbound_click', { kind: 'phone', place_id: id })}>
      <Icon name="phone" size={15} /> <span style={{ fontVariantNumeric: "tabular-nums" }}>{phoneText(phone)}</span>
    </a>
  )
}

export function SiteLink({ id, website }: { id: string; website?: string | null }) {
  const site = website ? siteOf(website) : null
  if (!site) return null
  return (
    <a className="tg-link tg-contact" href={site.href} target="_blank" rel="noopener noreferrer" onClick={() => track('outbound_click', { kind: 'website', place_id: id })}>
      {site.label} <Icon name="external" size={14} />
    </a>
  )
}

// Both, side by side, for the lodging card; nothing at all when the record has neither.
export function Contact({ id, phone, website }: Props) {
  const has = (phone && /\d{6}/.test(phone)) || (website && siteOf(website))
  if (!has) return null
  return <span className="tg-contacts"><PhoneLink id={id} phone={phone} /><SiteLink id={id} website={website} /></span>
}
