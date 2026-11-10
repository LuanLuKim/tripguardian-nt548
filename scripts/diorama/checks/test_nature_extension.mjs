import {CODE} from '../paths.mjs';
import {join} from 'node:path';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {test} from 'node:test';
import * as THREE from '../vendor/node_modules/three/build/three.module.js';
import {mergeGeometries} from '../vendor/node_modules/three/examples/jsm/utils/BufferGeometryUtils.js';

// Exercise real geometry and raycasts; no browser/rendering doubles are needed here.
function fixture() {
  const scene=new THREE.Scene(),objects={},walkableGeometries=[],currentEnvelope=[],mats=new Map();
  const context={THREE,mergeGeometries,scene,walkableGeometries,currentEnvelope,
    material:color=>{const key=String(color);if(!mats.has(key))mats.set(key,new THREE.MeshStandardMaterial({color,roughness:1}));return mats.get(key);},
    registerObjectType:(type,builder)=>objects[type]=builder};
  vm.runInNewContext(fs.readFileSync(join(CODE, 'kits/nature.js'),'utf8'),context);
  function build(type,options={}) {
    assert.equal(typeof objects[type],'function',type+' must be registered');
    const id=options.id||'subject';objects[type]({id,...options});scene.updateMatrixWorld(true);
    const group=scene.getObjectByName(id+'-nature');assert.ok(group,type+' has semantic root');
    group.traverse(o=>{if(o.geometry)for(const n of o.geometry.attributes.position.array)assert.ok(Number.isFinite(n),type+' finite vertices');});
    return group;
  }
  return {scene,objects,walkableGeometries,currentEnvelope,build};
}
const down=new THREE.Vector3(0,-1,0);
function ray(group,x,y,z){return new THREE.Raycaster(new THREE.Vector3(x,y,z),down).intersectObject(group,true).filter(h=>h.object.isMesh);}

for(const style of ['safari','bell','glass_a_frame','dome'])test(style+' tent has its own recognisable shell and grounded platform',()=>{
  const f=fixture(),g=f.build('nature_tent',{style,size:[4.8,3.2,4.8],wallHeight:1.9,position:[2,.4,-3],rotation:27});
  assert.ok(g.getObjectByName('subject-'+style+'-shell'),'style is not ignored or replaced by the legacy A-frame');
  assert.ok(g.getObjectByName('subject-seams'),'fine canvas seams / glass frame');
  const box=new THREE.Box3().setFromObject(g);assert.ok(Math.abs(box.min.y-.4)<.03,'floor rooted at declared base');
  if(style==='safari'){
    assert.ok(g.getObjectByName('subject-roof'));assert.ok(g.getObjectByName('subject-windows'));
    const a=g.localToWorld(new THREE.Vector3(0,1.1,4)),b=g.localToWorld(new THREE.Vector3(0,1.1,0));
    const hit=new THREE.Raycaster(a,b.clone().sub(a).normalize(),0,a.distanceTo(b)).intersectObject(g,true).filter(h=>h.object.isMesh);
    assert.equal(hit.length,0,'safari front has a real opening, not a painted door');
  }
  if(style==='bell')assert.ok(g.getObjectByName('subject-center-pole'));
  if(style==='glass_a_frame')assert.ok(g.getObjectByName('subject-glazing'));
  if(style==='dome')assert.ok(g.getObjectByName('subject-ribs')?.isInstancedMesh);
});

test('dome door follows the curved canvas instead of floating on a plane in front of it',()=>{
  const f=fixture(),g=f.build('nature_tent',{style:'dome',size:[4.2,2.2,4.5]}),door=g.getObjectByName('subject-door'),shell=g.getObjectByName('subject-dome-shell');
  for(const x of [-.2,0,.2])for(const y of [.7,1,1.3]){
    const cast=new THREE.Raycaster(new THREE.Vector3(x,y,5),new THREE.Vector3(0,0,-1)),a=cast.intersectObject(door)[0],b=cast.intersectObject(shell)[0];
    assert.ok(a&&b,'door and canvas both present at '+[x,y]);
    assert.ok(a.point.distanceTo(b.point)<.045,'door attached to curved shell, gap='+a.point.distanceTo(b.point));
  }
});

test('legacy tent remains the default; invalid styles fail loudly',()=>{
  const f=fixture();assert.ok(f.build('nature_tent').getObjectByName('subject-canvas'));
  assert.throws(()=>f.build('nature_tent',{id:'bad',style:'unrecognised'}),/style/);
});

for(const pattern of ['stepping','boardwalk'])test(pattern+' path is separate instances with continuous hidden route support on a transformed slope',()=>{
  const f=fixture(),g=f.build('nature_path',{pattern,position:[20,2,5],rotation:37,points:[[-5,0,0],[0,1,0],[5,1,3]],width:1.8,stepLength:.6,stepGap:.2});
  assert.ok(g.getObjectByName('subject-'+pattern)?.isInstancedMesh,'repeated surfaces are instanced');
  const support=g.getObjectByName('subject-route-support');assert.ok(support?.userData.paving);
  assert.equal(support.material.visible,false,'no visible ribbon fills stone/plank gaps');
  for(const t of [.1,.4,.7,.9]){
    const p=g.localToWorld(new THREE.Vector3(-5+5*t,t,0));
    const hits=ray(g,p.x,20,p.z).filter(h=>h.object.userData.paving);
    assert.ok(hits.length);assert.ok(Math.abs(hits[0].point.y-(2+t+.1))<.015,'route follows actual slope');
  }
  assert.ok(f.walkableGeometries.length>0);
});

test('stepping stones default to human scale even when the route corridor is wide',()=>{
  const f=fixture(),matrix=new THREE.Matrix4();
  for(const [width,stoneWidth] of [[3.2,undefined],[1,undefined],[3.2,.6]]){
    const g=f.build('nature_path',{id:'path-'+width+'-'+stoneWidth,pattern:'stepping',width,...(stoneWidth?{stoneWidth}:{})}),stones=g.getObjectByName('path-'+width+'-'+stoneWidth+'-stepping');
    stones.getMatrixAt(0,matrix);const scale=new THREE.Vector3().setFromMatrixScale(matrix);
    assert.ok(Math.abs(scale.x*2-(stoneWidth??Math.min(.8,width*.88)))<1e-6,'visible stones are not metre-wide slabs unless explicitly requested');
  }
});

test('stretched canopy has peaks, sagging edges and genuinely open sides',()=>{
  const f=fixture(),g=f.build('nature_canopy',{size:[8,4.4,6],edgeHeight:2.1,peaks:[[-2,0,4.4],[2,0,4.1]]});
  const membrane=g.getObjectByName('subject-membrane');assert.ok(membrane);
  assert.ok(new THREE.Box3().setFromObject(membrane).max.y>=4.39);
  assert.ok(g.getObjectByName('subject-poles')?.isInstancedMesh);
  const hit=new THREE.Raycaster(new THREE.Vector3(0,1,5),new THREE.Vector3(0,0,-1),0,10).intersectObject(g,true);
  assert.equal(hit.filter(h=>h.object.isMesh).length,0,'no tent walls across canopy sides');
});

test('rocky stream keeps water non-walkable and grounds its boulders; boardwalk follows bends',()=>{
  const f=fixture(),g=f.build('nature_stream',{points:[[0,0,-6],[0,.2,0],[1,.4,6]],width:3,boulders:24,boardwalk:{side:1,width:1.8,gap:.4,height:.2}});
  assert.ok(g.getObjectByName('subject-water'));assert.ok(!g.getObjectByName('subject-water').userData.paving);
  assert.equal(g.getObjectByName('subject-boulders').count,24);
  assert.ok(g.getObjectByName('subject-boardwalk-boardwalk')?.isInstancedMesh);
  assert.ok(f.walkableGeometries.length,'only boardwalk supplies route geometry');
  const stones=g.getObjectByName('subject-boulders'),matrix=new THREE.Matrix4();
  for(let i=0;i<stones.count;i++){stones.getMatrixAt(i,matrix);const p=new THREE.Vector3().setFromMatrixPosition(matrix),s=new THREE.Vector3().setFromMatrixScale(matrix);assert.ok(p.y-s.y<=.5,'boulders sit in bed, not in air');}
});
test('stream boulders never intrude into the whole boardwalk width, including a translated/rotated root',()=>{
  const f=fixture(),g=f.build('nature_stream',{position:[20,2,5],rotation:37,points:[[0,0,-16.8],[0,0,-9],[0,0,0],[0,0,9],[0,0,16.8]],width:4,bankWidth:.85,boulders:70,boulderScale:.85,seed:12,boardwalk:{side:1,width:2.3,gap:.85,height:.04,thickness:.1}}),stones=g.getObjectByName('subject-boulders');
  assert.equal(stones.count,70,'clearance does not empty the stream');
  for(const x of [2.87,3.3,4,4.7,5.13])for(let z=-16;z<=16;z+=.4){
    const p=g.localToWorld(new THREE.Vector3(x,20,z)),hits=new THREE.Raycaster(p,down).intersectObject(stones);
    assert.equal(hits.length,0,'rock footprint overlaps boardwalk at local '+[x,z]);
  }
  const exported=new THREE.Mesh(mergeGeometries(f.walkableGeometries),new THREE.MeshBasicMaterial({side:THREE.DoubleSide})),live=g.getObjectByName('subject-boardwalk-route-support');
  for(const z of [-12,0,12]){
    const p=g.localToWorld(new THREE.Vector3(4,20,z)),cast=new THREE.Raycaster(p,down),a=cast.intersectObject(live)[0],b=cast.intersectObject(exported)[0];
    assert.ok(a&&b&&a.point.distanceTo(b.point)<1e-6,'live and exported route support have identical world transforms');
  }
  // Stream rocks embed below the bed. Their world-space bounds may lie below
  // base 2, but must not remain at the untransformed local support height .14.
  assert.ok(f.currentEnvelope.every(p=>p.y>1),'instance framing points are world-space after composite reparent');
});

test('string lights sag between grounded posts and use instanced bulbs, without per-bulb point lights',()=>{
  const f=fixture(),g=f.build('nature_lights',{points:[[-4,0,0],[4,.5,0]],height:3.4,sag:.6,bulbSpacing:.8});
  assert.equal(g.getObjectByName('subject-posts').count,2);
  assert.ok(g.getObjectByName('subject-bulbs').count>=9);
  const wire=g.getObjectByName('subject-wire'),box=new THREE.Box3().setFromObject(wire);assert.ok(box.min.y<3.2);
  assert.equal(g.getObjectsByProperty('isPointLight',true).length,0);
});

test('firepit has an open stone ring, ash, crossed logs and true-scale log seats',()=>{
  const f=fixture(),g=f.build('nature_firepit',{radius:.85,seats:[[0,2.1,1.8],[120,2.1,1.8],[240,2.1,1.8]]});
  assert.ok(g.getObjectByName('subject-ring')?.isInstancedMesh);
  assert.ok(g.getObjectByName('subject-ash'));assert.equal(g.getObjectByName('subject-seats').count,3);
  const hits=ray(g,0,10,0);assert.ok(hits[0].point.y<.3,'pit centre is not a solid pedestal');
});
test('firepit stoneSize specifies full dimensions, with each stone grounded rather than half buried',()=>{
  const f=fixture(),g=f.build('nature_firepit',{stoneSize:[.4,.3,.32]}),ring=g.getObjectByName('subject-ring'),matrix=new THREE.Matrix4();
  ring.geometry.computeBoundingBox();
  for(let i=0;i<ring.count;i++){
    ring.getMatrixAt(i,matrix);const scale=new THREE.Vector3().setFromMatrixScale(matrix),bounds=ring.geometry.boundingBox.clone().applyMatrix4(matrix);
    assert.ok(bounds.min.y>=-.005,'stone bottoms rest on the declared ground: '+bounds.min.y);
    assert.ok(scale.x<=.4*.6&&scale.z<=.32*.6,'stoneSize is diameter, not radius');
  }
});

for(const kind of ['picnic_table','log_seat','folding_chair','table','bench'])test(kind+' furniture has grounded real-scale parts',()=>{
  const f=fixture(),g=f.build('nature_furniture',{kind});
  const b=new THREE.Box3().setFromObject(g);assert.ok(b.min.y>=-.01&&b.min.y<.1);assert.ok(b.max.y> .2&&b.max.y<1.2);
});
test('elliptical log seats respect distinct height and depth, including their end grain',()=>{
  const f=fixture(),g=f.build('nature_furniture',{kind:'log_seat',size:[1.8,.6,.3]}),b=new THREE.Box3().setFromObject(g);
  assert.ok(Math.abs(b.min.y)<.01,'elliptical log is grounded');assert.ok(Math.abs(b.max.y-.6)<.01,'height is not swapped with depth');
  assert.ok(Math.abs(b.max.z-b.min.z-.3)<.01,'end grain fits the elliptical body');
});

test('net pavilion has a real raised floor, thin net linework and furnished long tables',()=>{
  const f=fixture(),g=f.build('nature_pavilion',{size:[8,3.2,7],deckHeight:.3,roof:'net',tables:[[-2,0],[2,0]],tableSize:[4.6,.75,.9]});
  assert.ok(g.getObjectByName('subject-net'));assert.ok(g.getObjectByName('subject-net-grid')?.isLineSegments);
  assert.ok(g.getObjectByName('subject-tables'));assert.ok(f.walkableGeometries.length);
  const hits=ray(g,0,10,3).filter(h=>h.object.userData.paving);assert.ok(hits.length&&Math.abs(hits[0].point.y-.3)<.03);
});

test('gravel is a bounded walkable patch with instanced small stones, never a painted water object',()=>{
  const f=fixture(),g=f.build('nature_gravel',{outline:[[-3,-2],[3,-2],[2,2],[-2,2]],granules:120});
  assert.ok(g.getObjectByName('subject-grains')?.isInstancedMesh);assert.ok(f.walkableGeometries.length);
  assert.equal(ray(g,4,10,0).length,0);assert.ok(ray(g,0,10,0).some(h=>h.object.userData.paving));
});

test('terrace top, retaining lip and flower beds follow the authored slope without floating plants',()=>{
  const f=fixture(),g=f.build('nature_terrace',{size:[12,6],height:.5,slope:[.03,-.08]});
  assert.ok(g.getObjectByName('subject-lawn'));assert.ok(g.getObjectByName('subject-retaining'));
  for(const [x,z] of [[0,0],[3,2],[-3,-2]]){const hit=ray(g,x,10,z)[0];assert.ok(Math.abs(hit.point.y-(.5+.03*x-.08*z))<.01);}
  for(const kind of ['daisy','cosmos','mixed']){
    const bed=f.build('nature_flowerbed',{id:kind,kind,size:[4,2],count:30,slope:[.03,-.08]});
    assert.ok(bed.getObjectByName(kind+'-petals')?.isInstancedMesh);assert.ok(bed.getObjectByName(kind+'-stems')?.isInstancedMesh);
    assert.ok(bed.getObjectByName(kind+'-centres')?.isInstancedMesh);
  }
});

test('new types boot with omitted options, rotated roots, finite bounds and bounded draw calls',()=>{
  const f=fixture(),types=['nature_canopy','nature_stream','nature_lights','nature_firepit','nature_furniture','nature_pavilion','nature_gravel','nature_terrace','nature_flowerbed'];
  for(const type of types){const g=f.build(type,{id:type,position:[40,1,30],rotation:29});const b=new THREE.Box3().setFromObject(g);assert.ok(!b.isEmpty()&&Number.isFinite(b.max.y));let count=0;g.traverse(o=>{if(o.isMesh||o.isLine)count++;});assert.ok(count<35,type+' details are batched: '+count);}
});
