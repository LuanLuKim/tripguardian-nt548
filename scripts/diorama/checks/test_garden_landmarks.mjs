import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {join} from 'node:path';
import {spawnSync} from 'node:child_process';
import {CODE,DATA} from '../paths.mjs';
import {THREE,mergeGeometries,boot,digest} from './pagoda_runtime.mjs';

// Captured from the published pre-extension Yersin build, before rebuilding it.
const BASELINES={"surface":"42392a9638851190cfee7d35cbeb604488c99368a12ca2219ae4c8409b287434","path":"3d1c11cc95e2b13f9871c22e21b34fbb66f8e9cb082936891d49f0d4e212d46b","bed":"90bcb16b8be7a51f2bfa416b9f3420e25260acbc3f4a0b68ed84f1bda94bfe8e","water":"19e18afa99f4c4042072d9370e8b4486d082e99b35f34c04420fd9ac3c821c45","arch":"934e88c805eebe6e3f50ea7610c101eb25d872a95019f9c30ac1d36585402714","structure":"dbab2295b637f2647d1c26aa1772d1576a6e41b1a0e978c5fa83f8663d18c6c4","topiary":"881d82359b70baf422407a0c33391998e4d9dea6b29c3296e8584ece9e63cdc9","grove":"6c4c4262d6153099ffdff505ebd869a8f7a858d739251c923885ddfff9037c84","furniture":"97ea0aa637fe36ad415a0c97248f2247c0e2825e5f24d9e3cc848322464fcfc1","terrain":"c6949d74cc15937dafbc2f88e2ef8fafa9e517e7f93adc4d8ee1a54a15477fdb","field":"9e6c86a3c91b15e54a4264048fb578f60a2320276548eaa41eb299c5d64e8914","bridge":"0488622f94602a2963c8eeac3ea667f416379bd6a31142a97ebf53bb98d4ccc2","stairs":"f1eb91abe18b5d80732017c963ce33c41d548979b0887d045fd26750f80bceff","platform":"18cbc14ba5ddcc8ad26a571f079a7e07c15aa523d53ec575c460cd5579332ca9","swing":"e203e55aa8b205428fbc6d7a601171bed5e9c8f950e2a18ca4d9d78558e3455a","sculpture":"5e88e34cce3a03bb0d5ac537b3b5309cd37c85438d2b67abcc94a429135d27fd","conifer":"2dc8daf766a3458ae9015c22e93e527764188ce0f728541232d9085306ac5735","shelter":"e5838b16e5f1b41539e1f10bc56f2f4586ec286065e0d5b166c4ae41ffe4e168"};
const oldTypes=['surface','path','bed','water','arch','structure','topiary','grove','furniture','terrain','field','bridge','stairs','platform','swing','sculpture','conifer','shelter'];
function harness(source){
  const objects={},scene=new THREE.Scene(),walkableGeometries=[],roofRecords=[];
  vm.runInNewContext(source,{THREE,mergeGeometries,scene,walkableGeometries,roofRecords,currentEnvelope:[],place:{route:[]},
    material:c=>new THREE.MeshStandardMaterial({color:c}),registerObjectType:(k,b)=>objects[k]=b,
    document:{createElement:()=>({getContext:()=>new Proxy({},{get:()=>()=>{}})})}});
  function build(type,options={}){objects['garden_'+type]({id:'fixture',...options});const g=scene.children.at(-1);g.updateWorldMatrix(true,true);g.traverse(p=>{if(p.geometry)for(const v of p.geometry.attributes.position.array)assert.ok(Number.isFinite(v),type+' finite vertices');});return g;}
  return {build,objects,walkableGeometries,scene};
}
const source=fs.readFileSync(join(CODE,'kits/garden.js'),'utf8');
for(const type of oldTypes){const h=harness(source);assert.equal(digest(h.build(type)).hash,BASELINES[type],type+' unchanged default geometry/materials/transforms');}
const h=harness(source);
assert.notEqual(digest(h.build('bed',{foliageForm:'foam'})).hash,BASELINES.bed,'foam foliage is opt-in');
const mill=h.build('windmill');assert.equal(mill.getObjectsByProperty('name','garden-windmill-sail').length,4);
h.build('windmill',{sides:32,gallery:true});
const turbine=h.build('turbine',{height:80,bladeLength:35});assert.equal(turbine.getObjectsByProperty('name','garden-turbine-blade').length,3);
assert.ok(new THREE.Box3().setFromObject(turbine).max.y>105);
const count=h.walkableGeometries.length;
h.build('bridge',{style:'glass',position:[3,1,-2],rotation:27,ends:[[-10,2,0],[10,5,0]],sag:.5});
assert.ok(h.walkableGeometries.length>count,'glass deck is walkable');
const glass=h.walkableGeometries.at(-1),ray=new THREE.Raycaster(new THREE.Vector3(3,50,-2),new THREE.Vector3(0,-1,0));
const hits=ray.intersectObject(new THREE.Mesh(glass,new THREE.MeshBasicMaterial({side:THREE.DoubleSide})));
assert.ok(Math.abs(hits[0].point.y-4)<.02,'sloped sagging glass deck is transformed exactly');
for(const options of [{outline:'heart',repeat:6},{repeat:3},{canopy:'umbrella'},{canopy:'pinwheel'}])h.build('arch',options);
const cloud=h.build('conifer',{form:'cloud',height:1.2,radius:.5,pot:true});
assert.ok(cloud.getObjectByName('garden-cloud-foliage-pads').isInstancedMesh);
h.build('rockery');h.build('koi_pond',{size:[14,10],waterfall:{height:3},steppingStones:[[-2,0],[0,0],[2,0]],koi:24});
const cascade=h.build('koi_pond',{waterfall:{position:[0,0],height:3,depth:3,tiers:3}});
const fallHit=new THREE.Raycaster(new THREE.Vector3(0,2.68,10),new THREE.Vector3(0,0,-1)).intersectObject(cascade,true).find(v=>['garden-rock-waterfall','garden-rounded-boulders'].includes(v.object.name));
assert.equal(fallHit.object.name,'garden-rock-waterfall','backing rocks do not cover the falling water sheet');
for(const kind of ['liberty','bust','clay'])h.build('sculpture',{kind});
for(const roofed of [false,true])h.build('clay_tunnel',{roofed});
const wall=h.build('clay_tunnel',{kind:'wall',position:[2,0,3],rotation:0});
assert.equal(new THREE.Raycaster(new THREE.Vector3(2,2,10),new THREE.Vector3(0,0,-1)).intersectObject(wall,true).filter(v=>v.object.isMesh).length,0,'carved wall has a real central arched opening');
const tunnel=h.build('clay_tunnel');
assert.equal(new THREE.Raycaster(new THREE.Vector3(0,2,15),new THREE.Vector3(0,0,-1)).intersectObject(tunnel,true).filter(v=>v.object.isMesh).length,0,'tunnel remains open along its walking axis');
const heart=h.build('arch',{outline:'heart',repeat:1});
assert.equal(new THREE.Raycaster(new THREE.Vector3(0,.15,3),new THREE.Vector3(0,0,-1)).intersectObject(heart,true).filter(v=>v.object.isMesh).length,0,'heart feet do not cross the path');
assert.throws(()=>h.build('bridge',{style:'glass',ends:[[0,0,0],[0,2,0]]}),/distinct ends/);
const example=JSON.parse(fs.readFileSync(join(CODE,'kits/examples/garden.place.json'),'utf8'));
for(const type of ['windmill','turbine','rockery','koi_pond','clay_tunnel'])assert.ok(example.objects.some(o=>o.type==='garden_'+type),'example contains '+type);
for(const kind of ['liberty','bust','clay'])assert.ok(example.objects.some(o=>o.type==='garden_sculpture'&&o.kind===kind));
assert.ok(example.objects.some(o=>o.type==='garden_bridge'&&o.style==='glass'));
assert.ok(example.objects.some(o=>o.type==='garden_arch'&&o.outline==='heart'));
assert.ok(example.objects.some(o=>o.type==='garden_conifer'&&o.form==='cloud'));
assert.ok(example.objects.some(o=>o.type==='garden_bed'&&o.foliageForm==='foam'));
assert.ok(example.objects.some(o=>o.type==='garden_clay_tunnel'&&o.kind==='wall'));
for(const canopy of ['umbrella','pinwheel'])assert.ok(example.objects.some(o=>o.type==='garden_arch'&&o.canopy===canopy));
const out=join(DATA,'out_garden_landmarks');
const build=spawnSync('python3',['-B',join(CODE,'build.py'),join(CODE,'kits/examples/garden.place.json'),out],{encoding:'utf8',cwd:DATA});assert.equal(build.status,0,build.stdout+build.stderr);
const runtime=await boot(fs.readFileSync(join(out,'index.html'),'utf8'));assert.equal(runtime.window.__ready,true);
const published={camtucau:'fa040055c29c61d90414c2b1be647de22f6c978070c3dcf1e431bde9a8993ce0',vuonhoa:'18a3baed349cab27396d89a92a7b90f8db2ee39bfe60b0ea3baf891956d04da0',yersin:'478b4f725f5523369eb4ffb2780ba167e1364d1db3761f081714f2d02e99cde0'};
for(const [slug,hash] of Object.entries(published)){
  const dir=join(DATA,'out_'+slug,'garden-landmarks-regression');
  const result=spawnSync('python3',['-B',join(CODE,'build.py'),join(DATA,'places',slug,'place.json'),dir],{encoding:'utf8',cwd:DATA});assert.equal(result.status,0,result.stdout+result.stderr);
  assert.equal(digest((await boot(fs.readFileSync(join(dir,'index.html'),'utf8'))).scene).hash,hash,slug+' published scene is identical to baseline');
}
console.log('garden landmarks: old defaults stable; all variants finite; transformed glass route; example build + boot PASS');
