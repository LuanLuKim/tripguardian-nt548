import {CODE} from '../paths.mjs';
import {join} from 'node:path';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import * as THREE from '../vendor/node_modules/three/build/three.module.js';

const source=fs.readFileSync(join(CODE, "index.template.html"),'utf8');
const start=source.indexOf('function updatePins(');
const block=source.slice(start,source.indexOf('// === Test hooks ==='));
const loop=block+'\nupdatePins();';
const camera=new THREE.PerspectiveCamera(40,1600/900,.1,100);
camera.position.set(0,0,10);camera.lookAt(0,0,0);camera.updateMatrixWorld();
const xForNdc=x=>x*Math.tan(THREE.MathUtils.degToRad(20))*10*1600/900;
for(const edge of [-1.2,-.98,0,.98,1.2]) {
  const hotspots=Array.from({length:8},(_,i)=>({anchor:[xForNdc(i===7?edge:0),0,0]}));
  const pins=hotspots.map(()=>({style:{}})),leaders=hotspots.map(()=>({style:{},setAttribute(){}}));
  const state={THREE,camera,place:{hotspots},pins,leaders,current:null,innerWidth:1600,innerHeight:900};
  vm.createContext(state);vm.runInContext(loop,state);
  for(const pin of pins) if(pin.style.display!=='none') {
    const x=parseFloat(pin.style.left),y=parseFloat(pin.style.top);
    assert.ok(x>=18&&x<=1582&&y>=18&&y<=882,'visible pin is clipped by the viewport edge');
  }
  if(Math.abs(edge)>1) assert.equal(pins[7].style.display,'none','offscreen subject must not leave a floating pin');
  state.current={};vm.runInContext(loop,state);
  assert.ok(pins.some(p=>p.style.display!=='none'),'tour focus must keep model markers available');
}
const hotspots=Array.from({length:8},(_,i)=>({anchor:[xForNdc((i%3-1)*.012),(Math.floor(i/3)-1)*.03,0]}));
const pins=hotspots.map(()=>({style:{}})),leaders=hotspots.map(()=>({style:{},attributes:{},setAttribute(k,v){this.attributes[k]=v}}));
const state={THREE,camera,place:{hotspots},pins,leaders,current:null,innerWidth:1600,innerHeight:900};
vm.createContext(state);vm.runInContext(loop,state);
for(let i=0;i<pins.length;i++) if(pins[i].style.display!=='none') {
  const x=parseFloat(pins[i].style.left),y=parseFloat(pins[i].style.top),line=leaders[i].attributes;
  assert.ok(Math.hypot(x-line.x1,y-line.y1)<=50,'collision resolution created a long leader');
  assert.ok(Math.hypot(line.x2-line.x1,line.y2-line.y1)<=37,'leader exceeds short stem length');
  for(let j=0;j<i;j++) if(pins[j].style.display!=='none') assert.ok(Math.hypot(x-parseFloat(pins[j].style.left),y-parseFloat(pins[j].style.top))>=31,'colliding pins');
}
console.log('PASS pin margins, offscreen subjects, focused state, collision separation and short leaders');
{
  const hotspots=Array.from({length:8},(_,i)=>({id:String(i),anchor:[0,0,0]}));
  const pins=hotspots.map(()=>({style:{},classList:{toggle(){}}})),leaders=hotspots.map(()=>({style:{},setAttribute(){}}));
  const state={THREE,camera,place:{hotspots},pins,leaders,current:hotspots[6],innerWidth:1600,innerHeight:900};
  vm.createContext(state);vm.runInContext(loop,state);
  assert.equal(pins[6].style.display,'block','current stop must win marker collisions');
  assert.equal(pins[7].style.display,'block','next stop must be second priority');
}
