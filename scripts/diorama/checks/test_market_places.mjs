import {CODE, DATA} from '../paths.mjs';
import {join} from 'node:path';
process.chdir(DATA);
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {spawnSync} from 'node:child_process';
import * as THREE from '../vendor/node_modules/three/build/three.module.js';
import {mergeGeometries} from '../vendor/node_modules/three/examples/jsm/utils/BufferGeometryUtils.js';

// Reuse the exact node build/boot harness required before every bridge shot.
const checker=fs.readFileSync(join(CODE,'check_place.mjs'),'utf8');
const boot=eval('('+checker.slice(checker.indexOf('async function boot('),checker.indexOf('\nconst slug=')).replace('hillSurfaceHeight,roundWalkingPath','hillSurfaceHeight,buildInteriorFlightPath,roundWalkingPath')+')');
function contains(poly,x,z){let hit=false;for(let i=0,j=poly.length-1;i<poly.length;j=i++){const a=poly[i],b=poly[j];if((a[1]>z)!==(b[1]>z)&&x<(b[0]-a[0])*(z-a[1])/(b[1]-a[1])+a[0])hit=!hit;}return hit;}
for(const slug of ['chomoi','namthien']){
  const data=JSON.parse(fs.readFileSync(`places/${slug}/place.json`)),r=await boot(`places/${slug}/place.json`,`out_${slug}/contract-build`);
  let meshes=0,instances=0;r.scene.traverse(m=>{if(m.isMesh){meshes++;if(m.isInstancedMesh)instances+=m.count;for(const v of m.geometry.attributes.position.array)assert.ok(Number.isFinite(v),'finite '+slug);}});
  assert.ok(meshes<500,'mesh budget '+slug+': '+meshes);assert.ok(instances>800,'dense instanced detail '+slug);
  const area=r.window.__inspect().freeArea,points=data.objects.filter(o=>!['market_paving','market_street'].includes(o.type)).flatMap(o=>r.modelEnvelopes.get(o.id)||[]).map(p=>p.clone().project(r.camera));
  const fill=(Math.max(...points.map(p=>p.x))-Math.min(...points.map(p=>p.x)))*800/area.width;
  assert.ok(fill>.76&&fill<.94,'tight overview '+slug+': '+fill);
  const outside=data.hotspots.filter(s=>s.walk);assert.equal(data.route.length,outside.length-1,'one route leg per outside stop');
  for(const s of data.hotspots){assert.ok(s.photos.length,'evidence '+slug+'/'+s.id);assert.ok(s.caption.length<100);for(const photo of s.photos)assert.ok(fs.existsSync(`places/${slug}/photos/${photo}`));for(const id of s.subjects||[])assert.ok(r.modelEnvelopes.has(id),'subject id is object id, not mesh name');}
  const ray=new THREE.Raycaster(new THREE.Vector3(),new THREE.Vector3(0,-1,0));let samples=0;
  for(const [i,leg] of data.route.entries()){
    assert.deepEqual(leg[0],outside[i].walk);assert.deepEqual(leg.at(-1),outside[i+1].walk);
    for(const path of [leg,r.roundWalkingPath(leg)])for(let k=1;k<path.length;k++){
      const a=new THREE.Vector2(...path[k-1]),b=new THREE.Vector2(...path[k]),n=b.clone().sub(a).normalize();
      for(let t=0;t<=1;t+=.07)for(const offset of [-.8,0,.8]){
        const p=a.clone().lerp(b,t).add(new THREE.Vector2(-n.y,n.x).multiplyScalar(offset));ray.ray.origin.set(p.x,100,p.y);assert.ok(ray.intersectObject(r.walkableMesh).length,'paved arrow '+slug);
        for(const o of data.objects){const angle=(o.rotation||0)*Math.PI/180,dx=p.x-o.position[0],dz=p.y-o.position[2],x=dx*Math.cos(angle)-dz*Math.sin(angle),z=dx*Math.sin(angle)+dz*Math.cos(angle);let blocked=false;
          if(o.type==='market_building')blocked=contains(o.footprint,x,z);
          if(o.type==='market_umbrella')blocked=Math.hypot(x,z)<o.radius+.04;
          if(['market_shed','market_planting','market_goods'].includes(o.type))blocked=Math.abs(x)<o.size[0]/2+.08&&Math.abs(z)<o.size[1]/2+.08;
          if(o.type==='market_shophouses'){const width=o.houses.reduce((s,h)=>s+h.width,0)+o.gap*(o.houses.length-1);blocked=Math.abs(x)<width/2&&z> -o.size[1]/2&&z<o.size[1]/2+(o.awning?.depth??1.1);}
          if(o.type==='market_street')for(const [bx,bz,yaw=0] of o.motorbikes??[]){const a=yaw*Math.PI/180,xx=(x-bx)*Math.cos(a)-(z-bz)*Math.sin(a),zz=(x-bx)*Math.sin(a)+(z-bz)*Math.cos(a);if(Math.abs(xx)<.4&&Math.abs(zz)<.85)blocked=true;}
          assert.ok(!blocked,`clear arrow ${slug}/${o.id} at ${p.toArray()}`);
        }samples++;
      }
    }
  }
  if(slug==='chomoi'){
    const hall=data.objects.find(o=>o.id==='hall'),record=r.roofRecords.find(v=>v.objectId==='hall'),base=record.group.position.y;
    r.window.__open('stairs');assert.equal(record.group.position.y,base+hall.cutaway.lift,'outside opens upper floors');
    r.window.__open('inside');assert.equal(record.group.position.y,base,'inside restores sealed ceiling');
    const ceiling=r.scene.getObjectByName('market-sealed-ceiling');assert.ok(ceiling);
    for(const yaw of [-4,0,4]){const eye=new THREE.Vector3(...data.hotspots.find(s=>s.id==='inside').camera),direction=new THREE.Vector3(Math.sin(yaw*Math.PI/180),.5,-Math.cos(yaw*Math.PI/180)).normalize();assert.ok(new THREE.Raycaster(eye,direction).intersectObject(ceiling,true).length,'no sky in inside yaw '+yaw);}
    const osm=JSON.parse(fs.readFileSync('places/chomoi/osm_footprints.json')),raw=osm.buildings.find(b=>b.osm_id===osm.main).poly_m.slice(0,-1),angle=-54*Math.PI/180;
    for(const [i,[x,north]] of raw.entries())assert.ok(Math.hypot(hall.footprint[i][0]-(x*Math.cos(angle)+north*Math.sin(angle)),hall.footprint[i][1]-(x*Math.sin(angle)-north*Math.cos(angle)))<.012,'exact rigid OSM transform');
  }else assert.equal(data.hotspots.some(s=>s.interior),false,'excluded neighbouring interiors are not invented');
  console.log(JSON.stringify({slug,meshes,instances,overviewWidth:fill,routeSamples:samples,status:'PASS'}));
}
const defaults=await boot('market_checks/default-interior.place.json','market_checks/default-interior-build');
for(const name of ['altar-warm-light','interior-fill-light'])assert.ok(defaults.scene.getObjectByName(name).position.toArray().every(Number.isFinite),'default market light integrates with viewer');
for(const entering of [true,false])for(const point of defaults.buildInteriorFlightPath(new THREE.Vector3(20,15,20),new THREE.Vector3(3,1.78,1),entering,defaults.place))assert.ok(point.toArray().every(Number.isFinite),'default market flight integrates with viewer');
const defaultShell=defaults.scene.getObjectByName('hall-market'),start=defaultShell.localToWorld(new THREE.Vector3(0,10,-20)),end=defaultShell.localToWorld(new THREE.Vector3(1,1.78,0));
for(const [from,to,entering] of [[start,end,true],[end,start,false]]){
  const path=defaults.buildInteriorFlightPath(from,to,entering,defaults.place);
  for(let i=1;i<path.length;i++){const distance=path[i-1].distanceTo(path[i]),direction=path[i].clone().sub(path[i-1]).normalize();assert.equal(new THREE.Raycaster(path[i-1],direction,.01,distance-.01).intersectObject(defaultShell,true).filter(hit=>hit.object.isMesh).length,0,'default entry/exit flight clears tower and passes through its doorway');}
}
console.log('PASS market interior viewer defaults: rotated offset room, lights and entry/exit flight');
const example=await boot(join(CODE,'kits/examples/market.place.json'),'market_checks/example-build');
for(const suffix of ['building','entrance','shophouses','umbrella','shed','goods','street'])assert.ok(example.place.objects.some(o=>o.type==='market_'+suffix),'example exercises extension '+suffix);
assert.ok(example.scene.getObjectByName('market-sealed-ceiling'),'example actually builds the interior, not only its unused JSON');
example.window.__open('cutaway');example.window.__open('inside');assert.equal(example.window.__inspect().insideView,true);
console.log('PASS market example: all seven extension types and active cutaway/interior build and boot');
