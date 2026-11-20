import { useEffect, useRef, useState, type CSSProperties, type RefObject } from 'react'

// TikTok clips, played only in TikTok's own embedded player (our server keeps no video file, only a clip's frames: the poster).
// Shared by the place sheet's Video tab (PlaceSheet.tsx) and the chat's clip stage (screens/understand/Clips.tsx).

// `preview`: no controls, muted, looping (a hover). Otherwise TikTok's controls stay (progress, sound, full screen).
export const playerSrc = (id: string, preview: boolean, autoplay = true) =>
  `https://www.tiktok.com/player/v1/${id}?autoplay=${autoplay ? 1 : 0}&rel=0&music_info=0&description=0${preview ? '&controls=0&progress_bar=0&play_button=0&volume_control=0&fullscreen_button=0&timestamp=0&loop=1' : '&loop=1'}`
// The player's page and script come from these two hosts: their connections open as soon as a clip is in reach, so the first
// one does not wait on DNS and TLS.
const PLAYER_HOSTS = ['https://www.tiktok.com', 'https://sf16-website-login.neutral.ttwstatic.com']
export function warmPlayer() {
  for (const href of PLAYER_HOSTS) {
    if (document.head.querySelector(`link[rel="preconnect"][href="${href}"]`)) continue
    const l = document.createElement('link')
    l.rel = 'preconnect'; l.href = href; l.crossOrigin = ''
    document.head.appendChild(l)
  }
}
export const poster = (id: string) => `/media/tiktok/${id}/frames/f1.jpg`
export const tell = (f: HTMLIFrameElement | null, type: string) => f?.contentWindow?.postMessage({ type, 'x-tiktok-player': true }, '*')
// The player says when it is ready: a preview is then muted (hovering never makes a sound), a clip waiting beside the viewer stays paused.
export function usePlayerReady(frame: RefObject<HTMLIFrameElement | null>, on: boolean, onReady: (w: HTMLIFrameElement) => void) {
  const ready = useRef(onReady)
  ready.current = onReady
  useEffect(() => {
    if (!on) return
    const f = (e: MessageEvent) => {
      const el = frame.current
      if (!el || e.source !== el.contentWindow || !e.data?.['x-tiktok-player']) return
      if (e.data.type === 'onPlayerReady') ready.current(el)
    }
    addEventListener('message', f)
    return () => removeEventListener('message', f)
  }, [frame, on])
}

// One clip of the stage: the place it shows is part of it (the stage runs across places).
export interface StageClip { id: string; url: string; handle: string | null; desc: string; placeId: string; place: string }

// One player of a vertical feed. The clip on screen plays; the ones just before and after load beside it, paused, so moving
// on shows them at once. The clip's own frame stands in its place until the player is ready, so nothing waits on a black box.
export function FeedPlayer({ v, current, paused, title, onPlay, className, slotStyle }: {
  v: { id: string; handle: string | null }; current: boolean; paused?: boolean; title: string; onPlay: () => void
  className: string; slotStyle?: CSSProperties
}) {
  const frame = useRef<HTMLIFrameElement>(null)
  const [ready, setReady] = useState(false)
  const live = current && !paused
  const isLive = useRef(live)
  isLive.current = live
  usePlayerReady(frame, true, (el) => { setReady(true); if (isLive.current) { tell(el, 'play'); onPlay() } else tell(el, 'pause') })
  useEffect(() => { if (ready) tell(frame.current, live ? 'play' : 'pause'); if (ready && live) onPlay() }, [live, ready]) // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className={`${className} ${current ? 'is-on' : ''} ${ready ? 'is-ready' : ''}`} style={slotStyle} aria-hidden={!current}>
      <img className="tg-cv__poster" src={poster(v.id)} alt="" decoding="async" onError={(e) => { e.currentTarget.style.visibility = 'hidden' }} />
      {!ready && current && <span className="tg-cv__wait" role="status" aria-label="Đang mở clip"><i /></span>}
      <iframe ref={frame} className="tg-cv__frame" src={playerSrc(v.id, false, current)} title={title} tabIndex={current ? 0 : -1} loading="eager" allow="autoplay; fullscreen; encrypted-media; picture-in-picture" allowFullScreen />
    </div>
  )
}
