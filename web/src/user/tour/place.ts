export type Rect = { x: number; y: number; w: number; h: number }
export type Spot = { x: number; y: number; side: 'left' | 'right' }

const GAP = 22
const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v))
const hits = (a: Rect, b: Rect) => a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y

// Where the mascot stands (top-left of its box) so neither it nor its speech bubble covers the lit element. The bubble is `bubbleW`
// wide and `bubbleH` tall, centered right above the mascot. Beside the element on the roomier side if it fits, else below (the bubble
// then sits between the element and the mascot), else above. `side` says on which side of the mascot the element is, so the pointing
// paw can turn toward it. No element: the middle of the screen.
export function placeMascot(target: Rect | null, view: { w: number; h: number }, size: number, bubbleH: number, bubbleW = size): Spot {
  const over = Math.max(0, (bubbleW - size) / 2) // how far the bubble sticks out on each side of the mascot
  const fit = (x: number, y: number) => ({ x: clamp(x, 0, Math.max(0, view.w - size)), y: clamp(y, bubbleH, Math.max(bubbleH, view.h - size)) })
  if (!target) {
    const c = fit((view.w - size) / 2, (view.h - size) / 2)
    return { ...c, side: 'right' }
  }
  const cx = target.x + target.w / 2
  const cy = target.y + target.h / 2
  const right = fit(target.x + target.w + GAP + over, cy - size / 2)
  const left = fit(target.x - size - GAP - over, cy - size / 2)
  const below = fit(cx - size / 2, target.y + target.h + GAP + bubbleH)
  const above = fit(cx - size / 2, target.y - size - GAP)
  const order = cx < view.w / 2 ? [right, left, below, above] : [left, right, below, above]
  const clear = (p: { x: number; y: number }) => !hits({ x: p.x - over, y: p.y - bubbleH, w: size + 2 * over, h: size + bubbleH }, target)
  const free = order.find(clear) ?? order[0]
  return { ...free, side: cx > free.x + size / 2 ? 'right' : 'left' }
}
