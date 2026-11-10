import {CODE} from '../paths.mjs';
import {join} from 'node:path';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {test} from 'node:test';
import * as THREE from '../vendor/node_modules/three/build/three.module.js';
import {mergeGeometries} from '../vendor/node_modules/three/examples/jsm/utils/BufferGeometryUtils.js';

function fixture(objects=[]){
  const scene=new THREE.Scene(),builders={},interiors={},roofs=[],walkable=[];
  const context={THREE,mergeGeometries,scene,place:{objects,route:[]},currentEnvelope:[],roofRecords:roofs,
    walkableGeometries:walkable,material:c=>new THREE.MeshStandardMaterial({color:c}),contactShadow(){},
    registerObjectType:(n,f)=>builders[n]=f,registerInteriorKit:(n,f)=>interiors[n]=f};
  vm.createContext(context);vm.runInContext(fs.readFileSync(join(CODE, 'kits/church.js'),'utf8'),context);
  function build(type,options={}){
    assert.equal(typeof builders[type],'function',`${type} is registered`);
    builders[type]({id:'fixture',position:[0,0,0],...options});scene.updateMatrixWorld(true);
    scene.traverse(m=>{if(m.geometry)assert.ok([...m.geometry.attributes.position.array].every(Number.isFinite),'finite geometry');});
    return scene.children.at(-1);
  }
  return {scene,build,roofs,walkable,interiors};
}
test('A-frame roof color follows JSON without recoloring timber',()=>{
  const f=fixture();f.build('church_aframe',{size:[19,31],roofColor:'#ded9c8'});
  assert.equal(f.roofs[0].parameters.color,'#ded9c8');
  const roof=f.scene.getObjectByName('camly-main-roof');
  assert.ok(roof.children.some(m=>m.isMesh&&m.material.color.getHexString()==='ded9c8'));
});
test('pointed facade has independently colored bands, tall glazing and doors',()=>{
  const f=fixture(),g=f.build('church_facade',{width:20,eaveHeight:3,ridgeHeight:22,wallColor:'#ded8c8',
    bands:[{from:0,to:4,color:'#a66f65'}],arches:[{x:0,y:1,width:4,height:15,doorHeight:3},{x:-5,y:1,width:3,height:9,doorHeight:3}]});
  assert.ok(g.getObjectByName('church-facade-band-0'));
  assert.ok(g.getObjectByName('church-pointed-glass'));
  assert.ok(g.getObjectByName('church-facade-door'));
  const ray=new THREE.Raycaster(new THREE.Vector3(0,10,5),new THREE.Vector3(0,0,-1));
  assert.ok(ray.intersectObject(g,true).some(h=>h.object.name==='church-pointed-glass'),'glass occupies the central arch');
});
test('rose, triple lancets and projecting balcony are reusable facade options',()=>{
  const f=fixture(),g=f.build('church_facade',{width:17,eaveHeight:7,ridgeHeight:22,
    rose:{y:17,radius:1.2},lancets:{centres:[-5,5],y:6.6,width:.55,height:2,count:3,spacing:.9},
    arches:[{x:0,y:4.3,width:3.8,height:5.4,doorHeight:2.5}],balcony:{y:4.3,width:3.8,depth:2.1,doorWidth:1.2,doorHeight:2.5}});
  for(const n of ['church-rose-tracery','church-lancets','church-box-balcony'])assert.ok(g.getObjectByName(n),n);
});
test('gabled nave registers configurable roof and stone flank buttresses',()=>{
  const f=fixture(),g=f.build('church_gabled',{size:[17,34],eaveHeight:7,ridgeHeight:22,roofColor:'#797b73',
    buttresses:{count:7,height:6,width:.8,projection:1.5},dormers:{count:5,width:2,height:2}});
  assert.equal(f.roofs[0].parameters.color,'#797b73');
  assert.ok(g.getObjectByName('church-stone-buttresses'));
  assert.ok(g.getObjectByName('church-roof-dormers'));
});
test('side glazing can be disabled for a windowless chapel',()=>{
  const f=fixture(),g=f.build('church_gabled',{size:[12,20],sideWindows:false});
  assert.ok(!g.getObjectByName('church-pointed-glass'),'disabled side glazing produces no panes');
});
test('narrow curved stairs reach their top without a broad fan footprint',()=>{
  const f=fixture(),g=f.build('church_stairs',{points:[[-9,2],[-7,1],[-2,1]],width:1.4,height:4.3,steps:24});
  const bounds=new THREE.Box3().setFromObject(g);
  assert.ok(bounds.max.z-bounds.min.z<4,'a narrow flight, not a fan');
  assert.ok(bounds.max.y>=5,'top parapet reaches the landing');
  assert.ok(f.walkable.length>=24,'each tread is walkable');
});
test('straight podium stair and patterned forecourt remain independently parameterized',()=>{
  const f=fixture(),g=f.build('church_forecourt',{size:[22,15],podium:{width:20,depth:3,height:1.2},
    stairs:{width:18,depth:4,steps:8},pattern:{spacing:1,color:'#b59f94'}});
  assert.ok(g.getObjectByName('church-court-pattern'));
  assert.ok(f.walkable.length>8);
});
test('multi-storey pointed verandas, roof gables and external curved stair are built together',()=>{
  const f=fixture(),g=f.build('parish_arcade',{size:[10,30],storeys:3,storeyHeight:3.6,bays:6,
    roofGables:6,externalStair:{side:1,width:1.5,steps:24}});
  assert.equal(g.getObjectByName('parish-stacked-arcades').userData.storeys,3);
  assert.ok(g.getObjectByName('parish-roof-gables'));
  assert.ok(g.getObjectByName('parish-external-stair'));
});
test('arcade repetition is batched across floors and bays',()=>{
  const f=fixture(),g=f.build('parish_arcade',{size:[10,30],storeys:3,bays:7,roofGables:7});
  let meshes=0;g.traverse(m=>{if(m.isMesh)meshes++;});
  assert.ok(meshes<100,`repeated veranda details use shared batches, got ${meshes}`);
});
test('convent windows occupy every storey with many dormers',()=>{
  const f=fixture(),g=f.build('parish_arcade',{size:[10,30],storeys:4,storeyHeight:3,bays:7,veranda:false,dormers:{count:7}});
  assert.equal(g.getObjectByName('parish-stacked-windows').userData.storeys,4);
  assert.ok(g.getObjectByName('parish-roof-dormers'));
});
test('convent rectangular windows do not become pointed church windows',()=>{
  const f=fixture(),g=f.build('parish_arcade',{size:[10,30],storeys:2,bays:7,veranda:false,windowStyle:'rectangular'});
  assert.equal(g.getObjectByName('parish-stacked-windows').userData.windowStyle,'rectangular');
});
test('solid parish wings show their end glazing from both exterior sides',()=>{
  for(const windowStyle of ['pointed','rectangular']){
    const f=fixture(),g=f.build('parish_arcade',{size:[10,30],storeys:2,veranda:false,windowStyle,windowColor:'#123456'});
    for(const end of [-1,1]){
      const ray=new THREE.Raycaster(new THREE.Vector3(.3,1.5,end*20),new THREE.Vector3(0,0,-end));
      const first=ray.intersectObject(g,true).find(h=>h.object.isMesh);
      assert.equal(first?.object.material.color.getHexString(),'123456',`${windowStyle} glazing is outside end ${end}`);
    }
  }
});
test('planting accepts the documented default stair path and court footprint',()=>{
  for(const type of ['church_stairs','church_forecourt']){
    const object={type,id:'default',position:[0,0,0]},f=fixture([object]);
    f.build(type,object);
    assert.doesNotThrow(()=>f.build('parish_planting',{size:[30,30],spacing:2,density:1,flowers:0}),type);
  }
});
test('roof gables include real pitched roof surfaces, not freestanding triangles',()=>{
  const f=fixture(),g=f.build('parish_arcade',{size:[10,30],storeys:3,bays:6,roofGables:6});
  assert.ok(g.getObjectByName('parish-cross-gable-roofs'));
});
test('oval shrine stands vertically around a statue on a paved circle',()=>{
  const f=fixture(),g=f.build('church_shrine',{ring:{width:3.6,height:6,thickness:.24},pavingRadius:4});
  const ring=g.getObjectByName('church-oval-ring'),bounds=new THREE.Box3().setFromObject(ring);
  assert.ok(bounds.max.y-bounds.min.y>5.9);
  assert.ok(bounds.max.z-bounds.min.z<.6);
  assert.ok(g.getObjectByName('church-shrine-statue'));
  assert.ok(f.walkable.length);
});
test('Marian shrine has a veil and restrained prayer pose rather than a crossbar',()=>{
  const f=fixture(),g=f.build('church_shrine',{pose:'prayer',statueColor:'#ddd9c9',veilColor:'#c6cfc4'});
  assert.ok(g.getObjectByName('church-shrine-veil'));
  assert.equal(g.getObjectByName('church-shrine-statue').userData.pose,'prayer');
});
test('new masonry volumes and courts exclude random planting',()=>{
  const f=fixture();f.build('parish_planting',{size:[30,30],spacing:2,density:1,flowers:0});
  // Reboot with the footprint in the real place data supplied to the kit.
  const scene=new THREE.Scene(),builders={};
  const ctx={THREE,mergeGeometries,scene,place:{objects:[{type:'church_gabled',position:[0,0,0],size:[20,20]}],route:[]},
    currentEnvelope:[],roofRecords:[],walkableGeometries:[],material:c=>new THREE.MeshStandardMaterial({color:c}),
    registerObjectType:(n,f)=>builders[n]=f,registerInteriorKit(){},contactShadow(){}};
  vm.createContext(ctx);vm.runInContext(fs.readFileSync(join(CODE, 'kits/church.js'),'utf8'),ctx);
  builders.parish_planting({position:[0,0,0],size:[30,30],spacing:2,density:1,flowers:0});
  const batch=scene.getObjectByName('parish-shrub-instances'),m=new THREE.Matrix4(),p=new THREE.Vector3();
  for(let i=0;i<batch.count;i++){batch.getMatrixAt(i,m);p.setFromMatrixPosition(m);assert.ok(Math.abs(p.x)>10||Math.abs(p.z)>10,'no shrubs inside masonry church');}
});
test('masonry interior matches its roof and the lower entrance opens through the wall',()=>{
  const f=fixture(),o={id:'fixture',type:'church_gabled',position:[0,0,0],size:[17,34],eaveHeight:7,ridgeHeight:22,
    facade:{balcony:{y:5.3,width:4,depth:2,doorHeight:2.6,doorWidth:1.2}},
    interior:{kit:'church_nave',pews:{rows:6,startZ:9,spacing:1.4,width:5,aisleWidth:2},altar:{z:-12,width:3,crucifixX:0},
      timber:{trussSpacing:3,tieEvery:3,tieHeights:[10,15],boardSpacing:.24}}};
  const g=f.build('church_gabled',o),room=f.interiors.church_nave(o);
  assert.equal(room.door?.name,'church-lower-door');
  room.door.visible=false;
  const hits=new THREE.Raycaster(new THREE.Vector3(0,1.7,20),new THREE.Vector3(0,0,-1)).intersectObject(g,true).filter(h=>h.object.visible);
  assert.ok(!hits.some(h=>h.distance<5),'no masonry backing blocks the lower door');
  const b=new THREE.Box3().setFromObject(room.ceiling);
  assert.ok(b.max.y>21&&b.max.y<22.1,'timber ceiling meets masonry ridge');
  assert.ok(b.min.y>6,'timber ceiling meets masonry eave');
  assert.equal(room.front?.name,'church-gabled-reveal-walls');
});
test('masonry interior supports a pointed sanctuary and entrance gallery',()=>{
  const f=fixture(),o={id:'fixture',type:'church_gabled',position:[0,0,0],size:[17,34],eaveHeight:7,ridgeHeight:22,
    interior:{kit:'church_nave',pews:{rows:6,startZ:9,spacing:1.4,width:5,aisleWidth:2},altar:{z:-12,width:3,crucifixX:0},
      timber:{trussSpacing:3,tieEvery:3,tieHeights:[10,15],boardSpacing:.24},
      sanctuary:{width:12,height:12,z:-15,color:'#ded4b7'},gallery:{height:5.3,depth:3}}};
  f.build('church_gabled',o);const room=f.interiors.church_nave(o);
  assert.ok(room.group.getObjectByName('nave-pointed-sanctuary'));
  assert.ok(room.group.getObjectByName('nave-entrance-gallery'));
  delete o.eaveHeight;delete o.ridgeHeight;
  const fallback=f.interiors.church_nave(o);
  fallback.ceiling.traverse(m=>{if(m.geometry)assert.ok([...m.geometry.attributes.position.array].every(Number.isFinite),'interior uses the same roof defaults as the exterior');});
});
