import { useEffect, useRef, useState, type CSSProperties, type KeyboardEvent } from 'react'
import { track } from '../../events'
import { info } from '../../lib'
import type { ClipsBlock } from '../../tu/types'
import { FeedPlayer, poster, warmPlayer } from '../../ui/clips'
import { HeartFill, Icon } from '../../ui/icons'
import { openPlace } from '../../ui/PlaceSheet'
import { StageFrame, useStage } from './Ask'
import '../../css/clips.css'

// One clip of the stage: the place it shows is part of it (a stage may run across places).
export interface StageClip { id: string; url: string; handle: string | null; desc: string; placeId: string; place: string }

// A place's own clips (the web's snapshot, as the place sheet's Video tab shows them), for the "▶ N clip" of a place card.
export function placeClips(id: string): StageClip[] {
  const p = info(id)
  return (p?.videos ?? []).map((v) => ({ id: v.id, url: v.url, handle: v.handle, desc: v.desc, placeId: id, place: p!.name }))
}

// The clip stage (owner 20/11/2026): clips on the same stage as the photo cards (the screen blurs behind it), read like
// TikTok: one tall clip in the middle, the one before and the one after peeking above and below it; the wheel, a swipe,
// ↑ ↓ or the round buttons move to the next. A tap on the clip pauses it; TikTok's own bar (time, sound, full screen)
// stays reachable along its bottom edge. Beside it: the place (opens its sheet), Thích (puts the place in the trip), who
// posted it, their words and the way out to TikTok. The feed may run across places: the place changes with the clip.
export function ClipStage({ clips, title, start = 0, liked, onLike, onClose }: {
  clips: StageClip[]; title: string; start?: number
  liked?: (placeId: string) => boolean; onLike?: (placeId: string, on: boolean) => void; onClose: () => void
}) {
  const { leaving, close } = useStage(true)
  const panel = useRef<HTMLDivElement>(null)
  const area = useRef<HTMLDivElement>(null)
  const n = clips.length
  const [at, setAt] = useState(Math.min(Math.max(0, start), Math.max(0, n - 1)))
  const [paused, setPaused] = useState(false)
  const go = (d: number) => { setAt((i) => Math.min(Math.max(0, i + d), n - 1)); setPaused(false) }
  const goRef = useRef(go)
  goRef.current = go
  const played = useRef(new Set<string>())
  const leave = (then?: () => void) => close(() => { onClose(); then?.() })
  useEffect(() => { warmPlayer() }, [])
  // One clip per wheel notch or swipe; a short rest between moves keeps a trackpad from racing through the feed.
  useEffect(() => {
    const el = area.current
    if (!el) return
    let rest = 0, sum = 0, y0: number | null = null
    const wheel = (e: WheelEvent) => {
      e.preventDefault()
      sum += e.deltaY
      const now = performance.now()
      if (Math.abs(sum) < 40 || now < rest) return
      goRef.current(Math.sign(sum)); sum = 0; rest = now + 450
    }
    const down = (e: TouchEvent) => { y0 = e.touches[0]?.clientY ?? null }
    const up = (e: TouchEvent) => {
      const y1 = e.changedTouches[0]?.clientY
      if (y0 !== null && y1 !== undefined && Math.abs(y1 - y0) > 48) goRef.current(y1 < y0 ? 1 : -1)
      y0 = null
    }
    el.addEventListener('wheel', wheel, { passive: false })
    el.addEventListener('touchstart', down, { passive: true })
    el.addEventListener('touchend', up, { passive: true })
    return () => { el.removeEventListener('wheel', wheel); el.removeEventListener('touchstart', down); el.removeEventListener('touchend', up) }
  }, [])
  const keys = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Escape') { e.preventDefault(); leave() }
    else if (e.key === 'ArrowDown' || e.key === 'j') { e.preventDefault(); go(1) }
    else if (e.key === 'ArrowUp' || e.key === 'k') { e.preventDefault(); go(-1) }
    else if (e.key === ' ' && !/BUTTON|A/.test((e.target as HTMLElement).tagName)) { e.preventDefault(); setPaused((p) => !p) }
  }
  if (!n) return null
  const v = clips[at]
  const on = liked?.(v.placeId) ?? false
  const desc = v.desc.replace(/\s+/g, ' ').trim()
  // the clip on screen and its two neighbours stay mounted (keyed by clip): moving on slides them, nothing reloads
  const near = [at - 1, at, at + 1].filter((k) => k >= 0 && k < n)
  return (
    <StageFrame leaving={leaving} kicker={`${n} clip`} kickerIcon="play" question={title} closeLabel="Đóng" onClose={() => leave()} onKeyDown={keys} panel={panel}>
      <div ref={area} className="tg-cs">
        <div className="tg-cs__feed" role="group" aria-roledescription="clip" aria-label={`Clip ${at + 1} trên ${n}: ${v.place}`}>
          {near.map((k) => (
            <FeedPlayer key={clips[k].id} v={clips[k]} current={k === at} paused={paused} className="tg-cs__slot" slotStyle={{ '--d': k - at, '--a': Math.abs(k - at) } as CSSProperties}
              title={`Clip TikTok của @${clips[k].handle ?? 'tiktok'} về ${clips[k].place}`}
              onPlay={() => { if (!played.current.has(clips[k].id)) { played.current.add(clips[k].id); track('evidence_play', { place_id: clips[k].placeId, video_id: clips[k].id }) } }} />
          ))}
          <button type="button" className="tg-cs__tap" onClick={() => setPaused((p) => !p)} aria-label={paused ? 'Phát tiếp' : 'Tạm dừng'}>
            {paused && <span className="tg-cs__paused"><Icon name="play" size={34} /></span>}
          </button>
          {at > 0 && <button type="button" className="tg-cs__peek is-up" onClick={() => go(-1)} aria-label="Clip trước" tabIndex={-1} />}
          {at < n - 1 && <button type="button" className="tg-cs__peek is-down" onClick={() => go(1)} aria-label="Clip sau" tabIndex={-1} />}
        </div>
        <aside className="tg-cs__info">
          <button type="button" className="tg-cs__place" onClick={() => leave(() => openPlace(v.placeId))} title="Xem nơi này">
            <Icon name="pin" size={15} /><b>{v.place}</b><Icon name="chevronRight" size={16} />
          </button>
          {onLike && <button type="button" className={`tg-cs__like ${on ? 'is-on' : ''}`} aria-pressed={on} onClick={() => onLike(v.placeId, !on)}>
            {on ? <HeartFill size={18} /> : <Icon name="heart" size={18} strokeWidth={2.2} />}{on ? 'Đã thích nơi này' : 'Thích nơi này'}
          </button>}
          <p className="tg-cs__who"><i>{(v.handle ?? 't').slice(0, 1).toUpperCase()}</i><b>@{v.handle ?? 'tiktok'}</b></p>
          {desc && <p className="tg-cs__desc">{desc}</p>}
          <a href={v.url} target="_blank" rel="noreferrer" className="tg-cs__out" onClick={() => track('outbound_click', { kind: 'tiktok', place_id: v.placeId })}>Mở trên TikTok <Icon name="external" size={14} /></a>
        </aside>
        {n > 1 && <div className="tg-cs__nav">
          <button type="button" onClick={() => go(-1)} disabled={at === 0} aria-label="Clip trước"><Icon name="chevronUp" size={22} /></button>
          <span className="tg-mono">{at + 1}/{n}</span>
          <button type="button" onClick={() => go(1)} disabled={at === n - 1} aria-label="Clip sau"><Icon name="chevronDown" size={22} /></button>
        </div>}
      </div>
      <p className="tg-stage__hint"><span className="tg-stage__mouse"><Icon name="mouse" size={18} /></span>Lăn chuột, vuốt hoặc ↑ ↓ để xem clip khác · bấm vào clip để dừng</p>
    </StageFrame>
  )
}

// The clips of a reply (place_clips), as one line in the chat like the photo stage's: three frames, the heading, how many
// and of which places. The stage never opens by itself (it would play a sound-capable player unasked): the user taps it.
export function ClipsLine({ block, busy, onLike }: { block: ClipsBlock; busy: boolean; onLike: (id: string, on: boolean) => void }) {
  const [open, setOpen] = useState(false)
  const [likes, setLikes] = useState(() => new Set(block.cards.filter((c) => c.liked).map((c) => c.id)))
  const clips: StageClip[] = block.clips.map((c) => ({ id: c.video_id, url: c.url, handle: c.handle, desc: c.caption, placeId: c.place_id, place: c.place }))
  if (!clips.length) return null
  const places = [...new Set(clips.map((c) => c.place))]
  const like = (id: string, on: boolean) => { setLikes((s) => { const t = new Set(s); if (on) t.add(id); else t.delete(id); return t }); onLike(id, on) }
  return <>
    <button type="button" className="tg-stage__reopen tg-clips__open" disabled={busy} onClick={() => { warmPlayer(); setOpen(true) }} onPointerEnter={warmPlayer}>
      <span className="tg-stage__thumbs" aria-hidden="true">{clips.slice(0, 3).map((c) => <img key={c.id} src={poster(c.id)} alt="" loading="lazy" decoding="async" />)}</span>
      <span><b>{block.title}</b><small>{clips.length} clip · {places.slice(0, 2).join(', ')}{places.length > 2 ? '…' : ''}</small></span>
      <Icon name="play" size={16} />
    </button>
    {open && <ClipStage clips={clips} title={block.title} liked={(id) => likes.has(id)} onLike={like} onClose={() => setOpen(false)} />}
  </>
}
