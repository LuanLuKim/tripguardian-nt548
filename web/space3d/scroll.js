// Tour by wheel. Inlined before the scene's animate(), so it shares its scope: once the tour has started, the wheel
// drives the camera along the route, one stop after the other in the place's order. One mouse notch is enough to
// reach the next stop; a lighter touch settles back. On the overview the wheel keeps zooming the model.
const WHEEL_PER_STOP = 320 // wheel distance from one stop to the next: about three mouse notches
const WHEEL_START = 24 // a stray touch of the wheel moves nothing (the rotary disc uses the same threshold)
const WHEEL_SETTLE_MS = 160
const scroll = { segment: null, pending: 0, carry: 0, carryDirection: 0, lastWheel: 0, lastFrame: 0, lastStep: 0 }
const stopIndex = () => (current ? place.hotspots.findIndex((spot) => spot.id === current.id) : -1)

function startSegment(direction, amount) {
  const from = stopIndex(), to = from + direction
  if (to < 0 || to >= place.hotspots.length) return tourEdge()
  const back = { position: camera.position.clone(), target: controls.target.clone() }
  tourRoute(from)
  goTour(to)
  if (!flight) return tourRoute(null) // reduced motion: the stop changes at once
  flight.scrub = true
  flight.q = 0
  scroll.segment = { from, to, direction, back, p: Math.min(amount, 1), q: 0, forward: true }
}

addEventListener('wheel', (event) => {
  if (!current || event.ctrlKey) return
  event.preventDefault()
  event.stopPropagation() // the orbit controls must not zoom during the tour
  const wheel = THREE.MathUtils.clamp(event.deltaY * (event.deltaMode === 1 ? 40 : 1), -120, 120)
  const now = performance.now()
  scroll.lastWheel = now
  if (flight && !flight.scrub) return // the flight of a click on a stop finishes first
  const segment = scroll.segment
  if (segment) {
    const step = wheel * segment.direction / WHEEL_PER_STOP
    segment.forward = step > 0
    segment.p = Math.max(0, segment.p + step)
    if (segment.p > 1) {
      scroll.carry = Math.min(segment.p - 1, .5)
      scroll.carryDirection = segment.direction
      segment.p = 1
    }
    return
  }
  if (Math.sign(scroll.pending) !== Math.sign(wheel)) scroll.pending = 0
  scroll.pending += wheel
  if (Math.abs(scroll.pending) < WHEEL_START) return
  if (reducedMotion.matches && now - scroll.lastStep < 700) return
  scroll.lastStep = now
  const direction = Math.sign(scroll.pending)
  const amount = Math.abs(scroll.pending) / WHEEL_PER_STOP
  scroll.pending = 0
  startSegment(direction, amount)
}, { capture: true, passive: false })

function scrollStep(now) {
  controls.enabled = !flight?.walk // a drag on the walk is a look round (freeLook), not an orbit
  const gap = now - scroll.lastFrame
  const elapsed = Math.min(gap, 100)
  scroll.lastFrame = now
  const segment = scroll.segment
  if (!segment) {
    if (scroll.carry > .3 && !flight && now - scroll.lastWheel < 220) startSegment(scroll.carryDirection, scroll.carry)
    scroll.carry = 0
    return
  }
  if (!flight?.scrub) { // a click or a key took over
    scroll.segment = null
    tourRoute(null)
    return
  }
  const settling = now - scroll.lastWheel > Math.max(WHEEL_SETTLE_MS, gap * 3) // a slow frame is not the end of a scroll
  if (settling) segment.p = (segment.forward ? segment.p > .25 : segment.p > .75) ? 1 : 0
  segment.q += (segment.p - segment.q) * (1 - Math.exp(-elapsed / (settling ? 170 : 90)))
  if (Math.abs(segment.p - segment.q) < .003) segment.q = segment.p
  flight.q = segment.q
  tourRoute(segment.from + (segment.to - segment.from) * segment.q)
  if (segment.q === 1) {
    scroll.segment = null
    tourRoute(null)
  } else if (segment.q === 0 && settling) { // scrolled back to where it began: nothing happened
    scroll.segment = null
    tourRoute(null)
    goTour(segment.from, true)
    camera.position.copy(segment.back.position)
    controls.target.copy(segment.back.target)
    controls.update()
  }
}
window.__tourBusy = () => Boolean(flight)
window.__viewState = () => camera.position.toArray().map((v) => Math.round(v * 100) / 100)

// Free look on the walk. While the camera walks the arrows the orbit controls step aside and a drag turns the head instead:
// yaw without limit, pitch within a quarter turn. The walk keeps going under the gaze; when it ends the gaze eases back to
// the stop's own view, so the camera never jumps to the destination because someone touched the mouse.
const look = { yaw: 0, pitch: 0, drag: null, last: 0 }
const LOOK_RATE = .0042 // radians per pixel
const walking = () => Boolean(flight?.walk)
renderer.domElement.addEventListener('pointerdown', (event) => {
  if (!walking() || event.button !== 0) return
  look.drag = { x: event.clientX, y: event.clientY, id: event.pointerId }
  renderer.domElement.setPointerCapture?.(event.pointerId)
})
renderer.domElement.addEventListener('pointermove', (event) => {
  if (!look.drag || event.pointerId !== look.drag.id) return
  look.yaw -= (event.clientX - look.drag.x) * LOOK_RATE
  look.pitch = THREE.MathUtils.clamp(look.pitch - (event.clientY - look.drag.y) * LOOK_RATE, -1.2, 1.2)
  look.drag.x = event.clientX
  look.drag.y = event.clientY
})
const endLook = (event) => { if (look.drag && event.pointerId === look.drag.id) look.drag = null }
renderer.domElement.addEventListener('pointerup', endLook)
renderer.domElement.addEventListener('pointercancel', endLook)
const lookQuaternion = new THREE.Quaternion(), lookUp = new THREE.Vector3(0, 1, 0)
function freeLook(now) {
  const elapsed = Math.min(now - (look.last || now), 100)
  look.last = now
  if (!walking() && !look.drag && (look.yaw || look.pitch)) {
    look.yaw = Math.atan2(Math.sin(look.yaw), Math.cos(look.yaw)) // the short way back
    const keep = Math.exp(-elapsed / 240)
    look.yaw *= keep
    look.pitch *= keep
    if (Math.abs(look.yaw) < 1e-3) look.yaw = 0
    if (Math.abs(look.pitch) < 1e-3) look.pitch = 0
  }
  if (!look.yaw && !look.pitch) return
  camera.quaternion.premultiply(lookQuaternion.setFromAxisAngle(lookUp, look.yaw))
  camera.quaternion.multiply(lookQuaternion.setFromAxisAngle(new THREE.Vector3(1, 0, 0), look.pitch))
  camera.updateMatrixWorld()
}
