import type { Card } from '../pd/types'

// Shared card copy: pet policy is a plain attribute, never a fit warning or tradeoff.
export function cardLines(c: Card): { why: Card['why']; trade: string | undefined; alerts: string[]; pets: Card['why'] } {
  const petNote = (text: string) => /thú cưng|\bpets\b/i.test(text)
  const pets = [...c.why, ...c.tradeoffs].filter((r) => r.sid === 'pets')
  for (const text of c.unverified.filter(petNote)) {
    if (!pets.some((r) => r.text === text)) pets.push({ text, sid: null })
  }
  const trades = c.tradeoffs.filter((r) => r.sid !== 'pets')
  const notes = [...c.failed.filter((t) => !petNote(t)).map((t) => `Không hợp điều kiện của bạn: ${t}`), ...c.unverified.filter((t) => !petNote(t)), ...c.warnings.filter((t) => !petNote(t)), ...(c.depends_on_unknown ? [c.depends_on_unknown] : [])]
  const trade = trades[0]?.text ?? notes.shift()
  return { why: c.why.filter((r) => r.sid !== 'pets').slice(0, 3), trade, alerts: [...trades.slice(1).map((t) => t.text), ...notes].slice(0, 2), pets }
}
