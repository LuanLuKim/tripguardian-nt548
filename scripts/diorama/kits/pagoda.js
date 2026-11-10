// Reusable pagoda kit. Local +z faces the forecourt; dimensions are metres.
(()=>{
  const defaultColors={cream:'#e4dfd0',stone:'#b9b3a4',wall:'#c7bd9d',sage:'#80968b',edge:'#a5b4a6',line:'#8d8878',dark:'#4e5149',rose:'#a18b7c',gold:'#b7a37c'};
  let C=defaultColors;
  function withColors(palette,build){const previous=C;C={...defaultColors,...palette};try{return build();}finally{C=previous;}}
  const mat=new Map();
  const hallFronts=new Map();
  function paint(c){if(!mat.has(c))mat.set(c,material(c));return mat.get(c);}
  const ceramicMaterials=new Map();
  function ceramic(c){
    const flecks=C.mosaicColors,key=flecks?`${c}|${flecks.join(',')}`:c;
    if(ceramicMaterials.has(key))return ceramicMaterials.get(key);
    const m=paint(c).clone();m.userData.ceramic=true;
    m.customProgramCacheKey=()=>`ceramic-joints-v1-${key}`;
    const photoFlecks=flecks?.map((hex,i)=>{const rgb=new THREE.Color(hex).toArray().map(n=>n.toFixed(6)).join(',');return `${i<flecks.length-1?`seed<${((i+1)/flecks.length).toFixed(6)}?`:''}vec3(${rgb})${i<flecks.length-1?':':''}`;}).join('');
    m.onBeforeCompile=shader=>{
      shader.vertexShader=shader.vertexShader.replace('#include <common>','#include <common>\nvarying vec3 vCeramicPosition; varying vec3 vCeramicNormal;').replace('#include <begin_vertex>','#include <begin_vertex>\nvCeramicPosition=position; vCeramicNormal=normal;');
      shader.fragmentShader=shader.fragmentShader.replace('#include <common>','#include <common>\nvarying vec3 vCeramicPosition; varying vec3 vCeramicNormal;').replace('#include <color_fragment>',`#include <color_fragment>
        vec3 cn=abs(vCeramicNormal); vec2 cp=cn.y>max(cn.x,cn.z)?vCeramicPosition.xz:(cn.x>cn.z?vCeramicPosition.zy:vCeramicPosition.xy);
        cp*=5.8; cp.x+=sin(floor(cp.y)*2.41)*.28; cp.y+=sin(cp.x*1.8)*.10;
        vec2 cell=floor(cp), uv=fract(cp); float seed=fract(sin(dot(cell,vec2(127.1,311.7)))*43758.5453);
        float joint=min(min(uv.x,1.-uv.x),min(uv.y,1.-uv.y));
        joint=min(joint,abs(uv.x+uv.y-(.65+seed*.7))*.65);
        float edge=1.-smoothstep(.013,.013+max(fwidth(cp.x),fwidth(cp.y))*.9,joint);
        ${photoFlecks?`vec3 photoFleck=${photoFlecks};
        diffuseColor.rgb=mix(diffuseColor.rgb,photoFleck,.72)*(1.-edge*.16);`:`vec3 tint=seed<.25?vec3(.82,.91,.86):(seed<.5?vec3(1.,.94,.81):(seed<.75?vec3(.94,.85,.84):vec3(1.,.99,.94)));
        diffuseColor.rgb*=mix(tint,vec3(.72,.72,.67),edge*.42);`}`);
    };
    ceramicMaterials.set(key,m);return m;
  }
  function root(o){const g=new THREE.Group();g.name=o.id;g.position.set(...o.position);g.rotation.y=(o.rotation||0)*Math.PI/180;scene.add(g);return g;}
  function add(g,geo,c){const m=new THREE.Mesh(geo,typeof c==='string'?paint(c):c);m.castShadow=true;m.receiveShadow=true;g.add(m);return m;}
  function block(g,x,y,z,w,h,d,c=C.cream){const m=add(g,new THREE.BoxGeometry(w,h,d),c);m.position.set(x,y,z);return m;}
  function tube(g,points,r,c,closed=false){return add(g,new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points.map(p=>new THREE.Vector3(...p)),closed),Math.max(12,points.length*6),r,6,closed),c);}
  function lines(g,p,c=C.line){const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(p,3));const m=new THREE.LineSegments(geo,new THREE.LineBasicMaterial({color:c,transparent:true,opacity:.38}));g.add(m);return m;}
  function instances(g,geo,items,name,c=C.cream){
    if(!items.length)return;const m=new THREE.InstancedMesh(geo,paint(c),items.length),dummy=new THREE.Object3D();m.name=name;m.castShadow=true;m.receiveShadow=true;
    items.forEach((p,i)=>{dummy.position.set(...p.p);dummy.scale.set(...(p.s||[1,1,1]));dummy.rotation.set(...(p.r||[0,0,0]));dummy.updateMatrix();m.setMatrixAt(i,dummy.matrix);if(p.c)m.setColorAt(i,new THREE.Color(p.c));});m.computeBoundingBox();m.computeBoundingSphere();g.add(m);
    g.updateWorldMatrix(true,true);geo.computeBoundingBox();const b=geo.boundingBox,matrix=new THREE.Matrix4();
    if(currentEnvelope)for(let i=0;i<items.length;i++){m.getMatrixAt(i,matrix);for(const x of [b.min.x,b.max.x])for(const y of [b.min.y,b.max.y])for(const z of [b.min.z,b.max.z])currentEnvelope.push(new THREE.Vector3(x,y,z).applyMatrix4(matrix).applyMatrix4(m.matrixWorld));}
    return m;
  }
  function compact(g){
    for(const child of g.children)if(child.isGroup)compact(child);
    const batches=new Map();for(const m of g.children){if(!m.isMesh||m.isInstancedMesh||m.name||m.material.map)continue;const key=m.material;if(!batches.has(key))batches.set(key,[]);batches.get(key).push(m);}
    for(const [m,parts] of batches){if(parts.length<2)continue;const geos=parts.map(p=>{p.updateMatrix();const geo=p.geometry.index?p.geometry.toNonIndexed():p.geometry.clone();for(const a of Object.keys(geo.attributes))if(!['position','normal'].includes(a))geo.deleteAttribute(a);return geo.applyMatrix4(p.matrix);});const merged=new THREE.Mesh(mergeGeometries(geos),m);merged.castShadow=true;merged.receiveShadow=true;parts.forEach(p=>{g.remove(p);p.geometry.dispose();});g.add(merged);geos.forEach(p=>p.dispose());}
  }
  function flatten(g,child){child.updateMatrix();for(const part of [...child.children]){part.applyMatrix4(child.matrix);g.add(part);}g.remove(child);}
  function register(type,fn){registerObjectType(type,o=>withColors(o.palette,()=>{const g=root(o);fn(o,g);compact(g);}));}
  function roof(g,w,d,eave,rise,z=0,color=C.sage,options={}){
    const first=scene.children.length;let result;
    vietnameseRoof({position:[0,0,z],width:w,depth:d,eaveHeight:eave,ridgeHeight:eave+rise,overhang:options.overhang??.7,cornerLift:options.curl??.7,curve:.15,thickness:.15,ridgeOrnament:options.ornament??true,color,trimColor:C.edge,tileSpacing:.5});
    for(const child of scene.children.slice(first)){
      result=child;
      g.add(child);child.position.x+=options.x||0;child.rotation.y+=(options.rotation||0)*Math.PI/180;
      if(options.figures){
        const figures=new THREE.Group();figures.name='pagoda-ridge-figures';child.add(figures);
        const p=roofRecords.find(record=>record.group===child).parameters;
        const halfWidth=p.width/2+p.overhang,ridgeHalf=Math.max(.02,(p.width-p.depth)/2);
        const surfaceY=x=>Math.abs(x)<=ridgeHalf?p.ridgeHeight:roofSurfacePoint(x>0?2:3,0,(halfWidth-Math.abs(x))/(halfWidth-ridgeHalf),p).y;
        for(const s of [-1,1]){
          const x=s*p.width*.24,y=surfaceY(x),curlX=s*p.width*.38,curlY=surfaceY(curlX);
          tube(figures,[[curlX,curlY,0],[curlX+s*.35,curlY+.33,0],[curlX+s*.44,curlY+.9,0],[curlX+s*.1,curlY+1,0]],.075,C.cream);
          const robe=add(figures,new THREE.ConeGeometry(.22,.64,8),C.gold);robe.position.set(x,y+.30,0);
          const head=add(figures,new THREE.SphereGeometry(.12,8,6),C.cream);head.position.set(x,y+.74,0);
        }
      }
    }
    return result;
  }
  function portal(g,x,y,z,w,h){
    const group=new THREE.Group();group.name='pagoda-layered-portal';g.add(group);
    for(let layer=0;layer<3;layer++){
      const radius=w/2+layer*.16,top=y+h-w/2,pts=[[x-radius,y,z+layer*.07],[x-radius,top,z+layer*.07]];
      for(let i=0;i<=28;i++){const a=Math.PI-i*Math.PI/28;pts.push([x+Math.cos(a)*radius,top+Math.sin(a)*radius,z+layer*.07]);}
      pts.push([x+radius,y,z+layer*.07]);tube(group,pts,layer===1?.055:.085,[C.cream,C.gold,C.edge][layer]);
    }
  }
  function arch(g,x,y,z,w,h,depth=.2){
    const s=new THREE.Shape();s.moveTo(-w/2,0);s.lineTo(w/2,0);s.lineTo(w/2,h-w/2);s.absarc(0,h-w/2,w/2,0,Math.PI,false);s.lineTo(-w/2,0);
    const m=add(g,new THREE.ExtrudeGeometry(s,{depth,bevelEnabled:false,curveSegments:12}),C.dark);m.position.set(x,y,z);
    const pts=[[-w/2,y,z+.23],[-w/2,y+h-w/2,z+.23]];for(let k=0;k<=20;k++){const a=Math.PI-k*Math.PI/20;pts.push([x+Math.cos(a)*w/2,y+h-w/2+Math.sin(a)*w/2,z+.23]);}pts[0][0]+=x;pts[1][0]+=x;pts.push([x+w/2,y,z+.23]);tube(g,pts,.075,C.cream);
  }
  function mosaic(g,panels,density=.12){
    const items=[];
    const colors=C.mosaicColors??['#d5ceba','#9bac9e','#c3af89','#b69d92'];
    for(const [x,y,z,w,h] of panels)for(let ix=-w/2+density*.5;ix<w/2;ix+=density)for(let iy=density*.5;iy<h;iy+=density){const k=items.length,j=Math.sin(k*12.71),seed=Math.sin((k+1)*12.9898)*43758.5453,index=C.mosaicColors?Math.floor((seed-Math.floor(seed))*colors.length):k%colors.length;items.push({p:[x+ix+j*density*.08,y+iy,z+.035],s:[density*(.78+j*.08),density*(.82-j*.09),.018],r:[0,0,j*.17],c:colors[index]});}
    const chip=new THREE.Shape();chip.moveTo(-.5,-.4);chip.lineTo(-.1,-.5);chip.lineTo(.5,-.32);chip.lineTo(.42,.5);chip.lineTo(-.46,.42);chip.closePath();
    const relief=instances(g,new THREE.ShapeGeometry(chip),items,'pagoda-mosaic-inlays','#ffffff');if(relief)relief.castShadow=false;
  }
  function column(g,x,z,h,r=.28,color,reliefColor=C.edge){
    const m=add(g,new THREE.CylinderGeometry(r*.85,r,h,10),color??ceramic(C.wall));m.position.set(x,h/2+.16,z);block(g,x,.17,z,r*2.6,.34,r*2.6,C.stone);
    const pts=[];for(let i=0;i<75;i++){const a=i*.22;pts.push([x+Math.cos(a)*r*1.18,.5+i*(h-.6)/74,z+Math.sin(a)*r*1.18]);}tube(g,pts,.065,reliefColor);
  }
  function rail(g,w,z,y){block(g,0,y,z,w,.12,.18,C.cream);block(g,0,y-.65,z,w,.12,.18,C.stone);for(let x=-w/2+.15;x<w/2;x+=.48)block(g,x,y-.34,z,.08,.6,.12,C.cream);}
  function finial(g,x,y,z,h){const m=add(g,new THREE.ConeGeometry(h*.18,h,8),C.stone);m.position.set(x,y+h/2,z);for(let k=0;k<3;k++){const m=add(g,new THREE.TorusGeometry(h*(.18-k*.035),.045,4,12),C.cream);m.rotation.x=Math.PI/2;m.position.set(x,y+h*(.18+k*.24),z);}}
  function sign(g,text,w,y,z){
    const canvas=document.createElement('canvas');canvas.width=1024;canvas.height=128;const c=canvas.getContext('2d');c.fillStyle=C.cream;c.fillRect(0,0,1024,128);c.fillStyle=C.dark;c.font='bold 76px Georgia';c.textAlign='center';let f=76;while(c.measureText(text).width>990&&f>3)c.font=`bold ${--f}px Georgia`;c.fillText(text,512,91);
    const texture=new THREE.CanvasTexture(canvas);texture.colorSpace=THREE.SRGBColorSpace;const m=new THREE.Mesh(new THREE.PlaneGeometry(w,.85),new THREE.MeshBasicMaterial({map:texture}));m.name='pagoda-hall-sign';m.position.set(0,y,z);g.add(m);
  }
  register('pagoda_court',(o,g)=>{
    const [w,d]=o.size,m=block(g,0,.04,0,w,.08,d,o.color||'#d6d0c1');g.updateMatrixWorld(true);walkableGeometries.push(m.geometry.clone().applyMatrix4(m.matrixWorld));
    const p=[];for(let x=-w/2+1;x<w/2;x+=o.grid||2)p.push(x,.083,-d/2,x,.083,d/2);for(let z=-d/2+1;z<d/2;z+=o.grid||2)p.push(-w/2,.083,z,w/2,.083,z);lines(g,p,o.jointColor??'#b4b0a1');
    for(const s of [-1,1])block(g,s*(w/2-.1),.11,0,.16,.2,d,o.curbColor??C.cream);
  });
  register('pagoda_hall',(o,g)=>{
    const [w,d]=o.footprint,h=o.height||6,front=d/2;
    block(g,0,.23,0,w,.46,d,C.stone);
    const fg=new THREE.Group();fg.name='pagoda-facade';g.add(fg);hallFronts.set(o.id,fg);
    if(o.interior){
      for(const s of [-1,1])block(g,s*(w/2-.35),h/2+.4,-.3,.4,h,d-.6,ceramic(C.wall));
      block(g,0,h/2+.4,-d/2+.3,w-.4,h,.4,ceramic(C.wall));
      for(const s of [-1,1])block(fg,s*(w*.3),h/2+.4,front-.5,w*.38,h,.4,ceramic(C.wall));
      block(fg,0,h-.4,front-.5,w*.24,1.6,.4,ceramic(C.wall));
    }else block(g,0,h/2+.4,-.6,w-.65,h,d-1.2,ceramic(C.wall));
    // The dark arched recesses sit in front of the solid closed mass, not behind it.
    for(const x of [-w*.34,-w*.17,0,w*.17,w*.34]){
      if(x!==0||!o.interior)arch(fg,x,.48,front-.48,w*.12,h*.72);
      else {const door=block(fg,0,3.0,front-.4,3.2,5.05,.12,C.dark);door.name='pagoda-entrance-door';}
      column(fg,x+w*.076,front+.04,h*.92,.29);
    }
    if(o.facadeTiers)portal(fg,0,.48,front+.08,3.2,Math.min(h*.72,5.4));
    mosaic(fg,[[-w*.46,.5,front-.30,w*.07,h*.8],[w*.46,.5,front-.30,w*.07,h*.8],[0,h-1,front-.30,w-1,.75]]);
    if(o.sign)sign(fg,o.sign,w*.68,h-.5,front+.2);
    roof(g,w,d,h,2.4,0,o.roofColor||C.sage,{curl:1,figures:Boolean(o.facadeTiers)});
    for(let level=0;level<(o.facadeTiers??2);level++){
      const tw=w*(.64-level*.19),td=d*(.48-level*.10),y=h+2.1+level*3.8;
      block(g,0,y+1,front-td/2-.15,tw-1,2.6,td-.6,ceramic(C.wall));
      for(const x of [-tw*.28,0,tw*.28])arch(g,x,y+.05,front-.55,tw*.17,2.1);
      mosaic(g,[[-tw*.43,y,front-.4,tw*.12,2.4],[tw*.43,y,front-.4,tw*.12,2.4]]);
      rail(g,tw-.6,front+.13,y+.02);const upperRoof=roof(g,tw,td,y+2.5,1.65,front-td/2-.65,o.roofColor||C.sage,{curl:1.05,figures:true});
      if(level===(o.facadeTiers??2)-1){const crown=new THREE.Group();crown.name='pagoda-top-finial';g.add(crown);finial(crown,0,y+4.2,front-td/2-.65,2.5);g.updateWorldMatrix(true,true);upperRoof.attach(crown);}
    }
    for(const s of [-1,1]){const side=new THREE.Group();side.rotation.y=s*Math.PI/2;g.add(side);mosaic(side,[[0,.7,w/2-.17,d-1,1.3],[0,h-1.1,w/2-.17,d-1,.8]]);}
    if(o.sideTurrets!==false)for(const s of [-1,1]){
      for(let level=0;level<2;level++){const y=h+.3+level*3.3;block(g,s*w*.36,y+1,front-2.3,3.6,2.5,3.6,C.mosaicColors?ceramic(C.wall):C.wall);arch(g,s*w*.36,y+.1,front-.43,1.4,2);roof(g,4.5-level*.4,4.1-level*.4,y+2.4,1.4,front-2.3,o.roofColor||C.sage,{curl:.8,x:s*w*.36});}
    }
    for(let i=0;i<3;i++)block(g,0,.12+i*.12,front+.2+(2-i)*.36,5.4,.24+i*.24,.65,C.cream);
  });
  register('pagoda_tower',(o,g)=>{
    const [w,d]=o.footprint,levels=o.levels||7,step=o.storeyHeight||4.1;
    block(g,0,.24,0,w,.48,d,C.stone);
    const tiers=new THREE.Group();tiers.name='pagoda-tower-levels';g.add(tiers);
    for(let k=0;k<levels;k++){
      const level=new THREE.Group();tiers.add(level);const scale=1-k*.085,tw=w*.7*scale,td=d*.7*scale,y=.5+k*step;
      block(level,0,y+1.45,0,tw,2.9,td,ceramic(C.wall));
      for(let face=0;face<4;face++){const fg=new THREE.Group();fg.rotation.y=face*Math.PI/2;level.add(fg);arch(fg,0,y+.14,td/2+.02,tw*.42,2.6);rail(fg,tw+.5,td/2+.35,y+.48);mosaic(fg,[[-tw*.38,y+.1,td/2+.06,tw*.18,2.6],[tw*.38,y+.1,td/2+.06,tw*.18,2.6],[0,y+2.6,td/2+.06,tw-.3,.25]],.18);flatten(level,fg);}
      if(k>0)roof(level,tw+1.1,td+1.1,y+2.9,1.65,0,C.sage,{curl:.85*scale,overhang:.6,ornament:false});
    }
    roof(g,w,d,3,1.9,0,C.sage,{curl:1.1});
    for(const x of [-w*.38,0,w*.38])column(g,x,d*.39,2.9,.25);
    finial(g,0,.5+(levels-1)*step+4.6,0,3);
  });
  register('pagoda_annex',(o,g)=>{
    const [w,d]=o.footprint,h=o.height||5;
    if(o.outline){const shape=new THREE.Shape();o.outline.forEach(([x,z],i)=>i?shape.lineTo(x,-z):shape.moveTo(x,-z));shape.closePath();for(const [height,base,c] of [[.36,0,C.stone],[h,.36,C.mosaicColors?ceramic(C.cream):C.cream]]){const geo=new THREE.ExtrudeGeometry(shape,{depth:height,bevelEnabled:false});geo.rotateX(-Math.PI/2);geo.translate(0,base,0);add(g,geo,c);}}
    else{block(g,0,.18,0,w,.36,d,C.stone);block(g,0,h/2+.3,0,w-.3,h,d-.3,C.mosaicColors?ceramic(C.cream):C.cream);}
    if(o.wings)for(const wing of o.wings){const wg=new THREE.Group();wg.position.set(wing.position[0],0,wing.position[1]);wg.rotation.y=(wing.rotation||0)*Math.PI/180;g.add(wg);roof(wg,...wing.size,wing.eave||h+.2,wing.rise||2.4,0,o.roofColor||C.sage,{curl:.35,overhang:o.roofOverhang??.3});}
    else{for(let x=-w/2+1.5;x<w/2;x+=3){arch(g,x,.4,d/2-.07,1.5,h*.63);column(g,x+1,d/2+.07,h*.9,.17);}roof(g,w,d,h+.2,2.4,0,o.roofColor||C.sage,{curl:.35,overhang:o.roofOverhang??.3});}
    if(o.outline){const area=o.outline.reduce((sum,[x,z],i)=>{const b=o.outline[(i+1)%o.outline.length];return sum+x*b[1]-b[0]*z;},0);
      for(let i=0;i<o.outline.length;i++){const [ax,az]=o.outline[i],[bx,bz]=o.outline[(i+1)%o.outline.length],dx=bx-ax,dz=bz-az,len=Math.hypot(dx,dz);if(len<4)continue;const nx=(area>0?dz:-dz)/len,nz=(area>0?-dx:dx)/len;
        const face=new THREE.Group();face.position.set((ax+bx)/2+nx*.03,0,(az+bz)/2+nz*.03);face.rotation.y=Math.atan2(nx,nz);g.add(face);
        const count=Math.max(1,Math.floor(len/3.2));for(let k=0;k<count;k++)arch(face,(k-(count-1)/2)*3.0,h>5?1.25:.45,0,1.15,h>5?2.2:2.5);flatten(g,face);
      }
    }
    if(o.screen){const s=o.screen,sg=new THREE.Group();sg.position.set(...s.position);g.add(sg);const sw=s.width,sh=s.height,b=s.base||0,depth=s.depth||3;
      block(sg,0,b+sh/2,0,sw,sh,depth,C.mosaicColors?ceramic(C.wall):C.wall);block(sg,0,b+sh/2,depth/2+.03,sw-1.05,sh-1,.08,C.dark);
      mosaic(sg,[[-sw/2+.3,b+.3,depth/2+.07,.6,sh-.6],[sw/2-.3,b+.3,depth/2+.07,.6,sh-.6],[0,b+sh-.65,depth/2+.07,sw-.8,.5]]);
      roof(sg,sw+.5,depth+.5,b+sh,1.2,0,C.rose,{curl:.6});
    }
    if(o.bridge){const b=o.bridge,[ax,ay,az]=b.start,[bx,by,bz]=b.end,n=b.steps||15,width=b.width||2.2;
      for(let k=0;k<n;k++){const t=(k+.5)/n,x=ax+(bx-ax)*t,z=az+(bz-az)*t,y=ay+(by-ay)*(k+1)/n;block(g,x,y-.15,z,Math.abs(bx-ax)/n+.03,.3,width,C.stone);for(const s of [-1,1])block(g,x,y+.45,z+s*width/2,.06,.9,.06,C.cream);}
      for(const s of [-1,1])tube(g,[[ax,ay+.9,az+s*width/2],[bx,by+.9,bz+s*width/2]],.075,C.cream);
      for(const [x,y,z] of [b.start,b.end])for(const s of [-1,1])block(g,x,y/2,z+s*(width/2-.2),.28,y,.28,C.stone);
    }
    if(o.roofStatue){const s=o.roofStatue,sg=new THREE.Group();sg.position.set(...s.position);g.add(sg);const h=s.height||4;
      block(sg,0,-.125,0,h*.65,.65,h*.55,C.stone);
      const seat=add(sg,new THREE.SphereGeometry(1,12,8),C.sage);seat.scale.set(h*.35,h*.12,h*.24);seat.position.y=h*.13;
      const robe=add(sg,new THREE.ConeGeometry(h*.22,h*.58,10),C.gold);robe.position.y=h*.43;
      const head=add(sg,new THREE.SphereGeometry(h*.09,12,8),C.cream);head.position.y=h*.8;finial(sg,0,h*.87,0,h*.24);
      const halo=add(sg,new THREE.TorusGeometry(h*.32,.035,4,28),C.line);halo.position.set(0,h*.72,-.3);
      tube(sg,[[-h*.14,h*.64,.1],[-h*.24,h*.45,.3],[0,h*.38,.4]],.13,C.gold);tube(sg,[[h*.14,h*.64,.1],[h*.22,h*.53,.3],[.1,h*.42,.4]],.13,C.gold);
    }
  });
  register('pagoda_dragon',(o,g)=>{
    const curve=new THREE.CatmullRomCurve3(o.points.map(p=>new THREE.Vector3(...p))),r=o.radius||.75;
    const radiusAt=t=>THREE.MathUtils.lerp(r,o.tailRadius??r,THREE.MathUtils.smoothstep(t,.67,1));
    const body=new THREE.TubeGeometry(curve,160,r,14,false),positions=body.attributes.position;
    for(let i=0;i<=160;i++){
      const p=curve.getPointAt(i/160),factor=radiusAt(i/160)/r;
      for(let j=0;j<=14;j++){const k=i*15+j;positions.setXYZ(k,p.x+(positions.getX(k)-p.x)*factor,p.y+(positions.getY(k)-p.y)*factor,p.z+(positions.getZ(k)-p.z)*factor);}
    }
    body.computeVertexNormals();add(g,body,ceramic(o.bodyColor||'#ada391'));
    const frames=curve.computeFrenetFrames(189,false),scales=[],spines=[];
    const colors=o.mosaicColors||['#bdb5a4','#acb3a1','#b6aa91'],relief=o.scaleRelief??.045,crest=o.crestHeight??.36;
    for(let k=0;k<190;k++){
      const p=curve.getPointAt(k/189),t=frames.tangents[k],a=Math.atan2(t.x,t.z);
      for(let j=0;j<24;j++){
        const theta=(j+(k%2)*.5)*Math.PI/12,normal=frames.normals[k].clone().multiplyScalar(Math.cos(theta)).addScaledVector(frames.binormals[k],Math.sin(theta));
        const v=normal.clone().multiplyScalar(radiusAt(k/189)+relief*.4).add(p),euler=new THREE.Euler().setFromQuaternion(new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0,0,1),normal));
        const seed=Math.sin((k*24+j+1)*12.9898)*43758.5453,index=C.mosaicColors?Math.floor((seed-Math.floor(seed))*colors.length):(j+k)%colors.length;
        scales.push({p:v.toArray(),s:[.28,.22,relief],r:[euler.x,euler.y,euler.z],c:colors[index]});
      }
      if(k%7===0)spines.push({p:[p.x,p.y+radiusAt(k/189)+crest*.35,p.z],s:[.18,crest,.22],r:[0,a,0]});
    }
    instances(g,new THREE.IcosahedronGeometry(1,0),scales,'pagoda-dragon-scales','#ffffff');
    instances(g,new THREE.ConeGeometry(1,1,4),spines,'pagoda-dragon-crest',C.edge);
    const p=curve.getPoint(0),head=new THREE.Group();head.position.copy(p);head.scale.setScalar(o.headScale??1);g.add(head);
    const profile=[[-3.4,1.7],[-2.7,2.3],[-1.2,2.1],[-.5,3.5],[1.1,3.2],[1.9,1.4],[1.2,-1.2],[.5,-2],[-.7,-1.4],[-.3,.5],[-2.6,.7]],shape=new THREE.Shape();profile.forEach(([x,y],i)=>i?shape.lineTo(x,y):shape.moveTo(x,y));shape.closePath();
    const geo=new THREE.ExtrudeGeometry(shape,{depth:.8,bevelEnabled:true,bevelSize:.1,bevelThickness:.07,bevelSegments:1});geo.translate(0,0,-.4);const mask=add(head,geo,C.rose);mask.name='pagoda-dragon-head-relief';
    const inlays=[];
    for(let x=-3.1;x<1.7;x+=.24)for(let y=-1.8;y<3.4;y+=.24){let inside=false;for(let i=0,j=profile.length-1;i<profile.length;j=i++){const [ax,ay]=profile[i],[bx,by]=profile[j];if((ay>y)!==(by>y)&&x<(bx-ax)*(y-ay)/(by-ay)+ax)inside=!inside;}if(inside)for(const side of [-1,1])inlays.push({p:[x,y,side*.49],s:[.12,.1,.035],r:[0,0,(x+y)*.3],c:[C.cream,C.gold,C.sage][inlays.length%3]});}
    instances(head,new THREE.BoxGeometry(1,1,1),inlays,'pagoda-dragon-head-inlays','#ffffff');
    for(const side of [-1,1]){
      const eye=add(head,new THREE.SphereGeometry(.21,10,6),C.dark);eye.position.set(-.7,1.75,side*.54);
      const ring=add(head,new THREE.TorusGeometry(.3,.065,5,18),C.cream);ring.position.set(-.7,1.75,side*.57);
      tube(head,[[.35,2.4,side*.4],[.9,3.8,side*.65],[.45,4.4,side*.8]],.09,C.edge);tube(head,[[-2.8,1.6,side*.3],[-3.6,2.8,side*.7],[-4.1,2.1,side*.8]],.055,C.dark);
      const scroll=[];for(let k=0;k<40;k++){const a=k*.22,r=.55*(1-k/50);scroll.push([.3+Math.cos(a)*r,.7+Math.sin(a)*r,side*.59]);}tube(head,scroll,.06,C.gold);
      for(let k=0;k<6;k++)tube(head,[[1.1,.8-k*.4,side*.4],[2.2+k*.1,.3-k*.55,side*.45],[2.6+k*.12,-.1-k*.57,side*.4]],.1,C.cream);
    }
    for(const foot of o.feet||[]){block(g,foot[0],.18,foot[1],1.2,.36,1.3,C.stone);tube(g,[[foot[0],.35,foot[1]],[foot[0]+.3,1.3,foot[1]],[foot[0]+1,1.8,foot[1]]],.24,C.rose);}
  });
  register('pagoda_guardian',(o,g)=>{
    const h=o.height||4.8;block(g,0,.25,0,1.7,.5,1.5,C.stone);
    const robe=add(g,new THREE.ConeGeometry(.65,h*.58,8),C.sage);robe.position.y=h*.38;
    const body=add(g,new THREE.SphereGeometry(.65,10,8),C.gold);body.scale.set(.8,1.1,.65);body.position.y=h*.62;
    const head=add(g,new THREE.SphereGeometry(.36,10,8),C.cream);head.position.y=h*.84;finial(g,0,h*.88,0,.6);
    const face=new THREE.Group();face.name='pagoda-guardian-face';g.add(face);block(face,0,h*.815,.35,.1,.2,.14,C.cream);for(const s of [-1,1])block(face,s*.13,h*.835,.365,.095,.035,.045,C.dark);block(face,0,h*.795,.32,.16,.035,.045,C.dark);
    const helmet=add(g,new THREE.SphereGeometry(.41,10,8,0,Math.PI*2,0,Math.PI/2),C.gold);helmet.position.y=h*.85;
    const cape=new THREE.Shape();cape.moveTo(-.5,h*.7);cape.quadraticCurveTo(-1.35,h*.5,-.95,.6);cape.lineTo(.9,.75);cape.quadraticCurveTo(.95,h*.5,.5,h*.7);cape.closePath();const cloak=add(g,new THREE.ExtrudeGeometry(cape,{depth:.16,bevelEnabled:false}),C.rose);cloak.position.z=-.4;
    block(g,0,h*.53,.08,1.15,.23,.76,C.gold);for(const s of [-1,1]){block(g,s*.3,.69,.17,.34,.44,.65,C.dark);const shoulder=add(g,new THREE.SphereGeometry(.34,8,6),C.edge);shoulder.position.set(s*.54,h*.65,.02);}
    tube(g,[[-.45,h*.65,0],[-.9,h*.5,.2],[-.65,h*.38,.3]],.17,C.gold);tube(g,[[.45,h*.65,0],[.85,h*.72,.2],[.8,h*.85,.1]],.17,C.gold);
    tube(g,[[.9,.4,0],[.9,h*1.08,0]],.055,C.dark);
  });
  register('pagoda_garden',(o,g)=>{
    const [w,d]=o.size;block(g,0,.08,0,w,.16,d,o.groundColor??'#b9c0aa');
    const shrubs=[],crowns=[],trunks=[];
    for(let x=-w/2+.7;x<w/2;x+=o.shrubSpacing||1.3)for(let z=-d/2+.6;z<d/2;z+=o.shrubSpacing||1.3){const q=Math.sin(x*11+z*23);shrubs.push({p:[x+q*.22,.4+q*.07,z+Math.cos(x*7+z*3)*.2],s:[.72,.27,.65],r:[0,q,0],c:(o.shrubColors??['#a7b397','#96a486'])[q>0?0:1]});}
    for(const [cx,cz,ch] of o.trees||[])for(let j=0;j<(o.treesPerCluster||1);j++){const a=j*2.4+cx*.1,x=cx+(j?Math.cos(a)*1.7:0),z=cz+(j?Math.sin(a)*1.7:0),h=ch*(1-j*.12),r=o.crownRadius||3;
      trunks.push({p:[x,h/2,z],s:[.13,h,.13]});for(let k=0;k<5;k++)crowns.push({p:[x+Math.sin(k*2.4)*.6,h*(.74+k*.057),z+Math.cos(k*2)*.5],s:[r-k*.3,.4,r*.9-k*.26],r:[0,k*.4,0]});
    }
    instances(g,new THREE.IcosahedronGeometry(1,1),shrubs,'pagoda-sage-shrubs','#ffffff');instances(g,new THREE.CylinderGeometry(1,1,1,6),trunks,'pagoda-tree-trunks',o.trunkColor??'#938778');instances(g,new THREE.IcosahedronGeometry(1,1),crowns,'pagoda-sage-crowns',o.crownColor??'#98a58c');
  });
  register('pagoda_bus',(o,g)=>{
    const [w,h,d]=o.size||[2.6,3.2,10.5];block(g,0,.3,0,w*.86,.6,d*.82,C.dark);block(g,0,h*.49,0,w,h*.69,d,o.color||'#a69689');block(g,0,h*.84,0,w*.96,.5,d*.97,C.cream);
    for(const s of [-1,1]){block(g,s*(w/2+.01),h*.65,0,.04,h*.27,d*.87,o.windowColor??'#87968f');for(let z=-d*.38;z<d*.4;z+=1.1)block(g,s*(w/2+.04),h*.65,z,.07,h*.29,.07,C.cream);for(const z of [-d*.3,d*.3]){const m=add(g,new THREE.CylinderGeometry(.48,.48,.22,10),C.dark);m.rotation.z=Math.PI/2;m.position.set(s*w*.47,.48,z);}}
    block(g,0,h*.63,d/2+.015,w*.8,h*.38,.06,o.windowColor??'#87968f');
  });
  // Family builders are additive: the ceramic Linh Phuoc builders above stay unchanged.
  const familyColors={wall:'#d1bc87',roof:'#9a8065',wood:'#69564a',trim:'#b7aa8c',stone:'#c5bfb0'};
  function familyRoof(g,w,d,eave,settings={},colors=familyColors){
    const start=scene.children.length;
    vietnameseRoof({position:[0,0,0],width:w,depth:d,eaveHeight:eave,ridgeHeight:eave+(settings.rise??2),overhang:settings.overhang??.7,cornerLift:settings.curl??.7,curve:settings.curve??.15,thickness:settings.thickness??.14,ridgeOrnament:settings.ornament??true,color:colors.roof,trimColor:colors.trim,tileSpacing:settings.tileSpacing??.45});
    const parts=scene.children.slice(start);for(const part of parts){
      g.add(part);
      if(settings.soffit){const wide=Math.max(w,d),deep=Math.min(w,d),soffit=block(part,0,eave-.11,0,wide+.25,.13,deep+.25,colors.wood);soffit.name='pagoda-timber-soffit';}
    }return parts[0];
  }
  function familyColumn(g,x,z,h,r,base,c){
    const shaft=add(g,new THREE.CylinderGeometry(r*.9,r,h-base,12),c.wood);shaft.position.set(x,(h+base)/2,z);
    block(g,x,base/2,z,r*2.8,base,r*2.8,c.stone);
    block(g,x,h-.16,z,r*3,.28,r*3,c.wood);
  }
  function openingTrim(g,x,z,width,height,base,c){
    block(g,x,base+height/2,z,width,height,.08,c.wood);
    for(const s of [-1,1])block(g,x+s*(width/2+.08),base+height/2,z+.04,.12,height+.12,.10,c.trim);
    block(g,x,base+height+.05,z,width+.3,.13,.12,c.wood);
    for(let i=1;i<5;i++)block(g,x-width/2+i*width/5,base+height*.82,z+.07,.035,height*.32,.035,c.trim);
  }
  function familySign(g,text,w,h,y,z,c){
    sign(g,text,w,y,z);const m=g.children[g.children.length-1];m.scale.y=h/.85;
    const canvas=m.material.map.image,ctx=canvas.getContext('2d');ctx.fillStyle=c.wood;ctx.fillRect(0,0,1024,128);ctx.fillStyle=c.trim;
    ctx.font='bold 76px Georgia';ctx.textAlign='center';let f=76;while(ctx.measureText(text).width>990&&f>3)ctx.font=`bold ${--f}px Georgia`;ctx.fillText(text,512,91);m.material.map.needsUpdate=true;
  }
  register('pagoda_building',(o,g)=>{
    const [w,d]=o.footprint??[14,9],h=o.height??5,base=o.plinth??.42,c={...familyColors,...o.colors},form=o.form??'hall',r=o.columnRadius??.18,rs=o.roof??{},veranda=o.veranda??1.7;
    const foundation=block(g,0,base/2,0,w,base,d,c.stone);foundation.name='pagoda-foundation';
    if(o.facade?.style==='stone'){
      stoneHall(o,g,w,d,h,base,c,rs);
    }else if(form==='gate'){
      const piers=[[-w*.48,w*.04],[-w*.163,w*.065],[w*.163,w*.065],[w*.48,w*.04]];
      for(const [x,pw] of piers){block(g,x,(h+base)/2,0,pw,h-base,d*.62,c.wall);block(g,x,(h+base)/2,d*.32,pw*.44,h-base,.07,c.wood);}
      for(const x of [-w*.325,0,w*.325]){
        const ow=w*(x===0?.26:.25),oh=h*(x===0?.86:.67),radius=ow/2,spring=Math.max(base+.9,oh-radius),shape=new THREE.Shape();
        shape.moveTo(-ow/2,h);shape.lineTo(ow/2,h);shape.lineTo(ow/2,spring);
        for(let i=0;i<=28;i++){const a=i*Math.PI/28;shape.lineTo(Math.cos(a)*radius,spring+Math.sin(a)*radius);}shape.closePath();
        const spandrel=add(g,new THREE.ExtrudeGeometry(shape,{depth:d*.62,bevelEnabled:false}),c.wall);spandrel.position.set(x,0,-d*.31);
        const pts=[];for(let i=0;i<=28;i++){const a=i*Math.PI/28;pts.push([x+Math.cos(a)*radius,spring+Math.sin(a)*radius,d*.315]);}tube(g,pts,.075,c.trim);
      }
      familyRoof(g,w,d,h,rs,c);
      if((rs.tiers??2)>1){block(g,0,h+.6,0,w*.39,1.2,d*.68,c.wood);familyRoof(g,w*.47,d*.92,h+1.15,{...rs,rise:(rs.rise??1.3)*.8},c);}
      if(o.sign){
        const sw=o.signWidth??w*.39,sh=o.signHeight??h*.085,sy=h*.925,sz=d/2+(rs.overhang??.7)+.04;
        familySign(g,o.sign,sw,sh,sy,sz,c);
        for(const x of [-sw*.4,sw*.4])block(g,x,(h+sy+sh/2)/2,sz,.035,h-sy-sh/2,.035,c.wood);
      }
    }else if(form==='pavilion'||form==='tower'){
      const levels=form==='tower'?(o.levels??3):1,step=o.storeyHeight??(h+(rs.rise??1.7)+1.2),taper=o.taper??.88;
      if(form==='tower'&&levels>1){
        const core=o.core??{},smallest=taper**(levels-1),[cw,cd]=core.size??[w*smallest*.28,d*smallest*.28],[cx,cz]=core.offset??[0,-d*smallest*.28],top=(levels-1)*step+base;
        const support=block(g,cx,(top+base)/2,cz,cw,top-base,cd,core.color??c.wall);support.name='pagoda-tower-core';
      }
      for(let k=0;k<levels;k++){
        const scale=taper**k,tw=w*scale,td=d*scale,y=k*step,level=new THREE.Group();level.position.y=y;g.add(level);
        if(k)block(level,0,base/2,0,tw,base,td,c.stone);
        for(const x of [-1,1])for(const z of [-1,1])familyColumn(level,x*(tw/2-.35),z*(td/2-.35),h,r,base,c);
        for(const z of [-1,1])block(level,0,h-.15,z*(td/2-.35),tw,.28,r*2.2,c.wood);
        for(const x of [-1,1])block(level,x*(tw/2-.35),h-.15,0,r*2.2,.28,td,c.wood);
        const tiers=form==='tower'?1:(rs.tiers??1);
        for(let j=0;j<tiers;j++){
          const shrink=(rs.shrink??.72)**j,yroof=h+j*(rs.gap??1.25);
          if(j)block(level,0,yroof-.4,0,tw*shrink*.85,.8,td*shrink*.85,c.wood);
          familyRoof(level,tw*shrink,td*shrink,yroof,{...rs,rise:(rs.rise??1.7)*shrink},c);
        }
        if(o.railing){for(const z of [-1,1])rail(level,tw-.8,z*(td/2-.3),base+.85);}
        if(o.bell&&k===0){
          const bh=o.bell.height??1.5,br=o.bell.radius??.55,bottom=base+(h-base-bh)*.44;
          const bell=add(level,new THREE.LatheGeometry([[br*1.12,0],[br,.1],[br*.78,bh*.35],[br*.7,bh*.8],[br*.28,bh],[0,bh]].map(p=>new THREE.Vector2(...p)),20),o.bell.color??'#958767');bell.position.y=bottom;bell.name='pagoda-bell';
          block(level,0,(bottom+bh+h)/2,0,.06,h-bottom-bh,.06,c.wood);
          const lip=add(level,new THREE.TorusGeometry(br*1.06,.045,5,24),c.trim);lip.rotation.x=Math.PI/2;lip.position.y=bottom+.04;
        }
      }
    }else{
      const wallZ=-veranda/2,wallD=d-veranda;
      block(g,0,base+(h-base)/2,wallZ,w-.5,h-base,wallD-.3,c.wall);
      const bays=o.bays??5,spacing=(w-1.5)/bays,doorH=o.doorHeight??h*.63;
      for(let i=0;i<bays;i++){
        const x=(i-(bays-1)/2)*spacing;
        openingTrim(g,x,d/2-veranda+.03,spacing*.64,doorH,base,c);
        if(o.openingStyle==='arched'){
          const rise=o.lintelRise??.35,ww=spacing*.7,y=base+doorH,z=d/2-veranda+.15,s=new THREE.Shape();
          s.moveTo(-ww/2,0);s.quadraticCurveTo(-ww*.25,rise*.15,0,rise);s.quadraticCurveTo(ww*.25,rise*.15,ww/2,0);s.lineTo(ww/2,-.16);s.lineTo(-ww/2,-.16);s.closePath();
          const lintel=add(g,new THREE.ExtrudeGeometry(s,{depth:.07,bevelEnabled:false,curveSegments:12}),c.wood);lintel.position.set(x,y,z);lintel.name='pagoda-carved-lintel';
          tube(g,[[x-ww*.43,y+.02,z+.09],[x-ww*.2,y+rise*.28,z+.09],[x,y+rise*.72,z+.09],[x+ww*.2,y+rise*.28,z+.09],[x+ww*.43,y+.02,z+.09]],.018,c.trim);
        }
        if(i!==Math.floor(bays/2))block(g,x,base+doorH*.48,d/2-veranda+.12,spacing*.52,doorH*.82,.08,c.wood);
      }
      for(let i=0;i<=bays;i++)familyColumn(g,-(w-1.2)/2+i*(w-1.2)/bays,d/2-.32,h,r,base,c);
      block(g,0,h-.16,d/2-.32,w-.6,.3,.3,c.wood);
      if(o.lanterns){
        const group=new THREE.Group();group.name='pagoda-hanging-lanterns';g.add(group);
        const count=o.lanterns.count??bays,lh=o.lanterns.height??.45,lw=o.lanterns.width??.22;
        for(let i=0;i<count;i++){
          const lantern=new THREE.Group();lantern.position.set((i-(count-1)/2)*(w-2)/count,h-.6,d/2-.55);group.add(lantern);
          block(lantern,0,.32,0,.025,.64,.025,c.wood);
          const body=add(lantern,new THREE.CylinderGeometry(lw*.65,lw*.65,lh,6),c.trim);body.position.y=-lh/2;
          for(const y of [0,-lh])block(lantern,0,y,0,lw*1.5,.055,lw*1.3,c.wood);
          for(const x of [-1,1])for(const z of [-1,1])block(lantern,x*lw*.54,-lh/2,z*lw*.47,.025,lh,.025,c.wood);
        }
      }
      for(const s of [-1,1])for(let i=0;i<3;i++){
        const side=new THREE.Group();side.rotation.y=s*Math.PI/2;g.add(side);
        openingTrim(side,(i-1)*(wallD-1)/3,w/2-.23,Math.min(1.2,wallD*.16),h*.37,base+h*.27,c);
      }
      const tiers=rs.tiers??2;
      for(let j=0;j<tiers;j++){
        const shrink=(rs.shrink??.88)**j,depthShrink=(rs.depthShrink??.64)**j,eave=h+j*(rs.gap??1.7);
        if(j){block(g,0,eave-.55,-veranda*.15,w*shrink*.93,1.1,d*depthShrink*.90,c.wall);for(let x=-w*shrink*.4;x<w*shrink*.45;x+=1.2)block(g,x,eave-.5,d*depthShrink*.45+.01,.7,.55,.04,c.wood);}
        familyRoof(g,w*shrink,d*depthShrink,eave,{...rs,rise:(rs.rise??2)*shrink},c);
      }
      if(o.sign)sign(g,o.sign,w*.45,h-.65,d/2-.12);
    }
  });
  function flatShape(g,w,d,shape,y,c){
    const s=new THREE.Shape();
    if(shape==='ellipse')s.absellipse(0,0,w/2,d/2,0,Math.PI*2,false,0);
    else{ s.moveTo(-w/2,-d/2);s.lineTo(w/2,-d/2);s.lineTo(w/2,d/2);s.lineTo(-w/2,d/2);s.closePath(); }
    const geo=new THREE.ShapeGeometry(s,48);geo.rotateX(-Math.PI/2);geo.translate(0,y,0);return add(g,geo,c);
  }
  register('pagoda_path',(o,g)=>{
    const points=o.points??[[-4,0],[4,0]],w=o.width??3.4,y=o.surfaceY??.10,left=[],right=[],joints=[];
    for(let i=0;i<points.length;i++){
      const p=new THREE.Vector2(...points[i]),prev=new THREE.Vector2(...points[Math.max(0,i-1)]),next=new THREE.Vector2(...points[Math.min(points.length-1,i+1)]);
      const a=p.clone().sub(prev).normalize(),b=next.clone().sub(p).normalize();if(!i)a.copy(b);if(i===points.length-1)b.copy(a);
      const n=new THREE.Vector2(-a.y-b.y,a.x+b.x).normalize(),factor=w/2/Math.max(.35,n.dot(new THREE.Vector2(-a.y,a.x)));
      left.push([p.x+n.x*factor,p.y+n.y*factor]);right.push([p.x-n.x*factor,p.y-n.y*factor]);
      if(i){const len=p.distanceTo(prev),direction=p.clone().sub(prev).normalize(),normal=new THREE.Vector2(-direction.y,direction.x);
        for(let t=.5;t<len;t+=o.grid??1.2){const q=prev.clone().addScaledVector(direction,t);joints.push(q.x+normal.x*w*.49,y+.005,q.y+normal.y*w*.49,q.x-normal.x*w*.49,y+.005,q.y-normal.y*w*.49);}}
    }
    const shape=new THREE.Shape([...left,...right.reverse()].map(([x,z])=>new THREE.Vector2(x,-z))),geo=new THREE.ExtrudeGeometry(shape,{depth:y,bevelEnabled:false});geo.rotateX(-Math.PI/2);
    geo.setIndex(Array.from({length:geo.attributes.position.count},(_,i)=>i));
    const m=add(g,geo,o.color??'#c8c7b8');m.name='pagoda-paving';g.updateWorldMatrix(true,true);walkableGeometries.push(geo.clone().applyMatrix4(m.matrixWorld));
    lines(g,joints,o.jointColor??'#a8aa9c');
  });
  let foamShrub;
  function familyShrubGeometry(){
    if(foamShrub)return foamShrub;
    const a=new THREE.SphereGeometry(1,10,6),b=a.clone();a.scale(.72,.85,.78);a.translate(-.25,0,0);b.scale(.60,.75,.62);b.translate(.35,-.10,.08);
    foamShrub=mergeGeometries([a,b]);a.dispose();b.dispose();return foamShrub;
  }
  register('pagoda_landscape',(o,g)=>{
    const [w,d]=o.size??[10,8],shape=o.shape??'rectangle',density=o.density??.55,shrubs=[],flowers=[],trunks=[],crowns=[[],[],[],[]],spacing=o.spacing??1.4;
    flatShape(g,w,d,shape,.025,o.groundColor??'#bcc2ab');
    const random=n=>{const t=Math.sin(n*127.1+o.position[0]*13+o.position[2]*7)*43758.5453;return t-Math.floor(t);};let k=0;
    for(let x=-w/2+.6;x<w/2-.4;x+=spacing)for(let z=-d/2+.6;z<d/2-.4;z+=spacing){
      const scale=.65+random(k+11)*.55,sy=.23+random(k+5)*.18;
      k++;if(random(k)>density)continue;
      const margin=scale+.05;if(w<=margin*2||d<=margin*2)continue;
      const px=THREE.MathUtils.clamp(x+(random(k+3)-.5)*spacing*.7,-w/2+margin,w/2-margin),pz=THREE.MathUtils.clamp(z+(random(k+7)-.5)*spacing*.7,-d/2+margin,d/2-margin);
      if(shape==='ellipse'&&Math.hypot(px/(w/2),pz/(d/2))+margin/Math.min(w/2,d/2)>1)continue;
      if(o.clearings?.some(([cx,cz,cw,cd])=>Math.abs(px-cx)<cw/2+margin&&Math.abs(pz-cz)<cd/2+margin))continue;
      shrubs.push({p:[px,.04+sy,pz],s:[scale,sy,scale*.8],r:[0,k*2.4,0],c:(o.shrubColors??['#a6b299','#94a58b','#b2bda1'])[k%3]});
      if(random(k+14)<(o.flowers??.2))for(let j=0;j<5;j++)flowers.push({p:[px+Math.sin(j*2.4)*scale*.5,.06+sy*1.8,pz+Math.cos(j*2.4)*scale*.45],s:[.12,.07,.12],c:(o.flowerColors??['#baa5a2','#d6cdb0','#a8b9b9'])[j%3]});
    }
    instances(g,familyShrubGeometry(),shrubs,'pagoda-low-planting','#ffffff');
    instances(g,new THREE.IcosahedronGeometry(1,0),flowers,'pagoda-small-flowers','#ffffff');
    if(o.surface==='needles'){
      const needles=[];for(let i=0;i<(o.needleCount??Math.round(w*d*3));i++){
        const x=(random(i+310)-.5)*w,z=(random(i+911)-.5)*d;
        if(shape==='ellipse'&&Math.hypot(x/(w/2),z/(d/2))>1)continue;
        if(o.clearings?.some(([cx,cz,cw,cd])=>Math.abs(x-cx)<cw/2&&Math.abs(z-cz)<cd/2))continue;
        needles.push({p:[x,.033,z],s:[.012,.004,.14+random(i+710)*.16],r:[0,random(i+420)*Math.PI,0],c:['#a89b81','#b9aa8e','#c1b69a'][i%3]});
      }instances(g,new THREE.BoxGeometry(1,1,1),needles,'pagoda-pine-needles','#ffffff');
    }
    for(const [x,z,h] of o.trees??[]){
      trunks.push({p:[x,h/2,z],s:[.13,h,.13]});
      const levels=[[.71,.14,-.055],[.77,.19,.06],[.80,.14,-.08],[.86,.21,.04],[.90,.16,-.03],[.94,.15,.05],[.96,.095,0]];
      levels.forEach(([e,spread,offset],i)=>{const a=i*2.4+x*.17+z*.11,r=h*spread*(1+.16*Math.sin(a));crowns[i%4].push({p:[x+Math.sin(a)*h*.05+offset*h,h*(e+.011*Math.sin(a)),z+Math.cos(a)*h*.075],s:[r,r*(.25+.05*Math.cos(a)),r*(.78+.16*Math.cos(a))],r:[0,a,0],c:(o.treeColors??['#87977f','#94a48c','#a3b098'])[i%3]});});
    }
    instances(g,new THREE.CylinderGeometry(.4,1,1,8),trunks,'pagoda-pine-trunks',o.trunkColor??'#8e8372');
    crowns.forEach((items,i)=>instances(g,foliageGeometries[i],items,'pagoda-foam-crowns','#ffffff'));
    if(o.border){const y=.12,c=o.borderColor??C.stone;if(shape==='ellipse'){const p=[];for(let i=0;i<=64;i++)p.push([Math.cos(i*Math.PI/32)*w/2,y,Math.sin(i*Math.PI/32)*d/2]);tube(g,p,.09,c,true);}else for(const s of [-1,1]){block(g,0,y,s*d/2,w,.24,.16,c);block(g,s*w/2,y,0,.16,.24,d,c);}}
  });
  register('pagoda_stairs',(o,g)=>{
    const n=o.steps??5,rise=o.rise??.15,run=o.run??.35,w=o.width??5;
    for(let i=0;i<n;i++){const top=(i+1)*rise,z=(n/2-i-.5)*run,m=block(g,0,top/2,z,w,top,run+.003,o.color??C.stone);g.updateWorldMatrix(true,true);walkableGeometries.push(m.geometry.clone().applyMatrix4(m.matrixWorld));}
    if(o.rail)for(const s of [-1,1]){
      for(let i=0;i<n;i+=2)block(g,s*(w/2-.15),(i+1)*rise+.42,(n/2-i-.5)*run,.10,.84,.10,o.railColor??C.cream);
      tube(g,[[s*(w/2-.15),rise+.85,(n/2-.5)*run],[s*(w/2-.15),n*rise+.85,(-n/2+.5)*run]],.065,o.railColor??C.cream);
    }
    if(o.dragon)dragonRails(g,o.dragon,w,n,rise,run);
  });
  register('pagoda_stupa',(o,g)=>{
    const r=o.radius??2,h=o.height??7,c=o.color??C.gold,tiers=o.tiers??5;
    block(g,0,h*.04,0,r*2.3,h*.08,r*2.3,o.baseColor??C.stone);
    if((o.kind??'dome')==='dome'){
      const dome=add(g,new THREE.SphereGeometry(r,24,12,0,Math.PI*2,0,Math.PI/2),c);dome.position.y=h*.08;dome.scale.y=h*.42/r;
      block(g,0,h*.58,0,r*.7,h*.24,r*.7,c);
    }else for(let i=0;i<tiers;i++){
      const sr=r*(1-i/(tiers+1)),y=h*.08+i*h*.62/tiers;
      const drum=add(g,new THREE.CylinderGeometry(sr*.78,sr,h*.62/tiers,8),c);drum.position.y=y+h*.31/tiers;
    }
    const tip=add(g,new THREE.ConeGeometry(r*.35,h*.30,16),c);tip.position.y=h*.85;
    for(let i=0;i<5;i++){const ring=add(g,new THREE.TorusGeometry(r*(.31-i*.05),.035,4,20),C.trim??C.cream);ring.rotation.x=Math.PI/2;ring.position.y=h*(.72+i*.047);}
  });
  register('pagoda_statue',(o,g)=>{
    const h=o.height??3,base=o.baseHeight??.4,c=o.color??C.cream,standing=(o.pose??'seated')==='standing';
    block(g,0,base/2,0,h*.55,base,h*.45,o.baseColor??C.stone);
    const lotus=add(g,new THREE.CylinderGeometry(h*.25,h*.31,h*.10,16),c);lotus.position.y=base+h*.05;
    const bodyHeight=h*(standing?.64:.42),bodyY=base+h*.10+bodyHeight/2;
    const robe=add(g,new THREE.ConeGeometry(h*(standing?.18:.28),bodyHeight,16),c);robe.position.y=bodyY;
    if(!standing){const knees=add(g,new THREE.SphereGeometry(1,16,8),c);knees.scale.set(h*.30,h*.12,h*.19);knees.position.set(0,base+h*.18,.05);
      const neck=add(g,new THREE.CylinderGeometry(h*.045,h*.07,h*.15,12),c);neck.position.y=base+h*.55;}
    const headY=base+h*(standing?.83:.64),head=add(g,new THREE.SphereGeometry(h*.09,16,10),c);head.position.y=headY;
    const cap=add(g,new THREE.SphereGeometry(h*.092,12,8,0,Math.PI*2,0,Math.PI/2),o.hairColor??C.dark);cap.position.y=headY+h*.025;
    for(const s of [-1,1]){block(g,s*h*.033,headY+h*.005,h*.083,h*.022,h*.009,h*.009,C.line);tube(g,[[s*h*.12,bodyY+bodyHeight*.3,0],[s*h*.22,bodyY,.12],[s*h*.05,bodyY-bodyHeight*.2,h*.17]],h*.04,c);}
    if(o.halo){const halo=add(g,new THREE.TorusGeometry(h*.22,.025,5,36),o.haloColor??C.gold);halo.position.set(0,headY,-h*.09);}
  });
  register('pagoda_water',(o,g)=>{
    const [w,d]=o.size??[12,8],shape=o.shape??'ellipse';flatShape(g,w,d,shape,.01,o.bankColor??'#adaf9c');flatShape(g,w-.4,d-.4,shape,.025,o.color??'#9fbbb4');
    const rocks=[],n=o.stones??24;for(let i=0;i<n;i++){const a=i*Math.PI*2/n;rocks.push({p:[Math.cos(a)*w/2,.18,Math.sin(a)*d/2],s:[.35+(i%3)*.08,.18,.3],r:[0,a,0]});}
    instances(g,new THREE.IcosahedronGeometry(1,1),rocks,'pagoda-shore-stones',o.stoneColor??C.stone);
    const ripples=[];for(let k=1;k<4;k++)for(let i=0;i<64;i++){const a=i*Math.PI/32,b=(i+1)*Math.PI/32; ripples.push(Math.cos(a)*w*k/12,.031,Math.sin(a)*d*k/12,Math.cos(b)*w*k/12,.031,Math.sin(b)*d*k/12);}lines(g,ripples,'#c7d0c0');
  });
  register('pagoda_furniture',(o,g)=>{
    const [w,h,d]=o.size??[1.8,1.5,1.4],c=o.color??'#948d78',kind=o.kind??'incense';
    if(kind==='bench'){
      for(const s of [-1,1])block(g,s*w*.33,h*.24,0,.16,h*.48,d*.8,o.baseColor??C.stone);
      block(g,0,h*.52,0,w,h*.12,d,c);block(g,0,h*.83,-d*.37,w,h*.34,.10,c);
    }else{
      block(g,0,.06,0,w*.95,.12,d*.95,o.baseColor??C.stone);
      for(const x of [-1,1])for(const z of [-1,1])block(g,x*w*.28,h*.22,z*d*.27,.13,h*.36,.13,c);
      const bowl=add(g,new THREE.LatheGeometry([[w*.22,h*.32],[w*.37,h*.45],[w*.45,h*.72],[w*.43,h*.78]].map(p=>new THREE.Vector2(...p)),24),c);bowl.scale.z=d/w;
      const top=add(g,new THREE.CylinderGeometry(w*.41,w*.41,.04,24),C.stone);top.scale.z=d/w;top.position.y=h*.75;
      for(const s of [-1,1])tube(g,[[s*w*.37,h*.62,0],[s*w*.63,h*.67,0],[s*w*.57,h*.95,0]],.06,c);
      for(let i=0;i<3;i++)block(g,(i-1)*.14,h*.88,0,.025,h*.25,.025,C.gold);
    }
    if(o.standHeight){
      for(const child of g.children)child.position.y+=o.standHeight;
      const stand=block(g,0,o.standHeight/2,0,w*1.12,o.standHeight,d*1.12,o.baseColor??C.stone);stand.name='pagoda-urn-stand';
      block(g,0,o.standHeight-.04,0,w*1.24,.08,d*1.24,o.baseColor??C.stone);
      for(const s of [-1,1])block(g,s*w*.44,o.standHeight/2,d*.568,.035,o.standHeight*.7,.025,c);
    }
  });

  // Sculpture coordinates are normalized to a one-metre figure, excluding its pedestal.
  function oval(g,x,y,z,sx,sy,sz,c){const m=add(g,new THREE.SphereGeometry(1,20,14),c);m.position.set(x,y,z);m.scale.set(sx,sy,sz);return m;}
  function lathe(g,profile,c){return add(g,new THREE.LatheGeometry(profile.map(p=>new THREE.Vector2(...p)),40),c);}
  function lotusBase(g,r,h,c){
    const drum=lathe(g,[[0,0],[r*.88,0],[r,h*.17],[r*.92,h*.48],[r*.81,h*.7],[r*.85,h],[0,h]],c);drum.name='icon-lotus';
    const petals=[];for(let row=0;row<2;row++)for(let i=0;i<20;i++){
      const a=(i+row*.5)*Math.PI/10;petals.push({p:[Math.sin(a)*r*.82,h*(.45+row*.30),Math.cos(a)*r*.82],s:[r*.16,h*.25,r*.13],r:[Math.cos(a)*.35,a,-Math.sin(a)*.35]});
    }instances(g,new THREE.SphereGeometry(1,10,6),petals,'icon-lotus-petals',c);
  }
  function sculptFace(g,y,c,kind){
    const face=new THREE.Group();face.name='icon-face';g.add(face);
    oval(face,0,y,.008,.052,.073,.048,c);
    for(const s of [-1,1]){
      oval(face,s*.052,y-.004,.003,.012,.029,.012,c);
      tube(face,[[s*.009,y+.011,.052],[s*.022,y+.014,.050],[s*.034,y+.009,.044]],.0022,C.line);
      tube(face,[[s*.009,y+.022,.047],[s*.024,y+.025,.045],[s*.035,y+.019,.040]],.002,c);
    }
    oval(face,0,y-.006,.057,.007,.015,.01,c);
    tube(face,[[-.019,y-.034,.043],[0,y-(kind==='maitreya'?.044:.035),.050],[.019,y-.034,.043]],.0025,C.rose);
    if(kind==='maitreya')oval(face,0,y-.042,.045,.022,.007,.003,C.line);
    return face;
  }
  function foldedRobe(g,profile,c,foldCount=30){
    const geo=new THREE.LatheGeometry(profile.map(p=>new THREE.Vector2(...p)),Math.max(96,foldCount*12)),pos=geo.attributes.position;
    for(let i=0;i<pos.count;i++){
      const x=pos.getX(i),z=pos.getZ(i),y=pos.getY(i),a=Math.atan2(x,z),r=Math.hypot(x,z),fold=.009*Math.cos(a*foldCount+y*2.7)*Math.min(1,r/.07);
      pos.setXYZ(i,x+Math.sin(a)*fold,y,z+Math.cos(a)*fold);
    }geo.computeVertexNormals();const robe=add(g,geo,c);robe.name='icon-folded-robe';
    const folds=new THREE.Group();folds.name='icon-robe-folds';g.add(folds);
    for(let i=0;i<foldCount;i++){
      const a=(i+.5)*Math.PI*2/foldCount,points=[],outline=profile.slice(1,-1).filter(p=>p[1]<.76);
      for(let j=1;j<outline.length;j++)for(let k=0;k<=8;k++){
        if(j>1&&k===0)continue;const t=k/8,[r0,y0]=outline[j-1],[r1,y1]=outline[j];
        const r=r0+(r1-r0)*t,y=y0+(y1-y0)*t,angle=a-y*2.7/foldCount,surface=r-.009*Math.min(1,r/.07)+.003;
        points.push([Math.sin(angle)*surface,y,Math.cos(angle)*surface]);
      }
      if(points.length>2)tube(folds,points,.0013,C.stone);
    }
  }
  function iconFigure(o,g){
    const kind=o.kind??'quan_am',h=o.height??3,base=o.baseHeight??.4,c=o.color??C.cream,bc=o.baseColor??C.stone;
    const seated=['buddha','maitreya'].includes(kind),radius=seated?.36:.19,baseW=o.baseWidth??h*radius*2.5,steps=o.baseSteps??3;
    for(let i=0;i<steps;i++){const t=i/steps;block(g,0,base*(i+.5)/steps,0,baseW*(1-t*.18),base/steps,baseW*(o.baseDepthRatio??.8)*(1-t*.18),bc);}
    const sg=new THREE.Group();sg.position.y=base;sg.scale.setScalar(h);g.add(sg);
    lotusBase(sg,radius,.075,c);
    if(!seated){
      foldedRobe(sg,kind==='guardian'?[[0,.32],[.15,.32],[.13,.44],[.12,.55],[.14,.70],[.08,.77],[.031,.81]]:[[0,.065],[.151,.065],[.146,.13],[.115,.32],[.095,.52],[.112,.69],[.085,.78],[.031,.81]],c,o.folds??30);
      if(kind==='guardian'&&o.robePanelColor){
        const robe=sg.getObjectByName('icon-folded-robe'),p=robe.geometry.attributes.position,colors=[];
        for(let i=0;i<p.count;i++){
          const y=p.getY(i),front=p.getZ(i)>0&&Math.abs(p.getX(i))<.105;
          const color=new THREE.Color(front&&y>=.52&&y<=.71?o.robePanelColor:(front&&y>=.43&&y<.52?(o.accentColor??c):c));colors.push(...color.toArray());
        }
        robe.geometry.setAttribute('color',new THREE.Float32BufferAttribute(colors,3));robe.material=paint('#ffffff').clone();robe.material.vertexColors=true;
      }
      const y=.862;sculptFace(sg,y,c,kind);
      const neck=lathe(sg,[[.026,.77],[.028,.81],[.027,.82]],c);
      if(kind==='guardian'){
        for(const s of [-1,1]){
          oval(sg,s*.091,.70,0,.068,.045,.07,o.armorColor??C.gold);
          block(sg,s*.065,.27,.02,.065,.34,.08,c);
          oval(sg,s*.065,.105,.034,.045,.04,.065,o.armorColor??C.gold);
          tube(sg,[[s*.09,.72,.01],[s*.15,.59,.04],[s*.17,.65,.09]],.032,c);
        }
        const chest=oval(sg,0,.65,.055,.095,.12,.025,o.armorColor??C.gold);chest.name='icon-armour';
        block(sg,0,.48,.02,.26,.045,.15,o.accentColor??o.armorColor??C.gold);
        for(let i=0;i<6;i++)tube(sg,[[-.078,.56+i*.025,.066],[0,.54+i*.025,.086],[.078,.56+i*.025,.066]],.004,o.trimColor??C.stone);
        const staff=tube(sg,[[.18,.08,.09],[.18,.95,.09]],.008,o.staffColor??C.gold);staff.name='icon-staff';
        const blade=add(sg,new THREE.ConeGeometry(.025,.14,3),o.staffColor??C.gold);blade.position.set(.18,.94,.09);
        const helmet=lathe(sg,[[.052,.88],[.067,.91],[.042,.96],[0,1]],o.armorColor??C.gold);helmet.name='icon-helmet';
      }else{
        // Veil surrounds the cheeks and connects into a shoulder mantle, never a detached ball cap.
        const veil=add(sg,new THREE.SphereGeometry(1,28,18,Math.PI/2+.65,Math.PI*2-1.3,0,Math.PI*.78),c);veil.position.set(0,.861,-.008);veil.scale.set(.068,.102,.063);veil.name='icon-open-veil';
        for(const s of [-1,1]){
          tube(sg,[[s*.055,.93,-.004],[s*.071,.84,.005],[s*.10,.75,.011],[s*.13,.62,-.01],[s*.12,.40,-.015],[s*.15,.12,-.025]],.012,c);
          tube(sg,[[s*.055,.78,.06],[s*.082,.67,.085],[s*.077,.52,.095],[s*.04,.32,.13],[s*.08,.09,.125]],.004,C.stone);
        }
        const crown=lathe(sg,[[.043,.922],[.052,.941],[.032,.962],[.025,.984],[0,1]],c);crown.name='icon-crown';
        oval(sg,0,.956,.035,.014,.021,.009,o.crownColor??c);
        tube(sg,[[-.093,.746,.03],[-.14,.68,.04],[-.14,.61,.11],[-.088,.60,.13]],.031,c);
        tube(sg,[[.096,.748,.022],[.144,.687,.04],[.153,.72,.08],[.135,.803,.087]],.028,c);
        const hand=oval(sg,.133,.823,.089,.017,.035,.012,c);hand.name='icon-raised-hand';hand.rotation.z=.12;
        for(let i=0;i<4;i++)tube(sg,[[.122+i*.007,.831,.098],[.12+i*.007,.86-Math.abs(i-1.5)*.004,.099]],.0026,c);
        oval(sg,-.073,.602,.137,.023,.012,.013,c);
        const vase=lathe(sg,[[.012,0],[.019,.01],[.017,.037],[.009,.054],[.012,.061]],o.vaseColor??c);vase.position.set(-.063,.53,.145);
      }
    }else{
      // Distinct crossed thighs, feet, upright torso, bent arms and a connected neck.
      for(const s of [-1,1]){
        const thigh=oval(sg,s*.14,.15,.06,.21,.085,.14,c);thigh.rotation.z=s*.12;
        const foot=oval(sg,s*.10,.17,.18,.12,.038,.052,c);foot.rotation.y=s*.36;
      }
      if(kind==='maitreya'){
        foldedRobe(sg,[[.23,.14],[.20,.26],[.16,.47],[.095,.66],[.032,.70]],c,22);
        const belly=oval(sg,0,.38,.115,.20,.205,.14,c);belly.name='icon-belly';
        oval(sg,0,.34,.252,.011,.009,.004,C.stone);
        sculptFace(sg,.79,c,kind);lathe(sg,[[.04,.64],[.04,.74]],c);
        oval(sg,0,.83,-.005,.059,.057,.054,c);
        for(const s of [-1,1])tube(sg,[[s*.13,.60,.02],[s*.25,.39,.04],[s*.22,.24,.16]],.047,c);
        const beads=[];for(let i=0;i<19;i++){const a=i*Math.PI/18;beads.push({p:[Math.cos(a)*.15,.56-Math.sin(a)*.19,.20],s:[.014,.014,.014]});}instances(sg,new THREE.SphereGeometry(1,8,6),beads,'icon-prayer-beads',o.beadColor??C.stone);
        // A large round head is characteristic here, but never substitutes for belly or limbs.
        sg.scale.y*=1/.89;
      }else{
        foldedRobe(sg,[[.24,.16],[.18,.30],[.135,.50],[.16,.68],[.09,.77],[.033,.79]],c,28);
        lathe(sg,[[.033,.76],[.031,.82]],c);sculptFace(sg,.865,c,kind);
        const cap=add(sg,new THREE.SphereGeometry(.055,24,14,0,Math.PI*2,0,Math.PI*.56),o.hairColor??c);cap.position.set(0,.885,0);
        oval(sg,0,.96,0,.025,.04,.026,o.hairColor??c);
        for(const s of [-1,1])tube(sg,[[s*.125,.70,.015],[s*.21,.48,.045],[s*.12,.32,.17],[s*.026,.33,.20]],.037,c);
        for(let k=0;k<7;k++)tube(sg,[[-.26+k*.014,.16,.13],[-.15+k*.018,.24,.17],[.02+k*.02,.19,.19]],.0025,C.stone);
      }
    }
    if(o.halo){const halo=add(sg,new THREE.TorusGeometry(o.haloRadius??(kind==='maitreya'?.10:.14),.0035,6,64),o.haloColor??C.gold);halo.position.set(0,kind==='maitreya'?.78:(seated?.84:.86),-.075);halo.name='icon-halo';}
  }
  register('pagoda_icon',iconFigure);
  register('pagoda_statue_row',(o,g)=>{
    const prototype=new THREE.Group(),envelope=currentEnvelope;
    try{currentEnvelope=null;iconFigure({...o,height:o.height??2.5,baseHeight:o.baseHeight??.3},prototype);}finally{currentEnvelope=envelope;}
    compact(prototype);prototype.updateMatrixWorld(true);
    const placements=o.placements??Array.from({length:o.count??8},(_,i)=>[(i-((o.count??8)-1)/2)*(o.spacing??3),0,0]);
    prototype.traverse(m=>{
      if(!m.isMesh||m.isInstancedMesh)return;
      const geometry=m.geometry.clone().applyMatrix4(m.matrixWorld);
      const row=instances(g,geometry,placements.map(p=>({p})),`pagoda-row-${m.name||'sculpture'}`,m.material.color.getStyle());
      if(row&&m.material.vertexColors)row.material=m.material.clone();
    });
    // Lotus petals in the prototype are already instanced; replicate their baked transforms.
    prototype.traverse(m=>{if(!m.isInstancedMesh)return;const matrix=new THREE.Matrix4(),items=[];for(const p of placements)for(let i=0;i<m.count;i++){m.getMatrixAt(i,matrix);matrix.premultiply(m.matrixWorld);const v=new THREE.Vector3(),q=new THREE.Quaternion(),s=new THREE.Vector3();matrix.decompose(v,q,s);const e=new THREE.Euler().setFromQuaternion(q);items.push({p:v.add(new THREE.Vector3(...p)).toArray(),s:s.toArray(),r:[e.x,e.y,e.z]});}instances(g,m.geometry,items,'pagoda-row-lotus',m.material.color.getStyle());});
  });

  function dragonRails(g,settings,w,n,rise,run){
    const group=new THREE.Group();group.name='pagoda-dragon-balustrades';g.add(group);
    const supports=new THREE.Group();supports.name='pagoda-dragon-rail-supports';group.add(supports);
    const h=settings.height??.8,c=settings.color??C.gold,r=settings.radius??h*.13;
    for(const s of [-1,1]){
      const x=s*(w/2-r-.06),points=[];
      for(let i=0;i<=n*4;i++){const t=i/(n*4);points.push([x,(1+t*(n-1))*rise+h*.48+Math.sin(t*Math.PI*5)*h*.16,(n/2-.5-t*(n-1))*run]);}
      tube(group,points,r,c);
      for(let i=0;i<n;i++)block(supports,x,(i+1)*rise+h*.15,(n/2-i-.5)*run,r*2,h*.3,run,c);
      const z=(n/2-.5)*run,y=rise+h*.55,head=oval(group,x,y,z+h*.18,h*.22,h*.18,h*.32,c);head.name='pagoda-dragon-rail-head';
      oval(group,x,y+h*.02,z+h*.43,h*.18,h*.08,h*.2,c);
      for(const side of [-1,1]){
        oval(group,x+side*h*.19,y+h*.07,z+h*.26,h*.025,h*.028,h*.028,C.dark);
        tube(group,[[x+side*h*.11,y+h*.13,z+h*.09],[x+side*h*.17,y+h*.46,z-h*.03],[x+side*h*.25,y+h*.53,z-h*.14]],h*.025,c);
        tube(group,[[x+side*h*.1,y,z+h*.48],[x+side*h*.37,y+h*.13,z+h*.55],[x+side*h*.43,y+h*.29,z+h*.41]],h*.014,c);
      }
      for(let i=1;i<points.length-1;i+=2){const p=points[i];const crest=add(group,new THREE.ConeGeometry(r*.6,h*.16,4),c);crest.position.set(p[0],p[1]+r+h*.06,p[2]);}
    }
  }

  function goldCrest(roofGroup,w,d,h,rs,c){
    const group=new THREE.Group();group.name='pagoda-gold-crest';roofGroup.add(group);const y=h+(rs.rise??2);
    for(const s of [-1,1]){
      tube(group,[[s*w*.12,y+.02,0],[s*w*.24,y+.12,0],[s*w*.29,y+.55,0],[s*w*.23,y+.68,0],[s*w*.20,y+.41,0]],.05,c.trim);
      for(const z of [-1,1])tube(group,[[s*w*.46,h+.15,z*d*.43],[s*w*.52,h+.42,z*d*.50],[s*w*.55,h+.85,z*d*.51]],.04,c.trim);
    }
    const wheel=add(group,new THREE.TorusGeometry(.36,.055,6,28),c.trim);wheel.position.y=y+.37;
    for(let i=0;i<8;i++){const a=i*Math.PI/4;tube(group,[[0,y+.37,0],[Math.sin(a)*.34,y+.37+Math.cos(a)*.34,0]],.018,c.trim);}
  }
  function stoneHall(o,g,w,d,h,base,c,rs){
    const facade=o.facade??{},front=d/2-(o.veranda??.5),thickness=facade.wallThickness??.3;
    const fg=new THREE.Group();fg.name='pagoda-stone-facade';g.add(fg);hallFronts.set(o.id,fg);
    const shape=new THREE.Shape();shape.moveTo(-w/2,base);shape.lineTo(w/2,base);shape.lineTo(w/2,h);shape.lineTo(-w/2,h);shape.closePath();
    const doorW=o.doorWidth??2.5,doorH=o.doorHeight??h*.60;
    const hole=new THREE.Path();hole.moveTo(-doorW/2,base);hole.lineTo(-doorW/2,base+doorH);hole.lineTo(doorW/2,base+doorH);hole.lineTo(doorW/2,base);hole.closePath();shape.holes.push(hole);
    const windows=new THREE.Group();windows.name='pagoda-round-windows';fg.add(windows);
    for(const [x,y] of facade.roundWindows??[[-w*.32,h*.67],[w*.32,h*.67]]){
      const radius=facade.windowRadius??.55,path=new THREE.Path();path.absarc(x,y,radius,0,Math.PI*2,true);shape.holes.push(path);
      const wg=new THREE.Group();wg.position.set(x,y,front+.04);windows.add(wg);
      const rim=add(wg,new THREE.TorusGeometry(radius,.045,8,40),c.trim);
      const glass=add(wg,new THREE.CircleGeometry(radius-.025,40),C.dark);glass.position.z=-thickness*.7;
      for(let i=-2;i<=2;i++){const offset=i*radius*.28,len=Math.sqrt(radius*radius-offset*offset)*1.82;block(wg,offset,0,-.02,.018,len,.025,c.wood);}
    }
    const wall=add(fg,new THREE.ExtrudeGeometry(shape,{depth:thickness,bevelEnabled:false,curveSegments:32}),c.wall);wall.position.z=front-thickness;wall.name='pagoda-stone-block-wall';
    const joints=[],course=facade.courseHeight??.65,bw=facade.blockWidth??1.4;
    for(let y=base+course;y<h;y+=course){
      for(let x=-w/2;x<w/2;x+=.12){const middle=x+.06;const onDoor=Math.abs(middle)<doorW/2&&y<base+doorH,onWindow=(facade.roundWindows??[[-w*.32,h*.67],[w*.32,h*.67]]).some(([wx,wy])=>Math.hypot(middle-wx,y-wy)<(facade.windowRadius??.55)+.025);if(!onDoor&&!onWindow)joints.push(x,y,front+.008,Math.min(x+.12,w/2),y,front+.008);}
      for(let x=-w/2+(Math.round(y/course)%2)*bw/2;x<w/2;x+=bw){const mid=y-course/2;if(Math.abs(x)<doorW/2&&mid<base+doorH)continue;if((facade.roundWindows??[[-w*.32,h*.67],[w*.32,h*.67]]).some(([wx,wy])=>Math.hypot(x-wx,mid-wy)<(facade.windowRadius??.55)+course/2))continue;joints.push(x,y-course,front+.008,x,y,front+.008);}
    }lines(fg,joints,facade.jointColor??'#927f79');
    for(const s of [-1,1]){
      block(g,s*(w/2-thickness/2),(base+h)/2,-(o.veranda??.5)/2,thickness,h-base,d-(o.veranda??.5),c.wall);
      block(fg,s*(doorW/2+.1),base+doorH/2,front+.06,.16,doorH+.15,.10,c.trim);
      familyColumn(fg,s*(w/2-.5),front+.3,h,o.columnRadius??.18,base,c);
    }
    block(g,0,(h+base)/2,-d/2+thickness/2,w,h-base,thickness,c.wall);
    block(fg,0,base+doorH+.1,front+.06,doorW+.4,.18,.12,c.trim);
    const door=block(fg,0,base+doorH/2,front-.1,doorW,doorH,.12,facade.doorColor??c.wood);door.name='pagoda-entrance-door';
    if(o.sign)familySign(fg,o.sign,o.signWidth??w*.43,o.signHeight??.55,base+doorH+.55,front+.12,c);
    for(let i=0;i<(rs.tiers??2);i++){
      const shrink=(rs.shrink??.86)**i,deep=(rs.depthShrink??.60)**i,eave=h+i*(rs.gap??1.6),settings={...rs,rise:(rs.rise??1.5)*shrink};
      if(i){block(g,0,eave-.5,0,w*shrink*.9,1,d*deep*.92,c.wall);for(let x=-w*shrink*.42;x<w*shrink*.43;x+=1)block(g,x,eave-.45,d*deep/2,.55,.44,.05,c.wood);}
      const roof=familyRoof(g,w*shrink,d*deep,eave,settings,c);if(rs.crest)goldCrest(roof,w*shrink,d*deep,eave,settings,c);
    }
    for(const wing of o.wings??[]){
      const wg=new THREE.Group();wg.position.set(wing.position[0],0,wing.position[1]);wg.rotation.y=(wing.rotation??0)*Math.PI/180;g.add(wg);
      const [ww,wd]=wing.footprint??[10,8],wh=wing.height??3;
      block(wg,0,wh/2+base/2,0,ww,wh-base,wd,c.wall);block(wg,0,base/2,0,ww,base,wd,c.stone);
      familyRoof(wg,ww,wd,wh,{tiers:1,rise:wing.roofRise??1,curl:wing.curl??.35,ornament:false},c);
      if(wing.openings){
        const openings=new THREE.Group();openings.name='pagoda-wing-openings';wg.add(openings);
        for(const [x,ow,oh] of wing.openings){const recess=new THREE.Group();openings.add(recess);block(recess,x,base+oh/2,wd/2+.015,ow,oh,.035,C.dark);for(const s of [-1,1])block(recess,x+s*(ow/2+.05),base+oh/2,wd/2+.04,.08,oh+.08,.06,c.trim);}
      }
      if(wing.text){
        const tw=wing.textWidth??ww*.84,th=wing.textHeight??wh*.38,[tx,ty]=wing.textPosition??[0,wh*.55],canvas=document.createElement('canvas');
        canvas.width=Math.min(4096,Math.max(256,Math.round(256*tw/th)));canvas.height=256;
        const ctx=canvas.getContext('2d');ctx.clearRect(0,0,canvas.width,canvas.height);ctx.fillStyle=wing.textColor??C.dark;ctx.textAlign='center';ctx.textBaseline='middle';
        let font=208;ctx.font=`bold ${font}px "Noto Serif CJK SC", Georgia, serif`;while(ctx.measureText(wing.text).width>canvas.width*.94&&font>4)ctx.font=`bold ${--font}px "Noto Serif CJK SC", Georgia, serif`;ctx.fillText(wing.text,canvas.width/2,128);
        const texture=new THREE.CanvasTexture(canvas);texture.colorSpace=THREE.SRGBColorSpace;
        const inscription=new THREE.Mesh(new THREE.PlaneGeometry(tw,th),new THREE.MeshBasicMaterial({map:texture,transparent:true,depthWrite:false}));inscription.name='pagoda-wing-inscription';inscription.position.set(tx,ty,wd/2+.055);wg.add(inscription);
      }
    }
  }
  register('pagoda_gate',(o,g)=>{
    const [w,d]=o.footprint??[15,3],h=o.height??5,c={...familyColors,wall:o.style==='stone'?'#bcb9aa':'#ad8870',...o.colors},base=o.plinth??.08;
    const shape=new THREE.Shape();shape.moveTo(-w/2,base);shape.lineTo(w/2,base);shape.lineTo(w/2,h);shape.lineTo(-w/2,h);shape.closePath();
    for(const x of [-w*.325,0,w*.325]){
      const ww=w*(x===0?.265:.21),hh=h*(x===0?.88:.66),radius=ww/2,spring=hh-radius,path=new THREE.Path();
      path.moveTo(x-radius,base);path.lineTo(x-radius,spring);path.absarc(x,spring,radius,Math.PI,0,true);path.lineTo(x+radius,base);path.closePath();shape.holes.push(path);
      const pts=[[x-radius,base,d/2+.03],[x-radius,spring,d/2+.03]];for(let i=0;i<=32;i++){const a=Math.PI-i*Math.PI/32;pts.push([x+Math.cos(a)*radius,spring+Math.sin(a)*radius,d/2+.03]);}pts.push([x+radius,base,d/2+.03]);tube(g,pts,.065,c.trim);
    }
    const wall=add(g,new THREE.ExtrudeGeometry(shape,{depth:d,bevelEnabled:false,curveSegments:32}),c.wall);wall.position.z=-d/2;
    for(const y of [h*.96,h+ .12])block(g,0,y,0,w+.35,.18,d+.3,c.trim);
    for(const x of [-w*.47,-w*.17,w*.17,w*.47]){block(g,x,h/2, d/2+.08,.18,h,.18,c.trim);finial(g,x,h+.22,0,.55);}
    if(o.style==='stone'){
      familyRoof(g,w,d,h+.25,{rise:.65,curl:.55,ornament:false},{...c,roof:c.wall});
      block(g,0,h+1.25,0,w*.42,1.15,d*.75,c.wall);familyRoof(g,w*.48,d,h+1.8,{rise:.55,curl:.45,ornament:false},{...c,roof:c.wall});
    }else{
      for(const s of [-1,1])tube(g,[[s*w*.25,h+.28,0],[s*w*.35,h+.45,0],[s*w*.36,h+.86,0]],.08,c.trim);
    }
    if(o.sign)familySign(g,o.sign,o.signWidth??w*.45,o.signHeight??.45,h-.22,d/2+.14,{...c,wood:c.wall});
    if(o.walls){
      const walls=new THREE.Group();walls.name='pagoda-gate-walls';g.add(walls);const length=o.walls.length??10,wh=o.walls.height??2.2;
      for(const s of [-1,1]){
        block(walls,s*(w+length)/2,wh/2,0,length,wh,o.walls.depth??.7,c.wall);block(walls,s*(w+length)/2,wh,0,length+.08,.15,(o.walls.depth??.7)+.15,c.trim);
        for(let x=.35;x<length;x+=.65)block(walls,s*(w/2+x),wh*.78,(o.walls.depth??.7)/2+.02,.09,wh*.24,.08,c.trim);
      }
    }
  });

  registerInteriorKit('buddhist_altar',(hall,context)=>{
    const o=hall.interior,[w,outer,d]=hall.size??[hall.footprint[0],hall.height??5.5,hall.footprint[1]],floor=o.floor??.46,h=o.ceilingHeight??outer-.5;
    const c=o.goldColor??'#b6a076',red=o.redColor??'#92564e',wall=o.wallColor??'#c4b5a0',rotation=(o.rotation??hall.rotation??0)*Math.PI/180;
    const group=new THREE.Group();group.name='buddhist-altar-interior';group.position.set(...hall.position);group.rotation.y=rotation;
    block(group,0,floor-.05,0,w-.5,.1,d-.5,o.floorColor??'#b7b5a7');
    for(const s of [-1,1])block(group,s*(w/2-.32),floor+h/2,0,.18,h,d-.5,wall);
    block(group,0,floor+h/2,-d/2+.32,w-.5,h,.18,wall);
    const altarZ=o.altarZ??-d*.32;
    block(group,0,floor+h*.48,altarZ-.35,o.altarWidth??w*.64,h*.94,.16,red);
    for(const x of [-1,1])block(group,x*w*.32,floor+h*.48,altarZ-.23,.12,h*.96,.08,c);
    const statues=new THREE.Group();statues.name='buddhist-altar-statues';group.add(statues);
    const sh=o.statueHeight??2.7,spacing=o.statueSpacing??w*.19;
    for(let i=-1;i<=1;i++){
      const sg=new THREE.Group();sg.position.set(i*spacing,floor+(o.altarHeight??.6),altarZ+.12);statues.add(sg);
      iconFigure({kind:'quan_am',height:sh,baseHeight:.16,color:c,baseColor:c,halo:true,haloRadius:.145,haloColor:c},sg);
      block(group,i*spacing,floor+(o.altarHeight??.6)/2,altarZ+.10,sh*.65,o.altarHeight??.6,sh*.48,c);
    }
    const columns=new THREE.Group();columns.name='buddhist-red-columns';group.add(columns);
    for(const x of [-1,1])for(const z of [-d*.25,d*.23]){
      const shaft=add(columns,new THREE.CylinderGeometry(.20,.23,h,20),red);shaft.position.set(x*w*.34,floor+h/2,z);
      for(const y of [floor+.22,floor+h-.2]){const ring=add(columns,new THREE.CylinderGeometry(.26,.28,.16,20),c);ring.position.set(x*w*.34,y,z);}
      block(columns,x*w*.34,floor+.12,z,.58,.24,.58,C.stone);
    }
    const tableZ=altarZ+sh*.7;
    block(group,0,floor+.5,tableZ,o.offeringWidth??w*.47,1,.8,red);block(group,0,floor+1.02,tableZ,o.offeringWidth??w*.47,.12,.95,c);
    for(let i=-2;i<=2;i++){
      const x=i*w*.075;block(group,x,floor+.5,tableZ+.41,w*.064,.65,.035,c);
      if(i%2===0){const vase=lathe(group,[[.1,0],[.15,.12],[.10,.29],[.07,.4]],c);vase.position.set(x,floor+1.08,tableZ);oval(group,x,floor+1.6,tableZ,.24,.15,.21,'#b3a0a7');}
    }
    const ceiling=new THREE.Group();ceiling.name='buddhist-coffered-ceiling';ceiling.position.set(hall.position[0],hall.position[1]+floor+h,hall.position[2]);ceiling.rotation.y=rotation;
    const radius=o.domeRadius??Math.min(w,d)*.19,ceilingShape=new THREE.Shape();
    ceilingShape.moveTo(-w/2-.05,-d/2-.05);ceilingShape.lineTo(w/2+.05,-d/2-.05);ceilingShape.lineTo(w/2+.05,d/2+.05);ceilingShape.lineTo(-w/2-.05,d/2+.05);ceilingShape.closePath();
    const opening=new THREE.Path();opening.absarc(0,0,radius,0,Math.PI*2,true);ceilingShape.holes.push(opening);
    const ceilingGeometry=new THREE.ExtrudeGeometry(ceilingShape,{depth:.2,bevelEnabled:false,curveSegments:48});ceilingGeometry.rotateX(-Math.PI/2);add(ceiling,ceilingGeometry,o.ceilingColor??'#85775e');
    const coffers=[],rosettes=[],cell=o.cofferSize??.65;
    for(let x=-w/2+cell/2;x<w/2;x+=cell)for(let z=-d/2+cell/2;z<d/2;z+=cell){
      if(Math.hypot(x,z)<radius+cell*.65)continue;
      coffers.push({p:[x,-.025,z],s:[cell*.79,.04,cell*.79]});rosettes.push({p:[x,-.055,z],s:[cell*.13,.025,cell*.13],r:[Math.PI/2,0,0]});
    }
    instances(ceiling,new THREE.BoxGeometry(1,1,1),coffers,'buddhist-gold-coffers',c);
    instances(ceiling,new THREE.SphereGeometry(1,8,6),rosettes,'buddhist-coffer-rosettes','#d0c3a1');
    for(const x of [-w*.34,w*.34])block(ceiling,x,-.14,0,.22,.3,d,red);
    for(const z of [-d*.25,d*.23])block(ceiling,0,-.14,z,w,.3,.22,red);
    const dome=new THREE.Group();dome.name='buddhist-painted-dome';ceiling.add(dome);
    // Painted octagonal vault: geometry and canvas both scale from the same radius.
    const canvas=document.createElement('canvas');canvas.width=canvas.height=1024;const ctx=canvas.getContext('2d');ctx.fillStyle='#9baeb1';ctx.fillRect(0,0,1024,1024);
    for(let i=0;i<8;i++){
      const a=i*Math.PI/4,b=a+Math.PI/4;ctx.fillStyle=i%2?'#aab9bb':'#91a8b0';ctx.beginPath();ctx.moveTo(512,512);ctx.arc(512,512,500,a,b);ctx.closePath();ctx.fill();
      const x=512+Math.cos(a+Math.PI/8)*305,y=512+Math.sin(a+Math.PI/8)*305;ctx.save();ctx.translate(x,y);ctx.rotate(a+Math.PI*.625);ctx.fillStyle='#c2ab7d';ctx.beginPath();ctx.ellipse(0,10,26,64,0,0,Math.PI*2);ctx.fill();ctx.fillStyle='#d9cbb2';ctx.beginPath();ctx.arc(0,-58,20,0,Math.PI*2);ctx.fill();ctx.strokeStyle='#887e65';ctx.lineWidth=3;ctx.beginPath();ctx.arc(0,-57,29,0,Math.PI*2);ctx.stroke();ctx.restore();
    }
    const texture=new THREE.CanvasTexture(canvas);texture.colorSpace=THREE.SRGBColorSpace;
    const vault=new THREE.RingGeometry(0,radius,64,12),vp=vault.attributes.position;
    for(let i=0;i<vp.count;i++){const r=Math.hypot(vp.getX(i),vp.getY(i));vp.setZ(i,-.46*(1-(r/radius)**2));}vault.computeVertexNormals();
    const painting=new THREE.Mesh(vault,new THREE.MeshStandardMaterial({map:texture,roughness:1,side:THREE.DoubleSide}));painting.rotation.x=Math.PI/2;painting.position.y=-.18;dome.add(painting);
    for(const r of [radius,radius*.96,radius*.25]){const ring=add(dome,new THREE.TorusGeometry(r,.04,6,64),c);ring.rotation.x=Math.PI/2;ring.position.y=-.21+.46*(1-(r/radius)**2);if(r===radius*.25)ring.name='buddhist-dome-oculus';}
    for(let i=0;i<8;i++){const a=i*Math.PI/4,p=[];for(let j=0;j<=12;j++){const r=radius*(.25+.75*j/12);p.push([Math.sin(a)*r,-.20+.46*(1-(r/radius)**2),Math.cos(a)*r]);}tube(dome,p,.025,c);}
    compact(group);compact(ceiling);
    context.roof.updateWorldMatrix(true,false);ceiling.applyMatrix4(new THREE.Matrix4().copy(context.roof.matrixWorld).invert());
    const front=hallFronts.get(hall.id);
    front?.traverse(m=>{if(m.material){const original=m.material;m.material=original.clone();m.material.onBeforeCompile=original.onBeforeCompile;m.material.customProgramCacheKey=original.customProgramCacheKey;}});
    return {group,ceiling,front,door:front?.getObjectByName('pagoda-entrance-door')};
  });
  registerInteriorKit('quan_am_gallery',(hall,context)=>withColors(hall.interior?.palette,()=>{
    const settings=hall.interior,[w,outerHeight,d]=hall.size,h=settings.ceilingHeight??outerHeight,floor=settings.floor??.48;
    const orientation=(settings.rotation??hall.rotation??0)*Math.PI/180;
    const group=new THREE.Group();group.name='quan-am-interior';group.position.set(...hall.position);group.rotation.y=orientation;
    const gold=settings.goldColor||C.gold,blue=settings.runnerColor??'#415969',light=settings.statueDetailColor??'#ded6c1',wall=settings.wallColor??'#c5bfa9';
    block(group,0,floor-.04,0,w,.08,d,C.cream);
    // This inner shell is independent of the exterior's decorative masonry recesses.
    const wallMaterial=settings.wallMaterialColor??ceramic(wall);
    for(const s of [-1,1])block(group,s*(w/2-.1),floor+h/2,0,.2,h,d,wallMaterial);
    block(group,0,floor+h/2,-d/2+.1,w,h,.2,wallMaterial);
    for(const s of [-1,1])block(group,s*(w/4+1),floor+h/2,d/2-.1,w/2-2,h,.2,wallMaterial);
    block(group,0,floor+h-.65,d/2-.1,4,1.3,.2,wallMaterial);
    const runner=block(group,0,floor+.012,.5,settings.runnerWidth,.024,d-1.2,blue);runner.name='quan-am-blue-runner';
    for(const s of [-1,1])block(group,s*(settings.runnerWidth/2-.06),floor+.027,.5,.035,.006,d-1.2,settings.runnerTrimColor??'#b7ac88');
    function statue(parent,height,name){
      const sg=new THREE.Group();sg.name=name;parent.add(sg);const scale=height/7.25;sg.scale.setScalar(scale);
      const profile=[[1.03,.42],[1.12,.6],[.87,1.15],[.62,3.5],[.67,4.65],[.47,5.25],[.23,5.45]];
      const robe=new THREE.LatheGeometry(profile.map(p=>new THREE.Vector2(...p)),20);
      add(sg,robe,gold);
      const lotus=add(sg,new THREE.CylinderGeometry(1.08,1.25,.4,18),gold);lotus.position.y=.2;
      const head=add(sg,new THREE.SphereGeometry(.35,16,12),light);head.scale.set(.82,1.25,.82);head.position.set(0,5.87,.03);
      const veil=add(sg,new THREE.SphereGeometry(.43,16,10,Math.PI,Math.PI,0,Math.PI*.8),gold);veil.position.set(0,5.99,-.08);veil.scale.y=1.25;
      finial(sg,0,6.4,-.08,.85);
      for(const s of [-1,1]){
        tube(sg,[[s*.5,4.95,.1],[s*.87,4.2,.18],[s*.42,3.9,.52]],.19,gold);
        const hand=add(sg,new THREE.SphereGeometry(.16,10,8),light);hand.scale.set(.8,1.4,.65);hand.position.set(s*.32,4.08,.65);
        tube(sg,[[s*.04,5.9,.32],[s*.13,5.92,.33],[s*.22,5.9,.30]],.019,C.line);
      }
      block(sg,0,5.76,.356,.055,.15,.055,light);tube(sg,[[-.08,5.62,.32],[0,5.6,.34],[.08,5.62,.32]],.014,C.rose);
      const radius=y=>{const i=profile.findIndex(p=>p[1]>=y),a=profile[i-1],b=profile[i];return THREE.MathUtils.lerp(a[0],b[0],(y-a[1])/(b[1]-a[1]));};
      const folds=[];for(let k=0;k<17;k++){const a=(k-8)*.09;for(let j=0;j<20;j++)for(const y of [.65+j*.23,.65+(j+1)*.23]){const r=radius(y)+.012;folds.push(Math.sin(a)*r,y,Math.cos(a)*r);}}
      const robeLines=lines(sg,folds,settings.robeLineColor??'#82795f');robeLines.name='quan-am-robe-linework';robeLines.material.opacity=.65;
      const petals=[];for(let k=0;k<18;k++){const a=k*Math.PI/9;petals.push({p:[Math.cos(a)*1.06,.39,Math.sin(a)*1.06],s:[.22,.17,.12],r:[0,-a,0]});}
      instances(sg,new THREE.SphereGeometry(1,8,5),petals,'quan-am-lotus-petals',light);
      return sg;
    }
    const focal=statue(group,settings.statueHeight,'quan-am-focal-statue');focal.position.set(0,floor,-d/2+2.7);
    const halo=new THREE.Shape();halo.moveTo(0,7.5);halo.bezierCurveTo(3,6.5,2.1,2.5,1,0);halo.quadraticCurveTo(0,-.35,-1,0);halo.bezierCurveTo(-2.1,2.5,-3,6.5,0,7.5);
    const aureole=add(group,new THREE.ExtrudeGeometry(halo,{depth:.08,bevelEnabled:false,curveSegments:24}),settings.haloMaterialColor??ceramic(settings.haloColor??'#c7b78d'));aureole.position.set(0,floor+.2,-d/2+2.28);
    const edge=halo.getPoints(70).map(p=>[p.x,p.y+floor+.2,-d/2+2.41]);tube(group,edge,.035,C.gold,true);
    const rows=new THREE.Group();rows.name='quan-am-side-statues';group.add(rows);
    for(const s of [-1,1])for(let k=0;k<settings.sideCount;k++){
      const z=-d/2+1.65+k*(d-4.5)/(settings.sideCount-1),x=s*(w/2-1.35);
      const sg=statue(rows,settings.sideStatueHeight,'quan-am-wall-statue');sg.position.set(x,floor+.3,z);sg.rotation.y=-s*Math.PI/2;
      flatten(rows,sg);
      block(group,x,floor+.15,z,1.5,.3,1.35,C.gold);
    }
    for(const s of [-1,1]){
      for(const y of [4.2,6.1,7.5]){block(group,s*(w/2-.48),floor+y,0,.65,.14,d-.5,settings.beamColor??C.gold);mosaic(group,[[s*(w/2-.7),floor+y-.42,0,.3,.3]]);}
      for(const z of [-5.3,-1.2,2.9])column(group,s*(w/2-2.35),z,h-.3,.22,settings.columnColor,settings.columnReliefColor??C.edge);
    }
    // Keep offerings behind the runner's end, away from the entrance camera.
    const table=new THREE.Group();table.name='quan-am-offering-table';table.position.set(0,floor,-d/2+4.1);group.add(table);
    const tableHeight=settings.offeringHeight??1.05,tableWidth=settings.offeringWidth??2.1;
    block(table,0,tableHeight/2,0,tableWidth,tableHeight,.75,settings.woodColor??'#947d64');
    block(table,0,tableHeight,0,tableWidth+.16,.12,.9,C.gold);
    block(table,0,.05,0,tableWidth+.12,.1,.85,C.gold);
    const panel=block(table,0,tableHeight*.5,.3975,tableWidth-.25,tableHeight*.62,.03,settings.woodPanelColor??'#a3947b');panel.name='quan-am-offering-panel';
    for(const s of [-1,1]){block(table,s*(tableWidth/2-.09),tableHeight*.5,.423,.045,tableHeight-.18,.045,C.gold);block(table,0,tableHeight*.5+s*(tableHeight/2-.09),.423,tableWidth-.16,.045,.045,C.gold);}
    tube(table,[[0,tableHeight*.3,.43],[.17,tableHeight*.5,.43],[0,tableHeight*.7,.43],[-.17,tableHeight*.5,.43]],.016,light,true);
    const vesselProfile=[[.11,0],[.15,.08],[.17,.18],[.08,.3],[.1,.36]].map(p=>new THREE.Vector2(...p));
    for(const s of [-1,1]){
      const vase=add(table,new THREE.LatheGeometry(vesselProfile,16),light);vase.position.set(s*tableWidth*.35,tableHeight+.06,0);
      for(const y of [.08,.26]){const band=add(table,new THREE.TorusGeometry(y===.08?.15:.104,.012,4,16),C.gold);band.rotation.x=Math.PI/2;band.position.set(s*tableWidth*.35,tableHeight+.06+y,0);}
    }
    const bowl=add(table,new THREE.CylinderGeometry(.2,.12,.18,16),C.gold);bowl.position.set(0,tableHeight+.15,.05);
    const ceiling=new THREE.Group();ceiling.name='quan-am-ceiling';ceiling.position.set(hall.position[0],hall.position[1]+floor+h,hall.position[2]);ceiling.rotation.y=orientation;
    block(ceiling,0,0,0,w+.5,.16,d+.6,settings.ceilingColor);
    for(const s of [-1,1])for(const z of [-5.4,-1.9,1.6,5.1]){
      const strip=block(ceiling,s*2.5,-.095,z,1.45,.035,2.1,settings.ceilingPanelColor??'#dadfda');strip.material=paint(settings.ceilingPanelColor??'#dadfda').clone();strip.material.emissive.set(settings.ceilingLightColor??'#c2d0ca');strip.material.emissiveIntensity=.22;
    }
    for(const z of [-6,-2,2,6]){block(ceiling,0,-.25,z,w,.3,.16,settings.beamColor??C.gold);tube(ceiling,[[-w/2,-.3,z],[0,-1.1,z],[w/2,-.3,z]],.07,C.line);}
    compact(group);compact(ceiling);
    context.roof.updateWorldMatrix(true,false);ceiling.applyMatrix4(new THREE.Matrix4().copy(context.roof.matrixWorld).invert());
    const front=hallFronts.get(hall.id);front.traverse(m=>{if(m.material){const original=m.material;m.material=original.clone();m.material.onBeforeCompile=original.onBeforeCompile;m.material.customProgramCacheKey=original.customProgramCacheKey;}});
    return {group,ceiling,front,door:front.getObjectByName('pagoda-entrance-door')};
  }));
})();
