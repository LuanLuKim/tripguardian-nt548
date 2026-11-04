import { useEffect, useState, type CSSProperties } from 'react'
import { useAccount } from '../../account'
import { json } from '../../journey'
import { PlacePhoto } from '../../ui/common'
import { Icon } from '../../ui/icons'
import { TimeInput } from '../../ui/TimeInput'

// D.3 evening check (docs/PLANNING.md §Đổi lịch tối trước ngày đi): what tomorrow may need to change on the confirmed
// plan. The server only fills it while eve_replan is on; otherwise GET answers an empty state.
// Options are photo cards like the Trip Understanding ones (tg-cx__opt); the photo is the place the option moves to or keeps.

export type EveOption = { id: string; place?: string; kind: 'relay' | 'trim' | 'shift' | 'swap_day' | 'backup' | 'drop' | 'keep'; text: string; changed: string[]; shifted: string[] }
export type EvePending = { date: string; place_id: string; name: string; level: number; cause: { factor?: string; text: string; source: string | null; retrieved_at: string | null }; options: EveOption[] }
export type EveNote = { date: string; place_id: string; name: string; level: number; factor: string; text: string }
export type EveState = { pending: EvePending[]; notes?: EveNote[]; undo: boolean }

const URL = (id: string) => `/api/harness/sessions/${id}/eve`
// Eve off: the harness used to answer 409 (read as "nothing to show"), later answers an empty state. Both work; a missing field is read as empty.
const clean = (s: Partial<EveState> | null): EveState | null => (s ? { pending: s.pending ?? [], notes: s.notes ?? [], undo: !!s.undo } : null)

// Guests get 403 on this route (members only), so it is not asked for them at all.
export function useEve(journeyId: string | null) {
  const account = useAccount()
  const member = !!account && account.kind === 'user' && !account.guest
  const [state, setState] = useState<EveState | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    setState(null); setError(null)
    if (!journeyId || !member) return
    let live = true
    fetch(URL(journeyId)).then((r) => (r.ok ? json<EveState>(r) : null)).then((s) => { if (live) setState(clean(s)) }, () => { if (live) setState(null) })
    return () => { live = false }
  }, [journeyId, member])
  const send = async (operation: 'accept' | 'decline' | 'undo' | 'times', body: Record<string, unknown> = {}): Promise<boolean> => {
    if (!journeyId || !member) return false
    setBusy(true); setError(null)
    try {
      const next = await fetch(URL(journeyId), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ operation, ...body }) }).then((r) => json<EveState>(r))
      setState(clean(next))
      if (operation !== 'decline' && operation !== 'times') location.reload() // the confirmed plan itself changed
      return true
    } catch {
      setError(operation === 'times' ? 'Chưa lưu được giờ, bạn kiểm tra lại giờ rồi thử lại nhé.' : 'Chưa đổi được lịch, bạn thử lại nhé.')
      return false
    } finally {
      setBusy(false)
    }
  }
  return { state, busy, error, send }
}

const KIND: Record<EveOption['kind'], string> = { relay: 'Xếp lại giờ', shift: 'Dời giờ', trim: 'Bỏ bớt', swap_day: 'Đổi ngày', backup: 'Thay nơi', drop: 'Bỏ điểm', keep: 'Giữ nguyên' }

function changes(o: EveOption) {
  if (o.kind === 'keep') return 'Không đổi gì'
  const n = o.changed.length
  return `Đổi ${n} điểm${o.shifted.length ? `, lệch giờ ${o.shifted.length} điểm` : ''}`
}

const headline = (p: EvePending) => (p.cause.factor === 'window' ? `Ngày mai: ${p.cause.text}` : `Ngày mai ở ${p.name}: ${p.cause.text}`)

type Props = { state: EveState; busy: boolean; error: string | null; send: ReturnType<typeof useEve>['send']; arrive?: string | null; leave?: string | null }

// Arrive / leave time of the confirmed trip (eve `times`): only the first day's start and the last day's end move; the plan
// stays confirmed and the next evening check offers the options if something no longer fits.
export function EveTimes({ arrive, leave, busy, send }: { arrive: string; leave: string; busy: boolean; send: Props['send'] }) {
  const [a, setA] = useState(arrive)
  const [l, setL] = useState(leave)
  const [saved, setSaved] = useState(false)
  const changed = a !== arrive || l !== leave
  const save = async () => {
    const body: Record<string, string> = {}
    if (a !== arrive) body.arrive = a
    if (l !== leave) body.leave = l
    setSaved(await send('times', body))
  }
  const moments = [
    { key: 'arrive', icon: 'plane' as const, label: 'Đến nơi lúc', note: 'Ngày đầu tiên bắt đầu từ giờ này', value: a, set: (v: string) => { setA(v); setSaved(false) } },
    { key: 'leave', icon: 'home' as const, label: 'Rời đi lúc', note: 'Ngày cuối cùng kết thúc trước giờ này', value: l, set: (v: string) => { setL(v); setSaved(false) } },
  ]
  return (
    <section className="tg-eve__times" aria-label="Giờ đến và giờ về">
      <header><Icon name="clock" size={18} /><h3>Giờ đến và giờ về</h3></header>
      <div className="tg-eve__moments">
        {moments.map((m) => (
          <div key={m.key} className={`tg-eve__moment ${m.key === 'arrive' ? (a !== arrive ? 'is-edited' : '') : l !== leave ? 'is-edited' : ''}`}>
            <span className="tg-eve__moment-ico" aria-hidden="true"><Icon name={m.icon} size={18} /></span>
            <div>
              <span className="tg-eve__moment-label">{m.label}</span>
              <TimeInput label={m.label} value={m.value} disabled={busy} onChange={m.set} />
              <small>{m.note}</small>
            </div>
          </div>
        ))}
      </div>
      <footer>
        <p className="tg-faint" role="status">{changed ? 'Giờ mới chưa lưu. Lịch vẫn giữ nguyên, không tự xếp lại.' : saved ? <><Icon name="check" size={14} /> Đã lưu. Tối trước ngày đi, TripGuardian kiểm tra lại và hỏi bạn nếu có điểm không còn vừa.</> : 'Đổi giờ sau khi đã chốt không tự xếp lại lịch.'}</p>
        {changed && <button type="button" className="tg-btn tg-btn--primary tg-btn--sm tg-eve__save" disabled={busy || !a || !l} onClick={save}>Lưu giờ</button>}
      </footer>
    </section>
  )
}

export function EveBanner({ state, busy, error, send, arrive, leave }: Props) {
  const [pick, setPick] = useState<Record<string, string>>({})
  const [leaving, setLeaving] = useState<string | null>(null)
  const notes = (state.notes ?? []).slice(0, 4) // what the check saw but does not ask about: nothing to choose, just good to know
  const times = !!arrive && !!leave
  if (!state.pending.length && !state.undo && !notes.length && !times) return null
  const apply = async (p: EvePending, o: EveOption, key: string) => {
    setLeaving(key)
    await new Promise((r) => setTimeout(r, matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 240))
    if (o.kind === 'keep') await send('decline', { date: p.date, place_id: p.place_id })
    else await send('accept', { date: p.date, place_id: p.place_id, option_id: o.id, confirmed: true })
    setLeaving(null)
  }
  return (
    <>
      {state.pending.map((p) => {
        const key = p.date + p.place_id
        const keep = p.level < 3 ? p.options.find((o) => o.kind === 'keep') ?? { id: `keep:${p.place_id}`, kind: 'keep' as const, text: 'Giữ nguyên lịch', changed: [], shifted: [], place: p.place_id } : null
        const opts = [...p.options.filter((o) => o.kind !== 'keep'), ...(keep ? [keep] : [])]
        const chosen = pick[key] ?? keep?.id ?? ''
        const option = opts.find((o) => o.id === chosen)
        return (
          <section key={key} className={`tg-eve ${leaving === key ? 'is-leaving' : ''}`} aria-label="Có thay đổi cho ngày mai">
            <header className="tg-eve__head">
              <span className="tg-eve__ico"><Icon name={p.cause.source === 'open-meteo' ? 'rain' : 'warn'} size={20} /></span>
              <div><h3>{headline(p)}</h3><p>{p.level >= 3 ? 'Điểm này không đi được như lịch, bạn chọn một cách nhé.' : 'Bạn muốn xử lý thế nào?'}</p></div>
            </header>
            <div className="tg-eve__opts" role="radiogroup" aria-label={`Phương án cho ${p.name}`}>
              {opts.map((o, i) => (
                <button key={o.id} type="button" role="radio" aria-checked={chosen === o.id} disabled={busy || leaving === key} className={`tg-cx__opt tg-eve__opt ${chosen === o.id ? 'is-on' : ''}`} style={{ '--i': i } as CSSProperties} onClick={() => setPick((m) => ({ ...m, [key]: o.id }))}>
                  <span className="tg-cx__pics"><span className="tg-cx__pic is-big">{o.place ? <PlacePhoto id={o.place} name={o.text} /> : null}<span className="tg-tag tg-tag--dark tg-eve__kind">{KIND[o.kind]}</span></span><span className="tg-cx__ring"><Icon name="check" size={16} /></span></span>
                  <span className="tg-cx__opt-b"><b>{o.text}</b><small>{changes(o)}</small></span>
                </button>
              ))}
            </div>
            <footer className="tg-eve__foot">
              <button type="button" className="tg-btn tg-btn--primary" disabled={busy || !option || leaving === key} onClick={() => option && apply(p, option, key)}>{option?.kind === 'keep' ? 'Giữ nguyên lịch' : 'Áp dụng cách này'}</button>
            </footer>
          </section>
        )
      })}
      {notes.map((n, i) => <div key={`${i}:${n.date}${n.place_id}${n.factor}`} className="tg-it-note" role="status"><Icon name="info" size={18} /><span><b>{n.name} · ngày {n.date.slice(8)}/{n.date.slice(5, 7)}:</b> {n.text}</span></div>)}
      {times && <EveTimes key={`${arrive}${leave}`} arrive={arrive!} leave={leave!} busy={busy} send={send} />}
      {state.undo && <button type="button" className="tg-btn tg-btn--ghost tg-btn--sm" disabled={busy} onClick={() => send('undo')}><Icon name="return" size={15} /> Hoàn tác thay đổi vừa chọn</button>}
      {error && <p className="tg-it-diff is-bad" role="alert"><Icon name="warn" size={15} />{error}</p>}
    </>
  )
}
