import { placeById, signal, useDetail } from '../../data/store'
import type { Claim } from '../pd/types'

// Pet evidence expands in place, without interrupting selection or judging the user's choice.
export function PetFacts({ id, claims }: { id: string; claims: Claim[] }) {
  useDetail(claims.length ? [id] : [])
  const p = placeById(id)
  return claims.map((claim) => {
    const evidence = p && claim.sid ? signal(p, claim.sid) : undefined
    return claim.sid ? <details key={claim.text} className="tg-faint" data-sid={claim.sid}>
      <summary>{claim.text}</summary>
      {evidence?.quotes.length ? <ul>{evidence.quotes.map((q) => <li key={q.text}><q>{q.text}</q><small> · {q.source}{q.date ? ` · ${q.date}` : ''}</small></li>)}</ul> : <p>Chưa tải được lời người đã đi.</p>}
    </details> : <p key={claim.text} className="tg-faint">{claim.text}</p>
  })
}
