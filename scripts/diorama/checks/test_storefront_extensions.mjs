import {CODE} from '../paths.mjs';
import {join} from 'node:path';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import * as THREE from '../vendor/node_modules/three/build/three.module.js';
import {mergeGeometries} from '../vendor/node_modules/three/examples/jsm/utils/BufferGeometryUtils.js';

const objects={},interiors={},scene=new THREE.Scene(),roofs=[],walk=[],materials=new Map();
const context={THREE,mergeGeometries,scene,roofRecords:roofs,walkableGeometries:walk,currentEnvelope:null,
  material:c=>{if(!materials.has(c))materials.set(c,new THREE.MeshStandardMaterial({color:c,roughness:1}));return materials.get(c);},
  registerObjectType:(t,b)=>objects[t]=b,registerInteriorKit:(t,b)=>interiors[t]=b,
  place:{hotspots:[]},resolveInteriorBuilding:()=>null,KITS:{interiors},contactShadow(){}};
vm.createContext(context);vm.runInContext(fs.readFileSync(join(CODE, 'kits/storefront.js'),'utf8'),context);
const fixtures=[
  ['shelter',{size:[12,5,10],roof:{kind:'shed',rise:.8,pitch:.22},postSpacing:4}],
  ['stilt_house',{size:[9,5.5,6],stiltHeight:2.1,balcony:{depth:1.5,jars:9}}],
  ['jars',{entries:[[-1,0,0,1.4],[1,0,0,.8]],shelf:{size:[4,3,.8],levels:3,columns:6}}],
  ['pavilion',{size:[4,3,3],roof:{rise:1.4,pitch:.12}}],
  ['figures',{figures:[[-1,0,1.5],[1,0,1.9]],color:'#8e7156'}],
  ['mushroom_stair',{radius:1.8,height:3,steps:18,turn:240}],
  ['rockery',{size:[7,6],height:3,tiers:4,pool:[4,2.5],ferns:24,seed:9}],
  ['rope_bridge',{size:[2.4,7],height:.8,sag:.3,postSpacing:1.8}],
  ['dining_hall',{size:[7,3.4,18],postSpacing:3,tables:[[-1.7,-6],[1.7,6]],roof:{kind:'gable',rise:1}}],
];
for(const [suffix,options] of fixtures){
  const type='storefront_'+suffix;
  assert.equal(typeof objects[type],'function',type+' is registered');
  const id='test-'+suffix;
  context.currentEnvelope=[];
  objects[type]({id,type,position:[2,0,3],rotation:17,...options});
  const root=scene.getObjectByName(id+'-storefront');
  assert.ok(root,'semantic root '+type);
  root.updateMatrixWorld(true);
  const bounds=new THREE.Box3().setFromObject(root);
  assert.ok(!bounds.isEmpty()&&bounds.max.y>0,'nonempty '+type);
  assert.ok(bounds.min.y>=-.03&&bounds.min.y<.2,'grounded '+type+': '+bounds.min.y);
  for(const p of context.currentEnvelope)assert.ok(bounds.clone().expandByScalar(.001).containsPoint(p),'framing points use full ancestor transform '+type+': '+p.toArray());
  context.currentEnvelope=null;
  let count=0;
  root.traverse(m=>{if(m.isMesh){count++;for(const v of m.geometry.attributes.position.array)assert.ok(Number.isFinite(v),'finite '+type);}});
  assert.ok(count<65,'batched '+type+': '+count);
}
assert.ok(scene.getObjectByName('storefront-corrugated-ribs')?.isInstancedMesh,'actual repeated metal ribs');
assert.ok(scene.getObjectByName('storefront-jar-bodies')?.isInstancedMesh,'lathed jar bodies are instanced');
assert.ok(scene.getObjectByName('storefront-jar-mouths'),'dark recessed jar openings');
assert.ok(scene.getObjectByName('storefront-carved-faces'),'wooden figures have faces');
assert.ok(scene.getObjectByName('storefront-water-falls'),'tiered water sheets');
assert.ok(scene.getObjectByName('storefront-fern-fronds')?.isInstancedMesh,'fern leaflets are batched');
objects.storefront_jars({id:'default-jar'});
assert.equal(scene.getObjectByName('default-jar-storefront').getObjectByName('storefront-jar-bodies')?.count,1,'standalone jars have a sensible visible default');
const tierRocks=scene.getObjectByName('test-rockery-storefront').getObjectByName('storefront-boulders');
assert.ok(tierRocks.count>100,'boulders mantle waterfall tiers as well as pool edges');
assert.ok(roofs.length>=4,'all building roofs are registered');
objects.storefront_shelter({id:'cross-shed',size:[8,3.4,10],braces:false,roof:{kind:'shed',ridgeAxis:'z',rise:.8}});
const crossShed=scene.getObjectByName('cross-shed-storefront'),postMesh=crossShed.getObjectByName('storefront-structural-posts'),matrix=new THREE.Matrix4(),point=new THREE.Vector3();
for(let i=0;i<postMesh.count;i++){postMesh.getMatrixAt(i,matrix);point.set(0,.5,0).applyMatrix4(matrix);const roofY=3.4+.8*(.5-point.x/8.7);assert.ok(Math.abs(point.y-roofY)<.001,'shed posts meet sloped roof along selected axis');}
const pavilion=scene.getObjectByName('test-pavilion-storefront'),pavilionStructure=pavilion.getObjectByName('storefront-batch').geometry.attributes.position;
for(let i=0;i<pavilionStructure.count;i++){
  const x=pavilionStructure.getX(i),y=pavilionStructure.getY(i),z=pavilionStructure.getZ(i);
  const hipTop=3+1.4*Math.min(1-Math.abs(z)/2.1,1-Math.max(0,Math.abs(x)-.5)/2.1);
  assert.ok(y<=hipTop+.11,'pavilion trusses remain under the hip roof: '+[x,y,z]);
}
const mushroom=scene.getObjectByName('test-mushroom_stair-storefront'),mushroomParts=mushroom.getObjectByName('storefront-batch').geometry.attributes.position;
let innerRadius=Infinity;
for(let i=0;i<mushroomParts.count;i++)if(Math.abs(mushroomParts.getY(i)-((3-.15)/18-.1))<.001)innerRadius=Math.min(innerRadius,Math.hypot(mushroomParts.getX(i),mushroomParts.getZ(i)));
assert.ok(innerRadius<=1.8*.16,'mushroom treads connect to supporting stem: '+innerRadius);
const beforeWalk=walk.length;
objects.storefront_rockery({id:'dry-test',size:[5,5],tiers:2});
assert.equal(walk.length,beforeWalk,'rocks and pool are not walkable');
objects.storefront_garden({id:'curve',size:[8,6],shape:'kidney',kind:'bed',density:5,seed:3});
const curve=scene.getObjectByName('curve-storefront');
assert.ok(curve.getObjectByName('storefront-curved-border'),'continuous curved kerb');
const ground=curve.getObjectByName('storefront-garden-ground');
assert.ok(ground.geometry.attributes.position.count>30,'curved ground is not a box');
objects.storefront_grove({id:'aged',kind:'aged',trees:[[0,0,9]],crownDensity:.25});
assert.ok(scene.getObjectByName('aged-storefront').getObjectByName('storefront-aged-branches'),'old trees expose woody branches');
objects.storefront_steps({id:'stair',size:[1.8,5],steps:15,rise:.2,openRisers:true,rail:{spacing:.7}});
assert.ok(scene.getObjectByName('stair-storefront').getObjectByName('storefront-stair-stringers'),'external stair has structural stringers');
objects.storefront({id:'stone',size:[8,6,7],storeys:2,cladding:{kind:'stone',course:.3},facade:{kind:'rectangular'},roof:{kind:'gable'}});
assert.ok(scene.getObjectByName('stone-storefront').getObjectByName('storefront-cladding-joints'),'masonry wraps the shell');
const room=interiors.storefront_room({id:'timber-room',size:[8,4,9],interior:{counter:false,wall:'#8c745e',windowKind:'rectangular',jars:{shelf:{size:[5,2.6,.7],levels:3,columns:8}},pendants:[[0,-2],[0,2]],tables:[],plants:[]}}, {roof:new THREE.Group()});
assert.ok(room.group.getObjectByName('storefront-jar-bodies'),'room supports jar shelves');
assert.ok(room.group.getObjectByName('storefront-pendant-shades'),'room supports pendant lighting fixtures');
assert.ok(room.ceiling.getObjectByName('storefront-sealed-ceiling'),'room retains sealed ceiling');
context.place.hotspots=[{interior:true,building:'rect-open'}];context.resolveInteriorBuilding=()=>({id:'rect-open'});
objects.storefront({id:'rect-open',size:[8,4,6],interior:{kit:'storefront_room'},facade:{kind:'rectangular',bays:3,openingWidth:1.5,openingHeight:2.8}});
const rectangular=scene.getObjectByName('rect-open-storefront');rectangular.updateMatrixWorld(true);
assert.equal(new THREE.Raycaster(new THREE.Vector3(0,1.7,3.3),new THREE.Vector3(0,0,-1),0,.6).intersectObject(rectangular,true).length,0,'rectangular entrance is physically open for supported interior');
const openRoom=interiors.storefront_room({id:'open-room',size:[8,4,9],interior:{size:[7.8,8.8],openSides:true,counter:false,tables:[],plants:[],windows:[]}},{roof:new THREE.Group()});openRoom.group.updateMatrixWorld(true);
assert.equal(new THREE.Raycaster(new THREE.Vector3(4.2,1.7,0),new THREE.Vector3(-1,0,0),0,.6).intersectObject(openRoom.group,true).length,0,'open hall has no visible opaque exterior side wall');
assert.ok(new THREE.Raycaster(new THREE.Vector3(0,1.7,0),new THREE.Vector3(1,0,0)).intersectObject(openRoom.group,true).length,'open hall studio horizon still seals sky inside');
assert.equal(openRoom.group.getObjectByName('storefront-room-horizon').castShadow,false,'studio horizons never cast artificial wall shadows into an open hall');
console.log('PASS storefront extensions: nine families, curved beds, aged trees, cladding, stairs and room details');
