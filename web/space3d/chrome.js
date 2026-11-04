// Runs first in the viewer bundle: loads the place, talks to the app (web/src/user/ui/Space3d.tsx), and owns the
// page chrome around the 3D scene (reveal, caption change, slow-machine fallback). The scene code knows none of this.
const search = new URLSearchParams(location.search)
const poster = search.has('poster')
const tell = (type) => { if (parent !== window) parent.postMessage({ type }, location.origin) }

let ready = false
const failed = () => { if (!ready) tell('space3d:error') }
addEventListener('error', failed)
addEventListener('unhandledrejection', failed)
if (poster) document.documentElement.classList.add('is-poster')

async function loadPlace() {
  const slug = search.get('place') ?? ''
  if (!/^[a-z0-9-]+$/.test(slug)) throw new Error('bad place')
  const response = await fetch(`places/${slug}.json`)
  if (!response.ok) throw new Error(`place ${response.status}`)
  return response.json()
}

// Half the frames slower than ~25 fps on a warmed-up scene: drop the ambient occlusion pass, keep the model.
function watchSpeed() {
  if (poster) return
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
  requestAnimationFrame(() => requestAnimationFrame(() => {
    document.documentElement.classList.add('is-ready')
    tell('space3d:ready')
    watchSpeed()
  }))
  const copy = document.querySelector('.tour-copy')
  new MutationObserver(() => {
    copy.classList.remove('is-new')
    void copy.offsetWidth
    copy.classList.add('is-new')
  }).observe(document.getElementById('tour-title'), { childList: true, characterData: true, subtree: true })
}
