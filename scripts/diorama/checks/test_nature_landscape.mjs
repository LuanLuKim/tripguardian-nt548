import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {createHash} from 'node:crypto';
import {join} from 'node:path';
import {spawnSync} from 'node:child_process';
import {CODE,DATA} from '../paths.mjs';
import {boot,THREE,mergeGeometries} from './pagoda_runtime.mjs';

const source=fs.readFileSync(join(CODE,'kits/nature.js'),'utf8');
function fixture(){
  const scene=new THREE.Scene(),builders={},walkableGeometries=[];
  vm.runInNewContext(source,{THREE,scene,mergeGeometries,currentEnvelope:[],walkableGeometries,
    material:c=>new THREE.MeshStandardMaterial({color:c}),registerObjectType:(t,b)=>builders[t]=b});
  return {scene,walkableGeometries,build(type,o={}){const id=o.id||'subject';builders[type]({id,...o});scene.updateMatrixWorld(true);const g=scene.getObjectByName(id+'-nature');assert.ok(g);g.traverse(m=>{if(m.geometry)for(const x of m.geometry.attributes.position.array)assert.ok(Number.isFinite(x),type+' finite geometry');});return g;}};
}
function legacyDigest(scene){
  const h=createHash('sha256');scene.updateMatrixWorld(true);scene.traverse(o=>{if(o.geometry){h.update(o.name);h.update(JSON.stringify(o.matrixWorld.toArray()));for(const k of Object.keys(o.geometry.attributes).sort())h.update(Buffer.from(o.geometry.attributes[k].array.buffer));if(o.geometry.index)h.update(Buffer.from(o.geometry.index.array.buffer));if(o.instanceMatrix)h.update(Buffer.from(o.instanceMatrix.array.buffer));if(o.instanceColor)h.update(Buffer.from(o.instanceColor.array.buffer));h.update(o.material.color.getHexString());}});return h.digest('hex');
}
// Core hashes were captured before implementation; camping builders stay untouched.
const legacy={
  nature_terrain:'bc03d3244dd1f9fbf613092e7febb167a6fdf4eeac035078e6b9dce53ca004b4',
  nature_water:'8d16b40c7edf4b303bb80ccf4513902f14723a2721903edd0b63cc4c3b72458f',
  nature_cascade:'7be6036ec00967d2ab07593340fae18dc5c280ceb69faba76f20a08cfe21148b',
  nature_path:'ea755add6c9fe85f984f8d8442129f4a6a45d2ea6ccd5d0916089d54209942b4',
  nature_bridge:'55e7a82c7d38d3987082654a84e77361db26117da0bc73a44af38da38dabc069',
  nature_deck:'a46b6ca8f6a6c037f23702c47581556bf77772a8e8de660acc4ca9d5b98c40df',
  nature_tent:'779f1d8c227f60991b976061b48694901bdd073a8ac7bf70b6eaf212980c51d3',
  nature_grove:'592fb3f342469b40f46a84d362b03ada78896b5f0a91e55e89a59afc6d858b60',
  nature_stream:'e0928c515ec5f04d3c807baf18865824711c650af605d7b02708c326ec2f76f5',
  nature_canopy:'85c6670e98d92c32c50ab97efc512acde8ccdfaf0c0664e6a4de143a277e83d6',
  nature_lights:'68220c3d997257681f2855e73a25cdca796147b07470a175a9a69a1213d5639b',
  nature_firepit:'e5417de90a3f61251ad406d0e5097f3d33e09f89b26c82b19779957369c2f6a5',
  nature_furniture:'d6cfeb74886f130bb04a29d0484e26323d5a7dd484858834ec2e2cae6cac9ec5',
  nature_pavilion:'990831c9c1926d2ffcfa8b9ecc81a8181064e00a9beeb5395f3a9f50d219d1a3',
  nature_gravel:'fbc180d754bb62b4e32466ed64583c8a8b084370c99b27e2cc69cd46492535ee',
  nature_terrace:'9e19e4daf61e47f4812fa82fedb06f7593ac44b88d1f5450e0d668d5faa3d64b',
  nature_flowerbed:'98f1fa4708c496cd0323e5ceb286e6edbb9763729bb97eb30e483a3e4fdf6f0f'
};
for(const [type,hash] of Object.entries(legacy)){const f=fixture();f.build(type,{id:'legacy'});assert.equal(legacyDigest(f.scene),hash,type+' defaults must remain bit-identical');}
const f=fixture(),terrain=f.build('nature_hills',{id:'hill',position:[13,2,-5],rotation:27,size:[60,40],segments:[48,36],masses:[{center:[0,0],size:[55,12,38]}],peak:{center:[14,-4],size:[15,14,18]},terraceHeight:1.2,bands:true,greenhouses:{rows:2,columns:4,position:[-18,0],roofSize:[2,.4,4],spacing:[3,6]}});
const down=new THREE.Vector3(0,-1,0),land=terrain.getObjectByName('hill-land');
for(const [x,z] of [[0,0],[4,8],[-9,-3],[27,15]]){const p=terrain.localToWorld(new THREE.Vector3(x,50,z)),hit=new THREE.Raycaster(p,down).intersectObject(land)[0];assert.ok(hit);assert.ok(Math.abs(hit.point.y-(2+terrain.userData.heightAt(x,z)))<1e-5,'heightAt matches rendered triangles under transforms');}
assert.throws(()=>terrain.userData.heightAt(99,0),/outside/);
assert.equal(terrain.getObjectByName('hill-greenhouse-roofs').count,8);
const roofHits=new THREE.Raycaster(terrain.localToWorld(new THREE.Vector3(-19.4,60,-3)),down).intersectObject(terrain.getObjectByName('hill-greenhouse-roofs'));assert.ok(roofHits.length,'greenhouse upper faces are visible from overview, not inward-facing');
const clearing=[[-4,-20],[4,-20],[4,20],[-4,20]],forest=f.build('nature_grove',{id:'forest',terrain:'hill',position:[13,0,-5],rotation:27,size:[56,36],kind:'kesiya',density:.3,edgeFalloff:0,treeHeight:[8,12],shrubs:0,excludePolygons:[clearing]}),trunks=forest.getObjectByName('forest-trunks'),matrix=new THREE.Matrix4();
assert.ok(trunks.count>400,'hundreds of slope pines are instanced');
for(let i=0;i<trunks.count;i++){trunks.getMatrixAt(i,matrix);const p=new THREE.Vector3().setFromMatrixPosition(matrix),s=new THREE.Vector3().setFromMatrixScale(matrix);assert.ok(Math.abs(p.x)>=4,'excluded polygon stays free');const world=forest.localToWorld(new THREE.Vector3(p.x,p.y-s.y/2,p.z)),local=terrain.worldToLocal(world.clone());assert.ok(Math.abs(local.y-terrain.userData.heightAt(local.x,local.z))<2e-5,'trunk feet follow actual slope');}
let draws=0;forest.traverse(o=>{if(o.isMesh)draws++;});assert.ok(draws<=3,'forest has bounded draw calls');
const path=f.build('nature_path',{id:'slope-path',terrain:'hill',position:[13,0,-5],rotation:27,points:[[0,0,-15],[0,0,15]],width:1,heightOffset:.08,edges:false});assert.ok(f.walkableGeometries.length>0);
const boards=f.build('nature_path',{id:'slope-boards',pattern:'boardwalk',terrain:'hill',position:[13,0,-5],rotation:27,points:[[0,0,-15],[0,0,15]],width:1,heightOffset:.08,edges:false}),planks=boards.getObjectByName('slope-boards-boardwalk');
for(let i=0;i<planks.count;i+=Math.max(1,Math.floor(planks.count/10))){planks.getMatrixAt(i,matrix);const p=new THREE.Vector3().setFromMatrixPosition(matrix),world=boards.localToWorld(p),local=terrain.worldToLocal(world);assert.ok(local.y>terrain.userData.heightAt(local.x,local.z),'visible boards follow the same sampled terrain as route support');}
for(const z of [-13,-4,7,14]){const p=path.localToWorld(new THREE.Vector3(0,50,z)),hits=new THREE.Raycaster(p,down).intersectObject(path,true).filter(h=>h.object.userData.paving);assert.ok(hits.length);const local=terrain.worldToLocal(hits[0].point.clone());assert.ok(local.y>=terrain.userData.heightAt(local.x,local.z)+.07,'draped path clears terrain');}
const lake=f.build('nature_lake',{id:'lake',size:[180,90],outline:[[-85,-25],[-25,-40],[70,-30],[86,10],[12,40],[-70,25]],islands:[{position:[0,0],size:[14,9],height:.8}],jetty:{position:[0,0,32]},position:[-100,0,100],rotation:19});
assert.ok(lake.getObjectByName('lake-shore'));assert.ok(lake.getObjectByName('lake-fringe').isInstancedMesh);const island=lake.localToWorld(new THREE.Vector3(0,20,0));assert.equal(new THREE.Raycaster(island,down).intersectObject(lake.getObjectByName('lake-water')).length,0,'water has real island hole');assert.ok(lake.getObjectByName('lake-jetty-nature'));
const falls=f.build('nature_cascade',{id:'falls',position:[3,1,8],rotation:25,tiers:[{z:0,top:9,bottom:6},{z:4,top:6,bottom:3},{z:8,top:3,bottom:0}]});for(let i=0;i<3;i++){assert.ok(falls.getObjectByName('falls-tier-'+i+'-curtain'));assert.ok(falls.getObjectByName('falls-ledge-'+i));assert.ok(falls.getObjectByName('falls-pool-'+i));}
assert.throws(()=>f.build('nature_cascade',{id:'bad',tiers:[]}),/empty/);
for(const kind of ['cable','coaster']){const points=[[-20,0,0],[0,5,4],[20,9,0]],g=f.build('nature_line',{id:kind,kind,points,vehicles:12,towers:7});assert.equal(g.getObjectByName(kind+'-vehicles').count,12);assert.equal(g.getObjectByName(kind+'-stations').count,2);assert.ok(g.getObjectByName(kind+'-'+(kind==='cable'?'cables':'rails')).isInstancedMesh);const height=kind==='cable'?8:1.2,profile=new THREE.CatmullRomCurve3(points.map(([x,y,z])=>new THREE.Vector3(x,y+height,z)),false,'centripetal'),posts=g.getObjectByName(kind+'-towers');for(let i=0;i<posts.count;i++){posts.getMatrixAt(i,matrix);const p=new THREE.Vector3().setFromMatrixPosition(matrix),s=new THREE.Vector3().setFromMatrixScale(matrix);assert.ok(Math.abs(p.y-s.y/2-(profile.getPointAt(i/6).y-height))<1e-5,'tower feet interpolate the profile, not the nearest authored control point');}}
const stream=f.build('nature_stream',{id:'rapids',points:[[0,0,-8],[0,0,8]],width:6,boulders:70,rapids:{count:24,scale:1.1},excludePolygons:[[[-8,-1],[8,-1],[8,1],[-8,1]]]});const foam=stream.getObjectByName('rapids-rapids');assert.ok(foam.count>50&&foam.count<=120);assert.ok(!stream.getObjectByName('rapids-water').userData.paving);
for(let i=0;i<foam.count;i++){foam.getMatrixAt(i,matrix);const p=new THREE.Vector3().setFromMatrixPosition(matrix),s=new THREE.Vector3().setFromMatrixScale(matrix);assert.ok(Math.abs(p.z)+Math.max(s.x,s.z)<8,'rapids never spill past the authored stream ends');assert.ok(Math.abs(p.x)+Math.max(s.x,s.z)<3,'rapids remain inside both banks');}
const rocks=stream.getObjectByName('rapids-boulders');for(let i=0;i<rocks.count;i++){rocks.getMatrixAt(i,matrix);const p=new THREE.Vector3().setFromMatrixPosition(matrix),s=new THREE.Vector3().setFromMatrixScale(matrix);assert.ok(Math.abs(p.z)>1+Math.max(s.x,s.z)-1e-5,'bridge exclusion clears boulders');}
const raised=fixture();raised.build('nature_stream',{id:'raised-stream',position:[3,2,-4],rotation:23,baseY:8,boardwalk:{},boulders:0});assert.ok(raised.walkableGeometries.length);for(const geo of raised.walkableGeometries){geo.computeBoundingBox();assert.ok(geo.boundingBox.min.y>=10,'nested boardwalk route support includes baseY exactly once');assert.ok(geo.boundingBox.max.y<12);}
for(const type of ['nature_lake','nature_hills','nature_line'])assert.ok(new THREE.Box3().setFromObject(fixture().build(type)).max.y>=0,'default '+type+' boots');
const tapered=fixture().build('nature_hills',{size:[40,40],height:8,masses:[],bottom:0,edgeFalloff:[4,4]});assert.equal(tapered.userData.heightAt(20,0),0);assert.equal(tapered.userData.heightAt(0,0),8);assert.ok(tapered.userData.heightAt(18,0)>0&&tapered.userData.heightAt(18,0)<8,'hill edge is a real softened slope');
const blocks=fixture().build('nature_hills',{size:[60,40],masses:[],height:1,profile:[[-20,0],[0,0],[10,4],[20,4]],profileBend:3,greenhouses:{blocks:[{rows:2,columns:3,position:[-12,-10],rotation:6},{rows:2,columns:3,position:[12,-10],rotation:-6}]}});for(let i=0;i<2;i++)assert.equal(blocks.getObjectByName('subject-block-'+i+'-greenhouse-roofs').count,6);assert.ok(blocks.userData.heightAt(0,5)>blocks.userData.heightAt(20,5),'bent hill profile is a curved land edge, not a billboard');
assert.throws(()=>fixture().build('nature_line',{towers:1}),/two towers/);assert.throws(()=>fixture().build('nature_hills',{segments:[0,5]}),/segments/);
const customStations=fixture().build('nature_line',{points:[[-12,2,0],[12,6,0]],stationSize:[8,4,6]}).getObjectByName('subject-stations');for(let i=0;i<2;i++){customStations.getMatrixAt(i,matrix);const p=new THREE.Vector3().setFromMatrixPosition(matrix),s=new THREE.Vector3().setFromMatrixScale(matrix);assert.ok(Math.abs(p.y-s.y/2-[2,6][i])<1e-6,'custom station dimensions stay grounded at each end');}
const example=JSON.parse(fs.readFileSync(join(CODE,'kits/examples/nature.place.json'),'utf8'));
for(const type of ['nature_lake','nature_hills','nature_line','nature_grove','nature_cascade'])assert.ok(example.objects.some(o=>o.type===type),'example contains '+type);
const output=fs.mkdtempSync(join(DATA,'out_nature-landscape-test-'));
try{
  const build=spawnSync('python3',['-B',join(CODE,'build.py'),join(CODE,'kits/examples/nature.place.json'),output],{encoding:'utf8'});assert.equal(build.status,0,build.stdout+build.stderr);
  const start=performance.now(),runtime=await boot(fs.readFileSync(join(output,'index.html'),'utf8'));assert.ok(runtime.scene.getObjectByName('landscape-forest-nature'));assert.ok(runtime.window.__hotspots.length===2);const elapsed=performance.now()-start;assert.ok(elapsed<15000,'landscape example boots within the 15 second geometry budget');console.log('nature landscape example boot ms:',Math.round(elapsed));
}finally{fs.rmSync(output,{recursive:true,force:true});}
console.log('nature landscape: geometry, instancing, transforms, exclusions, example boot and legacy defaults pass');
