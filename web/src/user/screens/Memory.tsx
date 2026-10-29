import { useEffect, useMemo, useRef, useState } from 'react'
import { rememberProfile, useAccount } from '../account'
import { deleteEntry, editEntry, KINDS, loadMemory, pauseMemory, STATUS_LABEL, type Entry, type EntryKind, type Memory } from '../memory'
import { toast } from '../store'
import { ArtCup, ArtHills, Busy, Empty, go } from '../ui/common'
import { Icon } from '../ui/icons'
import { Page, useTitle } from '../ui/Shell'

const day = (iso: string) => { const [y, m, d] = iso.split('-'); return y && m && d ? `${d}/${m}/${y}` : iso }
const RANK: Record<Entry['status'], number> = { active: 0, candidate: 1, weak: 2, retired: 3 }
const HOW: Record<string, string> = { picked: 'Bạn đã chọn', acted: 'Từ cách bạn dùng lịch trình' }

// "Mình nhớ gì về bạn": every entry the profile holds, readable and changeable one by one (docs/TRIP_UNDERSTANDING.md §17).
// The profile is only a prior for a new trip; the page says so and shows where each line came from.
export function MemoryPage() {
  useTitle('Mình nhớ gì về bạn')
  const account = useAccount()
  const [mem, setMem] = useState<Memory | null>(null)
  const [err, setErr] = useState(false)
  const [kind, setKind] = useState<EntryKind | 'all'>('all')
  const [busy, setBusy] = useState(false)
  useEffect(() => { loadMemory().then(setMem, () => setErr(true)) }, [])

  const entries = mem?.entries ?? []
  const counts = useMemo(() => Object.fromEntries(KINDS.map(([k]) => [k, entries.filter((e) => e.kind === k).length])) as Record<EntryKind, number>, [entries])
  const kinds = KINDS.filter(([k]) => counts[k] > 0)
  const shown = entries.filter((e) => kind === 'all' || e.kind === kind).sort((a, b) => RANK[a.status] - RANK[b.status] || b.last_seen.localeCompare(a.last_seen))
  const remembering = account?.consents.patterns === true

  const change = (id: string, patch: Partial<Entry>) => setMem((m) => m && { ...m, entries: m.entries.map((e) => e.id === id ? { ...e, ...patch } : e) })
  const drop = (id: string) => setMem((m) => m && { ...m, entries: m.entries.filter((e) => e.id !== id) })

  const toggleRemember = () => {
    setBusy(true)
    rememberProfile(!remembering).then(() => toast(remembering ? 'Mình sẽ không ghi thêm gì sau chuyến' : 'Mình sẽ nhớ cho lần sau'), () => toast('Chưa đổi được, bạn thử lại nhé')).finally(() => setBusy(false))
  }
  const togglePause = () => {
    if (!mem) return
    const next = !mem.paused
    setMem({ ...mem, paused: next })
    setBusy(true)
    pauseMemory(next).then(() => toast(next ? 'Đã tạm dừng, chuyến mới không dùng hồ sơ này' : 'Mình dùng lại hồ sơ này cho chuyến mới'), () => { setMem((m) => m && { ...m, paused: !next }); toast('Chưa đổi được, bạn thử lại nhé') }).finally(() => setBusy(false))
  }

  return (
    <Page narrow>
      <header className="tg-head"><div><p className="tg-kicker">Hồ sơ</p><h1>Mình nhớ gì về bạn</h1><p>Mình dùng những điều này để hỏi ít hơn khi bạn lên chuyến mới. Chúng chỉ là gợi ý ban đầu: điều bạn nói trong chuyến luôn được ưu tiên, và mình không bao giờ coi một nơi bạn đã đến là nơi bạn thích.</p></div></header>
      {err ? <Empty art={<ArtHills />} title="Chưa mở được hồ sơ" body="Máy chủ chưa trả lời. Thử lại sau ít phút." action={<button type="button" className="tg-btn tg-btn--primary" onClick={() => location.reload()}>Thử lại</button>} />
        : !mem ? <Busy text="Đang mở những điều mình nhớ…" />
        : !mem.enabled ? <Empty art={<ArtCup />} title="Mình chưa ghi nhớ gì lúc này" body="Chuyến nào bạn cũng bắt đầu từ trang trắng. Khi tính năng này mở, những điều bạn lặp lại qua các chuyến sẽ hiện ở đây để bạn xem và sửa." action={<button type="button" className="tg-btn tg-btn--primary" onClick={() => go('/profile')}>Về cài đặt</button>} />
        : (
          <>
            <section className="tg-card tg-mem__ctl" aria-label="Cách mình nhớ">
              <Switch id="tg-mem-remember" on={remembering} busy={busy} onChange={toggleRemember} title="Nhớ cho lần sau" body="Sau mỗi chuyến, mình ghi lại những điều bạn tự nói hoặc tự chọn. Không ghi điều mình đoán." />
              <Switch id="tg-mem-pause" on={mem.paused} busy={busy} onChange={togglePause} title="Tạm dừng hồ sơ" body="Danh sách vẫn giữ nguyên, nhưng chuyến mới không dùng đến nó." />
            </section>

            {entries.length === 0 ? (
              <Empty art={<ArtCup />} title="Chưa có gì để nhớ" body={remembering ? 'Sau vài chuyến, những điều bạn lặp lại sẽ hiện ở đây. Bạn xóa hay sửa từng dòng được.' : 'Bật “Nhớ cho lần sau” ở trên, rồi đi một vài chuyến. Những điều bạn lặp lại sẽ hiện ở đây.'} />
            ) : (
              <>
                {kinds.length > 1 && (
                  <div className="tg-tabs" role="tablist" aria-label="Nhóm">
                    <button type="button" role="tab" aria-selected={kind === 'all'} className="tg-tab" onClick={() => setKind('all')}>Tất cả<b>{entries.length}</b></button>
                    {kinds.map(([k, l]) => <button key={k} type="button" role="tab" aria-selected={kind === k} className="tg-tab" onClick={() => setKind(k)}>{l}<b>{counts[k]}</b></button>)}
                  </div>
                )}
                <ul className={`tg-mem__list ${mem.paused ? 'is-paused' : ''}`}>
                  {shown.map((e) => <Row key={e.id} e={e} held={mem.paused} onChange={(p) => change(e.id, p)} onGone={() => drop(e.id)} />)}
                </ul>
                <p className="tg-faint tg-mem__fine"><Icon name="shield" size={14} /> Chỉ những điều bạn tự nói hoặc tự chọn mới được lưu. Xóa một dòng là xóa luôn lời bạn đã nói ở đó.</p>
              </>
            )}
          </>
        )}
    </Page>
  )
}

function Switch({ id, on, busy, onChange, title, body }: { id: string; on: boolean; busy: boolean; onChange: () => void; title: string; body: string }) {
  return (
    <div className="tg-mem__sw">
      <div><label htmlFor={id}><b>{title}</b></label><p className="tg-faint" id={`${id}-d`}>{body}</p></div>
      <button type="button" id={id} role="switch" aria-checked={on} aria-describedby={`${id}-d`} className="tg-switch" disabled={busy} onClick={onChange}><i /></button>
    </div>
  )
}

function Row({ e, held, onChange, onGone }: { e: Entry; held: boolean; onChange: (p: Partial<Entry>) => void; onGone: () => void }) {
  const [open, setOpen] = useState(false)
  const [mode, setMode] = useState<'view' | 'edit' | 'ask'>('view')
  const [text, setText] = useState(e.statement)
  const [busy, setBusy] = useState(false)
  const [leaving, setLeaving] = useState(false)
  const input = useRef<HTMLInputElement>(null)
  useEffect(() => { if (mode === 'edit') input.current?.focus() }, [mode])
  const fail = () => toast('Chưa lưu được, bạn thử lại nhé')

  const save = () => {
    const s = text.trim()
    if (!s || s === e.statement) return setMode('view')
    setBusy(true)
    editEntry(e.id, { statement: s }).then((x) => { onChange({ statement: x.statement, user_edited: true, status: x.status, used: x.used }); setMode('view'); toast('Đã sửa dòng này') }, fail).finally(() => setBusy(false))
  }
  const pause = () => {
    const next = !e.paused
    onChange({ paused: next, used: next ? false : e.used })
    editEntry(e.id, { paused: next }).then((x) => onChange({ paused: x.paused, used: x.used, status: x.status }), () => { onChange({ paused: !next }); fail() })
  }
  const remove = () => {
    setBusy(true)
    deleteEntry(e.id).then(() => { setLeaving(true); setTimeout(onGone, 220); toast('Đã xóa, mình quên dòng này rồi') }, () => { setBusy(false); fail() })
  }

  const trips = new Set(e.evidence.map((p) => p.session_id)).size
  const tag = e.paused ? 'Đang tạm dừng' : STATUS_LABEL[e.status]
  const tone = e.paused || e.status === 'weak' || e.status === 'retired' ? 'tg-tag--warn' : e.used && !held ? 'tg-mem__on' : ''
  return (
    <li className={`tg-mem__row ${leaving ? 'is-leaving' : ''} ${e.paused || (held && e.used) ? 'is-off' : ''}`}>
      <div className="tg-mem__main">
        {mode === 'edit' ? (
          <form className="tg-mem__edit" onSubmit={(ev) => { ev.preventDefault(); save() }}>
            <label className="tg-sr" htmlFor={`tg-mem-${e.id}`}>Nội dung dòng này</label>
            <input id={`tg-mem-${e.id}`} ref={input} className="tg-input" value={text} maxLength={200} onChange={(ev) => setText(ev.target.value)} onKeyDown={(ev) => { if (ev.key === 'Escape') { setText(e.statement); setMode('view') } }} />
            <button type="submit" className="tg-btn tg-btn--primary tg-btn--sm" disabled={busy || !text.trim()}>Lưu</button>
            <button type="button" className="tg-btn tg-btn--ghost tg-btn--sm" disabled={busy} onClick={() => { setText(e.statement); setMode('view') }}>Thôi</button>
          </form>
        ) : <p className="tg-mem__text">{e.statement}</p>}
        <p className="tg-mem__meta">
          <span className={`tg-tag ${tone}`}>{tag}</span>
          <span>Từ {trips} chuyến</span><span aria-hidden="true">·</span><span>gần nhất {day(e.last_seen)}</span>
          {e.against > 0 && <><span aria-hidden="true">·</span><span>{e.against} chuyến sau nói khác</span></>}
        </p>
        <div className={`tg-mem__proof ${open ? 'is-open' : ''}`}><div><ul>
          {e.evidence.map((p, i) => <li key={`${p.session_id}-${i}`}><span className="tg-mono tg-faint">{day(p.date)}</span> {p.quote ? <>Bạn nói: “{p.quote}”</> : (HOW[p.how] ?? 'Bạn đã chọn')}</li>)}
        </ul></div></div>
      </div>
      <div className="tg-mem__ops">
        {mode === 'ask' ? (
          <span className="tg-mem__ask" role="alertdialog" aria-label="Xóa dòng này?">Xóa dòng này?
            <button type="button" className="tg-btn tg-btn--sm tg-del__yes" disabled={busy} onClick={remove}>{busy ? 'Đang xóa…' : 'Xóa'}</button>
            <button type="button" className="tg-link" disabled={busy} onClick={() => setMode('view')}>Giữ lại</button>
          </span>
        ) : (
          <>
            <button type="button" className="tg-link" aria-expanded={open} onClick={() => setOpen(!open)}>{open ? 'Ẩn nguồn' : 'Nguồn'}</button>
            <button type="button" className="tg-mem__ic" title="Sửa" aria-label="Sửa dòng này" onClick={() => { setText(e.statement); setMode('edit') }}><Icon name="edit" size={16} /></button>
            <button type="button" className="tg-link" aria-pressed={e.paused} onClick={pause}>{e.paused ? 'Dùng lại' : 'Tạm dừng'}</button>
            <button type="button" className="tg-mem__ic tg-mem__ic--del" title="Xóa" aria-label="Xóa dòng này" onClick={() => setMode('ask')}><Icon name="trash" size={16} /></button>
          </>
        )}
      </div>
    </li>
  )
}
