// Fast boot check of one place, no browser: build + run the viewer module in node, print the full error if it throws.
// Usage: node check_place.mjs <slug>   (run before bridge/shot.py; a crash here would leave the render blank)
import assert from 'node:assert/strict';
import {CODE, DATA} from './paths.mjs';
import {join} from 'node:path';
import fs from 'node:fs';
import vm from 'node:vm';
import {spawnSync} from 'node:child_process';
import * as THREE from './vendor/node_modules/three/build/three.module.js';
import {mergeGeometries} from './vendor/node_modules/three/examples/jsm/utils/BufferGeometryUtils.js';

async function boot(source,out){
  const build=spawnSync('python3',['-B',join(CODE,'build.py'),source,out],{encoding:'utf8'});
  assert.equal(build.status,0,build.stdout+build.stderr);
  const html=fs.readFileSync(out+'/index.html','utf8');
  const canvas=new Proxy({measureText:t=>({width:t.length*24}),createImageData:(w,h)=>({data:new Uint8ClampedArray(w*h*4)})},{get:(t,k)=>t[k]??(()=>{})});
  const elements=new Map(),frames=[];
  const element=()=>({style:{setProperty(){}},dataset:{},classList:{add(){},toggle(){}},appendChild(){},setAttribute(){},addEventListener(){},querySelector:()=>element(),getContext:()=>canvas});
  const document={body:element(),createElement:element,createElementNS:element,getElementById:id=>{if(!elements.has(id))elements.set(id,element());return elements.get(id);}};
  class Renderer{constructor(){this.domElement=element();this.shadowMap={};this.info={render:{},reset(){}};}setPixelRatio(){}setSize(){}getContext(){return {finish(){}};}}
  class PMREM{fromScene(){return {texture:null};}dispose(){}}
  class Controls{constructor(c){this.camera=c;this.target=new THREE.Vector3();}update(){this.camera.lookAt(this.target);this.camera.updateMatrixWorld();}addEventListener(){}}
  class Pass{constructor(){this.overrideVisibility=()=>{};}addPass(){}setSize(){}updateGtaoMaterial(){}render(){}}
  const window={matchMedia:()=>({matches:false}),addEventListener(){}};
  const state={document,window,innerWidth:1600,innerHeight:900,devicePixelRatio:1,console:{info(){}},performance:{now:()=>0},requestAnimationFrame:f=>frames.push(f),
    loadModule:async n=>n==='three'?{...THREE,WebGLRenderer:Renderer,PMREMGenerator:PMREM}:n.endsWith('BufferGeometryUtils.js')?{mergeGeometries}:{OrbitControls:Controls,RoomEnvironment:THREE.Scene,EffectComposer:Pass,RenderPass:Pass,GTAOPass:Pass,OutputPass:Pass,ShaderPass:Pass}};
  vm.createContext(state);
  await vm.runInContext('(async()=>{'+html.match(/<script type="module">([\s\S]*?)<\/script>/)[1].replaceAll('import(','loadModule(')+'\nglobalThis.runtime={scene,camera,controls,modelEnvelopes,roofRecords,routeSegments,walkableMesh,hillSurfaceHeight,roundWalkingPath,KITS,place};})()',state);
  assert.equal(window.__ready,true,'complete module boots');frames.shift()(100);
  state.runtime.scene.updateMatrixWorld(true);
  return {...state.runtime,window,html};
}
const slug=process.argv[2];
try{
  const r=await boot(join(DATA,`places/${slug}/place.json`),join(DATA,`out_${slug}/check-build`));
  console.log(`boot ok: ${r.window.__hotspots.length} stops`);
}catch(error){console.log('BOOT FAILED:',error.stack.split('\n').slice(0,6).join('\n'));process.exit(1);}
