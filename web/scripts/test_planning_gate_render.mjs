// Server rendering checks the real gate controls without needing a listening socket or Chromium.
import assert from 'node:assert/strict'
import { resolve } from 'node:path'
import { test } from 'node:test'
import React from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { renderToStaticMarkup } from 'react-dom/server'
import { build } from 'vite'

const bundle = await build({ configFile: false, root: resolve(import.meta.dirname, '..'), logLevel: 'error',
  define: { 'window.location.pathname': '"/app/explore"', window: 'undefined', document: '({})' },
  build: { ssr: resolve(import.meta.dirname, '../src/user/ui/Gate.tsx'), write: false, minify: false,
    rollupOptions: { output: { paths: id => import.meta.resolve(id) } } } })
const { GateAsk } = await import(`data:text/javascript;base64,${Buffer.from(bundle.output[0].code).toString('base64')}`)
const trip = { qid: 'trip', kind: 'required', header: 'Ngày đi', question: 'Bạn ở Đà Lạt từ ngày nào đến ngày nào?', why: '', inputs: ['dates'], options: [], multi: false }
const care = { qid: 'care', kind: 'required', header: 'Lưu ý', question: 'Có lưu ý sức khỏe, ăn uống?', why: '', inputs: [], options: [{ id: 'none', label: 'Không có', description: '', prefilled: false }], multi: true }
const render = tabs => renderToStaticMarkup(React.createElement(Dialog.Root, { open: true }, React.createElement(GateAsk, {
  deck: { tabs, left: tabs.length, total: 2 }, busy: false, issues: [], error: null, onAnswer() {}, onOther() {},
})))
test('dates-only gate renders a calendar, no hours, progress pill, ledger or read-back', () => {
  const html = render([trip])
  assert.match(html, /Chọn ngày đến và ngày về/)
  assert.match(html, /Sửa trong Tìm hiểu/)
  assert.doesNotMatch(html, /tg-gt__(?:hours|meter|ledger|check)|Đúng rồi, xếp lịch|Còn \d/)
  assert.doesNotMatch(html, /1\/1/)
})
test('care-only gate has one safety card, no calendar or optional questions', () => {
  const html = render([care])
  assert.equal((html.match(/class="tg-gt__card /g) ?? []).length, 1)
  assert.match(html, /Không có/)
  assert.doesNotMatch(html, /tg-gt__cal|Ngân sách|Phương tiện|Nơi lưu trú|Nhịp độ|1\/1/)
})
test('dates and care gate keeps two pastel cards without the seven-question counter', () => {
  const html = render([trip, care])
  assert.equal((html.match(/class="tg-gt__card /g) ?? []).length, 2)
  assert.doesNotMatch(html, /Còn \d|tg-gt__meter|Đúng rồi, xếp lịch/)
})
