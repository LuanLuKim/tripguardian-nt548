import {CODE, DATA} from '../paths.mjs';
import {join} from 'node:path';
process.chdir(DATA);
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createHash} from 'node:crypto';
import {boot,THREE} from './pagoda_runtime.mjs';

const data=JSON.parse(fs.readFileSync('places/linhphuoc/place.json'));
for(const key of ['wallMaterialColor','columnColor','columnReliefColor','beamColor','haloMaterialColor'])delete data.objects.find(o=>o.interior).interior[key];
const template=fs.readFileSync(join(CODE, 'index.template.html'),'utf8');
const inline=d=>template.replace('/*__KITS__*/',fs.readFileSync(join(CODE, 'kits/pagoda.js'),'utf8')).replace('__PLACE__',JSON.stringify(d));
const baseline=await boot(inline(data));
Object.assign(data.objects.find(o=>o.interior).interior,{
  wallMaterialColor:'#29221d',columnColor:'#302821',columnReliefColor:'#655740',
  beamColor:'#302821',haloMaterialColor:'#c3ad65'
});
const changed=await boot(inline(data));
const interior=changed.scene.getObjectByName('quan-am-interior');
const materials=[];interior.traverse(m=>{if(m.material)materials.push(m.material);});
assert.ok(materials.every(m=>!m.userData.ceramic),'overridden interior does not reuse the exterior ceramic shader');
assert.ok(materials.some(m=>m.color?.getHexString()==='29221d'&&!m.userData.ceramic),'interior has plain dark lacquer walls');
assert.ok(materials.some(m=>m.color?.getHexString()==='302821'),'interior columns use independent dark wood');
assert.ok(materials.some(m=>m.color?.getHexString()==='655740'),'column relief uses independent subdued bronze');
assert.ok(materials.some(m=>m.color?.getHexString()==='c3ad65'&&!m.userData.ceramic),'halo has warm gold without exterior mosaic');
const ceiling=changed.scene.getObjectByName('quan-am-ceiling');
assert.ok(ceiling.children.some(m=>m.material?.color?.getHexString()==='302821'),'ceiling beams use independent wood');
function geometry(scene){
  const points=[],p=new THREE.Vector3(),instance=new THREE.Matrix4();
  for(const name of ['quan-am-interior','quan-am-ceiling'])scene.getObjectByName(name).traverse(m=>{
    if(!m.geometry)return;
    const positions=m.geometry.attributes.position;
    for(let k=0;k<(m.isInstancedMesh?m.count:1);k++){
      if(m.isInstancedMesh)m.getMatrixAt(k,instance);
      for(let i=0;i<positions.count;i++){
        p.fromBufferAttribute(positions,i);if(m.isInstancedMesh)p.applyMatrix4(instance);p.applyMatrix4(m.matrixWorld);
        points.push(p.toArray().map(v=>v.toFixed(4)).join(','));
      }
    }
  });return createHash('sha256').update(points.sort().join(';')).digest('hex');
}
assert.equal(geometry(changed.scene),geometry(baseline.scene),'material overrides preserve all geometry and transforms');
console.log('PASS independent lacquer, column, beam and halo colours; geometry unchanged');
