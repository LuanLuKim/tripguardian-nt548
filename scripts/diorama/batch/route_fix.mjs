// route_fix.mjs: repair a place's walking route without a model. Builds the place, rasterises every walkable surface
// (paving the viewer raycasts the route onto) on a 0.25 m grid, snaps each outdoor stop's `walk` point onto paving and
// rebuilds each failing leg as the shortest path over paving (A*, then straightened with line-of-sight).
// Usage: node scripts/diorama/batch/route_fix.mjs <slug> [--all]   (--all rebuilds every leg)
// Prints one JSON line: {"ok":true,"changed":[...]} or {"ok":false,"error":"stops a and b are not connected by paving"}
import fs from 'node:fs';
import {CODE, DATA} from '../paths.mjs';
import {join} from 'node:path';
import vm from 'node:vm';
import {spawnSync} from 'node:child_process';
import * as THREE from '../vendor/node_modules/three/build/three.module.js';
import {mergeGeometries} from '../vendor/node_modules/three/examples/jsm/utils/BufferGeometryUtils.js';

const slug = process.argv[2], rebuildAll = process.argv.includes('--all');
const file = join(DATA, `places/${slug}/place.json`), place = JSON.parse(fs.readFileSync(file, 'utf8'));

async function surfaces() {
  const out = join(DATA, `out_${slug}/route-build`);
  const b = spawnSync('python3', ['-B', join(CODE, 'build.py'), file, out], {encoding: 'utf8'});
  if (b.status !== 0) throw new Error('build failed: ' + (b.stdout + b.stderr).slice(-400));
  let html = fs.readFileSync(out + '/index.html', 'utf8');
  html = html.replace('// === Walking route ===', 'globalThis.__pre={geoms:walkableGeometries.map(g=>g.clone()),scene};\n// === Walking route ===');
  const canvas = new Proxy({measureText: t => ({width: t.length * 24}), createImageData: (w, h) => ({data: new Uint8ClampedArray(w * h * 4)})}, {get: (t, k) => t[k] ?? (() => {})});
  const el = () => ({style: {setProperty() {}}, dataset: {}, classList: {add() {}, toggle() {}}, appendChild() {}, setAttribute() {}, addEventListener() {}, querySelector: () => el(), getContext: () => canvas});
  const els = new Map();
  const document = {body: el(), createElement: el, createElementNS: el, getElementById: id => { if (!els.has(id)) els.set(id, el()); return els.get(id); }};
  class Renderer { constructor() { this.domElement = el(); this.shadowMap = {}; this.info = {render: {}, reset() {}}; } setPixelRatio() {} setSize() {} getContext() { return {finish() {}}; } }
  class PMREM { fromScene() { return {texture: null}; } dispose() {} }
  class Controls { constructor(c) { this.camera = c; this.target = new THREE.Vector3(); } update() {} addEventListener() {} }
  class Pass { constructor() { this.overrideVisibility = () => {}; } addPass() {} setSize() {} updateGtaoMaterial() {} render() {} }
  const state = {document, window: {matchMedia: () => ({matches: false}), addEventListener() {}}, innerWidth: 1600, innerHeight: 900, devicePixelRatio: 1,
    console: {info() {}}, performance: {now: () => 0}, requestAnimationFrame: () => {},
    loadModule: async n => n === 'three' ? {...THREE, WebGLRenderer: Renderer, PMREMGenerator: PMREM} : n.endsWith('BufferGeometryUtils.js') ? {mergeGeometries}
      : {OrbitControls: Controls, RoomEnvironment: THREE.Scene, EffectComposer: Pass, RenderPass: Pass, GTAOPass: Pass, OutputPass: Pass, ShaderPass: Pass}};
  vm.createContext(state);
  try { await vm.runInContext('(async()=>{' + html.match(/<script type="module">([\s\S]*?)<\/script>/)[1].replaceAll('import(', 'loadModule(') + '})()', state); } catch (e) { /* route errors come after __pre */ }
  if (!state.__pre) throw new Error('viewer failed before the route section (not a route problem)');
  const tris = [];
  const add = (g, m) => { g = g.index ? g.toNonIndexed() : g; const p = g.attributes.position, v = new THREE.Vector3();
    for (let i = 0; i < p.count; i++) { v.fromBufferAttribute(p, i); if (m) v.applyMatrix4(m); tris.push(v.x, v.z); } };
  for (const g of state.__pre.geoms) add(g, null);
  state.__pre.scene.updateMatrixWorld(true);
  for (const m of state.__pre.scene.children.filter(c => c.name === 'approach-paving')) add(m.geometry, m.matrixWorld);
  return tris;
}

const tris = await surfaces().catch(e => { console.log(JSON.stringify({ok: false, error: e.message})); process.exit(1); });
const S = 0.25;
let minX = Infinity, minZ = Infinity, maxX = -Infinity, maxZ = -Infinity;
for (let i = 0; i < tris.length; i += 2) { minX = Math.min(minX, tris[i]); maxX = Math.max(maxX, tris[i]); minZ = Math.min(minZ, tris[i + 1]); maxZ = Math.max(maxZ, tris[i + 1]); }
minX -= 2; minZ -= 2;
const W = Math.ceil((maxX - minX) / S) + 4, H = Math.ceil((maxZ - minZ) / S) + 4, grid = new Uint8Array(W * H);
for (let t = 0; t < tris.length; t += 6) {
  const [ax, az, bx, bz, cx, cz] = tris.slice(t, t + 6);
  const area = (bx - ax) * (cz - az) - (bz - az) * (cx - ax);
  if (Math.abs(area) < 1e-6) continue;
  const i0 = Math.floor((Math.min(ax, bx, cx) - minX) / S), i1 = Math.ceil((Math.max(ax, bx, cx) - minX) / S);
  const j0 = Math.floor((Math.min(az, bz, cz) - minZ) / S), j1 = Math.ceil((Math.max(az, bz, cz) - minZ) / S);
  for (let i = i0; i <= i1; i++) for (let j = j0; j <= j1; j++) {
    const x = minX + (i + .5) * S, z = minZ + (j + .5) * S;
    const w0 = (bx - x) * (cz - z) - (bz - z) * (cx - x), w1 = (cx - x) * (az - z) - (cz - z) * (ax - x), w2 = (ax - x) * (bz - z) - (az - z) * (bx - x);
    if ((w0 >= 0 && w1 >= 0 && w2 >= 0) || (w0 <= 0 && w1 <= 0 && w2 <= 0)) grid[j * W + i] = 1;
  }
}
const erode = (g, r) => { const o = new Uint8Array(W * H); for (let j = r; j < H - r; j++) for (let i = r; i < W - r; i++) { let ok = 1;
  for (let dj = -r; dj <= r && ok; dj++) for (let di = -r; di <= r; di++) if (!g[(j + dj) * W + i + di]) { ok = 0; break; } o[j * W + i] = ok; } return o; };
const safe = erode(grid, 2), inner = erode(grid, 1);
const cell = ([x, z]) => [Math.floor((x - minX) / S), Math.floor((z - minZ) / S)];
const pt = (i, j) => [Math.round((minX + (i + .5) * S) * 10) / 10, Math.round((minZ + (j + .5) * S) * 10) / 10];
const on = (g, [x, z]) => { const [i, j] = cell([x, z]); return i >= 0 && j >= 0 && i < W && j < H && g[j * W + i] === 1; };
function nearest(g, p, maxR = 40) {
  const [ci, cj] = cell(p);
  for (let r = 0; r <= maxR; r++) for (let di = -r; di <= r; di++) for (let dj = -r; dj <= r; dj++) {
    if (Math.max(Math.abs(di), Math.abs(dj)) !== r) continue;
    const i = ci + di, j = cj + dj;
    if (i >= 0 && j >= 0 && i < W && j < H && g[j * W + i]) return pt(i, j);
  }
  return null;
}
function sight(g, a, b) { const d = Math.hypot(b[0] - a[0], b[1] - a[1]), n = Math.ceil(d / .1);
  for (let k = 0; k <= n; k++) if (!on(g, [a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n])) return false; return true; }
function astar(g, a, b) {
  const [si, sj] = cell(a), [ti, tj] = cell(b), N = W * H, cost = new Float32Array(N).fill(Infinity), from = new Int32Array(N).fill(-1);
  const open = [[0, sj * W + si]]; cost[sj * W + si] = 0;
  const push = (f, n) => { open.push([f, n]); let k = open.length - 1; while (k) { const p = (k - 1) >> 1; if (open[p][0] <= open[k][0]) break; [open[p], open[k]] = [open[k], open[p]]; k = p; } };
  const pop = () => { const top = open[0], last = open.pop(); if (open.length) { open[0] = last; let k = 0; for (;;) { const l = 2 * k + 1, r = l + 1; let m = k;
    if (l < open.length && open[l][0] < open[m][0]) m = l; if (r < open.length && open[r][0] < open[m][0]) m = r; if (m === k) break; [open[m], open[k]] = [open[k], open[m]]; k = m; } } return top; };
  open.length = 0; push(0, sj * W + si);
  while (open.length) {
    const [, n] = pop(), i = n % W, j = (n / W) | 0;
    if (i === ti && j === tj) { const path = []; for (let c = n; c !== -1; c = from[c]) path.push(pt(c % W, (c / W) | 0)); return path.reverse(); }
    for (const [di, dj, w] of [[1, 0, 1], [-1, 0, 1], [0, 1, 1], [0, -1, 1], [1, 1, 1.414], [1, -1, 1.414], [-1, 1, 1.414], [-1, -1, 1.414]]) {
      const ni = i + di, nj = j + dj, m = nj * W + ni;
      if (ni < 0 || nj < 0 || ni >= W || nj >= H || !g[m]) continue;
      const c = cost[n] + w; if (c < cost[m]) { cost[m] = c; from[m] = n; push(c + Math.hypot(ti - ni, tj - nj), m); }
    }
  }
  return null;
}
function straighten(g, path) { const out = [path[0]]; let k = 0;
  while (k < path.length - 1) { let far = k + 1; for (let m = path.length - 1; m > k + 1; m--) if (sight(g, path[k], path[m])) { far = m; break; } out.push(path[far]); k = far; } return out; }
function legOk(leg) { for (let k = 1; k < leg.length; k++) if (!sight(grid, leg[k - 1], leg[k])) return false; return true; }

const outdoor = place.hotspots.filter(h => h.walk), changed = [];
for (const h of outdoor) {
  if (on(inner, h.walk)) continue;
  const s = nearest(safe, h.walk) || nearest(inner, h.walk);
  if (!s || Math.hypot(s[0] - h.walk[0], s[1] - h.walk[1]) > 8) { console.log(JSON.stringify({ok: false, error: `stop ${h.id}: no paving within 8 m of walk ${JSON.stringify(h.walk)}; add a paved path/plaza there or move the stop`})); process.exit(1); }
  changed.push(`walk ${h.id} ${JSON.stringify(h.walk)}->${JSON.stringify(s)}`); h.walk = s;
}
const route = [];
for (let k = 0; k + 1 < outdoor.length; k++) {
  const a = outdoor[k].walk, b = outdoor[k + 1].walk, old = (place.route || [])[k];
  if (!rebuildAll && old && old.length >= 2 && legOk(old) && Math.hypot(old[0][0] - a[0], old[0][1] - a[1]) < .3 && Math.hypot(old.at(-1)[0] - b[0], old.at(-1)[1] - b[1]) < .3) { route.push(old); continue; }
  const p = astar(safe, a, b) || astar(inner, a, b) || astar(grid, a, b);
  if (!p) { console.log(JSON.stringify({ok: false, error: `stops ${outdoor[k].id} and ${outdoor[k + 1].id} are not connected by paving; add a walkable path between ${JSON.stringify(a)} and ${JSON.stringify(b)}`})); process.exit(1); }
  const g = p.every(q => on(safe, q)) ? safe : p.every(q => on(inner, q)) ? inner : grid;
  const leg = straighten(g, p); leg[0] = a; leg[leg.length - 1] = b;
  route.push(leg); changed.push(`leg ${k} ${outdoor[k].id}->${outdoor[k + 1].id}: ${leg.length} points`);
}
place.route = route;
fs.writeFileSync(file, JSON.stringify(place, null, 1) + '\n');
console.log(JSON.stringify({ok: true, changed, cells: grid.reduce((a, b) => a + b, 0)}));
