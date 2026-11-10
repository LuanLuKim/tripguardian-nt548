import {CODE, DATA} from '../paths.mjs';
import {join} from 'node:path';
process.chdir(DATA);
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {spawnSync} from 'node:child_process';
import {boot,digest,THREE,mergeGeometries} from './pagoda_runtime.mjs';
const template=fs.readFileSync(join(CODE, 'index.template.html'),'utf8');
const kit=fs.readFileSync(join(CODE, 'kits/pagoda.js'),'utf8');
function inline(data){return template.replace('/*__KITS__*/',kit).replace('__PLACE__',JSON.stringify(data));}
const fixture={name:'Parametric fixture',kits:['pagoda'],site:{width:120,depth:120},hotspots:[],route:[],objects:[
  {id:'hall',type:'pagoda_building',position:[16,0,-14],rotation:37,footprint:[16,10],height:5,openingStyle:'arched',lintelRise:.35,lanterns:{count:4,height:.45,width:.2},roof:{tiers:2,rise:1.8,soffit:true},colors:{wall:'#cbbb99',roof:'#8d796a',wood:'#66544a',trim:'#b6ac90',stone:'#b6b3a4'}},
  {id:'gate',type:'pagoda_building',form:'gate',position:[0,0,26],footprint:[10,3],height:4,sign:'CỔNG THIỀN',roof:{tiers:2}},
  {id:'bell',type:'pagoda_building',form:'pavilion',position:[-20,0,-5],footprint:[5,5],height:4,bell:{height:1.6,radius:.55},roof:{tiers:2}},
  {id:'tower',type:'pagoda_building',form:'tower',position:[-30,0,-30],footprint:[6,6],height:3,levels:3,storeyHeight:5.9,taper:.86},
  {id:'stupa',type:'pagoda_stupa',position:[30,0,28],radius:2,height:8,kind:'dome'},
  {id:'statue',type:'pagoda_statue',position:[-30,0,28],height:3.2,pose:'standing',halo:true},
  {id:'steps',type:'pagoda_stairs',position:[0,0,35],width:6,steps:5,rise:.15,run:.35,rail:true},
  {id:'path',type:'pagoda_path',position:[0,0,0],points:[[-10,15],[0,15],[10,20]],width:3.4},
  {id:'garden',type:'pagoda_landscape',position:[24,0,0],size:[12,8],shape:'ellipse',density:.7,flowers:.3,trees:[[0,0,8]]},
  {id:'pond',type:'pagoda_water',position:[-24,0,12],size:[10,6],shape:'ellipse',stones:14},
  {id:'incense',type:'pagoda_furniture',kind:'incense',position:[0,0,10],size:[1.8,1.6,1.4]},
  {id:'bench',type:'pagoda_furniture',kind:'bench',position:[8,0,24],size:[2,.9,.65]}
]};
const f=await boot(inline(fixture));
for(const o of fixture.objects){assert.ok(f.scene.getObjectByName(o.id),`${o.type} registered and built`);}
assert.equal(f.roofRecords.filter(r=>r.objectId==='tower').length,3,'one roof per tower level');
assert.equal(f.roofRecords.filter(r=>r.objectId==='hall').length,2,'double eaves are independent roof records');
assert.ok(f.scene.getObjectByName('pagoda-bell'),'bell pavilion carries a suspended bell');
assert.ok(f.scene.getObjectByName('pagoda-foam-crowns')?.isInstancedMesh,'foam trees instanced');
assert.ok(f.scene.getObjectByName('pagoda-low-planting')?.isInstancedMesh,'ground planting instanced');
assert.ok(f.scene.getObjectByName('hall').getObjectByName('pagoda-carved-lintel'),'arched hall opening has shallow carved lintel');
assert.equal(f.scene.getObjectByName('pagoda-hanging-lanterns')?.children.length,4,'lantern count follows JSON');
assert.ok(f.roofRecords.filter(r=>r.objectId==='hall').every(r=>r.group.getObjectByName('pagoda-timber-soffit')),'optional soffit belongs to every moving roof tier');
for(const id of ['hall','gate','bell','tower']){
  const o=fixture.objects.find(o=>o.id===id),g=f.scene.getObjectByName(id);
  const b=new THREE.Box3().setFromObject(g);assert.ok(b.min.y>=-.01&&b.min.y<=.11,`${id} grounded`);
  assert.ok(f.modelEnvelopes.get(id).every(p=>b.clone().expandByScalar(.15).containsPoint(p)),`${id} framing uses actual transformed geometry`);
}
// The gate openings must be real voids, including after rotation/translation.
const gate=f.scene.getObjectByName('gate');
const signBounds=new THREE.Box3().setFromObject(gate.getObjectByName('pagoda-hall-sign'));
assert.ok(signBounds.max.y<4&&signBounds.min.y>4*.86,'gate nameplate clears eave and central arch');
const signCenter=signBounds.getCenter(new THREE.Vector3()),signEye=new THREE.Vector3(0,12,50);
assert.equal(new THREE.Raycaster(signEye,signCenter.clone().sub(signEye).normalize()).intersectObject(gate,true).find(h=>h.object.isMesh)?.object.name,'pagoda-hall-sign','raised gate view sees nameplate, not the lower roof');
for(const x of [-3.25,0,3.25])assert.equal(new THREE.Raycaster(new THREE.Vector3(x,1.5,31),new THREE.Vector3(0,0,-1),0,10).intersectObject(gate,true).length,0,'gate passage unobstructed');
const rawPave=new THREE.Mesh(mergeGeometries(f.walkableGeometries),new THREE.MeshBasicMaterial({side:THREE.DoubleSide}));rawPave.updateMatrixWorld();
assert.ok(new THREE.Raycaster(new THREE.Vector3(0,5,15),new THREE.Vector3(0,-1,0)).intersectObject(rawPave).length,'path registers a walkable surface');
console.log('PASS parametric pagoda family fixture');

// Catalogue defaults must be connected and safe without place-specific overrides.
const defaults=await boot(inline({...fixture,objects:[
  {id:'dome',type:'pagoda_stupa',position:[0,0,0]},
  {id:'seated',type:'pagoda_statue',position:[14,0,0]},
  {id:'default-tower',type:'pagoda_building',form:'tower',position:[-20,0,0]},
  {id:'dense-bed',type:'pagoda_landscape',position:[0,0,20],size:[10,8],density:1},
  {id:'oval-bed',type:'pagoda_landscape',position:[20,0,20],size:[10,8],shape:'ellipse',density:1}
]}));
for(const [id,x,y] of [['dome',0,7*.68],['seated',14,.4+3*.535]]){
  const ray=new THREE.Raycaster(new THREE.Vector3(x,y,5),new THREE.Vector3(0,0,-1),0,10);
  assert.ok(ray.intersectObject(defaults.scene.getObjectByName(id),true).length,`${id} has no disconnected vertical air gap`);
}
const tower=defaults.scene.getObjectByName('default-tower'),levels=tower.children.filter(g=>g.isGroup&&!g.name);
const lowerRoof=defaults.roofRecords.find(r=>r.objectId==='default-tower').group;
assert.ok(levels[1].position.y>=new THREE.Box3().setFromObject(lowerRoof).max.y,'default tower floors clear preceding roof');
const coreBox=new THREE.Box3().setFromObject(tower.getObjectByName('pagoda-tower-core'));
assert.ok(Math.max(Math.abs(coreBox.min.z),Math.abs(coreBox.max.z))<=9*.88**2/2,'default core stays inside smallest tapered floor');
for(let k=1;k<levels.length;k++){
  const below=new THREE.Box3().setFromObject(levels[k-1]),above=new THREE.Box3().setFromObject(levels[k]),y=(below.max.y+above.min.y)/2;
  assert.ok(new THREE.Raycaster(new THREE.Vector3(-20,y,-20),new THREE.Vector3(0,0,1),0,40).intersectObject(tower,true).some(h=>h.object.isMesh),'tower has continuous support between floors, not floating tiers');
}
for(const id of ['dense-bed','oval-bed']){
  const garden=defaults.scene.getObjectByName(id),shrubs=garden.getObjectByName('pagoda-low-planting'),geo=shrubs.geometry;
  assert.ok((geo.index?.count??geo.attributes.position.count)/3<=240,'lightweight foam shrubs stay below 240 triangles');
  const matrix=new THREE.Matrix4(),p=new THREE.Vector3();
  for(let k=0;k<shrubs.count;k++){
    shrubs.getMatrixAt(k,matrix);
    for(let i=0;i<geo.attributes.position.count;i++){
      p.fromBufferAttribute(geo.attributes.position,i).applyMatrix4(matrix);
      assert.ok(id==='oval-bed'?(p.x/5)**2+(p.z/4)**2<=1.001:Math.abs(p.x)<=5.001&&Math.abs(p.z)<=4.001,'entire shrub stays inside planting patch');
    }
  }
}
console.log('PASS connected catalogue defaults and bounded lightweight planting');

assert.ok(fs.existsSync('places/truclam/place.json'),'Truc Lam data exists');
const data=JSON.parse(fs.readFileSync('places/truclam/place.json','utf8'));
const build=(src,out)=>{const r=spawnSync('python3',['-B',join(CODE, 'build.py'),src,out],{encoding:'utf8'});assert.equal(r.status,0,r.stdout+r.stderr);return fs.readFileSync(out+'/index.html','utf8');};
const r=await boot(build('places/truclam/place.json','pagoda_checks/truclam_test'));
assert.equal(data.tourTitle,'Một vòng Thiền Viện Trúc lâm Đà Lạt');
assert.ok(data.hotspots.length>=5&&data.hotspots.length<=7);
assert.ok(!data.hotspots.some(h=>h.interior||h.cutaway),'two interior photos are below the four-photo threshold');
const main=data.objects.find(o=>o.role==='main');
const osm=JSON.parse(fs.readFileSync('places/truclam/osm_footprints.json','utf8'));
assert.equal(main.osm,osm.main);
const p=osm.buildings.find(b=>b.osm_id===osm.main).poly_m.slice(0,-1).map(([x,y])=>new THREE.Vector3(x-main.position[0],0,-y-main.position[2]).applyAxisAngle(new THREE.Vector3(0,1,0),-main.rotation*Math.PI/180));
const b=new THREE.Box3().setFromPoints(p);
assert.ok(Math.abs(b.min.x+main.footprint[0]/2)<.08&&Math.abs(b.max.x-main.footprint[0]/2)<.08,'main hall width and centre follow OSM');
assert.ok(Math.abs(b.min.z+main.footprint[1]/2)<.08&&Math.abs(b.max.z-main.footprint[1]/2)<.08,'main hall depth and orientation follow OSM');
const scenePoints=data.objects.flatMap(o=>r.modelEnvelopes.get(o.id)||[]).map(p=>p.clone().project(r.camera));
const fill=(Math.max(...scenePoints.map(p=>p.x))-Math.min(...scenePoints.map(p=>p.x)))*1600/2/1520;
assert.ok(fill>=.77&&fill<=.83,`subject fills about 80% of free width: ${fill}`);
for(const [x,z] of data.site.outline){const p=new THREE.Vector3(x,-1.2,z).project(r.camera),sx=800+p.x*800,sy=450-p.y*450;assert.ok(sx>=10&&sx<=1590&&sy>=125&&sy<=780,`plinth avoids viewport edge and tour bar: ${sx},${sy}`);}
let meshes=0,instances=0;
for(const o of data.objects){
  const g=r.scene.getObjectByName(o.id);assert.ok(g,`${o.id} built`);
  const bb=new THREE.Box3().setFromObject(g);assert.ok(bb.min.y>=-.02&&bb.min.y<=.12,`${o.id} grounded: ${bb.min.y}`);
  g.traverse(m=>{if(m.isMesh){meshes++;if(m.isInstancedMesh)instances+=m.count;assert.ok([...m.geometry.attributes.position.array].every(Number.isFinite),`${o.id} finite`);}});
}
assert.ok(meshes<240,'batched meshes, not one mesh per repeated detail');assert.ok(instances>200,'dense planting is instanced');
const paving=new THREE.Mesh(mergeGeometries(r.walkableGeometries),new THREE.MeshBasicMaterial({side:THREE.DoubleSide}));paving.updateMatrixWorld();
assert.equal(data.route.length,data.hotspots.length-1);
for(let i=0;i<data.route.length;i++){
  assert.deepEqual(data.route[i][0],data.hotspots[i].walk);assert.deepEqual(data.route[i].at(-1),data.hotspots[i+1].walk);
}
for(const leg of r.routeSegments)for(let i=0;i<leg.samples.length;i++){
  const p=leg.samples[i].point,dir=leg.samples[Math.min(i+1,leg.samples.length-1)].point.clone().sub(leg.samples[Math.max(0,i-1)].point).setY(0).normalize(),n=new THREE.Vector3(-dir.z,0,dir.x);
  for(const sign of [-1,0,1]){
    const e=p.clone().addScaledVector(n,sign*.7);
    assert.ok(new THREE.Raycaster(new THREE.Vector3(e.x,30,e.z),new THREE.Vector3(0,-1,0)).intersectObject(paving).length,`route strip paved ${e.x},${e.z}`);
    for(const o of data.objects.filter(o=>o.type==='pagoda_building')){
      const q=e.clone().sub(new THREE.Vector3(...o.position)).applyAxisAngle(new THREE.Vector3(0,1,0),-o.rotation*Math.PI/180);
      if(o.form==='gate')continue;
      assert.ok(Math.abs(q.x)>o.footprint[0]/2+.7||Math.abs(q.z)>o.footprint[1]/2+.7,`route clear of ${o.id}`);
    }
    for(const o of data.objects.filter(o=>o.type==='pagoda_landscape')){
      const q=e.clone().sub(new THREE.Vector3(...o.position)).applyAxisAngle(new THREE.Vector3(0,1,0),-o.rotation*Math.PI/180);
      assert.ok(Math.abs(q.x)>o.size[0]/2+.05||Math.abs(q.z)>o.size[1]/2+.05,`route strip clear of planted patch ${o.id}: ${q.x},${q.z}`);
    }
  }
}
for(const h of data.hotspots){assert.ok(h.caption.length<100&&h.photos.length);for(const p of h.photos){assert.ok(!['g05.jpg','g20.jpg'].includes(p),'excluded evidence never used');assert.ok(fs.existsSync('places/truclam/photos/'+p));}}
for(const h of data.hotspots.filter(h=>h.subjects?.length===1)){
  r.window.__open(h.id);const anchor=new THREE.Vector3(...h.anchor),direction=anchor.clone().sub(r.camera.position);
  const planting=data.objects.filter(o=>o.type==='pagoda_landscape').map(o=>r.scene.getObjectByName(o.id));
  assert.equal(new THREE.Raycaster(r.camera.position,direction.clone().normalize(),0,direction.length()-.15).intersectObjects(planting,true).length,0,`${h.id}: signature anchor not hidden by foreground planting`);
}
const example=await boot(build(join(CODE,'kits/examples/pagoda.place.json'),'pagoda_checks/example_test'));
assert.ok(example.scene.getObjectByName('example-hall'),'catalogue example builds and boots');
const exampleData=JSON.parse(fs.readFileSync(join(CODE, 'kits/examples/pagoda.place.json'),'utf8'));
for(const type of ['pagoda_building','pagoda_path','pagoda_landscape','pagoda_stairs','pagoda_stupa','pagoda_statue','pagoda_water','pagoda_furniture','pagoda_court'])assert.ok(exampleData.objects.some(o=>o.type===type),`catalogue uses ${type}`);
const legacy=JSON.parse(fs.readFileSync('places/linhphuoc/place.json','utf8'));
const before=await boot(fs.readFileSync('out_linhphuoc/index.html','utf8'));
const after=await boot(inline(legacy));
assert.deepEqual(digest(after.scene),digest(before.scene),'Linh Phuoc complete scene geometry remains byte-identical');
console.log('PASS Truc Lam OSM, grounding, paved route, stops, batching, example, Linh Phuoc compatibility',JSON.stringify({meshes,instances,legacy:digest(after.scene)}));
