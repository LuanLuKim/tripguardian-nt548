import {CODE} from '../paths.mjs';
import {join} from 'node:path';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import * as THREE from '../vendor/node_modules/three/build/three.module.js';

const template=fs.readFileSync(join(CODE, "index.template.html"),'utf8');
const primitives=template.split('// === Primitives ===')[1].split('function road(')[0];
const boxes=[],details=[],roofs=[],scene=new THREE.Scene();
const palette={stone:'#e9e4da',stair:'#d9d2c4',wood:'#4a2a20',ochre:'#cfae6a',white:'#f4f1ea',roof:'#582e27',roofEdge:'#42251f',blue:'#3e6e9a',trunk:'#797063',gold:'#bd9862',bed:'#bbc5ad'};
const ctx=new Proxy({}, {get:(o,k)=>o[k]??(()=>{}),set:(o,k,v)=>(o[k]=v,true)});
const state={THREE,palette,scene,vegetationMode:false,
  box:(...a)=>boxes.push(a),cylinder:(...a)=>details.push(['cylinder',...a]),ball:()=>{},
  detail:(...a)=>details.push(a),material:c=>new THREE.MeshStandardMaterial({color:c}),
  mesh:(g,c,x,y,z)=>{const m=new THREE.Mesh(g,new THREE.MeshStandardMaterial({color:c}));m.position.set(x,y,z);scene.add(m);return m;},
  vietnameseRoof:o=>roofs.push(o),document:{createElement:()=>({getContext:()=>ctx})}
};
vm.createContext(state);
vm.runInContext(template.slice(template.indexOf('function contouredBed('),template.indexOf('function slope('))+primitives+'\nglobalThis.api={tower,pavilion,gate,stoneStele,lion:typeof guardianLion==="function"?guardianLion:null};',state);
let failures=0;
function check(name,fn){try{fn();console.log('PASS',name)}catch(e){failures++;console.error('FAIL',name,e.message)}}
check('guardian lion has separate chest, paired paws and projecting muzzle',()=>{
  assert.ok(state.api.lion,'guardianLion primitive missing');
  state.api.lion({position:[0,0,0]});
  for(const key of ['lion-chest','lion-paw','lion-muzzle','lion-mane']) assert.ok(details.some(d=>d[0]===key),key);
  assert.equal(details.filter(d=>d[0]==='lion-paw').length,2);
  assert.ok(!boxes.some(b=>b[6]==='#d7d4bc'),'guardian must not have cartoon teeth');
  const eye=details.find(d=>d[0]==='lion-eye');
  assert.ok(eye[4][0]<=.035&&eye[4][1]<=.025,'eyes must be quiet carved details');
  const muzzle=details.find(d=>d[0]==='lion-muzzle');
  assert.ok(muzzle[4][1]<=.105&&muzzle[4][2]<=.14,'muzzle must not be a bulbous mascot snout');
  const head=details.find(d=>d[0]==='lion-head')[1].attributes.position;
  assert.ok(Array.from({length:head.count},(_,i)=>head.getZ(i)).filter(z=>Math.abs(z-.72)<.001).length>8,'head needs a broad sculpted facial plane');
});
check('stele tower shaft is slender with inset panels and modest caps',()=>{
  boxes.length=details.length=roofs.length=0;state.api.tower({position:[0,0,0],height:9});
  const shaft=boxes.find(b=>b[4]>5&&b[3]<1);
  assert.ok(shaft,'shaft must be under 0.9 m at 9 m overall');
  assert.ok(boxes.some(b=>b[6]==='#ded9bd'&&b[4]>4),'pale inset inscription panel');
  assert.equal(roofs.length,3);
  assert.ok(roofs.every(r=>r.width+2*r.overhang<1.7),'cap width must stay restrained');
});
check('gate piers have capitals and thin roof slabs',()=>{
  boxes.length=roofs.length=0;state.api.gate({position:[0,0,0],width:8,height:6.5});
  assert.ok(boxes.filter(b=>b[6]==='#b5b6ae'&&b[4]>3).length===4,'grey stone masonry piers');
  assert.ok(roofs.every(r=>r.thickness<=.12));
});
check('shrine robe has a scalloped hem and blooms are small petals',()=>{
  details.length=0;state.api.pavilion({position:[0,0,0],size:[6.4,6.3,5.8],statue:true});
  assert.ok(details.some(d=>d[0]==='flower-petal'),'grouped petals missing');
  const robe=scene.children.find(m=>m.name==='draped-robe');
  assert.ok(robe,'named flowing robe');
  const p=robe.geometry.attributes.position;let lo=Infinity,hi=-Infinity;
  for(let i=0;i<p.count;i++)if(p.getY(i)<.1){const r=Math.hypot(p.getX(i),p.getZ(i));lo=Math.min(lo,r);hi=Math.max(hi,r)}
  assert.ok(hi-lo>.06,'flowing hem must not be a perfect lathe circle');
});
check('bell pavilion has brackets, hanger, and furnished lower floor',()=>{
  boxes.length=details.length=0;state.api.pavilion({position:[0,0,0],size:[7,9.5,7],storeys:2});
  assert.ok(details.some(d=>d[0]==='pavilion-bracket'),'bracket layer');
  assert.ok(scene.children.some(m=>m.name==='hanging-bell'),'bell profile');
  assert.ok(boxes.some(b=>b[4]<.3&&b[3]>1&&b[1]>1&&b[1]<2),'lower incense stand');
});
check('all pavilion brackets have positive-determinant instances',()=>{
  details.length=0;state.api.pavilion({position:[0,0,0],size:[7,9.5,7],storeys:2});
  const brackets=details.filter(d=>d[0]==='pavilion-bracket');assert.equal(brackets.length,16);
  assert.ok(brackets.every(d=>d[4][0]*d[4][1]*d[4][2]>0),'reflected instance winding');
});
check('timber posts are slim and lattice does not become a solid beam',()=>{
  boxes.length=0;state.api.gate({position:[0,0,0],width:7,height:5,wood:true});
  assert.ok(boxes.some(b=>b[4]>3&&b[3]<.65&&b[6]===palette.wood),'slim timber posts');
});
check('timber trim triangles face in the direction of their normals',()=>{
  const n=scene.children.length;state.api.gate({position:[0,0,0],width:7,height:5,wood:true});
  const trims=scene.children.slice(n).filter(m=>m.geometry.type==='ExtrudeGeometry');assert.equal(trims.length,5,'two braces, two carved frame layers and crest');
  for(const m of trims) {
    const p=m.geometry.attributes.position,n=m.geometry.attributes.normal;
    for(let i=0;i<p.count;i+=3) {
      const a=new THREE.Vector3().fromBufferAttribute(p,i),b=new THREE.Vector3().fromBufferAttribute(p,i+1),c=new THREE.Vector3().fromBufferAttribute(p,i+2);
      const cross=b.sub(a).cross(c.sub(a));
      if(cross.length()>1e-8) assert.ok(cross.dot(new THREE.Vector3().fromBufferAttribute(n,i))>0,'reflected trim winding');
    }
  }
});
check('stone slab is rounded and naturally asymmetric',()=>{
  const n=scene.children.length;state.api.stoneStele({position:[0,0,0]});
  const slab=scene.children.slice(n).find(m=>m.name==='stone-slab');assert.ok(slab.geometry.parameters.options.bevelSegments>=3);
  assert.ok(scene.children.slice(n).filter(m=>m.name==='natural-rock').length>=3);
});
check('duplicated stone vertices share smooth normals rather than triangular shading',()=>{
  const n=scene.children.length;state.api.stoneStele({position:[0,0,0]});
  const g=scene.children.slice(n).find(m=>m.name==='stone-slab').geometry,p=g.attributes.position,normal=g.attributes.normal,seen=new Map();
  for(let i=0;i<p.count;i++) {
    const key=[p.getX(i),p.getY(i),p.getZ(i)].map(v=>v.toFixed(5)).join(',');
    const v=new THREE.Vector3().fromBufferAttribute(normal,i);
    if(seen.has(key)) assert.ok(seen.get(key).distanceTo(v)<.001,'unwelded stone shading');
    else seen.set(key,v);
  }
});
check('bridge can inspect one signature asset without changing the public hotspot list',()=>{
  const window={},points=[new THREE.Vector3(10,4,2),new THREE.Vector3(14,8,6)];let opened;
  const hookState={THREE,window,place:{hotspots:[{id:'stairs',target:[0,0,0],camera:[10,5,10],subjects:['stair']}]},
    modelEnvelopes:new Map([['lion',points]]),openSpot:s=>opened=s};
  vm.createContext(hookState);
  vm.runInContext(template.slice(template.indexOf('window.__open ='),template.indexOf('window.__close =')),hookState);
  window.__open({id:'stairs',focus:'lion'});
  assert.equal(opened.subjects[0],'lion');assert.deepEqual(Array.from(opened.target),[12,6,4]);
  window.__open('stairs');assert.equal(opened.subjects[0],'stair');
});
check('focused asset keeps original tour id and updates navigation',()=>{
  const hotspots=[{id:'gate'},{id:'stairs'}];let updated=0;
  const s={place:{hotspots},current:null,flight:null,configureInteriorView(){},exteriorDim:{value:1},altarLight:{intensity:0},interiorFill:{intensity:0},hallCutaway:{set(){}},hallRoof:{position:{y:0},updateMatrixWorld(){}},camera:{view:{offsetX:0,offsetY:0},setViewOffset(){}},innerWidth:1600,innerHeight:900,stopRotation(){},frameView(){},setForegroundVisibility(){},moveTo(){},updateTour(){updated++;},fitSpot:()=>({})};vm.createContext(s);
  vm.runInContext(template.slice(template.indexOf('function openSpot('),template.indexOf('function closeSpot('))+'\nglobalThis.open=openSpot;',s);
  s.open({...hotspots[1],subjects:['lion']},true);
  assert.equal(s.current.id,'stairs');assert.equal(updated,1);
});
process.exitCode=failures?1:0;
