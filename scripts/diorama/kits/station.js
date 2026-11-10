// Railway landmark kit. Metres; local +x follows the tracks, +z faces the garden.
(()=>{
  window.addEventListener('error',event=>{const url=event.target?.src||event.target?.href;if(url)console.error('Required station asset failed: '+url);},true);
  const C={wall:'#d4be87',white:'#eee9dc',roof:'#735b51',tile:'#92776a',column:'#88665c',glass:'#8b9e9a',dark:'#4c514c',rail:'#777870',wood:'#786553',lawn:'#b0b99b',sage:'#8d9f83',flower:['#a67f90','#bba274','#7f97a7']};
  function root(o,suffix){const g=new THREE.Group();g.name=o.id+'-'+suffix;g.position.set(...(o.position||[0,0,0]));g.rotation.y=(o.rotation||0)*Math.PI/180;scene.add(g);return g;}
  function add(g,geo,c,name){const m=new THREE.Mesh(geo,material(c));m.castShadow=true;m.receiveShadow=true;m.name=name||'';g.add(m);return m;}
  function block(g,x,y,z,w,h,d,c,name){const m=add(g,new THREE.BoxGeometry(w,h,d),c,name);m.position.set(x,y,z);return m;}
  function rod(g,a,b,r,c){const u=new THREE.Vector3(...a),v=new THREE.Vector3(...b),d=v.clone().sub(u),m=add(g,new THREE.CylinderGeometry(r,r,d.length(),8),c);m.position.copy(u.add(v).multiplyScalar(.5));m.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),d.normalize());return m;}
  function instances(g,geo,items,c,name){
    const m=new THREE.InstancedMesh(geo,material(c),items.length),dummy=new THREE.Object3D();m.name=name;m.castShadow=true;m.receiveShadow=true;g.add(m);
    items.forEach((p,i)=>{dummy.position.set(...p.p);dummy.scale.set(...(p.s||[1,1,1]));dummy.rotation.set(...(p.r||[0,0,0]));dummy.updateMatrix();m.setMatrixAt(i,dummy.matrix);if(p.c)m.setColorAt(i,new THREE.Color(p.c));});
    m.computeBoundingBox();m.computeBoundingSphere();m.instanceMatrix.needsUpdate=true;
    if(currentEnvelope){g.updateMatrixWorld(true);geo.computeBoundingBox();const b=geo.boundingBox,t=new THREE.Matrix4();for(let i=0;i<items.length;i++){m.getMatrixAt(i,t);for(const x of [b.min.x,b.max.x])for(const y of [b.min.y,b.max.y])for(const z of [b.min.z,b.max.z])currentEnvelope.push(new THREE.Vector3(x,y,z).applyMatrix4(t).applyMatrix4(m.matrixWorld));}}
    return m;
  }
  function compact(g){
    for(const c of g.children)if(c.isGroup)compact(c);
    const batches=new Map();for(const m of g.children){if(!m.isMesh||m.isInstancedMesh||m.name||m.material.map)continue;const k=m.material.color.getHexString()+':'+m.material.side;if(!batches.has(k))batches.set(k,[]);batches.get(k).push(m);}
    for(const list of batches.values()){if(list.length<2)continue;const geometries=list.map(m=>{m.updateMatrix();const geo=m.geometry.index?m.geometry.toNonIndexed():m.geometry.clone();for(const key of Object.keys(geo.attributes))if(!['position','normal'].includes(key))geo.deleteAttribute(key);return geo.applyMatrix4(m.matrix);});const m=new THREE.Mesh(mergeGeometries(geometries),list[0].material);m.castShadow=true;m.receiveShadow=true;list.forEach(p=>{g.remove(p);p.geometry.dispose();});geometries.forEach(p=>p.dispose());g.add(m);}
  }
  function register(type,builder){registerObjectType(type,o=>{const g=builder(o);if(g)compact(g);});}
  function paving(g,x,z,w,d,y=.08,c='#d4cfc2'){
    const m=block(g,x,y/2,z,w,y,d,c);g.updateMatrixWorld(true);walkableGeometries.push(m.geometry.clone().applyMatrix4(m.matrixWorld));return m;
  }
  function text(g,label,x,y,z,w,h,c=C.wood){
    const canvas=document.createElement('canvas');canvas.width=1024;canvas.height=160;const ctx=canvas.getContext('2d');ctx.clearRect(0,0,1024,160);ctx.font='600 100px Georgia';ctx.fillStyle=c;ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(label,512,80,990);
    const tex=new THREE.CanvasTexture(canvas);tex.colorSpace=THREE.SRGBColorSpace;const m=new THREE.Mesh(new THREE.PlaneGeometry(w,h),new THREE.MeshBasicMaterial({map:tex,transparent:true,depthWrite:false}));m.position.set(x,y,z);g.add(m);return m;
  }
  function roof(g,w,d,eave,ridge,x,z,name,axis='x'){
    const rg=new THREE.Group();rg.name=name;g.add(rg);rg.position.set(x,0,z);
    const span=axis==='x'?d:w,run=axis==='x'?w:d,slope=Math.hypot(span/2,ridge-eave),a=Math.atan2(ridge-eave,span/2);
    for(const s of [-1,1]){const m=block(rg,axis==='x'?0:s*span/4,(eave+ridge)/2,axis==='x'?s*span/4:0,axis==='x'?run:slope,.14,axis==='x'?slope:run,C.roof);if(axis==='x')m.rotation.x=s*a;else m.rotation.z=-s*a;}
    const lines=[];for(let t=.22;t<span/2;t+=.38){const h=ridge-(ridge-eave)*t/(span/2)+.10/Math.cos(a);for(const s of [-1,1]){if(axis==='x')lines.push(-run/2,h,s*t,run/2,h,s*t);else lines.push(s*t,h,-run/2,s*t,h,run/2);}}
    const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(lines,3));const courses=new THREE.LineSegments(geo,new THREE.LineBasicMaterial({color:C.tile,transparent:true,opacity:.5}));courses.name='station-tile-courses';rg.add(courses);
    if(axis==='x')rod(rg,[-w/2,ridge+.09,0],[w/2,ridge+.09,0],.065,C.tile);else rod(rg,[0,ridge+.09,-d/2],[0,ridge+.09,d/2],.065,C.tile);
    roofRecords.push({group:rg,parameters:{width:w,depth:d,eaveHeight:eave,ridgeHeight:ridge},tiers:1,thickness:.14,ridgeOrnament:false});return rg;
  }
  function windowGrid(g,x,y,z,w,h,columns=4,rows=7){
    block(g,x,y,z,w,h,.08,C.glass);for(let i=0;i<=columns;i++)block(g,x-w/2+i*w/columns,y,z+.07,i===0||i===columns?.14:.075,h+.12,.1,C.white);
    for(let i=0;i<=rows;i++)block(g,x,y-h/2+i*h/rows,z+.08,w+.12,i===0||i===rows?.14:.075,.1,C.white);
  }
  function canopy(g,o){
    const w=o.width,d=o.depth,y=o.height||3.1,z=o.z||0,rg=new THREE.Group();rg.name=o.name||'station-canopy-roof';g.add(rg);
    block(rg,0,y,z,w,.19,d,C.white);block(rg,0,y+.15,z,w-.18,.12,d-.18,C.roof);
    for(const edge of [-1,1])block(rg,0,y-.14,z+edge*d/2,w,.13,.1,C.white);
    const count=Math.floor(w/(o.spacing||3.9));for(let i=0;i<=count;i++){const x=-w/2+.4+i*(w-.8)/count;if(o.entryWidth&&Math.abs(x)<o.entryWidth/2+.2)continue;block(g,x,y/2,z+(o.front===false?-1:1)*(d/2-.5),.24,y,.26,C.column);block(g,x,.17,z+(o.front===false?-1:1)*(d/2-.5),.36,.34,.38,C.white);}
    return rg;
  }
  function entranceArches(g,centres,w,z,d,rise){
    const group=new THREE.Group();group.name='station-entrance-arches';g.add(group);const top=[],fascia=[];
    const quad=(out,a,b,c,d)=>out.push(...a,...b,...c,...a,...c,...d);
    for(const centre of centres)for(let i=0;i<20;i++){
      const a=-1+i/10,b=-1+(i+1)/10,x1=centre+a*w/2,x2=centre+b*w/2,y1=3.32+rise*(1-a*a),y2=3.32+rise*(1-b*b);
      quad(top,[x1,y1,z-d/2],[x1,y1,z+d/2],[x2,y2,z+d/2],[x2,y2,z-d/2]);
      quad(fascia,[x1,y1,z+d/2+.015],[x1,3.1,z+d/2+.015],[x2,3.1,z+d/2+.015],[x2,y2,z+d/2+.015]);
    }
    for(const [vertices,color] of [[top,C.roof],[fascia,C.white]]){const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));geo.computeVertexNormals();add(group,geo,color);}
  }
  register('station_building',o=>{
    const g=root(o,'station'),[w,d]=o.size,eave=o.eave||5.3,ridge=o.ridge||7.8,bay=o.gableWidth||4.7,gap=o.gableGap||.35,top=o.gablePeak||11.6;
    const central=3*bay+2*gap,wing=(w-central)/2;
    block(g,0,.16,0,w,.32,d,C.column);
    for(const side of [-1,1])block(g,side*(central+wing)/2,eave/2+.15,0,wing,eave-.3,d,C.wall);
    for(const z of [-d/2-.025,d/2+.025]){block(g,0,.6,z,w,.18,.13,C.white);block(g,0,3.65,z,w,.16,.14,C.white);block(g,0,4.65,z,w,.16,.14,C.white);}
    for(const s of [-1,1])roof(g,wing+.4,d+.65,eave,ridge,s*(central+wing)/2,0,'station-wing-roof');
    const wingEnd=new THREE.Shape();wingEnd.moveTo(-d/2,eave);wingEnd.lineTo(d/2,eave);wingEnd.lineTo(0,ridge);wingEnd.closePath();
    for(const side of [-1,1]){const wall=add(g,new THREE.ExtrudeGeometry(wingEnd,{depth:.2,bevelEnabled:false}),C.wall);wall.rotation.y=Math.PI/2;wall.position.x=side*w/2-.1;}
    const grids=new THREE.Group();grids.name='station-window-grids';g.add(grids);
    for(const side of [-1,1])for(let x=-w/2+1.4;x<w/2-1;x+=2.25){windowGrid(grids,x,4.13,side*(d/2+.12),1.9,.72,3,2);if(side===1){if(!o.interior||Math.abs(x)>(o.interior.doorWidth??2.4)/2+.85)block(g,x,1.9,d/2+.08,1.7,1.8,.12,C.dark);}else block(g,x,1.7,-d/2-.08,1.6,2.25,.12,C.glass);}
    for(let i=-1;i<=1;i++){
      const x=i*(bay+gap),bayGroup=new THREE.Group();bayGroup.name='station-gable-'+(i+1);g.add(bayGroup);bayGroup.position.x=x;
      for(const side of [-1,1]) {
        const z=side*(d/2-.12);
        if(i===0&&side===1&&o.interior){
          for(const end of [-1,1])block(bayGroup,end*(bay+2.4)/4,4.42,z,(bay-2.4)/2,8.26,.24,C.wall);
          block(bayGroup,0,5.75,z,2.4,5.6,.24,C.wall);
        }else block(bayGroup,0,4.42,z,bay,8.26,.24,C.wall);
      }
      const shape=new THREE.Shape();shape.moveTo(-bay/2,8.55);shape.lineTo(bay/2,8.55);shape.lineTo(0,top);shape.closePath();
      for(const end of [-1,1]){const face=add(bayGroup,new THREE.ExtrudeGeometry(shape,{depth:.22,bevelEnabled:false}),C.wall);face.position.z=end*d/2-.1;}
      const rg=roof(bayGroup,bay+.22,d+1,8.55,top+.2,0,.2,'station-gable-roof','z');
      for(const s of [-1,1])rod(bayGroup,[s*(bay/2+.06),8.55,d/2+.21],[0,top+.15,d/2+.21],.07,C.white);
      windowGrid(grids,x,6.27,d/2+.17,bay*.72,3.82,4,7);
      block(g,x,4.3,d/2+.31,bay*.76,.2,.42,C.white);
      if(i===0){
        const clock=add(g,new THREE.CylinderGeometry(.69,.69,.1,32),C.white,'station-clock');clock.rotation.x=Math.PI/2;clock.position.set(0,9.45,d/2+.28);
        for(let k=0;k<12;k++){const a=k*Math.PI/6,m=block(g,Math.sin(a)*.54,9.45+Math.cos(a)*.54,d/2+.35,.065,.12,.035,C.dark);m.rotation.z=-a;}
        rod(g,[0,9.45,d/2+.39],[0,9.9,d/2+.39],.035,C.dark);rod(g,[0,9.45,d/2+.39],[-.3,9.45,d/2+.39],.035,C.dark);
        block(g,0,8.36,d/2+.3,bay*.7,.53,.09,C.white);text(g,o.sign||'ĐÀ LẠT',0,8.36,d/2+.36,bay*.64,.43);
      }
    }
    for(const s of [-1,1]){for(const end of [-1,1])block(g,s*(bay+gap)/2,4.42,end*(d/2-.12),gap,8.26,.24,C.wall);block(g,s*central/2,4.42,0,.25,8.26,d,C.wall);block(g,s*(bay+gap)/2,8.57,.2,gap+.06,.14,d+1,C.roof);}
    canopy(g,{width:w+.7,depth:2.8,z:d/2+1.25,height:3.1,name:'station-front-canopy',entryWidth:o.interior?.doorWidth});
    if(o.frontCanopyRise)entranceArches(g,[-bay-gap,0,bay+gap],bay+gap,d/2+1.25,2.8,o.frontCanopyRise);
    for(let x=-w/2+1;x<w/2;x+=3.6)if(!o.interior||Math.abs(x)>2.5)block(g,x,1.35,d/2+.18,2.45,2.15,.12,C.dark);
    paving(g,0,d/2+1.3,w+1.1,3.5,.16,C.white);
    contactShadow(o.position[0],.01,o.position[2],w,d,.22);return g;
  });
  registerInteriorKit('station_hall',(o,{roof})=>{
    const p=o.interior,g=new THREE.Group();g.name='station-hall-interior';g.position.set(...o.position);g.rotation.y=(o.rotation||0)*Math.PI/180;
    const [w,d]=p.size,y=p.floorY,wood=p.wood||'#655647',ochre=p.wall||'#d4be87';
    block(g,0,y-.035,0,w,.07,d,'#b6ad95','station-hall-tiles');
    const seams=[],pitch=p.tileSize??.45,joint=Math.min(.012,pitch*.035);for(let x=-w/2;x<=w/2;x+=pitch)seams.push({p:[x,y+.003,0],s:[joint,.006,d]});for(let z=-d/2;z<=d/2;z+=pitch)seams.push({p:[0,y+.004,z],s:[w,.006,joint]});
    instances(g,new THREE.BoxGeometry(1,1,1),seams,'#c2b9a3','station-hall-tile-joints');
    const panels=new THREE.Group();panels.name='station-hall-panelling';g.add(panels);
    for(const side of [-1,1]) {
      block(panels,side*w/2,1.75,0,.12,2.8,d,wood);
      if(side===1)for(const end of [-1,1])block(panels,end*(w+2.4)/4,1.75,side*d/2,(w-2.4)/2,2.8,.12,wood);
      else block(panels,0,1.75,side*d/2,w,2.8,.12,wood);
      block(g,side*(w/2-.04),5.6,0,.08,4.85,d,ochre);
      block(g,0,5.6,side*(d/2-.04),w,4.85,.08,ochre);
    }
    const lines=[];for(let h=.65;h<3.1;h+=.22)for(const side of [-1,1]){if(side===-1)lines.push({p:[0,h,side*(d/2-.08)],s:[w,.022,.03]});else for(const end of [-1,1])lines.push({p:[end*(w+2.4)/4,h,side*(d/2-.08)],s:[(w-2.4)/2,.022,.03]});lines.push({p:[side*(w/2-.08),h,0],s:[.03,.022,d]});}
    instances(g,new THREE.BoxGeometry(1,1,1),lines,'#88745f','station-hall-panel-joints');
    const panes=[],frames=[],rows=p.glassRows??1;for(const side of [-1,1])for(let row=0;row<rows;row++)for(let x=-w/2+.6;x<w/2-.2;x+=.8){const height=6.5+(row-(rows-1)/2)*.58;panes.push({p:[x,height,side*(d/2-.18)],s:[.69,.49,.035],c:p.glass[panes.length%p.glass.length]});frames.push({p:[x,height,side*(d/2-.11)],s:[.78,.58,.025]});}
    instances(g,new THREE.BoxGeometry(1,1,1),frames,C.white,'station-hall-glass-frames');instances(g,new THREE.BoxGeometry(1,1,1),panes,'#ffffff','station-hall-coloured-glass');
    const photos=new THREE.Group();photos.name='station-hall-old-photos';g.add(photos);
    const borders=new THREE.Group();borders.name='station-hall-photo-borders';g.add(borders);
    for(const side of [-1,1])for(const [index,x] of [-4.4,0,4.4].entries()) {
      for(const sign of [-1,1]){block(borders,x+sign*1.9,4.65,side*(d/2-.12),.06,1.9,.025,C.white);block(borders,x,4.65+sign*.95,side*(d/2-.12),3.86,.06,.025,C.white);}
      block(photos,x,4.65,side*(d/2-.18),3.3,1.35,.08,wood);block(photos,x,4.65,side*(d/2-.24),3.12,1.17,.04,C.white);
      const texture=new THREE.TextureLoader().load('photos/'+p.photoAssets[(index+Number(side>0))%p.photoAssets.length]);texture.colorSpace=THREE.SRGBColorSpace;
      const mat=new THREE.MeshBasicMaterial({map:texture,color:'#bdb5a0'});
      mat.onBeforeCompile=shader=>{shader.fragmentShader=shader.fragmentShader.replace('#include <color_fragment>','#include <color_fragment>\ndiffuseColor.rgb=vec3(dot(diffuseColor.rgb,vec3(.299,.587,.114)));');};
      mat.customProgramCacheKey=()=> 'station-photo-monochrome-v1';
      const picture=new THREE.Mesh(new THREE.PlaneGeometry(2.64,1.1),mat);picture.name='station-hall-photo-image';picture.position.set(x,4.65,side*(d/2-.27));photos.add(picture);if(side===1)picture.rotation.y=Math.PI;
    }
    const door=new THREE.Group();door.name='station-hall-door';
    block(door,0,1.68,d/2+.13,2.4,2.7,.12,wood);g.add(door);
    for(const x of [-1.3,1.3])block(g,x,1.7,d/2-.12,.16,2.85,.16,wood);
    block(g,0,3.14,d/2-.12,2.75,.2,.16,wood);
    const counter=new THREE.Group();counter.name='station-hall-counter';g.add(counter);block(counter,0,.85,-d/2+.65,3.3,1,.8,wood);block(counter,0,1.42,-d/2+.65,3.45,.12,.9,'#9c8a70');text(counter,p.counterLabel,0,1.05,-d/2+1.07,2.4,.26,C.white);
    const benches=new THREE.Group();benches.name='station-hall-benches';g.add(benches);
    for(const [x,z,length] of p.benches||[]) {
      block(benches,x,y+.45,z,.52,.12,length,wood);
      for(const end of [-1,1])for(const side of [-1,1])block(benches,x+side*.18,y+.21,z+end*(length/2-.2),.07,.42,.07,wood);
      for(const height of [.66,.82])block(benches,x+Math.sign(x)*.23,y+height,z,.06,.12,length,wood);
    }
    const ceiling=new THREE.Group();ceiling.name='station-hall-ceiling';ceiling.position.x=-roof.position.x;
    block(ceiling,0,8.2,0,w+.4,.16,d+.45,C.white);
    const beams=[],rafters=[];for(let z=-d/2+.25;z<d/2;z+=2.2)beams.push({p:[0,7.95,z],s:[w+.25,.28,.2]});for(let x=-w/2+.2;x<w/2;x+=.65)rafters.push({p:[x,8.08,0],s:[.09,.12,d+.2]});
    instances(ceiling,new THREE.BoxGeometry(1,1,1),beams,C.white,'station-hall-white-beams');instances(ceiling,new THREE.BoxGeometry(1,1,1),rafters,wood,'station-hall-rafters');
    compact(g);compact(ceiling);return {group:g,ceiling,door,front:new THREE.Group()};
  });
  register('station_canopy',o=>{const g=root(o,'canopy');paving(g,0,0,o.size[0],o.size[1],.18);const rg=canopy(g,{width:o.size[0],depth:o.size[1]-.3,height:o.height||3.6,front:false});roofRecords.push({group:rg,parameters:{width:o.size[0],depth:o.size[1],eaveHeight:3.6,ridgeHeight:3.8},tiers:1,thickness:.19,ridgeOrnament:false});return g;});
  register('station_paving',o=>{
    const g=root(o,'paving'),[w,d]=o.size;paving(g,0,0,w,d,o.height||.08,o.color);
    const joints=[];for(let x=-w/2+.8;x<w/2;x+=o.grid||1.6)joints.push({p:[x,(o.height||.08)+.003,0],s:[.013,.006,d]});for(let z=-d/2+.8;z<d/2;z+=o.grid||1.6)joints.push({p:[0,(o.height||.08)+.003,z],s:[w,.006,.013]});instances(g,new THREE.BoxGeometry(1,1,1),joints,'#bcb8ab','station-paving-joints');return g;
  });
  register('station_tracks',o=>{
    const g=root(o,'tracks'),[w,d]=o.size;block(g,0,.045,0,w,.09,d,'#bcb9ad');const sleepers=[];
    for(const z of o.lines||[-3,3]){for(let x=-w/2+.6;x<w/2;x+=.8)sleepers.push({p:[x,.15,z],s:[.17,.16,2]});for(const s of [-1,1]){block(g,0,.29,z+s*.5,w,.13,.075,C.rail);block(g,0,.22,z+s*.5,w,.035,.16,C.dark);}}
    instances(g,new THREE.BoxGeometry(1,1,1),sleepers,'#8d8171','station-sleepers');return g;
  });
  register('station_train',o=>{
    const g=root(o,'train'),[length,width]=o.size,base=.45,body=o.kind==='steam'?C.dark:o.kind==='diesel'?'#7c8474':C.wood;
    g.position.y+=(o.railTop??.355)-.17;
    block(g,0,.68,0,length,.45,width*.87,C.dark);
    const axles=o.kind==='steam'?[[-length*.36,.32],[-length*.2,.55],[0,.55],[length*.2,.55]]:[[-length*.33,.4],[-length*.22,.4],[length*.22,.4],[length*.33,.4]];
    const wheels=[];for(const [x,r] of axles)for(const s of [-1,1])wheels.push({p:[x,.17+r,s*.55],s:[r,.16,r],r:[Math.PI/2,0,0],c:o.kind==='steam'?C.column:C.dark});instances(g,new THREE.CylinderGeometry(1,1,1,24),wheels,'#ffffff','station-train-wheels');
    if(o.kind==='steam'){
      const boiler=add(g,new THREE.CylinderGeometry(.89,.89,length*.64,20),body);boiler.rotation.z=Math.PI/2;boiler.position.set(-length*.12,1.95,0);
      block(g,length*.31,2.03,0,length*.25,2.5,width*.9,body);block(g,length*.31,3.35,0,length*.31,.17,width+ .12,C.dark);
      for(const s of [-1,1])block(g,length*.31,2.63,s*(width*.46),length*.16,.7,.06,C.glass);
      const chimney=add(g,new THREE.CylinderGeometry(.25,.19,.85,12),C.dark);chimney.position.set(-length*.32,3.05,0);
      const dome=add(g,new THREE.SphereGeometry(.26,12,8),body);dome.position.set(0,2.88,0);
      for(const s of [-1,1]){rod(g,[-length*.4,1.1,s*.95],[length*.18,1.1,s*.95],.065,'#a29c8f');rod(g,[-length*.38,2.55,s*.66],[length*.16,2.55,s*.66],.035,C.white);}
      block(g,-length/2,.93,0,.2,.32,width,C.column);block(g,-length/2-.12,.55,0,.3,.12,width+ .3,C.dark);
      const front=-length*.44;
      const ring=add(g,new THREE.TorusGeometry(.85,.035,8,32),C.white);ring.rotation.y=Math.PI/2;ring.position.set(front-.045,1.95,0);
      const lamp=add(g,new THREE.CylinderGeometry(.23,.23,.3,20),C.dark,'station-headlamp');lamp.rotation.z=Math.PI/2;lamp.position.set(front-.04,3.05,0);
      const lens=add(g,new THREE.CylinderGeometry(.17,.17,.025,20),C.white);lens.rotation.z=Math.PI/2;lens.position.set(front-.205,3.05,0);
      block(g,front-.04,2.35,0,.09,.32,.95,C.column);
      if(o.number){const label=text(g,o.number,front-.09,2.35,0,.86,.23,C.white);label.rotation.y=-Math.PI/2;}
      for(const [x,r] of axles.filter(([,r])=>r>.5))for(const side of [-1,1])for(let k=0;k<8;k++){const a=k*Math.PI/4;rod(g,[x,.17+r,side*.645],[x+Math.cos(a)*r*.83,.17+r+Math.sin(a)*r*.83,side*.645],.025,C.tile);}
      for(const side of [-1,1])rod(g,[-length*.2,.72,side*.69],[length*.2,.72,side*.69],.05,C.tile);
    }else{
      block(g,0,1.9,0,length*.95,2.45,width,body);
      const roof=new THREE.Group();roof.name='station-carriage-roof';g.add(roof);block(roof,0,3.2,0,length,.19,width+.19,C.dark);
      const arch=add(roof,new THREE.CylinderGeometry(width*.53,width*.53,length,16,1,false,0,Math.PI),C.dark);arch.rotation.z=Math.PI/2;arch.scale.set(.32,1,1);arch.position.y=3.15;
      for(const s of [-1,1])for(let x=-length*.4;x<length*.43;x+=1.35){block(g,x,2.1,s*(width/2+.035),.83,1.14,.06,C.glass);for(const dx of [-.46,.46])block(g,x+dx,2.1,s*(width/2+.085),.055,1.28,.06,C.white);block(g,x,1.5,s*(width/2+.085),.95,.055,.06,C.white);}
      for(const x of [-length*.48,length*.48]){block(g,x,1.65,0,.1,1.8,.72,C.dark);for(const s of [-1,1])rod(g,[x,.8,s*.8],[x,1.8,s*.8],.04,C.white);}
      if(o.kind==='diesel'){block(g,-length*.36,2.3,0,length*.22,1.95,width+.05,body);block(g,-length*.44,2.8,0,.08,.8,width*.72,C.glass);for(let i=0;i<10;i++)block(g,-length*.05+i*.3,1.94,width/2+.07,.08,1.15,.05,C.dark);}
    }
    return g;
  });
  register('station_garden',o=>{
    const g=root(o,'garden'),[w,d]=o.size;block(g,0,.04,0,w,.08,d,C.lawn);const hedge=[],shrubs=[],flowers=[],leaves=[],stems=[];
    for(const side of [-1,1]){block(g,0,.095,side*d/2,w+.12,.11,.1,'#c9c7b3');block(g,side*w/2,.095,0,.1,.11,d,'#c9c7b3');}
    for(const s of [-1,1]){for(let x=-w/2+.2;x<w/2;x+=.38)hedge.push({p:[x,.33,s*(d/2-.2)],s:[.42,.53,.42]});for(let z=-d/2+.2;z<d/2;z+=.38)hedge.push({p:[s*(w/2-.2),.33,z],s:[.42,.53,.42]});}
    for(let x=-w*.31;x<=w*.32;x+=w*.31)shrubs.push({p:[x,1,0],s:[1.35,.95,1.2]});
    for(let x=-w/2+.75;x<w/2-.6;x+=o.flowerSpacing||.32)for(let z=-d/2+.75;z<d/2-.6;z+=.36){
      if((o.sparse&&Math.abs(z)<d*.22)||Math.sin(x*6.17+z*2.9)+.5*Math.sin(x*2-z*4)<-.15)continue;
      const px=x+.12*Math.sin(x*12+z*7),pz=z+.12*Math.sin(x*5-z*9),py=.35+.05*Math.sin(x*3+z),r=.13+.02*Math.sin(z*8);
      flowers.push({p:[px,py,pz],s:[r,r,r],r:[0,x*3+z,0],c:C.flower[Math.floor(Math.abs(x/2+z/3))%3]});leaves.push({p:[px,.23,pz],s:[.19,.12,.17]});stems.push({p:[px,py/2,pz],s:[.014,py,.014]});
    }
    const petals=[];for(let k=0;k<5;k++){const a=k*Math.PI*2/5,c=Math.cos(a),s=Math.sin(a);petals.push(0,.1,0,.55*c-.3*s,.05,.55*s+.3*c,c,.2,s,0,.1,0,c,.2,s,.55*c+.3*s,.05,.55*s-.3*c);}
    const flowerGeometry=new THREE.BufferGeometry();flowerGeometry.setAttribute('position',new THREE.Float32BufferAttribute(petals,3));flowerGeometry.computeVertexNormals();
    instances(g,new THREE.BoxGeometry(1,1,1),hedge,C.sage,'station-clipped-hedge');instances(g,new THREE.IcosahedronGeometry(1,2),shrubs,C.sage,'station-round-shrubs');instances(g,new THREE.IcosahedronGeometry(1,0),leaves,'#9aaa8d','station-flower-leaves');instances(g,new THREE.BoxGeometry(1,1,1),stems,C.sage,'station-flower-stems');instances(g,flowerGeometry,flowers,'#ffffff','station-flowers');return g;
  });
  register('station_grove',o=>{
    const g=root(o,'grove');g.updateMatrixWorld(true);vegetationMode=true;
    for(const [x,z,h] of o.trees){const p=g.localToWorld(new THREE.Vector3(x,0,z));tree({kind:'pine',position:p.toArray(),height:h,grounded:true});}
    vegetationMode=false;
    if(o.understory){
      const plants=[],radius=o.understoryRadius||3.3;
      for(const [index,[x,z]] of o.trees.entries()){
        const s=new THREE.Shape();for(let i=0;i<=40;i++){const a=i*Math.PI/20,r=radius*(1+.12*Math.sin(a*3+index));const px=x+Math.cos(a)*r,pz=z+Math.sin(a)*r*.72;i?s.lineTo(px,-pz):s.moveTo(px,-pz);}s.closePath();const geo=new THREE.ShapeGeometry(s);geo.rotateX(-Math.PI/2);const bed=add(g,geo,'#b2bea4');bed.position.y=.036;
        for(let k=0;k<12;k++){const a=k*2.4+index,r=radius*Math.sqrt((k+.5)/12)*.8;plants.push({p:[x+Math.cos(a)*r,.35+.05*Math.sin(k),z+Math.sin(a)*r*.7],s:[.75+.12*Math.sin(k),.3,.65],c:['#9eae91','#a8b69b','#b1bda2'][k%3]});}
      }
      instances(g,new THREE.IcosahedronGeometry(1,2),plants,'#ffffff','station-grove-understory');
    }
    return g;
  });
  register('station_lawn',o=>{
    const g=root(o,'lawn'),[w,d]=o.size,r=o.radius||2,s=new THREE.Shape();
    s.moveTo(-w/2+r,-d/2);s.lineTo(w/2-r,-d/2);s.quadraticCurveTo(w/2,-d/2,w/2,-d/2+r);s.lineTo(w/2,d/2-r);s.quadraticCurveTo(w/2,d/2,w/2-r,d/2);s.lineTo(-w/2+r,d/2);s.quadraticCurveTo(-w/2,d/2,-w/2,d/2-r);s.lineTo(-w/2,-d/2+r);s.quadraticCurveTo(-w/2,-d/2,-w/2+r,-d/2);
    const geo=new THREE.ShapeGeometry(s,8);geo.rotateX(-Math.PI/2);const m=add(g,geo,o.color||'#c5ccba');m.position.y=.025;return g;
  });
  register('station_annex',o=>{const g=root(o,'annex'),[w,d]=o.size;block(g,0,1.45,0,w,2.9,d,C.wall);roof(g,w+.4,d+.4,3,4.1,0,0,'station-annex-roof');for(let x=-w/2+1;x<w/2;x+=2)windowGrid(g,x,1.7,d/2+.06,1.1,1.2,2,2);return g;});
})();
