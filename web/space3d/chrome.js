// Runs first in the viewer bundle: loads the place, talks to the app (web/src/user/ui/Space3d.tsx), and owns the
// page chrome around the 3D scene (reveal, caption change, slow-machine fallback). The scene code knows none of this.
// Timing marks (Performance panel / checks): script start, place data in, scene built, first frame shown.
performance.mark('space3d:script')
const search = new URLSearchParams(location.search)
const poster = search.has('poster')
const tell = (type) => { if (parent !== window) parent.postMessage({ type }, location.origin) }

let ready = false
const failed = () => { if (!ready) tell('space3d:error') }
addEventListener('error', failed)
addEventListener('unhandledrejection', failed)
if (poster) document.documentElement.classList.add('is-poster')

// ?host=full: the page is the whole window (the app's "Khám phá 3D" dive), so it makes room for the app's Back button and
// hands Esc back to the app when there is no stop left to leave (on a stop, Esc still goes to the overview first).
const full = search.get('host') === 'full'
if (full) {
  document.documentElement.classList.add('is-full')
  addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !document.documentElement.classList.contains('is-touring')) tell('space3d:back')
  }, true)
}

async function loadPlace() {
  const slug = search.get('place') ?? ''
  if (!/^[a-z0-9-]+$/.test(slug)) throw new Error('bad place')
  const response = await fetch(`places/${slug}.json`)
  if (!response.ok) throw new Error(`place ${response.status}`)
  const place = await response.json()
  performance.mark('space3d:place')
  return place
}

// ?warm: the app built this frame ahead of the dive (web/src/user/ui/Space3d.tsx). After its first frame the scene stops
// drawing until the app shows it ('space3d:show'), and goes back to the overview and stops again when the app parks it
// after Back ('space3d:hide'). window.__paused is read at the top of the scene's animate().
const warm = search.has('warm')
let shown = !warm
window.__paused = false
addEventListener('message', (e) => {
  if (e.origin !== location.origin || e.source !== parent) return
  if (e.data?.type === 'space3d:show') {
    shown = true
    window.__paused = false
    if (ready) watchSpeed()
  }
  if (e.data?.type === 'space3d:hide') {
    shown = false
    window.__close?.()
    window.__paused = true
  }
})

// A weak GPU (integrated in an office laptop, a phone, a software renderer) starts without the ambient occlusion pass, at
// a capped pixel ratio and with a smaller shadow map: less to compile before the first frame, and a steady frame rate.
function weakGpu(gl) {
  if (poster) return false // the posters are stills at full quality, whatever renders them
  try {
    const info = gl.getExtension('WEBGL_debug_renderer_info')
    const name = String(gl.getParameter(info ? info.UNMASKED_RENDERER_WEBGL : gl.RENDERER))
    if (/swiftshader|llvmpipe|software|basic render/i.test(name)) return true
    if (/nvidia|geforce|quadro|rtx|radeon (rx|pro)|apple m\d|apple gpu/i.test(name)) return false
    return /intel|uhd|iris|hd graphics|radeon(\(tm\))? graphics|vega|mali|adreno|powervr|apple/i.test(name) || navigator.hardwareConcurrency <= 4
  } catch {
    return false
  }
}

// Half the frames slower than ~25 fps on a warmed-up scene: drop the ambient occlusion pass, keep the model.
let watching = false
function watchSpeed() {
  if (poster || watching) return
  watching = true
  const gaps = []
  let last = 0
  const step = (now) => {
    if (last) gaps.push(now - last)
    last = now
    if (gaps.length < 50) return requestAnimationFrame(step)
    const median = gaps.slice(10).sort((a, b) => a - b)[20]
    if (median > 40) window.__lowQuality?.()
  }
  requestAnimationFrame(step)
}

// The route line of the tour card. tourRoute(position) follows the wheel between two stops; null hands it back to tourStop.
let routeLive = false
function drawRoute(position) {
  const dots = document.getElementById('tour-dots')
  const last = dots.childElementCount - 1
  dots.style.setProperty('--route', String(last > 0 ? Math.max(position, 0) / last : 0))
  ;[...dots.children].forEach((dot, i) => dot.classList.toggle('is-past', i <= position + 0.02))
}
function tourRoute(position) {
  routeLive = position !== null
  document.getElementById('tour-dots').classList.toggle('is-live', routeLive)
  if (routeLive) drawRoute(position)
}

// Called by the scene on every stop change (-1 = the overview): the step label, the route and the scroll guide.
function tourStop(index, total) {
  document.documentElement.classList.toggle('is-touring', index >= 0)
  const dots = document.getElementById('tour-dots')
  if (dots.childElementCount !== total) {
    dots.replaceChildren(...Array.from({ length: total }, (_, i) => {
      const dot = document.createElement('button')
      dot.className = 'tour-dot'
      dot.setAttribute('aria-label', `Tới điểm ${i + 1}`)
      dot.onclick = () => document.querySelectorAll('.pin')[i]?.click()
      return dot
    }))
  }
  ;[...dots.children].forEach((dot, i) => (i === index ? dot.setAttribute('aria-current', 'step') : dot.removeAttribute('aria-current')))
  if (!routeLive) drawRoute(index)
  if (index < 0) return
  document.getElementById('tour-step').textContent = `Điểm ${index + 1} / ${total}`
  document.getElementById('tour-guide-text').textContent = index === total - 1
    ? 'Điểm cuối rồi, lăn lên để xem lại'
    : index === 0 ? 'Lăn chuột xuống để đi tiếp' : 'Lăn chuột lên hoặc xuống để đi tiếp'
}

// The wheel pushed past either end of the route: the guide answers, so the stillness does not read as broken.
function tourEdge() {
  const guide = document.getElementById('tour-guide')
  guide.classList.remove('is-bump')
  void guide.offsetWidth
  guide.classList.add('is-bump')
}

function sceneReady() {
  ready = true
  performance.mark('space3d:built')
  requestAnimationFrame(() => requestAnimationFrame(() => {
    document.documentElement.classList.add('is-ready')
    performance.mark('space3d:shown')
    if (!shown) window.__paused = true // warmed ahead: the first frame is drawn, the rest waits for the dive
    tell('space3d:ready')
    if (shown) watchSpeed()
  }))
  const copy = document.querySelector('.tour-copy')
  new MutationObserver(() => {
    copy.classList.remove('is-new')
    void copy.offsetWidth
    copy.classList.add('is-new')
  }).observe(document.getElementById('tour-title'), { childList: true, characterData: true, subtree: true })
}
