// Church kit. Dimensions are metres; local +z is the entrance gable.
(()=>{
  const C={stone:'#b9b4a6',joint:'#8d8c80',wood:'#574b40',roof:'#705348',course:'#8d7262',glass:['#b3b48e','#8babb0','#c6a378','#a18c9f'],cream:'#e6dfcf',green:'#a4b194'};
  function root(o){const g=new THREE.Group();g.position.set(...o.position);g.rotation.y=(o.rotation||0)*Math.PI/180;scene.add(g);return g;}
  function add(g,geo,color,name){const m=new THREE.Mesh(geo,material(color));m.castShadow=true;m.receiveShadow=true;if(name)m.name=name;g.add(m);return m;}
  function block(g,x,y,z,w,h,d,c,name){const m=add(g,new THREE.BoxGeometry(w,h,d),c,name);m.position.set(x,y,z);return m;}
  function rod(g,a,b,r,c){const u=new THREE.Vector3(...a),v=new THREE.Vector3(...b),d=v.clone().sub(u);const m=add(g,new THREE.CylinderGeometry(r,r,d.length(),6),c);m.position.copy(u.add(v).multiplyScalar(.5));m.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),d.normalize());return m;}
  function lines(g,points,c,name){const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(points,3));const m=new THREE.LineSegments(geo,new THREE.LineBasicMaterial({color:c,transparent:true,opacity:.45}));m.name=name||'';g.add(m);return m;}
  function pave(g,x,z,w,d,c=C.cream,y=.045){const m=block(g,x,y/2,z,w,y,d,c);g.updateMatrixWorld(true);walkableGeometries.push(m.geometry.clone().applyMatrix4(m.matrixWorld));return m;}
  function shrub(g,x,z,r=.65){const m=add(g,new THREE.IcosahedronGeometry(r,1),C.green);m.scale.y=.6;m.position.set(x,r*.48,z);}
  function instances(g,geometry,items,name,color='#ffffff'){
    if(!items.length)return;
    const batch=new THREE.InstancedMesh(geometry,material(color),items.length),dummy=new THREE.Object3D();
    batch.name=name;batch.castShadow=true;batch.receiveShadow=true;
    items.forEach((p,i)=>{dummy.position.set(...p.position);dummy.scale.set(...(p.scale||[1,1,1]));dummy.rotation.set(...(p.rotation||[0,0,0]));dummy.updateMatrix();batch.setMatrixAt(i,dummy.matrix);if(p.color)batch.setColorAt(i,new THREE.Color(p.color));});
    batch.instanceMatrix.needsUpdate=true;batch.computeBoundingBox();batch.computeBoundingSphere();g.add(batch);
    if(typeof currentEnvelope!=='undefined'&&currentEnvelope){
      g.updateMatrixWorld(true);geometry.computeBoundingBox();const bounds=geometry.boundingBox,matrix=new THREE.Matrix4();
      for(let i=0;i<items.length;i++){batch.getMatrixAt(i,matrix);for(const x of [bounds.min.x,bounds.max.x])for(const y of [bounds.min.y,bounds.max.y])for(const z of [bounds.min.z,bounds.max.z])currentEnvelope.push(new THREE.Vector3(x,y,z).applyMatrix4(matrix).applyMatrix4(batch.matrixWorld));}
    }
    return batch;
  }
  function compact(g){
    for(const child of [...g.children])if(child.isGroup)compact(child);
    const batches=new Map();
    for(const m of g.children){
      if(!m.isMesh||m.isInstancedMesh||m.name||m.material.map)continue;
      const key=m.material.color.getHexString()+':'+m.material.side;
      if(!batches.has(key))batches.set(key,[]);batches.get(key).push(m);
    }
    for(const items of batches.values()){
      if(items.length<2)continue;
      const geometries=items.map(m=>{m.updateMatrix();const geo=m.geometry.index?m.geometry.toNonIndexed():m.geometry.clone();for(const name of Object.keys(geo.attributes))if(!['position','normal'].includes(name))geo.deleteAttribute(name);return geo.applyMatrix4(m.matrix);});
      const merged=new THREE.Mesh(mergeGeometries(geometries),items[0].material);merged.castShadow=true;merged.receiveShadow=true;
      items.forEach(m=>{g.remove(m);m.geometry.dispose();});geometries.forEach(geo=>geo.dispose());g.add(merged);
    }
  }
  function register(type,builder){registerObjectType(type,o=>{const first=scene.children.length;builder(o);for(const g of scene.children.slice(first))if(g.isGroup)compact(g);});}
  function roof(g,w,d,eave,apex,z,name,options={}){
    const rg=new THREE.Group();rg.name=name;rg.userData.pitch=Math.atan2(apex-eave,w/2)*180/Math.PI;g.add(rg);
    const slope=Math.hypot(w/2,apex-eave),angle=Math.atan2(apex-eave,w/2);
    for(const side of [-1,1]){const m=block(rg,side*w/4,(apex+eave)/2,z,slope,.17,d,options.color||C.roof);m.rotation.z=-side*angle;}
    const pts=[];
    for(let y=eave+.13;y<apex;y+=.25){const x=w/2*(1-(y-eave)/(apex-eave));for(const s of [-1,1])pts.push(s*(x+.1),y+.05,z-d/2,s*(x+.1),y+.05,z+d/2);}
    lines(rg,pts,options.courseColor||C.course,'camly-shingle-courses');
    for(const end of [-1,1])for(const side of [-1,1])rod(rg,[0,apex+.06,z+end*d/2],[side*w/2,eave+.06,z+end*d/2],.11,options.edgeColor||C.course);
    rod(rg,[0,apex+.05,z-d/2],[0,apex+.05,z+d/2],.11,options.ridgeColor||C.wood);
    roofRecords.push({group:rg,parameters:{position:[...g.position],width:w,depth:d,eaveHeight:eave,ridgeHeight:apex,color:options.color||C.roof},tiers:1,thickness:.17,ridgeOrnament:false});
    return rg;
  }
  function gable(g,w,base,top,z,front,options={}){
    const shape=new THREE.Shape();shape.moveTo(-w/2,base);shape.lineTo(w/2,base);shape.lineTo(0,top);shape.closePath();
    const holes=[];
    for(const [x,y,r] of options.openings||[[0,top-3,.55],[-2.2,8.4,1.05],[2.2,8.4,1.05],[0,6.3,1.15],[-4.4,4.6,.35],[4.4,4.6,.35]]){
      if(y>=top-1)continue;const p=new THREE.Path(),star=r>1;
      const points=star?Array.from({length:16},(_,i)=>{const a=Math.PI/2+i*Math.PI/8,rr=i%2?r*(options.starInner||.12):r*(i%4===0?1:.5);return [x+Math.cos(a)*rr,y+Math.sin(a)*rr];}):[[x,y+r],[x+r*.5,y],[x,y-r],[x-r*.5,y]];
      const scaled=points.map(([px,py])=>[x+(px-x)*(options.starScale||1),y+(py-y)*(options.starScale||1)]);
      scaled.forEach(([px,py],i)=>i?p.lineTo(px,py):p.moveTo(px,py));p.closePath();shape.holes.push(p);holes.push(scaled);
    }
    const panel=add(g,new THREE.ExtrudeGeometry(shape,{depth:.12,bevelEnabled:false}),options.color||(front?C.wood:'#9e9f8e'));panel.position.z=z;
    const openings=new THREE.Group();if(front)openings.name='parish-gable-openings';g.add(openings);
    holes.forEach((points,i)=>{const glass=new THREE.Shape();points.forEach(([x,y],k)=>k?glass.lineTo(x,y):glass.moveTo(x,y));glass.closePath();const color=options.openingColor||(options.glassPalette||C.glass)[i%4],m=add(openings,new THREE.ShapeGeometry(glass),color);m.material=m.material.clone();m.material.side=THREE.DoubleSide;if(options.glow){m.material.emissive.set(color);m.material.emissiveIntensity=options.glow;}m.position.z=z+.07;});
    const lattice=new THREE.Group();lattice.name=front?'camly-gable-lattice':'camly-rear-frame';g.add(lattice);
    if(options.lattice!==false){
      for(let y=base+.7;y<top-.8;y+=1.3){const half=w/2*(1-(y-base)/(top-base));rod(lattice,[-half,y,z+.17],[half,y,z+.17],.055,C.course);}
      for(let x=-w/2+1;x<w/2;x+=1.45){const h=top-(top-base)*Math.abs(x)/(w/2);rod(lattice,[x,base,z+.19],[x,h,z+.19],.055,options.latticeColor||C.wood);}
    }
    for(const side of [-1,1])rod(lattice,[0,top,z+.2],[side*w/2,base,z+.2],.12,C.wood);
  }
  // Basilica options are independent of the existing timber A-frame preset.
  function arch(g,x,y,z,w,h,yaw,color,trim=C.cream,options={}){
    const group=new THREE.Group();group.position.set(x,y,z);group.rotation.y=yaw;g.add(group);
    const shape=(width,height)=>{const s=new THREE.Shape(),r=width/2;s.moveTo(-r,0);s.lineTo(r,0);s.lineTo(r,height-r);s.absarc(0,height-r,r,0,Math.PI,false);s.closePath();return s;};
    const outer=shape(w+(options.frameWidth??.32),h+(options.frameHeight??.17)),hole=shape(w,h);outer.holes.push(new THREE.Path(hole.getPoints(20)));
    const frame=add(group,new THREE.ExtrudeGeometry(outer,{depth:.09,bevelEnabled:false,curveSegments:12}),trim);
    const pane=add(group,new THREE.ShapeGeometry(shape(w,h),16),color);pane.position.z=.035;
    block(group,0,.045,.05,w+.48,.09,.25,trim);
    if(options.leaded){
      const leads=[];
      for(const x of [-w*.23,w*.23])leads.push(x,.12,.075,x,h-w/2+Math.sqrt((w/2)**2-x*x)-.1,.075);
      for(const y of [h*.27,h*.53,h*.76])leads.push(-w*.46,y,.075,w*.46,y,.075);
      lines(group,leads,'#6f7065','basilica-glass-leads');
      for(const [index,y] of [h*.27,h*.53].entries()){
        const s=new THREE.Shape();s.moveTo(0,y+.24);s.lineTo(w*.19,y);s.lineTo(0,y-.24);s.lineTo(-w*.19,y);s.closePath();
        const jewel=add(group,new THREE.ShapeGeometry(s),C.glass[index?2:3]);jewel.position.z=.06;
      }
    }
    return {group,pane,frame};
  }
  function basilicaRoof(g,w,d,eave,apex,z,name,color){
    const rg=roof(g,w,d,eave,apex,z,name);
    for(const m of rg.children)if(m.isMesh&&m.material.color.equals(new THREE.Color(C.roof)))m.material=material(color);
    rg.getObjectByName('camly-shingle-courses').name='basilica-roof-courses';
    roofRecords.at(-1).parameters.color=color;return rg;
  }
  register('church_basilica',o=>{
    const g=root(o);g.name='basilica-'+(o.id||'church');
    const [w,d]=o.size,wall=o.wallColor||'#c49b88',trim=o.trimColor||'#e5d8c3',roofColor=o.roofColor||'#827a6c';
    const nave=o.nave||{},eave=nave.eave||14.2,ridge=nave.ridge||17.2,aisle=nave.aisleWidth||3.2;
    const hollow=Boolean(o.interior?.vault);
    block(g,0,.3,0,w+aisle*2+.5,.6,d,C.stone);
    if(hollow){
      for(const side of [-1,1])block(g,side*(w/2-.14),(eave+7.8)/2,0,.28,eave-7.8,d,wall);
      // The tower vestibule opens into the nave; only its shoulders are masonry.
      for(const side of [-1,1])block(g,side*(w+3.1)/4,eave/2,d/2,(w-3.1)/2,eave,.3,wall);
      block(g,0,(eave+6.2)/2,d/2,3.1,eave-6.2,.3,wall);
    }else block(g,0,eave/2,0,w,eave,d,wall);
    const windows=new THREE.Group();windows.name='basilica-arched-windows';g.add(windows);
    const buttresses=new THREE.Group();buttresses.name='basilica-buttresses';g.add(buttresses);
    for(const side of [-1,1]){
      const x=side*(w+aisle)/2;
      if(hollow){
        block(g,side*(w/2+aisle-.14),3.9,0,.28,7.8,d,wall);
        for(const end of [-1,1])block(g,x,3.9,end*d/2,aisle,7.8,.28,wall);
      }else block(g,x,3.9,0,aisle,7.8,d,wall);
      const slope=block(g,side*(w/2+aisle/2),8.2,0,aisle+.45,.16,d+.6,roofColor);slope.rotation.z=-side*.14;
      const aisleRoof=new THREE.Group();aisleRoof.name='basilica-aisle-roof';g.add(aisleRoof);aisleRoof.add(slope);
      roofRecords.push({group:aisleRoof,parameters:{position:[...o.position],width:aisle,depth:d,eaveHeight:7.9,ridgeHeight:8.5,color:roofColor},tiers:1,thickness:.16,ridgeOrnament:false});
      for(let z=-d/2+2.4;z<d/2-1;z+=nave.baySpacing||4.3){
        arch(windows,side*(w/2+aisle+.025),2.1,z,1.5,3.8,side*Math.PI/2,'#777e78',trim,{leaded:true});
        arch(windows,side*(w/2+.025),9.5,z,1.2,3.3,side*Math.PI/2,C.glass[Math.round(z+d)%4],trim,{leaded:true});
        for(const xx of [side*(w/2+.22),side*(w/2+aisle+.24)]){
          const h=Math.abs(xx)<w/2+1?eave:7.7;
          block(buttresses,xx,h/2,z+1.65,.5,h,.55,trim);
          block(buttresses,xx,h+.1,z+1.65,.65,.22,.75,trim);
        }
      }
      block(g,side*(w/2+.07),13.8,0,.3,.25,d+.35,trim);
      block(g,side*(w/2+aisle+.09),7.5,0,.25,.2,d+.3,trim);
    }
    basilicaRoof(g,w+.65,d+.7,eave,ridge,0,'basilica-nave-roof',roofColor);
    for(const end of [-1,1])gable(g,w,eave,ridge,end*d/2,end>0,{color:wall,openings:[],lattice:false});
    const transept=o.transept||{width:31,depth:9,z:-10,height:11.5};
    block(g,0,.25,transept.z,transept.width,.5,transept.depth,C.stone);
    if(hollow){
      for(const side of [-1,1]){
        block(g,side*(transept.width/2-.15),transept.height/2,transept.z,.3,transept.height,transept.depth,wall);
        for(const end of [-1,1])block(g,side*(transept.width+w)/4,transept.height/2,transept.z+end*transept.depth/2,(transept.width-w)/2,transept.height,.3,wall);
      }
    }else block(g,0,transept.height/2,transept.z,transept.width,transept.height,transept.depth,wall);
    const tr=new THREE.Group();tr.rotation.y=Math.PI/2;tr.position.z=transept.z;g.add(tr);
    if(hollow){
      const wings=new THREE.Group();wings.name='basilica-transept-roof';tr.add(wings);
      const length=(transept.width-w)/2+.45;
      for(const side of [-1,1]){
        const wing=basilicaRoof(tr,transept.depth+.6,length,transept.height,transept.height+2.3,side*(w/2+length/2-.25),'basilica-transept-wing',roofColor);
        wings.add(wing);roofRecords.pop();
      }
      roofRecords.push({group:wings,parameters:{position:[...o.position],width:transept.depth+.6,depth:transept.width+.5,eaveHeight:transept.height,ridgeHeight:transept.height+2.3,color:roofColor},tiers:1,thickness:.17,ridgeOrnament:false});
    }else basilicaRoof(tr,transept.depth+.6,transept.width+.5,transept.height,transept.height+2.3,0,'basilica-transept-roof',roofColor);
    for(const end of [-1,1])gable(tr,transept.depth,transept.height,transept.height+2.3,end*transept.width/2,end>0,{color:wall,openings:[],lattice:false});
    for(const side of [-1,1]){
      arch(windows,side*(transept.width/2+.025),2.2,transept.z,2.6,6.8,side*Math.PI/2,'#818780',trim,{leaded:true});
      for(const dz of [-transept.depth/2+.3,transept.depth/2-.3])block(g,side*(transept.width/2+.08),transept.height/2,transept.z+dz,.35,transept.height,.4,trim);
    }
    const apse=o.apse||{radius:7.9,z:-20,height:11.5},ap=new THREE.Group();ap.name='basilica-apse';g.add(ap);
    const shell=add(ap,new THREE.CylinderGeometry(apse.radius,apse.radius,apse.height,12,1,hollow,Math.PI/2,Math.PI),wall);shell.position.set(0,apse.height/2,apse.z);
    if(hollow){
      shell.material=shell.material.clone();shell.material.side=THREE.DoubleSide;
      for(const side of [-1,1])block(ap,side*(apse.radius+w/2)/2,apse.height/2,apse.z,apse.radius-w/2,apse.height,.2,wall);
    }else block(ap,0,apse.height/2,apse.z,apse.radius*2,apse.height,.2,wall);
    const ar=new THREE.Group();ar.name='basilica-apse-roof';g.add(ar);
    const cap=add(ar,new THREE.ConeGeometry(apse.radius+.4,2.3,12,1,hollow,Math.PI/2,Math.PI),roofColor);cap.position.set(0,apse.height+1.15,apse.z);
    if(hollow)for(const side of [-1,1]){
      const shoulder=new THREE.Shape();shoulder.moveTo(side*w/2,apse.height);shoulder.lineTo(side*(apse.radius+.4),apse.height);shoulder.lineTo(side*w/2,apse.height+2.3*(1-w/2/(apse.radius+.4)));shoulder.closePath();
      const panel=add(ar,new THREE.ExtrudeGeometry(shoulder,{depth:.12,bevelEnabled:false}),roofColor);panel.position.z=apse.z;
    }else gable(ar,(apse.radius+.4)*2,apse.height,apse.height+2.3,apse.z,true,{color:roofColor,openings:[],lattice:false});
    roofRecords.push({group:ar,parameters:{position:[...o.position],width:apse.radius*2,depth:apse.radius,eaveHeight:apse.height,ridgeHeight:apse.height+2.3,color:roofColor},tiers:1,thickness:.15,ridgeOrnament:false});
    for(let i=0;i<5;i++){
      const angle=Math.PI/2+(i+.5)*Math.PI/5,x=Math.sin(angle)*(apse.radius+.04),z=apse.z+Math.cos(angle)*(apse.radius+.04);
      arch(ap,x,2.2,z,1.75,6.5,angle,C.glass[i%4],trim,{leaded:true});
    }
    const base=new THREE.Group();base.name='basilica-stone-base';g.add(base);const courses=[];
    for(const side of [-1,1]){
      const x=side*(w/2+aisle+.05);block(base,x,.6,0,.16,1.2,d,'#a7a79a');
      block(base,side*(transept.width/2+.05),.6,transept.z,.16,1.2,transept.depth,'#a7a79a');
      for(const y of [.3,.6,.9])courses.push(x+side*.085,y,-d/2,x+side*.085,y,d/2);
      for(let z=-d/2+.4;z<d/2;z+=.85)for(let row=0;row<4;row++)courses.push(x+side*.085,row*.3,z+(row%2)*.4,x+side*.085,(row+1)*.3,z+(row%2)*.4);
    }
    const apseBase=add(base,new THREE.CylinderGeometry(apse.radius+.08,apse.radius+.08,1.2,12,1,false,Math.PI/2,Math.PI),'#a7a79a');apseBase.position.set(0,.6,apse.z);
    lines(base,courses,'#8c8f83','basilica-stone-joints');
    const tower=o.tower||{},tw=tower.width||8.1,tz=tower.z||24.7,th=tower.height||32,spire=tower.spire||13;
    const shaft=new THREE.Group();shaft.name='basilica-bell-shaft';g.add(shaft);shaft.userData.count=1;
    const portalHeight=6.2,portalWidth=3.1;
    block(shaft,0,(th+portalHeight)/2,tz,tw,th-portalHeight,tw,wall);
    for(const side of [-1,1])block(shaft,side*(tw+portalWidth)/4,portalHeight/2,tz,(tw-portalWidth)/2,portalHeight,tw,wall);
    if(!hollow)block(shaft,0,portalHeight/2,tz-tw/2+.24,portalWidth,portalHeight,.48,wall);
    const facade=new THREE.Shape(),hw=tw/2,r=portalWidth/2;
    facade.moveTo(-hw,0);facade.lineTo(-hw,portalHeight);facade.lineTo(hw,portalHeight);facade.lineTo(hw,0);facade.lineTo(r,0);facade.lineTo(r,6-r);facade.absarc(0,6-r,r,0,Math.PI,false);facade.lineTo(-r,0);facade.closePath();
    const lintel=add(shaft,new THREE.ExtrudeGeometry(facade,{depth:.45,bevelEnabled:false}),wall);lintel.position.z=tz+tw/2-.45;
    const recessed=arch(shaft,0,.04,tz+tw/2-1.5,portalWidth,5.85,0,'#594f46',trim);recessed.group.name='basilica-recessed-door';
    if(hollow)recessed.pane.name='basilica-entrance-door';
    block(shaft,0,.08,tz,portalWidth,.16,tw,'#a49c8d');
    const towerWindows=new THREE.Group();shaft.add(towerWindows);
    for(let face=0;face<4;face++){
      const f=new THREE.Group();f.position.z=tz;f.rotation.y=face*Math.PI/2;towerWindows.add(f);
      for(const x of [-tw/2+.24,tw/2-.24])block(f,x,16,tw/2+.12,.35,32,.24,trim);
      for(const y of [9,23,26,31.6])block(f,0,y,tw/2+.1,tw+.5,.22,.32,trim);
      for(const x of [-2,0,2])arch(f,x,10,tw/2+.03,.84,11,0,'#756e65',trim);
      for(const x of [-1.55,1.55]){
        arch(f,x,27,tw/2+.04,2.1,3.6,0,'#626d65',trim);
        for(let y=27.15;y<29.75;y+=.27)block(f,x,y,tw/2+.2,1.92,.09,.11,'#b6b8a6');
      }
      const clock=add(f,new THREE.CylinderGeometry(.94,.94,.08,24),trim,face===0?'basilica-clock':undefined);clock.rotation.x=Math.PI/2;clock.position.set(0,24.5,tw/2+.12);
      rod(f,[0,24.5,tw/2+.19],[0,25.17,tw/2+.19],.045,C.wood);rod(f,[0,24.5,tw/2+.19],[.53,24.27,tw/2+.19],.045,C.wood);
      for(let i=0;i<12;i++){const a=i*Math.PI/6;rod(f,[Math.sin(a)*.73,24.5+Math.cos(a)*.73,tw/2+.19],[Math.sin(a)*.83,24.5+Math.cos(a)*.83,tw/2+.19],.025,C.wood);}
    }
    towerWindows.scale.y=th/32;
    const portal=arch(shaft,0,0,tz+tw/2+.04,portalWidth,6,0,'#594f46',trim,{frameWidth:.7,frameHeight:.35});portal.group.name='basilica-main-door';portal.pane.visible=false;
    block(g,0,.2,tz+tw/2+1.1,5.8,.4,2.3,C.stone);
    const sp=new THREE.Group();sp.name='basilica-spire';g.add(sp);
    block(sp,0,th+.12,tz,tw+1,.24,tw+1,trim);
    const cone=add(sp,new THREE.ConeGeometry((tw+.5)/Math.sqrt(2),spire,4),'#85928a');cone.rotation.y=Math.PI/4;cone.position.set(0,th+spire/2+.25,tz);
    for(const side of [-1,1])for(const x of [-tw/2,tw/2])rod(sp,[x,th+.3,tz+side*tw/2],[0,th+spire+.25,tz],.045,trim);
    const rooster=new THREE.Group();rooster.name='basilica-rooster';g.add(rooster);
    const tip=th+spire+.25;rod(rooster,[0,tip,tz],[0,tip+1.9,tz],.055,C.wood);
    rod(rooster,[-.7,tip+.6,tz],[.7,tip+.6,tz],.035,C.wood);
    const body=add(rooster,new THREE.SphereGeometry(.32,10,7),'#9e8a60');body.scale.set(1.25,.7,.45);body.position.set(0,tip+1.48,tz);
    const head=add(rooster,new THREE.SphereGeometry(.16,8,6),'#9e8a60');head.position.set(.31,tip+1.75,tz);
    rod(rooster,[.24,tip+1.55,tz],[.3,tip+1.75,tz],.1,'#9e8a60');rod(rooster,[-.23,tip+1.5,tz],[-.59,tip+1.88,tz],.13,'#9e8a60');
    const turrets=new THREE.Group();turrets.name='basilica-side-turrets';turrets.userData.count=2;g.add(turrets);
    for(const side of [-1,1]){
      const x=side*(tower.turretOffset||6.5),z=tower.turretZ||19.3,h=tower.turretHeight||20;
      block(turrets,x,h/2,z,3.25,h,3.25,wall);
      for(const dx of [-1.55,1.55])block(turrets,x+dx,h/2,z+1.68,.19,h,.19,trim);
      for(const y of [h-3.2,h])block(turrets,x,y,z,3.7,.22,3.7,trim);
      for(const dx of [-.8,.8])arch(turrets,x+dx,h-2.9,z+1.66,.6,2.1,0,'#788278',trim);
      arch(turrets,x,6,z+1.66,.7,h-10,0,'#788278',trim);
      const top=add(turrets,new THREE.ConeGeometry(2.5,3.5,8),roofColor);top.position.set(x,h+1.75,z);
      rod(turrets,[x,h+3.5,z],[x,h+4.2,z],.045,C.wood);
    }
    // Flatten only these new relief assemblies so compact can merge shared finishes.
    for(const assembly of [windows,towerWindows,turrets,ap]){
      g.updateMatrixWorld(true);const parts=[];assembly.traverse(m=>{if(m.isMesh)parts.push(m);});
      for(const part of parts)assembly.attach(part);
    }
    if(hollow){
      const reveal=new THREE.Group();reveal.name='basilica-reveal-walls';g.add(reveal);g.updateMatrixWorld(true);
      const walls=[];g.traverse(m=>{
        if(!m.isMesh||!m.material.color.equals(new THREE.Color(wall)))return;
        for(let p=m.parent;p&&p!==g;p=p.parent)if(p===shaft||p===turrets)return;
        walls.push(m);
      });
      for(const m of walls)reveal.attach(m);
      reveal.attach(windows);reveal.attach(buttresses);
    }
  });
  register('church_plaza',o=>{
    const g=root(o),[w,d]=o.size,h=o.height||.9,r=o.curveRadius||12,s=new THREE.Shape();
    s.moveTo(-w/2,d/2);s.lineTo(w/2,d/2);s.lineTo(w/2,-d/2+r);s.quadraticCurveTo(w/2,-d/2,w/2-r,-d/2);s.lineTo(-w/2+r,-d/2);s.quadraticCurveTo(-w/2,-d/2,-w/2,-d/2+r);s.closePath();
    const geo=new THREE.ExtrudeGeometry(s,{depth:h,bevelEnabled:false,curveSegments:24});geo.rotateX(-Math.PI/2);
    const slab=add(g,geo,o.color||'#d5cebb','basilica-raised-plaza');
    g.updateMatrixWorld(true);const surface=slab.geometry.clone().applyMatrix4(slab.matrixWorld);
    surface.setIndex(Array.from({length:surface.attributes.position.count},(_,i)=>i));walkableGeometries.push(surface);
    const joints=[];for(let z=-d/2+2;z<d/2-3;z+=3){const end=z>d/2-r?w/2-r+Math.sqrt(r*r-(z-d/2+r)**2)-.6:w/2-.6;joints.push(-end,h+.005,z,end,h+.005,z);}lines(g,joints,'#b9b19f','basilica-plaza-joints');
    const steps=o.steps||6;
    for(let i=0;i<steps;i++){
      const y=h*(steps-i)/steps,z=d/2+.35+i*.55;
      if(o.stepCurveDepth){
        const half=(o.stepWidth+i*.8)/2,depth=o.stepCurveDepth+i*.48,shape=new THREE.Shape();
        shape.moveTo(-half,-d/2+.2);shape.lineTo(half,-d/2+.2);
        for(let k=0;k<=48;k++){const a=k*Math.PI/48;shape.lineTo(half*Math.cos(a),-d/2-depth*Math.sin(a));}shape.closePath();
        const geometry=new THREE.ExtrudeGeometry(shape,{depth:y,bevelEnabled:false});geometry.rotateX(-Math.PI/2);
        const step=add(g,geometry,o.color||'#d5cebb','basilica-curved-step-'+i);g.updateMatrixWorld(true);
        const surface=geometry.clone().applyMatrix4(step.matrixWorld);surface.setIndex(Array.from({length:surface.attributes.position.count},(_,i)=>i));walkableGeometries.push(surface);
      }else pave(g,0,z,o.stepWidth||16,.58,o.color||'#d5cebb',y);
    }
  });
  register('church_monument',o=>{
    const g=root(o),h=o.columnHeight||5.4;
    block(g,0,.3,0,2.5,.6,2.5,C.stone);block(g,0,.85,0,1.8,.5,1.8,C.cream);
    const col=add(g,new THREE.CylinderGeometry(.55,.67,h,12),C.cream);col.position.y=1.1+h/2;
    block(g,0,1.1+h,0,1.5,.24,1.5,C.cream);
    const y=1.22+h,robe=add(g,new THREE.ConeGeometry(.46,2,12),'#e6e1d4');robe.position.set(0,y+1,0);
    const head=add(g,new THREE.SphereGeometry(.23,12,9),C.cream);head.position.set(0,y+2.03,0);
    const veil=add(g,new THREE.SphereGeometry(.31,12,9),'#d9d7c9');veil.scale.set(1,1.6,.7);veil.position.set(0,y+1.94,-.13);
    for(const side of [-1,1]){rod(g,[side*.3,y+1.45,0],[side*.09,y+1.57,.3],.07,C.cream);rod(g,[side*.09,y+1.57,.3],[0,y+1.76,.33],.055,C.cream);}
    const halo=add(g,new THREE.TorusGeometry(.48,.025,6,32),'#b5aa87','basilica-marian-halo');halo.position.set(0,y+2.15,-.21);
  });
  register('church_benches',o=>{
    const g=root(o),parts=[],rows=o.rows||6,columns=o.columns||4;
    for(let row=0;row<rows;row++)for(let col=0;col<columns;col++){
      const x=(col-(columns-1)/2)*(o.spacingX||3.1),z=(row-(rows-1)/2)*(o.spacingZ||1.55),w=o.width||2.5;
      for(const dx of [-w*.35,w*.35])parts.push({position:[x+dx,.26,z],scale:[.16,.52,.55]});
      parts.push({position:[x,.52,z],scale:[w,.12,.6]});parts.push({position:[x,.9,z-.25],scale:[w,.62,.12]});
    }
    instances(g,new THREE.BoxGeometry(1,1,1),parts,'basilica-outdoor-benches',o.color||'#b9af9d');
  });
  register('church_aframe',o=>{
    const g=root(o),[w,d]=o.size,eave=2.35,apex=eave+w/2*Math.sqrt(3);
    pave(g,0,0,w,d,'#c3bcac',.16);
    for(const s of [-1,1])block(g,s*(w/2-.4),.7,0,.5,1.15,d-.4,C.stone);
    const joints=[];
    for(const s of [-1,1]){
      for(const y of [1.25,2.8])block(g,s*(w/2-.42),y,0,.22,.12,d-.8,C.wood);
      const windows=new THREE.Group();windows.name='camly-coloured-windows';g.add(windows);
      const lead=new THREE.Group();lead.name='nave-window-leads';windows.add(lead);
      const step=(d-1.8)/28;
      for(const z of [-d/2+.68,d/2-.68])block(windows,s*(w/2-.3),1.95,z,.2,1.85,.5,C.wood);
      for(let k=0;k<28;k++){
        const z=-d/2+.9+(k+.5)*step,x=s*(w/2-.28),half=(step-.06)/2;
        if(o.glazing?.pattern==='diamond'){
          const corners=[[-.8,-half],[-.8,half],[.8,half],[.8,-half]];
          for(let j=0;j<4;j++){
            const a=corners[j],b=corners[(j+1)%4],geo=new THREE.BufferGeometry();
            geo.setAttribute('position',new THREE.Float32BufferAttribute([x,1.95,z,x,1.95+a[0],z+a[1],x,1.95+b[0],z+b[1]],3));geo.computeVertexNormals();
            const color=C.glass[(k+j)%4],pane=add(windows,geo,color);pane.material=pane.material.clone();pane.material.side=THREE.DoubleSide;pane.material.emissive.set(color);pane.material.emissiveIntensity=o.glazing.glow||0;
          }
          for(const side of [-1,1])rod(lead,[x,1.15,z+side*half],[x,2.75,z-side*half],.014,C.wood);
        }else block(windows,x,1.95,z,.045,1.6,step-.06,C.glass[k%4]);
        block(windows,s*(w/2-.24),1.95,z+step/2,.12,1.85,.1,C.wood);
      }
      for(let y=.35;y<1.25;y+=.28)joints.push(s*(w/2-.245),y,-d/2+.2,s*(w/2-.245),y,d/2-.2);
      for(let k=0;k<42;k++){const z=-d/2+.2+k*(d-.4)/42;joints.push(s*(w/2-.24),.15,z,s*(w/2-.24),1.27,z);}
    }
    lines(g,joints,C.joint,'camly-stone-courses');
    roof(g,w+.55,d+.5,eave,apex+.48,0,'camly-main-roof',{color:o.roofColor});
    gable(g,w-1,3.1,apex-.7,d/2-1.2,true,o.gable);
    gable(g,w+.55,eave-.1,apex+.4,-d/2+.5,false,o.interior?.endWall);
    block(g,0,1.2,-d/2+.5,w+.55,2.4,.4,C.stone);
    for(const s of [-1,1])block(g,s*(w+1)/4,1.6,d/2-1.08,(w-5)/2,3.05,.3,C.stone);
    block(g,0,1.65,d/2-.87,3,3.1,.16,'#403d36','camly-gable-door');
    // Side entrance is visible on the approach photos; it is not the gable porch.
    block(g,-w/2-.02,1.28,0,.16,2.55,2.3,'#403d36','camly-side-door');
    pave(g,-w/2-1.3,0,2.8,3.1,C.cream,.12);
    roof(g,16.5,6.1,.65,15.15,d/2+1.8,'camly-porch-roof',{color:o.porchRoofColor||o.roofColor});
    for(const side of [-1,1]){block(g,side*7.15,.65,d/2+1.7,1.1,1.3,5.1,C.stone);rod(g,[side*7.3,.65,d/2+4.82],[0,14.6,d/2+4.82],.13,C.wood);}
    rod(g,[-5.4,3.9,d/2+4.8],[5.4,3.9,d/2+4.8],.11,C.wood);
    rod(g,[-3.6,7.2,d/2+4.8],[3.6,7.2,d/2+4.8],.10,C.wood);
    for(const s of [-1,1])rod(g,[s*5.4,3.9,d/2+4.8],[-s*3.6,7.2,d/2+4.8],.065,C.wood);
    if(o.porchLattice){const lattice=new THREE.Group();lattice.name='parish-porch-lattice';g.add(lattice);const z=d/2+4.8;
      rod(lattice,[-2.05,10.2,z],[2.05,10.2,z],.09,C.wood);
      for(const s of [-1,1]){rod(lattice,[s*3.6,7.2,z],[-s*2.05,10.2,z],.075,C.wood);rod(lattice,[s*1.65,3.9,z],[s*1.65,10.9,z],.075,C.wood);}}
    pave(g,0,d/2+2.6,13,5,C.cream,.09);
    contactShadow(o.position[0],.02,o.position[2],32,32,.18);
  });
  // Masonry church family. All dimensions below are local metres, +z faces the street.
  function pointed(w,h){
    const s=new THREE.Shape(),r=w/2,spring=h-Math.min(w*.9,h*.55);
    s.moveTo(-r,0);s.lineTo(r,0);s.lineTo(r,spring);
    s.quadraticCurveTo(r,spring+(h-spring)*.55,0,h);
    s.quadraticCurveTo(-r,spring+(h-spring)*.55,-r,spring);s.closePath();return s;
  }
  function flattenDetails(g){
    g.updateWorldMatrix(true,true);const parts=[];
    g.traverse(m=>{if(m.isMesh&&!m.isInstancedMesh&&!m.name)parts.push(m);});
    for(const m of parts)g.attach(m);compact(g);
  }
  function surface(g,shape,color,z=0,name,depth=0){
    const m=add(g,depth?new THREE.ExtrudeGeometry(shape,{depth,bevelEnabled:false,curveSegments:16}):new THREE.ShapeGeometry(shape,20),color,name);
    m.position.z=z;m.material=m.material.clone();m.material.side=THREE.DoubleSide;return m;
  }
  function pointedPanel(g,x,y,z,w,h,options={}){
    const a=new THREE.Group();a.position.set(x,y,z);g.add(a);
    const t=options.trimWidth??.16,outer=pointed(w+2*t,h+t),hole=pointed(w,h);
    outer.holes.push(new THREE.Path(hole.getPoints(24)));surface(a,outer,options.trimColor||C.cream,.04,undefined,.1);
    const pane=surface(a,hole,options.glassColor||'#8d9b98',.065,options.paneName===false?undefined:'church-pointed-glass');
    if(options.leaded!==false){
      const pts=[],limit=h-Math.min(w*.9,h*.55);
      for(const xx of [-w*.25,0,w*.25])pts.push(xx,.05,.085,xx,limit+.12,.085);
      for(let yy=1;yy<limit;yy+=Math.max(.65,w*.5))pts.push(-w/2,yy,.085,w/2,yy,.085);
      for(let i=0;i<8;i++){const p=hole.getPoints(24),q=p[Math.floor((i+.5)*p.length/8)];pts.push(0,limit-.2,.085,q.x,q.y,.085);}
      lines(a,pts,options.leadColor||'#626e68','church-glass-leads');
      for(let yy=Math.max(options.doorHeight||0,1)+.65;yy<limit-.3;yy+=1.6){
        const diamond=new THREE.Shape();diamond.moveTo(0,yy+.45);diamond.lineTo(w*.17,yy);diamond.lineTo(0,yy-.45);diamond.lineTo(-w*.17,yy);diamond.closePath();
        surface(a,diamond,(options.glassPalette||C.glass)[Math.floor(yy)%4],.09);
      }
    }
    if(options.doorHeight){
      const dh=options.doorHeight;block(a,0,dh/2,.12,w*.94,dh,.12,options.doorColor||C.wood,'church-facade-door');
      for(const xx of [-w*.25,0,w*.25])block(a,xx,dh/2,.195,.045,dh-.08,.04,options.trimColor||C.cream);
      block(a,0,dh*.67,.195,w*.94,.045,.04,options.trimColor||C.cream);
    }
    return {group:a,pane};
  }
  function clipped(points,low,high){
    for(const [edge,sign] of [[low,1],[high,-1]]){
      const input=points;points=[];
      for(let i=0;i<input.length;i++){
        const a=input[i],b=input[(i+1)%input.length],inside=p=>sign*(p[1]-edge)>=-1e-6;
        if(inside(a))points.push(a);
        if(inside(a)!==inside(b)){const t=(edge-a[1])/(b[1]-a[1]);points.push([a[0]+t*(b[0]-a[0]),edge]);}
      }
    }
    return points;
  }
  function polygon(points,path=false){const s=path?new THREE.Path():new THREE.Shape();points.forEach(([x,y],i)=>i?s.lineTo(x,y):s.moveTo(x,y));s.closePath();return s;}
  function facade(g,o){
    const w=o.width??18,eave=o.eaveHeight??3,ridge=o.ridgeHeight??20,trim=o.trimColor||C.cream;
    const a=new THREE.Group();a.name='church-masonry-facade';g.add(a);
    const arches=o.arches||[],outline=[[-w/2,0],[w/2,0],[w/2,eave],[0,ridge],[-w/2,eave]],holes=[];
    for(const ar of arches)holes.push(pointed(ar.width,ar.height).getPoints(24).map(p=>[p.x+(ar.x||0),p.y+(ar.y||0)]));
    if(o.balcony){const b=o.balcony,w=b.doorWidth??1.2,h=b.doorHeight??2.5;holes.push([[-w/2,0],[w/2,0],[w/2,h],[-w/2,h]]);}
    if(o.rose){const r=o.rose;holes.push(Array.from({length:64},(_,i)=>[(r.x||0)+Math.cos(i*Math.PI/32)*r.radius,r.y+Math.sin(i*Math.PI/32)*r.radius]));}
    const bands=o.bands||[],cuts=[...new Set([0,ridge,...bands.flatMap(b=>[Math.max(0,b.from),Math.min(ridge,b.to)])])].sort((x,y)=>x-y);
    for(let i=1;i<cuts.length;i++){
      const lo=cuts[i-1],hi=cuts[i],points=clipped(outline,lo,hi);if(points.length<3)continue;
      const s=polygon(points);for(const h of holes){const p=clipped(h,lo,hi);if(p.length>=3)s.holes.push(polygon(p,true));}
      const band=bands.find(b=>(lo+hi)/2>=b.from&&(lo+hi)/2<=b.to);
      surface(a,s,band?.color||o.wallColor||'#e5dfcf',-.22,'church-facade-band-'+(band?bands.indexOf(band):'base'),.22);
    }
    for(const ar of arches)pointedPanel(a,ar.x||0,ar.y||0,0,ar.width,ar.height,{trimColor:trim,...ar});
    for(const side of [-1,1])rod(a,[side*w/2,eave,.13],[0,ridge,.13],o.edgeWidth??.095,trim);
    if(o.rose){
      const r=o.rose,rg=new THREE.Group();rg.name='church-rose-tracery';rg.position.set(r.x||0,r.y,.12);a.add(rg);
      const disc=new THREE.Shape();disc.absarc(0,0,r.radius,0,Math.PI*2);surface(rg,disc,r.glassColor||'#9aa8a1',-.06);
      for(const rr of [r.radius,r.radius*.8,r.radius*.27])add(rg,new THREE.TorusGeometry(rr,r.trimWidth??.065,6,64),trim);
      for(let i=0;i<(r.petals??8);i++){
        const angle=i*Math.PI*2/(r.petals??8),petal=add(rg,new THREE.TorusGeometry(r.radius*.25,.035,5,24),trim);
        petal.position.set(Math.cos(angle)*r.radius*.52,Math.sin(angle)*r.radius*.52,.02);
        rod(rg,[Math.cos(angle)*r.radius*.28,Math.sin(angle)*r.radius*.28,.035],[Math.cos(angle)*r.radius*.95,Math.sin(angle)*r.radius*.95,.035],.025,trim);
      }
    }
    if(o.lancets){const l=o.lancets,lg=new THREE.Group();lg.name='church-lancets';a.add(lg);
      for(const centre of l.centres||[0])for(let i=0;i<(l.count??3);i++)pointedPanel(lg,centre+(i-((l.count??3)-1)/2)*(l.spacing??.8),l.y,.025,l.width??.45,l.height??1.8,{trimColor:trim,glassColor:l.color||'#8a7971',leaded:false});
    }
    if(o.balcony){const b=o.balcony,bg=new THREE.Group();bg.name='church-box-balcony';a.add(bg);
      const bw=b.width??3.4,bd=b.depth??1.8,by=b.y??4.3,bh=b.parapetHeight??1.05;
      block(bg,0,by-.12,bd/2,bw,.24,bd,trim);
      for(const side of [-1,1])block(bg,side*(bw/2-.08),by+bh/2,bd/2,.16,bh,bd,b.color||o.wallColor||'#ba9290');
      block(bg,0,by+bh/2,bd-.08,bw,bh,.16,b.color||o.wallColor||'#ba9290');
      block(bg,0,by+bh,bd-.08,bw+.08,.065,.22,trim);
      block(bg,0,(b.doorHeight??2.5)/2,.07,b.doorWidth??1.2,b.doorHeight??2.5,.12,b.doorColor||C.wood,'church-lower-door');
      block(bg,0,(b.doorHeight??2.5)+.12,.3,(b.doorWidth??1.2)+.4,.16,.6,trim);
      for(const side of [-1,1])rod(bg,[side*bw*.32,by-.2,bd*.85],[side*bw*.32,by-1,.1],.09,b.color||o.wallColor||'#ba9290');
    }
    if(o.cross!==false){const c=o.cross||{};block(a,0,ridge+(c.height??1)*.45,.02,c.width??.13,c.height??1,.13,trim);block(a,0,ridge+(c.height??1)*.65,.02,c.arm??.65,.13,.13,trim);}
    return a;
  }
  register('church_facade',o=>facade(root(o),o));
  function dormers(g,w,d,eave,ridge,settings,name,wallColor,roofColor){
    const dg=new THREE.Group();dg.name=name;g.add(dg);
    const count=settings.count??5,dw=settings.width??1.8,dh=settings.height??1.8,projection=settings.projection??1.8;
    const half=w/2,x=half-projection,base=eave+(ridge-eave)*(projection/half)-.1;
    for(const side of settings.sides||[-1,1])for(let i=0;i<count;i++){
      const z=(i-(count-1)/2)*(settings.spacing??((d-4)/count)),bay=new THREE.Group();bay.position.set(side*x,base,z);bay.rotation.y=side*Math.PI/2;dg.add(bay);
      block(bay,0,dh/2,0,dw,dh,projection,wallColor);
      const face=new THREE.Shape();face.moveTo(-dw/2,dh);face.lineTo(dw/2,dh);face.lineTo(0,dh+dw*.65);face.closePath();surface(bay,face,wallColor,projection/2);
      pointedPanel(bay,0,.18,projection/2+.025,dw*.56,dh*.82,{trimColor:C.cream,glassColor:'#7c8982',leaded:false,paneName:false});
      const slope=Math.hypot(dw*.65,dw/2+.12),angle=Math.atan2(dw*.65,dw/2+.12);
      for(const s of [-1,1]){const m=block(bay,s*(dw/4+.06),dh+dw*.325,0,slope,.11,projection+.25,roofColor);m.rotation.z=-s*angle;}
    }
    flattenDetails(dg);return dg;
  }
  register('church_gabled',o=>{
    const g=root(o),[w,d]=o.size,eave=o.eaveHeight??3,ridge=o.ridgeHeight??(eave+w*.9),wall=o.wallColor||'#e5dfcf',trim=o.trimColor||C.cream,base=o.baseHeight??.18;
    g.name='church-gabled-'+o.id;pave(g,0,0,w,d,o.baseColor||C.stone,base);
    const bands=o.sideBands||[{from:base,to:eave,color:wall}],walls=new THREE.Group();walls.name='church-gabled-reveal-walls';g.add(walls);
    for(const side of [-1,1]){
      for(const b of bands)block(walls,side*(w/2-.14),(b.from+b.to)/2,0,.28,b.to-b.from,d,b.color);
      const windows=o.sideWindows??{};
      if(windows!==false)for(let i=0;i<(windows.count??7);i++){
        const a=new THREE.Group();a.position.set(side*(w/2+.012),windows.y??1.4,(i-((windows.count??7)-1)/2)*(windows.spacing??((d-4)/(windows.count??7))));a.rotation.y=side*Math.PI/2;walls.add(a);
        pointedPanel(a,0,0,0,windows.width??1.1,windows.height??2,{trimColor:trim,glassColor:windows.color||'#89958c'});
      }
    }
    const roofGroup=roof(g,w+.5,d+.6,eave,ridge,0,'church-gabled-roof',{color:o.roofColor||'#817d72',edgeColor:o.roofEdgeColor||trim,courseColor:o.roofCourseColor||'#989489',ridgeColor:o.roofEdgeColor||trim});
    const fa=facade(walls,{width:w,eaveHeight:eave,ridgeHeight:ridge,wallColor:wall,trimColor:trim,...o.facade});fa.position.z=d/2;
    const rear=facade(g,{width:w,eaveHeight:eave,ridgeHeight:ridge,wallColor:wall,trimColor:trim,cross:false,...o.rear});rear.position.z=-d/2;rear.rotation.y=Math.PI;
    if(o.dormers)dormers(roofGroup,w,d,eave,ridge,o.dormers,'church-roof-dormers',wall,o.roofColor||'#817d72');
    if(o.buttresses){
      const b=o.buttresses,bg=new THREE.Group();bg.name='church-stone-buttresses';g.add(bg);
      const bh=b.height??eave,bw=b.width??.7,p=b.projection??1,count=b.count??7,joints=[];
      for(const side of [-1,1])for(let i=0;i<count;i++){
        const z=(i-(count-1)/2)*(b.spacing??((d-2)/count)),x=side*(w/2+p/2-.05);
        block(bg,x,bh*.22,z,p,bh*.44,bw,b.color||C.stone);block(bg,x-side*p*.16,bh*.68,z,p*.68,bh*.48,bw*.86,b.color||C.stone);
        const cap=block(bg,x-side*p*.16,bh*.94,z,p*.77,.18,bw+.12,b.capColor||trim);cap.rotation.z=-side*.15;
        for(let y=.3;y<bh*.42;y+=.4)joints.push(x+side*p/2+.005,y,z-bw/2,x+side*p/2+.005,y,z+bw/2);
      }
      lines(bg,joints,b.jointColor||C.joint,'church-buttress-joints');
    }
  });
  function stairs(g,o){
    const sg=new THREE.Group();sg.name=o.name||'church-curved-stairs';g.add(sg);
    const p=o.points||[[0,5],[0,2],[0,0]],curve=new THREE.QuadraticBezierCurve3(...p.map(([x,z])=>new THREE.Vector3(x,0,z))),n=o.steps??24,w=o.width??1.5,h=o.height??4.3,bottom=o.bottom??0,rail=o.railHeight??.8,railPts=[[],[]];
    for(let i=0;i<n;i++){
      const a=curve.getPoint(i/n),b=curve.getPoint((i+1)/n),tangent=b.clone().sub(a),normal=new THREE.Vector3(-tangent.z,0,tangent.x).normalize(),y=bottom+h*(i+1)/n;
      const step=pave(sg,(a.x+b.x)/2,(a.z+b.z)/2,w,tangent.length()+.035,o.color||'#ae7b68',y);step.rotation.y=Math.atan2(tangent.x,tangent.z);
      sg.updateWorldMatrix(true,true);walkableGeometries.pop().dispose();walkableGeometries.push(step.geometry.clone().applyMatrix4(step.matrixWorld));
      for(const [k,side] of [-1,1].entries()){
        const x=(a.x+b.x)/2+side*normal.x*(w/2+.06),z=(a.z+b.z)/2+side*normal.z*(w/2+.06);
        const parapet=block(sg,x,y+rail/2,z,.14,rail,tangent.length()+.08,o.railColor||C.cream);parapet.rotation.y=step.rotation.y;
        railPts[k].push([x,y+rail,z]);
      }
    }
    for(const points of railPts)for(let i=1;i<points.length;i++)rod(sg,points[i-1],points[i],.065,o.capColor||C.cream);
    return sg;
  }
  register('church_stairs',o=>stairs(root(o),o));
  register('church_forecourt',o=>{
    const g=root(o),[w,d]=o.size||[22,15],color=o.color||'#d9d2c1';pave(g,0,0,w,d,color,.08);
    const pattern=o.pattern||{},spacing=pattern.spacing??1.2,tiles=[],joints=[];
    for(let x=-w/2+spacing/2;x<w/2;x+=spacing)for(let z=-d/2+spacing/2;z<d/2;z+=spacing){
      const ix=Math.round((x+w/2)/spacing),iz=Math.round((z+d/2)/spacing);
      if((ix+iz)%4===0)tiles.push({position:[x,.085,z],scale:[spacing*.7,.012,spacing*.7],rotation:[0,Math.PI/4,0],color:pattern.color||'#bba99a'});
    }
    for(let z=-d/2;z<d/2;z+=spacing)joints.push(-w/2,.09,z,w/2,.09,z);
    for(let x=-w/2;x<w/2;x+=spacing)joints.push(x,.09,-d/2,x,.09,d/2);
    instances(g,new THREE.BoxGeometry(1,1,1),tiles,'church-court-pattern');lines(g,joints,pattern.jointColor||'#bdb5a7');
    if(o.podium){const p=o.podium,s=o.stairs||{},pd=p.depth??3,ph=p.height??1.2,z=-d/2+pd/2,n=s.steps??8,sd=s.depth??3;
      pave(g,0,z,p.width??w,pd,p.color||color,ph);
      for(let i=0;i<n;i++)pave(g,0,-d/2+pd+(i+.5)*sd/n,s.width??w-.8,sd/n+.025,s.color||color,ph*(1-i/n));
    }
  });
  register('parish_arcade',o=>{
    const g=root(o),[w,d]=o.size,storeys=o.storeys??3,sh=o.storeyHeight??3.6,h=storeys*sh,bays=o.bays??6,spacing=(d-.8)/bays,wall=o.wallColor||'#e1d4be',trim=o.trimColor||C.cream,rc=o.roofColor||'#8c8174',veranda=o.veranda!==false;
    pave(g,0,0,w+.4,d+.4,o.baseColor||C.stone,.18);
    block(g,0,h/2,0,w-(veranda?3:0),h,d,wall);
    const ag=new THREE.Group();ag.name=veranda?'parish-stacked-arcades':'parish-stacked-windows';ag.userData={storeys,windowStyle:o.windowStyle||'pointed'};g.add(ag);
    function windowPanel(a,width,height,y){
      if(o.windowStyle!=='rectangular'){pointedPanel(a,0,y,.015,width,height,{trimColor:trim,glassColor:o.windowColor||'#7c8983',leaded:false,paneName:false});return;}
      block(a,0,y+height/2,.035,width,height,.07,o.windowColor||'#7c8983');
      for(const x of [-width/2,0,width/2])block(a,x,y+height/2,.09,.065,height+.14,.08,trim);
      for(const yy of [y,y+height*.55,y+height])block(a,0,yy,.09,width+.16,.075,.1,trim);
    }
    for(let floor=0;floor<storeys;floor++){
      const fy=floor*sh;
      if(veranda)block(ag,0,fy+.12,0,w,.2,d+.15,trim);
      for(const side of [-1,1]){
        for(let i=0;i<bays;i++){
          const z=(i-(bays-1)/2)*spacing,a=new THREE.Group();a.position.set(side*(w/2+.02),fy,z);a.rotation.y=side*Math.PI/2;ag.add(a);
          if(veranda){
            const panel=polygon([[-spacing/2,0],[spacing/2,0],[spacing/2,sh],[-spacing/2,sh]]),hole=pointed(spacing-.45,sh-.38);panel.holes.push(new THREE.Path(hole.getPoints(24).map(p=>p.add(new THREE.Vector2(0,.12)))));
            surface(a,panel,wall,0,undefined,.2);
            const frame=pointed(spacing-.27,sh-.28),inner=pointed(spacing-.45,sh-.38);frame.holes.push(new THREE.Path(inner.getPoints(24)));surface(a,frame,trim,.23);
            if(floor){block(a,0,.5,-.03,spacing-.4,.75,.12,trim);for(let k=0;k<9;k++)block(a,(k-4)*(spacing-.65)/8,.58,.05,.04,.65,.08,wall);}
            block(a,0,sh*.45,-1.55,spacing*.48,sh*.65,.06,o.windowColor||'#7d8880');
          }else{
            windowPanel(a,Math.min(spacing*.55,1.5),sh*.6,sh*.24);
            for(const s of [-1,1])block(a,s*Math.min(spacing*.36,1.05),sh*.53,.09,.24,sh*.6,.08,o.shutterColor||'#7e786b');
          }
        }
        block(ag,side*(w/2+.12),fy+sh-.06,0,.25,.16,d+.3,trim);
      }
      for(const end of [-1,1])for(const x of [-w*.27,0,w*.27]){
        const a=new THREE.Group();a.position.set(x,fy,end*(d/2+.025));if(end<0)a.rotation.y=Math.PI;ag.add(a);
        windowPanel(a,1.2,sh*.68,.5);
      }
    }
    flattenDetails(ag);
    const rise=o.roofRise??2.6,rg=roof(g,w+.5,d+.5,h,h+rise,0,'parish-wing-roof',{color:rc,edgeColor:trim,courseColor:o.roofCourseColor||'#a99b88',ridgeColor:rc});
    for(const end of [-1,1]){const fa=facade(g,{width:w,eaveHeight:0,ridgeHeight:rise,wallColor:wall,trimColor:trim,cross:false});fa.position.set(0,h,end*d/2);if(end<0)fa.rotation.y=Math.PI;}
    if(o.dormers)dormers(rg,w,d,h,h+rise,o.dormers,'parish-roof-dormers',wall,rc);
    if(o.roofGables){const gg=new THREE.Group();gg.name='parish-roof-gables';rg.add(gg);
      const crossRoofs=new THREE.Group();crossRoofs.name='parish-cross-gable-roofs';gg.add(crossRoofs);
      for(let i=0;i<o.roofGables;i++){
        const bay=d/o.roofGables,gr=o.gableRise??2.1,cg=new THREE.Group();cg.position.set(0,h,(i-(o.roofGables-1)/2)*bay);cg.rotation.y=Math.PI/2;crossRoofs.add(cg);
        for(const side of [-1,1]){const m=block(cg,side*bay/4,gr/2,0,Math.hypot(bay/2,gr),.14,w+.5,rc);m.rotation.z=-side*Math.atan2(gr,bay/2);}
      }
      flattenDetails(crossRoofs);
      for(const side of [-1,1])for(let i=0;i<o.roofGables;i++){
        const fa=facade(gg,{width:d/o.roofGables,eaveHeight:0,ridgeHeight:o.gableRise??2.1,wallColor:wall,trimColor:trim,cross:false});
        fa.position.set(side*(w/2+.15),h,(i-(o.roofGables-1)/2)*d/o.roofGables);fa.rotation.y=side*Math.PI/2;
      }
    }
    if(o.externalStair){const s=o.externalStair,side=s.side??1,z=s.z??(d/2-1),x=side*(w/2+1.4);
      const st=stairs(g,{points:s.points||[[x+side*3,z+3],[x+side*4,z-4],[side*(w/2-.6),z-5]],height:s.height??sh,width:s.width??1.6,steps:s.steps??24,color:s.color||'#aba99e',railColor:s.railColor||trim});st.name='parish-external-stair';
    }
    if(o.porch){const p=o.porch,pg=new THREE.Group();pg.position.set((p.side??-1)*(w/2+.8),0,p.z??0);pg.rotation.y=(p.side??-1)*Math.PI/2;g.add(pg);
      facade(pg,{width:p.width??4.4,eaveHeight:p.height??4,ridgeHeight:(p.height??4)+2,wallColor:wall,trimColor:trim,cross:false,arches:[{x:0,y:0,width:2,height:3.4,doorHeight:2.6,leaded:false}]});
    }
  });
  register('church_shrine',o=>{
    const g=root(o),r=o.pavingRadius??3.2,disc=add(g,new THREE.CylinderGeometry(r,r,.12,64),o.pavingColor||'#d4ccba');disc.position.y=.06;
    g.updateWorldMatrix(true,true);walkableGeometries.push(disc.geometry.clone().applyMatrix4(disc.matrixWorld));
    const joint=[];for(let i=0;i<24;i++){const a=i*Math.PI/12; joint.push(Math.cos(a)*r*.45,.125,Math.sin(a)*r*.45,Math.cos(a)*r,.125,Math.sin(a)*r);}lines(g,joint,C.joint);
    const ph=o.plinthHeight??.8,pw=o.plinthWidth??1.5;block(g,0,ph/2,0,pw,ph,pw,o.plinthColor||C.stone);block(g,0,ph,0,pw+.2,.12,pw+.2,C.cream);
    const statue=new THREE.Group();statue.name='church-shrine-statue';statue.userData.pose=o.pose||'prayer';statue.position.y=ph+.06;statue.scale.setScalar(o.statueScale??1.4);g.add(statue);
    const sc=o.statueColor||'#dedccf',robe=add(statue,new THREE.ConeGeometry(.36,1.6,12),sc);robe.position.y=.8;
    const veil=add(statue,new THREE.SphereGeometry(.27,12,10),o.veilColor||'#ccd1c5','church-shrine-veil');veil.position.set(0,1.6,-.1);veil.scale.set(1,1.6,.65);
    const head=add(statue,new THREE.SphereGeometry(.19,12,10),sc);head.position.set(0,1.77,.025);
    for(const side of [-1,1]){
      const shoulder=[side*.17,1.43,.015],elbow=[side*(o.pose==='open'?.4:.28),1.13,.1],hand=[side*(o.pose==='open'?.52:.045),o.pose==='open'?1.03:1.4,.24];
      rod(statue,shoulder,elbow,.075,sc);rod(statue,elbow,hand,.055,sc);
    }
    if(o.halo){const halo=add(statue,new THREE.TorusGeometry(.34,.025,6,40),o.haloColor||'#b7ad8d');halo.position.set(0,1.9,-.22);}
    if(o.ring!==false){const q=o.ring||{},w=q.width??3.8,h=q.height??6,t=q.thickness??.22,ring=new THREE.Shape(),hole=new THREE.Path();
      ring.absellipse(0,0,w/2,h/2,0,Math.PI*2);hole.absellipse(0,0,w/2-t,h/2-t,0,Math.PI*2,true);ring.holes.push(hole);
      const m=surface(g,ring,q.color||C.cream,q.z??-.4,'church-oval-ring',q.depth??.22);m.position.y=(q.bottom??.2)+h/2;
      for(const inset of [t*.25,t*.75]){const pts=[];for(let i=0;i<80;i++){const a=i*Math.PI/40,b=(i+1)*Math.PI/40;pts.push(Math.cos(a)*(w/2-inset),m.position.y+Math.sin(a)*(h/2-inset),(q.z??-.4)+(q.depth??.22)+.006,Math.cos(b)*(w/2-inset),m.position.y+Math.sin(b)*(h/2-inset),(q.z??-.4)+(q.depth??.22)+.006);}lines(g,pts,q.lineColor||'#89978e');}
    }
  });
  register('camly_gate',o=>{
    const g=root(o),w=o.width||5.5;
    for(const s of [-1,1]){block(g,s*w/2,1.9,0,.32,3.8,.4,C.stone);block(g,s*w/2,3.87,0,.44,.14,.52,C.cream);}
    for(const s of [-1,1])for(let i=0;i<8;i++)block(g,s*(w/2+.32+i*.55),1.15,0,.06,2.3,.07,'#8b6f5c');
    for(const s of [-1,1])for(const y of [.35,1.85])block(g,s*(w/2+2.3),y,0,4.6,.08,.08,'#8b6f5c');
    // Two gate leaves stand open against the planted borders.
    for(const s of [-1,1]){for(let i=0;i<7;i++)block(g,s*(w/2-.12),1.05,.2+i*.34,.07,2.1,.055,'#8b6f5c');for(const y of [.3,1.8])block(g,s*(w/2-.12),y,1.2,.08,.08,2.3,'#8b6f5c');}
    block(g,0,3.55,0,w+.5,.9,.15,'#446a87');
    if(o.sign){const canvas=document.createElement('canvas');canvas.width=1024;canvas.height=160;const c=canvas.getContext('2d');c.fillStyle='#446a87';c.fillRect(0,0,1024,160);c.fillStyle='#f2ecda';c.font='bold 66px Georgia';c.textAlign='center';let f=66;while(c.measureText(o.sign).width>980&&f>2)c.font=`bold ${--f}px Georgia`;c.fillText(o.sign,512,105);const t=new THREE.CanvasTexture(canvas);t.colorSpace=THREE.SRGBColorSpace;const m=new THREE.Mesh(new THREE.PlaneGeometry(w+.43,.84),new THREE.MeshBasicMaterial({map:t,side:THREE.DoubleSide}));m.position.set(0,3.55,.085);m.name='camly-blue-sign';g.add(m);}
    pave(g,0,.5,w,2.6);
  });
  register('parish_ground',o=>{
    const g=root(o);block(g,0,.006,0,o.size[0],.012,o.size[1],o.color||'#c1c7af');
  });
  register('parish_bed',o=>{
    const g=root(o),[w,d]=o.size;
    block(g,0,.05,0,w,.1,d,'#b9bea7');
    if(o.border!==false){for(const s of [-1,1]){block(g,s*(w/2-.07),.12,0,.14,.24,d,C.stone);block(g,0,.12,s*(d/2-.07),w,.24,.14,C.stone);}}
    if(o.shrubs){
      const hedges=[],flowers=[];
      for(let z=-d/2+.6;z<d/2-.3;z+=.75){hedges.push({position:[0,.58,z],scale:[w-.5,.78,.8],color:'#919f78'});
        for(const s of [-1,1])flowers.push({position:[s*(w/2-.35),1.03,z],scale:[.16,.12,.16],color:['#b49a96','#b7a071','#e7dfcc'][flowers.length%3]});}
      instances(g,new THREE.BoxGeometry(1,1,1),hedges,'parish-shrub-instances');
      instances(g,new THREE.IcosahedronGeometry(1,0),flowers,'parish-flower-instances');
    }
  });
  register('parish_planting',o=>{
    const g=root(o),[w,d]=o.size,spacing=o.spacing||2.6,shrubs=[],clipped=[],flowers=[];
    const hash=(x,z)=>{const n=Math.sin(x*127.1+z*311.7)*43758.5453;return n-Math.floor(n);};
    const local=(p,object)=>new THREE.Vector3(p.x-object.position[0],0,p.z-object.position[2]).applyAxisAngle(new THREE.Vector3(0,1,0),-(object.rotation||0)*Math.PI/180);
    function clear(p,r){
      for(const object of place.objects){
        if(!object.position)continue;const q=local(p,object),t=object.type;
        if(t==='church_aframe'&&((Math.abs(q.x)<object.size[0]/2+r+.45&&Math.abs(q.z)<object.size[1]/2+r+.4)||(Math.abs(q.x)<8.9+r&&q.z>14-r&&q.z<21.5+r)))return false;
        if(['church_gabled','parish_arcade','church_forecourt'].includes(t)){
          const size=object.size||[22,15];
          if(Math.abs(q.x)<size[0]/2+r+.4&&Math.abs(q.z)<size[1]/2+r+.4)return false;
        }
        if(t==='church_shrine'&&Math.hypot(q.x,q.z)<(object.pavingRadius??3.2)+r)return false;
        if(t==='church_stairs'&&(object.points||[[0,5],[0,2],[0,0]]).some(([x,z])=>Math.hypot(q.x-x,q.z-z)<(object.width??1.5)+r))return false;
        if(['parish_house','parish_path','parish_playground'].includes(t)||(t==='parish_bed'&&object.border!==false)){
          const width=t==='parish_playground'?12:object.size[0],depth=t==='parish_playground'?10:t==='parish_house'?object.size[2]:object.size[1];
          if(Math.abs(q.x)<width/2+r+.3&&Math.abs(q.z)<depth/2+r+.3)return false;
        }
        if(t==='formal_garden'&&Math.hypot(q.x,q.z)<object.radius+r+.35)return false;
        if(['bell_frame','marian_grotto','garden_statue','camly_gate'].includes(t)&&Math.hypot(q.x,q.z)<(t==='marian_grotto'?4.4:t==='camly_gate'?5.5:t==='bell_frame'?3:2)+r)return false;
      }
      for(const leg of place.route)for(let i=1;i<leg.length;i++){
        const a=new THREE.Vector2(...leg[i-1]),v=new THREE.Vector2(...leg[i]).sub(a),p2=new THREE.Vector2(p.x,p.z),t=THREE.MathUtils.clamp(p2.clone().sub(a).dot(v)/v.lengthSq(),0,1);
        if(p2.distanceTo(a.addScaledVector(v,t))<1.75+r)return false;
      }
      return true;
    }
    for(let x=-w/2+.9;x<w/2;x+=spacing)for(let z=-d/2+.9;z<d/2;z+=spacing){
      const cluster=Math.sin(x/(o.clusterScale||9))*Math.cos(z/(o.clusterScale||9));
      if(o.density!==undefined&&hash(x+13,z+29)>o.density*(.6+.8*Math.max(0,cluster)))continue;
      const px=x+(hash(x,z)-.5)*1.8,pz=z+(hash(z,x)-.5)*1.8,r=1.1+hash(x+2,z)*.55,p=g.localToWorld(new THREE.Vector3(px,0,pz));
      if(!clear(p,r))continue;
      const h=.62+hash(x,z+7)*.65,isClipped=hash(x+41,z-17)<(o.clippedShare??0),yaw=isClipped?(o.hedgeRotation||0)*Math.PI/180:hash(x,z)*Math.PI;
      (isClipped?clipped:shrubs).push({position:[px,h/2+.025,pz],scale:[r,h/2,r*(isClipped?.36:.85)],rotation:[0,yaw,0],color:['#879575','#9ba582','#a7b08a'][(shrubs.length+clipped.length)%3]});
      if(hash(x+8,z)<(o.flowers??.32))for(let k=0;k<4;k++){
        const a=k*Math.PI/2,offset=isClipped?new THREE.Vector3((k-1.5)*r*.38,0,0).applyAxisAngle(new THREE.Vector3(0,1,0),yaw):new THREE.Vector3(Math.cos(a)*r*.48,0,Math.sin(a)*r*.48);
        flowers.push({position:[px+offset.x,(isClipped?h:h*.86)+.06,pz+offset.z],scale:[.15,.11,.15],color:['#b49a96','#b7a071','#e7dfcc'][k%3]});
      }
    }
    instances(g,new THREE.IcosahedronGeometry(1,1),shrubs,'parish-shrub-instances');
    const profile=new THREE.Shape();profile.moveTo(-.72,-.9);profile.lineTo(.72,-.9);profile.quadraticCurveTo(.9,-.9,.9,-.72);profile.lineTo(.9,.72);profile.quadraticCurveTo(.9,.9,.72,.9);profile.lineTo(-.72,.9);profile.quadraticCurveTo(-.9,.9,-.9,.72);profile.lineTo(-.9,-.72);profile.quadraticCurveTo(-.9,-.9,-.72,-.9);
    const hedgeGeometry=new THREE.ExtrudeGeometry(profile,{depth:1.8,steps:1,bevelEnabled:true,bevelThickness:.1,bevelSize:.1,bevelSegments:2,curveSegments:3});hedgeGeometry.translate(0,0,-.9);hedgeGeometry.rotateX(-Math.PI/2);
    instances(g,hedgeGeometry,clipped,'parish-clipped-instances');
    instances(g,new THREE.IcosahedronGeometry(1,0),flowers,'parish-flower-instances');
  });
  register('parish_grove',o=>{
    const g=root(o),trunks=[],crowns=[];
    for(const [cx,cz,h=11] of o.clusters)for(let k=0;k<(o.treesPerCluster||3);k++){
      const a=k*2.4+cx*.1,r=k?2.8:0,x=cx+Math.cos(a)*r,z=cz+Math.sin(a)*r,height=h*(1-k*.08);
      trunks.push({position:[x,height/2,z],scale:[.14,height,.14]});
      for(let j=0;j<5;j++){const t=j/4,size=(2.4-t*.85)*(1-k*.06);crowns.push({position:[x+Math.sin(j*2.4)*.55,height*(.73+t*.24),z+Math.cos(j*2.1)*.45],scale:[size,.34,size*.82],rotation:[0,a+j*.7,0],color:j%2?'#889777':'#98a486'});}
    }
    instances(g,new THREE.CylinderGeometry(1,1,1,6),trunks,'parish-grove-trunks','#928679');
    instances(g,new THREE.IcosahedronGeometry(1,1),crowns,'parish-grove-crowns');
  });
  register('parish_path',o=>{
    const g=root(o);pave(g,0,0,o.size[0],o.size[1],o.color||C.cream,.065);
    const p=[];for(let z=-o.size[1]/2;z<o.size[1]/2;z+=1.1)p.push(-o.size[0]/2,.069,z,o.size[0]/2,.069,z);lines(g,p,'#bdb5a5');
  });
  register('parish_walkway',o=>{
    const g=root(o),w=o.width||2.8,joints=[];
    for(const leg of (o.followRoute?place.route:o.legs)){
      for(let i=1;i<leg.length;i++){
        const a=new THREE.Vector2(...leg[i-1]),b=new THREE.Vector2(...leg[i]),v=b.clone().sub(a),length=v.length(),n=new THREE.Vector2(-v.y,v.x).normalize();
        const m=pave(g,(a.x+b.x)/2,(a.y+b.y)/2,w,length,o.color||'#d5cebb',.08);m.rotation.y=Math.atan2(v.x,v.y);
        g.updateMatrixWorld(true);walkableGeometries.pop().dispose();walkableGeometries.push(m.geometry.clone().applyMatrix4(m.matrixWorld));
        for(let d=1.2;d<length-.6;d+=1.2){const p=a.clone().addScaledVector(v,d/length);joints.push(p.x+n.x*w/2,.084,p.y+n.y*w/2,p.x-n.x*w/2,.084,p.y-n.y*w/2);}
      }
      for(const p of leg){const cap=add(g,new THREE.CylinderGeometry(w/2,w/2,.08,20),o.color||'#d5cebb');cap.position.set(p[0],.04,p[1]);g.updateMatrixWorld(true);walkableGeometries.push(cap.geometry.clone().applyMatrix4(cap.matrixWorld));}
    }
    lines(g,joints,'#b4ac98','parish-paving-joints');
  });
  register('formal_garden',o=>{
    const g=root(o),r=o.radius||6;const disc=add(g,new THREE.CylinderGeometry(r,r,.08,64),'#c8c1ad');disc.position.y=.04;
    const ring=new THREE.Shape();ring.absarc(0,0,r-.5,0,Math.PI*2);const hole=new THREE.Path();hole.absarc(0,0,r-1.25,0,Math.PI*2,true);ring.holes.push(hole);
    const m=add(g,new THREE.ExtrudeGeometry(ring,{depth:.35,bevelEnabled:false,curveSegments:32}),C.green);m.rotation.x=-Math.PI/2;m.position.y=.08;
    for(let i=0;i<6;i++){const a=i*Math.PI/3,s=new THREE.Shape();s.moveTo(Math.cos(a+.14)*1.35,Math.sin(a+.14)*1.35);s.absarc(0,0,r-1.7,a+.14,a+.9,false);s.lineTo(Math.cos(a+.9)*1.35,Math.sin(a+.9)*1.35);s.absarc(0,0,1.35,a+.9,a+.14,true);s.closePath();const p=add(g,new THREE.ExtrudeGeometry(s,{depth:.24,bevelEnabled:false}),C.green);p.rotation.x=-Math.PI/2;p.position.y=.08;}
    const hub=add(g,new THREE.CylinderGeometry(.75,.75,.4,16),C.green);hub.position.y=.24;
    if(o.flowers){const blooms=[];for(let i=0;i<6;i++)for(let j=0;j<5;j++){const a=i*Math.PI/3+.28+j*.1,rr=r*(.38+j%2*.17);blooms.push({position:[Math.cos(a)*rr,.43,Math.sin(a)*rr],scale:[.16,.1,.16],color:['#b49a96','#b7a071','#e7dfcc'][j%3]});}instances(g,new THREE.IcosahedronGeometry(1,0),blooms,'parish-flower-instances');}
  });
  register('parish_house',o=>{
    const g=root(o),[w,h,d]=o.size;block(g,0,.14,0,w+.3,.28,d+.3,C.stone);block(g,0,h/2+.2,0,w,h,d,o.wallColor||'#e8decb');
    const slope=Math.hypot(w/2,1.4);for(const s of [-1,1]){const m=block(g,s*w/4,h+.9,0,slope,.12,d+.6,o.roofColor||'#6b6157');m.rotation.z=-s*Math.atan2(1.4,w/2);}
    const doors=new THREE.Group();doors.name='parish-house-doors';g.add(doors);
    for(const s of [-1,1]){
      block(doors,s*(w/2+.025),1.35,0,.07,2.3,1.15,'#645b4d');block(g,s*(w/2+.075),2.56,0,.14,.12,1.4,C.cream);
      for(let z=-d/2+1.8;z<d/2-1;z+=3.2){if(Math.abs(z)<1.8)continue;block(g,s*(w/2+.02),1.8,z,.07,1.25,1.6,'#7f8d82');for(const dz of [-.82,0,.82])block(g,s*(w/2+.065),1.8,z+dz,.07,1.35,.065,C.cream);for(const y of [1.14,2.46])block(g,s*(w/2+.065),y,z,.1,.09,1.8,C.cream);}
    }
    for(const s of [-1,1]){block(g,0,1.5,s*(d/2+.02),1.25,2.3,.06,'#645b4d');block(g,0,2.72,s*(d/2+.06),1.5,.14,.1,C.cream);}
  });
  register('bell_frame',o=>{
    const g=root(o);pave(g,0,0,3.1,3.1,'#c3bdad',.13);
    for(const x of [-1.05,1.05])for(const z of [-1.05,1.05])block(g,x,3.05,z,.25,6.1,.25,C.wood);
    for(const y of [2.25,5.3,6]){block(g,0,y,-1.05,2.4,.22,.25,C.wood);block(g,0,y,1.05,2.4,.22,.25,C.wood);block(g,-1.05,y,0,.25,.22,2.4,C.wood);block(g,1.05,y,0,.25,.22,2.4,C.wood);}
    for(const s of [-1,1])for(let i=0;i<8;i++)block(g,-.92+i*.26,5.66,s*1.08,.07,.6,.09,'#9c7862');
    const geo=new THREE.ConeGeometry(2, .9,4);geo.rotateY(Math.PI/4);const m=add(g,geo,C.roof);m.position.y=6.55;
    const bell=add(g,new THREE.CylinderGeometry(.27,.48,.64,12),'#8f8769');bell.position.y=4.65;rod(g,[0,4.9,0],[0,5.4,0],.045,C.wood);
  });
  function figure(g,x,y,z){const robe=add(g,new THREE.ConeGeometry(.36,1.6,8),'#dddccf');robe.position.set(x,y+.8,z);const head=add(g,new THREE.SphereGeometry(.21,10,8),C.cream);head.position.set(x,y+1.77,z);rod(g,[x-.5,y+1.1,z],[x+.5,y+1.1,z],.08,C.cream);}
  register('marian_grotto',o=>{
    const g=root(o);pave(g,0,0,5.8,4.6,'#bcb8a7',.14);
    const mound=new THREE.Shape();mound.moveTo(-2.7,0);mound.lineTo(2.7,0);mound.lineTo(2.5,2.8);mound.lineTo(1.1,4.45);mound.lineTo(-.7,4.3);mound.lineTo(-2.55,2.7);mound.closePath();
    const opening=new THREE.Path();opening.moveTo(-1.05,.6);opening.lineTo(-1.05,2.25);opening.quadraticCurveTo(-1.05,3.25,0,3.35);opening.quadraticCurveTo(1.05,3.25,1.05,2.25);opening.lineTo(1.05,.6);opening.closePath();mound.holes.push(opening);
    const shell=add(g,new THREE.ExtrudeGeometry(mound,{depth:1,bevelEnabled:false}),'#9d9f91');shell.position.z=-1.45;
    block(g,0,1.75,-1.52,2.4,3.5,.16,'#73786b','camly-grotto-recess');
    for(let i=0;i<13;i++){const a=Math.PI*i/12,x=Math.cos(a)*2.1,y=.65+Math.sin(a)*3.25;const rock=add(g,new THREE.IcosahedronGeometry(.83,0),'#9d9f91');rock.position.set(x,y,-.5);rock.scale.set(1,.95,.8);}
    block(g,0,.45,.05,1.5,.7,1.2,C.stone);figure(g,0,.8,.1);for(const x of [-2.1,2.1])shrub(g,x,1.5,.7);
    if(o.palms){
      const stems=[],fronds=[],vertices=[];
      for(let j=0;j<6;j++){const t=j/6,u=(j+1)/6;const p=(v,s)=>[Math.sin(Math.PI*v)*.25*s,.5*Math.sin(Math.PI*v)-.5*v,v];vertices.push(...p(t,-1),...p(u,-1),...p(u,1),...p(t,-1),...p(u,1),...p(t,1));}
      const leaf=new THREE.BufferGeometry();leaf.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));leaf.computeVertexNormals();
      for(const [x,z,h] of o.palms){stems.push({position:[x,h/2,z],scale:[.09,h,.09]});for(let j=0;j<12;j++)fronds.push({position:[x,h,z],scale:[1.4,h<1?1.2:1.8,h<1?1.5:2.1],rotation:[0,j*Math.PI/6,0],color:j%2?'#8a9d7a':'#a3ad87'});}
      instances(g,new THREE.CylinderGeometry(1,1,1,6),stems,'parish-palm-stems','#96856c');
      const leaves=instances(g,leaf,fronds,'parish-palm-fronds');leaves.material.side=THREE.DoubleSide;
    }
  });
  register('garden_statue',o=>{
    const g=root(o);block(g,0,.35,0,1.1,.7,1.1,C.stone);figure(g,0,.7,0);
  });
  function vaultedNave(o,group,ceiling){
    const [w,d]=o.size,s=o.interior,v=s.vault,a=s.arcade,trim=s.trimColor||C.cream;
    const shell=new THREE.Group();shell.name='nave-arcade';group.add(shell);
    const surface=(geometry,color,name)=>{const mesh=add(ceiling,geometry,color,name);mesh.material=mesh.material.clone();mesh.material.side=THREE.DoubleSide;return mesh;};
    const vertices=[],segments=48;
    for(let i=0;i<segments;i++){
      const p=t=>[Math.sin(t)*w/2,v.spring+Math.cos(t)*v.rise];
      const lo=p(-Math.PI/2+i*Math.PI/segments),hi=p(-Math.PI/2+(i+1)*Math.PI/segments);
      vertices.push(lo[0],lo[1],-d/2,hi[0],hi[1],-d/2,hi[0],hi[1],d/2+.2,lo[0],lo[1],-d/2,hi[0],hi[1],d/2+.2,lo[0],lo[1],d/2+.2);
    }
    const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));geometry.computeVertexNormals();
    surface(geometry,v.color,'nave-vault');
    const cap=new THREE.Shape();cap.moveTo(-w/2,v.spring);for(let i=0;i<=48;i++){const t=-Math.PI/2+i*Math.PI/48;cap.lineTo(Math.sin(t)*w/2,v.spring+Math.cos(t)*v.rise);}cap.lineTo(w/2,v.spring);cap.closePath();
    for(const z of [-d/2+.3,d/2+.18]){const panel=surface(new THREE.ShapeGeometry(cap),v.color,'nave-vault-end');panel.position.z=z;}
    for(const side of [-1,1]){
      block(ceiling,side*(w/2+o.nave.aisleWidth/2),7.35,0,o.nave.aisleWidth+.3,.18,d+.3,s.wallColor);
      block(group,side*(w/2+o.nave.aisleWidth-.34),3.85,0,.12,7.3,d,s.wallColor);
      for(let z=a.frontZ;z>=a.backZ-.01;z-=a.spacing){
        const column=add(shell,new THREE.CylinderGeometry(a.radius,a.radius*1.08,a.spring-.18,12),trim,'nave-slim-column');column.position.set(side*(w/2-.15),(a.spring+.18)/2,z);
        for(const [y,width,height] of [[.33,.66,.3],[a.spring-.18,.78,.25],[a.spring+.06,.9,.18]])block(shell,side*(w/2-.15),y,z,width,height,width,trim);
        if(z-a.spacing<a.backZ-.01)continue;
        const half=a.spacing/2-.04,spandrel=new THREE.Shape();
        spandrel.moveTo(-a.spacing/2,v.spring);spandrel.lineTo(a.spacing/2,v.spring);spandrel.lineTo(a.spacing/2,a.spring);spandrel.lineTo(half,a.spring);spandrel.absarc(0,a.spring,half,0,Math.PI,false);spandrel.lineTo(-a.spacing/2,a.spring);spandrel.closePath();
        const wall=add(shell,new THREE.ExtrudeGeometry(spandrel,{depth:.28,bevelEnabled:false,curveSegments:24}),s.wallColor);wall.rotation.y=Math.PI/2;wall.position.set(side*(w/2-.15)-.14,0,z-a.spacing/2);
        const ribs=[];
        for(let k=0;k<32;k++){const t=k*Math.PI/32,u=(k+1)*Math.PI/32;ribs.push(side*(w/2-.32),a.spring+Math.sin(t)*half,z-a.spacing/2+Math.cos(t)*half,side*(w/2-.32),a.spring+Math.sin(u)*half,z-a.spacing/2+Math.cos(u)*half);}
        lines(shell,ribs,trim,'nave-arch-moulding');
        const glass=arch(shell,side*(w/2-.33),8.5,z-a.spacing/2,1.25,2.3,-side*Math.PI/2,C.glass[Math.round(z+a.frontZ)%4],trim,{leaded:true});
        glass.pane.material=glass.pane.material.clone();glass.pane.material.emissive.set(glass.pane.material.color);glass.pane.material.emissiveIntensity=.3;
        arch(shell,side*(w/2+o.nave.aisleWidth-.42),2.2,z-a.spacing/2,1.4,3.5,-side*Math.PI/2,C.glass[Math.round(z+a.frontZ)%4],trim,{leaded:true});
      }
      block(shell,side*(w/2-.26),7.65,0,.18,.2,d,trim);
      block(shell,side*(w/2-.26),v.spring-.1,0,.22,.18,d,trim);
    }
    // Repeated transverse ribs sit just beneath the continuous barrel surface.
    for(let z=a.frontZ;z>=a.backZ-.01;z-=a.spacing){
      for(let i=0;i<32;i++){
        const p=t=>[Math.sin(t)*(w/2-.04),v.spring+Math.cos(t)*v.rise-.035,z];
        rod(ceiling,p(-Math.PI/2+i*Math.PI/32),p(-Math.PI/2+(i+1)*Math.PI/32),.075,trim);
      }
    }
    const ap=o.apse,r=ap.radius-.3,apse=new THREE.Group();apse.name='nave-pink-apse';group.add(apse);
    const lining=add(apse,new THREE.CylinderGeometry(r,r,10.7,48,1,true,Math.PI/2,Math.PI),v.apseColor);lining.position.set(0,5.53,ap.z);lining.material=lining.material.clone();lining.material.side=THREE.DoubleSide;
    const dome=surface(new THREE.SphereGeometry(1,40,18,Math.PI,Math.PI,0,Math.PI/2),v.apseColor,'nave-apse-vault');dome.scale.set(r,2,r);dome.position.set(0,10.2,ap.z);
    const floor=add(group,new THREE.CylinderGeometry(r,r,.12,48,1,false,Math.PI/2,Math.PI),'#e7e1cf');floor.position.set(0,.12,ap.z);
    for(let i=0;i<5;i++){
      const angle=Math.PI/2+(i+.5)*Math.PI/5;
      const glass=arch(apse,Math.sin(angle)*(r-.04),7.65,ap.z+Math.cos(angle)*(r-.04),1.55,2.6,angle+Math.PI,C.glass[i%4],trim,{leaded:true});
      glass.pane.material=glass.pane.material.clone();glass.pane.material.emissive.set(glass.pane.material.color);glass.pane.material.emissiveIntensity=.45;
      for(let k=0;k<20;k++){
        const p=t=>[Math.sin(angle)*(r-.04)*Math.sin(t),10.2+2*Math.cos(t)-.04,ap.z+Math.cos(angle)*(r-.04)*Math.sin(t)];
        rod(ceiling,p(k*Math.PI/40),p((k+1)*Math.PI/40),.07,trim);
      }
    }
    for(const side of [-1,1])block(apse,side*(r+w/2)/2,5.5,ap.z,r-w/2,10.7,.2,v.apseColor);
    // Flatten only non-emissive relief; keep glowing panes as separate materials.
    for(const assembly of [shell,apse]){
      assembly.updateWorldMatrix(true,true);const parts=[];
      assembly.traverse(m=>{if(m.isMesh&&!m.name&&m.material.emissive.getHex()===0)parts.push(m);});
      for(const part of parts)assembly.attach(part);
    }
  }
  registerInteriorKit('church_nave',(o)=>{
    const [w,d]=o.size,settings=o.interior,pews=settings.pews,altar=settings.altar;
    const group=new THREE.Group();group.name='church-nave';group.position.set(...o.position);group.rotation.y=(o.rotation||0)*Math.PI/180;
    const ceiling=new THREE.Group();ceiling.name='nave-ceiling';
    const vaulted=Boolean(settings.vault),floorShift=vaulted?(settings.floorHeight-.18):0;
    group.position.y+=floorShift;ceiling.position.y=floorShift;
    if(vaulted)vaultedNave(o,group,ceiling);
    else {
    const masonry=o.type==='church_gabled',eave=masonry?(o.eaveHeight??3):2.35,apex=masonry?(o.ridgeHeight??(eave+w*.9)):eave+w/2*Math.sqrt(3)+.48;
    const foot=masonry?eave-.2:2.4;
    const slope=Math.hypot((w+.55)/2,apex-eave),angle=Math.atan2(apex-eave,(w+.55)/2);
    const boards=material('#796553').clone(),boardSpacing=settings.timber.boardSpacing;
    boards.customProgramCacheKey=()=>'church-nave-boards-v1';
    boards.onBeforeCompile=shader=>{
      shader.uniforms.naveBoardSpacing={value:boardSpacing};
      shader.vertexShader=shader.vertexShader.replace('#include <common>','#include <common>\nvarying vec2 vNaveBoard;').replace('#include <begin_vertex>','#include <begin_vertex>\nvNaveBoard=position.xz;');
      shader.fragmentShader=shader.fragmentShader.replace('#include <common>','#include <common>\nvarying vec2 vNaveBoard; uniform float naveBoardSpacing;').replace('#include <color_fragment>',`#include <color_fragment>
        float boardId=floor(vNaveBoard.x/naveBoardSpacing);
        float phase=mod(vNaveBoard.x,naveBoardSpacing);
        float edge=min(phase,naveBoardSpacing-phase);
        float aa=max(fwidth(vNaveBoard.x),.001);
        float joint=1.0-smoothstep(.004,.004+aa,edge);
        float endPhase=mod(vNaveBoard.y+mod(boardId,3.0)*1.15,3.45);
        float endEdge=min(endPhase,3.45-endPhase);
        float endJoint=1.0-smoothstep(.003,.003+max(fwidth(vNaveBoard.y),.001),endEdge);
        float tone=.97+.025*sin(boardId*2.39);
        diffuseColor.rgb*=mix(tone,.68,max(joint*.65,endJoint*.35));`);
    };
    for(const s of [-1,1]){
      const m=new THREE.Mesh(new THREE.BoxGeometry(slope+.12,.12,d+.55),boards);m.name='nave-ceiling-boards-'+(s<0?'left':'right');m.castShadow=true;m.receiveShadow=true;m.position.set(s*(w+.55)/4,(apex+eave)/2-.14,0);m.rotation.z=-s*angle;ceiling.add(m);
    }
    const rafters=new THREE.Group();rafters.name='nave-rafters';ceiling.add(rafters);
    const ties=new THREE.Group();ties.name='nave-ties';ceiling.add(ties);let frameIndex=0;
    for(let z=-d/2+.6;z<d/2;z+=settings.timber.trussSpacing,frameIndex++){
      for(const s of [-1,1]){
        rod(rafters,[s*(w/2-.25),foot,z],[0,apex-.32,z],.105,C.wood);
        rod(rafters,[s*(w/2-1.15),foot+.15,z],[0,apex-2.2,z],.075,C.wood);
        for(let y=masonry?eave+1.6:4;y<apex-3;y+=2.6){const x=(w/2-.25)*(1-(y-foot)/(apex-.32-foot));rod(rafters,[s*x,y,z],[s*(x-1),y+.3,z],.055,C.wood);}
      }
      if(frameIndex%settings.timber.tieEvery===0)for(const y of settings.timber.tieHeights){const x=(w/2-.25)*(1-(y-foot)/(apex-.32-foot));rod(ties,[-x,y,z],[x,y,z],.065,C.wood);}
    }
    for(const s of [-1,1])for(let y=masonry?eave+.65:3;y<apex-1;y+=1){const x=(w+.55)/2*(1-(y-eave)/(apex-eave));rod(ceiling,[s*x,y-.24,-d/2],[s*x,y-.24,d/2],.045,'#8a7560');}
    }
    const floorWidth=vaulted?w+o.nave.aisleWidth*2-.7:w-.8;
    block(group,0,.17,0,floorWidth,.025,d-.8,vaulted?'#e7e1cf':'#dfdfce');
    const tiles=[];
    for(let x=-(vaulted?floorWidth:w)/2+.8;x<(vaulted?floorWidth:w)/2-.5;x+=.65)for(let z=-d/2+.8;z<d/2-.5;z+=.65){
      const ix=Math.round((x+w/2-.8)/.65),iz=Math.round((z+d/2-.8)/.65);
      if(vaulted?(ix+iz)%2===0:(ix%6===0||iz%6===0)||((ix%6===2||ix%6===3)&&(iz%6===2||iz%6===3)))tiles.push({position:[x,.187,z],scale:[.63,.012,.63],color:vaulted?'#454742':'#a4b7a2'});
    }
    instances(group,new THREE.BoxGeometry(1,1,1),tiles,'nave-tile-pattern');
    if(settings.sanctuary){
      const s=settings.sanctuary,sw=s.width??w-3,sh=s.height??12,sz=s.z??(-d/2+.6),sg=new THREE.Group();sg.name='nave-pointed-sanctuary';group.add(sg);
      surface(sg,pointed(sw,sh),s.color||'#ddd2b4',sz);
      const frame=pointed(sw+.3,sh+.15);frame.holes.push(new THREE.Path(pointed(sw,sh).getPoints(32)));surface(sg,frame,s.trimColor||'#ece1c6',sz+.14,undefined,.2);
      const inner=pointed(sw*.8,sh*.86),outline=inner.getPoints(40),pts=[];
      for(let i=1;i<outline.length;i++)pts.push(outline[i-1].x,outline[i-1].y+.1,sz+.06,outline[i].x,outline[i].y+.1,sz+.06);
      lines(sg,pts,s.lineColor||'#b8ae95','nave-sanctuary-rib');
    }
    if(settings.gallery){
      const s=settings.gallery,gy=s.height??5.3,gd=s.depth??2.8,gz=s.z??(d/2-gd/2-.25),gg=new THREE.Group();gg.name='nave-entrance-gallery';group.add(gg);
      block(gg,0,gy-.12,gz,w-.6,.24,gd,s.color||C.cream);
      block(gg,0,gy+.08,gz-gd/2,w-.7,.16,.14,s.color||C.cream);
      block(gg,0,gy+1,gz-gd/2,w-.7,.14,.18,s.color||C.cream);
      for(let x=-w/2+.6;x<w/2-.3;x+=.55)block(gg,x,gy+.54,gz-gd/2,.07,.9,.08,s.color||C.cream);
      for(const side of [-1,1])block(gg,side*(w/2-.7),gy/2,gz-gd/2,.3,gy,.35,s.color||C.cream);
    }
    const stoneJoints=[];
    if(!vaulted){
    for(const s of [-1,1])for(let row=0;row<4;row++){
      const y=.18+row*.28,x=s*(w/2-.657);
      stoneJoints.push(x,y,-d/2+.6,x,y,d/2-1.4);
      for(let z=-d/2+.6+(row%2)*.3;z<d/2-1.4;z+=.66)stoneJoints.push(x,y,z,x,y+.28,z);
    }
    for(let row=0;row<7;row++){
      const y=.2+row*.31,z=-d/2+.705;
      stoneJoints.push(-w/2+.4,y,z,w/2-.4,y,z);
      for(let x=-w/2+.4+(row%2)*.33;x<w/2-.4;x+=.67)stoneJoints.push(x,y,z,x,y+.31,z);
    }
    lines(group,stoneJoints,'#77796c','nave-inner-stone-joints');
    }
    const benches=new THREE.Group();benches.name='nave-pews';benches.userData={rows:pews.rows,seatHeight:.45,backHeight:.9,aisleWidth:pews.aisleWidth};group.add(benches);
    for(let k=0;k<pews.rows;k++)for(const s of [-1,1]){
      const x=s*(pews.aisleWidth/2+pews.width/2),z=pews.startZ-k*pews.spacing;
      block(benches,x,.18+.45-.055,z,pews.width,.11,.45,pews.color||'#57483c');
      block(benches,x,.18+.71,z+.2,pews.width,.38,.09,pews.color||'#57483c');
      for(const dx of [-pews.width/2+.18,pews.width/2-.18]){block(benches,x+dx,.18+.23,z,.13,.46,.48,pews.frameColor||'#635143');block(benches,x+dx,.18+.71,z+.16,.12,.38,.12,pews.frameColor||'#635143');}
    }
    block(group,0,.27,altar.z,w-2,.18,6,'#b7b5a1');
    block(group,0,.41,altar.z-.25,w-2.5,.1,5.2,'#c5c6b0');
    if(settings.carpet){
      const carpet=new THREE.Group();carpet.name='nave-red-carpet';group.add(carpet);
      block(carpet,0,.205,altar.z+4.5,settings.carpet.width,.025,3,settings.carpet.color);
      block(carpet,0,.372,altar.z+2.675,settings.carpet.width,.025,.65,settings.carpet.color);
      block(carpet,0,.469,altar.z-.25,settings.carpet.width,.018,5.2,settings.carpet.color);
      block(carpet,0,.28,altar.z+3.005,settings.carpet.width,.16,.025,settings.carpet.color);
      block(carpet,0,.413,altar.z+2.36,settings.carpet.width,.1,.025,settings.carpet.color);
    }
    const table=new THREE.Group();table.name='nave-altar';group.add(table);
    block(table,0,1.33,altar.z,altar.width,.18,1.1,'#c9c5b5');
    for(const s of [-1,1])block(table,s*.8,.87,altar.z,.45,.82,.7,'#8d8b7c');
    block(table,0,1.44,altar.z,altar.width+.1,.035,1.15,'#e0ddcf');
    block(table,0,1.33,altar.z+.57,altar.width+.08,.24,.025,'#e0ddcf');
    const offerings=new THREE.Group();offerings.name='nave-altar-offerings';group.add(offerings);
    for(const s of [-1,1]){
      const x=s*(altar.width/2+.55),z=altar.z+.55;
      const pot=add(offerings,new THREE.CylinderGeometry(.18,.12,.35,8),'#d5d3c2');pot.position.set(x,.635,z);
      for(let i=0;i<6;i++){
        const a=i*Math.PI/3,y=1.02+(i%3)*.13,dx=Math.cos(a)*.22,dz=Math.sin(a)*.18;
        rod(offerings,[x,.8,z],[x+dx,y,z+dz],.015,'#82916c');
        const leaf=add(offerings,new THREE.IcosahedronGeometry(.13,0),'#8a9977');leaf.scale.set(.5,1.7,.5);leaf.position.set(x+dx*.7,y-.12,z+dz*.7);leaf.rotation.z=-a;
        const bloom=add(offerings,new THREE.IcosahedronGeometry(.1,1),i%2?'#b09b91':'#c5bd8f');bloom.position.set(x+dx,y,z+dz);
      }
    }
    const cross=new THREE.Group();cross.name='nave-crucifix';group.add(cross);
    const cz=altar.crucifixZ??(-d/2+.82),cx=altar.crucifixX;
    block(cross,cx,4,cz,.23,4.1,.17,'#53483e');block(cross,cx,5,cz,2.2,.22,.17,'#53483e');
    const torso=add(cross,new THREE.SphereGeometry(1,10,8),C.cream,'nave-crucifix-torso');torso.scale.set(.19,.48,.12);torso.position.set(cx,4.3,cz+.18);
    for(const s of [-1,1]){
      rod(cross,[cx+s,5.02,cz+.14],[cx+s*.18,4.55,cz+.18],.055,C.cream);
      rod(cross,[cx+s*.1,3.95,cz+.18],[cx+s*.12,3.3,cz+.2],.07,C.cream);
      rod(cross,[cx+s*.12,3.3,cz+.2],[cx+s*.04,2.7,cz+.16],.055,C.cream);
    }
    block(cross,cx,3.94,cz+.19,.39,.28,.27,'#d2cdb7');
    const head=add(cross,new THREE.SphereGeometry(.17,10,8),C.cream);head.position.set(cx,4.96,cz+.18);
    for(const [name,s,color] of [['mary',-1,'#9caeb0'],['joseph',1,'#ad9982']]){
      const statue=new THREE.Group();statue.name='nave-'+name;group.add(statue);
      const x=s*(w/2-2),z=altar.z-.7;
      block(statue,x,.79,z,.8,.67,.8,'#b2ac9b');
      const robe=add(statue,new THREE.ConeGeometry(.35,1.5,10),color);robe.position.set(x,1.87,z);
      if(name==='mary'){
        const veil=add(statue,new THREE.SphereGeometry(.25,10,8),'#c8cfc5','nave-mary-veil');veil.scale.set(1,1.9,.72);veil.position.set(x,2.53,z-.08);
      }else rod(statue,[x+.4,1.125,z+.1],[x+.4,2.95,z+.1],.025,'#7b6d56').name='nave-joseph-staff';
      const face=add(statue,new THREE.SphereGeometry(.19,10,8),C.cream);face.position.set(x,2.72,z);
      rod(statue,[x-.32,2.3,z+.12],[x+.32,2.12,z+.15],.07,C.cream);
      if(name==='mary'){
        const child=add(statue,new THREE.SphereGeometry(.12,10,8),C.cream);child.position.set(x+.2,2.34,z+.25);
        rod(statue,[x+.2,1.99,z+.24],[x+.2,2.21,z+.24],.09,'#d6d1b9');
      }
    }
    let front;
    if(vaulted){
      front=new THREE.Group();front.name='nave-cutaway-walls';group.add(front);group.updateMatrixWorld(true);
      front.attach(group.getObjectByName('nave-arcade'));
      const exterior=scene.getObjectByName('basilica-'+o.id)?.getObjectByName('basilica-reveal-walls');
      if(exterior)front.attach(exterior);
    }
    if(o.type==='church_gabled')front=scene.getObjectByName('church-gabled-'+o.id)?.getObjectByName('church-gabled-reveal-walls');
    compact(group);compact(ceiling);
    if(front){
      const finishes=new Map();front.traverse(m=>{
        if(!m.material)return;
        const clone=mat=>{if(!finishes.has(mat))finishes.set(mat,mat.clone());return finishes.get(mat);};
        m.material=Array.isArray(m.material)?m.material.map(clone):clone(m.material);
      });
    }
    return {group,ceiling,front,door:scene.getObjectByName(vaulted?'basilica-entrance-door':o.type==='church_gabled'?'church-lower-door':'camly-gable-door')};
  });
  register('parish_playground',o=>{
    const g=root(o);pave(g,0,0,12,10,'#cebea2',.035);
    for(const x of [-1.5,1.5])for(const z of [-1,1])rod(g,[x,0,z],[x,3.4,z],.075,'#8b9c91');
    block(g,0,2.2,0,3.2,.15,2.2,'#b8b995');
    const canopy=add(g,new THREE.ConeGeometry(2.2,.8,4),'#b6a478');canopy.rotation.y=Math.PI/4;canopy.position.y=3.65;
    const rails=new THREE.Group();rails.name='camly-ladder-rails';g.add(rails);
    for(const x of [-.56,.56])rod(rails,[x,.04,-4.5],[x,2.25,-1.1],.055,'#8a9d9a');
    for(let i=0;i<9;i++)block(g,0,.1+i*.265,-4.4+i*.4,1.1,.09,.08,'#8a9d9a');
    const slide=block(g,0,1.07,2.9,1.05,.09,4.4,'#91aaa4');slide.rotation.x=Math.atan2(2.1,4.1);
    for(const x of [3.8,5.4])for(const s of [-1,1])rod(g,[x,0,s*2],[x,2.6,0],.07,'#83968f');
    rod(g,[3.8,2.6,0],[5.4,2.6,0],.08,'#83968f');for(const x of [4.2,5])rod(g,[x,.65,0],[x,2.6,0],.022,C.wood);block(g,4.6,.63,0,1.2,.12,.5,'#a19c7b');
  });
})();
