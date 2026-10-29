// The long-term profile the user can read and change (docs/TRIP_UNDERSTANDING.md §17). Entries are the server's;
// nothing here makes one up. Routes: GET/PATCH /api/harness/me/profile, PATCH/DELETE .../profile/entries/<id>.

export type EntryKind = 'taste' | 'habit' | 'need' | 'avoid' | 'practical'
export type EntryStatus = 'candidate' | 'active' | 'weak' | 'retired'

export type Proof = { session_id: string; how: string; quote: string | null; date: string }

export type Entry = {
  id: string
  kind: EntryKind
  statement: string
  key: string
  value: string
  evidence: Proof[]
  against: number // later sessions that chose otherwise
  status: EntryStatus
  strength: number
  first_seen: string
  last_seen: string
  user_edited: boolean
  paused: boolean
  flag: string | null
  used: boolean // seeds the next trip
}

export type Memory = { enabled: boolean; paused: boolean; entries: Entry[] }

const BASE = '/api/harness/me/profile'

async function answer<T>(res: Response): Promise<T> {
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error((body as { error?: string }).error ?? `HTTP ${res.status}`)
  return body as T
}

const call = <T>(method: string, path: string, body?: unknown) =>
  fetch(path, { method, headers: { 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body) }).then((r) => answer<T>(r))

export const loadMemory = () => call<Memory>('GET', BASE)
export const pauseMemory = (paused: boolean) => call<unknown>('PATCH', BASE, { paused })
export const editEntry = (id: string, patch: { statement?: string; paused?: boolean }) => call<Entry>('PATCH', `${BASE}/entries/${id}`, patch)
export const deleteEntry = (id: string) => call<unknown>('DELETE', `${BASE}/entries/${id}`)

export const KINDS: [EntryKind, string][] = [
  ['taste', 'Gu của bạn'], ['habit', 'Thói quen'], ['need', 'Điều cần lưu ý'], ['avoid', 'Điều bạn tránh'], ['practical', 'Cách bạn hay đi'],
]

export const STATUS_LABEL: Record<EntryStatus, string> = {
  active: 'Đang dùng', candidate: 'Mình đang quan sát', weak: 'Ít chắc chắn', retired: 'Đã cũ',
}
