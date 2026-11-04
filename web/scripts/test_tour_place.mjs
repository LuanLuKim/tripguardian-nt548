// Where the tour mascot stands around the lit element (src/user/tour/place.ts). Plain Node (type stripping), no browser.
// usage: node web/scripts/test_tour_place.mjs
import assert from 'node:assert/strict'
import { placeMascot } from '../src/user/tour/place.ts'

const VIEW = { w: 1440, h: 900 }
const SIZE = 150
const BUBBLE = 120
const BUBBLE_W = 260 // the speech bubble is wider than the mascot and sits right above it
const PAD = (BUBBLE_W - SIZE) / 2
const hits = (a, b) => a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y
// the mascot together with its bubble
const spot = (p) => ({ x: p.x - PAD, y: p.y - BUBBLE, w: BUBBLE_W, h: SIZE + BUBBLE })
const inside = (p) => p.x >= 0 && p.y >= BUBBLE && p.x + SIZE <= VIEW.w && p.y + SIZE <= VIEW.h
let n = 0
const check = (name, fn) => { fn(); n++; console.log('ok', name) }

check('target on the left -> mascot on its right, target is on the mascot\'s left', () => {
  const t = { x: 20, y: 300, w: 60, h: 60 }
  const p = placeMascot(t, VIEW, SIZE, BUBBLE, BUBBLE_W)
  assert.ok(p.x >= t.x + t.w && inside(p) && !hits(spot(p), t))
  assert.equal(p.side, 'left')
})
check('target on the far right -> mascot on its left, target is on the mascot\'s right', () => {
  const t = { x: 1300, y: 300, w: 120, h: 80 }
  const p = placeMascot(t, VIEW, SIZE, BUBBLE, BUBBLE_W)
  assert.ok(p.x + SIZE <= t.x && inside(p) && !hits(spot(p), t))
  assert.equal(p.side, 'right')
})
check('target at the very top: the bubble does not cover it (mascot goes below, bubble between)', () => {
  const t = { x: 116, y: 34, w: 346, h: 36 }
  const p = placeMascot(t, VIEW, SIZE, BUBBLE, BUBBLE_W)
  assert.ok(inside(p) && !hits(spot(p), t))
})
check('a wide target filling the width still finds a free spot', () => {
  const t = { x: 100, y: 90, w: 1240, h: 250 }
  const p = placeMascot(t, VIEW, SIZE, BUBBLE, BUBBLE_W)
  assert.ok(inside(p) && !hits(spot(p), t))
})
check('no target -> centered', () => {
  const p = placeMascot(null, VIEW, SIZE, BUBBLE, BUBBLE_W)
  assert.ok(Math.abs(p.x + SIZE / 2 - VIEW.w / 2) <= 1 && inside(p))
})
check('a target bigger than the screen still returns a point inside the screen', () => {
  const p = placeMascot({ x: 0, y: 0, w: 1440, h: 900 }, VIEW, SIZE, BUBBLE, BUBBLE_W)
  assert.ok(inside(p))
})
console.log(`${n} checks passed`)
