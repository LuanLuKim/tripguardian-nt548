// Reusable lodging massing, landscaped grounds and a sealed lounge interior.
(() => {
  const C={wall:'#e6e1d4',trim:'#f2ecdd',roof:'#777b70',glass:'#82968e',wood:'#6d5c49',sage:'#a4b291',stone:'#c7c5b7',flower:'#b696a0'};
  const cube=new THREE.BoxGeometry(1,1,1),leaf=new THREE.SphereGeometry(1,8,5);
  let batches=new Map();
  function group(parent,name,position=[0,0,0],rotation=0) {
    const g=new THREE.Group();g.name=name;g.position.fromArray(position);g.rotation.y=rotation;parent.add(g);return g;
  }
  function add(parent,geometry,color,position=[0,0,0],scale=[1,1,1],rotation=0) {
    const matrix=new THREE.Matrix4().compose(new THREE.Vector3(...position),new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,1,0),rotation),new THREE.Vector3(...scale));
    if(!batches.has(parent))batches.set(parent,new Map());
    const bucket=batches.get(parent);if(!bucket.has(color))bucket.set(color,[]);
    bucket.get(color).push(geometry.clone().applyMatrix4(matrix));
  }
  function block(g,x,y,z,w,h,d,color){if(w>0&&h>0&&d>0)add(g,cube,color,[x,y,z],[w,h,d]);}
  function flush() {
    for(const [parent,colors] of batches)for(const [color,parts] of colors) {
      const geometry=mergeGeometries(parts.map(g=>g.index?g.toNonIndexed():g),false);
      const m=mesh(geometry,color,0,0,0,false);m.name=parent.name+'-mesh';parent.add(m);
      for(const part of parts)part.dispose();
      for(let ancestor=parent;ancestor;ancestor=ancestor.parent)if(ancestor.userData.front){m.material=m.material.clone();break;}
    }
    batches=new Map();
  }
  function instances(parent,name,geometry,entries,color) {
    if(!entries.length)return;
    const m=new THREE.InstancedMesh(geometry,material(color),entries.length),dummy=new THREE.Object3D();m.name=name;parent.add(m);m.castShadow=true;m.receiveShadow=true;
    entries.forEach((e,i)=>{dummy.position.fromArray(e.p);dummy.scale.fromArray(e.s||[1,1,1]);dummy.rotation.set(0,e.r||0,0);dummy.updateMatrix();m.setMatrixAt(i,dummy.matrix);if(e.c)m.setColorAt(i,new THREE.Color(e.c));});
    m.instanceMatrix.needsUpdate=true;m.computeBoundingBox();parent.updateWorldMatrix(true,false);
    if(currentEnvelope)for(const x of [m.boundingBox.min.x,m.boundingBox.max.x])for(const y of [m.boundingBox.min.y,m.boundingBox.max.y])for(const z of [m.boundingBox.min.z,m.boundingBox.max.z])currentEnvelope.push(new THREE.Vector3(x,y,z).applyMatrix4(parent.matrixWorld));
    return m;
  }
  function root(object,suffix) {return group(scene,object.id+'-'+suffix,object.position||[0,hillSurfaceHeight(0,0),0],object.rotation||0);}
  function slab(outline,height) {
    const shape=new THREE.Shape(outline.map(([x,z])=>new THREE.Vector2(x,-z)));
    const g=new THREE.ExtrudeGeometry(shape,{depth:height,bevelEnabled:false});g.rotateX(-Math.PI/2);return g;
  }
  function arch(width,height,thickness=.16,depth=.2) {
    const r=width/2,spring=height-r,s=new THREE.Shape();
    s.moveTo(-r,0);s.lineTo(-r,spring);s.absarc(0,spring,r,Math.PI,0,true);s.lineTo(r,0);s.lineTo(r-thickness,0);s.lineTo(r-thickness,spring);
    s.absarc(0,spring,r-thickness,0,Math.PI,false);s.lineTo(-r+thickness,0);s.closePath();
    return new THREE.ExtrudeGeometry(s,{depth,bevelEnabled:false,curveSegments:16});
  }
  function windowBay(g,x,y,z,w,h,shutters,trim,glass,arched=false) {
    block(g,x,y+h/2,z,w+.16,h+.16,.12,trim);
    block(g,x,y+h/2,z+.08,w,h,.08,glass);
    for(const dx of [-w/2,0,w/2])block(g,x+dx,y+h/2,z+.14,.055,h+.06,.07,trim);
    for(const dy of [0,h*.5,h])block(g,x,y+dy,z+.14,w+.10,.055,.07,trim);
    block(g,x,y-.10,z+.1,w+.35,.14,.36,trim);
    if(shutters)for(const side of [-1,1]) {
      block(g,x+side*w*.78,y+h/2,z+.08,w*.43,h+.08,.10,shutters);
      for(let i=0;i<8;i++)block(g,x+side*w*.78,y+(i+.5)*h/8,z+.15,w*.35,.04,.06,trim);
    }
    if(arched)add(g,arch(w+.25,h+.12,.10,.09),trim,[x,y,z+.16]);
  }
  function sign(g,text,w,h,color=C.wood,bg=C.wall,fontSize=80) {
    const canvas=document.createElement('canvas');canvas.width=1024;canvas.height=192;const ctx=canvas.getContext('2d');
    ctx.fillStyle=bg;ctx.fillRect(0,0,1024,192);ctx.fillStyle=color;ctx.font=fontSize+'px Georgia';ctx.textAlign='center';ctx.textBaseline='middle';
    const scale=Math.min(1,950/Math.max(1,ctx.measureText(text).width));ctx.font=(fontSize*scale)+'px Georgia';ctx.fillText(text,512,98);
    const texture=new THREE.CanvasTexture(canvas);texture.colorSpace=THREE.SRGBColorSpace;
    const m=new THREE.Mesh(new THREE.PlaneGeometry(w,h),new THREE.MeshStandardMaterial({map:texture,roughness:1}));g.add(m);return m;
  }
  function envelope(id,g) {
    g.updateWorldMatrix(true,true);const b=new THREE.Box3().setFromObject(g),points=[];if(b.isEmpty())return;
    for(const x of [b.min.x,b.max.x])for(const y of [b.min.y,b.max.y])for(const z of [b.min.z,b.max.z])points.push(new THREE.Vector3(x,y,z));modelEnvelopes.set(id,[...(modelEnvelopes.get(id)||[]),...points]);
  }
  function walkable(g) {
    g.updateWorldMatrix(true,true);g.traverse(p=>{if(p.isMesh&&!p.isInstancedMesh)walkableGeometries.push(p.geometry.clone().applyMatrix4(p.matrixWorld));});
  }
  function ramp(w,run,near,far,thickness=.12) {
    const geo=new THREE.BoxGeometry(w,thickness,run),v=geo.attributes.position;
    for(let i=0;i<v.count;i++)v.setY(i,THREE.MathUtils.lerp(near,far,(v.getZ(i)+run/2)/run)+(v.getY(i)>0?0:-thickness));
    geo.computeVertexNormals();return geo;
  }
  function pergola(g,spec,trim=C.trim) {
    const [w,h,d]=spec.size||[5,2.8,3],pitch=Math.max(.25,spec.spacing??.6),frame=spec.frameColor||trim;
    for(const x of [-w/2,w/2])for(const z of [-d/2,d/2])block(g,x,h/2,z,.16,h,.16,frame);
    for(const z of [-d/2,d/2])block(g,0,h,z,w+.35,.22,.16,frame);
    for(const x of [-w/2,w/2])block(g,x,h,0,.16,.22,d+.35,frame);
    const ribs=[];for(let x=-w/2;x<=w/2+.001;x+=w/Math.max(1,Math.ceil(w/pitch)))ribs.push({p:[x,h+.17,0],s:[.075,.18,d+.5]});instances(g,'stay-pergola-ribs',cube,ribs,frame);
  }
  function mansard(roof,spec,w,d,trim,glass) {
    const rise=spec.rise??3,inset=Math.min(spec.inset??1.1,Math.min(w,d)*.35),over=spec.overhang??.3,shoulder=rise*(spec.shoulder??.82);
    const rings=[[w/2+over,d/2+over,0],[w/2-inset,d/2-inset,shoulder],[w/2-inset-.15,d/2-inset-.15,rise]],vertices=[];
    const corners=([x,z,y])=>[[-x,y,-z],[x,y,-z],[x,y,z],[-x,y,z]];
    for(let n=0;n<2;n++) {
      const a=corners(rings[n]),b=corners(rings[n+1]);
      for(let k=0;k<4;k++){const j=(k+1)%4;vertices.push(...a[k],...b[k],...b[j],...a[k],...b[j],...a[j]);}
    }
    const top=corners(rings[2]);vertices.push(...top[0],...top[3],...top[2],...top[0],...top[2],...top[1]);
    const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));geo.computeVertexNormals();
    const slopes=group(roof,'stay-mansard-slopes');add(slopes,geo,spec.color||C.roof);
    const lines=group(roof,'stay-roof-seams'),pitch=Math.max(.18,spec.seamSpacing??.55);
    for(let y=.15;y<shoulder;y+=pitch*.55) {
      const t=y/shoulder,x=THREE.MathUtils.lerp(rings[0][0],rings[1][0],t),z=THREE.MathUtils.lerp(rings[0][1],rings[1][1],t);
      for(const side of [-1,1]){block(lines,0,y,side*(z+.009),x*2,.016,.018,spec.seamColor||'#84877e');block(lines,side*(x+.009),y,0,.018,.016,z*2,spec.seamColor||'#84877e');}
    }
    for(const p of spec.dormers||[]) {
      const edge=p.edge??2,angle=[Math.PI,-Math.PI/2,0,Math.PI/2][edge],width=p.width??1.8,height=p.height??2,depth=p.depth??1.2,y=p.y??.45;
      const front=edge%2===0?d/2:w/2,z=front+over-inset*(y/shoulder)-depth*.35;
      const pos=new THREE.Vector3(p.offset??0,y,z).applyAxisAngle(new THREE.Vector3(0,1,0),angle),dormer=group(roof,'stay-dormer',pos.toArray(),angle);
      block(dormer,0,height/2,0,width,height,depth,trim);
      windowBay(dormer,0,.18,depth/2+.01,width*.68,height-.4,false,trim,glass,true);
      const cap=group(dormer,'stay-dormer-crown',[0,height-.15,depth/2+.12]);add(cap,arch(width+.24,width*.46,.13,.22),trim,[0,0,0],[1,.6,1]);
      block(dormer,0,height+.20,-depth*.1,width+.28,.14,depth+.25,spec.color||C.roof);
    }
  }
  registerObjectType('stay_building',object=>{
    const g=root(object,'stay'),[w,H,d]=object.size||[18,9.6,12],levels=object.storeyHeights?.length??object.storeys??3,defaultLevel=H/levels,floor=object.floorHeight??.3;
    const outline=object.outline||[[-w/2,-d/2],[w/2,-d/2],[w/2,d/2],[-w/2,d/2]];
    const wall=object.wallColor||C.wall,trim=object.trimColor||C.trim,glass=object.glassColor||C.glass;
    const foundation=group(g,'stay-foundation');add(foundation,slab(outline,floor+.18),C.stone,[0,-.18,0]);
    const front=group(g,'stay-front');front.userData.front=true;g.userData.frontLayer=front;
    const arcadeGroup=group(g,'stay-arcades'),details=group(g,'stay-facade-detail'),balusters=[];
    const area=outline.reduce((s,a,i)=>{const b=outline[(i+1)%outline.length];return s+a[0]*b[1]-b[0]*a[1];},0);
    outline.forEach((a,i)=>{
      const b=outline[(i+1)%outline.length],dx=b[0]-a[0],dz=b[1]-a[1],L=Math.hypot(dx,dz);if(L<.01)return;
      const nx=(area>0?1:-1)*dz/L,nz=(area>0?-1:1)*dx/L,angle=Math.atan2(nx,nz);
      const edge=group(details,'stay-edge-'+i,[(a[0]+b[0])/2,0,(a[1]+b[1])/2],angle);
      const arc=object.arcade?.edges?.includes(i),depth=arc?(object.arcade.depth??2.4):0;
      const entry=object.entrance?.edge===i,doorW=object.entrance?.width??2.8,doorH=object.entrance?.height??3.1;
      const wallPart=entry?group(front,'stay-entry-wall',edge.position.toArray(),angle):edge;
      if(entry) {
        const doorX=object.entrance.offset??0,entryWall=arc?(object.arcade.wallColor||wall):wall;
        for(const [lo,hi] of [[-L/2,doorX-doorW/2],[doorX+doorW/2,L/2]])block(wallPart,(lo+hi)/2,(H+floor)/2,-depth,hi-lo,H-floor,.24,entryWall);
        block(wallPart,doorX,(H+floor+doorH)/2,-depth,doorW,H-floor-doorH,.24,entryWall);
        const door=group(g,'stay-entrance-door',wallPart.position.toArray(),angle);block(door,doorX,floor+doorH/2,.05-depth,doorW-.08,doorH,.14,C.wood);g.userData.interiorDoor=door;
      } else block(edge,0,(H+floor)/2,-depth,L,H-floor,.24,arc?(object.arcade.wallColor||wall):wall);
      const bays=Math.max(1,Math.round(L/(object.bayWidth??3.5))),bay=L/bays,windowW=Math.min((arc?object.arcade.windowWidth:undefined)??object.windowWidth??1.65,bay*(object.windowWidthRatio??.6)),windowH=object.windowHeight??2.2;
      for(let storey=0;storey<levels;storey++) {
        const level=object.storeyHeights?.[storey]??defaultLevel,y=floor+(object.storeyHeights?object.storeyHeights.slice(0,storey).reduce((a,b)=>a+b,0):storey*level),galleryActive=arc&&(object.arcade.levels??[0,1,2]).includes(storey),recess=arc&&!galleryActive?(object.arcade.upperRecess??depth):depth;
        if(arc&&!galleryActive&&object.arcade.upperRecess!==undefined)block(edge,0,y+level/2,-recess,L,Math.min(level,H-y),.24,wall);
        if(object.balconies?.band&&(!object.facadeEdges||object.facadeEdges.includes(i))&&!galleryActive&&storey>0&&(!object.balconies.edges||object.balconies.edges.includes(i))&&(!object.balconies.levels||object.balconies.levels.includes(storey))) {
          const b=object.balconies.band,bh=b.height??.25,bd=b.depth??.9,bw=L+2*(b.overhang??.15),band=group(edge,'stay-balcony-band-'+i+'-'+storey);
          block(band,0,y+.08-bh/2,bd/2-.1,bw,bh,bd,trim);
          block(band,0,y+.08,bd/2-.1,bw+.1,.06,bd+.08,trim);
        }
        for(let k=0;k<bays;k++) {
          const x=-L/2+(k+.5)*bay;
          if(object.facadeEdges&&!object.facadeEdges.includes(i))continue;
          if(entry&&storey===0&&Math.abs(x-(object.entrance.offset??0))<doorW/2+windowW/2)continue;
          const sill=object.windowSill??.65,clearance=object.windowSill===undefined?level-1:Math.max(.05,level-sill-.2);
          windowBay(edge,x,y+sill,-recess+.17,windowW,Math.min(windowH,clearance),arc?(object.arcade.shutters??object.shutters):object.shutters,object.windowFrameColor||trim,glass,arc&&(object.arcade.windowArched??false));
          if(object.balconies&&!galleryActive&&storey>0&&(!object.balconies.edges||object.balconies.edges.includes(i))&&(!object.balconies.levels||object.balconies.levels.includes(storey))) {
            const spec=object.balconies,bw=spec.width??windowW+.65,bd=spec.depth??.8,rail=spec.railThickness??.045,rh=spec.railHeight??.95,color=spec.color||C.wood;
            const balcony=group(edge,'stay-balcony-'+i+'-'+storey,[x,y,0]);
            block(balcony,0,.12,bd/2,bw,.16,bd,trim);block(balcony,0,rh+.12,bd,bw,rail,rail,color);
            const count=spec.railSpacing?Math.max(1,Math.ceil(bw/spec.railSpacing)):6;
            for(let q=0;q<=count;q++)block(balcony,-bw/2+q*bw/count,.12+rh/2,bd,rail,rh,rail,color);
            for(const side of [-1,1]) {
              block(balcony,side*bw/2,rh+.12,bd/2,rail,rail,bd,color);
              for(let z=.12;z<bd;z+=spec.railSpacing??.2)block(balcony,side*bw/2,.12+rh/2,z,rail,rh,rail,color);
            }
          }
        }
        if(galleryActive&&object.arcade.walkable) {
          const surface=group(edge,'stay-gallery-floor-'+i+'-'+storey);block(surface,0,y-.06,-recess/2,L+.12,.12,Math.max(.4,recess+.25),trim);
        } else block(edge,0,y+.09,-recess/2,L+.12,.18,Math.max(.4,recess+.25),trim);
        if(galleryActive) {
          const gallery=group(arcadeGroup,'stay-gallery-'+i+'-'+storey,edge.position.toArray(),angle);
          if(object.arcade.kind==='colonnade') {
            const radius=object.arcade.columnRadius??.3,columns=[],height=level-.28;
            for(let k=0;k<=bays;k++) {
              const x=-L/2+k*bay;columns.push({p:[x,y+height/2,0],s:[radius,height,radius]});
              add(gallery,new THREE.CylinderGeometry(radius*1.28,radius*1.28,.16,16),trim,[x,y+.08,0]);
              add(gallery,new THREE.CylinderGeometry(radius*1.24,radius,.18,16),trim,[x,y+height-.09,0]);
            }
            instances(gallery,'stay-round-columns',new THREE.CylinderGeometry(1,1,1,20),columns,object.arcade.columnColor||trim);
            const beam=group(gallery,'stay-straight-beam');block(beam,0,y+level-.14,0,L+.3,.28,radius*2.7,trim);
            block(gallery,0,y+level-.06,-depth/2,L,.12,depth,object.arcade.ceilingColor||wall);
          } else {
          for(let k=0;k<=bays;k++) {
            const x=-L/2+k*bay;block(gallery,x,y+level*.45,0,.4,level*.9,.45,trim);block(gallery,x,y+.12,0,.66,.22,.65,trim);
            block(gallery,x,y+level-.28,0,.65,.20,.65,trim);
          }
          for(let k=0;k<bays;k++) {
            const x=-L/2+(k+.5)*bay,archHeight=level-.25,archRadius=(bay-.38)/2,archRise=object.arcade.archRise??archRadius;
            const base=archHeight-archRise;
            if(object.arcade.archRise===undefined)add(gallery,arch(bay-.38,archHeight,.20,.30),trim,[x,y,0]);
            else {block(gallery,x-archRadius+.10,y+base/2,0,.20,base,.30,trim);block(gallery,x+archRadius-.10,y+base/2,0,.20,base,.30,trim);add(gallery,arch(bay-.38,archRadius,.20,.30),trim,[x,y+base,0],[1,archRise/archRadius,1]);}
            // Opaque spandrel above the arch; the gallery below stays open.
            const r=(bay-.38)/2,spring=level-.25-(object.arcade.archRise??r),shape=new THREE.Shape();shape.moveTo(-r,level);shape.lineTo(r,level);shape.lineTo(r,spring);
            if(object.arcade.archRise===undefined)shape.absarc(0,spring,r,0,Math.PI,false);else shape.absellipse(0,spring,r,object.arcade.archRise,0,Math.PI,false,0);
            shape.closePath();add(gallery,new THREE.ExtrudeGeometry(shape,{depth:.28,bevelEnabled:false,curveSegments:16}),wall,[x,y,0]);
          }
          if(object.arcade.upperRecess!==undefined)block(gallery,0,y+level-.06,-depth/2,L,.12,depth,object.arcade.ceilingColor||wall);
          }
          if(storey>0) {
            block(gallery,0,y+.92,.22,L,.13,.30,trim);block(gallery,0,y+.24,.22,L,.13,.30,trim);
            gallery.updateWorldMatrix(true,false);g.updateWorldMatrix(true,false);
            for(let x=-L/2+.2;x<L/2;x+=.32) {
              const p=new THREE.Vector3(x,y+.57,.22).applyMatrix4(gallery.matrixWorld).applyMatrix4(g.matrixWorld.clone().invert());balusters.push({p:p.toArray(),s:[.075,.60,.075]});
            }
          }
        }
      }
      if(object.cornice!==false) {
        block(edge,0,H-.12,0,L+.3,.20,.7,trim);
        for(let x=-L/2+.5;x<L/2;x+=1.65)block(edge,x,H-.5,-.01,.18,.64,.48,trim);
      }
    });
    instances(arcadeGroup,'stay-balusters',cube,balusters,trim);
    const roof=group(g,object.id+'-roof',[0,H,0]),spec=object.roof||{},roofColor=spec.color||C.roof;
    if((spec.kind||'flat')==='flat') {
      add(roof,slab(outline,.18),roofColor);
      // Parapet rails follow each edge, including rotated and stepped footprints.
      outline.forEach((a,i)=>{const b=outline[(i+1)%outline.length],L=Math.hypot(b[0]-a[0],b[1]-a[1]);if(L>.01)add(roof,cube,trim,[(a[0]+b[0])/2,.32,(a[1]+b[1])/2],[L,.45,.20],Math.atan2(-(b[1]-a[1]),b[0]-a[0]));});
    } else if(spec.kind==='mansard') {
      mansard(roof,spec,w,d,trim,glass);add(roof,slab(outline,.12),trim,[0,-.10,0]);
    } else {
      const rise=spec.rise??d*.30,ridge=spec.kind==='hip'?Math.max(0,w/2-d*.4):w/2,v=[];
      const A=[-w/2-.35,0,-d/2-.35],B=[w/2+.35,0,-d/2-.35],D=[-w/2-.35,0,d/2+.35],E=[w/2+.35,0,d/2+.35],L=[-ridge,rise,0],R=[ridge,rise,0];
      for(const tri of [[A,L,R],[A,R,B],[D,E,R],[D,R,L],[A,D,L],[B,R,E]])v.push(...tri.flat());
      const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(v,3));geo.computeVertexNormals();add(roof,geo,roofColor);add(roof,slab(outline,.12),C.trim,[0,-.10,0]);
      if(spec.seamSpacing) {
        const seams=group(roof,'stay-roof-seams'),pitch=Math.max(.18,spec.seamSpacing)*.55,color=spec.seamColor||'#84877e';
        for(let y=pitch;y<rise-.08;y+=pitch) {
          const t=y/rise,x=THREE.MathUtils.lerp(w/2+.35,ridge,t),z=(d/2+.35)*(1-t);
          for(const side of [-1,1]){block(seams,0,y+.012,side*(z+.012),x*2,.016,.022,color);block(seams,side*(x+.012),y+.012,0,.022,.016,z*2,color);}
        }
      }
    }
    if(spec.terrace) {
      const t=spec.terrace,[tw,th,td]=t.size||[16,3,8],terrace=group(roof,'stay-roof-terrace',t.position||[0,0,0]),frame=t.frameColor||trim,spacing=Math.max(.8,t.spacing??4),bays=Math.max(1,Math.round(tw/spacing)),pitch=tw/bays;
      for(const z of [-td/2,td/2]) {
        for(let k=0;k<=bays;k++)block(terrace,-tw/2+k*pitch,th/2,z,.20,th,.20,frame);
        block(terrace,0,th-.10,z,tw+.3,.22,.22,frame);
      }
      for(let k=0;k<=bays;k++)block(terrace,-tw/2+k*pitch,th+.04,0,.12,.14,td+.35,frame);
      for(const x of [-tw/2,tw/2])block(terrace,x,th-.10,0,.22,.22,td,frame);
      if((t.archRise??0)>0) {
        const arches=group(terrace,'stay-terrace-arches'),rise=t.archRise;
        for(const z of [-td/2,td/2])for(let k=0;k<bays;k++)add(arches,arch(pitch-.24,(pitch-.24)/2,.07,.10),frame,[-tw/2+(k+.5)*pitch,th-rise-.12,z],[1,rise/((pitch-.24)/2),1]);
      }
      if(t.canopy!==false)block(terrace,0,th+.13,0,tw+.4,.12,td+.4,t.color||roofColor);
    }
    const crown=group(roof,'stay-crown');
    for(const p of object.crown?.pavilions||[]) {
      const [pw,ph,pd]=p.size,tower=group(crown,'stay-pavilion',p.position||[0,0,0]);
      block(tower,0,ph/2,0,pw,ph,pd,wall);block(tower,0,ph+.12,0,pw+.5,.24,pd+.5,trim);
      windowBay(tower,0,.5,pd/2+.05,pw*.55,ph-.8,false,trim,glass,true);
      for(const x of [-pw/2+.25,pw/2-.25])block(tower,x,ph/2,pd/2+.1,.3,ph,.35,trim);
    }
    if(object.crown?.pediment) {
      const p=object.crown.pediment,[pw,ph]=p.size,s=new THREE.Shape();s.moveTo(-pw/2,0);s.lineTo(pw/2,0);s.lineTo(0,ph);s.closePath();
      const ped=group(crown,'stay-pediment',p.position||[0,0,0]);add(ped,new THREE.ExtrudeGeometry(s,{depth:.28,bevelEnabled:false}),trim);
      if(p.glazing) {
        const glassSpec=p.glazing===true?{}:p.glazing,inset=Math.min(.4,pw*.12),half=pw/2-inset,base=.22,top=ph-.35,light=group(ped,'stay-gable-glazing'),shape=new THREE.Shape();
        shape.moveTo(-half,base);shape.lineTo(half,base);shape.lineTo(0,top);shape.closePath();add(light,new THREE.ShapeGeometry(shape),glassSpec.color||glass,[0,0,.30]);
        const lines=group(ped,'stay-gable-mullions'),color=glassSpec.frameColor||trim,n=Math.max(2,glassSpec.mullions??5);
        block(lines,0,base,.33,half*2,.07,.07,color);
        for(let k=1;k<n;k++){const x=-half+k*half*2/n,height=(top-base)*(1-Math.abs(x)/half);block(lines,x,base+height/2,.33,.055,height,.07,color);}
        for(const side of [-1,1]) {
          const length=Math.hypot(half,top-base),line=cube.clone().scale(.07,length,.07).rotateZ(side*Math.atan2(half,top-base)).translate(side*half/2,(base+top)/2,.33);add(lines,line,color);
        }
      }
      if(p.text)sign(ped,p.text,pw*.70,ph*.32,C.wood,trim).position.set(0,ph*.29,.30);
    }
    if(object.entrance) {
      const e=object.entrance,a=outline[e.edge],b=outline[(e.edge+1)%outline.length],dx=b[0]-a[0],dz=b[1]-a[1],L=Math.hypot(dx,dz),nx=(area>0?1:-1)*dz/L,nz=(area>0?-1:1)*dx/L;
      const entry=group(g,'stay-entrance',[(a[0]+b[0])/2,0,(a[1]+b[1])/2],Math.atan2(nx,nz));entry.position.add(new THREE.Vector3(e.offset??0,0,0).applyAxisAngle(new THREE.Vector3(0,1,0),entry.rotation.y));
      const cw=e.canopyWidth??6,cd=e.canopyDepth??2.5,ch=floor+(e.height??3.1)+.25;
      if(e.canopy!==false){block(entry,0,ch,cd/2,cw,.14,cd,e.canopyColor||C.roof);
      const ribs=[];for(let x=-cw/2;x<=cw/2+.01;x+=cw/8)ribs.push({p:[x,ch-.10,cd/2],s:[.045,.07,cd]});instances(entry,'stay-canopy-ribs',cube,ribs,C.wood);}
      if(e.sign)sign(entry,e.sign,cw*.9,.60,C.wood,wall).position.set(0,ch+.46,.22);
      const steps=e.steps??3;for(let k=0;k<steps;k++)block(entry,0,floor*(steps-k)/(2*steps),cd+.25+k*.30,cw,floor*(steps-k)/steps,.55,trim);
      modelEnvelopes.set(object.id+'-entry',[]);
    }
    roofRecords.push({group:roof,parameters:{width:w,depth:d,ridgeHeight:H+((spec.kind||'flat')==='flat'?0:(spec.rise??(spec.kind==='mansard'?3:d*.30))),kind:spec.kind||'flat'},tiers:1,thickness:.18,ridgeOrnament:false});
    flush();
    if(object.arcade?.walkable)g.traverse(p=>{if(p.name.startsWith('stay-gallery-floor-'))walkable(p);});
    if(object.facadeEdges||object.balconies?.edges||object.arcade?.kind||spec.kind==='mansard') {
      g.traverse(p=>{if(/^stay-gallery-|^stay-balcony-/.test(p.name))envelope(object.id+'-'+p.name.replace('stay-',''),p);});envelope(object.id+'-roof',roof);
    }
    if(object.entrance) {
      g.updateWorldMatrix(true,true);const e=g.getObjectByName('stay-entrance'),box=new THREE.Box3().setFromObject(e),points=[];
      for(const x of [box.min.x,box.max.x])for(const y of [box.min.y,box.max.y])for(const z of [box.min.z,box.max.z])points.push(new THREE.Vector3(x,y,z));modelEnvelopes.set(object.id+'-entry',points);
    }
  });
  registerObjectType('stay_paving',object=>{
    const g=root(object,'paving'),color=object.color||C.stone,thickness=object.thickness??.12,joints=[];
    if(object.pattern==='stepping') {
      g.updateWorldMatrix(true,false);
      const points=object.points||[[0,0,-3],[0,0,3]],stones=[],length=object.stepLength??.65,gap=object.stepGap??.25,width=object.width??1;
      for(let i=1;i<points.length;i++) {
        const a=new THREE.Vector3(...points[i-1]),b=new THREE.Vector3(...points[i]),delta=b.clone().sub(a),L=delta.length(),count=Math.max(1,Math.floor((L+gap)/(length+gap))),step=L/count,angle=Math.atan2(delta.x,delta.z);
        for(let k=0;k<count;k++) {
          const p=a.clone().lerp(b,(k+.5)/count);p.y+=thickness/2;
          const stoneLength=Math.min(length,step-gap),geo=cube.clone();stones.push({p:p.toArray(),s:[width,thickness,Math.max(.05,stoneLength)],r:angle});
          walkableGeometries.push(geo.scale(width,thickness,Math.max(.05,stoneLength)).rotateY(angle).translate(...p.toArray()).applyMatrix4(g.matrixWorld));
        }
      }
      instances(g,'stay-stepping-stones',cube,stones,color);return;
    }
    if(object.points) {
      for(let i=1;i<object.points.length;i++) {
        const a=new THREE.Vector3(...object.points[i-1]),b=new THREE.Vector3(...object.points[i]),delta=b.clone().sub(a),L=delta.length(),angle=Math.atan2(delta.x,delta.z),mid=a.clone().add(b).multiplyScalar(.5);
        const section=group(g,'stay-paved-leg',mid.toArray(),angle);block(section,0,thickness/2,0,object.width??3,thickness,L+.02,color);
        const pitch=object.jointSpacing??1.2;for(let z=-L/2;z<L/2;z+=pitch)joints.push({p:new THREE.Vector3(0,thickness+.009,z).applyAxisAngle(new THREE.Vector3(0,1,0),angle).add(mid).toArray(),s:[object.width??3,.012,.018],r:angle});
      }
    } else if(object.pattern==='cobble') {
      const [w,,d]=object.size||[15,0,10],pitch=Math.max(.15,object.jointSpacing??.45),length=pitch*1.5;block(g,0,thickness/2,0,w,thickness,d,color);
      for(let row=0,z=-d/2;z<d/2;row++,z+=pitch) {
        const rowDepth=Math.min(pitch,d/2-z);joints.push({p:[0,thickness+.004,z],s:[w,.006,.012]});
        for(let x=-w/2+(row%2)*length/2;x<w/2;x+=length)joints.push({p:[x,thickness+.004,z+rowDepth/2],s:[.012,.006,rowDepth]});
      }
      flush();instances(g,'stay-cobble-joints',cube,joints,object.jointColor||'#b9b9ab');walkable(g);return;
    } else {
      const [w,,d]=object.size||[15,0,10];block(g,0,thickness/2,0,w,thickness,d,color);
      const pitch=object.jointSpacing??1.2;for(let z=-d/2;z<d/2;z+=pitch)for(let x=-w/2;x<w/2;x+=pitch*1.5) {
        const length=Math.min(pitch*1.5,w/2-x);joints.push({p:[x+length/2,thickness+.009,z],s:[length,.012,.018]});
        joints.push({p:[x,thickness+.009,z+Math.min(pitch,d/2-z)/2],s:[.018,.012,Math.min(pitch,d/2-z)]});
      }
    }
    flush();instances(g,'stay-paving-joints',cube,joints,object.jointColor||'#b9b9ab');g.updateWorldMatrix(true,true);
    g.traverse(p=>{if(p.isMesh&&!p.isInstancedMesh)walkableGeometries.push(p.geometry.clone().applyMatrix4(p.matrixWorld));});
  });
  registerObjectType('stay_garden',object=>{
    const g=root(object,'garden'),[w,,d]=object.size||[10,0,5],shape=object.shape||'rectangle',height=object.height??.18;
    if(shape==='ellipse')add(g,new THREE.CylinderGeometry(1,1,height,48),object.color||'#b7c0a5',[0,height/2,0],[w/2,1,d/2]);
    else block(g,0,height/2,0,w,height,d,object.color||'#b7c0a5');
    const leaves=[],flowers=[],hedge=[],spacing=object.spacing??.8;
    const inside=(x,z,margin=0)=>shape==='ellipse'?Math.pow(x/(w/2-margin),2)+Math.pow(z/(d/2-margin),2)<1:Math.abs(x)<w/2-margin&&Math.abs(z)<d/2-margin;
    for(let x=-w/2+.3;x<w/2;x+=spacing)for(let z=-d/2+.3;z<d/2;z+=spacing) {
      const xx=x+Math.sin(z*9+x)*spacing*.37,zz=z+Math.cos(x*6-z)*spacing*.37;if(!inside(xx,zz,.15))continue;
      const spread=1+.18*Math.sin(x*3.7+z*2.3);
      if(object.planting!==false)leaves.push({p:[xx,height+.16,zz],s:[spacing*.80*spread,.22+spread*.03,spacing*.72*spread],c:Math.sin(x+z)>0?'#a5b190':'#afbb9e'});
      if((object.flowers??true)&&Math.sin(xx*3+zz*4)>.15)flowers.push({p:[xx,height+.42,zz],s:[.09+.025*Math.sin(x),.05,.10],c:Math.sin(x*4-z)>0?(object.flowerColor||C.flower):'#cbbda0'});
    }
    if(object.hedge!==false) {
      const n=Math.ceil((w+d)*2/.7);for(let i=0;i<n;i++) {
        let x,z;if(shape==='ellipse'){const a=i/n*Math.PI*2;x=(w/2-.25)*Math.cos(a);z=(d/2-.25)*Math.sin(a);}else {const t=i/n*2*(w+d);if(t<w){x=-w/2+t;z=-d/2;}else if(t<w+d){x=w/2;z=-d/2+t-w;}else if(t<2*w+d){x=w/2-(t-w-d);z=d/2;}else{x=-w/2;z=d/2-(t-2*w-d);}}
        hedge.push({p:[x,height+.32,z],s:[.48,.32,.48]});
      }
    }
    instances(g,'stay-bed-leaves',leaf,leaves,C.sage);instances(g,'stay-bed-flowers',leaf,flowers,object.flowerColor||C.flower);instances(g,'stay-hedges',leaf,hedge,'#98a784');flush();
  });
  registerObjectType('stay_grove',object=>{
    const g=root(object,'grove'),trunks=[],crowns=[],under=[];
    for(const [i,p] of (object.trees||[[0,0,9]]).entries()) {
      const [x,z,h]=p;trunks.push({p:[x,h*.43,z],s:[.16,h*.86,.16]});
      if(object.species==='round')crowns.push({p:[x,h*.62,z],s:[h*(object.crownRatio??.45),h*.38,h*(object.crownRatio??.45)]});
      else if(object.species==='bonsai')for(let tier=0;tier<3;tier++)crowns.push({p:[x+Math.sin(tier*2+i)*h*.08,h*(.42+tier*.20),z],s:[h*(.45-tier*.07),h*.14,h*(.39-tier*.06)]});
      else if(object.species==='cypress')crowns.push({p:[x,h*.55,z],s:[h*.10,h*.45,h*.10]});
      else for(let tier=0;tier<5;tier++)for(let k=0;k<3;k++) {
        const a=k*2.094+tier*.7+i,r=h*(.11-tier*.013);crowns.push({p:[x+Math.cos(a)*r,h*(.60+tier*.075),z+Math.sin(a)*r],s:[r*1.15,h*.035,r*.8],r:a});
      }
      if(object.understory!==false)for(let k=0;k<8;k++){const a=k*2.4+i;under.push({p:[x+Math.sin(a)*1.7,.28,z+Math.cos(a)*1.4],s:[.75,.28,.64]});}
    }
    instances(g,'stay-tree-trunks',new THREE.CylinderGeometry(1,1,1,7),trunks,C.wood);instances(g,'stay-foam-crowns',leaf,crowns,object.color||C.sage);instances(g,'stay-understory',leaf,under,'#acb799');
  });
  registerObjectType('stay_sign',object=>{
    const g=root(object,'sign'),[w,h,d]=object.size||[5,1.5,.4];block(g,0,h/2,0,w,h,d,object.color||'#939e99');
    sign(g,object.text||'',w*.9,h*.62,object.textColor||C.trim,object.color||'#939e99').position.set(0,h*.56,d/2+.015);flush();
  });
  registerObjectType('stay_pool',object=>{
    const g=root(object,'pool'),[w,,d]=object.size||[8,0,4];block(g,0,.12,0,w+.7,.24,d+.7,C.trim);block(g,0,.25,0,w,.08,d,object.color||'#a2bab7');
    for(const x of [-w/2,w/2])block(g,x,.31,0,.16,.12,d+.3,C.stone);for(const z of [-d/2,d/2])block(g,0,.31,z,w+.3,.12,.16,C.stone);flush();
  });
  registerObjectType('stay_furniture',object=>{
    const g=root(object,'furniture');
    for(const [x,z,a=0] of object.benches||[]) {
      const bench=group(g,'stay-bench',[x,0,z],a);block(bench,0,.47,0,1.8,.12,.55,C.wood);block(bench,0,.80,-.25,1.8,.60,.10,C.wood);for(const xx of [-.65,.65])block(bench,xx,.22,0,.12,.44,.48,C.stone);
    }
    for(const [x,z,h=3.8] of object.lamps||[]) {block(g,x,h/2,z,.08,h,.08,C.wood);block(g,x,h-.1,z,.38,.55,.38,'#d4ceb7');block(g,x,h+.22,z,.5,.12,.5,C.wood);}
    for(const [x,z,h=1.6] of object.urns||[]) {
      add(g,new THREE.CylinderGeometry(.36,.50,.24,12),C.stone,[x,.12,z]);add(g,new THREE.CylinderGeometry(.6,.28,.64,16),C.trim,[x,.56,z]);add(g,leaf,object.flowerColor||C.flower,[x,h*.72,z],[.75,h*.28,.75]);
    }
    flush();
  });
  registerObjectType('stay_context',object=>{
    const g=root(object,'context'),[w,h,d]=object.size||[3,12,10],color=object.color||'#bcbab1';
    block(g,0,h/2,0,w,h,d,color);block(g,0,h+.06,0,w+.12,.12,d+.12,object.roofColor||'#aaa99e');flush();
  });
  registerObjectType('stay_planter',object=>{
    const g=root(object,'planter'),[w,h,d]=object.size||[3,.7,.8],color=object.color||'#c6c5b7',wall=Math.min(.13,d*.18),leaves=[],flowers=[];
    block(g,0,.06,0,w,.12,d,color);
    for(const side of [-1,1]){block(g,side*(w-wall)/2,h/2,0,wall,h,d,color);block(g,0,h/2,side*(d-wall)/2,w,h,wall,color);}
    block(g,0,h-.13,0,w-wall*2,.10,d-wall*2,'#a6ae96');
    const spacing=Math.max(.15,object.spacing??.32);
    for(let x=-w/2+.18;x<w/2-.1;x+=spacing)for(let z=-d/2+.16;z<d/2-.08;z+=spacing) {
      leaves.push({p:[x,h+.06,z],s:[spacing*.8,.18,spacing*.7]});
      if(object.flowers!==false&&Math.sin(x*12+z)>0)flowers.push({p:[x,h+.23,z],s:[.055,.04,.06]});
    }
    instances(g,'stay-planter-leaves',leaf,leaves,object.leafColor||C.sage);instances(g,'stay-planter-flowers',leaf,flowers,object.flowerColor||'#c6b7b2');
    if(object.text){const face=sign(g,object.text,w*.92,Math.min(h*.65,.85),object.textColor||C.trim,color,140);face.name='stay-planter-sign';face.position.set(0,h*.48,d/2+.012);}
    flush();
  });
  registerObjectType('stay_vines',object=>{
    const g=root(object,'vines'),width=object.width??5,drop=object.drop??3,count=Math.max(1,object.strands??16),seed=object.seed??1,leaves=[],stems=[];
    const random=n=>{const t=Math.sin(n*12.9898+seed*78.233)*43758.5453;return t-Math.floor(t);};
    const clear=(x,y)=>(object.openings||[]).some(([cx,cy,w,h])=>Math.abs(x-cx)<w/2+.16&&Math.abs(y-cy)<h/2+.16);
    for(let k=0;k<count;k++) {
      const x=-width/2+(k+.5)*width/count,length=drop*(.45+.55*random(k+1));
      for(let y=0,i=0;y<length;y+=.15,i++) {
        const xx=x+Math.sin(i*.7+k)*.08,yy=-y,z=.08+random(k*53+i)*.10;if(clear(xx+(i%2?.08:-.08),yy))continue;
        stems.push({p:[xx,yy,z],s:[.012,.19,.012]});
        leaves.push({p:[xx+(i%2?.08:-.08),yy,z+.04],s:[.09+random(k+i)*.04,.065,.045],r:k+i,c:random(k*31+i)>.4?(object.color||'#95a388'):'#a8b396'});
      }
    }
    instances(g,'stay-vine-stems',cube,stems,'#89927b');instances(g,'stay-vine-leaves',leaf,leaves,C.sage);
  });
  registerObjectType('stay_fence',object=>{
    const g=root(object,'fence'),length=object.length??8,height=object.height??1.15,spacing=Math.max(.12,object.spacing??.28),gate=object.gateWidth??0,gateX=object.gateX??0,color=object.color||'#eeece0',pickets=[];
    const open=x=>gate>0&&Math.abs(x-gateX)<gate/2;
    for(let x=-length/2;x<=length/2+.001;x+=length/Math.max(1,Math.ceil(length/spacing)))if(!open(x))pickets.push({p:[x,height*.48,0],s:[object.picketWidth??.095,height*.96,.075]});
    const segments=gate>0?[[-length/2,gateX-gate/2],[gateX+gate/2,length/2]]:[[-length/2,length/2]];
    for(const [a,b] of segments)if(b>a) {
      for(const y of [height*.28,height*.72])block(g,(a+b)/2,y,-.05,b-a,.085,.085,color);
      const bays=Math.max(1,Math.ceil((b-a)/2));for(let k=0;k<=bays;k++){const x=a+(b-a)*k/bays;block(g,x,height/2,0,.14,height,.14,color);add(g,new THREE.ConeGeometry(.11,.14,4),color,[x,height+.07,0],[1,1,1],Math.PI/4);}
    }
    const shape=new THREE.Shape();shape.moveTo(-.5,-.5);shape.lineTo(.5,-.5);shape.lineTo(.5,.37);shape.lineTo(0,.5);shape.lineTo(-.5,.37);shape.closePath();
    const geometry=new THREE.ExtrudeGeometry(shape,{depth:1,bevelEnabled:false});geometry.translate(0,0,-.5);instances(g,'stay-pickets',geometry,pickets,color);flush();
  });
  registerObjectType('stay_pergola',object=>{const g=root(object,'pergola');pergola(g,object);flush();});
  registerObjectType('stay_terrace',object=>{
    const g=root(object,'terrace'),[w,h,d]=object.size||[8,2.1,3],color=object.color||C.stone,cap=object.capColor||C.trim,garage=object.garage,stairs=object.stairs;
    const deck=group(g,'stay-terrace-deck');block(deck,0,h-.10,0,w,.20,d,cap);
    if(garage) {
      const x=garage.x??-w*.22,gw=garage.width??3,floor=Math.min(garage.floorHeight??0,h-.3),gh=Math.max(.05,Math.min(garage.height??h-.25,h-.2-floor)),run=garage.run??3,street=garage.streetHeight??0;
      for(const [a,b] of [[-w/2,x-gw/2],[x+gw/2,w/2]])block(g,(a+b)/2,(h-.2)/2,0,b-a,h-.2,d,color);
      block(g,x,(floor+gh+h-.2)/2,0,gw,Math.max(0,h-.2-floor-gh),d,color);
      const tunnel=group(g,'stay-garage-tunnel');block(tunnel,x,floor+gh/2,-d/2+.08,gw,gh,.16,'#777b70');
      block(tunnel,x,floor+.02,0,gw,.10,d,'#aaa99e');block(tunnel,x,floor+gh-.04,0,gw,.08,d,'#a3a599');
      const slope=group(g,'stay-garage-ramp',[x,0,d/2+run/2]);add(slope,ramp(gw,run,floor+.07,street+.07),object.rampColor||'#aeb0a6');
      const kerb=garage.kerbHeight??.16;
      for(const side of [-1,1])add(slope,ramp(.16,run,floor+.07+kerb,street+.07+kerb,kerb),cap,[side*(gw/2+.08),0,0]);
      flush();walkable(slope);envelope(object.id+'-garage',tunnel);envelope(object.id+'-ramp',slope);
    } else block(g,0,(h-.2)/2,0,w,h-.2,d,color);
    if(stairs) {
      const flight=group(g,'stay-terrace-stairs'),x=stairs.x??w*.25,width=stairs.width??2,run=stairs.run??2.5,steps=Math.max(1,stairs.steps??8),street=stairs.streetHeight??0;
      for(let k=0;k<steps;k++){const top=street+(h-street)*(steps-k)/steps;block(flight,x,(top+street)/2,d/2+(k+.5)*run/steps,width,top-street,run/steps+.012,cap);}
      flush();walkable(flight);envelope(object.id+'-stairs',flight);
    }
    const joints=group(g,'stay-terrace-joints');for(let x=-w/2+.7;x<w/2;x+=.7)block(joints,x,h+.003,0,.012,.005,d,'#c5c4b7');
    flush();walkable(deck);envelope(object.id+'-deck',deck);
  });
  registerInteriorKit('stay_lounge',(building,{roof})=>{
    const shell=scene.getObjectByName(building.id+'-stay'),spec=building.interior,[w,h,d]=spec.size||[7,4,10],offset=spec.offset||[0,building.floorHeight??.3,0];
    const room=group(scene,building.id+'-interior'),rotation=(building.rotation||0)+(spec.facing===-1?Math.PI:0);
    room.rotation.y=rotation;room.position.copy(shell.localToWorld(new THREE.Vector3(...offset)));
    const wall=spec.wallColor||'#e8dfcb',wood=spec.woodColor||'#76614c',gold=spec.trimColor||'#b8a17b',floor=group(room,'stay-interior-floor');
    block(floor,0,-.06,0,w,.12,d,spec.floorColor||'#b69b7f');
    const planks=[];
    if(spec.floorPattern==='tile') {
      const pitch=Math.max(.3,spec.tileSpacing??.8);
      for(let x=-w/2+pitch;x<w/2;x+=pitch)planks.push({p:[x,.003,0],s:[.009,.006,d]});
      for(let z=-d/2+pitch;z<d/2;z+=pitch)planks.push({p:[0,.003,z],s:[w,.006,.009]});instances(floor,'stay-tile-joints',cube,planks,'#bdb9ad');
    } else {for(let x=-w/2+.15;x<w/2;x+=.28)for(let z=-d/2+.6;z<d/2;z+=1.2)planks.push({p:[x,.003,Math.min(d/2-.05,z)],s:[.278,.006,Math.min(1.198,d/2-z+.6)],c:Math.sin(x*12+z)>0?'#b9a181':'#b1997c'});instances(floor,'stay-parquet',cube,planks,'#b1997c');}
    const walls=group(room,'stay-room-walls');for(const side of [-1,1])block(walls,side*w/2,h/2,0,.22,h,d+.2,wall);block(walls,0,h/2,-d/2,w+.2,h,.22,wall);
    const dw=spec.doorWidth??2.8,dh=spec.doorHeight??3.1;
    if(spec.doorOffset!==undefined) {
      const x=spec.doorOffset;for(const [a,b] of [[-w/2,x-dw/2],[x+dw/2,w/2]])block(walls,(a+b)/2,h/2,d/2,b-a,h,.20,wall);block(walls,x,(h+dh)/2,d/2,dw,h-dh,.20,wall);
    } else {for(const side of [-1,1])block(walls,side*(w+dw)/4,h/2,d/2,(w-dw)/2,h,.20,wall);block(walls,0,(h+dh)/2,d/2,dw,h-dh,.20,wall);}
    const panels=group(room,'stay-room-panelling'),panelHeight=spec.panelHeight??1.3;
    for(const side of [-1,1]) {
      block(panels,side*(w/2-.13),panelHeight/2,0,.06,panelHeight,d-.10,wood);
      for(let z=-d/2+.5;z<d/2;z+=1.05) {
        for(const y of [.18,panelHeight-.13])block(panels,side*(w/2-.18),y,z,.06,.055,.86,gold);
        for(const zz of [z-.43,z+.43])block(panels,side*(w/2-.18),panelHeight/2,zz,.06,panelHeight-.30,.055,gold);
      }
      for(const y of [panelHeight+.12,h-.25])block(panels,side*(w/2-.15),y,0,.09,.08,d,wall);
    }
    if(spec.wallFrames) {
      const frames=group(room,'stay-wall-frames'),fw=Math.min(1.6,w*.20),lo=panelHeight+.3,hi=h-.5;
      for(const side of [-1,1]) {
        const x=side*w*.31,z=-d/2+.14;
        for(const y of [lo,hi])block(frames,x,y,z,fw,.035,.035,gold);
        for(const dx of [-fw/2,fw/2])block(frames,x+dx,(lo+hi)/2,z,.035,hi-lo,.035,gold);
        block(frames,side*w*.44,h/2,z,.16,h-.2,.08,wall);
      }
    }
    const furnishings=group(room,'stay-lounge-furniture');
    if(spec.reception) {
      const p=spec.reception,[x,y,z]=p.position||[0,0,-d/2+.8],width=p.width??3,height=p.height??1.02,depth=p.depth??.7,counter=group(furnishings,'stay-reception-counter',[x,y,z]);
      if(p.openShelves) {
        block(counter,0,.16,0,width,.10,depth,wood);block(counter,0,height/2,-depth/2+.04,width,height,.08,wood);
        for(const x of [-width/2,width/2])block(counter,x,height/2,0,.10,height,depth,wood);block(counter,0,height/2,0,.08,height,depth,wood);
        const cups=[];for(let k=0;k<7;k++)cups.push({p:[-.8+k*.2,.27,.06],s:[.055,.07,.055]});instances(counter,'stay-reception-cups',new THREE.CylinderGeometry(1,.8,1,8),cups,C.trim);
      } else {block(counter,0,height/2,0,width,height,depth,wood);for(let xx=-width/2+.12;xx<width/2;xx+=.12)block(counter,xx,height/2,depth/2+.015,.024,height-.14,.028,gold);}
      block(counter,0,height+.04,0,width+.16,.08,depth+.14,p.topColor||'#d6d2c5');
      block(counter,0,height+.07,-depth/2+.12,.48,.06,.34,'#777d72');
      const backdrop=group(furnishings,'stay-reception-backdrop',[0,0,-d/2+.14]),bw=p.backdropWidth??Math.min(w-1,width+1),bh=p.backdropHeight??h-.35;
      block(backdrop,0,bh/2,0,bw,bh,.10,wood);
      for(let yy=.12;yy<bh;yy+=.13)block(backdrop,0,yy,.065,bw,.018,.025,gold);
      if(p.text)sign(backdrop,p.text,bw*.8,.65,p.textColor||gold,wood,110).position.set(0,bh*.70,.09);
    }
    if(spec.fireplace!==false) {
      const fw=spec.fireplace?.width??2.5;block(furnishings,0,.72,-d/2+.24,fw,1.44,.46,C.stone);block(furnishings,0,.62,-d/2+.49,fw*.63,1.10,.04,'#71685c');block(furnishings,0,1.49,-d/2+.3,fw+.32,.16,.65,wall);
      block(furnishings,0,2.55,-d/2+.15,fw*.82,1.70,.08,gold);block(furnishings,0,2.55,-d/2+.21,fw*.82-.14,1.56,.06,'#acb6ae');
    }
    const chairColor=spec.upholsteryColor||'#a7b4aa',chairs=spec.chairs||[[-2,-1,0],[2,-1,0],[-2,1,Math.PI],[2,1,Math.PI]];
    for(const [x,z,a=0] of chairs) {
      const chair=group(furnishings,'stay-club-chair',[x,0,z],a);block(chair,0,.44,0,.82,.16,.82,chairColor);block(chair,0,.77,-.37,.88,.65,.18,chairColor);for(const side of [-1,1])block(chair,side*.41,.65,0,.17,.3,.82,chairColor);for(const xx of [-.28,.28])for(const zz of [-.28,.28])block(chair,xx,.18,zz,.07,.36,.07,wood);
    }
    for(const [x,z,a=0,width=1.8] of spec.sofas||[]) {
      const sofa=group(furnishings,'stay-sofa',[x,0,z],a);block(sofa,0,.43,0,width,.18,.82,chairColor);block(sofa,0,.70,-.38,width,.60,.15,chairColor);
      for(const side of [-1,1]){block(sofa,side*(width/2-.07),.59,0,.14,.34,.82,chairColor);for(const zz of [-.29,.29])block(sofa,side*(width/2-.22),.17,zz,.07,.34,.07,wood);}
      for(let xx=-width/2+.35;xx<width/2-.15;xx+=.65)block(sofa,xx,.66,-.20,.46,.34,.12,spec.cushionColor||'#c6b5a8');
    }
    const table=spec.table||[0,0],tx=table[0],tz=table[1];add(furnishings,new THREE.CylinderGeometry(.62,.62,.08,24),wood,[tx,.65,tz]);add(furnishings,new THREE.CylinderGeometry(.08,.18,.61,12),wood,[tx,.305,tz]);
    add(furnishings,new THREE.CylinderGeometry(.10,.14,.26,12),gold,[tx,.82,tz]);add(furnishings,leaf,'#b397a2',[tx,1.03,tz],[.24,.18,.24]);
    if(spec.carpet!==false)block(furnishings,0,.010,tz,Math.min(w-1,spec.carpet?.[0]??4.6),.008,spec.carpet?.[1]??3.6,spec.carpetColor||'#9e9f8f');
    const curtains=group(room,'stay-curtains');for(const z of spec.windows||[-2.5,1.6])for(const side of [-1,1]) {
      const win=group(curtains,'stay-inner-window',[side*(w/2-.18),0,z],side===1?-Math.PI/2:Math.PI/2);windowBay(win,0,.65,0,1.6,h-1.1,false,wall,'#b9c6bb',true);
      for(const xx of [-1,1])block(win,xx, h/2+.2,.12,.32,h-.4,.20,spec.curtainColor||'#9da99b');
    }
    const ceiling=group(new THREE.Group(),'stay-sealed-ceiling');ceiling.position.fromArray(offset);ceiling.position.y+=h-roof.position.y;ceiling.rotation.y=spec.facing===-1?Math.PI:0;
    block(ceiling,0,-.04,0,w+.4,.16,d+.4,wall);
    for(const side of [-1,1]){block(ceiling,side*(w/2-.20),-.17,0,.20,.18,d,wall);block(ceiling,0,-.17,side*(d/2-.20),w,.18,.20,wall);}
    const coffer=group(ceiling,'stay-coffer-linework');
    if(spec.ceilingGrid!==false) {
      const [columns,rows]=spec.ceilingGrid||[2,3],cw=w/columns,cd=d/rows;
      for(let i=1;i<columns;i++)block(coffer,-w/2+i*cw,-.17,0,.14,.16,d,wall);
      for(let i=1;i<rows;i++)block(coffer,0,-.17,-d/2+i*cd,w,.16,.14,wall);
      for(let i=0;i<columns;i++)for(let j=0;j<rows;j++) {
        const x=-w/2+(i+.5)*cw,z=-d/2+(j+.5)*cd;
        for(const side of [-1,1]) {
          block(coffer,x+side*(cw/2-.22),-.13,z,.045,.05,cd-.44,wall);
          block(coffer,x,-.13,z+side*(cd/2-.22),cw-.44,.05,.045,wall);
        }
      }
    }
    if(spec.chandelier!==false) {
      const z=spec.chandelier?.z??-1,drop=spec.chandelier?.drop??1.0,cy=h-drop;
      block(furnishings,0,(h+cy)/2,z,.025,drop,.025,gold);
      for(let k=0;k<8;k++) {
        const a=k*Math.PI/4,x=Math.cos(a)*.48,zz=z+Math.sin(a)*.48;
        const path=new THREE.CatmullRomCurve3([new THREE.Vector3(0,cy+.12,z),new THREE.Vector3(x*.6,cy-.15,z+(zz-z)*.6),new THREE.Vector3(x,cy,zz)]);
        add(furnishings,new THREE.TubeGeometry(path,8,.022,5,false),gold);add(furnishings,new THREE.SphereGeometry(.075,8,6),'#d9cfad',[x,cy+.13,zz]);
      }
    }
    flush();return {group:room,ceiling,front:shell.userData.frontLayer,door:shell.userData.interiorDoor};
  });
})();
