import { useEffect, useRef, useState } from 'react'
import { Icon } from './icons'

// "Khám phá 3D" tab of the place sheet (docs/Role_Web_Functional_Design.md §6). The model runs in a same-origin iframe
// built by web/scripts/build_space3d.mjs: its scene owns the whole window, and removing the frame frees the GPU.
// The tab exists only for a place in /space3d/index.json; the poster holds the stage until the model has drawn.

let models: Promise<Record<string, string>> | undefined
const loadModels = () => (models ??= fetch('/space3d/index.json').then((r) => r.json() as Promise<Record<string, string>>).catch(() => ({} as Record<string, string>)))

// The model of this place, or null while unknown and for a place without one.
export function useSpace3d(id: string): string | null {
  const [slug, setSlug] = useState<string | null>(null)
  useEffect(() => {
    let on = true
    setSlug(null)
    void loadModels().then((all) => { if (on) setSlug(all[id] ?? null) })
    return () => { on = false }
  }, [id])
  return slug
}

export function Space3d({ slug, name }: { slug: string; name: string }) {
  const stage = useRef<HTMLDivElement>(null)
  const frame = useRef<HTMLIFrameElement>(null)
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading')
  const [full, setFull] = useState(false)

  useEffect(() => {
    const onMessage = (e: MessageEvent) => {
      if (e.origin !== location.origin || e.source !== frame.current?.contentWindow) return
      if (e.data?.type === 'space3d:ready') setState('ready')
      if (e.data?.type === 'space3d:error') setState('error')
    }
    const onFull = () => setFull(document.fullscreenElement === stage.current)
    window.addEventListener('message', onMessage)
    document.addEventListener('fullscreenchange', onFull)
    return () => {
      window.removeEventListener('message', onMessage)
      document.removeEventListener('fullscreenchange', onFull)
    }
  }, [])

  const toggleFull = () => {
    if (document.fullscreenElement) void document.exitFullscreen()
    else void stage.current?.requestFullscreen()
  }

  return (
    <div className="tg-s3">
      <h3>Khám phá 3D</h3>
      <p className="tg-pano__note">
        <Icon name="info" size={16} />
        <span>Mô hình minh họa dựng từ ảnh thực tế của nơi này. Tỷ lệ và chi tiết chỉ để tham khảo, có thể khác ngoài đời.</span>
      </p>
      <div className="tg-s3__stage" ref={stage} data-state={state} aria-busy={state === 'loading'}>
        {state !== 'error' && <iframe ref={frame} title={`Mô hình 3D của ${name}`} src={`/space3d/viewer.html?place=${slug}`} allow="fullscreen" />}
        <img className="tg-s3__poster" src={`/space3d/posters/${slug}.webp`} alt="" />
        {state === 'loading' && <div className="tg-s3__wait" role="status"><Icon name="compass" size={18} /> Đang dựng mô hình…</div>}
        {state === 'error' && (
          <div className="tg-s3__wait is-error" role="alert">
            Máy này chưa mở được mô hình 3D. Bạn vẫn xem được nơi này ở phần Hình ảnh.
          </div>
        )}
        {state === 'ready' && (
          <button type="button" className="tg-s3__full" onClick={toggleFull} aria-label={full ? 'Thu nhỏ mô hình' : 'Xem toàn màn hình'} title={full ? 'Thu nhỏ' : 'Toàn màn hình'}>
            <Icon name={full ? 'shrink' : 'expand'} size={18} />
          </button>
        )}
      </div>
    </div>
  )
}
