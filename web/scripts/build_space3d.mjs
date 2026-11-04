// Builds the "Khám phá 3D" viewer into web/public/space3d (docs/Role_Web_Functional_Design.md §6):
//   viewer.html + viewer-<hash>.js   one shared viewer: scene code + every kit + three, no CDN
//   places/<slug>.json               the data of each place in web/space3d/places.json (the approved list)
//   index.json                       place id -> slug, what the place sheet reads to show the tab
// The scene code and kits are authored under DIORAMA_DIR (logs/splat/diorama, docs/plans/DIORAMA_BATCH_HANDOFF.md);
// the page chrome is web/space3d/. Each PATCH below fails the build if the scene code stops matching it.
// usage: node web/scripts/build_space3d.mjs
import { createHash } from 'node:crypto'
import { copyFileSync, existsSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { rolldown } from 'rolldown'

const WEB = resolve(import.meta.dirname, '..')
const SOURCE = resolve(process.env.DIORAMA_DIR ?? join(WEB, '../logs/splat/diorama'))
const CHROME = join(WEB, 'space3d')
const OUT = join(WEB, 'public/space3d')
const THREE = join(SOURCE, 'vendor/node_modules/three') // the version the approved models were rendered with

const places = JSON.parse(readFileSync(join(CHROME, 'places.json'), 'utf8'))
const template = readFileSync(join(SOURCE, 'index.template.html'), 'utf8')
const scene = template.match(/<script type="module">([\s\S]*)<\/script>/)[1]

// Authoring output is a single page with a full-window layout; the viewer is a stage inside the sheet.
const PATCH = [
  [/^const (\w+|\{ \w+ \}) = await import\("(three[^"]*)"\);$/gm, ''],
  ['const place = __PLACE__;', 'const place = await loadPlace();'],
  // A stop frames the model beside the tour card; the overview leaves room for the start button.
  ['const left = 40, right = 40, top = focused ? 150 : 100, bottom = 140;', 'const left = focused ? document.querySelector(".tour-card").offsetWidth * .6 : 24, right = 24, top = 24, bottom = focused ? 24 : 72;'],
  ['y>=135&&y<=innerHeight-135', 'y>=24&&y<=innerHeight-(current?24:72)'],
  ['`${index+1} / ${place.hotspots.length} · ${current.title}`', 'current.title'],
  ['$("tour-next").textContent=index===place.hotspots.length-1 ? "Xem toàn cảnh" : "Tiếp →";', 'tourStop(index,place.hotspots.length);'],
  // The wheel drives the flight between two stops (web/space3d/scroll.js); a click still flies on the clock.
  ['function animate(now) {', () => `${readFileSync(join(CHROME, 'scroll.js'), 'utf8')}\nfunction animate(now) {`],
  ['  if (flight) {\n    const progress = Math.min((now - flight.start) / 1400, 1),', '  scrollStep(now);\n  if (flight) {\n    const progress = flight.scrub ? flight.q : Math.min((now - flight.start) / 1400, 1),'],
  ['window.__ready = true;', `window.__lowQuality = () => { gtao.enabled = false; renderer.setPixelRatio(1); composer.setPixelRatio(1); };
window.__ready = true;
sceneReady();`],
]
let code = scene
for (const [from, to] of PATCH) {
  const next = code.replace(from, to)
  if (next === code) throw new Error(`scene code no longer matches: ${from}`)
  code = next
}

// Kits reach the scene's helpers through module scope, so they are inlined; each runs only for the places that list it.
const kits = readdirSync(join(SOURCE, 'kits')).filter((f) => f.endsWith('.js') && f !== 'example.js').sort()
const kitCode = kits.map((f) => `if ((place.kits ?? []).includes(${JSON.stringify(f.slice(0, -3))})) {\n${readFileSync(join(SOURCE, 'kits', f), 'utf8')}\n}`).join('\n')
if (!code.includes('/*__KITS__*/')) throw new Error('scene code lost the kit slot')
code = code.replace('/*__KITS__*/', () => kitCode)

const imports = scene.matchAll(/^const (\w+|\{ \w+ \}) = await import\("(three[^"]*)"\);$/gm)
const header = [...imports].map(([, name, from]) => `import ${name === 'THREE' ? '* as THREE' : name} from ${JSON.stringify(from)};`).join('\n')
const entry = `${header}\n${readFileSync(join(CHROME, 'chrome.js'), 'utf8')}\n${code}`

const bundle = await rolldown({
  input: 'space3d-viewer',
  logLevel: 'warn',
  resolve: { alias: { 'three/addons': join(THREE, 'examples/jsm'), three: join(THREE, 'build/three.module.js') } },
  plugins: [{
    name: 'entry',
    resolveId: (id) => (id === 'space3d-viewer' ? id : null),
    load: (id) => (id === 'space3d-viewer' ? entry : null),
  }],
})
const { output } = await bundle.generate({ format: 'esm', minify: true, codeSplitting: false })
await bundle.close()
const js = output[0].code
const name = `viewer-${createHash('sha256').update(js).digest('hex').slice(0, 10)}.js`

// Posters survive a rebuild: only web/scripts/shots_space3d.mjs makes them.
for (const f of existsSync(OUT) ? readdirSync(OUT) : []) if (f !== 'posters') rmSync(join(OUT, f), { recursive: true })
mkdirSync(join(OUT, 'places'), { recursive: true })
writeFileSync(join(OUT, name), js)
writeFileSync(join(OUT, 'viewer.html'), readFileSync(join(CHROME, 'viewer.html'), 'utf8').replace('<!--VIEWER_SCRIPT-->', `<script type="module" src="${name}"></script>`))

const index = {}
for (const { slug, id, source } of places) {
  const place = JSON.parse(readFileSync(join(SOURCE, source), 'utf8'))
  delete place.evidence // working notes of the author, the viewer never reads them
  for (const spot of place.hotspots) delete spot.photos
  // Photos a model hangs on its walls (kits load 'photos/' + name): one folder per place, the names stay unique.
  for (const building of place.objects) {
    const interior = building.interior
    if (!interior?.photoAssets) continue
    mkdirSync(join(OUT, 'photos', slug), { recursive: true })
    for (const file of interior.photoAssets) copyFileSync(join(SOURCE, dirname(source), 'photos', file), join(OUT, 'photos', slug, file))
    interior.photoAssets = interior.photoAssets.map((file) => `${slug}/${file}`)
  }
  writeFileSync(join(OUT, 'places', `${slug}.json`), JSON.stringify(place))
  index[id] = slug
}
writeFileSync(join(OUT, 'index.json'), JSON.stringify(index))
console.log(`[space3d] ${name} ${(js.length / 1024).toFixed(0)} KB, ${places.length} places, kits: ${kits.join(' ')}`)
