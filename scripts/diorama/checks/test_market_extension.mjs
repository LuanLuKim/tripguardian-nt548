import {CODE} from '../paths.mjs';
import {join} from 'node:path';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import * as THREE from '../vendor/node_modules/three/build/three.module.js';
import {mergeGeometries} from '../vendor/node_modules/three/examples/jsm/utils/BufferGeometryUtils.js';

const objects={},interiors={},scene=new THREE.Scene(),roofs=[],walk=[],materials=new Map();
const canvas=new Proxy({},{get:()=>()=>{}});
const context={THREE,mergeGeometries,scene,roofRecords:roofs,walkableGeometries:walk,currentEnvelope:null,
  material:c=>{if(!materials.has(c))materials.set(c,new THREE.MeshStandardMaterial({color:c,roughness:1}));return materials.get(c);},
  registerObjectType:(t,b)=>objects[t]=b,registerInteriorKit:(t,b)=>interiors[t]=b,
  document:{createElement:()=>({getContext:()=>canvas})},tree(){}};
vm.createContext(context);vm.runInContext(fs.readFileSync(join(CODE, 'kits/market.js'),'utf8'),context);
const fixtures=[
  ['building',{size:[20,14],footprint:[[-10,-7],[10,-7],[10,7],[0,7],[0,3],[-10,3]],storeys:7,podiumStoreys:2,upperFootprint:[[-9,-6],[9,-6],[9,2],[-9,2]],entrance:{edge:2,width:4},planters:{every:1},roofGarden:{spacing:2}}],
  ['entrance',{size:[12,6],rise:1.2,steps:8,canopy:{height:4.8,pitch:.4},sign:{text:'CHỢ MẪU'}}],
  ['shophouses',{size:[22,7],houses:[{width:5,storeys:2},{width:6,storeys:4},{width:5,storeys:3}],balcony:{depth:1,spacing:.25}}],
  ['umbrella',{radius:2.1,segments:12,fabricColors:['#bdad97','#a5b1a2'],goods:'produce'}],
  ['shed',{size:[22,5],postSpacing:3,roof:{kind:'skillion',rise:.5},bays:7,goods:'produce'}],
  ['goods',{size:[3,1],kind:'produce',crates:6}],
  ['street',{size:[28,22],top:.2,junction:[-7,4],roadWidth:6,trafficLights:[{position:[-3,0,0],rotation:90}],motorbikes:[[0,1,15],[2,1,-10]],crossings:true}]
];
for(const [suffix,options] of fixtures){
  const type='market_'+suffix;assert.equal(typeof objects[type],'function',type+' is registered');
  context.currentEnvelope=[];objects[type]({id:'test-'+suffix,position:[2,0,3],rotation:19,...options});
  const g=scene.getObjectByName('test-'+suffix+'-market');assert.ok(g,'semantic root '+suffix);g.updateMatrixWorld(true);
  const b=new THREE.Box3().setFromObject(g);assert.ok(!b.isEmpty()&&b.max.y>0,'visible '+suffix);
  for(const p of context.currentEnvelope)assert.ok(b.clone().expandByScalar(.01).containsPoint(p),'world-space instance envelope '+suffix);
  context.currentEnvelope=null;let meshes=0;
  g.traverse(m=>{if(m.isMesh){meshes++;for(const v of m.geometry.attributes.position.array)assert.ok(Number.isFinite(v),'finite '+suffix);}});
  assert.ok(meshes<100,'batched '+suffix+': '+meshes);
  objects[type]({id:'default-'+suffix});
}
const building=scene.getObjectByName('test-building-market');
assert.ok(building.getObjectByName('market-horizontal-louvres')?.isInstancedMesh,'horizontal louvres are real batched geometry');
assert.ok(building.getObjectByName('market-facade-fins')?.isInstancedMesh,'vertical fins articulate the tower');
assert.ok(building.getObjectByName('market-ledge-foliage')?.count>50,'greenery on repeated ledges');
assert.ok(building.getObjectByName('market-polygon-floor'),'actual concave polygon, not bounding box');
const entry=scene.getObjectByName('test-entrance-market');
assert.equal(entry.getObjectByName('market-stair-treads').count,8,'JSON step count');
assert.equal(entry.getObjectByName('market-stair-nosings')?.geometry.attributes.position.count,16,'fine nosing line for each step');
assert.ok(entry.getObjectByName('market-lattice-slats')?.count>20,'open lattice canopy');
for(const rail of entry.children.filter(c=>c.isGroup&&Math.abs(c.position.x)>1)){
  const bar=rail.children.find(c=>c.isMesh),v=bar.geometry.attributes.position,points=Array.from({length:v.count},(_,i)=>entry.worldToLocal(bar.localToWorld(new THREE.Vector3().fromBufferAttribute(v,i))));
  const front=points.filter(p=>p.z>2.8),back=points.filter(p=>p.z< -2.8);
  assert.ok(Math.min(...back.map(p=>p.y))>Math.max(...front.map(p=>p.y)),'both handrails rise toward the high landing');
}
assert.ok(scene.getObjectByName('market-balcony-rails')?.isInstancedMesh,'repeated balcony rails');
assert.ok(scene.getObjectByName('market-umbrella-fabric'),'round fabric umbrella');
assert.ok(scene.getObjectByName('market-umbrella-fabric').children.length<=2,'umbrella fabric batches by tone, not by panel');
const umbrella=scene.getObjectByName('test-umbrella-market'),fabric=umbrella.getObjectByName('market-umbrella-fabric');umbrella.updateMatrixWorld(true);
assert.ok(new THREE.Raycaster(umbrella.localToWorld(new THREE.Vector3(.6,8,.3)),new THREE.Vector3(0,-1,0)).intersectObject(fabric,true).length,'batched umbrella fabric remains visible from above');
assert.ok(scene.getObjectByName('market-shed-posts')?.count>8,'long shed has intermediate supports');
const longShed=scene.getObjectByName('default-shed-market');longShed.updateMatrixWorld(true);
const shedTop=x=>new THREE.Raycaster(new THREE.Vector3(x,20,0),new THREE.Vector3(0,-1,0)).intersectObject(longShed,true)[0].point.y;
assert.ok(Math.abs(shedTop(0)-shedTop(5))<.02,'long shed ridge runs along its length, not across the short end');
assert.ok(scene.getObjectByName('market-motorbike-wheels')?.isInstancedMesh,'parked bikes use instanced massing');
const wheel=scene.getObjectByName('market-motorbike-wheels'),wm=new THREE.Matrix4();wheel.getMatrixAt(0,wm);
assert.ok(Math.abs(new THREE.Vector3(0,1,0).transformDirection(wm).y)<.01,'wheel axle is horizontal');
assert.ok(scene.getObjectByName('market-traffic-heads'),'traffic signal geometry');
const street=scene.getObjectByName('test-street-market'),streetPoint=street.localToWorld(new THREE.Vector3(7,10,4));
assert.ok(Math.abs(new THREE.Raycaster(streetPoint,new THREE.Vector3(0,-1,0)).intersectObject(street,true)[0].point.y-.2)<.001,'street top clears neighbouring paving when configured');
assert.ok(walk.length>=2,'stairs and street have real walkable surfaces');
assert.equal(typeof interiors.market_interior,'function','reusable market interior');
const defaultHall={id:'defaults-room',position:[3,.4,-2],rotation:37,size:[20,14],interior:{offset:[1,-2]}};
interiors.market_interior(defaultHall);
for(const key of ['entry','approach','boundsCenter'])assert.ok(defaultHall.interior[key]?.every(Number.isFinite),'finite default world '+key);
for(const key of ['altar','fill'])assert.ok(defaultHall.interior.lights?.[key]?.every(Number.isFinite),'finite default world light '+key);
assert.equal(defaultHall.interior.boundsDepth,13.4,'default room depth integrates with viewer');
assert.ok(Math.abs(defaultHall.interior.floorY-.58)<1e-8,'default interior floor sits just above the elevated shell floor');
assert.ok(defaultHall.interior.ridgeHeight>=20.8,'safe flight uses the multi-storey roof, not the room ceiling');
assert.ok(defaultHall.interior.dimmingSize[0]>=21.4&&defaultHall.interior.dimmingSize[1]>=17.4,'viewer dim bounds centered on building origin include an offset room');
const room=interiors.market_interior({id:'room',position:[0,0,0],size:[20,14],interior:{size:[18,12],height:4.8,ambientFill:.2,signs:['SẠP MẪU'],aisleWidth:4,stalls:4,stair:{width:3,depth:4,rise:2.4,steps:12,position:[0,-3]}}},{roof:new THREE.Group()});
assert.ok(room.group.getObjectByName('market-interior-goods'),'goods fill the interior stalls');
assert.ok(room.ceiling.getObjectByName('market-sealed-ceiling'),'ceiling closes the inside view');
assert.ok(room.ceiling.getObjectByName('market-fluorescent-strips'),'fluorescent corridor lights');
assert.ok(room.group.getObjectByName('market-central-stair'),'central stair at human scale');
const stair=room.group.getObjectByName('market-central-stair'),stairPosts=stair.getObjectByName('market-central-stair-rails'),postMatrix=new THREE.Matrix4();stairPosts.getMatrixAt(0,postMatrix);
assert.ok(new THREE.Vector3(0,-.5,0).applyMatrix4(postMatrix).y<.15,'central stair rail posts reach the treads');
assert.equal(stair.getObjectByName('market-central-stair-handrails')?.count,2,'continuous handrail on both sides');
const roomFloor=room.group.getObjectByName('market-interior-floor');assert.ok(roomFloor.material.emissive.getHex()>0&&roomFloor.material.emissiveIntensity===.2,'bounded indirect fill keeps the foreground readable without permanent point lights');
room.group.add(room.ceiling);room.group.updateMatrixWorld(true);
const packs=room.group.getObjectByName('market-interior-packages'),pm=new THREE.Matrix4();packs.getMatrixAt(0,pm);const packagePoint=new THREE.Vector3().setFromMatrixPosition(pm).applyMatrix4(packs.matrixWorld),eye=new THREE.Vector3(0,1.6,4);
const firstHit=new THREE.Raycaster(eye,packagePoint.clone().sub(eye).normalize(),0,eye.distanceTo(packagePoint)+.2).intersectObject(room.group,true).filter(h=>h.object.isMesh)[0];
assert.ok(firstHit?.object===packs,'packages are exposed to the aisle, not buried in a solid stall wall: '+firstHit?.object.name);
for(const yaw of [-4,0,4]){
  const direction=new THREE.Vector3(Math.sin(yaw*Math.PI/180),.5,-Math.cos(yaw*Math.PI/180)).normalize();
  assert.ok(new THREE.Raycaster(new THREE.Vector3(0,1.6,4),direction).intersectObject(room.group,true).length,'room seals sky at '+yaw);
}
assert.throws(()=>objects.market_building({id:'bad',footprint:[[0,0],[1,0],[2,0]]}),/polygon/i,'degenerate polygons fail clearly');
objects.market_building({id:'clockwise',size:[10,8],footprint:[[-5,-4],[-5,4],[5,4],[5,-4]],entrance:{edge:0,width:4},roofGarden:false});
const cw=scene.getObjectByName('clockwise-market');cw.updateMatrixWorld(true);
assert.equal(new THREE.Raycaster(new THREE.Vector3(-6,1.6,0),new THREE.Vector3(1,0,0),0,1.95).intersectObject(cw,true).length,0,'clockwise polygon preserves the original entrance edge index');
const frontMaterials=new Set();room.front.traverse(m=>{if(m.isMesh)frontMaterials.add(m.material);});
room.group.traverse(m=>{if(m.isMesh&&!room.front.getObjectById(m.id))assert.ok(!frontMaterials.has(m.material),'cutaway front owns isolated materials');});
const columns=building.getObjectByName('market-ground-columns'),cm=new THREE.Matrix4();
for(let i=0;i<columns.count;i++){columns.getMatrixAt(i,cm);assert.ok(new THREE.Vector3(0,.5,0).applyMatrix4(cm).y<=4.80001,'ground columns stop at first deck');}
const wingPoint=building.localToWorld(new THREE.Vector3(-9.6,50,2.9)),wingHit=new THREE.Raycaster(wingPoint,new THREE.Vector3(0,-1,0)).intersectObject(building,true)[0];
assert.ok(Math.abs(wingHit.point.y-8)<.01,'podium has a sealed roof outside the upper polygon');
console.log('PASS market extension: seven types, defaults, polygon, batching, circulation and sealed interior');
