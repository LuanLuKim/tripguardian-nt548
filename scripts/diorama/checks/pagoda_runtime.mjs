import assert from 'node:assert/strict';
import vm from 'node:vm';
import {createHash} from 'node:crypto';
import * as THREE from '../vendor/node_modules/three/build/three.module.js';
import {mergeGeometries} from '../vendor/node_modules/three/examples/jsm/utils/BufferGeometryUtils.js';
export {THREE,mergeGeometries};
export async function boot(html,{width=1600,height=900}={}){
  const canvas=new Proxy({measureText:t=>({width:t.length*24}),createImageData:(w,h)=>({data:new Uint8ClampedArray(w*h*4)})},{get:(t,k)=>t[k]??(()=>{})});
  const element=()=>({style:{setProperty(){}},dataset:{},classList:{add(){},toggle(){}},appendChild(){},setAttribute(){},addEventListener(){},querySelector:()=>element(),getContext:()=>canvas});
  const elements=new Map(),frames=[];
  const document={body:element(),createElement:element,createElementNS:element,getElementById:id=>{if(!elements.has(id))elements.set(id,element());return elements.get(id);}};
  class Renderer{constructor(){this.domElement=element();this.shadowMap={};this.info={render:{},reset(){}};}setPixelRatio(){}setSize(){}getContext(){return {finish(){}};}}
  class PMREM{fromScene(){return {texture:null};}dispose(){}}
  class Controls{constructor(c){this.camera=c;this.target=new THREE.Vector3();}update(){this.camera.lookAt(this.target);this.camera.updateMatrixWorld();}addEventListener(){}}
  class Pass{constructor(){this.overrideVisibility=()=>{};}addPass(){}setSize(){}updateGtaoMaterial(){}render(){}}
  const window={matchMedia:()=>({matches:false}),addEventListener(){}};
  const state={document,window,innerWidth:width,innerHeight:height,devicePixelRatio:1,console:{info(){}},performance:{now:()=>0},requestAnimationFrame:f=>frames.push(f),
    loadModule:async n=>n==='three'?{...THREE,WebGLRenderer:Renderer,PMREMGenerator:PMREM}:n.endsWith('BufferGeometryUtils.js')?{mergeGeometries}:{OrbitControls:Controls,RoomEnvironment:THREE.Scene,EffectComposer:Pass,RenderPass:Pass,GTAOPass:Pass,OutputPass:Pass,ShaderPass:Pass}};
  vm.createContext(state);
  await vm.runInContext('(async()=>{'+html.match(/<script type="module">([\s\S]*?)<\/script>/)[1].replaceAll('import(','loadModule(')+'\nglobalThis.runtime={scene,camera,controls,modelEnvelopes,roofRecords,routeSegments,walkableGeometries,objects:KITS.objects,fitOverview};})()',state);
  assert.equal(window.__ready,true);frames.shift()(100);state.runtime.scene.updateMatrixWorld(true);
  return {...state.runtime,window};
}
export function digest(scene){
  const hash=createHash('sha256');let meshes=0;scene.updateMatrixWorld(true);
  scene.traverse(p=>{if(!p.geometry)return;meshes++;
    hash.update(JSON.stringify([p.name,p.type,p.visible,p.matrixWorld.elements,p.material?.color?.getHexString(),p.material?.opacity,p.material?.side]));
    for(const [name,a] of Object.entries(p.geometry.attributes)){hash.update(name);hash.update(Buffer.from(a.array.buffer,a.array.byteOffset,a.array.byteLength));}
    for(const a of [p.geometry.index,p.instanceMatrix,p.instanceColor])if(a)hash.update(Buffer.from(a.array.buffer,a.array.byteOffset,a.array.byteLength));
  });return {hash:hash.digest('hex'),meshes};
}
