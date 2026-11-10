import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {join} from 'node:path';
import {spawnSync} from 'node:child_process';
import {CODE,DATA} from '../paths.mjs';
import {THREE,mergeGeometries,boot,digest} from './pagoda_runtime.mjs';

const scene=new THREE.Scene(),builders={},envelope=[],materials=new Map();
vm.runInNewContext(fs.readFileSync(join(CODE,'kits/garden.js'),'utf8'),{
  THREE,mergeGeometries,scene,currentEnvelope:envelope,walkableGeometries:[],roofRecords:[],place:{route:[]},
  material:c=>{if(!materials.has(c))materials.set(c,new THREE.MeshStandardMaterial({color:c}));return materials.get(c);},
  registerObjectType:(name,builder)=>builders[name]=builder
});
function build(text,options={}){
  const start=envelope.length;
  builders.garden_letters({id:'letters',text,...options});
  const group=scene.children.at(-1);group.updateWorldMatrix(true,true);
  group.traverse(m=>{if(m.geometry)for(const n of m.geometry.attributes.position.array)assert.ok(Number.isFinite(n),'finite glyph vertices');});
  return {group,points:envelope.slice(start),bounds:new THREE.Box3().setFromObject(group)};
}
const cap='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789♥';
assert.equal(build(cap).group.userData.letterCount,37,'complete embedded alphabet/digits/heart');
for(const c of cap)assert.ok(build(c).points.length>=8,c+' has solid framing geometry');
const vietnamese='ÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬĐÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴ';
assert.equal(build(vietnamese).group.userData.letterCount,Array.from(vietnamese).length);
build(vietnamese.toLowerCase());
for(const text of ['Thung Lũng Tình Yêu','Mộng Mơ Dalat','I ♥ Đà Lạt','a\u0306\u0301','o\u031b\u0309'])build(text);
for(const mark of ['\u0302','\u0306','\u031b','\u0301','\u0300','\u0309','\u0303','\u0323'])assert.notEqual(digest(build('A'+mark).group).hash,digest(build('A').group).hash,'separate solid for '+mark);
assert.equal(digest(build('Ố').group).hash,digest(build('O\u0302\u0301').group).hash,'NFD and precomposed glyphs agree');
assert.ok(build('Ố').bounds.max.y>build('Ô').bounds.max.y+.1,'tone mark stacks above circumflex');
assert.ok(build('Ư').bounds.max.x>build('U').bounds.max.x,'horn is separate right-hand solid');
assert.notEqual(digest(build('Đ').group).hash,digest(build('D').group).hash,'D stroke is modeled');
assert.equal(build('A🙂中? B').group.userData.letterCount,2,'unknown glyphs are gaps');
assert.equal(build('').group.userData.letterCount,0);
assert.equal(build('  ?').points.length,0);
const short=build('A'),long=build('LANGBIANG');
assert.ok(long.points.length>short.points.length&&long.bounds.getSize(new THREE.Vector3()).x>short.bounds.getSize(new THREE.Vector3()).x,'letter vertices/envelope grow with text');
const repeated=build('AAAAAA');assert.equal(digest(repeated.group).meshes,1,'same-colour letters merge');
assert.equal(digest(build('ABCABC',{colors:['#ee3333','#33aa55','#3399ee']}).group).meshes,3,'one mesh per colour');
for(const c of ['A','B','D','O','P','R','0','4','6','8','9']){
  const g=build(c).group;
  assert.ok(digest(g).meshes>0,c+' modeled counter glyph');
}
const O=build('O',{height:2});
assert.equal(new THREE.Raycaster(new THREE.Vector3(0,1,10),new THREE.Vector3(0,0,-1)).intersectObject(O.group,true).length,0,'O counter is an actual hole');
for(const font of ['block','rounded'])for(const plinth of ['none','bar','stones']){
  const sign=build('LANGBIANG',{font,plinth,outline:true,arc:40,tilt:5,position:[7,2,-8],rotation:32,terrain:{width:40,profile:[[-20,0],[20,2]],crossSlope:.05}});
  assert.ok(sign.points.every(p=>p.isVector3&&Number.isFinite(p.x)),'world-space framing');
}
assert.ok(build('AAA',{arc:12}).bounds.getSize(new THREE.Vector3()).z>build('AAA').bounds.getSize(new THREE.Vector3()).z,'arc bends layout');
assert.ok(Math.abs(build('LANGBIANG',{tilt:8}).bounds.min.y)<1e-5,'leaning letters rest on datum');
assert.ok(build('Lang').bounds.max.y<=3.1,'lowercase uses smaller cap shapes');
assert.ok(build('AAA',{letterHeights:[1,1.4,1]}).bounds.max.y>build('AAA').bounds.max.y*1.35,'authored individual cap-height rhythm');
assert.throws(()=>build('AAA',{letterHeights:[0]}));
for(const options of [{height:0},{depth:0},{colors:[]},{spacing:-1},{arc:Infinity},{tilt:NaN},{plinthHeight:-1},{font:'serif'},{plinth:'tower'}])assert.throws(()=>build('A',options));

const example=JSON.parse(fs.readFileSync(join(CODE,'kits/examples/garden.place.json'),'utf8'));
assert.ok(example.objects.some(o=>o.type==='garden_letters'&&o.text==='LANGBIANG'));
assert.ok(example.objects.some(o=>o.type==='garden_letters'&&o.text==='Thung Lũng Tình Yêu'));
const out=join(DATA,'out_garden_example');
const result=spawnSync('python3',['-B',join(CODE,'build.py'),join(CODE,'kits/examples/garden.place.json'),out],{encoding:'utf8',cwd:DATA});
assert.equal(result.status,0,result.stdout+result.stderr);
const runtime=await boot(fs.readFileSync(join(out,'index.html'),'utf8'));
assert.equal(runtime.window.__ready,true);
for(const object of example.objects.filter(o=>o.type==='garden_letters'))assert.ok(runtime.modelEnvelopes.get(object.id),'sign has viewer envelope');
console.log('garden letters: alphabet, Vietnamese marks, real counters, gaps, grounding, batching, envelopes and example build/boot PASS');
