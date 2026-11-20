import { useEffect, useState } from 'react'
import { useSnapshot } from '../../data/store'
import { info } from '../lib'
import { go } from '../ui/common'
import { Icon } from '../ui/icons'
import { openPlace } from '../ui/PlaceSheet'
import { loadModels } from '../ui/Space3d'
import { FEATURED, FEATURED_COVERS, FEATURED_ID } from './featured'
import { postHref } from './parts'

// The places of a gallery block that really have a 3D model on this server: the post never lists one that is missing (/space3d/index.json).
export function Tour3d({ title, ids }: { title: string; ids: string[] }) {
  const [models, setModels] = useState<Record<string, string> | null>(null)
  useEffect(() => { void loadModels().then(setModels) }, [])
  useSnapshot()
  const shown = ids.filter((id) => models?.[id] && info(id))
  if (!models || !shown.length) return null
  return (
    <section className="tg-3d" aria-label={title}>
      <h3><Icon name="cube" size={17} />{title}<small>{shown.length} nơi</small></h3>
      <ul>
        {shown.map((id) => {
          const p = info(id)!
          return (
            <li key={id}>
              <button type="button" onClick={() => openPlace(id)} aria-label={`${p.name}: mở trang nơi, chọn tab Khám phá 3D`}>
                <img src={`/space3d/posters/${models[id]}.webp`} alt="" loading="lazy" decoding="async" />
                <i aria-hidden="true"><Icon name="cube" size={12} />3D</i>
                <b>{p.name}</b>
                {p.category && <small>{p.category}</small>}
              </button>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

// The pinned post, above the lists of the Bài viết screen: a dark card with three tilted model posters and a ring of light that keeps moving.
export function FeaturedBanner() {
  return (
    <article className="tg-feat">
      <button type="button" onClick={() => go(postHref(FEATURED_ID))} aria-label={`Đọc bài: ${FEATURED.title}`}>
        <span className="tg-feat__txt">
          <span className="tg-feat__tag"><Icon name="cube" size={13} />Khám phá 3D<em>Mới</em></span>
          <strong>Đi một vòng Đà Lạt trước khi đến</strong>
          <small>Hơn 100 nơi đã có mô hình 3D: xoay, phóng to và đi dạo ở tầm mắt người đi bộ.</small>
          <span className="tg-feat__go">Đọc bài giới thiệu<Icon name="arrow" size={15} /></span>
        </span>
        <span className="tg-feat__art" aria-hidden="true">{FEATURED_COVERS.map((src, i) => <img key={src} src={src} alt="" loading="lazy" style={{ '--k': i } as React.CSSProperties} />)}</span>
      </button>
    </article>
  )
}
