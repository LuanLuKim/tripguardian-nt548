// A place sheet asks the Lựa chọn assistant something about one place ("vì sao không gợi ý X"). The assistant may not be
// mounted yet (it opens on this call), so one request waits here until the chat takes it.
export interface AskRequest { kind: 'why-not'; id: string; name: string }

let pending: AskRequest | null = null
const listeners = new Set<() => void>()

export function askAssistant(r: AskRequest) {
  pending = r
  listeners.forEach((l) => l())
}

export function takeAsk(): AskRequest | null {
  const r = pending
  pending = null
  return r
}

export function onAsk(l: () => void) {
  listeners.add(l)
  return () => { listeners.delete(l) }
}
