import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { stripTypeScriptTypes } from 'node:module'

function store() {
  const source = readFileSync(new URL('../src/user/store.ts', import.meta.url), 'utf8')
  const code = stripTypeScriptTypes(source).replace(/^import .*$/gm, '').replace(/^export /gm, '')
  return vm.runInNewContext(code + '\n;({ getUi, pushMsg, editMsg, clearMsgs })', {
    useSyncExternalStore: () => {}, FORGET_EVENT: 'forget', localStorage: { getItem: () => null }, setTimeout, clearTimeout,
  })
}

test('new chat clears only the selected stage, including legacy untagged decision messages', () => {
  const s = store()
  s.pushMsg({ role: 'user', text: 'legacy decision' })
  s.pushMsg({ role: 'bot', text: 'decision reply', stage: 'decision' })
  const planning = s.pushMsg({ role: 'user', text: 'planning', stage: 'planning' })
  s.clearMsgs('decision')
  assert.equal(s.getUi().assistant.msgs.length, 1)
  assert.equal(s.getUi().assistant.msgs[0].id, planning)
  s.clearMsgs('decision')
  assert.equal(s.getUi().assistant.msgs.length, 1)
  s.clearMsgs('planning')
  assert.equal(s.getUi().assistant.msgs.length, 0)
})

test('global clear remains compatible and message ids are never reused after a stage reset', () => {
  const s = store()
  const first = s.pushMsg({ role: 'bot', text: 'old', stage: 'planning' })
  s.clearMsgs('planning')
  const next = s.pushMsg({ role: 'bot', text: 'new', stage: 'planning' })
  s.editMsg(first, { text: 'late reply' })
  assert.ok(next > first)
  assert.equal(s.getUi().assistant.msgs[0].text, 'new')
  s.clearMsgs()
  assert.equal(s.getUi().assistant.msgs.length, 0)
})
