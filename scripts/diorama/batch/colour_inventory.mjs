// Colour inventory of one built place, no browser: which colours its kits paint, on which object types, how much area.
// Usage: node scripts/diorama/batch/colour_inventory.mjs <slug> [min%=0.3]
// Prints one line per colour: share of painted area, colour after place.colorMap, top object types / ids.
// Keys are the raw colour strings the builders pass to box/detail/mesh, i.e. what `place.colorMap` maps.
import fs from 'node:fs';
import {CODE, DATA} from '../paths.mjs';
import {join} from 'node:path';
import vm from 'node:vm';
import {spawnSync} from 'node:child_process';
import * as THREE from '../vendor/node_modules/three/build/three.module.js';
import {mergeGeometries} from '../vendor/node_modules/three/examples/jsm/utils/BufferGeometryUtils.js';

const slug = process.argv[2], minShare = Number(process.argv[3] ?? .3), asJson = process.argv.includes('--json');
const source = join(DATA, slug === 'linhson' ? 'linhson.json' : `places/${slug}/place.json`), out = join(DATA, `out_${slug}/inventory-build`);
const build = spawnSync('python3', ['-B', join(CODE, 'build.py'), source, out], {encoding: 'utf8'});
if (build.status) { console.log(build.stdout + build.stderr); process.exit(1); }
let html = fs.readFileSync(out + '/index.html', 'utf8');
const head = '  if (!mats.has(color)) mats.set(color, new THREE.MeshStandardMaterial({';
if (!html.includes(head)) { console.log('hook not found in material()'); process.exit(1); }
html = html.replace(head, '  __rec(color,currentObject);\n' + head);
for (const h of ['function box(x, y, z, w, h, d, color, part = null) {', 'function mesh(geometry, color, x, y, z, outlined = true) {',
  'function detail(key, geometry, color, position, scale, rotation = 0, lean = 0, part = null) {']) {
  if (!html.includes(h)) { console.log('hook not found: ' + h); process.exit(1); }
  html = html.replace(h, h + '__rec(typeof color==="string"?color.toLowerCase():color,currentObject);');
}
const stats = new Map(), areaCache = new WeakMap();
function area(geometry, scale) {
  let a = areaCache.get(geometry);
  if (a === undefined) {
    a = 0;
    const g = geometry.index ? geometry.toNonIndexed() : geometry, p = g.getAttribute('position');
    const A = new THREE.Vector3(), B = new THREE.Vector3(), C = new THREE.Vector3();
    if (p) for (let i = 0; i + 2 < p.count; i += 3) {
      A.fromBufferAttribute(p, i); B.fromBufferAttribute(p, i + 1); C.fromBufferAttribute(p, i + 2);
      a += B.sub(A).cross(C.sub(A)).length() / 2;
    }
    areaCache.set(geometry, a);
  }
  return scale ? a * Math.pow(Math.abs(scale[0] * scale[1] * scale[2]), 2 / 3) : a;
}
const canvas = new Proxy({measureText: t => ({width: t.length * 24}), createImageData: (w, h) => ({data: new Uint8ClampedArray(w * h * 4)})}, {get: (t, k) => t[k] ?? (() => {})});
const elements = new Map();
const element = () => ({style: {setProperty() {}}, dataset: {}, classList: {add() {}, toggle() {}}, appendChild() {}, setAttribute() {}, addEventListener() {}, querySelector: () => element(), getContext: () => canvas});
const document = {body: element(), createElement: element, createElementNS: element, getElementById: id => { if (!elements.has(id)) elements.set(id, element()); return elements.get(id); }};
class Renderer { constructor() { this.domElement = element(); this.shadowMap = {}; this.info = {render: {}, reset() {}}; } setPixelRatio() {} setSize() {} getContext() { return {finish() {}}; } }
class PMREM { fromScene() { return {texture: null}; } dispose() {} }
class Controls { constructor(c) { this.camera = c; this.target = new THREE.Vector3(); } update() { this.camera.lookAt(this.target); this.camera.updateMatrixWorld(); } addEventListener() {} }
class Pass { constructor() { this.overrideVisibility = () => {}; } addPass() {} setSize() {} updateGtaoMaterial() {} render() {} }
globalThis.document = document;  // three's ImageLoader (station kit wall textures) calls document.createElementNS
const window = {matchMedia: () => ({matches: false}), addEventListener() {}};
const state = {document, window, innerWidth: 1600, innerHeight: 900, devicePixelRatio: 1, console: {info() {}, warn() {}}, performance: {now: () => 0}, requestAnimationFrame: () => {},
  __area: area,
  loadModule: async n => n === 'three' ? {...THREE, WebGLRenderer: Renderer, PMREMGenerator: PMREM} : n.endsWith('BufferGeometryUtils.js') ? {mergeGeometries}
    : {OrbitControls: Controls, RoomEnvironment: THREE.Scene, EffectComposer: Pass, RenderPass: Pass, GTAOPass: Pass, OutputPass: Pass, ShaderPass: Pass}};
const calls = new Map();
state.__rec = (color, o) => {
  color = typeof color === 'string' ? color : '#' + new THREE.Color(color).getHexString();
  let c = calls.get(color);
  if (!c) calls.set(color, c = new Map());
  const t = o ? `${o.type}:${o.id}` : '(batched/interior)';
  c.set(t, (c.get(t) || 0) + 1);
};
vm.createContext(state);
try {
  await vm.runInContext('(async()=>{' + html.match(/<script type="module">([\s\S]*?)<\/script>/)[1].replaceAll('import(', 'loadModule(') +
    '\nglobalThis.runtime={scene,place,mats,material};})()', state);
} catch (e) { console.log('BOOT FAILED: ' + e.stack.split('\n').slice(0, 4).join('\n')); process.exit(1); }
const {scene, mats, place} = state.runtime;
const keyOf = new Map([...mats].map(([k, m]) => [m, typeof k === 'string' ? k : '#' + new THREE.Color(k).getHexString()]));
const own = new Map(), M = new THREE.Matrix4();
scene.updateMatrixWorld(true);
scene.traverse(m => {
  if (!m.isMesh || !m.visible || !m.material || Array.isArray(m.material) || !m.material.color || m.material.isMeshBasicMaterial) return;
  const add = (k, a) => { let s = stats.get(k); if (!s) stats.set(k, s = {area: 0}); s.area += a; };
  const g = area(m.geometry, null), C = new THREE.Color();
  const base = keyOf.get(m.material) ?? ('#' + m.material.color.getHexString() + ' [kit-own' + (m.material.map ? ',map' : '') + ']');
  const vc = m.geometry.getAttribute('color');
  if (vc) {  // vertex colours: share the mesh area by vertex count per colour
    const n = new Map();
    for (let i = 0; i < vc.count; i++) { C.setRGB(vc.getX(i), vc.getY(i), vc.getZ(i)); const k = '#' + C.getHexString(); n.set(k, (n.get(k) || 0) + 1); }
    const w = Math.pow(Math.abs(m.matrixWorld.determinant()), 2 / 3) * (m.isInstancedMesh ? m.count : 1);
    for (const [k, x] of n) add(k + ' [vtx on ' + base + ']', g * w * x / vc.count);
    return;
  }
  if (m.isInstancedMesh) for (let i = 0; i < m.count; i++) {
    m.getMatrixAt(i, M); M.premultiply(m.matrixWorld);
    const a = g * Math.pow(Math.abs(M.determinant()), 2 / 3);
    if (m.instanceColor) { m.getColorAt(i, C); const h = C.getHexString(); h === 'ffffff' ? add(base, a) : add('#' + h + ' [inst on ' + base + ']', a); } else add(base, a);
  }
  else add(base, g * Math.pow(Math.abs(m.matrixWorld.determinant()), 2 / 3));
});
const total = [...stats.values()].reduce((a, s) => a + s.area, 0);
const cmap = place.colorMap || {};
if (asJson) {
  const rows = [...stats].map(([k, st]) => {
    const raw = k.split(' ')[0], c = calls.get(raw) || new Map();
    const hex = '#' + new THREE.Color(raw.startsWith('#') || raw.startsWith('rgb') ? raw : '#000').getHexString();
    return {key: hex, share: 100 * st.area / total, inst: k.includes('[inst'), vtx: k.includes('[vtx'), kitOwn: k.includes('kit-own'), types: [...c.keys()]};
  });
  console.log(JSON.stringify(rows));
  process.exit(0);
}
console.log(`${slug}: ${stats.size} colours via box/detail/mesh; colorMap ${Object.keys(cmap).length} keys`);
for (const [k, s] of [...stats].sort((a, b) => b[1].area - a[1].area)) {
  const share = 100 * s.area / total;
  if (share < minShare) continue;
  const c = calls.get(k.split(' ')[0]) || new Map(), n = [...c.values()].reduce((a, b) => a + b, 0);
  const top = [...c].sort((a, b) => b[1] - a[1]).slice(0, 3).map(([t, x]) => `${t} ${Math.round(100 * x / n)}%`).join(', ');
  const hex = k.split(' ')[0].replace(/^rgb\((\d+),\s*(\d+),\s*(\d+)\)$/, (_, r, g, b) => '#' + [r, g, b].map(v => (+v).toString(16).padStart(2, '0')).join(''));
  console.log(`${share.toFixed(1).padStart(5)}% ${hex}${k.slice(k.split(' ')[0].length)}${cmap[hex] ? ' -> ' + cmap[hex] : ''}  ${top}`);
}
