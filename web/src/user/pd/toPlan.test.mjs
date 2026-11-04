import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

const source = readFileSync(new URL('./decision.tsx', import.meta.url), 'utf8')
const callback = source.slice(source.indexOf('  const toPlan = useCallback('), source.indexOf('\n  const ', source.indexOf('  const toPlan = useCallback(') + 10))

class DecisionError extends Error {
  constructor(status, detail) { super(detail); this.status = status; this.detail = detail }
}

async function rejected(detail) {
  const errors = []
  const context = {
    useCallback: fn => fn, id: 'fixture', location: { pathname: '/decision', search: '' },
    setBusy() {}, setGate() {}, setError: text => errors.push(text), dispatch() {},
    mutateJourney: async () => { throw new DecisionError(409, detail) },
    readJourney: async () => ({ missing: [] }), api: { DecisionError },
    explainError: () => 'offline', OFFLINE: 'offline',
  }
  const executable = callback.replace('readJourney<Readback>', 'readJourney').replace(' as DecisionOutput', '')
  vm.runInNewContext(executable + '\nglobalThis.run = toPlan', context)
  assert.equal(await context.run(), false)
  return errors.at(-1)
}

test('toPlan preserves a backend reason rather than blaming chosen places', async () => {
  assert.equal(await rejected('Chưa thể đọc dữ liệu chuyến đi. Vui lòng thử lại.'), 'Chưa thể đọc dữ liệu chuyến đi. Vui lòng thử lại.')
})

test('toPlan uses a neutral message for a bare backend code', async () => {
  const text = await rejected('partial')
  assert.equal(text, 'Chưa xếp lịch được lúc này. Bạn thử lại sau ít giây nhé.')
  assert.doesNotMatch(text, /thêm|đổi|đã chọn chưa đủ/)
})
