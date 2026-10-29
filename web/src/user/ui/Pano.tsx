import { useState } from 'react'
import { track } from '../events'
import { streetViewEmbed, streetViewLink } from '../../data/store'
import { Icon } from './icons'

// "Xem 360°" tab of the place sheet (docs/Role_Web_Functional_Design.md §6). The Google embed only starts on a click:
// it is third party, heavy, and sets its own cookies. The stage keeps one size from cover to loaded view.
export function Pano({ id, name, lat, lng }: { id: string; name: string; lat: number; lng: number }) {
  const [started, setStarted] = useState(false)
  const [ready, setReady] = useState(false)
  const at = { lat, lng }
  return (
    <div className="tg-pano">
      <h3>Xem 360°</h3>
      <p className="tg-pano__note">
        <Icon name="info" size={16} />
        <span>Đây là ảnh 360° gần nhất do Google và người dùng đăng. Có thể là mặt tiền hoặc chỗ lân cận, không phải bên trong nơi này.</span>
      </p>
      <div className="tg-pano__stage" aria-busy={started && !ready}>
        {started ? (
          <>
            <iframe title={`Ảnh 360° gần ${name}`} src={streetViewEmbed(at)} allow="fullscreen" referrerPolicy="no-referrer-when-downgrade" onLoad={() => setReady(true)} />
            {!ready && <div className="tg-pano__wait" role="status"><Icon name="compass" size={22} /> Đang mở ảnh 360°…</div>}
          </>
        ) : (
          <div className="tg-pano__cover">
            <button type="button" className="tg-btn tg-btn--primary" onClick={() => setStarted(true)}>
              <Icon name="compass" size={18} /> Xem ảnh 360° quanh đây
            </button>
            <small>Kéo để nhìn quanh, bấm mũi tên trên đường để đi tiếp.</small>
          </div>
        )}
      </div>
      <a href={streetViewLink(at)} target="_blank" rel="noreferrer" className="tg-link tg-pano__out" onClick={() => track('outbound_click', { kind: 'streetview', place_id: id })}>
        Mở Street View trên Google Maps <Icon name="external" size={14} />
      </a>
    </div>
  )
}
