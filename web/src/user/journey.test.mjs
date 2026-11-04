import { readFile } from 'node:fs/promises'
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { stripTypeScriptTypes } from 'node:module'

const source = await readFile(new URL('./journey.ts', import.meta.url), 'utf8')
const code = stripTypeScriptTypes(source, { mode: 'transform' })
const journey = await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`)
const notifySource = (await readFile(new URL('./notify.ts', import.meta.url), 'utf8')).replace(/^import .*$/gm, '')
const notify = await import(`data:text/javascript;base64,${Buffer.from(stripTypeScriptTypes(notifySource, { mode: 'transform' })).toString('base64')}`)

test('notification preferences never expose a raw kind, including future kinds', () => {
  assert.equal(notify.notificationLabel('eve_replan'), 'Tối trước ngày đi: lịch cần đổi gì')
  assert.equal(notify.notificationLabel('paused'), 'Tạm dừng thông báo')
  assert.equal(notify.notificationLabel('future_kind'), 'Thông báo khác')
})

test('stale revision refreshes the journey before retrying', async () => {
  const id = 'test-stale'
  let requests = 0
  let reads = 0
  globalThis.fetch = async (_url, init) => {
    if (!init) return Response.json({ id, stage: 'decision', revision: ++reads, sessions: {}, outputs: {}, result: null })
    requests++
    if (requests === 1) return Response.json({ error: 'stale revision' }, { status: 409 })
    const view = { id, stage: 'planning', revision: 3, sessions: {}, outputs: {}, result: null }
    return new Response(`data: ${JSON.stringify({ request_id: JSON.parse(init.body).request_id, stage: 'planning', revision: 3, event: 'journey', data: view })}\n\n`, { headers: { 'Content-Type': 'text/event-stream' } })
  }
  await journey.loadJourney(id)
  const result = await journey.mutateJourney(id, 'decision', 'advance')
  assert.equal(result.stage, 'planning')
  assert.equal(requests, 2)
  assert.equal(reads, 2)
})

test('incomplete trip is reported without retrying the advance', async () => {
  const id = 'test-incomplete'
  let requests = 0
  globalThis.fetch = async (_url, init) => {
    if (!init) return Response.json({ id, stage: 'decision', revision: 1, sessions: {}, outputs: {}, result: null })
    requests++
    assert.equal(init.headers.Accept, 'text/event-stream')
    const req = JSON.parse(init.body)
    return new Response(`data: ${JSON.stringify({ request_id: req.request_id, stage: req.stage, revision: req.expected_revision, event: 'error', data: { status: 409, error: 'trip_incomplete', missing: ['days'], readback: { missing: ['days'] } } })}\n\n`, { headers: { 'Content-Type': 'text/event-stream' } })
  }
  await journey.loadJourney(id)
  await assert.rejects(journey.mutateJourney(id, 'decision', 'advance'), e => e.detail === 'trip_incomplete')
  assert.equal(requests, 1)
})
