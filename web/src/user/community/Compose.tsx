import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type ClipboardEvent, type DragEvent, type KeyboardEvent as RKey } from 'react'
import { useSnapshot } from '../../data/store'
import { query, usePath } from '../../router'
import { useAccount } from '../account'
import { info } from '../lib'
import { search } from '../search'
import { toast } from '../store'
import { go } from '../ui/common'
import { Icon } from '../ui/icons'
import { useTitle } from '../ui/Shell'
import { FACT_LABELS, popularTags, publish, saveDraft, useStore, VIS, type UserBlock, type Facts, type Vis } from './data'
import { Avatar, PlacePic, postHref } from './parts'
import '../css/posts.css'

// The composer (docs/design/mock reference 8): a page to write on, not a form. Title, then blocks of text and photos that grow as you
// type; photos are added from the toolbar, pasted or dropped. The settings (tags, who can read, trip details) wait in the
// "Sẵn sàng đăng?" panel behind the Đăng bài button (tags, who can read, trip details), so the page stays for the writing.
type Item = { id: string; b: UserBlock }
const uid = () => Math.random().toString(36).slice(2, 9)
const MAX_IMAGES = 12
const MAX_TAGS = 5

// A photo the author adds: scaled to 1280px and re-encoded, so a few of them fit in the browser's storage.
async function toDataUrl(file: File): Promise<string> {
  const bmp = await createImageBitmap(file)
  const k = Math.min(1, 1280 / Math.max(bmp.width, bmp.height))
  const c = document.createElement('canvas')
  c.width = Math.round(bmp.width * k)
  c.height = Math.round(bmp.height * k)
  c.getContext('2d')!.drawImage(bmp, 0, 0, c.width, c.height)
  bmp.close()
  return c.toDataURL('image/jpeg', 0.82)
}

function Grow({ value, onChange, className, placeholder, label, inputRef, ...rest }: {
  value: string; onChange: (v: string) => void; className?: string; placeholder?: string; label: string; inputRef?: (el: HTMLTextAreaElement | null) => void
  onKeyDown?: (e: RKey<HTMLTextAreaElement>) => void; onFocus?: () => void; maxLength?: number; id?: string
}) {
  const el = useRef<HTMLTextAreaElement | null>(null)
  useLayoutEffect(() => { const t = el.current; if (t) { t.style.height = 'auto'; t.style.height = `${t.scrollHeight}px` } }, [value])
  return <textarea {...rest} ref={(t) => { el.current = t; inputRef?.(t) }} rows={1} aria-label={label} className={className} placeholder={placeholder} value={value} onChange={(e) => onChange(e.target.value)} />
}

export function Compose() {
  const { snap } = useSnapshot()
  useTitle('Viết bài')
  const store = useStore()
  const account = useAccount()
  const name = account?.name || 'Bạn'
  const params = query(usePath())
  const start = useRef(store.draft).current
  const preset = params.get('at')
  const [placeId, setPlaceId] = useState<string | null>(preset && info(preset) ? preset : start?.placeId && info(start.placeId) ? start.placeId : null)
  const [title, setTitle] = useState(start?.title ?? '')
  const [items, setItems] = useState<Item[]>(() => (start?.blocks.length ? start.blocks : [{ t: 'p', text: '' } as UserBlock]).map((b) => ({ id: uid(), b })))
  const [tags, setTags] = useState<string[]>(start?.tags ?? [])
  const [vis, setVis] = useState<Vis>(start?.vis ?? 'friends')
  const [facts, setFacts] = useState<Partial<Facts>>(start?.facts ?? {})
  const [consent, setConsent] = useState(start?.consent ?? false)
  const [panel, setPanel] = useState(false)
  const [saving, setSaving] = useState<'idle' | 'saved' | 'full'>(start ? 'saved' : 'idle')
  const [busy, setBusy] = useState(false)
  const fields = useRef(new Map<string, HTMLTextAreaElement>())
  const focus = useRef<string | null>(null)
  const file = useRef<HTMLInputElement>(null)
  const pending = useRef<{ id: string; at: number } | null>(null)

  const images = items.filter((i) => i.b.t === 'img').length
  const text = items.reduce((n, i) => n + (i.b.t === 'img' ? 0 : i.b.text.trim().length), 0)
  const dirty = !!title.trim() || text > 0 || images > 0

  // The draft saves itself a moment after the last keystroke.
  useEffect(() => {
    if (!dirty) return
    const t = setTimeout(() => setSaving(saveDraft({ placeId, title, blocks: items.map((i) => i.b), tags, vis, facts, consent, at: Date.now() }) ? 'saved' : 'full'), 700)
    return () => clearTimeout(t)
  }, [placeId, title, items, tags, vis, facts, consent, dirty])

  useEffect(() => {
    if (!pending.current) return
    const { id, at } = pending.current
    pending.current = null
    const el = fields.current.get(id)
    if (el) { el.focus(); const pos = at < 0 ? el.value.length : at; el.setSelectionRange(pos, pos) }
  }, [items])

  const patch = (id: string, b: UserBlock) => setItems((l) => l.map((i) => (i.id === id ? { ...i, b } : i)))
  // focusId gets the cursor afterwards: at its start (`caret` 0, a split paragraph) or its end (-1).
  const insertAfter = (id: string | null, add: Item[], focusId?: string, caret = -1) => {
    if (focusId) pending.current = { id: focusId, at: caret }
    setItems((l) => {
      const k = id ? l.findIndex((i) => i.id === id) : -1
      const at = k < 0 ? l.length : k + 1
      return [...l.slice(0, at), ...add, ...l.slice(at)]
    })
  }
  const remove = (id: string, focusPrev = false) => setItems((l) => {
    if (l.length <= 1) return [{ id: uid(), b: { t: 'p', text: '' } }]
    const k = l.findIndex((i) => i.id === id)
    const prev = l[k - 1]
    if (focusPrev && prev) pending.current = { id: prev.id, at: -1 }
    return l.filter((i) => i.id !== id)
  })
  const move = (id: string, d: -1 | 1) => setItems((l) => {
    const k = l.findIndex((i) => i.id === id), j = k + d
    if (k < 0 || j < 0 || j >= l.length) return l
    const out = [...l]
    ;[out[k], out[j]] = [out[j], out[k]]
    return out
  })

  const addImages = useCallback(async (files: File[]) => {
    const pics = files.filter((f) => f.type.startsWith('image/'))
    if (!pics.length) { if (files.length) toast('Chỉ thêm được ảnh'); return }
    const room = MAX_IMAGES - images
    if (room <= 0) { toast(`Mỗi bài tối đa ${MAX_IMAGES} ảnh`); return }
    setBusy(true)
    const added: Item[] = []
    for (const f of pics.slice(0, room)) {
      try { added.push({ id: uid(), b: { t: 'img', src: await toDataUrl(f), cap: '' } }) } catch { toast(`Không đọc được ảnh “${f.name}”`) }
    }
    setBusy(false)
    if (pics.length > room) toast(`Chỉ thêm ${room} ảnh đầu, mỗi bài tối đa ${MAX_IMAGES} ảnh`)
    if (!added.length) return
    // Keep a text block after the photos so writing can go on.
    const after = [...added, { id: uid(), b: { t: 'p', text: '' } as UserBlock }]
    insertAfter(focus.current, after, after[after.length - 1].id)
  }, [images]) // eslint-disable-line react-hooks/exhaustive-deps

  // Bold and italic wrap the selection in the textarea that has the cursor.
  const mark = (sym: string) => {
    const id = focus.current
    const el = id ? fields.current.get(id) : null
    const it = id ? items.find((i) => i.id === id) : null
    if (!el || !it || it.b.t === 'img') return
    const a = el.selectionStart, z = el.selectionEnd
    const v = el.value
    const next = `${v.slice(0, a)}${sym}${v.slice(a, z)}${sym}${v.slice(z)}`
    patch(it.id, { t: it.b.t, text: next })
    requestAnimationFrame(() => { el.focus(); el.setSelectionRange(a + sym.length, z + sym.length) })
  }
  const turn = (t: 'h' | 'q') => {
    const it = items.find((i) => i.id === focus.current)
    if (!it || it.b.t === 'img') { toast('Bấm vào một đoạn chữ trước'); return }
    patch(it.id, { t: it.b.t === t ? 'p' : t, text: it.b.text })
  }
  const onKey = (it: Item, e: RKey<HTMLTextAreaElement>) => {
    const el = e.currentTarget
    if (it.b.t === 'img') return
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'b') { e.preventDefault(); mark('**') }
    else if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'i') { e.preventDefault(); mark('*') }
    else if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      const a = el.selectionStart
      const nid = uid()
      patch(it.id, { t: it.b.t, text: el.value.slice(0, a) })
      insertAfter(it.id, [{ id: nid, b: { t: 'p', text: el.value.slice(el.selectionEnd) } }], nid, 0)
    } else if (e.key === 'Backspace' && !el.value && items.length > 1) { e.preventDefault(); remove(it.id, true) }
  }

  const onPaste = (e: ClipboardEvent) => {
    const files = [...e.clipboardData.files]
    if (files.length) { e.preventDefault(); void addImages(files) }
  }
  const onDrop = (e: DragEvent) => {
    if (!e.dataTransfer.files.length) return
    e.preventDefault()
    void addImages([...e.dataTransfer.files])
  }

  const place = placeId ? info(placeId) : null
  const checks = [
    { ok: !!place, text: 'Đã chọn nơi bạn viết về' },
    { ok: title.trim().length >= 3, text: 'Có tiêu đề' },
    { ok: items.some((i) => i.b.t === 'p' && i.b.text.trim().length >= 20), text: 'Có ít nhất một đoạn văn' },
  ]
  const ready = checks.every((c) => c.ok) && !busy
  const submit = () => {
    const missing = checks.find((c) => !c.ok)
    if (missing || !placeId) { toast(`Chưa đăng được: ${missing ? missing.text.replace(/^(Đã chọn|Có)/, 'thiếu') : 'thiếu nơi'}`); return }
    if (busy) return
    const blocks = items.map((i) => i.b).filter((b) => b.t === 'img' || b.text.trim()).map((b) => (b.t === 'img' ? b : { ...b, text: b.text.trim() }))
    const post = publish({ placeId, title: title.trim(), blocks, tags, author: name, vis, facts: Object.fromEntries(Object.entries(facts).filter(([, v]) => v?.trim())) as Partial<Facts>, consent: consent && vis === 'public' })
    if (!post) { toast('Bộ nhớ trình duyệt đã đầy. Bớt vài ảnh rồi đăng lại.'); return }
    toast('Đã đăng bài')
    go(postHref(post.id), { replace: true })
  }
  useEffect(() => {
    if (!panel) return
    const key = (e: KeyboardEvent) => { if (e.key === 'Escape') setPanel(false) }
    addEventListener('keydown', key)
    return () => removeEventListener('keydown', key)
  }, [panel])
  const leave = () => { if (!dirty || confirm('Rời trang này? Bản nháp đã được lưu trên máy này.')) history.length > 1 ? history.back() : go('/posts') }

  return (
    <div className="tg-cp" onPaste={onPaste} onDragOver={(e) => { if (e.dataTransfer.types.includes('Files')) e.preventDefault() }} onDrop={onDrop}>
      <div className="tg-pr__bar">
        <button type="button" className="tg-bp-back" onClick={leave}><Icon name="arrowLeft" size={16} />Quay lại</button>
        <span className="tg-pr__where"><b>Viết bài</b><i aria-hidden="true">·</i>{saving === 'full' ? 'Bộ nhớ đầy, chưa lưu được nháp' : dirty ? (saving === 'saved' ? 'Đã lưu nháp trên máy này' : 'Đang viết…') : 'Bản nháp trống'}</span>
        <div className="tg-pr__tools">
          <button type="button" className="tg-bp-btn is-dark" aria-expanded={panel} aria-haspopup="dialog" onClick={() => setPanel((v) => !v)}>Đăng bài<Icon name="chevronDown" size={14} /></button>
        </div>
        {panel && (
          <>
            <div className="tg-cp__veil" onClick={() => setPanel(false)} />
            <div className="tg-cp__panel" role="dialog" aria-label="Sẵn sàng đăng?">
              <h2>Sẵn sàng đăng?</h2>
              <ul className="tg-cp__checks">{checks.map((c) => <li key={c.text} className={c.ok ? 'is-ok' : ''}><Icon name={c.ok ? 'check' : 'minus'} size={14} />{c.text}</li>)}</ul>

              <label className="tg-cp__l" htmlFor="tg-cp-tag">Thẻ <small>tối đa {MAX_TAGS}, để người đọc biết bài nói về gì</small></label>
              <TagInput tags={tags} onChange={setTags} />

              <span className="tg-cp__l">Ai xem được bài này?</span>
              <div className="tg-cp__who" role="radiogroup" aria-label="Quyền xem">
                {(['friends', 'public', 'me'] as Vis[]).map((v) => (
                  <label key={v} className={vis === v ? 'is-on' : ''}><input type="radio" name="tg-vis" checked={vis === v} onChange={() => setVis(v)} /><Icon name={v === 'public' ? 'link' : v === 'friends' ? 'users' : 'lock'} size={15} />{VIS[v]}</label>
                ))}
              </div>
              <p className="tg-cp__hint">{vis === 'public' ? 'Mọi người thấy, kể cả khách chưa đăng nhập, và hiện ở kết quả tìm kiếm.' : vis === 'friends' ? 'Chỉ bạn bè của bạn thấy và bình luận được.' : 'Lưu như nhật ký riêng, chỉ bạn xem được.'}</p>

              <details className="tg-cp__more">
                <summary>Chi tiết chuyến đi <small>không bắt buộc</small></summary>
                <div className="tg-cp__facts">
                  {FACT_LABELS.map(([k, label]) => (
                    <label key={k}><span>{label}</span><input value={facts[k] ?? ''} maxLength={40} placeholder={{ when: 'Cuối tháng 10', who: '2 người', how: 'Xe máy', cost: '~ 120.000đ' }[k]} onChange={(e) => setFacts({ ...facts, [k]: e.target.value })} /></label>
                  ))}
                </div>
              </details>

              {vis === 'public' && <label className="tg-cp__consent"><input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} /><span>Cho phép TripGuardian dùng nội dung bài này (không kèm tên bạn) để hiểu thêm về nơi này và gợi ý tốt hơn. Không bắt buộc, tắt lúc nào cũng được.</span></label>}

              <div className="tg-cp__go">
                <button type="button" className="tg-bp-btn" onClick={() => setPanel(false)}>Viết tiếp</button>
                <button type="button" className="tg-bp-btn is-dark" disabled={!ready} onClick={submit}>{busy ? 'Đang xử lý ảnh…' : 'Đăng bài'}</button>
              </div>
              <p className="tg-cp__hint">Bài được lưu trên trình duyệt này; khi máy chủ nhận bài viết, bài sẽ đồng bộ theo tài khoản của bạn.</p>
            </div>
          </>
        )}
      </div>

      <div className="tg-cp__page">
        <div className="tg-cp__me">
          <Avatar name={name} size={44} me />
          <div><b>{name}</b><button type="button" className="tg-cp__aud" onClick={() => setPanel(true)}><Icon name={vis === 'public' ? 'link' : vis === 'friends' ? 'users' : 'lock'} size={13} />{VIS[vis]}<Icon name="chevronDown" size={12} /></button></div>
        </div>

        <PlacePick value={placeId} places={snap?.places ?? []} onChange={setPlaceId} />

        <Grow className="tg-cp__title" label="Tiêu đề" placeholder="Tiêu đề" maxLength={140} value={title} onChange={(v) => setTitle(v.replace(/\n/g, ' '))}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); const f = items[0]; if (f) fields.current.get(f.id)?.focus() } }} />

        <div className="tg-cp__tb" role="toolbar" aria-label="Định dạng" aria-controls="tg-cp-body">
          <button type="button" aria-label="In đậm" title="In đậm (Ctrl+B)" onMouseDown={(e) => e.preventDefault()} onClick={() => mark('**')}><b>B</b></button>
          <button type="button" aria-label="In nghiêng" title="In nghiêng (Ctrl+I)" onMouseDown={(e) => e.preventDefault()} onClick={() => mark('*')}><i>I</i></button>
          <span aria-hidden="true" />
          <button type="button" aria-label="Tiêu đề phụ" title="Tiêu đề phụ" onMouseDown={(e) => e.preventDefault()} onClick={() => turn('h')}>H</button>
          <button type="button" aria-label="Trích dẫn" title="Trích dẫn" onMouseDown={(e) => e.preventDefault()} onClick={() => turn('q')}>“</button>
          <span aria-hidden="true" />
          <button type="button" className="is-wide" onClick={() => file.current?.click()} disabled={busy}><Icon name="image" size={17} />{busy ? 'Đang xử lý…' : 'Thêm ảnh'}</button>
          <input ref={file} type="file" accept="image/*" multiple hidden onChange={(e) => { void addImages([...(e.target.files ?? [])]); e.target.value = '' }} />
          <small>{images}/{MAX_IMAGES} ảnh</small>
        </div>

        <div className="tg-cp__body" id="tg-cp-body">
          {items.map((it, k) => it.b.t === 'img' ? (
            <figure key={it.id} className="tg-cp__fig" onFocus={() => { focus.current = it.id }}>
              <img src={it.b.src} alt={it.b.cap || 'Ảnh của bài viết'} />
              <div className="tg-cp__figtools">
                <button type="button" aria-label="Chuyển ảnh lên" disabled={k === 0} onClick={() => move(it.id, -1)}><Icon name="chevronUp" size={16} /></button>
                <button type="button" aria-label="Chuyển ảnh xuống" disabled={k === items.length - 1} onClick={() => move(it.id, 1)}><Icon name="chevronDown" size={16} /></button>
                <button type="button" aria-label="Xóa ảnh" onClick={() => remove(it.id)}><Icon name="trash" size={16} /></button>
              </div>
              <input value={it.b.cap} maxLength={140} placeholder="Thêm chú thích cho ảnh (không bắt buộc)" aria-label="Chú thích ảnh" onChange={(e) => patch(it.id, { t: 'img', src: (it.b as { src: string }).src, cap: e.target.value })} />
            </figure>
          ) : (
            <Grow
              key={it.id} className={`tg-cp__blk is-${it.b.t}`} label={it.b.t === 'h' ? 'Tiêu đề phụ' : it.b.t === 'q' ? 'Trích dẫn' : 'Đoạn văn'}
              placeholder={it.b.t === 'h' ? 'Tiêu đề phụ' : it.b.t === 'q' ? 'Một câu bạn muốn người đọc nhớ' : k === 0 && items.length === 1 ? 'Kể lại chuyến đi của bạn: đi lúc nào, thấy gì, điều gì bạn muốn người sau biết…' : 'Viết tiếp…'}
              value={it.b.text} inputRef={(el) => { if (el) fields.current.set(it.id, el); else fields.current.delete(it.id) }}
              onFocus={() => { focus.current = it.id }} onChange={(v) => patch(it.id, { t: it.b.t as 'p', text: v })} onKeyDown={(e) => onKey(it, e)}
            />
          ))}
        </div>
        <p className="tg-cp__tip">Enter xuống đoạn mới · dán hoặc kéo thả ảnh vào đây để thêm · **đậm** và *nghiêng* hiện khi đăng.</p>
      </div>
    </div>
  )
}

function TagInput({ tags, onChange }: { tags: string[]; onChange: (t: string[]) => void }) {
  const [v, setV] = useState('')
  const suggest = useMemo(() => popularTags(8).filter((t) => !tags.includes(t)).slice(0, 5), [tags])
  const add = (raw: string) => {
    const t = raw.trim().replace(/^#/, '').toLowerCase().slice(0, 30)
    if (t && !tags.includes(t) && tags.length < MAX_TAGS) onChange([...tags, t])
    setV('')
  }
  return (
    <div className="tg-cp__tags">
      <div className="tg-cp__tagbox">
        {tags.map((t) => <span key={t} className="tg-cp__tag">#{t}<button type="button" aria-label={`Bỏ thẻ ${t}`} onClick={() => onChange(tags.filter((x) => x !== t))}><Icon name="x" size={11} /></button></span>)}
        {tags.length < MAX_TAGS && <input id="tg-cp-tag" value={v} placeholder={tags.length ? '' : '#sănmây'} maxLength={30} onChange={(e) => setV(e.target.value)} onBlur={() => add(v)}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); add(v) } else if (e.key === 'Backspace' && !v && tags.length) onChange(tags.slice(0, -1)) }} />}
      </div>
      {suggest.length > 0 && tags.length < MAX_TAGS && <div className="tg-cp__sug"><small>Thẻ được dùng nhiều:</small>{suggest.map((t) => <button key={t} type="button" onClick={() => add(t)}>#{t}</button>)}</div>}
    </div>
  )
}

// The place the post is about: only places the snapshot has.
function PlacePick({ value, places, onChange }: { value: string | null; places: Parameters<typeof search>[1]; onChange: (id: string | null) => void }) {
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const away = (e: PointerEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false) }
    addEventListener('pointerdown', away)
    return () => removeEventListener('pointerdown', away)
  }, [])
  const hits = useMemo(() => (q.trim().length >= 2 ? search(q, places, 6) : []), [q, places])
  const p = value ? info(value) : null
  return (
    <div className="tg-cp__place" ref={box}>
      <span className="tg-cp__l">Bạn viết về nơi nào?</span>
      {p ? (
        <span className="tg-cp__chip"><span><PlacePic id={value!} /></span><span><b>{p.name}</b><small>{[p.category, p.area].filter(Boolean).join(' · ')}</small></span><button type="button" aria-label="Chọn nơi khác" onClick={() => { onChange(null); setQ('') }}><Icon name="x" size={12} /></button></span>
      ) : (
        <div className="tg-cp__find">
          <Icon name="search" size={16} />
          <input value={q} placeholder="Gõ tên địa điểm ở Đà Lạt" maxLength={80} autoComplete="off" onFocus={() => setOpen(true)} onChange={(e) => { setQ(e.target.value); setOpen(true) }} aria-label="Tìm địa điểm để gắn vào bài" />
          {open && q.trim().length >= 2 && (
            <ul role="listbox" aria-label="Địa điểm">
              {hits.map((h) => <li key={h.id}><button type="button" role="option" aria-selected={false} onClick={() => { onChange(h.id); setOpen(false) }}><span><PlacePic id={h.id} /></span><span><b>{h.name}</b><small>{[h.category, info(h.id)?.area].filter(Boolean).join(' · ')}</small></span></button></li>)}
              {hits.length === 0 && <li className="is-none">Không thấy nơi nào tên “{q}” trong TripGuardian.</li>}
            </ul>
          )}
        </div>
      )}
      {!p && <p className="tg-cp__hint">Chỉ chọn được nơi có trong TripGuardian. Bài chưa gắn được nơi sẽ không đăng.</p>}
    </div>
  )
}
