// Market family: metres, local +z is the public frontage, rotation is degrees.
(()=>{
  const C={wall:'#ddd3b8',trim:'#eee7d5',roof:'#7d9087',metal:'#718078',wood:'#8c7864',dark:'#59645c',paving:'#d3cdbc',joint:'#b5b09f',soil:'#b4bca4',leaf:'#92a17f'};
  const unit=new THREE.BoxGeometry(1,1,1);
  const color=(o,key)=>o.colors?.[key]??C[key];
  function root(o){const g=new THREE.Group();g.name=o.id+'-market';g.position.set(...(o.position??[0,0,0]));g.rotation.y=THREE.MathUtils.degToRad(o.rotation??0);scene.add(g);return g;}
  function add(g,geometry,c,name=''){const m=new THREE.Mesh(geometry,material(c));m.name=name;m.castShadow=true;m.receiveShadow=true;g.add(m);return m;}
  function block(g,x,y,z,w,h,d,c,name=''){const m=add(g,new THREE.BoxGeometry(w,h,d),c,name);m.position.set(x,y,z);return m;}
  function lines(g,points,c,name){if(!points.length)return;const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(points,3));const m=new THREE.LineSegments(geo,new THREE.LineBasicMaterial({color:c,transparent:true,opacity:.48}));m.name=name;g.add(m);return m;}
  function instances(g,geometry,items,c,name){
    if(!items.length)return;
    const m=new THREE.InstancedMesh(geometry,material(c),items.length),dummy=new THREE.Object3D();m.name=name;m.castShadow=true;m.receiveShadow=true;g.add(m);
    for(const [i,p] of items.entries()){dummy.position.set(...p.p);dummy.scale.set(...(p.s??[1,1,1]));dummy.rotation.set(...(p.r??[0,0,0]));dummy.updateMatrix();m.setMatrixAt(i,dummy.matrix);if(p.c)m.setColorAt(i,new THREE.Color(p.c));}
    m.computeBoundingBox();m.computeBoundingSphere();m.instanceMatrix.needsUpdate=true;
    if(currentEnvelope){g.updateWorldMatrix(true,true);geometry.computeBoundingBox();const b=geometry.boundingBox,t=new THREE.Matrix4();for(let i=0;i<items.length;i++){m.getMatrixAt(i,t);for(const x of [b.min.x,b.max.x])for(const y of [b.min.y,b.max.y])for(const z of [b.min.z,b.max.z])currentEnvelope.push(new THREE.Vector3(x,y,z).applyMatrix4(t).applyMatrix4(m.matrixWorld));}}
    return m;
  }
  function compact(g){
    for(const child of [...g.children])if(child.isGroup)compact(child);
    const batches=new Map();
    for(const m of g.children){if(!m.isMesh||m.isInstancedMesh||m.name||m.material.map)continue;const key=m.material.uuid;if(!batches.has(key))batches.set(key,[]);batches.get(key).push(m);}
    for(const batch of batches.values()){
      if(batch.length<2)continue;
      const geometries=batch.map(m=>{m.updateMatrix();const geo=m.geometry.index?m.geometry.toNonIndexed():m.geometry.clone();return geo.applyMatrix4(m.matrix);});
      add(g,mergeGeometries(geometries),batch[0].material.color);
      for(const m of batch){g.remove(m);m.geometry.dispose();}for(const geo of geometries)geo.dispose();
    }
  }
  function register(type,builder){registerObjectType(type,o=>{const g=root(o);builder(g,o);compact(g);});}
  function sign(g,s,x,y,z,defaultWidth){
    if(!s?.text)return;
    const w=s.width??defaultWidth,h=s.height??1.15;
    block(g,x,y,z,w+.22,h+.22,.24,s.frame??C.trim,'market-entrance-sign');block(g,x,y,z+.14,w,h,.04,s.background??'#d8d9bd');
    const canvas=document.createElement('canvas');canvas.width=1024;canvas.height=160;const ctx=canvas.getContext('2d');ctx.clearRect(0,0,1024,160);ctx.font='700 100px sans-serif';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillStyle=s.color??'#637e83';ctx.fillText(s.text,512,83,980);
    const tex=new THREE.CanvasTexture(canvas);tex.colorSpace=THREE.SRGBColorSpace;
    const m=new THREE.Mesh(new THREE.PlaneGeometry(w*.95,h*.85),new THREE.MeshBasicMaterial({map:tex,transparent:true,depthWrite:false}));m.name='market-sign-lettering';m.position.set(x,y,z+.175);g.add(m);
  }
  function roof(g,o,w,d,eave,options={}){
    const rg=new THREE.Group();rg.name='market-roof';g.add(rg);
    const kind=options.kind??'gable',rise=options.rise??Math.min(w*.13,2.8),over=options.overhang??.35,t=options.thickness??.13,c=options.color??color(o,'roof'),ww=w+over*2,dd=d+over*2,seam=options.seamSpacing??.65;
    if(!['gable','hip','flat','skillion'].includes(kind))throw new TypeError('Unsupported market roof kind: '+kind);
    let height;
    if(kind==='flat'){block(rg,0,eave,0,ww,t,dd,c);height=()=>eave+t/2;}
    else if(kind==='skillion'){
      const a=Math.atan2(rise,dd),m=block(rg,0,eave+rise/2,0,ww,t,Math.hypot(dd,rise),c);m.rotation.x=a;height=(x,z)=>eave+rise*(.5-z/dd)+t/(2*Math.cos(a));
    }else if(kind==='hip'){
      const wide=ww>dd,span=Math.min(ww,dd),run=Math.max(ww,dd),ridge=run-span,v=[];
      const project=(u,y,v)=>wide?[v,y,u]:[u,y,v];
      const a=project(-span/2,eave,run/2),b=project(span/2,eave,run/2),c0=project(span/2,eave,-run/2),f=project(-span/2,eave,-run/2),p=project(0,eave+rise,ridge/2),q=project(0,eave+rise,-ridge/2);
      v.push(...a,...b,...p,...b,...c0,...q,...b,...q,...p,...c0,...f,...q,...f,...a,...p,...f,...p,...q);
      const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(v,3));geo.computeVertexNormals();const m=add(rg,geo,c);m.material=m.material.clone();m.material.side=THREE.DoubleSide;
      height=(x,z)=>eave+rise*Math.min((ww/2-Math.abs(x))/(span/2),(dd/2-Math.abs(z))/(span/2));
    }else{
      const a=Math.atan2(rise,ww/2);
      for(const side of [-1,1]){const m=block(rg,side*ww/4,eave+rise/2,0,Math.hypot(ww/2,rise),t,dd,c);m.rotation.z=-side*a;}
      const cap=add(rg,new THREE.CylinderGeometry(t*.65,t*.65,dd,8),c,'market-ridge-cap');cap.rotation.x=Math.PI/2;cap.position.set(0,eave+rise,0);
      height=x=>eave+rise*(1-Math.abs(x)/(ww/2))+t/(2*Math.cos(a));
    }
    const joints=[];
    if(seam>0)for(let x=-ww/2+seam;x<ww/2;x+=seam){
      if(kind==='hip'){
        const edge=Math.max(0,dd/2-Math.min(ww/2-Math.abs(x),Math.min(ww,dd)/2)),ends=[-dd/2+.04,-edge,edge,dd/2-.04].sort((a,b)=>a-b);
        for(let i=1;i<ends.length;i++)if(ends[i]>ends[i-1])joints.push(x,height(x,ends[i-1])+.025,ends[i-1],x,height(x,ends[i])+.025,ends[i]);
      }else{const inset=kind==='skillion'?.04:0;joints.push(x,height(x,-dd/2+inset)+.025,-dd/2+inset,x,height(x,dd/2-inset)+.025,dd/2-inset);}
    }
    lines(rg,joints,options.seamColor??color(o,'trim'),'market-roof-seams');
    roofRecords.push({group:rg,parameters:{kind,width:ww,depth:dd,eaveHeight:eave,ridgeHeight:eave+(kind==='flat'?0:rise)},tiers:1,thickness:t,ridgeOrnament:false});
    return {group:rg,height,rise,over,kind,thickness:t};
  }
  function closeRoof(g,o,w,d,h,r,glazed=false){
    const plane=(points,z,name,c)=>{const s=new THREE.Shape();s.moveTo(...points[0]);for(const p of points.slice(1))s.lineTo(...p);s.closePath();const m=add(g,new THREE.ExtrudeGeometry(s,{depth:.14,bevelEnabled:false}),c,name);m.position.z=z-.07;return m;};
    if(r.kind==='gable'){
      const edge=r.height(w/2,0)-r.thickness/2,peak=r.height(0,0)-r.thickness/2;
      for(const side of [-1,1])plane([[-w/2,h-.05],[w/2,h-.05],[w/2,edge],[0,peak],[-w/2,edge]],side*d/2,side===1?'market-clerestory':'market-rear-gable',glazed?color(o,'metal'):color(o,'wall'));
      if(glazed){const p=[];for(let x=-w/2+.4;x<w/2;x+=o.clerestorySpacing??1.5)p.push(x,h,d/2+.08,x,r.height(x,0)-r.thickness/2,d/2+.08);lines(g,p,color(o,'trim'),'market-clerestory-mullions');}
    }else if(r.kind==='skillion'){
      const front=r.height(0,d/2)-r.thickness/2,back=r.height(0,-d/2)-r.thickness/2;
      for(const side of [-1,1]){
        const p=plane([[-d/2,h-.05],[d/2,h-.05],[d/2,front],[-d/2,back]],0,'',color(o,'wall'));p.rotation.y=-Math.PI/2;p.position.set(side*w/2+.07,0,0);
      }
      block(g,0,(h+back)/2,-d/2,w,Math.max(.05,back-h),.2,color(o,'wall'));
      block(g,0,(h+front)/2,d/2,w,Math.max(.05,front-h),.2,color(o,'wall'));
    }else if(r.kind==='hip'){
      const top=r.height(w/2,d/2)+.02;
      for(const side of [-1,1]){block(g,0,(h+top)/2,side*d/2,w,Math.max(.08,top-h),.2,color(o,'wall'));block(g,side*w/2,(h+top)/2,0,.2,Math.max(.08,top-h),d,color(o,'wall'));}
    }
  }
  function awning(g,o,w,z,options={}){
    const depth=options.depth??1.8,h=options.height??2.9,drop=options.drop??.42,stripe=options.stripeWidth??.65,c=options.colors??['#b5b6a1','#d5ceba'];
    if(depth<=0)return;
    const a=Math.atan2(drop,depth),sheets=[],posts=[];
    const count=Math.max(1,Math.ceil(w/stripe));
    for(let i=0;i<count;i++){const sw=w/count,x=-w/2+(i+.5)*sw;sheets.push({p:[x,h-drop/2,z+depth/2],s:[sw,.075,Math.hypot(depth,drop)],r:[a,0,0],c:c[i%c.length]});}
    instances(g,unit,sheets,'#ffffff','market-awning-stripes');
    block(g,0,h-drop-.10,z+depth,w,.22,.09,c[0]);
    if(options.posts!==false)for(const x of [-w/2+.10,w/2-.10])posts.push({p:[x,(h-drop)/2,z+depth-.09],s:[.085,h-drop,.085]});
    instances(g,unit,posts,color(o,'metal'),'market-awning-posts');
    const beams=[];for(const x of [-w/2+.1,w/2-.1])beams.push(x,h,z,x,h-drop,z+depth);lines(g,beams,color(o,'metal'),'market-awning-braces');
  }
  function goods(g,o,x,z,w,kind){
    if(!kind||kind==='none')return;
    const counter=.78,depth=.8;block(g,x,counter/2,z,w*.83,counter,depth,color(o,'wood'));
    block(g,x,counter+.035,z,w*.88,.07,depth+.08,color(o,'trim'));
    const items=[],trays=[],n=Math.max(2,Math.floor(w/.65));
    const shades=kind==='textiles'?['#a48d87','#aaa993','#819496','#c5b49d']:['#92a37d','#bca575','#c3b698','#a28e81'];
    for(let i=0;i<n;i++){
      const xx=x-w*.37+(i+.5)*w*.74/n;
      if(kind==='textiles')for(let k=0;k<4;k++)items.push({p:[xx,counter+.10+k*.10,z],s:[w*.68/n,.10,.62],c:shades[(i+k)%shades.length]});
      else{
        trays.push({p:[xx,counter+.10,z],s:[w*.69/n,.12,.65]});
        for(let k=0;k<8;k++){const px=xx+((k%3)-1)*.13,pz=z+(Math.floor(k/3)-1)*.17;items.push({p:[px,counter+.22+(kind==='flowers'?.23:0),pz],s:kind==='flowers'?[.11,.16,.11]:[.12,.10,.12],c:shades[(i+k)%shades.length]});if(kind==='flowers')trays.push({p:[px,counter+.23,pz],s:[.025,.32,.025]});}
      }
    }
    instances(g,unit,trays,color(o,'wood'),'market-produce-crates');
    instances(g,kind==='textiles'?unit:new THREE.IcosahedronGeometry(1,1),items,'#ffffff','market-goods-'+kind);
    const feet=[];for(const side of [-1,1])feet.push({p:[x+side*w*.32,.13,z],s:[.12,.26,.63]});instances(g,unit,feet,color(o,'dark'),'market-counter-feet');
    if(kind==='textiles'&&o.display?.hanging){
      const p=o.display,y=p.railHeight??2.25,length=p.length??.62,pitch=p.spacing??.55,count=Math.max(1,Math.floor(w*.75/pitch)),clothes=[],supports=[],colors=p.colors??['#a89486','#9aa69b','#b4a3a2'];
      supports.push({p:[x,y,z-.28],s:[w*.85,.045,.045]});
      for(const side of [-1,1])supports.push({p:[x+side*w*.42,y/2,z-.28],s:[.045,y,.045]});
      for(let i=0;i<count;i++){
        const xx=x+(i-(count-1)/2)*pitch,c=colors[i%colors.length];
        supports.push({p:[xx,y-.09,z-.28],s:[.025,.18,.025]},{p:[xx,y-.18,z-.28],s:[.32,.025,.035]});
        clothes.push({p:[xx,y-.18-length/2,z-.28],s:[.34,length,.05],c});
        for(const side of [-1,1])clothes.push({p:[xx+side*.19,y-.18-length*.19,z-.28],s:[.14,length*.34,.05],r:[0,0,side*.38],c});
      }
      instances(g,unit,supports,color(o,'metal'),'market-garment-rails');instances(g,unit,clothes,'#ffffff','market-hanging-clothes');
    }
  }
  function shutter(g,o,x,z,w,h){
    block(g,x,h/2+.12,z,w,h,.09,color(o,'metal'));
    const p=[];for(let y=.25;y<h;y+=.17)p.push(x-w/2,y,z+.055,x+w/2,y,z+.055);lines(g,p,color(o,'trim'),'market-shutter-slats');
  }
  function frontBays(g,o,w,d,h,count){
    const pitch=w/count,pillars=[];
    for(let i=0;i<=count;i++){const x=-w/2+i*pitch;pillars.push({p:[x,h/2,d/2],s:[.25,h,.3]});block(g,x,.32,d/2,.30,.64,.34,color(o,'wood'));}
    instances(g,unit,pillars,color(o,'trim'),'market-bay-columns');
    for(let i=0;i<count;i++){
      const x=-w/2+(i+.5)*pitch,closed=Array.isArray(o.shutters)?o.shutters[i%o.shutters.length]:o.shutters===true;
      block(g,x,(h-.35)/2+.12,d/2-.6,pitch-.26,h-.35,.12,color(o,'dark'));
      if(closed)shutter(g,o,x,d/2-.55,pitch-.35,h-.4);
      else goods(g,o,x,d/2+.4,pitch-.4,Array.isArray(o.goods)?o.goods[i%o.goods.length]:o.goods??'produce');
    }
  }
  function shell(g,o,frontage=false){
    const [w,d]=o.size??[18,12],h=o.height??(frontage?6.4:4.6),wall=color(o,'wall');
    block(g,0,.07,0,w+.3,.14,d+.3,color(o,'trim'),'market-foundation');
    block(g,0,h/2,-d/2,w,h,.25,wall);
    for(const side of [-1,1])block(g,side*w/2,h/2,0,.25,h,d,wall);
    const bayHeight=frontage?(o.storeyHeight??3.1):h-.45;
    if(o.portal&&!frontage){
      const pw=(o.portal.width??w*.28)+.8,wing=(w-pw)/2;
      for(const side of [-1,1]){const group=new THREE.Group();group.position.x=side*(pw+wing)/2;g.add(group);frontBays(group,o,wing,d,bayHeight,Math.max(1,Math.floor((o.bays??5)/2)));}
      const recess=o.portal.recess??1.8;
      block(g,0,bayHeight/2,d/2-recess,pw,bayHeight,.14,color(o,'dark'));
      for(const side of [-1,1])goods(g,o,side*(pw/2-.9),d/2-recess/2,1.45,o.portal.goods??'textiles');
    }else frontBays(g,o,w,d,bayHeight,o.bays??Math.max(3,Math.round(w/3.6)));
    block(g,0,bayHeight+.12,d/2,w+.35,.25,.40,color(o,'trim'));
    if(frontage){
      block(g,0,(bayHeight+h)/2,d/2,w,h-bayHeight,.25,wall);
      const n=o.upperWindows??Math.max(2,Math.round(w/2.4)),frames=[];
      for(let i=0;i<n;i++){const x=-w/2+(i+.5)*w/n,y=(h+bayHeight)/2;
        block(g,x,y,d/2+.15,w/n*.62,(h-bayHeight)*.58,.08,color(o,'metal'));
        for(const side of [-1,1])frames.push({p:[x+side*w/n*.32,y,d/2+.21],s:[.08,(h-bayHeight)*.65,.08]});
        frames.push({p:[x,y,d/2+.21],s:[.055,(h-bayHeight)*.58,.07]});
      }instances(g,unit,frames,color(o,'trim'),'market-upper-window-frames');
    }
    const r=roof(g,o,w,d,h,o.roof??{});
    closeRoof(g,o,w,d,h,r,o.clerestory!==false);
    if(o.monitor){
      const p=o.monitor,mw=p.width??w*.3,md=p.depth??d,mh=p.height??h+r.rise+.8,offset=p.offset??[0,0],mg=new THREE.Group();mg.name='market-roof-monitor';mg.position.set(offset[0],0,offset[1]);g.add(mg);
      const low=Math.min(...[-mw/2,mw/2].flatMap(x=>[-md/2,md/2].map(z=>r.height(x+offset[0],z+offset[1]))))-.12;
      for(const side of [-1,1]){block(mg,side*mw/2,(low+mh)/2,0,.18,mh-low,md,color(o,'metal'));block(mg,0,(low+mh)/2,side*md/2,mw,mh-low,.18,color(o,'metal'));}
      const mr=roof(mg,o,mw,md,mh,{kind:'gable',rise:1.2,overhang:.18,...p.roof});closeRoof(mg,o,mw,md,mh,mr,p.glazed!==false);
    }
    if(o.awning)awning(g,o,w,d/2,o.awning);
    if(o.portal){
      const p=o.portal,pw=p.width??w*.28,ph=p.height??h+.25,pd=p.depth??1;
      block(g,0,ph,d/2+.18,pw+.65,.42,pd,color(o,'trim'));
      for(const side of [-1,1]){block(g,side*(pw/2+.2),ph/2,d/2+.18,.42,ph,pd,color(o,'trim'));block(g,side*(pw/2+.2),.4,d/2+pd/2,.45,.8,.14,color(o,'wood'));}
      sign(g,o.sign,0,ph+(o.sign?.height??1.15)/2+.38,d/2+pd/2+.08,pw+.65);
      if(p.flag){block(g,0,ph+1.6,d/2+pd/2+.3,.045,2.8,.045,color(o,'metal'));const flag=block(g,.29,ph+2,d/2+pd/2+.3,.58,.40,.02,'#a97763');flag.rotation.z=-.1;}
    }else sign(g,o.sign,0,h-.6,d/2+.25,w*.75);
  }
  register('market_hall',(g,o)=>shell(g,o));
  register('market_frontage',(g,o)=>shell(g,o,true));
  register('market_stalls',(g,o)=>{
    const [w,d]=o.size??[12,3.5],h=o.height??3.1;
    block(g,0,.07,0,w+.2,.14,d+.2,color(o,'trim'),'market-foundation');
    block(g,0,h/2,-d/2,w,h,.18,color(o,'wall'));
    for(const side of [-1,1])block(g,side*w/2,h/2,0,.18,h,d,color(o,'wall'));
    frontBays(g,o,w,d,h-.25,o.bays??Math.max(2,Math.round(w/2.8)));
    const r=roof(g,o,w,d,h,{kind:'skillion',rise:.45,...o.roof});closeRoof(g,o,w,d,h,r);
    if(o.awning!==false)awning(g,o,w,d/2,o.awning??{});
    sign(g,o.sign,0,h-.45,d/2+.1,w*.7);
  });
  register('market_canopy',(g,o)=>{
    const [w,d]=o.size??[5,4],h=o.height??2.8,posts=[];
    for(const x of [-w/2+.12,w/2-.12])for(const z of [-d/2+.12,d/2-.12])posts.push({p:[x,h/2,z],s:[.10,h,.10]});
    instances(g,unit,posts,color(o,'metal'),'market-canopy-columns');
    const beams=[];for(const side of [-1,1])beams.push({p:[0,h-.07,side*d/2],s:[w,.14,.09]},{p:[side*w/2,h-.07,0],s:[.09,.14,d]});instances(g,unit,beams,color(o,'metal'),'market-canopy-beams');
    roof(g,o,w,d,h,{kind:'hip',rise:.65,overhang:.2,...o.roof});
    goods(g,o,0,0,w-.5,o.goods??'produce');
  });
  register('market_paving',(g,o)=>{
    const [w,d]=o.size??[30,30],t=o.thickness??.09,top=o.top??.10;
    const slab=block(g,0,top-t/2,0,w,t,d,o.color??color(o,'paving'),'market-paved-surface');
    g.updateWorldMatrix(true,true);walkableGeometries.push(slab.geometry.clone().applyMatrix4(slab.matrixWorld));
    const pitch=o.jointSpacing??2,items=[];
    if(pitch>0){for(let x=-w/2+pitch;x<w/2;x+=pitch)items.push({p:[x,top+.003,0],s:[.014,.006,d]});for(let z=-d/2+pitch;z<d/2;z+=pitch)items.push({p:[0,top+.004,z],s:[w,.006,.014]});}
    instances(g,unit,items,o.jointColor??color(o,'joint'),'market-paving-joints');
    if(o.curb!==false)for(const side of [-1,1]){block(g,side*(w/2-.06),top+.05,0,.12,.10,d,color(o,'trim'));block(g,0,top+.05,side*(d/2-.06),w,.10,.12,color(o,'trim'));}
  });
  register('market_planting',(g,o)=>{
    const [w,d]=o.size??[12,3],floor=o.floor??.08;
    block(g,0,floor/2,0,w,floor,d,o.soilColor??color(o,'soil'),'market-planted-bed');
    const leaves=[],flowers=[],seed=o.seed??1,noise=i=>(Math.sin(i*127.1+seed*311.7)*43758.5453)%1,unitNoise=i=>Math.abs(noise(i));
    const spacing=o.spacing??1.1,points=o.points??Array.from({length:Math.max(1,Math.floor(w*d/(spacing*spacing)))},(_,i)=>[(unitNoise(i*2)-.5)*(w-.7),(unitNoise(i*2+1)-.5)*(d-.7)]);
    for(const [i,[x,z]] of points.entries()){
      const s=(o.shrubSize??.5)*(.7+unitNoise(i+30)*.55),y=floor+s*.29;
      leaves.push({p:[x,y,z],s:[s,s*.60,s*.85],r:[0,i*2.4,0]});
      if(unitNoise(i+78)<(o.flowers??.18))for(let k=0;k<5;k++)flowers.push({p:[x+Math.sin(k*2.4)*s*.5,y+s*.52,z+Math.cos(k*2.4)*s*.4],s:[.055,.05,.055],c:['#d1c4ae','#a58e98','#a8b8bc'][k%3]});
    }
    instances(g,new THREE.IcosahedronGeometry(1,2),leaves,o.leafColor??color(o,'leaf'),'market-shrub-crowns');
    instances(g,new THREE.IcosahedronGeometry(1,1),flowers,'#ffffff','market-flower-heads');
    if(o.border!==false)for(const side of [-1,1]){block(g,side*w/2,.10,0,.12,.2,d+.1,color(o,'trim'));block(g,0,.10,side*d/2,w,.2,.12,color(o,'trim'));}
    g.updateWorldMatrix(true,true);
    for(const [x,z,height] of o.pines??[]){const p=g.localToWorld(new THREE.Vector3(x,0,z));tree({position:[p.x,p.y,p.z],height,kind:'pine'});}
  });
  // Extensions are opt-in: the original six builders and their defaults stay unchanged.
  function polygon(points){
    const p=points.map(v=>[...v]);if(p.length>1&&p[0][0]===p.at(-1)[0]&&p[0][1]===p.at(-1)[1])p.pop();
    const area=p.reduce((s,a,i)=>{const b=p[(i+1)%p.length];return s+a[0]*b[1]-b[0]*a[1];},0);
    if(p.length<3||!p.every(a=>a.length===2&&a.every(Number.isFinite))||Math.abs(area)<.01)throw new TypeError('Market polygon must have finite, nondegenerate vertices');
    return p;
  }
  function polygonFloor(g,p,y,t,c,name=''){
    const s=new THREE.Shape();s.moveTo(p[0][0],-p[0][1]);for(const [x,z] of p.slice(1))s.lineTo(x,-z);s.closePath();
    const geo=new THREE.ExtrudeGeometry(s,{depth:t,bevelEnabled:false,steps:1});geo.rotateX(-Math.PI/2);geo.translate(0,y-t,0);return add(g,geo,c,name);
  }
  function walkSurface(g,m){g.updateWorldMatrix(true,true);walkableGeometries.push(m.geometry.clone().applyMatrix4(m.matrixWorld));}
  function inside(p,x,z){let yes=false;for(let i=0,j=p.length-1;i<p.length;j=i++){const a=p[i],b=p[j];if((a[1]>z)!==(b[1]>z)&&x<(b[0]-a[0])*(z-a[1])/(b[1]-a[1])+a[0])yes=!yes;}return yes;}
  function steps(g,o,w,d,rise,count,name='market-stair-treads'){
    const treads=[],nosings=[],pitch=d/count;for(let i=0;i<count;i++){const h=rise*(i+1)/count;treads.push({p:[0,h/2,d/2-(i+.5)*pitch],s:[w,h,pitch+.006]});nosings.push(-w/2,h+.008,d/2-i*pitch,w/2,h+.008,d/2-i*pitch);}
    lines(g,nosings,o.stepLineColor??color(o,'joint'),'market-stair-nosings');
    const m=instances(g,unit,treads,o.stoneColor??color(o,'trim'),name);
    // A single triangulated ramp follows the top nosings for route raycasts.
    const v=[-w/2,rise,-d/2,w/2,rise,-d/2,w/2,rise/count,d/2,-w/2,rise,-d/2,w/2,rise/count,d/2,-w/2,rise/count,d/2];
    const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(v,3));g.updateWorldMatrix(true,true);walkableGeometries.push(geo.applyMatrix4(g.matrixWorld));return m;
  }
  function railing(g,w,y,z,o,c,name='market-balcony-rails'){
    const h=o.height??.9,pitch=o.spacing??.28,parts=[{p:[0,y+h,z],s:[w,.055,.055]},{p:[0,y+.10,z],s:[w,.045,.045]}];
    for(let x=-w/2;x<=w/2+.001;x+=pitch)parts.push({p:[x,y+h/2,z],s:[.035,h,.035]});instances(g,unit,parts,c,name);
  }
  register('market_building',(g,o)=>{
    const [w,d]=o.size??[24,16],p=polygon(o.footprint??[[-w/2,-d/2],[w/2,-d/2],[w/2,d/2],[-w/2,d/2]]),up=polygon(o.upperFootprint??p),n=o.storeys??6,podium=o.podiumStoreys??n,gh=o.groundHeight??4.8,sh=o.storeyHeight??3.2;
    const floor=o.floorY??.15,terracotta=o.terracotta??'#ab8d78',glass=o.glassColor??'#84958b',roofGroup=new THREE.Group();roofGroup.name='market-building-roof';g.add(roofGroup);
    if(o.interior?.kit==='market_interior')o.entrance??={edge:2,width:o.interior.doorWidth??5};
    polygonFloor(g,p,floor,.16,color(o,'trim'),'market-polygon-floor');
    const foliage=[],fins=[],louvres=[],planters=[],columns=[],lp=o.louvres??{},pp=o.planters===false?null:o.planters??{},leaves=new THREE.IcosahedronGeometry(1,1);
    const frame=(poly,level,y,h,target)=>{
      const winding=Math.sign(poly.reduce((sum,a,i)=>{const b=poly[(i+1)%poly.length];return sum+a[0]*b[1]-b[0]*a[1];},0));
      for(let i=0;i<poly.length;i++){
        const a=poly[i],b=poly[(i+1)%poly.length],dx=b[0]-a[0],dz=b[1]-a[1],len=Math.hypot(dx,dz);if(len<.02)continue;
        const f=new THREE.Group();f.position.set((a[0]+b[0])/2,0,(a[1]+b[1])/2);f.rotation.y=Math.atan2(winding*dz,-winding*dx);target.add(f);
        if(level===0){
          const opening=o.entrance&&i===(o.entrance.edge??2),door=opening?(o.entrance.width??w*.3):0,offset=o.entrance?.offset??0,recess=o.recess??.8;
          if(opening){for(const [lo,hi] of [[-len/2,offset-door/2],[offset+door/2,len/2]])if(hi>lo)block(f,(lo+hi)/2,floor+h/2,-recess,hi-lo,h,.12,glass);}
          else block(f,0,floor+h/2,-recess,len,h,.12,glass);
          const pitch=o.columnSpacing??4,count=Math.max(1,Math.ceil(len/pitch));for(let k=0;k<=count;k++){const x=-len/2+k*len/count;if(opening&&Math.abs(x-offset)<door/2)continue;const pt=f.localToWorld(new THREE.Vector3(x,floor+h/2,0));g.worldToLocal(pt);columns.push({p:pt.toArray(),s:[.22,h,.28],r:[0,f.rotation.y,0]});}
          const bars=[];for(let x=-len/2+.7;x<len/2;x+=1.3)if(!opening||Math.abs(x-offset)>door/2)bars.push({p:[x,floor+h/2,-recess+.08],s:[.045,h,.05]});instances(f,unit,bars,color(o,'trim'),'market-ground-mullions');
        }else{
          block(f,0,y+h/2,-.12,len,h,.16,glass);
          const spacing=lp.spacing??.45,thickness=lp.thickness??.13,depth=lp.depth??.5;
          for(let yy=y+.22;yy<y+h-.10;yy+=spacing){f.updateWorldMatrix(true,true);const pt=g.worldToLocal(f.localToWorld(new THREE.Vector3(0,yy,.12)));louvres.push({p:pt.toArray(),s:[len,thickness,depth],r:[0,f.rotation.y,0]});}
          for(let x=-len/2+.6;x<len/2;x+=o.finSpacing??1.7){const pt=g.worldToLocal(f.localToWorld(new THREE.Vector3(x,y+h/2,.16)));fins.push({p:pt.toArray(),s:[o.finWidth??.10,h-.12,lp.depth??.5],r:[0,f.rotation.y,0]});}
          if(pp&&level%(pp.every??1)===0){const depth=pp.depth??.7,pt=g.worldToLocal(f.localToWorld(new THREE.Vector3(0,y+.08,depth*.38)));planters.push({p:pt.toArray(),s:[len,.22,depth],r:[0,f.rotation.y,0]});for(let x=-len/2+.45;x<len/2-.15;x+=pp.spacing??.85){const pt=g.worldToLocal(f.localToWorld(new THREE.Vector3(x,y+.30,depth*.55)));foliage.push({p:pt.toArray(),s:[.48,.29,.38],c:(Math.floor(x*7)+level)%3===0?'#8e9f81':color(o,'leaf')});}}
        }
      }
    };
    g.updateWorldMatrix(true,true);frame(p,0,0,gh-floor,g);
    for(let level=1;level<=n;level++){
      const y=gh+(level-1)*sh,poly=level>=podium&&o.upperFootprint?up:p;
      polygonFloor(roofGroup,level===podium?p:poly,y,.20,color(o,'trim'));
      if(level<n)frame(poly,level,y,sh,roofGroup);
    }
    // All upper floors move together so the ground-floor cutaway is real, not a roof floating over opaque slabs.
    instances(roofGroup,unit,louvres,terracotta,'market-horizontal-louvres');instances(roofGroup,unit,fins,o.finColor??'#bda58e','market-facade-fins');instances(roofGroup,unit,planters,o.planterColor??'#a49a83','market-planter-ledges');instances(roofGroup,leaves,foliage,'#ffffff','market-ledge-foliage');instances(g,unit,columns,color(o,'trim'),'market-ground-columns');
    if(o.roofGarden!==false){const q=o.roofGarden??{},spacing=q.spacing??2,poly=o.upperFootprint?up:p,items=[],y=gh+(n-1)*sh;const xs=poly.map(a=>a[0]),zs=poly.map(a=>a[1]);for(let x=Math.min(...xs)+.8;x<Math.max(...xs)-.5;x+=spacing)for(let z=Math.min(...zs)+.8;z<Math.max(...zs)-.5;z+=spacing)if(inside(poly,x,z))items.push({p:[x,y+.25,z],s:[.65,.32,.6]});instances(roofGroup,leaves,items,color(o,'leaf'),'market-green-roof');}
    roofRecords.push({group:roofGroup,parameters:{kind:'polygon',width:w,depth:d,eaveHeight:gh,ridgeHeight:gh+(n-1)*sh},tiers:n,thickness:.20,ridgeOrnament:false});
  });
  register('market_entrance',(g,o)=>{
    const [w,d]=o.size??[12,5],rise=o.rise??.9,n=o.steps??6,c=o.canopy===false?null:o.canopy??{},landing=o.landing??1.2;
    steps(g,o,w,d,rise,n);const slab=block(g,0,rise-.08,-d/2-landing/2,w,.16,landing,color(o,'trim'));walkSurface(g,slab);
    if(c){const cw=c.width??w+2,cd=c.depth??d+landing,h=c.height??4.6,z=-landing/2,slats=[],posts=[];for(let x=-cw/2;x<cw/2;x+=c.pitch??.45)slats.push({p:[x,h,z],s:[c.slatWidth??.10,c.slatHeight??.3,cd]});instances(g,unit,slats,c.color??color(o,'wood'),'market-lattice-slats');for(const side of [-1,1]){block(g,side*cw/2,h,z,.18,.34,cd,color(o,'metal'));block(g,0,h,side*cd/2+z,cw,.24,.16,color(o,'metal'));posts.push({p:[side*(cw/2-.2),h/2,-d/2],s:[.18,h,.18]});}instances(g,unit,posts,color(o,'metal'),'market-entrance-posts');sign(g,o.sign,0,h-.6,cd/2+z+.14,cw*.83);}
    if(o.rails!==false)for(const side of [-1,1]){const rail=new THREE.Group();rail.position.x=side*(w/2-.15);rail.rotation.y=Math.PI/2;g.add(rail);const rod=block(rail,0,rise/2+.9,0,Math.hypot(d,rise),.055,.055,color(o,'metal'));rod.rotation.z=Math.atan2(rise,d);}
  });
  register('market_shophouses',(g,o)=>{
    const [w,d]=o.size??[24,7],houses=o.houses??Array.from({length:o.count??4},()=>({})),gap=o.gap??.12,total=houses.reduce((s,h)=>s+(h.width??w/houses.length),0);let cursor=-total/2;
    for(const [i,p] of houses.entries()){
      const width=p.width??w/houses.length,n=p.storeys??o.storeys??3,sh=p.storeyHeight??o.storeyHeight??3,h=n*sh,wall=p.color??o.wallColors?.[i%(o.wallColors?.length||1)]??color(o,'wall'),f=new THREE.Group();f.name='market-house-'+i;f.position.x=cursor+width/2;cursor+=width+gap;g.add(f);
      block(f,0,h/2,-d/2,width,h,.18,wall);for(const side of [-1,1])block(f,side*width/2,h/2,0,.16,h,d,wall);
      block(f,0,sh/2,d/2-.5,width-.2,sh,.16,p.glassColor??color(o,'dark'));for(const side of [-1,1])block(f,side*(width/2-.12),sh/2,d/2,.24,sh,.3,color(o,'trim'));
      for(let level=1;level<n;level++){
        const y=level*sh;block(f,0,y+sh/2,d/2,width,sh,.16,wall);block(f,0,y,0,width+.12,.16,d+.2,color(o,'trim'));
        const count=p.windows??o.windows??2,ww=width/(count+1),frames=[];for(let k=0;k<count;k++){const x=(k-(count-1)/2)*width/count;block(f,x,y+sh*.5,d/2+.10,ww,sh*.55,.08,color(o,'metal'));for(const side of [-1,1])frames.push({p:[x+side*ww/2,y+sh*.5,d/2+.16],s:[.07,sh*.58,.07]});frames.push({p:[x,y+sh*.5,d/2+.16],s:[.035,sh*.55,.045]});}instances(f,unit,frames,color(o,'trim'),'market-house-window-frames');
        if(p.balcony!==false&&o.balcony!==false){const b={...o.balcony,...p.balcony},depth=b.depth??.8;block(f,0,y+.04,d/2+depth/2,width-.20,.14,depth,color(o,'trim'));railing(f,width-.3,y+.10,d/2+depth,b,color(o,'metal'));}
      }
      const rg=roof(f,o,width,d,h,{kind:'flat',overhang:.16,...o.roof,...p.roof});if(rg.kind==='flat')for(const side of [-1,1])block(f,0,h+.3,side*d/2,width,.6,.12,wall);
      if(p.awning!==false&&o.awning!==false)awning(f,o,width-.1,d/2,{height:sh-.3,depth:1.1,posts:false,...o.awning,...p.awning});sign(f,p.sign,0,sh-.55,d/2+.25,width*.85);
      if(p.goods)goods(f,o,0,d/2+.35,width-.6,p.goods);
    }
  });
  register('market_umbrella',(g,o)=>{
    const r=o.radius??1.8,h=o.height??2.5,rise=o.rise??.65,n=o.segments??12,colors=o.fabricColors??['#bdad97','#d4cbb7'],cloth=[],ribs=[];
    for(let i=0;i<n;i++){const a=i*Math.PI*2/n,b=(i+1)*Math.PI*2/n,m=(a+b)/2,geo=new THREE.BufferGeometry(),v=[0,h+rise,0,Math.cos(a)*r*.65,h+rise*.47,Math.sin(a)*r*.65,Math.cos(b)*r*.65,h+rise*.47,Math.sin(b)*r*.65,Math.cos(a)*r*.65,h+rise*.47,Math.sin(a)*r*.65,Math.cos(a)*r,h,Math.sin(a)*r,Math.cos(b)*r,h,Math.sin(b)*r,Math.cos(a)*r*.65,h+rise*.47,Math.sin(a)*r*.65,Math.cos(b)*r,h,Math.sin(b)*r,Math.cos(b)*r*.65,h+rise*.47,Math.sin(b)*r*.65];geo.setAttribute('position',new THREE.Float32BufferAttribute(v,3));geo.computeVertexNormals();const panel=add(g,geo,colors[i%colors.length]);panel.material=panel.material.clone();panel.material.side=THREE.DoubleSide;cloth.push(panel);ribs.push(0,h+rise-.02,0,Math.cos(m)*r,h-.03,Math.sin(m)*r);}
    const fabric=new THREE.Group(),fabricMaterials=new Map();fabric.name='market-umbrella-fabric';g.add(fabric);
    for(const panel of cloth){const key=panel.material.color.getHex();if(fabricMaterials.has(key)){panel.material.dispose();panel.material=fabricMaterials.get(key);}else fabricMaterials.set(key,panel.material);fabric.add(panel);}
    compact(fabric);fabric.children.forEach((panel,i)=>{panel.material=panel.material.clone();panel.material.side=THREE.DoubleSide;panel.name='market-umbrella-tone-'+i;});
    lines(g,ribs,color(o,'trim'),'market-umbrella-ribs');block(g,0,(h+rise)/2,0,.065,h+rise,.065,color(o,'metal'));block(g,0,.06,0,.55,.12,.55,color(o,'wood'));goods(g,o,0,0,r*1.4,o.goods??'produce');
  });
  register('market_shed',(g,o)=>{
    const [w,d]=o.size??[18,5],h=o.height??3.2,spacing=o.postSpacing??3,posts=[],trusses=[],bays=o.bays??Math.max(2,Math.round(w/2.8)),options={kind:'gable',rise:.7,...o.roof};
    const cross=options.kind==='gable'&&(options.ridgeAxis??'x')==='x',rg=new THREE.Group();g.add(rg);if(cross)rg.rotation.y=Math.PI/2;
    const raw=roof(rg,o,cross?d:w,cross?w:d,h,options),r=cross?{...raw,height:(x,z)=>raw.height(-z,x)}:raw;
    const count=Math.max(1,Math.ceil(w/spacing));for(let k=0;k<=count;k++){const x=-w/2+k*w/count;for(const side of [-1,1]){const top=r.height(x,side*(d/2-.12))-.08;posts.push({p:[x,top/2,side*(d/2-.12)],s:[.10,top,.10]});}trusses.push({p:[x,h-.07,0],s:[.09,.16,d]});}instances(g,unit,posts,color(o,'metal'),'market-shed-posts');instances(g,unit,trusses,color(o,'metal'),'market-shed-trusses');
    for(const side of [-1,1])block(g,0,h-.1,side*d/2,w,.22,.10,color(o,'wood'));
    for(let i=0;i<bays;i++)goods(g,o,-w/2+(i+.5)*w/bays,o.goodsZ??0,w/bays-.25,Array.isArray(o.goods)?o.goods[i%o.goods.length]:o.goods??'produce');sign(g,o.sign,0,h-.42,d/2+.10,w*.65);
  });
  register('market_goods',(g,o)=>{
    const [w,d]=o.size??[3,1],n=o.crates??4,items=[],frames=[];goods(g,o,0,0,w,o.kind??'produce');
    for(let k=0;k<n;k++){const x=(k-(n-1)/2)*w/n,z=d*.7,ww=w/n*.87;frames.push({p:[x,.16,z],s:[ww,.30,.55]});for(let j=0;j<9;j++)items.push({p:[x+((j%3)-1)*ww*.25,.36, z+(Math.floor(j/3)-1)*.15],s:[.11,.10,.11],c:['#95a67e','#b5a172','#bb927e'][k%3]});}instances(g,unit,frames,color(o,'wood'),'market-ground-crates');instances(g,new THREE.IcosahedronGeometry(1,1),items,'#ffffff','market-crate-fruit');
  });
  register('market_street',(g,o)=>{
    const [w,d]=o.size??[30,24],[jx,jz]=o.junction??[-w*.3,d*.2],rw=o.roadWidth??7,road=o.roadColor??'#aaa99e',top=o.top??.075;
    const a=block(g,0,top-.035,jz,w,.07,rw,road),b=block(g,jx,top-.035+.002,0,rw,.07,d,road);walkSurface(g,a);walkSurface(g,b);
    const marks=[];if(o.crossings!==false)for(let i=0;i<7;i++){marks.push({p:[jx+(i-3)*rw/8,top+.008,jz+rw*.72],s:[rw/13,.008,2]},{p:[jx+rw*.72,top+.009,jz+(i-3)*rw/8],s:[2,.008,rw/13]});}instances(g,unit,marks,o.markColor??'#d5d0bb','market-crosswalk-stripes');
    for(const p of o.trafficLights??[]){const f=new THREE.Group();f.position.set(...(p.position??[0,0,0]));f.rotation.y=(p.rotation??0)*Math.PI/180;g.add(f);block(f,0,1.8,0,.085,3.6,.085,color(o,'metal'));block(f,.36,3.5,0,.8,.075,.075,color(o,'metal'));block(f,.7,3.16,0,.26,.8,.22,color(o,'dark'),'market-traffic-heads');const lights=[];for(let i=0;i<3;i++)lights.push({p:[.7,3.4-i*.24,.13],s:[.075,.075,.03],c:['#b88470','#c2af7c','#8caa90'][i]});instances(f,new THREE.SphereGeometry(1,8,6),lights,'#ffffff','market-traffic-lenses');}
    const wheels=[],bodies=[],metal=[];for(const [i,p] of (o.motorbikes??[]).entries()){
      const [x,z,yaw=0]=p,a=yaw*Math.PI/180,point=(xx,y,zz)=>[x+xx*Math.cos(a)+zz*Math.sin(a),y,z-xx*Math.sin(a)+zz*Math.cos(a)];
      for(const zz of [-.58,.58]){wheels.push({p:point(0,.28,zz),s:[.25,.09,.25],r:[0,a,Math.PI/2]});metal.push({p:point(0,.3,zz),s:[.12,.105,.12],r:[0,a,Math.PI/2]});}
      bodies.push({p:point(0,.58,0),s:[.42,.48,1.0],r:[0,a,0],c:o.bikeColors?.[i%(o.bikeColors?.length||1)]??['#8c9990','#a28c7e','#b9b4a1'][i%3]},{p:point(0,.85,-.15),s:[.4,.12,.65],r:[0,a,0],c:color(o,'dark')});metal.push({p:point(0,1.04,.5),s:[.7,.045,.055],r:[0,a,0]},{p:point(0,.75,.5),s:[.07,.60,.07],r:[.15,a,0]});
    }instances(g,new THREE.CylinderGeometry(1,1,1,12),wheels,color(o,'dark'),'market-motorbike-wheels');instances(g,new THREE.CylinderGeometry(1,1,1,10),metal,color(o,'metal'),'market-motorbike-fittings');instances(g,unit,bodies,'#ffffff','market-parked-motorbikes');
  });
  registerInteriorKit('market_interior',(o,{roof:shellRoof}={})=>{
    const p=o.interior??{},[bw,bd]=o.size??[20,14],[w,d]=p.size??[bw-.6,bd-.6],h=p.height??4.6,y=(p.floorY??((o.position?.[1]??0)+(o.floorY??.15)+.03))-(o.position?.[1]??0),g=new THREE.Group(),ceiling=new THREE.Group(),front=new THREE.Group(),door=new THREE.Group(),offset=p.offset??[0,0],wood=p.wood??color(o,'wood'),wall=p.wall??color(o,'trim');
    g.name=o.id+'-interior';g.position.set(...(o.position??[0,0,0]));g.rotation.y=(o.rotation??0)*Math.PI/180;const room=new THREE.Group();room.position.set(offset[0],0,offset[1]);g.add(room);ceiling.position.copy(room.position);front.name='market-interior-front';door.name='market-interior-door';room.add(front,door);
    // Supply world-space viewer defaults without changing the shared template or authored overrides.
    o.interior=p;g.updateMatrixWorld(true);const world=(x,yy,z)=>room.localToWorld(new THREE.Vector3(x,yy,z)).toArray();
    p.floorY??=y+(o.position?.[1]??0);p.entry??=world(0,y+1.6,d/2+.25);p.approach??=world(0,y+1.6,d/2+3);
    const roofBounds=shellRoof?new THREE.Box3().setFromObject(shellRoof):null;
    p.boundsCenter??=world(0,y,0);p.boundsDepth??=d;p.safeApproach??=true;p.ridgeHeight??=roofBounds&&!roofBounds.isEmpty()?roofBounds.max.y-(o.position?.[1]??0):(o.groundHeight??4.8)+((o.storeys??6)-1)*(o.storeyHeight??3.2)+.6;p.dimmingSize??=[w+2*Math.abs(offset[0]),d+2*Math.abs(offset[1])];p.lights??={};p.lights.altar??=world(0,y+h*.7,-d*.22);p.lights.fill??=world(0,y+h*.7,d*.22);
    block(room,0,y-.04,0,w,.08,d,p.floorColor??'#ccc6b5','market-interior-floor');for(const side of [-1,1])block(room,side*w/2,y+h/2,0,.14,h,d,wall);block(room,0,y+h/2,-d/2,w,h,.14,wall);
    const dw=p.doorWidth??5,dh=p.doorHeight??3.8;for(const side of [-1,1])block(front,side*(w+dw)/4,y+h/2,d/2,(w-dw)/2,h,.14,wall);if(h>dh)block(front,0,y+dh+(h-dh)/2,d/2,dw,h-dh,.14,wall);
    const tile=p.tileSize??.6,joints=[];for(let x=-w/2;x<w/2;x+=tile)joints.push(x,y+.006,-d/2,x,y+.006,d/2);for(let z=-d/2;z<d/2;z+=tile)joints.push(-w/2,y+.007,z,w/2,y+.007,z);lines(room,joints,p.jointColor??'#ada997','market-interior-tile-joints');
    const aisle=p.aisleWidth??4,n=p.stalls??5,pitch=(d-4)/n,depth=p.stallDepth??2.5,shelves=[],items=[],goodsGroup=new THREE.Group();goodsGroup.name='market-interior-goods';room.add(goodsGroup);
    for(const side of [-1,1])for(let i=0;i<n;i++){
      const z=d/2-2-(i+.5)*pitch,x=side*(aisle/2+depth/2),length=pitch-.18;
      block(room,side*(aisle/2+depth-.08),y+1.25,z,.16,2.5,length,p.stallColor??'#aaa58d');block(room,x,y+.4,z,depth,.8,length,wood);block(room,x,y+.84,z,depth+.1,.08,length+.05,wood);
      // Faces look into the central corridor; packages and shelves are at true market scale.
      for(let level=0;level<4;level++){
        const yy=y+1.05+level*.32;shelves.push({p:[side*(aisle/2+depth*.75),yy,z],s:[depth*.42,.055,length]});
        for(let k=0;k<Math.max(3,Math.floor(length/.22));k++)items.push({p:[side*(aisle/2+.2),yy+.13,z-length/2+.14+k*.22],s:[.20,.24,.16],c:['#b5aa7f','#a58b73','#8d9c82','#c4bba2'][(i+k+level)%4]});
      }
      block(room,x,y+2.65,z,depth+.1,.38,length,wood);const f=new THREE.Group();f.position.set(side*(aisle/2-.08),y,z);f.rotation.y=-side*Math.PI/2;room.add(f);if(p.signs?.length)sign(f,{text:p.signs[i%p.signs.length],height:.32,background:wood,color:'#e7ddc1'},0,2.65,0,length*.9);
    }instances(goodsGroup,unit,shelves,wood,'market-interior-shelves');instances(goodsGroup,unit,items,'#ffffff','market-interior-packages');
    if(p.stair!==false){const s=p.stair??{},f=new THREE.Group(),sw=s.width??aisle*.8,sd=s.depth??4,sr=s.rise??2.4;f.name='market-central-stair';f.position.set(s.position?.[0]??0,y,s.position?.[1]??-d/2+3);room.add(f);steps(f,o,sw,sd,sr,s.steps??14,'market-interior-stair-treads');const rails=[],hands=[];for(const side of [-1,1]){for(let k=0;k<7;k++)rails.push({p:[side*sw/2,.45+sr*k/6,sd/2-k*sd/6],s:[.035,.9,.035]});hands.push({p:[side*sw/2,.9+sr/2,0],s:[.065,.065,Math.hypot(sd,sr)],r:[Math.atan2(sr,sd),0,0]});}instances(f,unit,rails,color(o,'metal'),'market-central-stair-rails');instances(f,unit,hands,color(o,'metal'),'market-central-stair-handrails');}
    block(ceiling,0,y+h,0,w+.3,.18,d+.3,p.ceilingColor??'#d7d2c4','market-sealed-ceiling');const beams=[],lights=[],lm=new THREE.MeshStandardMaterial({color:'#e6e9d9',emissive:'#dce4d1',emissiveIntensity:.65,roughness:1});
    for(let z=-d/2+.6;z<d/2;z+=p.lightSpacing??2.4){beams.push({p:[0,y+h-.18,z],s:[w,.22,.13]});for(const x of [-aisle*.65,aisle*.65])lights.push({p:[x,y+h-.33,z],s:[.10,.07,1.2]});}instances(ceiling,unit,beams,p.beamColor??'#a5aa9e','market-interior-ceiling-beams');const strips=instances(ceiling,unit,lights,'#e6e9d9','market-fluorescent-strips');strips.material=lm;
    compact(g);compact(ceiling);
    const litMaterials=new Map();for(const group of [g,ceiling])group.traverse(m=>{if(!m.isMesh||!m.material.emissive||m.name==='market-fluorescent-strips')return;const source=m.material;if(!litMaterials.has(source)){const mat=source.clone();mat.emissive.copy(mat.color);mat.emissiveIntensity=p.ambientFill??.14;litMaterials.set(source,mat);}m.material=litMaterials.get(source);});
    front.traverse(m=>{if(m.isMesh)m.material=m.material.clone();});return {group:g,ceiling,front,door};
  });
})();
