import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {join} from 'node:path';
import {CODE,DATA} from '../paths.mjs';
import * as THREE from '../vendor/node_modules/three/build/three.module.js';

const template=fs.readFileSync(join(CODE,'index.template.html'),'utf8');
const source=template.slice(template.indexOf('let overviewFovEffective='),template.indexOf('function fitSpot('));
const configure=template.slice(template.indexOf('function configureInteriorView('),template.indexOf('function resolveInteriorBuilding('));
// Disabling only the new fallback retains the original 25-step distance search.
const legacy=source.replace('if(high===600&&camera.fov<36)', 'if(false)');
function fit(site,{width=1600,height=900,original=false}={}) {
  const logs=[];
  const state={THREE,place:{site},innerWidth:width,innerHeight:height,controls:{},
    config:{frameFill:site.frameFill??.8,defaultAzimuth:site.overviewAzimuth??35,defaultPolar:site.overviewPolar??73},
    console:{info:(_,json)=>logs.push(JSON.parse(json))}};
  vm.createContext(state);
  vm.runInContext((original?legacy:source)+configure+`
    fitOverview(${site.overviewAzimuth??35},${site.overviewPolar??73});
    globalThis.api={camera,overview,configureInteriorView,fitOverview};`,state);
  return {...state.api,logs};
}
for(const slug of ['bensuoi','lonton','thacprenn','gadalat','mongolanddalat','khudulichthacd']) {
  const {site}=JSON.parse(fs.readFileSync(join(DATA,'places',slug,'place.json'),'utf8'));
  const before=fit(site,{original:true}),after=fit(site);
  const old=before.logs.at(-1),now=after.logs.at(-1);
  if(old.distance<600) {
    assert.deepEqual(now,old,`${slug}: unchanged FOV, distance and bounds`);
    assert.deepEqual(after.camera.projectionMatrix.elements,before.camera.projectionMatrix.elements);
    assert.deepEqual(after.camera.position.toArray(),before.camera.position.toArray());
  } else if(old.fov<36) {
    const ratio=Math.max(old.widthFraction/(site.frameFill??.8),old.heightFraction/(site.overviewHeightFill??.88));
    const expected=Math.min(36,THREE.MathUtils.radToDeg(2*Math.atan(Math.tan(THREE.MathUtils.degToRad(old.fov)/2)*ratio*1.02)));
    assert.ok(Math.abs(now.fov-expected)<1e-10,`${slug}: prescribed widening formula`);
    if(now.fov<36)assert.ok(now.distance<600,`${slug}: fits after widening`);
  }
  after.configureInteriorView({});assert.equal(after.camera.fov,36);
  after.configureInteriorView(null);assert.equal(after.camera.fov,now.fov,`${slug}: overview FOV survives hotspot`);
  console.log(`${slug}: ${old.fov} -> ${now.fov} degrees, distance ${now.distance}`);
}
const huge=fit({width:2000,depth:2000,overviewFov:8});
assert.equal(huge.camera.fov,36,'widening is capped at 36 degrees');
assert.equal(huge.logs.at(-1).distance,600,'retain capped distance when 36 degrees cannot fit');
for(const site of [{width:160,depth:154,overviewFov:8},{width:100,depth:114,overviewFov:8}]) {
  const result=fit(site),bounds=result.logs.at(-1);
  assert.ok(bounds.fov>8&&bounds.fov<36);
  assert.ok(bounds.widthFraction<=.8&&bounds.heightFraction<=.88,'widened overview fits both axes');
  const fov=result.camera.fov;
  result.fitOverview(35,73);
  assert.equal(result.camera.fov,fov,'refitting preserves the widened FOV');
}
for(const site of [{width:50,depth:50,overviewFov:8},{width:160,depth:154},{width:50,depth:50,overviewFov:45}]) {
  for(const viewport of [{},{width:900,height:1600}]) {
    const before=fit(site,{...viewport,original:true}),after=fit(site,viewport);
    assert.deepEqual(after.logs,before.logs,'fitting/default/portrait/wider FOV stays unchanged');
  }
}
console.log('PASS overview cap widening, exact fitting-site stability, portrait/default FOV and hotspot return');
