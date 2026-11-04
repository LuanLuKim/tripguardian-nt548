import { test } from 'node:test'
import assert from 'node:assert/strict'
import { cardLines } from '../cardLines.ts'

const base = { why: [], tradeoffs: [], failed: [], unverified: [], warnings: [], depends_on_unknown: null }
test('pet claims retain their source text and sid outside reasons and tradeoffs', () => {
  const out = cardLines({ ...base, why: [{ text: 'Cho mang thú cưng, theo 7 người', sid: 'pets' }, { text: 'Yên tĩnh', sid: 'noise' }], tradeoffs: [{ text: 'Cuối tuần đông', sid: 'crowd' }] })
  assert.deepEqual(out, { why: [{ text: 'Yên tĩnh', sid: 'noise' }], trade: 'Cuối tuần đông', alerts: [], pets: [{ text: 'Cho mang thú cưng, theo 7 người', sid: 'pets' }] })
})
test('failed pet filter is not a warning; other failed filters stay warnings', () => {
  const out = cardLines({ ...base, tradeoffs: [{ text: 'Không cho mang thú cưng, theo 4 người', sid: 'pets' }], failed: ['Mang thú cưng: không cho phép', 'Có chỗ đỗ xe: không'] })
  assert.equal(out.trade, 'Không hợp điều kiện của bạn: Có chỗ đỗ xe: không')
  assert.deepEqual(out.alerts, [])
  assert.deepEqual(out.pets, [{ text: 'Không cho mang thú cưng, theo 4 người', sid: 'pets' }])
})
test('unknown pet copy stays a plain attribute while other unknowns remain unchanged', () => {
  assert.deepEqual(cardLines({ ...base, unverified: ['Chưa rõ có cho mang thú cưng không', 'Chưa xác minh được: bãi đỗ xe'] }), {
    why: [], trade: 'Chưa xác minh được: bãi đỗ xe', alerts: [], pets: [{ text: 'Chưa rõ có cho mang thú cưng không', sid: null }],
  })
})
test('non-pet ordering, reason limit and alert limit remain unchanged', () => {
  const why = ['A', 'B', 'C', 'D'].map(text => ({ text, sid: null }))
  assert.deepEqual(cardLines({ ...base, why, tradeoffs: [{ text: 'T1', sid: null }, { text: 'T2', sid: null }], failed: ['F'], unverified: ['U'], warnings: ['W'], depends_on_unknown: 'D' }), {
    why: why.slice(0, 3), trade: 'T1', alerts: ['T2', 'Không hợp điều kiện của bạn: F'], pets: [],
  })
})
