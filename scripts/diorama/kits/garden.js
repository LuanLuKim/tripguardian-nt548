// Reusable studio garden vocabulary. Metres; +x east, +z south; rotations in degrees.
(()=>{
  const C={lawn:'#b8bea5',leaf:'#92a080',edge:'#929f7c',soil:'#9caa8c',paving:'#d7d2c5',joint:'#bdb9ab',wood:'#887462',roof:'#807266',frame:'#ddd7c9',water:'#a5b8b4',flowers:['#b393a4','#d4bd92','#d5cfbc','#9eaebc']};
  const rad=d=>d*Math.PI/180;
  const hash=n=>{const v=Math.sin(n*127.1+311.7)*43758.5453;return v-Math.floor(v);};
  function root(o){const g=new THREE.Group();g.name=o.id+'-garden';g.position.set(...(o.position||[0,0,0]));g.rotation.y=rad(o.rotation||0);scene.add(g);return g;}
  function add(g,geo,c,name=''){const m=new THREE.Mesh(geo,material(c));m.name=name;m.castShadow=true;m.receiveShadow=true;g.add(m);return m;}
  function block(g,x,y,z,w,h,d,c,name=''){const m=add(g,new THREE.BoxGeometry(w,h,d),c,name);m.position.set(x,y,z);return m;}
  function cylinder(g,x,y,z,r,h,c,top=r,sides=24){const m=add(g,new THREE.CylinderGeometry(top,r,h,sides),c);m.position.set(x,y,z);return m;}
  function rod(g,a,b,r,c){const u=new THREE.Vector3(...a),v=new THREE.Vector3(...b),d=v.clone().sub(u),m=add(g,new THREE.CylinderGeometry(r,r,d.length(),6),c);m.position.copy(u.add(v).multiplyScalar(.5));m.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),d.normalize());return m;}
  function instances(g,geo,items,c,name){
    if(!items.length)return;
    const m=new THREE.InstancedMesh(geo,material(c),items.length),dummy=new THREE.Object3D();m.name=name;m.castShadow=true;m.receiveShadow=true;g.add(m);
    items.forEach((p,i)=>{dummy.position.set(...p.p);dummy.scale.set(...(p.s||[1,1,1]));dummy.rotation.set(...(p.r||[0,0,0]));dummy.updateMatrix();m.setMatrixAt(i,dummy.matrix);if(p.c)m.setColorAt(i,new THREE.Color(p.c));});
    m.instanceMatrix.needsUpdate=true;m.computeBoundingBox();m.computeBoundingSphere();
    if(currentEnvelope){g.updateWorldMatrix(true,true);const b=m.boundingBox;for(const x of [b.min.x,b.max.x])for(const y of [b.min.y,b.max.y])for(const z of [b.min.z,b.max.z])currentEnvelope.push(new THREE.Vector3(x,y,z).applyMatrix4(m.matrixWorld));}
    return m;
  }
  function compact(g){
    for(const c of g.children)if(c.isGroup)compact(c);
    const batches=new Map();for(const m of g.children){if(!m.isMesh||m.isInstancedMesh||m.material.map)continue;const key=m.material.uuid;if(!batches.has(key))batches.set(key,[]);batches.get(key).push(m);}
    for(const list of batches.values())if(list.length>1){const geometries=list.map(m=>{m.updateMatrix();const geo=m.geometry.index?m.geometry.toNonIndexed():m.geometry.clone();for(const k of Object.keys(geo.attributes))if(!['position','normal'].includes(k))geo.deleteAttribute(k);return geo.applyMatrix4(m.matrix);});const m=new THREE.Mesh(mergeGeometries(geometries),list[0].material);m.name='garden-batch';m.castShadow=true;m.receiveShadow=true;list.forEach(p=>{g.remove(p);p.geometry.dispose();});geometries.forEach(p=>p.dispose());g.add(m);}
  }
  function register(type,builder){registerObjectType(type,o=>{const g=root(o);builder(o,g);compact(g);});}
  function boundary(o){
    const [w,d]=o.size||[12,8],shape=o.shape||'ellipse';
    if(o.outline)return o.outline.map(p=>p.slice());
    if(shape==='rectangle')return [[-w/2,-d/2],[w/2,-d/2],[w/2,d/2],[-w/2,d/2]];
    const start=rad(o.startAngle??0),end=rad(o.endAngle??360),points=[];
    if(shape==='sector')points.push([0,0]);
    for(let i=0;i<=64;i++){const a=start+(end-start)*i/64;points.push([Math.cos(a)*w/2,Math.sin(a)*d/2]);}return points;
  }
  function inside(x,z,poly){let yes=false;for(let i=0,j=poly.length-1;i<poly.length;j=i++){const a=poly[i],b=poly[j];if((a[1]>z)!==(b[1]>z)&&x<(b[0]-a[0])*(z-a[1])/(b[1]-a[1])+a[0])yes=!yes;}return yes;}
  function inset(poly,width){
    const points=poly.filter((p,i)=>Math.hypot(p[0]-poly[(i+1)%poly.length][0],p[1]-poly[(i+1)%poly.length][1])>1e-7);
    const area=points.reduce((s,p,i)=>{const q=points[(i+1)%points.length];return s+p[0]*q[1]-q[0]*p[1];},0),sign=Math.sign(area);
    const invalid=()=>{throw new RangeError('garden_water: rimWidth requires a simple, connected inset inside outline; reduce width or split pond');};
    if(points.length<3||!Number.isFinite(width)||width<=0||Math.abs(area)<1e-7)invalid();
    const normals=points.map((p,i)=>{const q=points[(i+1)%points.length],length=Math.hypot(q[0]-p[0],q[1]-p[1]);return [-(q[1]-p[1])/length*sign,(q[0]-p[0])/length*sign];});
    const inner=points.map((p,i)=>{const a=normals[(i+points.length-1)%points.length],b=normals[i],den=1+a[0]*b[0]+a[1]*b[1];if(den<1e-8)invalid();return [p[0]+width*(a[0]+b[0])/den,p[1]+width*(a[1]+b[1])/den];});
    const distance=(p,a,b)=>{const dx=b[0]-a[0],dz=b[1]-a[1],t=Math.max(0,Math.min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dz)/(dx*dx+dz*dz)));return Math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dz);};
    const cross=(a,b,c)=>(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
    const intersect=(a,b,c,d)=>{const u=cross(a,b,c),v=cross(a,b,d),s=cross(c,d,a),t=cross(c,d,b);return u*v< -1e-10&&s*t< -1e-10||distance(c,a,b)<1e-7||distance(d,a,b)<1e-7||distance(a,c,d)<1e-7||distance(b,c,d)<1e-7;};
    for(let i=0;i<points.length;i++){
      const a=inner[i],b=inner[(i+1)%inner.length],p=points[i],q=points[(i+1)%points.length];
      if((b[0]-a[0])*(q[0]-p[0])+(b[1]-a[1])*(q[1]-p[1])<=1e-7)invalid();
      for(const sample of [a,[(a[0]+b[0])/2,(a[1]+b[1])/2]])if(!inside(...sample,points)||points.some((p,j)=>distance(sample,p,points[(j+1)%points.length])<width-1e-6))invalid();
      for(let j=i+2;j<points.length;j++){if(i===0&&j===points.length-1)continue;if(intersect(a,b,inner[j],inner[(j+1)%inner.length])||intersect(p,q,points[j],points[(j+1)%points.length]))invalid();}
    }
    return inner;
  }
  function slab(g,poly,bottom,top,color,walk=false,holes=[]){
    const shape=new THREE.Shape(poly.map(([x,z])=>new THREE.Vector2(x,-z)));
    for(const hole of holes)shape.holes.push(new THREE.Path(hole.map(([x,z])=>new THREE.Vector2(x,-z))));
    const geo=new THREE.ExtrudeGeometry(shape,{depth:top-bottom,bevelEnabled:false,curveSegments:4});geo.rotateX(-Math.PI/2);geo.translate(0,bottom,0);
    const m=add(g,geo,color,'garden-slab');if(walk){g.updateMatrixWorld(true);walkableGeometries.push((geo.index?geo.toNonIndexed():geo.clone()).applyMatrix4(m.matrixWorld));}return m;
  }
  function edges(g,poly,width,height,color){
    const items=[];for(let i=0;i<poly.length;i++){const a=poly[i],b=poly[(i+1)%poly.length],length=Math.hypot(b[0]-a[0],b[1]-a[1]);if(length<.001)continue;items.push({p:[(a[0]+b[0])/2,height/2-.03,(a[1]+b[1])/2],s:[width,height,length+width*.3],r:[0,Math.atan2(b[0]-a[0],b[1]-a[1]),0]});}instances(g,new THREE.BoxGeometry(1,1,1),items,color,'garden-edging');
  }
  function flowerGeometry(){const p=[];for(let i=0;i<5;i++){const a=i*Math.PI*2/5,b=a+.5;const u=[Math.cos(a)*.25,.08,Math.sin(a)*.25],v=[Math.cos(b)*.48,0,Math.sin(b)*.48],w=[Math.cos(a+1)*.25,.08,Math.sin(a+1)*.25];p.push(0,.04,0,...v,...u,0,.04,0,...w,...v);}const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(p,3));geo.computeVertexNormals();return geo;}
  const bloom=flowerGeometry(),sphere=new THREE.SphereGeometry(1,8,5),leaf=new THREE.IcosahedronGeometry(1,0),cube=new THREE.BoxGeometry(1,1,1);
  function planting(o,g,poly,baseY=0){
    const spacing=o.spacing??.85,height=o.height??.36,colors=o.colors||C.flowers,pattern=o.pattern||'solid',bands=o.bands??4,seed=o.seed??1;
    const xs=poly.map(p=>p[0]),zs=poly.map(p=>p[1]),x0=Math.min(...xs),x1=Math.max(...xs),z0=Math.min(...zs),z1=Math.max(...zs),cx=(x0+x1)/2,cz=(z0+z1)/2;
    const leaves=[],flowers=[];let i=0;
    for(let x=x0+spacing*.4;x<x1;x+=spacing)for(let z=z0+spacing*.4;z<z1;z+=spacing){i++;const px=x+(hash(i+seed)-.5)*spacing*.6,pz=z+(hash(i*3+seed)-.5)*spacing*.6;if(!inside(px,pz,poly))continue;
      const n=Math.hypot((px-cx)/((x1-x0)/2),(pz-cz)/((z1-z0)/2));let band=0;
      if(pattern==='rings')band=Math.floor(n*bands);if(pattern==='stripes')band=Math.floor((px-x0)/(x1-x0)*bands);if(pattern==='petals')band=Math.floor((Math.atan2(pz-cz,px-cx)+Math.PI)/Math.PI/2*bands);
      const color=colors[((band%colors.length)+colors.length)%colors.length],s=.7+hash(i*7+seed)*.6;
      leaves.push({p:[px,baseY+.1+height*.25,pz],s:[spacing*.66,height*.4,spacing*.56],c:o.leafColor||C.leaf});
      for(let k=0;k<(o.flowersPerPlant??3);k++){const a=hash(i*5+k)*Math.PI*2,r=spacing*.29*hash(i*9+k);flowers.push({p:[px+Math.cos(a)*r,baseY+.16+height*.73+hash(i+k)*height*.2,pz+Math.sin(a)*r],s:[s*spacing*.43,s*.7,s*spacing*.43],r:[0,a,0],c:color});}
    }
    instances(g,o.foliageForm==='foam'?sphere:leaf,leaves,'#ffffff','garden-leaf-mats');instances(g,bloom,flowers,'#ffffff','garden-flower-drifts');
  }
  register('garden_surface',(o,g)=>{
    const poly=boundary({...o,shape:o.shape||'rectangle'}),top=o.level??.025;slab(g,poly,-.06,top,o.color||C.lawn,!!o.walkable);
    if(o.jointSpacing){const pitch=o.jointSpacing,items=[],xs=poly.map(p=>p[0]),zs=poly.map(p=>p[1]);for(let x=Math.min(...xs)+pitch;x<Math.max(...xs);x+=pitch)for(let z=Math.min(...zs)+pitch/2;z<Math.max(...zs);z+=pitch)if(inside(x,z,poly)&&inside(x,z+pitch*.45,poly)&&inside(x,z-pitch*.45,poly))items.push({p:[x,top+.004,z],s:[.025,.006,pitch*.9]});instances(g,cube,items,C.joint,'garden-surface-joints');}
  });
  register('garden_path',(o,g)=>{
    if(o.terrain||o.kerbWidth||o.tileRows){landscapePath(o,g);return;}
    const width=o.width??3.4,top=o.level??.075,color=o.color||C.paving,legs=o.followRoute?place.route:(o.legs||[o.shape?boundary(o):o.points||[[0,0],[0,-12]]]),joints=[];
    for(const original of legs){const points=original.slice();if(o.closed)points.push(points[0]);
      for(let i=1;i<points.length;i++){const a=points[i-1],b=points[i],dx=b[0]-a[0],dz=b[1]-a[1],len=Math.hypot(dx,dz);if(len<.001)continue;const nx=-dz/len*width/2,nz=dx/len*width/2;
        slab(g,[[a[0]+nx,a[1]+nz],[b[0]+nx,b[1]+nz],[b[0]-nx,b[1]-nz],[a[0]-nx,a[1]-nz]],-.04,top,color,true);
        for(let t=(o.jointSpacing??1.5);t<len;t+=o.jointSpacing??1.5)joints.push({p:[a[0]+dx*t/len,top+.004,a[1]+dz*t/len],s:[width*.94,.006,.018],r:[0,Math.atan2(dx,dz),0]});
      }
      for(const p of points){const disk=Array.from({length:20},(_,i)=>[p[0]+Math.cos(i*Math.PI/10)*width/2,p[1]+Math.sin(i*Math.PI/10)*width/2]);slab(g,disk,-.04,top-.001,color,true);}
    }
    instances(g,cube,joints,o.jointColor||C.joint,'garden-path-joints');
  });
  register('garden_bed',(o,g)=>{const poly=boundary(o);slab(g,poly,-.045,.085,o.soilColor||C.soil);if(o.border!==false)edges(g,poly,o.borderWidth??.28,o.borderHeight??.26,o.borderColor||C.edge);planting(o,g,poly);});
  register('garden_water',(o,g)=>{
    const poly=boundary(o),rim=o.rimWidth??.45,rimLevel=o.level??.25,level=rimLevel-.08;const xs=poly.map(p=>p[0]),zs=poly.map(p=>p[1]),cx=(Math.min(...xs)+Math.max(...xs))/2,cz=(Math.min(...zs)+Math.max(...zs))/2;
    const inner=inset(poly,rim);
    slab(g,poly,Math.min(-.05,level-.04),rimLevel,o.rimColor||C.frame,false,[inner]);slab(g,inner,Math.min(-.05,level-.04),level,o.color||C.water);
    if(o.fountain){const p=o.fountain,h=p.height??3,tiers=p.tiers??2;cylinder(g,cx,level+.25,cz,.7,.5,o.rimColor||C.frame);cylinder(g,cx,level+h/2,cz,.15,h,C.frame,.12,12);
      for(let i=0;i<tiers;i++){const y=level+.7+i*(h-.7)/Math.max(1,tiers-1),r=(p.radius??1.8)*(1-i*.32);cylinder(g,cx,y,cz,r,.2,o.rimColor||C.frame,r*.9);for(let j=0;j<12;j++){const a=j*Math.PI/6,curve=new THREE.CatmullRomCurve3([new THREE.Vector3(cx+Math.cos(a)*r*.8,y+.08,cz+Math.sin(a)*r*.8),new THREE.Vector3(cx+Math.cos(a)*r*1.15,y-.15,cz+Math.sin(a)*r*1.15),new THREE.Vector3(cx+Math.cos(a)*r*1.2,level+.06,cz+Math.sin(a)*r*1.2)]);add(g,new THREE.TubeGeometry(curve,8,.025,3,false),o.color||C.water);}}
    }
  });
  function arch(g,a,style,colors,options){
    const x=a.x??0,w=a.width??8,h=a.height??9,d=a.depth??1.5,t=a.thickness??1.1,r=w/2,spring=h-r,c=style==='metal'?C.frame:C.leaf,segments=48,foliage=[];
    for(const side of [-1,1]){block(g,x+side*(r+t/2),spring/2-.025,0,t,spring+.05,d,c);block(g,x+side*(r+t/2),.1,0,t+.45,.3,d+.4,C.frame);}
    const shape=new THREE.Shape();shape.absarc(x,spring,r+t,0,Math.PI,false);shape.absarc(x,spring,r,Math.PI,0,true);shape.closePath();const geo=new THREE.ExtrudeGeometry(shape,{depth:d,bevelEnabled:false,curveSegments:24});geo.translate(0,0,-d/2);add(g,geo,c);
    if(style!=='metal'){
      const spacing=options.coverSpacing??.35,layers=Math.max(2,Math.ceil(t/spacing)),count=Math.ceil(Math.PI*(r+t)/spacing),share=options.flowerShare??.18;
      const color=n=>hash(Math.floor(n/7))<share?colors[1%colors.length]:colors[hash(n)>.75?colors.length-1:0];
      for(let i=0;i<=count;i++){const angle=i/count*Math.PI;for(let j=0;j<layers;j++){const n=i*layers+j,radius=r+t*(j+.5+(hash(n)-.5)*.5)/layers;foliage.push({p:[x+Math.cos(angle)*radius,spring+Math.sin(angle)*radius,d/2+.02+hash(n+4)*.08],s:[spacing*(.65+hash(n)*.3),spacing*.65,spacing*.27],r:[0,0,hash(n+2)*Math.PI],c:color(n)});}}
      for(const side of [-1,1])for(let y=spacing/2;y<spring;y+=spacing)for(let j=0;j<layers;j++){const n=Math.floor(y/spacing)*layers+j;foliage.push({p:[x+side*(r+t*(j+.5)/layers),y+(hash(n+9)-.5)*spacing*.4,d/2+.04],s:[spacing*.7,spacing*.7,spacing*.29],r:[0,0,hash(n)*Math.PI],c:color(n+Math.floor(x*3))});}
      instances(g,leaf,foliage,'#ffffff','garden-arch-foliage');
    }
    return {x,r,spring,t,d};
  }
  register('garden_arch',(o,g)=>{
    if(o.outline==='heart'||o.repeat||o.canopy){archTunnel(o,g);return;}
    const arches=o.arches||[{}],colors=o.colors||[C.leaf,'#b397a5','#a7ae91'];let first;
    for(const a of arches){const p=arch(g,a,o.style||'foliage',colors,o);first??=p;}
    if(o.sign){const a=first,canvas=document.createElement('canvas');canvas.width=1536;canvas.height=192;const ctx=canvas.getContext('2d');ctx.clearRect(0,0,1536,192);ctx.font='bold 120px Georgia';ctx.textAlign='center';ctx.textBaseline='middle';ctx.strokeStyle=C.frame;ctx.lineWidth=10;ctx.strokeText(o.sign,768,96,1500);ctx.fillStyle=o.signColor||'#9d7569';ctx.fillText(o.sign,768,96,1500);const tex=new THREE.CanvasTexture(canvas);tex.colorSpace=THREE.SRGBColorSpace;
      const vertices=[],uv=[],indices=[];for(let i=0;i<=48;i++){const angle=2.5-i/48*1.86;for(const r of [a.r+a.t*.3,a.r+a.t*1.18]){vertices.push(a.x+Math.cos(angle)*r,a.spring+Math.sin(angle)*r,a.d/2+.23);uv.push(i/48,r===a.r+a.t*.3?0:1);}if(i<48){const k=i*2;indices.push(k,k+2,k+1,k+1,k+2,k+3);}}
      const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));geo.setAttribute('uv',new THREE.Float32BufferAttribute(uv,2));geo.setIndex(indices);geo.computeVertexNormals();const m=new THREE.Mesh(geo,new THREE.MeshBasicMaterial({map:tex,transparent:true,side:THREE.DoubleSide,depthWrite:false}));m.name='garden-arch-sign';g.add(m);
    }
  });
  register('garden_structure',(o,g)=>{
    const kind=o.kind||'gazebo',[w,d,h]=o.size||[7,7,4],rise=o.roofRise??2,color=o.color||C.wood,frame=o.frameColor||C.frame,roofColor=o.roofColor||C.roof;
    const base=o.baseHeight??.2,poly=kind==='gazebo'?Array.from({length:o.sides??6},(_,i)=>[Math.cos(i*Math.PI*2/(o.sides??6))*w/2,Math.sin(i*Math.PI*2/(o.sides??6))*d/2]):boundary({...o,size:[w,d],shape:o.outline?'polygon':'rectangle'});slab(g,poly,-.06,base,o.baseColor||C.frame);
    const cx=o.outline?poly.reduce((v,p)=>v+p[0],0)/poly.length:0,cz=o.outline?poly.reduce((v,p)=>v+p[1],0)/poly.length:0;
    if(o.baseCourseHeight){const vertices=[];for(let y=o.baseCourseHeight;y<base;y+=o.baseCourseHeight)for(let i=0;i<poly.length;i++){const a=poly[i],b=poly[(i+1)%poly.length];vertices.push(cx+(a[0]-cx)*1.003,y,cz+(a[1]-cz)*1.003,cx+(b[0]-cx)*1.003,y,cz+(b[1]-cz)*1.003);}const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));const lines=new THREE.LineSegments(geo,new THREE.LineBasicMaterial({color:'#9c9f93',transparent:true,opacity:.6}));lines.name='garden-base-courses';g.add(lines);}
    const roof=new THREE.Group();roof.name='garden-structure-roof';g.add(roof);
    if(kind==='kiosk'){
      slab(g,poly,base,h,color);slab(roof,poly,h,h+.2,roofColor);
      if(!o.outline){block(g,0,h*.55,d/2+.02,w*.7,h*.38,.06,o.glassColor||'#aab8b3');block(g,0,h*.35,d/2+.15,w*.8,.12,.4,frame);}
    }else if(kind==='gazebo'){
      const sides=o.sides??6,radius=w/2,cols=[];for(let i=0;i<sides;i++){const a=i/sides*Math.PI*2,x=Math.cos(a)*radius,z=Math.sin(a)*d/2;cols.push({p:[x,(h+base)/2,z],s:[.2,h-base,.2]});if(o.railings!==false&&i!==0){const b=(i+1)/sides*Math.PI*2;for(const y of [.65,1.2])rod(g,[x,y+base,z],[Math.cos(b)*radius,y+base,Math.sin(b)*d/2],.045,frame);}}
      instances(g,cube,cols,color,'garden-pavilion-posts');const geo=new THREE.ConeGeometry(1,rise,sides);geo.rotateY(Math.PI/2);geo.scale(w*.63,1,d*.63);const m=add(roof,geo,roofColor);m.position.y=h+rise/2-.03;
      for(let i=0;i<sides;i++){const a=i/sides*Math.PI*2;rod(roof,[0,h+rise,0],[Math.cos(a)*w*.63,h,Math.sin(a)*d*.63],.055,frame);}cylinder(roof,0,h+rise+.12,0,.09,.3,frame);
      const pitch=o.roofLineSpacing??.4;if(pitch>0){const vertices=[];for(let down=pitch;down<rise;down+=pitch){const t=down/rise,y=h+rise-down+.035;for(let i=0;i<sides;i++){const a=i*Math.PI*2/sides,b=(i+1)*Math.PI*2/sides;vertices.push(Math.cos(a)*w*.63*t,y,Math.sin(a)*d*.63*t,Math.cos(b)*w*.63*t,y,Math.sin(b)*d*.63*t);}}const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));const lines=new THREE.LineSegments(geo,new THREE.LineBasicMaterial({color:o.roofLineColor||'#a39180',transparent:true,opacity:.5}));lines.name='garden-roof-courses';roof.add(lines);}
    }else{
      const bays=o.bays??4,posts=[],glass=o.glassColor||'#bbc9c1';
      for(let i=0;i<=bays;i++){const z=-d/2+i*d/bays;for(const side of [-1,1])posts.push({p:[side*w/2,h/2,z],s:[.1,h,.1]});rod(roof,[-w/2,h,z],[0,h+rise,z],.055,frame);rod(roof,[0,h+rise,z],[w/2,h,z],.055,frame);}
      instances(g,cube,posts,frame,'garden-glasshouse-frame');
      const mat=material(glass).clone();mat.transparent=true;mat.opacity=o.opacity??.42;mat.depthWrite=false;mat.side=THREE.DoubleSide;
      for(const side of [-1,1]){const wall=block(g,side*w/2,h/2,0,.025,h,d,glass);wall.material=mat;const slope=Math.hypot(w/2,rise),m=block(roof,side*w/4,h+rise/2,0,slope,.035,d,glass);m.rotation.z=-side*Math.atan2(rise,w/2);m.material=mat;}
      for(const side of [-1,1]){
        const end=block(g,0,h/2,side*d/2,w,h,.025,glass);end.material=mat;
        const triangle=new THREE.Shape();triangle.moveTo(-w/2,h);triangle.lineTo(w/2,h);triangle.lineTo(0,h+rise);triangle.closePath();
        const gable=add(roof,new THREE.ShapeGeometry(triangle),glass);gable.position.z=side*d/2;gable.material=mat;
        rod(g,[-w/2,h,side*d/2],[w/2,h,side*d/2],.055,frame);
        for(const x of [-w/2,0,w/2])rod(g,[x,.2,side*d/2],[x,h,side*d/2],.055,frame);
      }
      rod(roof,[0,h+rise,-d/2],[0,h+rise,d/2],.06,frame);
      if(kind==='greenhouse'){const beds=o.cropRows??3;for(let i=0;i<beds;i++){const x=-w*.35+(i+.5)*w*.7/beds;slab(g,[[x-.35,-d*.43],[x+.35,-d*.43],[x+.35,d*.43],[x-.35,d*.43]],base,base+.2,C.soil);planting({spacing:.8,height:.25,colors:o.cropColors||['#a5af86','#bd9e9a']},g,[[x-.35,-d*.43],[x+.35,-d*.43],[x+.35,d*.43],[x-.35,d*.43]],base+.2);}}
    }
    roofRecords.push({group:roof,parameters:{width:w,depth:d,eaveHeight:h,ridgeHeight:h+rise},tiers:1,thickness:.15,ridgeOrnament:false});
  });
  register('garden_topiary',(o,g)=>{
    const items=[],trunks=[],shape=o.form||'tier';for(const p of o.points||[[0,0]]){const [x,z]=p,h=p[2]??o.height??3,r=p[3]??o.radius??1.3;trunks.push({p:[x,.25,z],s:[.18,.6,.18]});
      if(shape==='cone'){const m=add(g,new THREE.ConeGeometry(r,h,16),o.color||C.leaf);m.position.set(x,h/2,z);}
      else if(shape==='column')items.push({p:[x,h/2,z],s:[r,h/2,r]});
      else if(shape==='ball')items.push({p:[x,r+.25,z],s:[r,r,r]});
      else for(let i=0;i<3;i++)items.push({p:[x,h*(.22+i*.27),z],s:[r*(1-i*.22),h*.25,r*(1-i*.22)]});
    }instances(g,cube,trunks,C.wood,'garden-topiary-stems');instances(g,sphere,items,o.color||C.leaf,'garden-topiary-crowns');
  });
  register('garden_grove',(o,g)=>{
    const trunks=[],crowns=[],under=[];for(const [i,p]of (o.points||[[0,0,12]]).entries()){const [x,z]=p,h=p[2]??o.height??12,r=p[3]??o.radius??h*.2;trunks.push({p:[x,h*.37-.02,z],s:[.2,h*.74,.2]});
      for(let j=0;j<7;j++){const a=j*2.4+i;crowns.push({p:[x+Math.cos(a)*r*.3,h*(.68+j*.045),z+Math.sin(a)*r*.3],s:[r*(1-j*.065),h*.025,r*(.8-j*.05)],r:[0,a,.04*Math.sin(j)],c:j%2?o.color||'#a3b096':'#b3bea4'});}
      if(o.understory!==false)for(let j=0;j<6;j++){const a=j*Math.PI/3;under.push({p:[x+Math.cos(a)*r*.7,.3,z+Math.sin(a)*r*.7],s:[r*.33,.4,r*.3]});}
    }instances(g,cube,trunks,o.trunkColor||'#92836d','garden-grove-trunks');instances(g,sphere,crowns,'#ffffff','garden-grove-foam');instances(g,sphere,under,C.leaf,'garden-grove-understory');
  });
  register('garden_furniture',(o,g)=>{
    const items=[],color=o.color||C.wood;for(const p of o.points||[[0,0]]){const [x,z]=p,a=rad(p[2]??0),sub=new THREE.Group();sub.position.set(x,0,z);sub.rotation.y=a;g.add(sub);
      if((o.kind||'bench')==='pot'){const r=o.radius??.7,h=o.height??.9;cylinder(sub,0,h/2-.03,0,r*.7,h,o.potColor||C.frame,r);cylinder(sub,0,h,0,r*1.06,.12,o.potColor||C.frame);planting({spacing:.35,height:.25,colors:o.colors||C.flowers},sub,boundary({size:[r*1.6,r*1.6]}),h);}
      else if(o.kind==='lamp'){const h=o.height??4.2,frame=o.frameColor||'#797d70';cylinder(sub,0,.12,0,.25,.24,frame);cylinder(sub,0,h/2,0,.055,h,frame,.045,8);cylinder(sub,0,h-.15,0,.2,.36,o.glassColor||'#e2decb',.26,8);cylinder(sub,0,h+.06,0,.4,.08,frame,.27,12);}
      else{const w=o.length??2.2;for(const s of [-1,1])block(sub,s*(w/2-.25),.22,0,.14,.5,.55,C.frame);for(const z of [-.2,0,.2])block(sub,0,.5,z,w,.09,.15,color);for(const y of [.75,.95])block(sub,0,y,-.27,w,.12,.09,color);}
    }
  });

  // Profile coordinates are local [z,y], ordered north to south. A single ruled
  // surface joins level benches to sloped earthen banks without stacked boxes.
  function elevation(x,z,t={}){
    const profile=t.profile||[[-10,0],[10,0]],w=t.width??t.size?.[0]??40;
    const q=z-(t.bend??0)*(2*x/w)**2;
    let y=profile[0][1];
    for(let i=1;i<profile.length;i++){const a=profile[i-1],b=profile[i];if(q>=b[0])y=b[1];else{if(q>a[0])y=a[1]+(b[1]-a[1])*(q-a[0])/(b[0]-a[0]);break;}}
    return y+(t.crossSlope??0)*x;
  }
  function triangles(g,vertices,color,name,walk=false){
    const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));geo.computeVertexNormals();
    const m=add(g,geo,color,name);
    if(walk){g.updateWorldMatrix(true,true);walkableGeometries.push(geo.clone().applyMatrix4(m.matrixWorld));}return m;
  }
  function quad(v,a,b,c,d){v.push(...a,...c,...b,...a,...d,...c);}
  function linework(g,points,color,name='garden-fine-lines'){
    if(!points.length)return;const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(points,3));const lines=new THREE.LineSegments(geo,new THREE.LineBasicMaterial({color}));lines.name=name;g.add(lines);
  }
  function ellipsoid(g,p,s,color,name='') {const m=add(g,sphere,color,name);m.position.set(...p);m.scale.set(...s);return m;}
  function tube(g,points,r,color,name=''){return add(g,new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points.map(p=>new THREE.Vector3(...p))),24,r,8,false),color,name);}
  function label(g,text,p,size,color){
    const canvas=document.createElement('canvas');canvas.width=1024;canvas.height=192;const ctx=canvas.getContext('2d');ctx.clearRect(0,0,1024,192);ctx.font='600 118px Georgia';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillStyle=color;ctx.fillText(text,512,100,990);
    const tex=new THREE.CanvasTexture(canvas);tex.colorSpace=THREE.SRGBColorSpace;
    const m=new THREE.Mesh(new THREE.PlaneGeometry(...size),new THREE.MeshBasicMaterial({map:tex,transparent:true,depthWrite:false}));m.name='garden-lettering';m.position.set(...p);g.add(m);
  }
  // Unit-cap outlines, with real counters after |. No font loader or canvas text.
  const letterGlyphs={
    A:[.76,'M0 0 L.27 1 L.49 1 L.76 0 L.55 0 L.49 .24 L.26 .24 L.20 0 Z|M.31 .43 L.44 .43 L.375 .73 Z'],
    B:[.72,'M0 0 L0 1 L.39 1 Q.69 1 .69 .74 Q.69 .59 .55 .52 Q.73 .46 .73 .26 Q.73 0 .41 0 Z|M.21 .60 L.37 .60 Q.48 .60 .48 .73 Q.48 .81 .37 .81 L.21 .81 Z|M.21 .19 L.39 .19 Q.52 .19 .52 .31 Q.52 .42 .39 .42 L.21 .42 Z'],
    C:[.76,'M.76 .84 Q.64 1 .40 1 Q0 1 0 .50 Q0 0 .40 0 Q.64 0 .76 .16 L.62 .32 Q.53 .20 .40 .20 Q.22 .20 .22 .50 Q.22 .80 .40 .80 Q.53 .80 .62 .68 Z'],
    D:[.76,'M0 0 L0 1 L.33 1 Q.76 1 .76 .5 Q.76 0 .33 0 Z|M.22 .20 L.33 .20 Q.54 .20 .54 .50 Q.54 .80 .33 .80 L.22 .80 Z'],
    E:[.64,'M0 0 L0 1 L.64 1 L.64 .80 L.22 .80 L.22 .61 L.57 .61 L.57 .41 L.22 .41 L.22 .20 L.64 .20 L.64 0 Z'],
    F:[.64,'M0 0 L0 1 L.64 1 L.64 .80 L.22 .80 L.22 .59 L.57 .59 L.57 .39 L.22 .39 L.22 0 Z'],
    G:[.80,'M.78 .84 Q.65 1 .41 1 Q0 1 0 .50 Q0 0 .41 0 Q.65 0 .79 .14 L.79 .55 L.41 .55 L.41 .36 L.58 .36 L.58 .25 Q.51 .20 .41 .20 Q.22 .20 .22 .50 Q.22 .80 .41 .80 Q.55 .80 .64 .68 Z'],
    H:[.76,'M0 0 L0 1 L.22 1 L.22 .62 L.54 .62 L.54 1 L.76 1 L.76 0 L.54 0 L.54 .40 L.22 .40 L.22 0 Z'],
    I:[.26,'M0 0 L0 1 L.26 1 L.26 0 Z'],
    J:[.62,'M0 .30 L.21 .33 Q.21 .20 .31 .20 Q.40 .20 .40 .35 L.40 1 L.62 1 L.62 .33 Q.62 0 .31 0 Q0 0 0 .30 Z'],
    K:[.76,'M0 0 L0 1 L.22 1 L.22 .60 L.50 1 L.76 1 L.40 .52 L.78 0 L.51 0 L.25 .37 L.22 .32 L.22 0 Z'],
    L:[.62,'M0 0 L0 1 L.22 1 L.22 .20 L.62 .20 L.62 0 Z'],
    M:[.94,'M0 0 L0 1 L.24 1 L.47 .46 L.70 1 L.94 1 L.94 0 L.72 0 L.72 .60 L.54 .18 L.40 .18 L.22 .60 L.22 0 Z'],
    N:[.78,'M0 0 L0 1 L.22 1 L.56 .38 L.56 1 L.78 1 L.78 0 L.56 0 L.22 .62 L.22 0 Z'],
    O:[.80,'M.40 0 Q0 0 0 .50 Q0 1 .40 1 Q.80 1 .80 .50 Q.80 0 .40 0 Z|M.40 .20 Q.58 .20 .58 .50 Q.58 .80 .40 .80 Q.22 .80 .22 .50 Q.22 .20 .40 .20 Z'],
    P:[.72,'M0 0 L0 1 L.38 1 Q.72 1 .72 .67 Q.72 .34 .38 .34 L.22 .34 L.22 0 Z|M.22 .54 L.36 .54 Q.50 .54 .50 .67 Q.50 .80 .36 .80 L.22 .80 Z'],
    Q:[.82,'M.40 0 Q0 0 0 .50 Q0 1 .40 1 Q.80 1 .80 .50 Q.80 .23 .67 .10 L.82 0 L.57 0 L.52 .02 Q.46 0 .40 0 Z|M.40 .20 Q.58 .20 .58 .50 Q.58 .80 .40 .80 Q.22 .80 .22 .50 Q.22 .20 .40 .20 Z'],
    R:[.76,'M0 0 L0 1 L.38 1 Q.72 1 .72 .68 Q.72 .46 .53 .38 L.77 0 L.51 0 L.30 .35 L.22 .35 L.22 0 Z|M.22 .55 L.36 .55 Q.50 .55 .50 .68 Q.50 .80 .36 .80 L.22 .80 Z'],
    S:[.72,'M.70 .84 Q.58 1 .36 1 Q.02 1 .02 .70 Q.02 .48 .34 .40 Q.51 .36 .51 .28 Q.51 .19 .36 .19 Q.20 .19 .11 .31 L0 .14 Q.14 0 .36 0 Q.72 0 .72 .29 Q.72 .53 .40 .61 Q.23 .65 .23 .73 Q.23 .81 .36 .81 Q.49 .81 .59 .70 Z'],
    T:[.74,'M.26 0 L.26 .80 L0 .80 L0 1 L.74 1 L.74 .80 L.48 .80 L.48 0 Z'],
    U:[.78,'M0 1 L.22 1 L.22 .36 Q.22 .20 .39 .20 Q.56 .20 .56 .36 L.56 1 L.78 1 L.78 .35 Q.78 0 .39 0 Q0 0 0 .35 Z'],
    V:[.78,'M0 1 L.23 1 L.39 .27 L.55 1 L.78 1 L.51 0 L.27 0 Z'],
    W:[1.04,'M0 1 L.22 1 L.34 .31 L.43 1 L.62 1 L.72 .31 L.83 1 L1.05 1 L.85 0 L.62 0 L.52 .58 L.42 0 L.20 0 Z'],
    X:[.76,'M0 0 L.25 .51 L.01 1 L.25 1 L.38 .70 L.51 1 L.75 1 L.51 .51 L.77 0 L.52 0 L.38 .32 L.24 0 Z'],
    Y:[.78,'M.28 0 L.28 .39 L0 1 L.24 1 L.39 .63 L.54 1 L.78 1 L.50 .39 L.50 0 Z'],
    Z:[.72,'M0 0 L0 .18 L.44 .80 L.02 .80 L.02 1 L.72 1 L.72 .82 L.28 .20 L.72 .20 L.72 0 Z'],
    '1':[.47,'M.03 .72 L0 .91 L.23 1 L.42 1 L.42 0 L.20 0 L.20 .75 Z'],
    '2':[.72,'M0 0 L0 .18 Q.05 .33 .31 .53 Q.51 .68 .51 .75 Q.51 .82 .37 .82 Q.22 .82 .14 .67 L0 .80 Q.12 1 .38 1 Q.72 1 .72 .75 Q.72 .54 .46 .35 L.27 .20 L.72 .20 L.72 0 Z'],
    '3':[.72,'M0 .15 L.12 .32 Q.23 .19 .37 .19 Q.51 .19 .51 .31 Q.51 .43 .29 .43 L.29 .61 Q.49 .61 .49 .72 Q.49 .81 .36 .81 Q.23 .81 .13 .70 L.02 .86 Q.15 1 .37 1 Q.71 1 .71 .74 Q.71 .59 .56 .52 Q.73 .45 .73 .28 Q.73 0 .37 0 Q.13 0 0 .15 Z'],
    '4':[.76,'M.43 0 L.43 .23 L0 .23 L0 .42 L.39 1 L.65 1 L.65 .42 L.76 .42 L.76 .23 L.65 .23 L.65 0 Z|M.43 .42 L.43 .74 L.21 .42 Z'],
    '5':[.72,'M0 .15 L.12 .32 Q.22 .19 .37 .19 Q.51 .19 .51 .34 Q.51 .49 .35 .49 Q.23 .49 .14 .43 L.03 .50 L.08 1 L.68 1 L.68 .80 L.26 .80 L.24 .66 Q.32 .69 .40 .69 Q.73 .69 .73 .34 Q.73 0 .37 0 Q.14 0 0 .15 Z'],
    '6':[.74,'M.67 .88 L.55 .72 Q.48 .81 .38 .81 Q.23 .81 .22 .59 Q.30 .65 .43 .65 Q.74 .65 .74 .33 Q.74 0 .38 0 Q0 0 0 .48 Q0 1 .38 1 Q.57 1 .67 .88 Z|M.38 .19 Q.53 .19 .53 .33 Q.53 .47 .38 .47 Q.23 .47 .23 .33 Q.23 .19 .38 .19 Z'],
    '7':[.72,'M.12 0 L.44 .80 L0 .80 L0 1 L.72 1 L.72 .84 L.36 0 Z'],
    '8':[.74,'M.37 0 Q0 0 0 .28 Q0 .45 .16 .53 Q.03 .60 .03 .75 Q.03 1 .37 1 Q.71 1 .71 .75 Q.71 .60 .58 .53 Q.74 .45 .74 .28 Q.74 0 .37 0 Z|M.37 .18 Q.52 .18 .52 .30 Q.52 .42 .37 .42 Q.22 .42 .22 .30 Q.22 .18 .37 .18 Z|M.37 .61 Q.49 .61 .49 .72 Q.49 .82 .37 .82 Q.25 .82 .25 .72 Q.25 .61 .37 .61 Z'],
    '9':[.74,'M.07 .12 L.19 .28 Q.26 .19 .36 .19 Q.51 .19 .52 .41 Q.44 .35 .31 .35 Q0 .35 0 .67 Q0 1 .36 1 Q.74 1 .74 .52 Q.74 0 .36 0 Q.17 0 .07 .12 Z|M.36 .53 Q.51 .53 .51 .67 Q.51 .81 .36 .81 Q.21 .81 .21 .67 Q.21 .53 .36 .53 Z'],
    '♥':[.96,'M.48 0 C.34 .17 0 .43 0 .71 C0 1 .32 1.12 .48 .87 C.64 1.12 .96 1 .96 .71 C.96 .43 .62 .17 .48 0 Z']
  };
  letterGlyphs['0']=letterGlyphs.O;
  const letterMarks={
    '\u0302':'M-.18 1.06 L-.055 1.24 L.055 1.24 L.18 1.06 L.07 1.06 L0 1.14 L-.07 1.06 Z',
    '\u0306':'M-.18 1.23 L-.09 1.23 Q0 1.08 .09 1.23 L.18 1.23 Q0 .94 -.18 1.23 Z',
    '\u031b':'M.25 .85 Q.46 .91 .42 1.13 L.32 1.13 Q.36 .98 .24 .97 Z',
    '\u0301':'M-.08 1.08 L.04 1.27 L.18 1.27 L.03 1.08 Z',
    '\u0300':'M.08 1.08 L-.04 1.27 L-.18 1.27 L-.03 1.08 Z',
    '\u0309':'M-.09 1.24 Q.14 1.36 .14 1.17 Q.14 1.10 .03 1.07 L-.04 1.13 Q.07 1.16 .04 1.20 Q0 1.24 -.07 1.18 Z',
    '\u0303':'M-.19 1.11 Q-.13 1.31 0 1.19 Q.08 1.10 .13 1.23 L.20 1.18 Q.13 .98 0 1.10 Q-.08 1.19 -.12 1.06 Z',
    '\u0323':'M-.055 -.09 L.055 -.09 L.055 -.20 L-.055 -.20 Z'
  };
  function letterShape(outline){
    const paths=outline.split('|').map((part,i)=>{
      const p=i?new THREE.Path():new THREE.Shape(),tokens=part.match(/[MLQCZ]|-?(?:\d*\.)?\d+/g);let j=0;
      const n=()=>Number(tokens[j++]);
      while(j<tokens.length){const op=tokens[j++];if(op==='M')p.moveTo(n(),n());else if(op==='L')p.lineTo(n(),n());else if(op==='Q')p.quadraticCurveTo(n(),n(),n(),n());else if(op==='C')p.bezierCurveTo(n(),n(),n(),n(),n(),n());else if(op==='Z')p.closePath();}
      return p;
    });paths[0].holes.push(...paths.slice(1));return paths[0];
  }
  register('garden_letters',(o,g)=>{
    const h=o.height??3,d=o.depth??.45,spacing=o.spacing??.16,colors=o.colors??['#fff4dc'],font=o.font??'rounded',plinth=o.plinth??'none',arc=o.arc??0;
    if(!Number.isFinite(h)||h<=0||!Number.isFinite(d)||d<=0||!Number.isFinite(spacing)||spacing<0||!Number.isFinite(arc)||!Number.isFinite(o.tilt??0)||!Number.isFinite(o.plinthHeight??.16)||(o.plinthHeight??.16)<=0||!Array.isArray(colors)||!colors.length)throw new RangeError('garden_letters: positive finite height/depth/plinthHeight, nonnegative spacing and nonempty colors required');
    if(!['block','rounded'].includes(font)||!['none','bar','stones'].includes(plinth))throw new RangeError('garden_letters: unknown font or plinth');
    const heights=o.letterHeights??[1];if(!Array.isArray(heights)||!heights.length||heights.some(v=>!Number.isFinite(v)||v<=0))throw new RangeError('garden_letters: letterHeights must contain positive finite multipliers');
    const text=String(o.text??'GARDEN').normalize('NFD'),chars=[];
    for(const c of text){if(/\p{M}/u.test(c)){if(chars.length&&letterMarks[c])chars.at(-1).marks.push(c);continue;}const base=c==='đ'||c==='Đ'?'D':c.toUpperCase(),glyph=letterGlyphs[base];chars.push({c,base,glyph,marks:[],scale:c!==c.toUpperCase()?.78:1,width:glyph?glyph[0]:.40});}
    const total=chars.reduce((s,c)=>s+c.width*c.scale*h,0)+Math.max(0,chars.length-1)*spacing;
    const palette=colors.map(c=>material(c)),back=o.outline?(typeof o.outline==='string'?o.outline:'#445344'):null,foot=plinth==='none'?0:(o.plinthHeight??.16),bevel=Math.min(font==='rounded'?.018:.003,d/(h*6)),cache=new Map();
    let cursor=-total/2,index=0;
    for(const ch of chars){const w=ch.width*ch.scale*h,offset=cursor+w/2;cursor+=w+spacing;if(!ch.glyph)continue;
      const a=arc?offset/arc:0,x=arc?Math.sin(a)*arc:offset,z=arc?(1-Math.cos(a))*arc:0,y=elevation(x,z,o.terrain||{}),lean=rad((o.tilt??0)*(hash(index+17)*2-1)),scale=ch.scale*h;
      const transform=new THREE.Object3D();transform.position.set(x,y+foot,z);transform.rotation.set(0,-a,lean);transform.updateMatrix();
      const shapes=[{path:ch.glyph[1],x:-ch.width/2,y:0}];
      if(ch.c==='Đ'||ch.c==='đ')shapes.push({path:'M-.06 .44 L.34 .44 L.34 .57 L-.06 .57 Z',x:-ch.width/2,y:0});
      const stacked=ch.marks.includes('\u0302')||ch.marks.includes('\u0306');
      for(const mark of ch.marks)shapes.push({path:letterMarks[mark],x:0,y:stacked&&['\u0301','\u0300','\u0309','\u0303'].includes(mark)?.23:0});
      const vertical=heights[index%heights.length];
      const parts=shapes.map(s=>{const key=s.path+'|'+scale+'|'+vertical;let geo=cache.get(key);if(!geo){geo=new THREE.ExtrudeGeometry(letterShape(s.path),{depth:d,steps:1,curveSegments:10,bevelEnabled:true,bevelSize:bevel,bevelThickness:Math.min(d*.16,scale*bevel),bevelSegments:font==='rounded'?3:1});geo.scale(scale,scale*vertical/(1+2*bevel),1);cache.set(key,geo);}return geo.clone().translate(s.x*scale,s.y*scale*vertical,-d/2);});
      const geo=mergeGeometries(parts);parts.forEach(p=>p.dispose());
      geo.applyMatrix4(new THREE.Matrix4().makeRotationZ(lean));geo.computeBoundingBox();const lift=-geo.boundingBox.min.y;geo.translate(0,lift,0);geo.applyMatrix4(new THREE.Matrix4().makeRotationZ(-lean));
      const letter=add(g,geo,colors[index%colors.length],'garden-letter-'+index);letter.material=palette[index%palette.length];letter.applyMatrix4(transform.matrix);
      letter.userData.character=ch.c;g.updateWorldMatrix(true,true);
      // Each letter contributes framing even after same-colour meshes are merged.
      geo.computeBoundingBox();const bounds=geo.boundingBox;for(const X of [bounds.min.x,bounds.max.x])for(const Y of [bounds.min.y,bounds.max.y])for(const Z of [bounds.min.z,bounds.max.z])if(currentEnvelope)currentEnvelope.push(new THREE.Vector3(X,Y,Z).applyMatrix4(letter.matrixWorld));
      if(back){const outline=geo.clone();outline.scale(1.045,1.025,Math.min(1,h*.035/d));outline.translate(0,0,-d/2-h*.025);const m=add(g,outline,back,'garden-letter-outline');m.applyMatrix4(transform.matrix);}
      if(plinth==='stones'){const pad=block(g,x,y+foot/2,z,w*.92,foot,d+h*.12,o.plinthColor||'#a79c83','garden-letter-foot');pad.rotation.y=-a;}
      index++;
    }
    if(plinth==='bar'&&index){const n=Math.max(1,Math.ceil(total/Math.min(h,2))),step=total/n;
      for(let i=0;i<n;i++){const offset=-total/2+(i+.5)*step,a=arc?offset/arc:0,x=arc?Math.sin(a)*arc:offset,z=arc?(1-Math.cos(a))*arc:0,y=elevation(x,z,o.terrain||{}),pad=block(g,x,y+foot/2,z,step+.025,foot,d+h*.12,o.plinthColor||'#a79c83','garden-letter-bar');pad.rotation.y=-a;}
    }
    cache.forEach(geo=>geo.dispose());g.userData.letterCount=index;
    if(index&&currentEnvelope){g.updateWorldMatrix(true,true);const bounds=new THREE.Box3().setFromObject(g);for(const x of [bounds.min.x,bounds.max.x])for(const y of [bounds.min.y,bounds.max.y])for(const z of [bounds.min.z,bounds.max.z])currentEnvelope.push(new THREE.Vector3(x,y,z));}
  });
  register('garden_terrain',(o,g)=>{
    const [w,d]=o.size||[40,30],t={...o,width:w},profile=o.profile||[[-d/2,3],[-d*.25,3],[-d*.1,0],[d/2,0]],segments=o.segments??40;
    if(w<=0||segments<1||profile.length<2||profile.some((p,i)=>!p.every(Number.isFinite)||i&&p[0]<=profile[i-1][0]))throw new RangeError('garden_terrain: positive width/segments and increasing finite profile z required');
    const cap=[],banks=[],sides=[],bottom=o.bottom??-.1;
    for(let j=1;j<profile.length;j++)for(let i=0;i<segments;i++){
      const x0=-w/2+w*i/segments,x1=-w/2+w*(i+1)/segments,a=profile[j-1],b=profile[j];
      const p=(x,k)=>[x,k[1]+(o.crossSlope??0)*x,k[0]+(o.bend??0)*(2*x/w)**2];
      quad(Math.abs(b[1]-a[1])>.08?banks:cap,p(x0,a),p(x1,a),p(x1,b),p(x0,b));
      if(j===1||j===profile.length-1){const k=j===1?a:b,A=p(x0,k),B=p(x1,k);quad(sides,[A[0],bottom,A[2]],[B[0],bottom,B[2]],B,A);}
      if(i===0||i===segments-1){const x=i===0?x0:x1,A=p(x,a),B=p(x,b);quad(sides,[x,bottom,A[2]],[x,bottom,B[2]],B,A);}
    }
    // End walls are double-sided; their winding depends on the perimeter side.
    for(const [v,c,n]of [[cap,o.color||C.lawn,'garden-terrain-cap'],[banks,o.bankColor||'#b49a82','garden-earth-banks'],[sides,o.bankColor||'#b49a82','garden-terrain-sides']])if(v.length){const m=triangles(g,v,c,n,!!o.walkable);m.material=material(c).clone();m.material.side=THREE.DoubleSide;}
    const lines=[];for(const p of profile)for(let i=0;i<segments;i++){const x0=-w/2+w*i/segments,x1=x0+w/segments;lines.push(x0,p[1]+.012+(o.crossSlope??0)*x0,p[0]+(o.bend??0)*(2*x0/w)**2,x1,p[1]+.012+(o.crossSlope??0)*x1,p[0]+(o.bend??0)*(2*x1/w)**2);}
    if(o.contourLines!==false)linework(g,lines,o.lineColor||'#ad947e','garden-bank-contours');
  });
  // Small crop parts retain a rounded silhouette without microscopic tessellation.
  const cropHead=new THREE.SphereGeometry(1,6,3),cropLeaf=new THREE.OctahedronGeometry(1,0),cropCentre=new THREE.OctahedronGeometry(1,0),sunCentre=new THREE.CircleGeometry(1,10),sunPetal=new THREE.CircleGeometry(1,4);
  const floretVertices=[];for(let i=0;i<4;i++){const a=i*Math.PI/2;floretVertices.push(0,.04,0,Math.cos(a+.38)*.48,0,Math.sin(a+.38)*.48,Math.cos(a-.38)*.48,0,Math.sin(a-.38)*.48);}
  const cropFloret=new THREE.BufferGeometry();cropFloret.setAttribute('position',new THREE.Float32BufferAttribute(floretVertices,3));cropFloret.computeVertexNormals();
  register('garden_field',(o,g)=>{
    const poly=boundary({...o,shape:o.shape||'rectangle'}),species=o.species||'hydrangea',spacing=o.spacing??1.05,row=o.rowSpacing??spacing*1.12,h=o.height??(species==='sunflower'?1.65:species==='cosmos'?.8:1.05),t=o.terrain||{},colors=o.colors||(species==='sunflower'?['#cbb47e']:species==='cosmos'?['#b992a4','#d6bdc7']:['#aebdcd','#dbdcd1','#b4b4cc']),seed=o.seed??1;
    if(spacing<=0||row<=0)throw new RangeError('garden_field: spacing and rowSpacing must be positive');
    const xs=poly.map(p=>p[0]),zs=poly.map(p=>p[1]),x0=Math.min(...xs),x1=Math.max(...xs),z0=Math.min(...zs),z1=Math.max(...zs),substrate=[];
    // Triangulate then subdivide the substrate so it follows the same bank
    // sampling as every plant. Discard triangles outside authored exclusions.
    const pitch=o.soilResolution??1.5;
    if(pitch<=0)throw new RangeError('garden_field: soilResolution must be positive');
    g.updateWorldMatrix(true,true);const inverse=g.matrixWorld.clone().invert();
    const lanes=o.clearRoute?(place.route||[]).map(leg=>leg.map(p=>new THREE.Vector3(p[0],0,p[1]).applyMatrix4(inverse))):[];
    const inLane=(x,z)=>lanes.some(leg=>leg.some((b,i)=>{if(!i)return false;const a=leg[i-1],dx=b.x-a.x,dz=b.z-a.z,length=dx*dx+dz*dz,t=length?Math.max(0,Math.min(1,((x-a.x)*dx+(z-a.z)*dz)/length)):0;return Math.hypot(x-a.x-dx*t,z-a.z-dz*t)<(o.routeMargin??1.8)+spacing*.4;}));
    const open=(x,z)=>inside(x,z,poly)&&!(o.exclude||[]).some(p=>inside(x,z,p))&&!inLane(x,z);
    for(let x=x0;x<x1;x+=pitch)for(let z=z0;z<z1;z+=pitch){const b=Math.min(x+pitch,x1),d=Math.min(z+pitch,z1),corners=[[x,z],[b,z],[b,d],[x,d],[(x+b)/2,(z+d)/2]];
      if(corners.every(p=>open(...p))&&!(o.exclude||[]).some(poly=>poly.some(p=>p[0]>=x&&p[0]<=b&&p[1]>=z&&p[1]<=d)))terrainQuad(substrate,[x,elevation(x,z,t)+.035,z],[b,elevation(b,z,t)+.035,z],[b,elevation(b,d,t)+.035,d],[x,elevation(x,d,t)+.035,d],t,.035);
    }
    if(substrate.length)triangles(g,substrate,o.soilColor||'#a4ae91','garden-field-soil');
    const leaves=[],heads=[],petals=[],centres=[],stems=[];let i=0;
    for(let z=z0+row*.45;z<z1;z+=row)for(let x=x0+spacing*.45;x<x1;x+=spacing){i++;const jitter=o.jitter??.18,px=x+(hash(i+seed)-.5)*spacing*jitter,pz=z+(hash(i*3+seed)-.5)*row*jitter;
      if(!inside(px,pz,poly)||(o.exclude||[]).some(p=>inside(px,pz,p))||inLane(px,pz))continue;
      const y=elevation(px,pz,t)+.04,scale=.88+hash(i*7+seed)*.24,hh=h*scale,band=Math.floor((pz-z0)/(z1-z0)*(o.bands??7)),color=colors[((band%colors.length)+colors.length)%colors.length];
      if(species==='hydrangea'){
        leaves.push({p:[px,y+hh*.37,pz],s:[spacing*.63,hh*.42,row*.57],c:o.leafColor||'#8d9d7e'});
        for(let k=0;k<(o.headsPerPlant??3);k++){const a=k*2.4+hash(i)*2,r=spacing*.27,cx=px+Math.cos(a)*r,cz=pz+Math.sin(a)*r,cy=y+hh*(.82+hash(i+k)*.16),rhead=spacing*(o.headRadius??.31);heads.push({p:[cx,cy,cz],s:[rhead,rhead*.73,rhead],c:color});
          const count=o.floretsPerHead??3;for(let j=0;j<count;j++){const b=j*2.4,rj=rhead*Math.sqrt(j/Math.max(1,count));petals.push({p:[cx+Math.cos(b)*rj,cy+rhead*.66*Math.sqrt(1-j/(count+2)),cz+Math.sin(b)*rj],s:[rhead*.67,.27,rhead*.67],r:[0,b,0],c:color});}}
      }else{
        stems.push({p:[px,y+hh*.48,pz],s:[.026,hh,.026]});
        const count=o.leavesPerPlant??3;for(let k=0;k<count;k++)leaves.push({p:[px+(k%2?-.12:.12),y+hh*(.22+k*.38/Math.max(1,count-1)),pz],s:[spacing*.3,.06,spacing*.14],r:[0,k*2.4,.25],c:o.leafColor||'#8e9b78'});
        if(species==='sunflower'){
          const r=spacing*(o.headRadius??.24);centres.push({p:[px,y+hh,pz+.025],s:[r*.57,r*.57,.055]});
          for(let k=0;k<11;k++){const a=k*Math.PI*2/11;heads.push({p:[px+Math.cos(a)*r*.65,y+hh+Math.sin(a)*r*.65,pz],s:[r*.48,r*.26,.045],r:[0,0,a],c:color});}
        }else{const diameter=spacing*(o.headRadius??.3)*2;petals.push({p:[px,y+hh,pz],s:[diameter,1,diameter],r:[.15,hash(i)*6,.1],c:color});centres.push({p:[px,y+hh+.045,pz],s:[.045,.025,.045]});}
      }
    }
    const headGeometry=o.headSegments?new THREE.SphereGeometry(1,...o.headSegments):cropHead;
    if(o.leafScale)for(const item of leaves)item.s=item.s.map((v,i)=>v*o.leafScale[i]);
    instances(g,species==='hydrangea'?leaf:cropLeaf,leaves,'#ffffff','garden-crop-leaves');instances(g,species==='sunflower'?sunPetal:headGeometry,heads,'#ffffff','garden-crop-heads');instances(g,species==='hydrangea'?cropFloret:bloom,petals,'#ffffff','garden-crop-florets');instances(g,species==='sunflower'?sunCentre:cropCentre,centres,species==='sunflower'?'#756e50':'#c6b582','garden-crop-centres');instances(g,cube,stems,o.leafColor||'#8e9b78','garden-crop-stems');
    for(const m of g.children)if(m.name.startsWith('garden-crop-'))m.castShadow=!!o.castShadow&&!['garden-crop-florets','garden-crop-stems'].includes(m.name);
    if(species==='sunflower')for(const name of ['garden-crop-heads','garden-crop-centres']){
      const m=g.getObjectByName(name);if(m){m.material=m.material.clone();m.material.side=THREE.DoubleSide;}
    }
  });
  function terrainQuad(vertices,a,b,c,d,t,offset){
    const width=t.width??t.size?.[0]??40,bend=t.bend??0,profile=t.profile||[],q=p=>p[2]-bend*(2*p[0]/width)**2;
    const breakError=(a,b)=>{
      let error=0;const qa=q(a),qb=q(b);
      for(const [z] of profile)if(z>Math.min(qa,qb)+1e-8&&z<Math.max(qa,qb)-1e-8){
        // Explicit profile samples catch banks narrower than midpoint spacing.
        const f=(z-qa)/(qb-qa),x=a[0]+(b[0]-a[0])*f,zz=a[2]+(b[2]-a[2])*f;
        error=Math.max(error,Math.abs(elevation(x,zz,t)+offset-(a[1]+(b[1]-a[1])*f)));
      }
      return error;
    };
    const split=(a,b,c,depth=0)=>{
      const mid=(p,q)=>{const x=(p[0]+q[0])/2,z=(p[2]+q[2])/2;return [x,elevation(x,z,t)+offset,z];};
      const ab=mid(a,b),bc=mid(b,c),ca=mid(c,a),x=(a[0]+b[0]+c[0])/3,z=(a[2]+b[2]+c[2])/3;
      const error=Math.max(Math.abs(ab[1]-(a[1]+b[1])/2),Math.abs(bc[1]-(b[1]+c[1])/2),Math.abs(ca[1]-(c[1]+a[1])/2),Math.abs(elevation(x,z,t)+offset-(a[1]+b[1]+c[1])/3),breakError(a,b),breakError(b,c),breakError(c,a));
      if(error>.006&&depth<10){split(a,ab,ca,depth+1);split(ab,b,bc,depth+1);split(ca,bc,c,depth+1);split(ab,bc,ca,depth+1);}else{
        // Float32 T-junctions need a microscopic overlap for reliable route rays.
        for(const p of [a,b,c]){const dx=p[0]-x,dz=p[2]-z,f=.00001/Math.max(.001,Math.hypot(dx,dz));vertices.push(p[0]+dx*f,p[1],p[2]+dz*f);}
      }
    };
    split(a,c,b);split(a,d,c);
  }
  function landscapePath(o,g){
    const width=o.width??3.4,top=o.level??.075,t=o.terrain||{},paving=[],kerbs=[],joints=[],kw=o.kerbWidth??0,kh=o.kerbHeight??.18;
    const legs=o.followRoute?place.route:o.legs||[o.shape?boundary(o):o.points||[[0,0],[0,-12]]];
    for(const original of legs){const points=original.filter((p,i)=>!i||Math.hypot(p[0]-original[i-1][0],p[1]-original[i-1][1])>1e-6).map(p=>p.slice());if(points.length<2)continue;
      if(o.closed&&Math.hypot(points[0][0]-points.at(-1)[0],points[0][1]-points.at(-1)[1])<1e-6)points.pop();
      const normal=(a,b)=>{const dx=b[0]-a[0],dz=b[1]-a[1],l=Math.hypot(dx,dz)||1;return [-dz/l,dx/l];};
      const offsets=points.map((p,i)=>{const prev=i?points[i-1]:o.closed?points.at(-1):null,next=i<points.length-1?points[i+1]:o.closed?points[0]:null,A=prev?normal(prev,p):normal(p,next),B=next?normal(p,next):A,den=1+A[0]*B[0]+A[1]*B[1];return den>.08?[(A[0]+B[0])/den,(A[1]+B[1])/den]:B;});
      const count=o.closed?points.length:points.length-1;
      for(let i=0;i<count;i++){
      const next=(i+1)%points.length,a=points[i],b=points[next],dx=b[0]-a[0],dz=b[1]-a[1],len=Math.hypot(dx,dz);if(len<.001)continue;const n=Math.ceil(len/(o.jointSpacing??1.5));
      const p=(f,offset,dy=0)=>{const nx=offsets[i][0]*(1-f)+offsets[next][0]*f,nz=offsets[i][1]*(1-f)+offsets[next][1]*f,x=a[0]+dx*f+nx*offset,z=a[1]+dz*f+nz*offset;return [x,elevation(x,z,t)+top+dy,z];};
      for(let k=0;k<n;k++){const f=k/n,v=(k+1)/n;terrainQuad(paving,p(f,-width/2),p(v,-width/2),p(v,width/2),p(f,width/2),t,top);
        for(const side of [-1,1])if(kw){const u=side*width/2,outer=u+side*kw;terrainQuad(kerbs,p(f,u,kh),p(v,u,kh),p(v,outer,kh),p(f,outer,kh),t,top+kh);quad(kerbs,p(f,u,-.02),p(v,u,-.02),p(v,u,kh),p(f,u,kh));quad(kerbs,p(f,outer,kh),p(v,outer,kh),p(v,outer,-kh),p(f,outer,-kh));}
        if(k)joints.push(...p(f,-width/2,.007),...p(f,width/2,.007));
        for(let j=1;j<(o.tileRows??1);j++){const offset=-width/2+width*j/o.tileRows;joints.push(...p(f,offset,.008),...p(v,offset,.008));}
      }
    }}
    triangles(g,paving,o.color||C.paving,'garden-kerbed-paving',true);if(kerbs.length){const m=triangles(g,kerbs,o.kerbColor||'#b8b8a7','garden-stone-kerbs');m.material=material(o.kerbColor||'#b8b8a7').clone();m.material.side=THREE.DoubleSide;}linework(g,joints,o.jointColor||C.joint,'garden-paving-grid');
  }
  function stoneHand(g,o={}){
    const sub=new THREE.Group();sub.name='garden-hand';sub.position.set(...(o.position||[0,0,0]));sub.rotation.y=rad(o.rotation??0);g.add(sub);
    const h=o.height??7,w=o.width??h*.72,c=o.color||'#c0c1b3',vein=o.lineColor||'#969d8d';
    // Wrist, heel and palm form one overlapping carved mass; fingers curl
    // toward +z, so the deck can pass through the open cradle.
    ellipsoid(sub,[0,h*.22,0],[w*.27,h*.26,w*.23],c);
    ellipsoid(sub,[0,h*.49,0],[w*.47,h*.27,w*.2],c);
    for(let k=0;k<4;k++){const x=(-1.5+k)*w*.22,length=[.31,.39,.37,.29][k]*h,start=h*.57,tip=start+length;
      tube(sub,[[x,start,.01],[x*1.08,start+length*.46,-w*.08],[x*1.03,tip,-w*.04],[x*.98,tip-.055,w*.2]],w*(k===3?.066:.075),c,'garden-hand-finger');
      for(let j=0;j<2;j++){const y=start+length*(.5+j*.23);tube(sub,[[x-w*.045,y,w*.011],[x,y-.018,w*.025],[x+w*.045,y,w*.011]],.012,vein);}}
    tube(sub,[[-w*.34,h*.34,w*.08],[-w*.58,h*.5,w*.14],[-w*.56,h*.64,w*.28],[-w*.38,h*.68,w*.34]],w*.105,c,'garden-hand-thumb');
    tube(sub,[[-w*.24,h*.37,w*.183],[0,h*.44,w*.205],[w*.28,h*.4,w*.16]],.015,vein);
    return sub;
  }
  register('garden_bridge',(o,g)=>{
    if(o.style==='glass'){glassBridge(o,g);return;}
    const pts=o.points||[[-18,3],[-7,-2],[7,-2],[18,3]],h=o.deckHeight??4.5,w=o.width??3,th=o.thickness??.32,rh=o.railHeight??1.05,curve=new THREE.CatmullRomCurve3(pts.map(p=>new THREE.Vector3(p[0],h,p[1]))),n=o.segments??100,deck=[],rails=[[],[]],posts=[],joints=[],gold=o.color||'#c6b17d';
    const point=(t,offset,dy=0)=>{const p=curve.getPoint(t),v=curve.getTangent(t),normal=new THREE.Vector3(-v.z,0,v.x).normalize();p.addScaledVector(normal,offset);p.y+=Math.sin(t*Math.PI)*(o.rise??.35)+dy;return p.toArray();};
    for(let i=0;i<n;i++){const a=i/n,b=(i+1)/n;quad(deck,point(a,-w/2),point(b,-w/2),point(b,w/2),point(a,w/2));quad(deck,point(a,w/2,-th),point(b,w/2,-th),point(b,-w/2,-th),point(a,-w/2,-th));for(const s of [-1,1])quad(deck,point(a,s*w/2,-th),point(b,s*w/2,-th),point(b,s*w/2),point(a,s*w/2));}
    const m=triangles(g,deck,gold,'garden-curved-deck',true);m.material=material(gold).clone();m.material.side=THREE.DoubleSide;
    const count=Math.ceil(curve.getLength()/(o.balusterSpacing??.85));
    for(let j=0;j<2;j++){const s=j?1:-1;for(let i=0;i<=n;i++)rails[j].push(point(i/n,s*w/2,rh));tube(g,rails[j],.055,o.railColor||gold,'garden-bridge-handrail');tube(g,rails[j].map(p=>[p[0],p[1]-rh+.18,p[2]]),.035,gold);
      for(let i=0;i<=count;i++){const t=i/count,p=point(t,s*w/2,rh/2);posts.push({p,s:[.038,rh,.038]});if(i<count&&o.lattice!==false){rod(g,point(t,s*w/2,.2),point((i+1)/count,s*w/2,rh-.1),.017,gold);rod(g,point(t,s*w/2,rh-.1),point((i+1)/count,s*w/2,.2),.017,gold);}}}
    instances(g,cube,posts,gold,'garden-bridge-balusters');for(let i=1;i<count;i++)joints.push(...point(i/count,-w/2,.006),...point(i/count,w/2,.006));linework(g,joints,o.jointColor||'#b09c6d');
    for(const hand of o.hands||[])stoneHand(g,hand);
  });
  register('garden_stairs',(o,g)=>{
    const n=o.steps??16,r=o.rise??.28,t=o.tread??.6,w=o.width??3.6,taper=o.taper??0,sky=(o.kind||'ground')==='sky',th=o.thickness??.14,c=o.color||'#e4e0d4',lines=[];
    for(let i=0;i<n;i++){const width=w*(1-taper*i/Math.max(1,n-1)),y=(i+1)*r,z=-i*t;block(g,0,y-(sky?th:y)/2,z,width,sky?th:y,t+.015,c);const poly=[[-width/2,z-t/2],[width/2,z-t/2],[width/2,z+t/2],[-width/2,z+t/2]];if(o.walkable!==false)slab(g,poly,y-.015,y,c,true);lines.push(-width/2,y+.005,z+t/2,width/2,y+.005,z+t/2);}
    if(sky)for(const s of [-1,1])rod(g,[s*w*.27,.05,t*.25],[s*w*(1-taper)*.27,n*r-th,-(n-1)*t],o.stringerRadius??.09,o.frameColor||c);
    if(o.landing){const last=w*(1-taper),depth=o.landing;slab(g,[[-last/2,-n*t-depth],[last/2,-n*t-depth],[last/2,-n*t+.3],[-last/2,-n*t+.3]],n*r-.16,n*r,c,o.walkable!==false);}
    linework(g,lines,o.jointColor||'#c4c1b4','garden-stair-nosings');
  });
  register('garden_platform',(o,g)=>{
    const h=o.height??7,[w,d]=o.size||[5,4],c=o.color||'#a86f62',r=o.poleRadius??.25,rh=o.railHeight??1.05;
    cylinder(g,0,h/2,0,r,h,c,r*.85,12);block(g,0,h,0,w,.2,d,c);
    for(const x of [-w*.4,w*.4])for(const z of [-d*.4,d*.4])rod(g,[0,h-1.7,0],[x,h-.1,z],.045,c);
    const poly=[[-w/2,-d/2],[w/2,-d/2],[w/2,d/2],[-w/2,d/2]];slab(g,poly,h-.1,h+.1,c,true);
    for(let i=0;i<4;i++){const a=poly[i],b=poly[(i+1)%4],count=Math.ceil(Math.hypot(a[0]-b[0],a[1]-b[1])/.55);for(const dy of [.45,rh])rod(g,[a[0],h+dy,a[1]],[b[0],h+dy,b[1]],.04,c);for(let j=0;j<=count;j++){const t=j/count,x=a[0]+(b[0]-a[0])*t,z=a[1]+(b[1]-a[1])*t;rod(g,[x,h,z],[x,h+rh,z],.025,c);}}
  });
  register('garden_swing',(o,g)=>{
    const w=o.width??5.4,h=o.height??4.3,c=o.color||'#8a7762',post=o.postRadius??.15,seat=o.seatHeight??.55,len=o.seatWidth??w*.67;
    for(const s of [-1,1])cylinder(g,s*w/2,h/2,0,post,h,c,post*.8,10);
    rod(g,[-w/2-.4,h-.2,0],[w/2+.4,h-.2,0],post,c);
    for(const s of [-1,1])for(const z of [-.22,.22])rod(g,[s*len*.43,h-.25,0],[s*len*.43,seat,z],.018,o.ropeColor||'#b9ae94');
    for(const z of [-.23,0,.23])block(g,0,seat,z,len,.09,.18,c);
    if(o.back!==false)for(const y of [.25,.48])block(g,0,seat+y,-.3,len,.12,.08,c);
    if(o.sign){block(g,0,h-.7,.04,w*.8,.4,.08,c);label(g,o.sign,[0,h-.7,.09],[w*.76,.3],o.signColor||'#e3dcc7');}
  });
  register('garden_sculpture',(o,g)=>{
    if(['liberty','bust','clay'].includes(o.kind)){figurative(o,g);return;}
    const kind=o.kind||'relief',c=o.color||'#c7bfa6',[w,h,d]=o.size||[6,4,1.5],base=o.plinthHeight??.7;
    if(kind==='hand'){stoneHand(g,{...o,position:[0,0,0],rotation:0});return;}
    block(g,0,base/2,0,w*(o.plinthScale??1.04),base,d*1.12,o.plinthColor||'#636d66','garden-dark-plinth');
    if(kind==='plinth')return;
    if(kind==='statue'){
      ellipsoid(g,[0,base+h*.78,0],[w*.17,h*.13,d*.22],c);ellipsoid(g,[0,base+h*.47,0],[w*.3,h*.23,d*.23],c);
      for(const s of [-1,1]){rod(g,[s*w*.09,base,0],[s*w*.12,base+h*.42,0],w*.085,c);rod(g,[s*w*.22,base+h*.62,0],[s*w*.3,base+h*.29,0],w*.065,c);}return;
    }
    const shape=new THREE.Shape();shape.moveTo(-w*.5,base);shape.lineTo(w*.48,base);shape.lineTo(w*.5,base+h*.91);shape.lineTo(w*.1,base+h);shape.lineTo(-w*.4,base+h*.98);shape.lineTo(-w*.53,base+h*.63);shape.closePath();
    const geo=new THREE.ExtrudeGeometry(shape,{depth:d,bevelEnabled:true,bevelThickness:.07,bevelSize:.07,bevelSegments:1});geo.translate(0,0,-d/2);add(g,geo,c,'garden-carved-stone');
    const front=d/2,cy=base+h*.6,fw=w*(o.faceWidth??.25),fh=h*.34,depth=o.reliefDepth??.64,dark=o.shadowColor||'#9a9784',light=o.highlightColor||'#d3cbb4';
    ellipsoid(g,[0,cy,front],[fw,fh,depth],c,'garden-relief-head');
    // Bald forehead, inset eye sockets, angular brows, hooked nose, forked
    // moustache and pointed beard read as carved relief, never painted eyes.
    ellipsoid(g,[0,cy+fh*.56,front+depth*.56],[fw*.78,fh*.55,depth*.42],light);
    for(const s of [-1,1]){
      ellipsoid(g,[s*fw*.89,cy-.05,front+depth*.18],[fw*.13,fh*.27,depth*.27],c);
      ellipsoid(g,[s*fw*.4,cy+fh*.17,front+depth*.86],[fw*.23,fh*.065,.035],dark);
      tube(g,[[s*fw*.12,cy+fh*.26,front+depth*.9],[s*fw*.4,cy+fh*.3,front+depth],[s*fw*.7,cy+fh*.2,front+depth*.76]],.065,light);
      ellipsoid(g,[s*fw*.48,cy-fh*.24,front+depth*.6],[fw*.3,fh*.3,depth*.32],c);
      tube(g,[[s*fw*.06,cy-fh*.24,front+depth*1.12],[s*fw*.32,cy-fh*.35,front+depth*1.07],[s*fw*.61,cy-fh*.42,front+depth*.85]],fw*.12,light);
      tube(g,[[s*fw*.7,cy-fh*.1,front+depth*.77],[s*fw*.64,cy-fh*.65,front+depth*.74],[s*fw*.17,cy-fh*1.03,front+depth*.57]],fw*.09,light);
    }
    const nose=[];const A=[-fw*.08,cy+fh*.25,front+depth*.87],B=[fw*.08,cy+fh*.25,front+depth*.87],L=[-fw*.16,cy-fh*.23,front+depth*.88],R=[fw*.16,cy-fh*.23,front+depth*.88],T=[0,cy-fh*.16,front+depth*1.27];nose.push(...A,...L,...T,...A,...T,...B,...B,...T,...R,...L,...R,...T);triangles(g,nose,light,'garden-relief-nose');
    ellipsoid(g,[0,cy-fh*.54,front+depth*.86],[fw*.4,fh*.06,depth*.09],dark);
    const beardShape=new THREE.Shape();beardShape.moveTo(-fw*.62,cy-fh*.44);beardShape.lineTo(-fw*.58,cy-fh*.89);beardShape.lineTo(-fw*.23,cy-fh*1.22);beardShape.lineTo(fw*.23,cy-fh*1.22);beardShape.lineTo(fw*.58,cy-fh*.89);beardShape.lineTo(fw*.62,cy-fh*.44);beardShape.closePath();
    const beard=new THREE.ExtrudeGeometry(beardShape,{depth:depth*.3,bevelEnabled:true,bevelThickness:depth*.18,bevelSize:.08,bevelSegments:1});beard.translate(0,0,front+depth*.5);add(g,beard,light,'garden-relief-beard');
    const drapes=[];for(const s of [-1,1])for(let k=0;k<4;k++)tube(g,[[s*fw*(.65+k*.19),base+h*.91,front+.02],[s*fw*(.95+k*.2),base+h*.68,front+.1],[s*fw*(1.1+k*.18),base+h*.12,front+.04]],.025,o.lineColor||'#afa78f');
    for(let k=0;k<9;k++){const x=(k-4)*fw*.105;drapes.push(x,cy-fh*.62,front+depth*1.015,x*.5,cy-fh*1.12,front+depth*1.015);}linework(g,drapes,dark,'garden-carving-chisel-lines');
  });
  register('garden_conifer',(o,g)=>{
    if(o.form==='cloud'){cloudPines(o,g);return;}
    const form=o.form||'pine',h=o.height??9,r=o.radius??1.7,c=o.color||'#8c9e85',trunks=[],crowns=[],cone=new THREE.ConeGeometry(1,1,20),lobes=[];
    for(const [i,p]of (o.points||[[0,0]]).entries()){
      const [x,z]=p,H=p[2]??h,R=p[3]??r,y=p[4]??0;trunks.push({p:[x,y+H*.23,z],s:[.17,H*.46,.17]});
      if(form==='wall'){crowns.push({p:[x,y+H*.48,z],s:[R,H*.5,R*.72],c});continue;}
      const tiers=form==='cypress'?8:6;for(let j=0;j<tiers;j++){const f=j/(tiers-1),radius=R*(1-f*.89);crowns.push({p:[x,y+H*(.29+f*.6),z],s:[radius,H*(form==='cypress'?.35:.32),radius],r:[0,i*.7,0],c:j%2?c:o.tipColor||'#9eac92'});if(o.texture!==false)for(let k=0;k<5;k++){const a=k*Math.PI*2/5+j;lobes.push({p:[x+Math.cos(a)*radius*.42,y+H*(.25+f*.6),z+Math.sin(a)*radius*.42],s:[radius*.24,H*.022,radius*.23],c:c});}}
    }
    instances(g,cube,trunks,o.trunkColor||'#8b826e','garden-conifer-trunks');instances(g,form==='wall'?sphere:cone,crowns,'#ffffff','garden-conifer-crowns');instances(g,sphere,lobes,'#ffffff','garden-conifer-texture');
  });
  register('garden_shelter',(o,g)=>{
    const [w,d,h]=o.size||[10,24,3],rise=o.roofRise??2,kind=o.kind||'greenhouse',roofKind=o.roof||'arched',bays=o.bays??Math.ceil(d/3),c=o.frameColor||'#9aa69b',glass=o.glassColor||'#c9cec2',th=o.frameRadius??.035;
    slab(g,boundary({size:[w,d],shape:'rectangle'}),-.05,.09,o.baseColor||C.paving,kind==='shed');
    const roof=new THREE.Group();roof.name='garden-shelter-roof';g.add(roof);const roofV=[],walls=[],frames=[],posts=[];
    const section=roofKind==='arched'?Array.from({length:17},(_,i)=>[-w/2+w*i/16,h+rise*Math.sin(i*Math.PI/16)]):roofKind==='sawtooth'?[[-w/2,h],[-w*.08,h+rise],[-w*.08,h],[w*.36,h+rise],[w/2,h]]:[[-w/2,h],[0,h+rise],[w/2,h]];
    for(let k=1;k<section.length;k++){const a=section[k-1],b=section[k];quad(roofV,[a[0],a[1],-d/2],[b[0],b[1],-d/2],[b[0],b[1],d/2],[a[0],a[1],d/2]);rod(roof,[a[0],a[1],-d/2],[a[0],a[1],d/2],th,c);}
    const shell=triangles(roof,roofV,glass,'garden-plastic-roof');shell.material=material(glass).clone();shell.material.side=THREE.DoubleSide;shell.material.transparent=(o.opacity??.8)<1;shell.material.opacity=o.opacity??.8;shell.material.depthWrite=true;
    for(let i=0;i<=bays;i++){const z=-d/2+d*i/bays;for(const s of [-1,1])posts.push({p:[s*w/2,h/2,z],s:[th*2,h,th*2]});for(let j=1;j<section.length;j++)rod(roof,[...section[j-1],z],[...section[j],z],th,c);
      if(kind==='shed')rod(roof,[-w/2,h,z],[w/2,h,z],th,c);
    }
    instances(g,cube,posts,c,'garden-shelter-posts');
    for(const s of [-1,1]){quad(walls,[s*w/2,0,-d/2],[s*w/2,h,-d/2],[s*w/2,h,d/2],[s*w/2,0,d/2]);rod(g,[s*w/2,h*.53,-d/2],[s*w/2,h*.53,d/2],th,c);}
    if(kind==='shed'){
      const gables=[];for(const s of [-1,1])for(let j=1;j<section.length;j++)quad(gables,[section[j-1][0],h,s*d/2],[section[j][0],h,s*d/2],[section[j][0],section[j][1],s*d/2],[section[j-1][0],section[j-1][1],s*d/2]);const glazing=triangles(roof,gables,glass,'garden-shed-gable');glazing.material=shell.material.clone();
      const door=o.openingWidth??w*.65;block(g,-(w+door)/4,h*.42,d/2,(w-door)/2,h*.84,.09,o.wallColor||'#889c9e');block(g,(w+door)/4,h*.42,d/2,(w-door)/2,h*.84,.09,o.wallColor||'#889c9e');block(g,0,h*.92,d/2,w,h*.16,.09,o.wallColor||'#889c9e');block(g,0,h/2,-d/2,w,h,.09,o.wallColor||'#889c9e');
      if(o.sign)label(g,o.sign,[0,h*.94,d/2+.07],[w*.65,h*.14],o.signColor||'#e2ddcc');
      // Fine alternating steel diagonals visible through the entrance.
      for(let k=1;k<section.length;k++)rod(roof,[section[k-1][0],section[k-1][1],d/2],[section[k][0],h,d/2],th*.8,c);
    }else for(const s of [-1,1]){
      quad(walls,[-w/2,0,s*d/2],[w/2,0,s*d/2],[w/2,h,s*d/2],[-w/2,h,s*d/2]);
      for(let j=1;j<section.length;j++)quad(walls,[section[j-1][0],h,s*d/2],[section[j][0],h,s*d/2],[section[j][0],section[j][1],s*d/2],[section[j-1][0],section[j-1][1],s*d/2]);
    }
    const wall=triangles(g,walls,kind==='shed'?o.wallColor||'#8fa0a0':glass,'garden-shelter-skin');wall.material=shell.material.clone();wall.material.color.set(kind==='shed'?o.wallColor||'#8fa0a0':glass);
    if(o.cropRows){const rows=o.cropRows;for(let i=0;i<rows;i++){const x=-w*.4+(i+.5)*w*.8/rows;planting({spacing:.7,height:.2,colors:['#a7af91']},g,boundary({size:[w*.6/rows,d*.88],shape:'rectangle'}).map(p=>[p[0]+x,p[1]]),.1);}}
    roofRecords.push({group:roof,parameters:{width:w,depth:d,eaveHeight:h,ridgeHeight:h+rise},tiers:1,thickness:.1,ridgeOrnament:false});
  });
  // Landmark branches are opt-in: existing defaults never enter these builders.
  register('garden_windmill',(o,g)=>{
    const h=o.height??9,r=o.radius??2,top=o.topRadius??r*.48,sides=o.sides??8,rise=o.roofRise??1.4,c=o.color||'#ae655e',trim=o.trimColor||'#e2ddcc',roof=o.roofColor||'#756b62',hub=o.hubHeight??h*.88,L=o.sailLength??h*.59,sw=o.sailWidth??L*.18;
    if(h<=0||r<=0||top<=0||sides<3||(o.courseSpacing??.24)<=0)throw new RangeError('garden_windmill: positive dimensions/courseSpacing and at least three sides required');
    cylinder(g,0,h/2,0,r,h,c,top,sides).rotation.y=Math.PI/sides;cylinder(g,0,.12,0,r*1.08,.24,trim,r*1.08,sides).rotation.y=Math.PI/sides;
    cylinder(g,0,h+rise/2,0,top*1.28,rise,roof,0,sides).rotation.y=Math.PI/sides;
    for(let i=0;i<sides;i++){const a=(i+.5)*Math.PI*2/sides;rod(g,[Math.sin(a)*r,0,Math.cos(a)*r],[Math.sin(a)*top,h,Math.cos(a)*top],.045,trim);}
    const courses=[];for(let y=.3;y<h;y+=o.courseSpacing??.24){const rr=r+(top-r)*y/h+.012;for(let i=0;i<sides;i++){const a=(i+.5)*Math.PI*2/sides,b=a+Math.PI*2/sides;courses.push(Math.sin(a)*rr,y,Math.cos(a)*rr,Math.sin(b)*rr,y,Math.cos(b)*rr);}}linework(g,courses,o.lineColor||'#995d57','garden-windmill-courses');
    for(const [y,w,hh] of [[1.25,r*.48,2.2],[h*.61,r*.3,h*.16]]){
      const z=(r+(top-r)*y/h)*Math.cos(Math.PI/sides)+.055;
      block(g,0,y,z,w,hh,.06,o.openingColor||'#697971');
      for(const s of [-1,1])block(g,s*w*.53,y,z+.045,.065,hh+.15,.08,trim);
      for(const yy of [y-hh/2,y,y+hh/2])block(g,0,yy,z+.05,w+.13,.065,.08,trim);
      block(g,0,y,z+.06,.055,hh,.08,trim);
      rod(g,[-w*.6,y+hh/2,z+.08],[0,y+hh*.68,z+.08],.045,trim);rod(g,[0,y+hh*.68,z+.08],[w*.6,y+hh/2,z+.08],.045,trim);
    }
    if(o.gallery){const y=o.galleryHeight??h*.36,rr=r*1.28;cylinder(g,0,y-.08,0,rr,.16,trim,rr,sides);for(let i=0;i<sides*2;i++){const a=i*Math.PI/sides,b=(i+1)*Math.PI/sides;rod(g,[Math.sin(a)*rr,y,Math.cos(a)*rr],[Math.sin(a)*rr,y+.85,Math.cos(a)*rr],.035,trim);rod(g,[Math.sin(a)*rr,y+.85,Math.cos(a)*rr],[Math.sin(b)*rr,y+.85,Math.cos(b)*rr],.04,trim);}}
    const rotor=new THREE.Group();rotor.name='garden-windmill-rotor';rotor.position.set(0,hub,top*1.35+.18);rotor.rotation.z=rad(o.sailAngle??45);g.add(rotor);
    const axle=cylinder(rotor,0,0,-.12,.18,.65,o.hubColor||roof,.18,16);axle.rotation.x=Math.PI/2;
    for(let k=0;k<4;k++){const sub=new THREE.Group();sub.name='garden-windmill-sail';sub.rotation.z=k*Math.PI/2;rotor.add(sub);rod(sub,[0,0,0],[0,L,0],.055,trim);for(const s of [-1,1])rod(sub,[s*sw/2,L*.24,0],[s*sw/2,L,0],.034,trim);for(let j=0;j<=12;j++){const y=L*(.24+.76*j/12);rod(sub,[-sw/2,y,0],[sw/2,y,0],.025,trim);}rod(sub,[-sw/2,L*.24,0],[sw/2,L*.24,0],.03,trim);}
  });
  register('garden_turbine',(o,g)=>{
    const h=o.height??60,r=o.mastRadius??h*.022,L=o.bladeLength??h*.45,c=o.color||'#deded3',hub=o.hubColor||'#c5c9c0';
    if(h<=0||r<=0||L<=0)throw new RangeError('garden_turbine: positive height, mastRadius and bladeLength required');
    cylinder(g,0,h/2,0,r,h,c,r*.43,24);cylinder(g,0,.15,0,r*1.55,.3,o.baseColor||'#b9b9aa');
    ellipsoid(g,[0,h,0],[r*.85,r*.85,r*2.1],hub);const rotor=new THREE.Group();rotor.name='garden-turbine-rotor';rotor.position.set(0,h,r*2.2);rotor.rotation.z=rad(o.bladeAngle??15);g.add(rotor);ellipsoid(rotor,[0,0,.1],[r*.75,r*.75,r*.7],c);
    for(let k=0;k<3;k++){const shape=new THREE.Shape();shape.moveTo(-r*.16,r*.3);shape.lineTo(-L*.055,L*.18);shape.lineTo(-L*.025,L*.65);shape.lineTo(0,L);shape.lineTo(L*.012,L*.98);shape.lineTo(L*.045,L*.28);shape.lineTo(r*.24,r*.55);shape.closePath();const geo=new THREE.ExtrudeGeometry(shape,{depth:r*.16,bevelEnabled:false});const m=add(rotor,geo,c,'garden-turbine-blade');m.rotation.z=k*Math.PI*2/3;}
  });
  function glassBridge(o,g){
    const ends=o.ends||[[-15,3,0],[15,3,0]],A=ends[0],B=ends[1],w=o.width??2.4,sag=o.sag??.65,rh=o.railHeight??1.2,n=o.segments??48,th=o.thickness??.12,tower=o.towerHeight??5,frame=o.frameColor||'#a2ada7',rail=o.railColor||'#dedfd4',dx=B[0]-A[0],dz=B[2]-A[2],len=Math.hypot(dx,dz),nx=-dz/len,nz=dx/len;
    if(len<=0||n<2)throw new RangeError('garden_bridge glass: distinct ends and at least two segments required');
    const p=(t,side=0,dy=0)=>[A[0]+dx*t+nx*side,A[1]+(B[1]-A[1])*t-4*sag*t*(1-t)+dy,A[2]+dz*t+nz*side],deck=[],joints=[];
    for(let i=0;i<n;i++){const a=i/n,b=(i+1)/n;quad(deck,p(a,-w/2),p(b,-w/2),p(b,w/2),p(a,w/2));joints.push(...p(a,-w/2,.008),...p(a,w/2,.008));}
    const m=triangles(g,deck,o.glassColor||'#aec5c6','garden-glass-deck',true);m.material=material(o.glassColor||'#aec5c6').clone();m.material.side=THREE.DoubleSide;m.material.transparent=true;m.material.opacity=o.opacity??.72;m.material.depthWrite=false;
    linework(g,joints,frame,'garden-glass-panel-seams');
    for(const side of [-1,1]){const edge=[],hand=[],cable=[];for(let i=0;i<=n;i++){const t=i/n;edge.push(p(t,side*w/2,-th));hand.push(p(t,side*w/2,rh));cable.push(p(t,side*(w/2+.16),tower*(1-4*.68*t*(1-t))));if(i%3===0){rod(g,p(t,side*w/2),p(t,side*w/2,rh),.025,rail);rod(g,p(t,side*(w/2+.16),rh),cable.at(-1),.018,frame);}}
      tube(g,edge,.045,frame);tube(g,hand,.045,rail);tube(g,cable,o.cableRadius??.055,frame);
      for(const t of [0,1]){const pt=p(t,side*(w/2+.16)),foot=o.footY??0;rod(g,[pt[0],foot,pt[2]],[pt[0],pt[1]+tower,pt[2]],o.towerRadius??.13,frame);}
    }
    for(const t of [0,1])rod(g,p(t,-w/2-.16,tower),p(t,w/2+.16,tower),.12,frame);
  }
  function archTunnel(o,g){
    const count=o.repeat??5,pitch=o.pitch??2.7,w=o.width??4,h=o.height??4.6,th=o.thickness??.18,colors=o.colors||['#8c9c7d','#b68c9d','#d6c9b5'],cover=[],flowers=[],frame=o.frameColor||'#c2bc9f';
    if(count<1||pitch<=0||w<=0||h<=0||th<=0||!colors.length||(o.coverSpacing??.17)<=0)throw new RangeError('garden_arch tunnel: positive repeat/dimensions/coverSpacing and a nonempty palette required');
    if(o.canopy){const rows=o.rows??3,kind=o.canopy,items=[];for(let i=0;i<count;i++){const z=-i*pitch;for(const s of [-1,1])rod(g,[s*w/2,0,z],[s*w/2,h,z],.045,frame);rod(g,[-w/2,h,z],[w/2,h,z],.025,frame);for(let j=0;j<rows;j++){const x=-w/2+w*(j+.5)/rows,y=h-.25,r=o.elementRadius??.42,c=colors[(i+j)%colors.length];rod(g,[x,h,z],[x,y,z],.012,frame);if(kind==='umbrella'){const m=add(g,new THREE.ConeGeometry(r,r*.3,8,1,true),c);m.position.set(x,y,z);m.material=material(c).clone();m.material.side=THREE.DoubleSide;rod(g,[x,y-r*.45,z],[x,y+r*.1,z],.015,frame);}else for(let k=0;k<4;k++){const a=k*Math.PI/2;items.push({p:[x+Math.cos(a)*r*.45,y+Math.sin(a)*r*.45,z],s:[r*.75,r*.26,.035],r:[0,0,a+.6],c});}}}instances(g,cube,items,'#ffffff','garden-pinwheel-canopy');return;}
    for(let i=0;i<count;i++){const z=-i*pitch,pts=[];if(o.outline==='heart'){
      // Open the lower cusp into two grounded feet: no stem crosses the path.
      const foot=2.2,fy=13*Math.cos(foot)-5*Math.cos(2*foot)-2*Math.cos(3*foot)-Math.cos(4*foot);
      for(let j=0;j<=96;j++){const t=-foot+j*foot*2/96,x=16*Math.sin(t)**3,y=13*Math.cos(t)-5*Math.cos(2*t)-2*Math.cos(3*t)-Math.cos(4*t);pts.push([x*w/32,(y-fy)*h/(12-fy),z]);}
    }else{pts.push([-w/2,0,z],[-w/2,h-w/2,z]);for(let j=0;j<=48;j++){const a=Math.PI-j*Math.PI/48;pts.push([Math.cos(a)*w/2,h-w/2+Math.sin(a)*w/2,z]);}pts.push([w/2,0,z]);}
      // A polyline preserves the heart cusp and does not overshoot the feet.
      let serial=0;for(let j=1;j<pts.length;j++){const a=pts[j-1],b=pts[j];rod(g,a,b,th,o.style==='metal'?frame:colors[0]);const length=Math.hypot(...a.map((v,k)=>b[k]-v)),steps=Math.max(1,Math.ceil(length/(o.coverSpacing??.17)));if(o.style==='metal')continue;for(let k=0;k<steps;k++){const f=k/steps,p=a.map((v,q)=>v+(b[q]-v)*f),id=serial++;for(const face of [-1,1]){cover.push({p:[p[0],p[1],z+face*th*.25],s:[th*1.25,th*1.1,th*.85],c:colors[0]});if(hash(id+i*77)<(o.flowerShare??.35))flowers.push({p:[p[0]+(hash(id*7)-.5)*th,p[1],z+face*th*1.13],s:[th*1.5,1,th*1.5],r:[Math.PI/2,hash(id)*6,0],c:colors[1+(id%(colors.length-1||1))]||colors[0]});}}}
    }instances(g,sphere,cover,'#ffffff','garden-tunnel-flower-cover');const blooms=instances(g,bloom,flowers,'#ffffff','garden-tunnel-blossoms');if(blooms){blooms.material=material('#ffffff').clone();blooms.material.side=THREE.DoubleSide;}
  }
  function cloudPines(o,g){
    const pads=[],texture=[],h=o.height??5,r=o.radius??2.2,c=o.color||'#839276',wood=o.trunkColor||'#887a65',levels=o.padLevels??5;
    if(levels<1)throw new RangeError('garden_conifer cloud: padLevels must be positive');
    for(const [i,p] of (o.points||[[0,0]]).entries()){
      const [x,z]=p,H=p[2]??h,R=p[3]??r,y=p[4]??0,twist=o.twist??.23,trunk=t=>[x+Math.sin(t*5+i)*H*twist*.36,y+H*t,z+Math.sin(t*4+i+1)*H*twist*.22];
      tube(g,[[x,y,z],trunk(.24),trunk(.52),trunk(.76),trunk(.97)],H*.027,wood,'garden-cloud-twisted-trunk');
      if(o.pot){const ph=o.potHeight??H*.16,pr=o.potRadius??R*.65;cylinder(g,x,y-ph/2,z,pr*.75,ph,o.potColor||'#a59680',pr,12);cylinder(g,x,y,z,pr*1.04,ph*.1,o.potColor||'#a59680');}
      for(let j=0;j<levels;j++){const f=j/Math.max(1,levels-1),t=.32+f*.6,a=i*1.71+j*2.5,spread=R*(1-f*.63),start=trunk(t-.1),end=[x+Math.cos(a)*spread*.75,y+H*t,z+Math.sin(a)*spread*.65];tube(g,[start,[(start[0]+end[0])*.5,end[1]-H*.05,(start[2]+end[2])*.5],end],H*.014*(1-f*.5),wood);
        for(let k=0;k<3;k++){const b=k*2.4+j,px=end[0]+Math.cos(b)*spread*.3,pz=end[2]+Math.sin(b)*spread*.24,py=end[1]+H*.015*k;pads.push({p:[px,py,pz],s:[spread*.64,H*.033,spread*.48],c:j%2?c:o.tipColor||'#97a488'});if(o.texture!==false)for(let q=0;q<5;q++){const aa=q*2.4,rr=Math.sqrt((q+.5)/5);texture.push({p:[px+Math.cos(aa)*spread*.49*rr,py+H*.028,pz+Math.sin(aa)*spread*.35*rr],s:[spread*.25,H*.012,spread*.2],c});}}
      }
    }instances(g,sphere,pads,'#ffffff','garden-cloud-foliage-pads');instances(g,leaf,texture,'#ffffff','garden-cloud-needle-mats');
  }
  function rocks(g,points,c,seed=1){
    const items=points.map((p,i)=>({p:[p[0],(p[4]??0)+p[3]/2,p[1]],s:[p[2],p[3]/2,p[5]??p[2]*.8],r:[.06*Math.sin(i),hash(i+seed)*6,.09*Math.cos(i)],c:i%3?c:'#aaa18e'}));
    instances(g,new THREE.IcosahedronGeometry(1,2),items,'#ffffff','garden-rounded-boulders');
  }
  register('garden_rockery',(o,g)=>{rocks(g,o.rocks||[[-2,0,1.8,2],[1,0,1.4,3.5],[0,2,1.6,1.2]],o.color||'#999481',o.seed??1);});
  register('garden_koi_pond',(o,g)=>{
    const poly=boundary(o),level=o.level??.18,c=o.rockColor||'#999481',seed=o.seed??1;
    slab(g,poly,level-.12,level,o.color||'#839c93');
    const shore=[],pitch=o.rockSpacing??1.5;let run=0,next=0,k=0;
    if(pitch<=0)throw new RangeError('garden_koi_pond: rockSpacing must be positive');
    for(let i=0;i<poly.length;i++){const a=poly[i],b=poly[(i+1)%poly.length],len=Math.hypot(b[0]-a[0],b[1]-a[1]);if(len<1e-7)continue;while(next<run+len){const t=(next-run)/len,r=(o.rockRadius??.8)*(.72+hash(k+seed)*.55);shore.push([a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t,r,r*(.65+hash(k)*.6),level-.14,r*(.65+hash(k+8)*.3)]);k++;next+=pitch;}run+=len;}rocks(g,shore,c,seed);
    if(o.waterfall){const f=o.waterfall,[x,z]=f.position||[0,-(o.size?.[1]??8)/2],h=f.height??2.8,w=f.width??3.5,tiers=f.tiers??3,depth=f.depth??2.4,boulders=[];
      if(tiers<1||h<=0||w<=0||depth<=0)throw new RangeError('garden_koi_pond waterfall: positive tiers and dimensions required');
      for(let j=0;j<tiers;j++){const y=level+h*(1-j/tiers),zz=z+depth*j/tiers;for(const s of [-1,1])boulders.push([x+s*w*(.52+j%2*.04),zz,w*.26,h/tiers*1.4,y-h/tiers,w*.28]);boulders.push([x,zz-depth/tiers*.45,w*.51,h/tiers*.5,y-h/tiers,w*.18]);const endY=level+h*(1-(j+1)/tiers),verts=[];quad(verts,[x-w*.23,y,zz],[x+w*.23,y,zz],[x+w*.27,endY,zz+depth/tiers],[x-w*.27,endY,zz+depth/tiers]);const m=triangles(g,verts,f.color||'#cfdbd3','garden-rock-waterfall');m.material=material(f.color||'#cfdbd3').clone();m.material.side=THREE.DoubleSide;for(let k=0;k<9;k++)rod(g,[x+w*(k/8-.5)*.43,y+.015,zz+.025],[x+w*(k/8-.5)*.49,endY+.025,zz+depth/tiers+.025],.012,'#e3e7da');}rocks(g,boulders,c,seed);}
    const fish=[],colors=o.koiColors||['#c18b60','#ddd7c4','#a96d5e'];for(let i=0;i<(o.koi??16);i++){const xs=poly.map(p=>p[0]),zs=poly.map(p=>p[1]),x=Math.min(...xs)+(Math.max(...xs)-Math.min(...xs))*hash(i*7+seed),z=Math.min(...zs)+(Math.max(...zs)-Math.min(...zs))*hash(i*13+seed);if(!inside(x,z,poly))continue;const a=hash(i+2)*6;fish.push({p:[x,level+.018,z],s:[.3,.018,.09],r:[0,a,0],c:colors[i%colors.length]});}instances(g,sphere,fish,'#ffffff','garden-koi');
    for(const [x,z,r=.65] of o.steppingStones||[]){const poly=Array.from({length:12},(_,i)=>[x+Math.cos(i*Math.PI/6)*r,z+Math.sin(i*Math.PI/6)*r*.7]);slab(g,poly,level-.07,level+.16,o.stoneColor||'#bfb6a0',true);}
  });
  function figurative(o,g){
    const [w,h,d]=o.size||[4,8,3],base=o.plinthHeight??.7,c=o.color||(o.kind==='clay'?'#a56f53':'#a5b1a0'),light=o.highlightColor||c,dark=o.shadowColor||'#767d70';
    block(g,0,base/2,0,w*(o.plinthScale??1.04),base,d*1.12,o.plinthColor||'#8e8d7b');
    if(o.kind==='liberty'||o.kind==='clay'&&o.figure==='standing'){
      const robe=new THREE.CylinderGeometry(w*.19,w*.39,h*.61,14);const body=add(g,robe,c);body.position.y=base+h*.305;
      ellipsoid(g,[0,base+h*.68,0],[w*.17,h*.1,d*.2],c);ellipsoid(g,[0,base+h*.56,0],[w*.29,h*.09,d*.25],c);
      tube(g,[[w*.22,base+h*.55,0],[w*.38,base+h*.73,0],[w*.43,base+h*.91,.03]],w*.068,c);
      tube(g,[[-w*.22,base+h*.56,0],[-w*.34,base+h*.41,d*.2],[-w*.13,base+h*.43,d*.32]],w*.07,c);
      block(g,-w*.15,base+h*.44,d*.33,w*.25,h*.18,.16,c);
      cylinder(g,w*.43,base+h*.94,.03,w*.06,h*.1,c,w*.13,10);ellipsoid(g,[w*.43,base+h*.995,.03],[w*.065,h*.035,d*.08],o.torchColor||'#c5ad78');
      for(let i=0;i<7;i++){const a=i*Math.PI/6;rod(g,[Math.cos(a)*w*.13,base+h*.735+Math.sin(a)*h*.035,0],[Math.cos(a)*w*.28,base+h*.735+Math.sin(a)*h*.09,0],w*.018,c);}
      for(let i=0;i<9;i++){const x=(i-4)*w*.065;rod(g,[x*.5,base+h*.5,d*.22],[x,base+.05,d*.32],.014,o.lineColor||dark);}return;
    }
    // Smooth monumental head with projecting facial planes, never a portrait texture.
    const head=(p,s,color)=>{const m=add(g,new THREE.SphereGeometry(1,24,16),color);m.position.set(...p);m.scale.set(...s);return m;};
    cylinder(g,0,base+h*.11,-d*.06,w*.2,h*.22,c,w*.23,24);
    head([0,base+h*.6,0],[w*.37,h*.4,d*.43],c);
    head([0,base+h*.32,d*.18],[w*.24,h*.12,d*.28],c);
    for(const s of [-1,1]){head([s*w*.353,base+h*.57,-d*.015],[w*.035,h*.075,d*.07],c);head([s*w*.14,base+h*.61,d*.406],[w*.072,h*.012,d*.026],dark);tube(g,[[s*w*.04,base+h*.65,d*.43],[s*w*.15,base+h*.67,d*.42],[s*w*.25,base+h*.63,d*.35]],w*.018,light);head([s*w*.17,base+h*.49,d*.29],[w*.13,h*.085,d*.14],c);}
    const nose=[],a=[-w*.045,base+h*.68,d*.37],b=[w*.045,base+h*.68,d*.37],tip=[0,base+h*.49,d*.67],left=[-w*.065,base+h*.47,d*.41],right=[w*.065,base+h*.47,d*.41];nose.push(...a,...left,...tip,...b,...tip,...right,...left,...right,...tip);const nm=triangles(g,nose,light,'garden-bust-nose');nm.material=material(light).clone();nm.material.side=THREE.DoubleSide;
    head([0,base+h*.385,d*.398],[w*.12,h*.02,d*.04],c);tube(g,[[-w*.12,base+h*.39,d*.421],[0,base+h*.38,d*.441],[w*.12,base+h*.39,d*.421]],w*.009,dark);
    const lines=[];for(let i=0;i<11;i++){const x=(i-5)*w*.06;lines.push(x,base+h*.86,d*.3,x*.8,base+h*.97,d*.15);}linework(g,lines,o.lineColor||dark,'garden-head-carved-hair');
    for(const s of [-1,1])for(let i=0;i<5;i++)tube(g,[[s*w*(.24+i*.018),base+h*.87,-d*.16],[s*w*(.34+i*.007),base+h*.78,-d*.06],[s*w*(.36-i*.005),base+h*.69,d*.06]],w*.009,o.lineColor||dark,'garden-bust-side-carving');
    for(const s of [-1,1])for(let i=0;i<3;i++){const pts=[];for(let j=0;j<=32;j++){const a=j*Math.PI*3/32,r=(1-j/40)*h*.055;pts.push([s*w*.357,base+h*(.6+i*.1)+Math.sin(a)*r,-d*.08+Math.cos(a)*r]);}tube(g,pts,w*.008,o.lineColor||dark,'garden-bust-carved-scroll');}
  }
  register('garden_clay_tunnel',(o,g)=>{
    if(o.kind==='wall'){clayWall(o,g);return;}
    const [w,h,len]=o.size||[7,5,18],t=o.wallThickness??1.25,roof=o.roofed??false,c=o.color||'#a46f52',frame=o.reliefColor||'#ba8764',base=o.floorLevel??.08,bays=o.bays??4;
    if(w<=2*t||h<=w/2||bays<1)throw new RangeError('garden_clay_tunnel: clear width, positive bays and height above arch spring required');
    slab(g,boundary({shape:'rectangle',size:[w,len]}),-.06,base,o.floorColor||'#c5ac89',true);
    const clear=w-2*t,r=clear/2,spring=h-r,shape=new THREE.Shape();shape.moveTo(-w/2,base);shape.lineTo(-w/2,h+.35);shape.lineTo(w/2,h+.35);shape.lineTo(w/2,base);shape.lineTo(r,base);shape.lineTo(r,spring);shape.absarc(0,spring,r,0,Math.PI,false);shape.lineTo(-r,base);shape.closePath();
    for(const z of [-len/2,len/2]){const geo=new THREE.ExtrudeGeometry(shape,{depth:t,bevelEnabled:true,bevelSize:.09,bevelThickness:.09,bevelSegments:2});geo.translate(0,0,z-t/2);add(g,geo,c,'garden-clay-arched-portal');}
    for(const s of [-1,1]){block(g,s*(w-t)/2,h/2,0,t,h,len,c);for(const y of [h*.27,h*.71,h*.93]){const pts=[];for(let j=0;j<=bays*8;j++){const z=-len/2+j*len/(bays*8);pts.push([s*(w/2+.035),y+Math.sin(j*Math.PI/4)*h*.018,z]);}tube(g,pts,.065,frame,'garden-clay-relief-band');}for(let j=0;j<bays;j++){const z=-len/2+(j+.5)*len/bays;ellipsoid(g,[s*(w/2+.04),h*.48,z],[.17,h*.12,len/bays*.23],frame);}}
    if(roof){const outer=r+t,archShape=new THREE.Shape();archShape.absarc(0,spring,outer,0,Math.PI,false);archShape.absarc(0,spring,r,Math.PI,0,true);archShape.closePath();const geo=new THREE.ExtrudeGeometry(archShape,{depth:len,bevelEnabled:false,curveSegments:28});geo.translate(0,0,-len/2);add(g,geo,c,'garden-clay-vault');}
    if(o.sign)label(g,o.sign,[0,h+.12,len/2+t/2+.1],[w*.85,.4],o.signColor||'#dfc5a1');
  });
  function clayWall(o,g){
    const [w,h,d]=o.size||[18,6,1.7],count=o.openings??3,clear=o.openingWidth??w/(count*1.65),c=o.color||'#a46f52',relief=o.reliefColor||'#ba8764',spring=o.springHeight??h*.48;
    if(count<1||clear*count>=w||spring+clear/2>=h)throw new RangeError('garden_clay_tunnel wall: openings must fit wall width and height');
    const shape=new THREE.Shape();shape.moveTo(-w/2,0);shape.lineTo(-w/2,h);shape.lineTo(w/2,h);shape.lineTo(w/2,0);
    for(let i=count-1;i>=0;i--){const x=-w/2+w*(i+.5)/count,r=clear/2;shape.lineTo(x+r,0);shape.lineTo(x+r,spring);shape.absarc(x,spring,r,0,Math.PI,false);shape.lineTo(x-r,0);}shape.closePath();
    const geo=new THREE.ExtrudeGeometry(shape,{depth:d,bevelEnabled:true,bevelSize:.08,bevelThickness:.08,bevelSegments:2});geo.translate(0,0,-d/2);add(g,geo,c,'garden-carved-clay-wall');
    for(const side of [-1,1]){for(const y of [h*.88,h*.97]){const pts=[];for(let i=0;i<=48;i++)pts.push([-w/2+i*w/48,y+Math.sin(i*Math.PI/4)*.055,side*(d/2+.035)]);tube(g,pts,.05,relief);}for(let i=0;i<=count;i++){const x=-w/2+w*i/count;ellipsoid(g,[x,h*.45,side*(d/2+.025)],[w/count*.1,h*.2,.14],relief);}}
    // Only the real openings receive narrow walkable thresholds.
    for(let i=0;i<count;i++){const x=-w/2+w*(i+.5)/count;slab(g,[[x-clear/2,-d/2-.4],[x+clear/2,-d/2-.4],[x+clear/2,d/2+.4],[x-clear/2,d/2+.4]],-.04,.06,o.floorColor||'#c5ac89',true);}
  }
})();
