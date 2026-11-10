import {CODE} from '../paths.mjs';
import {join} from 'node:path';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import * as THREE from '../vendor/node_modules/three/build/three.module.js';

const template=fs.readFileSync(join(CODE, "index.template.html"),'utf8');
const source=template.split('// === Primitives ===')[1].split('function road(')[0];
const boxes=[],roofs=[],scene=new THREE.Scene();
const palette={stone:'#e9e4da',stair:'#d9d2c4',wood:'#4a2a20',ochre:'#cfae6a',white:'#f4f1ea',roof:'#582e27',roofEdge:'#42251f',green:'#b9c6a5',trunk:'#797063',gold:'#bd9862',bed:'#bbc5ad'};
const state={THREE,palette,scene,vegetationMode:false,
  box:(...args)=>boxes.push(args),cylinder:()=>{},ball:()=>{},detail:()=>{},
  mesh:(geometry,color,x,y,z)=>{const m=new THREE.Mesh(geometry,new THREE.MeshStandardMaterial({color}));m.position.set(x,y,z);scene.add(m);return m},
  vietnameseRoof:o=>roofs.push(o),
  document:{createElement:()=>({width:0,height:0,getContext:()=>({fillRect(){},fillText(){},strokeRect(){},beginPath(){},moveTo(){},lineTo(){},stroke(){}})})}
};
vm.createContext(state);
vm.runInContext(template.slice(template.indexOf('function contouredBed('),template.indexOf('function slope('))+source+'\nglobalThis.api={building,pavilion,gate,stoneStele};',state);
state.api.building({position:[0,7,-23],size:[32,5.2,14],role:'main'});
const columns=boxes.filter(b=>b[6]===palette.wood&&b[3]>=.3&&b[3]<.6&&b[4]>3&&b[5]<.6);
assert.equal(columns.length,10,'main hall needs ten freestanding front columns');
assert.ok(!boxes.some(b=>b[3]===32&&b[4]===5.2&&b[5]===14),'main hall must not be an opaque solid box');
assert.ok(boxes.some(b=>b[6]==='#30221d'),'recessed warm-brown interior');
boxes.length=0;roofs.length=0;
state.api.pavilion({position:[0,0,0],size:[6,6,5],statue:true});
assert.ok(scene.children.some(m=>m.geometry.type==='LatheGeometry'),'shrine has a shaped robe');
assert.equal(boxes.filter(b=>b[6]==='#d9c99f'&&b[4]>4).length,2,'both shrine columns retain plain inset panels');
assert.equal(boxes.filter(b=>b[6]==='#8b785b').length,0,'no repeated pseudo-text on shrine columns');
boxes.length=0;roofs.length=0;
state.api.pavilion({position:[0,0,0],size:[7,9,7],storeys:2});
assert.ok(scene.children.filter(m=>m.geometry.type==='LatheGeometry').length>=2,'hanging bell has a flared lip');
assert.equal(roofs.length,2,'bell pavilion has two coherent roof tiers');
boxes.length=0;roofs.length=0;
state.api.gate({position:[0,0,0],width:8,height:6});
assert.equal(roofs.length,3);
assert.equal(roofs[0].tiers,2);
assert.ok(Math.abs(roofs[1].position[0])>5,'side openings must not overlap the centre columns');
assert.equal(boxes.filter(b=>b[3]>=.8&&b[3]<=1.3&&b[4]>3&&b[5]>=1).length,4,'three gate openings need four columns, not duplicate side columns');
state.api.gate({position:[0,0,0],width:7,height:5,wood:true});
assert.ok(!boxes.some(b=>b[1]===4.2&&b[3]===7&&b[4]>1),'timber beam must not cover fretwork');
const beforeStone=scene.children.length;
state.api.stoneStele({position:[0,0,0]});
const stone=scene.children.slice(beforeStone).find(m=>m.name==='stone-slab');
stone.geometry.computeBoundingBox();
assert.ok(stone.geometry.boundingBox.max.y<2.6&&stone.geometry.boundingBox.max.y>2.2);
assert.ok(scene.children.slice(beforeStone).some(m=>m.isLineSegments),'stele inscription is low-contrast linework');
console.log('Building silhouettes, open colonnade, statue, inscriptions, bell and gate passed.');
