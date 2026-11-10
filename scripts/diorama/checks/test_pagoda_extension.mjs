import {CODE, DATA} from '../paths.mjs';
import {join} from 'node:path';
process.chdir(DATA);
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {boot,THREE} from './pagoda_runtime.mjs';
const template=fs.readFileSync(join(CODE, 'index.template.html'),'utf8');
const inline=data=>template.replace('/*__KITS__*/',fs.readFileSync(join(CODE, 'kits/pagoda.js'),'utf8')).replace('__PLACE__',JSON.stringify(data));
const fixture={name:'Sculpture family',kits:['pagoda'],site:{width:160,depth:160,overviewSubjects:['quan_am','buddha','maitreya','guardian']},hotspots:[],route:[],objects:[
  ...['quan_am','buddha','maitreya','guardian'].map((kind,i)=>({id:kind,type:'pagoda_icon',kind,position:[i*24-36,0,-30],height:i?5:70,baseHeight:1,halo:true})),
  {id:'row',type:'pagoda_statue_row',position:[0,0,30],height:2.5,count:7,spacing:3,rotation:31},
  {id:'gate',type:'pagoda_gate',position:[0,0,0],footprint:[16,3],height:6,walls:{length:9,height:2.4},style:'brick'},
  {id:'stone',type:'pagoda_building',position:[36,0,0],footprint:[22,14],height:5,facade:{style:'stone',roundWindows:[[-7,3.3],[7,3.3]],windowRadius:.6,doorColor:'#4e5149'},wings:[{position:[-15,0],footprint:[8,8],height:3,text:'佛 光',textPosition:[-1.5,1.8],openings:[[2,1.1,2.2]]}],roof:{crest:true}},
  {id:'steps',type:'pagoda_stairs',position:[-30,0,5],width:6,steps:12,rise:.2,run:.45,dragon:{height:.8}},
  {id:'forest',type:'pagoda_landscape',position:[0,0,55],size:[20,12],surface:'needles',density:1,clearings:[[0,0,5,5]]},
  {id:'urn',type:'pagoda_furniture',position:[24,0,30],kind:'incense',standHeight:.6}
]};
const r=await boot(inline(fixture));
for(const id of ['quan_am','buddha','maitreya','guardian']){
  const g=r.scene.getObjectByName(id);assert.ok(g,`${id} sculpture is registered`);
  assert.ok(g.getObjectByName('icon-face'),`${id} has a modelled face`);
  const bb=new THREE.Box3().setFromObject(g),h=fixture.objects.find(o=>o.id===id).height;
  assert.ok(Math.abs(bb.min.y)<.01&&Math.abs(bb.max.y-(h+1))<h*.03,`${id} height includes connected head and crown, excludes base`);
  g.traverse(m=>{if(m.geometry)assert.ok([...m.geometry.attributes.position.array].every(Number.isFinite));});
}
assert.ok(r.scene.getObjectByName('quan_am').getObjectByName('icon-robe-folds'));
assert.ok(r.scene.getObjectByName('quan_am').getObjectByName('icon-raised-hand'));
const robeProfile=[[.151,.065],[.146,.13],[.115,.32],[.095,.52],[.112,.69],[.085,.78],[.031,.81]];
assert.ok(r.scene.getObjectByName('quan_am').getObjectByName('icon-folded-robe').geometry.parameters.segments>=30*10,'robe folds have enough circular samples to avoid triangular fins');
let minimumCreaseClearance=Infinity;
r.scene.getObjectByName('quan_am').getObjectByName('icon-robe-folds').traverse(m=>{
  if(!m.geometry)return;const p=m.geometry.attributes.position;
  for(let i=0;i<p.count;i++){
    const x=p.getX(i),y=p.getY(i),z=p.getZ(i);if(y<.07||y>.68)continue;
    const j=robeProfile.findIndex(q=>q[1]>=y),a=robeProfile[j-1],b=robeProfile[j],t=(y-a[1])/(b[1]-a[1]);
    const radius=a[0]+(b[0]-a[0])*t,angle=Math.atan2(x,z),surface=radius+.009*Math.cos(angle*30+y*2.7)*Math.min(1,radius/.07);
    assert.ok(Math.cos(angle*30+y*2.7)<-.6,'crease follows the twisted valley instead of crossing a ridge');
    minimumCreaseClearance=Math.min(minimumCreaseClearance,Math.hypot(x,z)-surface);
  }
});
assert.ok(minimumCreaseClearance>.0002,`robe creases clear the sculpted surface instead of intersecting it: ${minimumCreaseClearance}`);
const quan=r.scene.getObjectByName('quan_am'),eye=new THREE.Vector3(.022*70,1+.876*70,10).add(new THREE.Vector3(-36,0,-30));
const eyeHit=new THREE.Raycaster(eye,new THREE.Vector3(0,0,-1),0,10).intersectObject(quan,true).find(h=>h.object.isMesh);
assert.equal(eyeHit?.object.parent.name,'icon-face','veil must leave the frontal eye line exposed');
assert.ok(r.scene.getObjectByName('maitreya').getObjectByName('icon-belly'));
assert.ok(r.scene.getObjectByName('guardian').getObjectByName('icon-staff'));
assert.equal(new THREE.Raycaster(new THREE.Vector3(36,2,0),new THREE.Vector3(0,0,-1),0,40).intersectObject(r.scene.getObjectByName('guardian'),true).filter(h=>h.object.isMesh).length,0,'guardian has two separate legs below the armour, not a floor-length cone');
let rowInstances=0;r.scene.getObjectByName('row').traverse(m=>{if(m.isInstancedMesh)rowInstances+=m.count;});
assert.ok(rowInstances>=7,'rows share instanced sculpture geometry');
const rowBounds=new THREE.Box3().setFromObject(r.scene.getObjectByName('row')).expandByScalar(.01);
assert.ok(r.modelEnvelopes.get('row').every(p=>rowBounds.containsPoint(p)),'row framing contains only transformed copies, not the prototype at origin');
const gate=r.scene.getObjectByName('gate');
for(const x of [-5.2,0,5.2])assert.equal(new THREE.Raycaster(new THREE.Vector3(x,1.5,8),new THREE.Vector3(0,0,-1),0,14).intersectObject(gate,true).filter(h=>h.object.isMesh).length,0,'three real gate voids');
assert.ok(gate.getObjectByName('pagoda-gate-walls'));
assert.equal(r.scene.getObjectByName('stone').getObjectByName('pagoda-round-windows').children.length,2);
assert.ok(r.scene.getObjectByName('stone').getObjectByName('pagoda-wing-inscription'));
assert.ok(r.scene.getObjectByName('stone').getObjectByName('pagoda-wing-inscription').material.transparent,'painted characters have no opaque signboard rectangle');
assert.equal(r.scene.getObjectByName('stone').getObjectByName('pagoda-wing-openings')?.children.length,1,'wing door recesses follow JSON');
assert.ok(r.scene.getObjectByName('stone').getObjectByName('pagoda-gold-crest'));
assert.equal(r.scene.getObjectByName('stone').getObjectByName('pagoda-entrance-door').material.color.getHexString(),'4e5149','door color follows JSON independently of red columns');
assert.ok(r.scene.getObjectByName('steps').getObjectByName('pagoda-dragon-balustrades'));
const railBase=r.scene.getObjectByName('steps').getObjectByName('pagoda-dragon-rail-supports');
assert.ok(railBase,'dragon balustrades have separately auditable load-bearing bases');
const railBounds=new THREE.Box3().setFromObject(railBase);
assert.ok(railBounds.min.x>=-33-.001&&railBounds.max.x<=-27+.001,'dragon bases stand on the stair width, not in mid-air outside it');
assert.ok(r.scene.getObjectByName('forest').getObjectByName('pagoda-pine-needles')?.isInstancedMesh);
const shrubs=r.scene.getObjectByName('forest').getObjectByName('pagoda-low-planting'),shrubMatrix=new THREE.Matrix4();
for(let i=0;i<shrubs.count;i++){shrubs.getMatrixAt(i,shrubMatrix);const b=new THREE.Box3().setFromBufferAttribute(shrubs.geometry.attributes.position).applyMatrix4(shrubMatrix);assert.ok(b.max.x<=-2.5||b.min.x>=2.5||b.max.z<=-2.5||b.min.z>=2.5,'whole shrubs stay outside JSON path clearings');}
assert.ok(r.scene.getObjectByName('urn').getObjectByName('pagoda-urn-stand'));
console.log('PASS sculpture silhouettes, dimensions, instancing, gate voids, hall details, forest and stairs');

for(const type of ['pagoda_hall','pagoda_building']){
  const hall={id:'hall',type,position:[14,0,-10],rotation:27,footprint:[18,14],size:[18,5.5,14],height:5.5,facadeTiers:0,sideTurrets:false,facade:{style:'stone'},interior:{kit:'buddhist_altar',floor:.46,ceilingHeight:5.1,statueHeight:2.6,statueSpacing:3,domeRadius:2.1}};
  const data={...fixture,objects:[hall],hotspots:[{id:'outside',cutaway:'hall',anchor:[14,1,2],camera:[20,12,20],target:[14,3,-10]},{id:'inside',building:'hall',interior:true,anchor:[16,1.9,-6],camera:[16,1.9,-6],target:[14,2,-14],photos:[]} ]};
  const s=await boot(inline(data));
  assert.ok(s.scene.getObjectByName('buddhist-altar-interior'));
  assert.equal(s.scene.getObjectByName('buddhist-altar-statues').children.length,3);
  assert.ok(s.scene.getObjectByName('buddhist-painted-dome'));
  assert.ok(new THREE.Box3().setFromObject(s.scene.getObjectByName('buddhist-painted-dome')).getSize(new THREE.Vector3()).y>.3,'painted dome is recessed curved geometry, not a flat decal');
  assert.ok(s.scene.getObjectByName('buddhist-dome-oculus')?.position.y>.15,'inner gold ring follows the raised vault rather than hanging below it');
  const ceiling=s.scene.getObjectByName('buddhist-coffered-ceiling');assert.ok(ceiling);
  assert.ok(s.roofRecords.some(r=>r.objectId==='hall'&&r.group.getObjectByName(ceiling.name)));
  s.window.__open('outside');s.scene.updateMatrixWorld(true);
  const outsideWall=s.scene.getObjectByName('hall').children.find(m=>m.isMesh&&m.material.color.getHexString()==='d1bc87');
  if(type==='pagoda_building')assert.equal(outsideWall.material.opacity,1,'cutaway fades only the dedicated facade, not shared rear or wing materials');
  s.window.__open('inside');s.scene.updateMatrixWorld(true);
  const eye=new THREE.Vector3(0,1.8,2).applyAxisAngle(new THREE.Vector3(0,1,0),27*Math.PI/180).add(new THREE.Vector3(14,0,-10));
  assert.ok(new THREE.Raycaster(eye,new THREE.Vector3(0,1,0)).intersectObject(ceiling,true).some(h=>h.object.isMesh&&h.distance<5),'ceiling itself seals overhead, not an unrelated roof');
}
console.log('PASS shared altar shell fits original and family halls, including rotated ceiling');

const tallData={...fixture,objects:[fixture.objects[0]],site:{width:30,depth:30,overviewSubjects:['quan_am'],overviewHeightFill:1.14,overviewAllAngles:true}};
const tall=await boot(inline(tallData),{width:3840,height:2160});
const tallPoints=tall.modelEnvelopes.get('quan_am').map(p=>p.clone().project(tall.camera));
assert.ok((1-Math.max(...tallPoints.map(p=>p.y)))*1080>=23,'height-bound framing preserves the top screen margin even at 4K');

for(const slug of ['linhan','chuatau']){
  const data=JSON.parse(fs.readFileSync(`places/${slug}/place.json`,'utf8')),s=await boot(inline(data));
  if(slug==='chuatau'){
    const planting=data.objects.filter(o=>o.type==='pagoda_landscape').map(o=>s.scene.getObjectByName(o.id));
    for(const point of [[-2,5,-36],[0,7,-36],[0,10,-36],[2,7,-36]]){
      const direction=new THREE.Vector3(...point).sub(s.camera.position);
      assert.equal(new THREE.Raycaster(s.camera.position,direction.clone().normalize(),0,direction.length()-.2).intersectObjects(planting,true).filter(h=>h.object.isMesh).length,0,'overview shows the Buddha rather than a foreground pine crown');
    }
  }
  if(slug==='linhan'){
    const statue=s.scene.getObjectByName('quan-am'),robe=statue.getObjectByName('icon-folded-robe');
    assert.ok(robe.geometry.parameters.segments>=36*10,'actual giant statue resolves its 36 folds smoothly');
    const localRobe=new THREE.Mesh(robe.geometry,new THREE.MeshBasicMaterial({side:THREE.DoubleSide}));localRobe.updateMatrixWorld();
    statue.getObjectByName('icon-robe-folds').traverse(m=>{
      if(!m.geometry)return;const p=m.geometry.attributes.position,stride=Math.max(1,Math.floor(p.count/256));
      for(let i=0;i<p.count;i+=stride){
        const x=p.getX(i),y=p.getY(i),z=p.getZ(i),radius=Math.hypot(x,z);if(y<.07||y>.68)continue;
        const hit=new THREE.Raycaster(new THREE.Vector3(0,y,0),new THREE.Vector3(x/radius,0,z/radius),0,1).intersectObject(localRobe)[0];
        assert.ok(hit&&radius-hit.distance>.00015,'36-fold giant crease stays outside the actual triangulated robe, not only an analytic surface');
      }
    });
    const points=data.site.overviewSubjects.flatMap(id=>s.modelEnvelopes.get(id)||[]).map(p=>p.clone().project(s.camera));
    const fill=(Math.max(...points.map(p=>p.x))-Math.min(...points.map(p=>p.x)))*800/1520;
    assert.ok(fill>=.77&&fill<=.83,`giant statue and site occupy about 80% of free width: ${fill}`);
  }
  for(const h of data.hotspots){s.window.__open(h.id);assert.ok(s.camera.position.toArray().every(Number.isFinite),`${slug}/${h.id} opens with a finite fitted camera`);if(slug==='chuatau'&&h.id==='statue'){
    const reference=structuredClone(data);delete reference.hotspots.find(p=>p.id==='statue').walk;
    const noRoute=await boot(inline(reference));noRoute.window.__open('statue');
    assert.ok(s.camera.position.distanceTo(noRoute.camera.position)<1e-6,'opt-out statue framing matches the subject-only camera exactly');
    assert.ok(s.camera.position.z<0,'statue view stays between the hall and the hill rather than backing into the hall');
  }}
  for(const [width,height] of [[1600,900],[3840,2160]]){
    const viewport=await boot(inline(data),{width,height});
    const projected=data.site.overviewSubjects.flatMap(id=>viewport.modelEnvelopes.get(id)||[]).map(p=>p.clone().project(viewport.camera));
    const top=(1-Math.max(...projected.map(p=>p.y)))*height/2,bottom=(1-Math.min(...projected.map(p=>p.y)))*height/2;
    assert.ok(top>=23&&bottom<=height-23,`${slug} has safe screen margins at ${width}x${height}: ${top},${bottom}`);
  }
  const platform=data.objects.find(o=>o.id==='gate-platform'),gate=data.objects.find(o=>o.id==='brick-gate');
  if(gate)assert.ok(platform.width>=gate.footprint[0]+2*gate.walls.length,'elevated gate walls have ground support across their complete width');
  const inside=(x,z)=>{let yes=false;const a=data.site.outline;for(let i=0,j=a.length-1;i<a.length;j=i++){const [ax,az]=a[i],[bx,bz]=a[j];if((az>z)!==(bz>z)&&x<(bx-ax)*(z-az)/(bz-az)+ax)yes=!yes;}return yes;};
  for(const o of data.objects.filter(o=>o.type==='pagoda_landscape')){
    const [w,d]=o.size,points=o.shape==='ellipse'?Array.from({length:64},(_,i)=>[Math.sin(i*Math.PI/32)*w*.499,Math.cos(i*Math.PI/32)*d*.499]):[[-w*.499,-d*.499],[-w*.499,d*.499],[w*.499,-d*.499],[w*.499,d*.499]];
    assert.ok(points.every(([x,z])=>inside(x+o.position[0],z+o.position[2])),`${slug}/${o.id} ground patch stays on its plinth`);
  }
}
console.log('PASS target stops open and elevated walls have continuous support');
