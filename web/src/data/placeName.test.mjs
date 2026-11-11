import { readFile } from 'node:fs/promises'
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { stripTypeScriptTypes } from 'node:module'

const code = stripTypeScriptTypes(await readFile(new URL('./placeName.ts', import.meta.url), 'utf8'), { mode: 'transform' })
const { displayName, tidyPlaceNames, setNameSwaps, tidyText } = await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`)

test('a name is capitalised, never shouting, never cut mid-word', () => {
  assert.equal(displayName('dồi Cù'), 'Dồi Cù')
  assert.equal(displayName('ĐÀ LẠT THIÊN VƯƠNG'), 'Đà Lạt Thiên Vương')
  assert.equal(displayName('ENJOY_VILLA'), 'Enjoy Villa')
  assert.equal(displayName('homy hostel'), 'Homy Hostel')
  assert.equal(displayName('Cá tầm Đà Lạt QUÁN ÁNH DƯƠNG CS2 .lẩu nướng cá tầm.Gà đồi cơm lam'), 'Cá tầm Đà Lạt Quán Ánh Dương CS2')
})

test('a tagline, a hashtag and a copy in another script are dropped', () => {
  assert.equal(displayName('Mộc Hương spa - Dưỡng sinh & chăm sóc sức khỏe'), 'Mộc Hương spa')
  assert.equal(displayName('CÁ TẦM CÂY ĐÀO QUÁN : Lẩu_Nướng. Gà Đồi_ Cơm Lam - quán cá tầm'), 'Cá Tầm Cây Đào Quán')
  assert.equal(displayName('Windy Valley 1- Homestay Đà Lạt'), 'Windy Valley 1')
  assert.equal(displayName('Massage Đà Lạt & Gội Đầu Dưỡng Sinh - MEM SPA (샴푸와 컨디셔너, 마사지)'), 'Massage Đà Lạt & Gội Đầu Dưỡng Sinh')
  assert.equal(displayName('실내 스크린 골프 & 연습장 / 달랏(Đà Lạt) sân tập golf trong nhà / LUIS GOLF CLUB'), 'Sân Tập Golf Trong Nhà')
})

test('acronyms and dotted names stay; long names stop at a word', () => {
  assert.equal(displayName('T.U.K Villa & Hotel'), 'T.U.K Villa & Hotel')
  assert.equal(displayName('KDL Rừng Thông Núi Voi - Elephant Mountain Pine Forest'), 'KDL Rừng Thông Núi Voi')
  const long = displayName('Một cái tên rất dài của một nơi nào đó ở Đà Lạt không có dấu phân cách nào cả')
  assert.ok(long.length <= 45 && long.endsWith('…'))
})

test('only objects carrying a place id are renamed', () => {
  const v = { cards: [{ id: '0x31:0xab', name: 'dồi Cù' }, { id: 'u1', name: 'AN NGUYEN' }], items: [{ place_id: '0x31:0xfe', name: 'ĐÀ LẠT' }] }
  tidyPlaceNames(v)
  assert.deepEqual([v.cards[0].name, v.cards[1].name, v.items[0].name], ['Dồi Cù', 'AN NGUYEN', 'Đà Lạt'])
})

test('a corpus name quoted in free text is swapped for the tidy one', () => {
  setNameSwaps([['Mộc Hương spa - Dưỡng sinh & chăm sóc sức khỏe', 'Mộc Hương spa'], ['Mộc Hương', 'x']])
  assert.equal(tidyText('Mình gợi ý Mộc Hương spa - Dưỡng sinh & chăm sóc sức khỏe nhé.'), 'Mình gợi ý Mộc Hương spa nhé.')
  assert.equal(tidyText('Cafe ZooDoo'), 'Cafe ZooDoo')
  const v = { say: 'Đến Mộc Hương spa - Dưỡng sinh & chăm sóc sức khỏe', notes: ['Mộc Hương spa - Dưỡng sinh & chăm sóc sức khỏe mở 8h'] }
  tidyPlaceNames(v)
  assert.deepEqual([v.say, v.notes[0]], ['Đến Mộc Hương spa', 'Mộc Hương spa mở 8h'])
})
