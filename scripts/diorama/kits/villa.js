// Parametric European villas and low, terrain-following landscape elements.
(() => {
  const colors={wall:'#eee9db',timber:'#645c4e',glass:'#a9b9b3',shutter:'#6f8372',roof:'#ad7760',ivy:'#87987c'};
  function pack(group,excluded=[]) {
    group.updateWorldMatrix(true,true);
    const inverse=group.matrixWorld.clone().invert(),buckets=new Map(),parts=[];
    group.traverse(part=>{
      if(part.isInstancedMesh||!(part.isMesh||part.isLineSegments)||excluded.some(e=>{let p=part;while(p){if(p===e)return true;p=p.parent;}return false;}))return;
      if(['villa-foundation','villa-roof','villa-rounded-corner','villa-entry-step','villa-chimney','reception-sign','villa-flag','villa-flat-rounded-foundation','villa-flat-canopy-column'].includes(part.name)||part.parent?.name==='villa-roof')return;
      const key=(part.isMesh?'mesh:':'line:')+part.material.uuid;
      if(!buckets.has(key))buckets.set(key,{material:part.material,line:part.isLineSegments,geometries:[]});
      buckets.get(key).geometries.push(part.geometry.clone().applyMatrix4(inverse.clone().multiply(part.matrixWorld)));
      parts.push(part);
    });
    for(const part of parts)part.removeFromParent();
    for(const {material:mat,line:lines,geometries} of buckets.values()) {
      const geometry=mergeGeometries(geometries.map(g=>g.index?g.toNonIndexed():g),false);
      const merged=lines?new THREE.LineSegments(geometry,mat):new THREE.Mesh(geometry,mat);
      merged.name=lines?'villa-batched-linework':'villa-batched-detail';merged.castShadow=!lines;merged.receiveShadow=!lines;group.add(merged);
      for(const g of geometries)g.dispose();
    }
  }
  function solid(parent,geometry,color,name,x=0,y=0,z=0,outlined=true) {
    const part=mesh(geometry,color,x,y,z,outlined);part.name=name;parent.add(part);return part;
  }
  function block(parent,name,x,y,z,w,h,d,color) {
    return solid(parent,new THREE.BoxGeometry(w,h,d),color,name,x,y,z);
  }
  function line(parent,a,b,width,color=colors.timber) {
    const start=new THREE.Vector3(...a),end=new THREE.Vector3(...b),delta=end.clone().sub(start);
    const part=solid(parent,new THREE.BoxGeometry(width,delta.length(),width),color,'villa-line',...start.add(end).multiplyScalar(.5).toArray(),false);
    part.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),delta.normalize());return part;
  }
  function instances(parent,name,geometry,entries,color) {
    const part=new THREE.InstancedMesh(geometry,material(color),entries.length),dummy=new THREE.Object3D();
    if(geometry.userData.doubleSide){part.material=part.material.clone();part.material.side=THREE.DoubleSide;}
    part.name=name;parent.add(part);part.castShadow=true;part.receiveShadow=true;
    for(const [i,e] of entries.entries()) {
      dummy.position.set(...e.position);dummy.scale.set(...(e.scale||[1,1,1]));
      dummy.rotation.set(...(e.rotation||[0,0,0]));dummy.updateMatrix();part.setMatrixAt(i,dummy.matrix);
      if(e.color)part.setColorAt(i,new THREE.Color(e.color));
    }
    part.instanceMatrix.needsUpdate=true;part.computeBoundingBox();parent.updateWorldMatrix(true,false);
    if(currentEnvelope&&part.boundingBox)for(const x of [part.boundingBox.min.x,part.boundingBox.max.x])for(const y of [part.boundingBox.min.y,part.boundingBox.max.y])for(const z of [part.boundingBox.min.z,part.boundingBox.max.z])currentEnvelope.push(new THREE.Vector3(x,y,z).applyMatrix4(parent.matrixWorld));
    return part;
  }
  function ivyLeafGeometry() {
    const positions=[],corners=[[0,1,0],[-1,0,0],[0,-1,0],[1,0,0]];
    for(let i=0;i<4;i++)positions.push(0,0,.5,...corners[i],...corners[(i+1)%4]);
    const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));geometry.computeVertexNormals();geometry.userData.doubleSide=true;
    return geometry;
  }
  function frontGable(parent,x,y,z,width,rise,depth,color,timber=true,faceColor='#bccdb1') {
    const gable=new THREE.Group();gable.position.set(x,y,z);parent.add(gable);
    const cross=new THREE.Group();cross.rotation.y=Math.PI/2;cross.position.z=-depth/2;gable.add(cross);
    roof(cross,depth,width,rise,'gable',color,false);
    const shape=new THREE.Shape();shape.moveTo(-width/2,0);shape.lineTo(width/2,0);shape.lineTo(0,rise);shape.closePath();
    const face=solid(gable,new THREE.ShapeGeometry(shape),faceColor,'villa-front-gable-face',0,0,.035,false);
    face.material=face.material.clone();face.material.side=THREE.DoubleSide;
    if(timber) {
      line(gable,[-width/2,0,.10],[0,rise,.10],.14);line(gable,[width/2,0,.10],[0,rise,.10],.14);
      line(gable,[-width/2,.06,.10],[width/2,.06,.10],.14);
      for(let i=-3;i<=3;i++) {
        const dx=i*width/8,top=rise*(1-Math.abs(dx)/(width/2));
        line(gable,[dx,0,.10],[dx,top,.10],.095);
        if(i<3){const end=dx+width/8;line(gable,[dx,.05,.11],[end,rise*(1-Math.abs(end)/(width/2))*.76,.11],.075);}
      }
    }
    return gable;
  }
  function roof(parent,w,d,rise,kind,color,tileCourses=true) {
    const ridge=kind==='hip'?Math.max(0,w/2-d*.42):w/2,points=[];
    const A=[-w/2,0,-d/2],B=[w/2,0,-d/2],C=[w/2,0,d/2],D=[-w/2,0,d/2],L=[-ridge,rise,0],R=[ridge,rise,0];
    const triangle=(a,b,c)=>points.push(...a,...b,...c);
    triangle(A,L,R);triangle(A,R,B);triangle(D,C,R);triangle(D,R,L);
    if(kind==='hip'){triangle(A,D,L);triangle(B,R,C);}
    const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(points,3));geometry.computeVertexNormals();
    const part=solid(parent,geometry,color,'villa-roof');part.material=part.material.clone();part.material.side=THREE.DoubleSide;
    for(const [a,b] of [[A,B],[B,C],[C,D],[D,A],[L,R]])line(parent,a,b,.13,color);
    // Fine tile courses, quieter than the structural edges.
    if(tileCourses)for(const side of [-1,1])for(let i=1;i<Math.ceil(d/.8);i++) {
      const t=i/Math.ceil(d/.8),z=side*d/2*(1-t),y=rise*t+.035+.025*rise/d;
      const extent=kind==='hip'?w/2-(w/2-ridge)*t:w/2;
      line(parent,[-extent,y,z],[extent,y,z],.025,'#b78b74');
    }
    if(kind==='gable')for(const side of [-1,1]) {
      const s=new THREE.Shape();s.moveTo(-d/2,0);s.lineTo(d/2,0);s.lineTo(0,rise);s.closePath();
      const g=new THREE.ShapeGeometry(s);g.rotateY(Math.PI/2);
      const endX=side*(w/2-.9);
      const end=solid(parent,g,colors.wall,'villa-gable',endX,0,0);end.material=end.material.clone();end.material.side=THREE.DoubleSide;
      line(parent,[endX,.1,-d/2],[endX,rise,0],.12);
      line(parent,[endX,.1,d/2],[endX,rise,0],.12);
      for(let k=-2;k<=2;k++)line(parent,[endX+side*.025,.05,k*d/6],[endX+side*.025,rise*(1-Math.abs(k)/3),k*d/6],.10);
    }
    return part;
  }
  function windowBay(parent,x,y,z,w,h,shutters=false,rotation=0) {
    const bay=new THREE.Group();bay.position.set(x,y,z);bay.rotation.y=rotation;parent.add(bay);
    block(bay,'villa-window-recess',0,0,0,w+.18,h+.16,.12,colors.timber);
    block(bay,'villa-window-glass',0,0,.075,w,h,.06,colors.glass);
    for(const dx of [-w/2,0,w/2])block(bay,'villa-window-frame',dx,0,.13,.065,h+.1,.075,colors.wall);
    for(const dy of [-h/2,0,h/2])block(bay,'villa-window-frame',0,dy,.13,w+.12,.065,.075,colors.wall);
    block(bay,'villa-window-sill',0,-h/2-.12,.15,w+.4,.13,.38,colors.wall);
    if(shutters)for(const side of [-1,1]) {
      block(bay,'villa-shutter',side*(w*.78),0,.09,w*.43,h+.14,.12,colors.shutter);
      for(let i=0;i<8;i++)block(bay,'villa-shutter-slat',side*(w*.78),-h/2+.14+i*(h-.18)/8,.17,w*.36,.045,.045,'#92a08a');
    }
  }
  function flatVilla(object) {
    const [cx,,cz]=object.position,[w,d]=object.footprint,angle=object.rotation||0;
    const outline=object.outline||[[-w/2,-d/2],[w/2,-d/2],[w/2,d/2],[-w/2,d/2]];
    const world=([x,z])=>[cx+Math.cos(angle)*x+Math.sin(angle)*z,cz-Math.sin(angle)*x+Math.cos(angle)*z];
    const ground=outline.map(p=>hillSurfaceHeight(...world(p))),floor=Math.max(...ground)+.18,bottom=Math.min(...ground)-.22;
    const root=new THREE.Group();root.name=object.id+'-villa';root.position.set(cx,floor,cz);root.rotation.y=angle;scene.add(root);
    root.userData={floorY:floor,footprint:outline.map(world)};
    const level=object.storeyHeight||3.6,H=(object.storeys||2)*level,wall=object.wallColor||'#d4c4a4';
    const shape=new THREE.Shape(outline.map(([x,z])=>new THREE.Vector2(x,-z)));
    const slab=(parent,name,y,height,color)=>{
      const geometry=new THREE.ExtrudeGeometry(shape,{depth:height,bevelEnabled:false});geometry.rotateX(-Math.PI/2);
      return solid(parent,geometry,color,name,0,y,0);
    };
    slab(root,'villa-foundation',bottom-floor,floor-bottom,'#b9b4a4');
    if(!object.interior)slab(root,'villa-flat-walls',0,H,wall);
    else {
      const front=new THREE.Group();front.name='villa-front-layer';root.add(front);root.userData.frontLayer=front;
      const {doorX,doorZ,doorWidth=2.8,doorHeight=3}=object.interior;
      for(let i=0;i<outline.length;i++) {
        const a=outline[i],b=outline[(i+1)%outline.length],length=Math.hypot(b[0]-a[0],b[1]-a[1]);
        if(length<.001)continue;
        const angle=Math.atan2(-(b[1]-a[1]),b[0]-a[0]);
        if(Math.abs(a[1]-doorZ)<.1&&Math.abs(b[1]-doorZ)<.1&&doorX>Math.min(a[0],b[0])&&doorX<Math.max(a[0],b[0])) {
          for(const [lo,hi] of [[Math.min(a[0],b[0]),doorX-doorWidth/2],[doorX+doorWidth/2,Math.max(a[0],b[0])]])block(front,'villa-shell-wall',(lo+hi)/2,H/2,doorZ,hi-lo,H,.24,wall);
          block(front,'villa-door-lintel',doorX,(H+doorHeight)/2,doorZ,doorWidth,H-doorHeight,.24,wall);
        } else {
          const p=block(root,'villa-shell-wall',(a[0]+b[0])/2,H/2,(a[1]+b[1])/2,length,H,.24,wall);p.rotation.y=angle;
        }
      }
    }
    const roofGroup=new THREE.Group();roofGroup.name=object.id+'-roof';roofGroup.position.y=H;root.add(roofGroup);
    slab(roofGroup,'villa-flat-roof',0,.16,object.roof.color||'#c7c5b7');
    const joints=[],pitch=object.tilePattern?.pitch||.65,jointColor=object.tilePattern?.color||'#e0d3b9';
    const detailGroups=[],bands=new THREE.Group();bands.name='villa-window-bands';
    if(object.windowBands){root.add(bands);detailGroups.push(bands);}
    const signedArea=outline.reduce((s,a,i)=>{const b=outline[(i+1)%outline.length];return s+a[0]*b[1]-b[0]*a[1];},0);
    for(let i=1;i<=outline.length;i++) {
      const a=outline[i-1],b=outline[i%outline.length],dx=b[0]-a[0],dz=b[1]-a[1],length=Math.hypot(dx,dz);
      if(length<.001)continue;
      const nx=(signedArea>0?1:-1)*dz/length,nz=(signedArea>0?-1:1)*dx/length,rotation=Math.atan2(nx,nz);
      const at=(t,offset=.04)=>[a[0]+dx*t+nx*offset,a[1]+dz*t+nz*offset];
      const doorEdge=object.interior&&Math.abs(a[1]-object.interior.doorZ)<.1&&Math.abs(b[1]-object.interior.doorZ)<.1;
      const doorRange=doorEdge?[(object.interior.doorX-object.interior.doorWidth/2-a[0])/dx,(object.interior.doorX+object.interior.doorWidth/2-a[0])/dx].sort((a,b)=>a-b):null;
      for(const y of [.16,level-.12,H-.14]) {
        const [x,z]=at(.5,.07);const band=block(root,'villa-horizontal-course',x,y,z,length+.06,.12,.15,'#e7ddc7');band.rotation.y=rotation;
      }
      const [rx,rz]=at(.5);const parapet=block(roofGroup,'villa-flat-parapet',rx,.25,rz,length+.08,.34,.16,wall);parapet.rotation.y=rotation;
      const coping=block(roofGroup,'villa-parapet-coping',rx,.46,rz,length+.18,.08,.30,'#e8dfcb');coping.rotation.y=rotation;
      if(length>2)for(let k=0;k<Math.max(1,Math.round(length/2.8));k++) {
        const t=(k+.5)/Math.max(1,Math.round(length/2.8)),[x,z]=at(t,.11);
        for(let s=0;s<(object.storeys||2);s++)if(!(object.windowBands?.levels.includes(s)&&length>=(object.windowBands.minSpan||7)))windowBay(root,x,s*level+level*.54,z,Math.min(1.7,length*.5),1.55,false,rotation);
      }
      if(object.windowBands&&length>=(object.windowBands.minSpan||7))for(const s of object.windowBands.levels) {
        const y=s*level+level*.54,ranges=doorRange&&y<3?[[0,doorRange[0]],[doorRange[1],1]]:[[0,1]];
        for(const [lo,hi] of ranges) {
        const [x,z]=at((lo+hi)/2,.11),span=(hi-lo)*length-.9;
        if(span<=.1)continue;
        windowBay(bands,x,y,z,span,1.55,false,rotation);
        for(let q=.6;q<span;q+=object.windowBands.mullionSpacing||1.1) {
          const [mx,mz]=at(lo+(q+.45)/length,.24),m=block(bands,'villa-band-mullion',mx,y,mz,.065,1.66,.08,'#e6dcc7');m.rotation.y=rotation;
        }
        }
      }
      if(object.tilePattern) {
        const offset=object.interior?.124:.008;
        for(let q=pitch;q<length;q+=pitch){const [x,z]=at(q/length,offset),low=doorRange&&q/length>doorRange[0]&&q/length<doorRange[1]?object.interior.doorHeight:0;joints.push({position:[x,(H+low)/2,z],scale:[.024,H-low,.024],rotation:[0,rotation,0]});}
        for(let y=pitch;y<H;y+=pitch)for(const [lo,hi] of doorRange&&y<3?[[0,doorRange[0]],[doorRange[1],1]]:[[0,1]]){const [x,z]=at((lo+hi)/2,offset);joints.push({position:[x,y,z],scale:[length*(hi-lo),.024,.024],rotation:[0,rotation,0]});}
      }
    }
    if(object.rounded) {
      const {x,z,radius:radius=3.8,rise:rise=1.1}=object.rounded;
      if(!object.interior)solid(root,new THREE.CylinderGeometry(radius,radius,H+rise,48),wall,'villa-rounded-corner',x,(H+rise)/2,z);
      else {
        const shell=new THREE.Group();shell.name='villa-rounded-corner';root.add(shell);
        const gap=Math.asin((object.interior.doorWidth||2.8)/(2*radius));
        for(const side of [-1,1]) {
          const s=new THREE.Shape(),points=[];
          for(let i=0;i<=32;i++){const a=side*(gap+(Math.PI/2-gap)*i/32);points.push([Math.sin(a)*radius,Math.cos(a)*radius]);}
          for(let i=32;i>=0;i--){const a=side*(gap+(Math.PI/2-gap)*i/32);points.push([Math.sin(a)*(radius-.24),Math.cos(a)*(radius-.24)]);}
          points.forEach(([px,pz],i)=>i?s.lineTo(px,-pz):s.moveTo(px,-pz));s.closePath();
          const g=new THREE.ExtrudeGeometry(s,{depth:H+rise,bevelEnabled:false});g.rotateX(-Math.PI/2);solid(shell,g,wall,'villa-rounded-shell',x,0,z);
        }
        const lintel=solid(shell,new THREE.CylinderGeometry(radius,radius,H+rise-3,48,1,false,-gap,2*gap),wall,'villa-rounded-door-lintel',x,3+(H+rise-3)/2,z);
        lintel.material=lintel.material.clone();lintel.material.side=THREE.DoubleSide;
      }
      solid(root,new THREE.CylinderGeometry(radius,radius,floor-bottom,48),'#b9b4a4','villa-flat-rounded-foundation',x,(bottom-floor)/2,z);
      for(const y of [level+.15,level+1.6]) {
        const ring=solid(root,new THREE.CylinderGeometry(radius+.05,radius+.05,.10,48),'#e6dcc7','villa-rounded-course',x,y,z);
        ring.name='villa-rounded-course';
      }
      const band=new THREE.Group();band.name='villa-curved-window-band';root.add(band);
      for(let i=0;i<16;i++) {
        const a=-Math.PI/2+i/15*Math.PI,px=x+Math.sin(a)*(radius+.055),pz=z+Math.cos(a)*(radius+.055);
        const pane=block(band,'villa-rounded-glass',px,level+.88,pz,.70,1.20,.06,colors.glass);pane.rotation.y=a;
        const mullion=block(band,'villa-rounded-mullion',px,level+.88,pz,.055,1.35,.12,'#e6dcc7');mullion.rotation.y=a;
      }
      solid(roofGroup,new THREE.CylinderGeometry(radius+.14,radius+.14,.13,48),'#e5dbc5','villa-rounded-roof',x,rise+.055,z);
      if(object.tilePattern) {
        for(let i=0;i<Math.ceil(Math.PI*2*radius/pitch);i++) {
          const a=i/Math.ceil(Math.PI*2*radius/pitch)*Math.PI*2;
          if(object.interior&&Math.cos(a)<0)continue;
          const low=object.interior&&Math.cos(a)>0&&Math.abs(Math.sin(a)*radius)<object.interior.doorWidth/2?3:0;
          joints.push({position:[x+Math.sin(a)*(radius+.024),(H+rise+low)/2,z+Math.cos(a)*(radius+.024)],scale:[.030,H+rise-low,.030]});
        }
        for(let y=pitch;y<H+rise;y+=pitch) {
          const gap=object.interior&&y<3?Math.asin(object.interior.doorWidth/(2*radius)):0;
          const arcs=object.interior?(gap?[[0,Math.PI/2-gap],[Math.PI/2+gap,Math.PI]]:[[0,Math.PI]]):[[0,Math.PI*2]];
          for(const [lo,hi] of arcs){const geometry=new THREE.TorusGeometry(radius+.025,.015,4,96,hi-lo);geometry.rotateZ(lo);
          const ring=solid(root,geometry,jointColor,'villa-rounded-tile-course',x,y,z,false);ring.rotation.x=Math.PI/2;}
        }
      }
      if(object.flagpole) {
        const top=H+rise,pole=object.flagpole.height||5.5;
        solid(root,new THREE.CylinderGeometry(.035,.055,pole,8),'#a59e87','villa-flagpole',x,top+pole/2,z);
        const flagShape=new THREE.Shape();flagShape.moveTo(0,0);flagShape.lineTo(1.5,-.18);flagShape.lineTo(1.32,-1.06);flagShape.lineTo(0,-.90);flagShape.closePath();
        const flag=solid(root,new THREE.ShapeGeometry(flagShape),'#a16c64','villa-flag',x+.04,top+pole-.18,z,false);flag.material=flag.material.clone();flag.material.side=THREE.DoubleSide;
        const star=new THREE.Shape();for(let i=0;i<10;i++){const a=Math.PI/2+i*Math.PI/5,r=i%2?.09:.22;const xx=.72+Math.cos(a)*r,yy=-.52+Math.sin(a)*r;if(i)star.lineTo(xx,yy);else star.moveTo(xx,yy);}star.closePath();
        const emblem=solid(root,new THREE.ShapeGeometry(star),'#d8c797','villa-flag-emblem',x+.04,top+pole-.18,z+.012,false);emblem.material=emblem.material.clone();emblem.material.side=THREE.DoubleSide;
      }
    }
    if(object.towerBlock) {
      const {position:[x,y,z],size:[tw,th,td]}=object.towerBlock;
      const tower=new THREE.Group();tower.name='villa-tower-block';roofGroup.add(tower);
      block(tower,'villa-tower-wall',x,y+th/2,z,tw,th,td,wall);
      block(tower,'villa-tower-coping',x,y+th+.08,z,tw+.35,.16,td+.35,'#e6ddc8');
      for(const side of [-1,1])windowBay(tower,x,y+th*.5,z+side*(td/2+.04),tw*.55,.6,false,side>0?0:Math.PI);
    }
    if(object.porteCochere) {
      const {x,z,width:pw,depth:pd,height:ph}=object.porteCochere;
      const canopy=new THREE.Group();canopy.name='villa-porte-cochere';root.add(canopy);
      detailGroups.push(canopy);
      const s=new THREE.Shape();s.moveTo(-pw/2,0);s.lineTo(pw/2,0);s.lineTo(pw/2,-pd+pw*.20);s.quadraticCurveTo(pw/2,-pd,0,-pd);s.quadraticCurveTo(-pw/2,-pd,-pw/2,-pd+pw*.20);s.closePath();
      const geometry=new THREE.ExtrudeGeometry(s,{depth:.24,bevelEnabled:false,curveSegments:32});geometry.rotateX(-Math.PI/2);
      solid(canopy,geometry,'#ded8c4','villa-curved-canopy',x,ph,z);
      for(const side of [-1,1]) {
        const px=x+side*pw*.34,pz=z+pd*.77,base=hillSurfaceHeight(...world([px,pz]))-floor;
        solid(canopy,new THREE.CylinderGeometry(.14,.18,ph-base,12),'#d6cfb9','villa-flat-canopy-column',px,(ph+base)/2,pz);
      }
      const doorZ=object.rounded?object.rounded.z+object.rounded.radius+.06:z;
      const door=new THREE.Group();door.name='villa-palace-door';root.add(door);
      block(door,'villa-door-timber',x,1.5,doorZ,2.8,3,.18,colors.timber);
      for(const dx of [-.73,.73])block(door,'villa-palace-door-glass',x+dx,1.8,doorZ+.13,1.24,1.9,.05,colors.glass);
      if(object.interior)root.userData.interiorDoor=door;
      root.updateWorldMatrix(true,true);
      const envelope=new THREE.Box3().setFromObject(canopy);
      if(object.rounded)envelope.union(new THREE.Box3().setFromObject(root.getObjectByName('villa-rounded-corner')));
      const points=[];for(const px of [envelope.min.x,envelope.max.x])for(const py of [envelope.min.y,envelope.max.y])for(const pz of [envelope.min.z,envelope.max.z])points.push(new THREE.Vector3(px,py,pz));
      modelEnvelopes.set(object.id+'-entrance',points);
    }
    if(joints.length)instances(root,'villa-tile-joints',new THREE.BoxGeometry(1,1,1),joints,jointColor);
    roofRecords.push({group:roofGroup,parameters:{width:w,depth:d,ridgeHeight:H+(object.towerBlock?.size[1]||.6),kind:'flat'},tiers:1,thickness:.16,ridgeOrnament:false});
    if(object.interior)root.userData.frontLayer.traverse(p=>{if(p.material)p.material=p.material.clone();});
    for(const group of detailGroups)pack(group);
    pack(roofGroup);pack(root,[roofGroup,...detailGroups,...(object.interior?[root.userData.frontLayer,root.userData.interiorDoor]:[])]);
  }
  registerObjectType('villa',object=>{
    if(['aframe','steep_gable'].includes(object.roof?.kind))return cottage(object);
    if(object.roof?.kind==='flat')return flatVilla(object);
    const [cx,,cz]=object.position,[w,d]=object.footprint,angle=object.rotation||0;
    const local=(x,z)=>[cx+Math.cos(angle)*x+Math.sin(angle)*z,cz-Math.sin(angle)*x+Math.cos(angle)*z];
    const corners=[[-w/2-.5,-d/2-.5],[w/2+.5,-d/2-.5],[w/2+.5,d/2+3],[-w/2-.5,d/2+3]].map(([x,z])=>local(x,z));
    const ground=corners.map(([x,z])=>hillSurfaceHeight(x,z)),floor=Math.max(...ground)+.18,bottom=Math.min(...ground)-.22;
    const root=new THREE.Group();root.name=object.id+'-villa';root.position.set(cx,floor,cz);root.rotation.y=angle;scene.add(root);
    root.userData={floorY:floor,footprint:corners};
    const storeys=object.storeys||2,level=object.storeyHeight||3.2,H=storeys*level,wall=object.ivy?'#56664b':object.wallColor||colors.wall;
    block(root,'villa-foundation',0,(bottom-floor)/2,object.veranda?1:0,w+.9,floor-bottom,d+(object.veranda?3.8:.9),'#d6d0c1');
    const frontLayer=new THREE.Group();frontLayer.name='villa-front-layer';root.add(frontLayer);
    if(object.interior) {
      block(root,'villa-back-wall',0,H/2,-d/2+.12,w,H,.24,wall);
      for(const side of [-1,1])block(root,'villa-side-wall',side*(w/2-.12),H/2,0,.24,H,d,wall);
      for(const side of [-1,1])block(frontLayer,'villa-front-wall',side*(w/4+.4),H/2,d/2-.12,w/2-.8,H,.24,wall);
      block(frontLayer,'villa-door-lintel',0,(H+2.6)/2,d/2-.12,1.6,H-2.6,.24,wall);
      const door=block(frontLayer,'villa-entrance-door',0,1.25,d/2+.02,1.48,2.5,.15,colors.timber);
      root.userData.interiorDoor=door;root.userData.frontLayer=frontLayer;
      for(const y of [.23,level,H-.18]) {
        for(const side of [-1,1])block(root,'villa-stringcourse',side*w/2,y,0,.16,.14,d+.18,'#dcd5c6');
        block(root,'villa-stringcourse',0,y,-d/2,w+.18,.14,.16,'#dcd5c6');
      }
    } else {
      block(root,'villa-wall',0,H/2,0,w,H,d,wall);
      for(const y of [.23,level,H-.18])block(root,'villa-stringcourse',0,y,0,w+.18,.14,d+.18,'#dcd5c6');
    }
    const bays=Math.max(3,Math.round(w/4)),spacing=w/(bays+1);
    for(let levelIndex=0;levelIndex<storeys;levelIndex++)for(let i=1;i<=bays;i++) {
      const x=-w/2+spacing*i,y=levelIndex*level+level*.53;
      if(i===Math.ceil(bays/2)&&levelIndex===0) {
        if(!object.interior) {
          block(root,'villa-door',x,1.25,d/2+.06,1.25,2.5,.16,colors.timber);
          block(root,'villa-door-light',x,1.6,d/2+.16,.88,1.3,.08,colors.glass);
        }
      } else windowBay(root,x,y,d/2+.05,object.rounded?2.35:1.25,1.72,object.shutters);
      windowBay(root,x,y,-d/2-.05,1.2,1.72,object.shutters,Math.PI);
    }
    for(const side of [-1,1])for(let k=0;k<storeys;k++)for(const z of [-d*.26,d*.26])windowBay(root,side*(w/2+.05),k*level+level*.53,z,1.15,1.7,object.shutters,side*Math.PI/2);
    if(object.timber) {
      for(const side of [-1,1]) {
        const z=side*(d/2+.18);
        for(const y of [level,level+.9,H-.12])line(root,[-w/2,y,z],[w/2,y,z],.13);
        for(let i=0;i<=bays+1;i++) {
          const x=-w/2+spacing*i;line(root,[x,level,z],[x,H,z],.13);
          if(i<bays+1)line(root,[x,level+.1,z],[x+spacing*.6,H-.15,z],.10);
        }
      }
      for(const side of [-1,1])for(const z of [-d/2,0,d/2])line(root,[side*(w/2+.12),level,z],[side*(w/2+.12),H,z],.14);
    }
    if(object.veranda) {
      const veranda=new THREE.Group();veranda.name='villa-veranda';root.add(veranda);
      const front=d/2+2.6;
      block(veranda,'villa-veranda-floor',0,level-.10,d/2+1.32,w+.3,.24,2.8,'#d8d2c3');
      // Piers and curved spandrels leave the ground-floor arcade genuinely open.
      const n=object.interior&&bays%2===0?bays-1:bays,span=w/n;
      for(let i=0;i<=n;i++)block(veranda,'villa-arcade-pier',-w/2+i*span,level/2,front,.36,level,.44,wall);
      for(let i=0;i<n;i++) {
        const shape=new THREE.Shape(),r=(span-.36)/2,b=level-1.05;
        shape.moveTo(-span/2,level);shape.lineTo(span/2,level);shape.lineTo(span/2,b);
        for(let j=0;j<=24;j++){const a=j/24*Math.PI;shape.lineTo(Math.cos(a)*r,b+Math.sin(a)*.85);}
        shape.lineTo(-span/2,b);shape.closePath();
        solid(veranda,new THREE.ExtrudeGeometry(shape,{depth:.38,bevelEnabled:false}),wall,'villa-arch',-w/2+(i+.5)*span,0,front-.19);
      }
      for(const y of [level+.2,level+1.02])line(veranda,[-w/2,y,front],[w/2,y,front],.105);
      for(let x=-w/2;x<=w/2+.01;x+=.48)line(veranda,[x,level+.2,front],[x,level+1.02,front],.065);
      if(object.lattice) {
        const lattice=new THREE.Group();lattice.name='villa-lattice-railing';veranda.add(lattice);
        for(let x=-w/2;x<w/2-.48;x+=.48)for(const side of [-1,1])line(lattice,[x,level+(side>0?.24:.96),front+.035],[x+.48,level+(side>0?.96:.24),front+.035],.045);
      }
      for(let i=0;i<=n;i++)line(veranda,[-w/2+i*span,level,front],[-w/2+i*span,H,front],.15);
      for(const side of [-1,1])for(const y of [level+.2,level+1.02])line(veranda,[side*w/2,y,d/2],[side*w/2,y,front],.11);
    }
    if(object.rounded) {
      const radius=object.deco?.radius||Math.min(w,d)*.20,x=-w/2+radius*.45,z=d/2-radius*.35;
      const towerH=H+(object.deco?.towerRise||0);
      solid(root,new THREE.CylinderGeometry(radius,radius,towerH,40),wall,'villa-rounded-corner',x,towerH/2,z);
      solid(root,new THREE.CylinderGeometry(radius+.12,radius+.12,floor-bottom,40),'#d6d0c1','villa-rounded-foundation',x,(bottom-floor)/2,z);
      for(const y of [level,level*2-.12]) {
        solid(root,new THREE.CylinderGeometry(radius+.7,radius+.7,.18,40),wall,'villa-rounded-balcony',x,y,z);
        block(root,'villa-deco-balcony',1,y+.1,d/2+.8,w-1,.22,1.8,wall);
        block(root,'villa-deco-parapet',1,y+.62,d/2+1.64,w-1,.88,.15,wall);
        for(const dx of [-w/2+2,0,w/2-2])line(root,[dx,y+.18,d/2+1.7],[dx,y+1.05,d/2+1.7],.07,'#8a9287');
        line(root,[-w/2+2,y+1.05,d/2+1.7],[w/2-2,y+1.05,d/2+1.7],.075,'#8a9287');
      }
      windowBay(root,x-.3,level*.56,z+radius+.035,1.4,1.8);
      windowBay(root,x-.3,level*1.52,z+radius+.035,1.4,1.8);
      const band=new THREE.Group();band.name='villa-curved-window-band';root.add(band);
      for(const y of [level*.55,level*1.55])for(let i=0;i<12;i++) {
        const a=-Math.PI*.65+i/11*Math.PI*1.2,px=x+Math.sin(a)*(radius+.04),pz=z+Math.cos(a)*(radius+.04);
        const pane=block(band,'villa-curved-glass',px,y,pz,.70,1.4,.09,colors.glass);pane.rotation.y=a;
        const mullion=block(band,'villa-curved-mullion',px,y,pz,.06,1.52,.16,colors.wall);mullion.rotation.y=a;
      }
      for(const y of [level+.65,towerH+.1]) {
        const rim=solid(root,new THREE.CylinderGeometry(radius+.76,radius+.76,.68,40),wall,'villa-curved-parapet',x,y,z);
        rim.scale.y=.62;
      }
      if(towerH>H)solid(root,new THREE.CylinderGeometry(radius+.82,radius+.82,.18,40),'#ddd7c7','villa-tower-flat-cap',x,towerH+.38,z);
      if(object.deco?.roofEdge) {
        const edge=new THREE.Group();edge.name='villa-deco-roof-edge';root.add(edge);
        block(edge,'villa-flat-coping',0,H+.12,0,w+.55,.35,d+.55,wall);
        block(edge,'villa-horizontal-window-band',1,level*1.55,d/2+.1,w-3,1.25,.1,colors.glass);
        for(let x=-w/2+2;x<w/2;x+=2.2)block(edge,'villa-band-mullion',x,level*1.55,d/2+.20,.1,1.40,.1,wall);
      }
    }
    const roofGroup=new THREE.Group();roofGroup.name=object.id+'-roof';roofGroup.position.y=H;root.add(roofGroup);
    const roofSpec=object.roof||{},rw=w+1.8,rd=d+1.8+(object.veranda?2.7:0),rise=roofSpec.pitch?Math.tan(roofSpec.pitch*Math.PI/180)*rd/2:2.6;
    roofGroup.position.z=object.veranda?1.15:0;
    roof(roofGroup,rw,rd,rise,roofSpec.kind||'hip',object.ivy?'#586b4c':roofSpec.color||colors.roof,!object.ivy);
    roofRecords.push({group:roofGroup,parameters:{width:rw,depth:rd,ridgeHeight:H+rise,kind:roofSpec.kind||'hip'},tiers:1,thickness:.16,ridgeOrnament:false});
    if(object.secondaryGables) {
      const gables=new THREE.Group();gables.name='villa-secondary-gables';roofGroup.add(gables);
      const spec=object.secondaryGables;
      for(let i=0;i<spec.count;i++)frontGable(gables,(i-(spec.count-1)/2)*w*.48,.025,rd/2-.1,spec.width,spec.rise,rd*.62,roofSpec.color||colors.roof);
    }
    if(object.frontGable) {
      const projection=new THREE.Group();projection.name='villa-front-gable';root.add(projection);
      const gw=w*.38,gx=-w*.10,front=d/2+3;
      block(projection,'villa-projecting-wing',gx,H/2,d/2+1.5,gw,H,3,wall);
      block(projection,'villa-projecting-foundation',gx,(bottom-floor)/2,d/2+1.5,gw+.4,floor-bottom,3.2,'#d6d0c1');
      block(projection,'villa-door',gx,1.25,front+.06,1.25,2.5,.16,colors.timber);
      for(const side of [-1,1])windowBay(projection,gx+side*gw*.31,1.7,front+.1,.85,1.6,true);
      for(let k=1;k<storeys;k++)windowBay(projection,gx,k*level+level*.53,front+.1,1.8,1.8,true);
      if(object.frontBay) {
        const bay=new THREE.Group();bay.name='villa-projecting-bay';projection.add(bay);
        const shape=new THREE.Shape();shape.moveTo(-1.65,0);shape.lineTo(-1.65,-.8);shape.lineTo(-1.05,-1.45);shape.lineTo(1.05,-1.45);shape.lineTo(1.65,-.8);shape.lineTo(1.65,0);shape.closePath();
        const geometry=new THREE.ExtrudeGeometry(shape,{depth:2.25,bevelEnabled:false});geometry.rotateX(-Math.PI/2);
        solid(bay,geometry,wall,'villa-bay-shell',gx,level+.12,front,false);
        windowBay(bay,gx,level+1.45,front+1.49,1.85,1.42,false);
        for(const side of [-1,1])windowBay(bay,gx+side*1.37,level+1.45,front+1.12,.66,1.42,false,side*Math.PI/4);
        block(bay,'villa-bay-base',gx,level+.24,front+.75,3.4,.22,1.65,colors.shutter);
        block(bay,'villa-bay-cornice',gx,level+2.44,front+.75,3.5,.16,1.7,colors.wall);
      }
      const crossRoof=new THREE.Group();crossRoof.position.set(gx,.035,d/2+.4);crossRoof.rotation.y=Math.PI/2;roofGroup.add(crossRoof);
      roof(crossRoof,6.7,gw+1,Math.min(rise*.7,2.4),'gable',roofSpec.color||colors.roof);
      if(object.gableTimber)frontGable(roofGroup,gx,.08,front+.2,gw+.8,Math.min(rise*.78,2.8),5.9,roofSpec.color||colors.roof);
      const [endX,endZ]=local(gx,front+2.8),stepCount=Math.max(3,Math.ceil((floor-hillSurfaceHeight(endX,endZ))/.16));
      for(let i=0;i<stepCount;i++) {
        const z=front+.2+i*.30,[px,pz]=local(gx,z),bottom=hillSurfaceHeight(px,pz)-floor-.08,top=-i*.16;
        block(projection,'villa-entry-step',gx,(top+bottom)/2,z,2.2+i*.22,top-bottom,.36,'#d6d0c1');
      }
    }
    if(object.chimney) {
      const ridge=roofSpec.kind==='gable'?rw/2:Math.max(0,rw/2-rd*.42);
      const roofY=rise*Math.min(1-1/rd,(rw/2-w*.22)/Math.max(.001,rw/2-ridge));
      block(roofGroup,'villa-chimney',w*.22,roofY+.55,-.5,.65,1.5,.72,'#d8d3c6');
      block(roofGroup,'villa-chimney-cap',w*.22,roofY+1.32,-.5,.87,.16,.94,colors.timber);
    }
    if(object.ivy) {
      const ivy=new THREE.Group();ivy.name='villa-ivy';root.add(ivy);
      const spec=typeof object.ivy==='object'?object.ivy:{},spacing=spec.spacing||.22,size=spec.leafSize||.16,leaves=[],roofLeaves=[];
      const leaf=(out,x,y,z,rotation=[0,0,0])=>{
        const i=out.length,bulge=(spec.bulge||.10)*(.4+.6*Math.sin(i*.73)**2);
        const shade=Math.floor((Math.sin(i*12.9898)*43758.5453%1+1)%1*4);
        out.push({position:[x,y,z],scale:[size*(.85+.3*Math.sin(i)),size*.72,.025+bulge*.12],rotation:[rotation[0],rotation[1],i*2.39996],color:['#4b603e','#5c744b','#71875a','#7b9065'][shade]});
      };
      const opening=(x,y,front)=>{
        if(object.sign&&front&&Math.abs(x)<2.6&&Math.abs(y-(level+.12))<.72)return true;
        for(let k=0;k<storeys;k++)for(let i=1;i<=bays;i++) {
          const bx=-w/2+spacingForBay*i,door=front&&i===Math.ceil(bays/2)&&k===0;
          if(Math.abs(x-bx)<(door?.87:.92)&&Math.abs(y-(door?1.25:k*level+level*.53))<(door?1.45:1.07))return true;
        }
        return false;
      };
      const spacingForBay=w/(bays+1);
      for(const side of [-1,1])for(let x=-w/2;x<=w/2;x+=spacing)for(let y=.18;y<H;y+=spacing) {
        const px=x+.072*Math.sin(x*31+y*27),py=y+.072*Math.cos(x*21-y*17);
        if(!opening(px,py,side===1))leaf(leaves,px,py,side*(d/2+.15+.025*Math.sin(x*3+y*2)),[0,side<0?Math.PI:0,0]);
      }
      for(const side of [-1,1])for(let z=-d/2;z<=d/2;z+=spacing)for(let y=.18;y<H;y+=spacing) {
        if(Array.from({length:storeys},(_,k)=>k).some(k=>Math.abs(y-(k*level+level*.53))<1.05&&[-d*.26,d*.26].some(v=>Math.abs(z-v)<.85)))continue;
        leaf(leaves,side*(w/2+.15),y,z,[0,side*Math.PI/2,0]);
      }
      const hip=(roofSpec.kind||'hip')==='hip',ridge=hip?Math.max(0,rw/2-rd*.42):rw/2;
      for(const side of [-1,1])for(let x=-rw/2+.08;x<rw/2;x+=spacing)for(let z=.06;z<rd/2;z+=spacing) {
        const px=Math.max(-rw/2+.02,Math.min(rw/2-.02,x+.07*Math.sin(x*37+z*13))),pz=Math.max(.02,Math.min(rd/2-.03,z+.08*Math.cos(x*31-z*23)));
        const frontT=1-pz/(rd/2),endT=hip?(rw/2-Math.abs(px))/(rw/2-ridge):1;
        const rotation=hip&&endT<frontT?[-Math.PI/2,Math.atan2(Math.sign(px)*rise,rw/2-ridge),0]:[-side*Math.atan2(rd/2,rise),0,0];
        leaf(roofLeaves,px,rise*Math.min(frontT,endT)+.10,side*pz,rotation);
      }
      if(!hip)for(const side of [-1,1])for(let z=-d/2;z<=d/2;z+=spacing)for(let y=.06;y<rise*(1-Math.abs(z)/(d/2));y+=spacing)leaf(roofLeaves,side*(w/2+.09),y,z,[0,side*Math.PI/2,0]);
      instances(ivy,'villa-ivy-leaves',ivyLeafGeometry(),leaves,'#ffffff');
      instances(roofGroup,'villa-ivy-roof-leaves',ivyLeafGeometry(),roofLeaves,'#ffffff');
      if(object.sign) {
        const canvas=document.createElement('canvas');canvas.width=512;canvas.height=128;
        const context=canvas.getContext('2d');context.fillStyle=object.sign.background||'#3c4833';context.fillRect(0,0,512,128);context.fillStyle=object.sign.color||'#ead7a1';context.textAlign='center';
        for(const [i,text] of object.sign.lines.entries()){context.font=i?'bold 28px Arial':'bold 43px Arial';context.fillText(text,256,53+i*46);}
        const sign=new THREE.Mesh(new THREE.PlaneGeometry(4.8,1.2),new THREE.MeshBasicMaterial({map:new THREE.CanvasTexture(canvas),transparent:true}));
        sign.position.set(0,level+.12,d/2+.91);sign.name='reception-sign';root.add(sign);
      }
    }
    if(object.interior)frontLayer.traverse(part=>{if(part.material)part.material=part.material.clone();});
    pack(roofGroup);pack(root,[roofGroup,frontLayer]);
  });
  registerInteriorKit('villa_lounge',(building,{roof})=>{
    const shell=scene.getObjectByName(building.id+'-villa'),spec=building.interior,[w,d]=spec.size?[spec.size[0],spec.size[2]]:building.footprint,H=spec.size?.[1]??(building.storeys||2)*(building.storeyHeight||3.2);
    const group=new THREE.Group();group.name=building.id+'-interior';group.position.copy(shell.position);group.rotation.copy(shell.rotation);
    if(spec.offset)group.position.add(new THREE.Vector3(...spec.offset).applyAxisAngle(new THREE.Vector3(0,1,0),shell.rotation.y));
    const section=name=>{const g=new THREE.Group();g.name=name;group.add(g);return g;};
    const wood=spec.timberColor,white=spec.wallColor,stone=spec.fireplace?.stoneColor,copper=spec.fireplace?.hoodColor;
    const sidePanel=(parent,name,side,y,height,color,inset=.255,thickness=.05)=>{
      const x=side*(w/2-inset);
      if(!spec.corridor||side<0)return block(parent,name,x,y,0,thickness,height,d-.45,color);
      const z=spec.corridor.doorZ,half=spec.corridor.doorWidth/2;
      for(const [lo,hi] of [[-d/2+.225,z-half],[z+half,d/2-.225]])block(parent,name,x,y,(lo+hi)/2,thickness,height,hi-lo,color);
      if(y+height/2>spec.corridor.doorHeight){const low=Math.max(y-height/2,spec.corridor.doorHeight),high=y+height/2;block(parent,name,x,(low+high)/2,z,thickness,high-low,half*2,color);}
    };
    const walls=section('villa-interior-timber');
    block(walls,'interior-back-plaster',0,H/2,-d/2+.255,w-.45,H,.05,white);
    for(const side of [-1,1])sidePanel(walls,'interior-side-plaster',side,H/2,H,white);
    const wallBays=Math.max(2,Math.round(w/3.2));
    for(let i=0;i<=wallBays;i++) {
      const x=-w/2+.3+i*(w-.6)/wallBays;
      block(walls,'interior-timber-post',x,H/2,-d/2+.32,.16,H,.16,wood);
      if(Math.abs(x)>3)line(walls,[x,3.4,-d/2+.35],[x-Math.sign(x)*Math.min(1.1,w*.12),H-.12,-d/2+.35],.13,wood);
    }
    for(const y of [.18,3.15,H-.15])block(walls,'interior-timber-rail',0,y,-d/2+.32,w-.45,.16,.16,wood);
    const parquet=section('villa-parquet'),planks=[];
    block(parquet,'parquet-substrate',0,.025,0,w-.45,.05,d-.45,'#9e8060');
    for(let x=-w/2+.4;x<w/2-.4;x+=.64)for(let z=-d/2+.45;z<d/2-.35;z+=.64) {
      const i=Math.round((x+w/2)/.64)+Math.round((z+d/2)/.64);
      for(let strip=0;strip<3;strip++) {
        const offset=(strip-1)*.205;
        planks.push({position:[x+(i%2?0:offset),.062,z+(i%2?offset:0)],scale:[.192,.024,.61],rotation:[0,i%2?Math.PI/2:0,0],color:['#b29774','#ae9171','#b99b78'][(Math.abs(i)+strip)%3]});
      }
    }
    instances(parquet,'parquet-tiles',new THREE.BoxGeometry(1,1,1),planks,'#ffffff');
    if(spec.fireplace) {
    const hearth=section('villa-fireplace'),fw=spec.fireplace.width,back=-d/2+.85;
    block(hearth,'stone-hearth',0,.17,back+.40,fw+.6,.2,1.35,stone);
    for(const side of [-1,1])block(hearth,'stone-fireplace-jamb',side*(fw/2-.22),.77,back,.44,1.3,.60,stone);
    block(hearth,'firebox-dark',0,.70,back-.22,fw-.8,1.0,.15,'#514c43');
    block(hearth,'stone-fireplace-lintel',0,1.4,back,fw+.12,.24,.72,stone);
    block(hearth,'timber-mantel',0,1.62,back+.03,fw+.5,.19,.88,wood);
    for(let row=0;row<5;row++)for(const side of [-1,1])for(let j=0;j<2;j++)block(hearth,'stone-joint',side*(fw/2-.24)+(j-.5)*.17,.27+row*.22,back+.311,.15,.016,.012,'#bbb29f');
    for(const side of [-1,1])line(hearth,[side*.40,.38,back+.26],[side*-.12,.59,back+.14],.14,'#887560');
    const hood=section('villa-copper-hood'),height=spec.fireplace.hoodHeight;
    const shape=new THREE.Shape();shape.moveTo(-fw/2,1.75);shape.lineTo(fw/2,1.75);shape.lineTo(fw*.26,height);shape.lineTo(-fw*.26,height);shape.closePath();
    solid(hood,new THREE.ExtrudeGeometry(shape,{depth:.48,bevelEnabled:false}),copper,'copper-hood',0,0,back-.23,false);
    block(hood,'copper-hood-rim',0,1.78,back+.05,fw+.1,.10,.64,wood);
    block(hood,'hood-crown',0,height+.08,back,fw*.56,.16,.55,copper);
    for(const side of [-1,1])for(let i=0;i<8;i++) {
      const t=i/7,y=1.88+t*(height-1.97),x=side*(fw*.48-t*fw*.22);
      solid(hood,new THREE.SphereGeometry(.035,6,4),'#b9a485','hood-rivet',x,y,back+.27,false);
    }
    }
    if(spec.galleryWidth!==false) {
    const gallery=section('villa-mezzanine'),galleryWidth=spec.galleryWidth??3.15,gx=w/2-.2-galleryWidth/2,left=gx-galleryWidth/2;
    block(gallery,'gallery-deck',gx,3.22,0,galleryWidth,.22,d-.50,wood);
    for(const z of [-d/2+.5,0,d/2-.5])block(gallery,'gallery-support',left+.10,1.62,z,.18,3.24,.18,wood);
    for(const y of [3.45,4.22])block(gallery,'gallery-handrail',left+.05,y,0,.11,.11,d-.5,wood);
    for(let z=-d/2+.4;z<d/2-.3;z+=.27)block(gallery,'gallery-baluster',left+.05,3.84,z,.065,.76,.065,wood);
    }
    if(spec.cabinetX!==undefined) {
    const cabinet=section('villa-display-cabinet');
    cabinet.position.set(spec.cabinetX,0,-d/2+.67);
    block(cabinet,'cabinet-back',0,1.25,-.22,1.65,2.35,.12,wood);
    block(cabinet,'cabinet-base',0,.23,0,1.82,.35,.62,wood);
    block(cabinet,'cabinet-crown',0,2.56,0,1.9,.20,.65,wood);
    for(const x of [-.81,0,.81])block(cabinet,'cabinet-frame',x,1.35,.27,.065,2.25,.065,wood);
    const glass=new THREE.MeshStandardMaterial({color:'#a6b8ad',transparent:true,opacity:.18,roughness:.24,depthWrite:false});
    for(const x of [-.4,.4]) {const pane=new THREE.Mesh(new THREE.BoxGeometry(.71,2.12,.025),glass);pane.position.set(x,1.35,.25);cabinet.add(pane);}
    for(const y of [.7,1.32,1.96]) {
      block(cabinet,'cabinet-shelf',0,y,0,1.65,.06,.52,wood);
      for(const x of [-.52,0,.52])solid(cabinet,new THREE.CylinderGeometry(.065,.09,.24,8),'#c9c4b3','display-ceramic',x,y+.15,.04,false);
    }
    }
    const seats=section('villa-armchairs');
    for(const [x,z,angle] of spec.armchairs) {
      const chair=new THREE.Group();chair.position.set(x,.074,z);chair.rotation.y=angle;seats.add(chair);
      if(spec.armchairStyle==='club') {
        for(const dx of [-.30,.30])for(const dz of [-.29,.29])block(chair,'armchair-leg',dx,.15,dz,.065,.30,.065,wood);
        block(chair,'armchair-seat',0,.38,0,.68,.19,.66,spec.upholsteryColor);
        block(chair,'armchair-club-back',0,.65,-.29,.72,.55,.16,spec.upholsteryColor).rotation.x=-.10;
        for(const side of [-1,1])block(chair,'armchair-club-arm',side*.38,.49,0,.12,.30,.69,spec.upholsteryColor);
        continue;
      }
      for(const dx of [-.30,.30])for(const dz of [-.29,.29])block(chair,'armchair-leg',dx,.18,dz,.055,.36,.055,wood);
      block(chair,'armchair-seat-frame',0,.33,0,.70,.08,.64,wood);
      solid(chair,new THREE.SphereGeometry(1,16,10),spec.upholsteryColor||'#c8c1ae','armchair-cushion',0,.40,0,false).scale.set(.35,.07,.33);
      solid(chair,new THREE.SphereGeometry(1,16,12),wood,'armchair-back-frame',0,.68,-.30,false).scale.set(.39,.29,.12);
      solid(chair,new THREE.SphereGeometry(1,16,12),spec.upholsteryColor||'#c8c1ae','armchair-upholstered-back',0,.69,-.235,false).scale.set(.35,.25,.10);
      for(const side of [-1,1]) {
        for(let i=0;i<8;i++) {
          const z=-.29+i*.08,next=z+.08;
          const height=t=>.55+.12*Math.sin((t+.29)/.64*Math.PI);
          line(chair,[side*.37,height(z),z],[side*.37,height(next),next],.075,wood);
        }
        block(chair,'armchair-arm-support',side*.37,.44,.25,.055,.25,.055,wood);
      }
    }
    const lounge=section('villa-round-table');lounge.position.set(...spec.roundTable);if(spec.tableScale)lounge.scale.setScalar(spec.tableScale);
    solid(lounge,new THREE.CylinderGeometry(.68,.68,.10,32),wood,'round-table-top',0,.76,0,false);
    solid(lounge,new THREE.CylinderGeometry(.09,.15,.65,10),wood,'round-table-pedestal',0,.39,0,false);
    for(let i=0;i<3;i++)line(lounge,[0,.18,0],[Math.cos(i*2.094)*.4,.1,Math.sin(i*2.094)*.4],.08,wood);
    const portraits=section('villa-portraits');
    for(const x of spec.portraitXs) {
      const z=spec.altar? -d/2+1.12:-d/2+.37;
      block(portraits,'portrait-frame',x,2,z,.82,1.04,.10,'#9e8967');
      block(portraits,'portrait-canvas',x,2,z+.06,.68,.9,.025,'#8e8d79');
      solid(portraits,new THREE.SphereGeometry(.15,10,7),'#b5a48b','portrait-head',x,2.17,z+.10,false).scale.z=.15;
      solid(portraits,new THREE.SphereGeometry(.26,10,7),wood,'portrait-shoulders',x,1.84,z+.10,false).scale.set(1,.9,.10);
    }
    if(spec.altar) {
      const altar=section('villa-altar-cabinet'),az=-d/2+.83,dark=spec.altar.color;
      for(const x of [-1.30,1.30])block(altar,'altar-foot',x,.25,az,.18,.5,.64,dark);
      block(altar,'altar-cabinet-body',0,.77,az,2.85,1.10,.72,dark);
      for(const y of [.33,1.25,1.40])block(altar,'altar-carved-rail',0,y,az+.12,3.06,.09,.86,dark);
      for(const x of [-.96,0,.96]) {
        block(altar,'altar-panel',x,.77,az+.38,.83,.67,.055,'#756046');
        for(let i=0;i<8;i++){const a=i*Math.PI/4;solid(altar,new THREE.SphereGeometry(.085,6,4),'#a38a60','altar-carving',x+Math.cos(a)*.26,.77+Math.sin(a)*.20,az+.43,false).scale.z=.18;}
      }
      for(const x of [-1.25,1.25]) {
        solid(altar,new THREE.CylinderGeometry(.12,.16,.28,12),'#839887','altar-vase',x,1.59,az+.1,false);
        for(let k=0;k<7;k++){const dx=Math.sin(k*2.4)*.18,y=1.94+k*.065;line(altar,[x,1.72,az+.1],[x+dx,y,az+.10+Math.cos(k)*.12],.018,'#7c8661');solid(altar,new THREE.SphereGeometry(.095,7,5),'#bfaf76','altar-flower',x+dx,y,az+.10+Math.cos(k)*.12,false);}
      }
      const panels=section('villa-wall-panelling');
      for(const side of [-1,1]) {
        sidePanel(panels,'timber-wainscot',side,.78,1.45,'#a28160',.31,.07);
        for(let z=-d/2+.4;z<d/2-.4;z+=.62)if(!spec.corridor||side<0||Math.abs(z-spec.corridor.doorZ)>spec.corridor.doorWidth/2)block(panels,'timber-panel-stile',side*(w/2-.36),.78,z,.06,1.45,.055,wood);
        for(const y of [.16,1.46])sidePanel(panels,'timber-panel-rail',side,y,.08,wood,.37,.07);
      }
      const carpet=section('villa-patterned-carpet'),[cw,cd,cz]=spec.carpet;
      block(carpet,'carpet-ground',0,.095,cz,cw,.025,cd,'#955e58');
      const motifs=[];
      for(let x=-cw/2+.20;x<cw/2;x+=.32)for(const z of [cz-cd/2+.16,cz+cd/2-.16])motifs.push({position:[x,.113,z],scale:[.12,.008,.12],rotation:[0,Math.PI/4,0]});
      for(let x=-cw/2+.55;x<cw/2-.3;x+=.72)for(let z=cz-cd/2+.55;z<cz+cd/2-.3;z+=.72)motifs.push({position:[x,.113,z],scale:[.10,.008,.16],rotation:[0,Math.PI/4,0]});
      instances(carpet,'carpet-fine-pattern',new THREE.BoxGeometry(1,1,1),motifs,'#c8ae8f');
      const curtains=section('villa-curtains');
      for(const z of spec.windows) {
        const x=-w/2+.34;
        block(curtains,'tall-window-recess',x,2.05,z,.06,2.80,1.75,'#647367');
        block(curtains,'tall-window-glass',x+.04,2.05,z,.04,2.62,1.58,'#a9b8ad');
        for(const dz of [-.80,0,.80])block(curtains,'window-mullion',x+.08,2.05,z+dz,.08,2.74,.055,white);
        for(const y of [.70,2.05,3.40])block(curtains,'window-transom',x+.08,y,z,.08,.055,1.72,white);
        for(const dz of [-1,1])for(let k=0;k<5;k++)solid(curtains,new THREE.CylinderGeometry(.065,.085,2.94,8),'#b5a38d','curtain-fold',x+.17+k*.022,1.95,z+dz*(.75+k*.055),false);
        block(curtains,'curtain-valance',x+.16,3.43,z,.16,.24,2.30,'#a18c77');
      }
      if(spec.corridor) {
        const corridor=section('villa-corridor'),c=spec.corridor,cx=w/2+c.width/2-.28,cz=c.doorZ+c.length/2-1;
        for(const z of [c.doorZ-c.doorWidth/2,c.doorZ+c.doorWidth/2])block(corridor,'corridor-door-jamb',w/2-.35,c.doorHeight/2,z,.14,c.doorHeight,.10,wood);
        block(corridor,'corridor-door-head',w/2-.35,c.doorHeight,c.doorZ,.14,.12,c.doorWidth+.1,wood);
        block(corridor,'corridor-floor',cx,.06,cz,c.width,.12,c.length,'#a58b6a');
        block(corridor,'corridor-outer-wall',cx+c.width/2,H/2,cz,.16,H,c.length,white);
        for(const z of [cz-c.length/2,cz+c.length/2])block(corridor,'corridor-end-wall',cx,H/2,z,c.width+.15,H,.16,white);
        block(corridor,'corridor-runner',cx,.126,cz,c.width*.55,.012,c.length-.3,'#8e6258');
        for(let z=cz-c.length/2+.7;z<cz+c.length/2;z+=1.8) {
          block(corridor,'corridor-door-leaf',cx+c.width/2-.10,1.2,z,.045,2.4,.72,wood);
          for(const y of [.6,1.4,2.1])block(corridor,'corridor-door-panel',cx+c.width/2-.13,y,z,.025,.045,.62,'#a58b69');
          solid(corridor,new THREE.SphereGeometry(.12,8,6),'#d6c7a6','corridor-ceiling-lamp',cx,H-.20,z,false);
        }
      }
    }
    if(spec.diningX!==undefined) {
    const dining=section('villa-dining'),dx=spec.diningX,dz=spec.diningZ??-.5;
    for(let x=dx-2.3;x<dx+2.5;x+=.6)for(let z=-d/2+.4;z<d/2-.3;z+=.6) {
      const i=Math.round((x-dx+2.3)/.6)+Math.round((z+d/2-.4)/.6);
      block(dining,'checkerboard-tile',x,.091,z,.595,.028,.595,i%2?'#8e8576':'#c8b89a');
    }
    block(dining,'dining-table',dx,.79,dz,1.2,.14,2.3,wood);
    for(const side of [-1,1])for(const z of [dz-.7,dz+.7]) {
      const x=dx+side*1.02;
      block(dining,'carved-chair-seat',x,.48,z,.48,.09,.48,wood);
      block(dining,'carved-chair-back',x+side*.22,.78,z,.07,.64,.50,wood);
      for(const sx of [-1,1])for(const sz of [-1,1])block(dining,'carved-chair-leg',x+sx*.18,.25,z+sz*.18,.045,.5,.045,wood);
      solid(dining,new THREE.SphereGeometry(.12,8,6),wood,'carved-chair-crest',x+side*.22,1.10,z,false).scale.set(.6,.5,1.8);
    }
    for(const x of [dx-.45,dx+.45])for(const z of [dz-.85,dz+.85])block(dining,'table-leg',x,.42,z,.09,.70,.09,wood);
    line(dining,[dx,3.13,dz],[dx,2.25,dz],.025,'#89785f');
    for(let i=0;i<6;i++) {
      const a=i*Math.PI/3,x=dx+Math.cos(a)*.5,z=dz+Math.sin(a)*.5;
      line(dining,[dx,2.25,dz],[x,2.05,z],.035,'#89785f');
      solid(dining,new THREE.SphereGeometry(.075,8,6),'#d7c5a0','chandelier-candle',x,2.21,z,false);
    }
    }
    const ceiling=new THREE.Group();ceiling.name='villa-sealed-ceiling';ceiling.position.z=-roof.position.z;
    if(spec.offset){ceiling.position.x=spec.offset[0];ceiling.position.z+=spec.offset[2];ceiling.position.y=H-roof.position.y;}
    block(ceiling,'villa-ceiling-plaster',0,-.08,0,w-.30,.16,d-.30,white);
    if(spec.vestibule)block(ceiling,'vestibule-ceiling',0,-.08,d/2+spec.vestibule.depth/2-.16,spec.doorWidth+.2,.16,spec.vestibule.depth+.25,white);
    if(spec.corridor){const c=spec.corridor;block(ceiling,'corridor-ceiling',w/2+c.width/2-.28,-.08,c.doorZ+c.length/2-1,c.width+.2,.16,c.length+.2,white);}
    if(spec.ceilingBeams!==false)for(let x=-w/2+.4;x<w/2;x+=1.8)block(ceiling,'villa-ceiling-beam',x,-.22,0,.15,.28,d-.3,wood);
    for(const g of group.children)if(g.name!=='villa-parquet')pack(g);
    pack(ceiling);
    return {group,ceiling,front:shell.userData.frontLayer,door:shell.userData.interiorDoor};
  });
  registerObjectType('villa_drive',object=>{
    const points=object.points.map(p=>new THREE.Vector3(...p));
    const curve=object.linear?new THREE.CurvePath():new THREE.CatmullRomCurve3(points,false,'centripetal');
    if(object.linear)for(let i=1;i<points.length;i++)curve.add(new THREE.LineCurve3(points[i-1],points[i]));
    const layer=place.objects.filter(o=>o.type==='villa_drive').indexOf(object)*.004;
    const vertices=[],edges=[],samples=object.linear?Array.from({length:241},(_,i)=>curve.getPoint(i/240)):curve.getPoints(240),half=object.width/2;
    const quad=(out,a,b,c,d)=>out.push(...a,...b,...c,...a,...c,...d);
    function point(i,offset,lift=.105) {
      const p=samples[i],t=curve.getTangent(i/240),v=new THREE.Vector3(-t.z,0,t.x).normalize().multiplyScalar(offset).add(p);
      return [v.x,hillSurfaceHeight(v.x,v.z)+lift+layer,v.z];
    }
    for(let i=1;i<samples.length;i++) {
      quad(vertices,point(i-1,-half),point(i,-half),point(i,half),point(i-1,half));
      for(const side of [-1,1])quad(edges,point(i-1,side*half,.135),point(i,side*half,.135),point(i,side*(half+.16),.135),point(i-1,side*(half+.16),.135));
    }
    for(const [positions,color,name] of [[vertices,object.color||(object.surface==='brick'?'#b58b76':'#d7d2c6'),'gravel-drive'],[edges,object.surface==='brick'?'#d0bda2':'#bfb9a9','gravel-edge']]) {
      const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));geometry.computeVertexNormals();
      const part=mesh(geometry,color,0,0,0,false);part.name=object.id||name;part.material=part.material.clone();part.material.side=THREE.DoubleSide;
      if(name==='gravel-drive')walkableGeometries.push(geometry.clone());
    }
    if(['brick','stone'].includes(object.surface)) {
      const stone=object.surface==='stone';
      const group=new THREE.Group();scene.add(group);const joints=[],n=Math.ceil(curve.getLength()/(stone?.9:.48));
      for(let i=0;i<=n;i++) {
        const p=curve.getPointAt(i/n),t=curve.getTangentAt(i/n);
        joints.push({position:[p.x,hillSurfaceHeight(p.x,p.z)+.12+layer,p.z],scale:[object.width,.014,.028],rotation:[0,Math.atan2(-t.z,t.x)+Math.PI/2,0]});
        if(stone) {
          const side=new THREE.Vector3(-t.z,0,t.x).multiplyScalar(Math.sin(i*2.4)*object.width*.22),q=p.clone().add(side).addScaledVector(t,.35);
          joints.push({position:[q.x,hillSurfaceHeight(q.x,q.z)+.12+layer,q.z],scale:[.024,.014,.8],rotation:[0,Math.atan2(t.x,t.z)+(i%2?.26:-.26),0]});
        }
      }
      instances(group,'garden-path-joints',new THREE.BoxGeometry(1,1,1),joints,stone?'#b8b7a8':'#c6aa8d');
    }
    if(object.hedges?.length) {
      const group=new THREE.Group();group.name=object.id+'-hedges';scene.add(group);const entries=[];
      for(const spec of object.hedges) {
        const length=curve.getLength()*(spec.end-spec.start),n=Math.ceil(length/.46);
        for(let i=0;i<=n;i++) {
          const t=spec.start+(spec.end-spec.start)*i/n,p=curve.getPointAt(t),v=curve.getTangentAt(t);
          const x=p.x-v.z*spec.side*(half+.62),z=p.z+v.x*spec.side*(half+.62);
          entries.push({position:[x,hillSurfaceHeight(x,z)+.34,z],scale:[.48,.68,.52],color:i%3?'#738465':'#819071'});
        }
      }
      instances(group,'garden-drive-hedge',new THREE.BoxGeometry(1,1,1),entries,'#ffffff');
    }
  });
  registerObjectType('villa_lawn',object=>{
    const [cx,,cz]=object.position,[w,,d]=object.size,vertices=[],indices=[],rings=32,n=128;
    for(let j=0;j<=rings;j++)for(let i=0;i<=n;i++) {
      const t=i/n*Math.PI*2,r=j/rings,power=object.shape==='rounded'?.45:1;
      const c=Math.cos(t),s=Math.sin(t),x=cx+Math.sign(c)*Math.abs(c)**power*w/2*r,z=cz+Math.sign(s)*Math.abs(s)**power*d/2*r;
      vertices.push(x,hillSurfaceHeight(x,z)+.060,z);
      if(j<rings&&i<n){const a=j*(n+1)+i,b=a+n+1;indices.push(a,b+1,b,a,a+1,b+1);}
    }
    const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));geometry.setIndex(indices);geometry.computeVertexNormals();
    mesh(geometry,object.color||'#c3c9b4',0,0,0,false).name=object.id||'villa-lawn';
  });
  registerObjectType('villa_flowerbed',object=>{
    contouredBed(object);
    const [cx,,cz]=object.position,[w,,d]=object.size,group=new THREE.Group();group.name=object.id+'-flowers';scene.add(group);
    for(let i=0;i<28;i++) {
      const a=i*2.39996,r=Math.sqrt((i+.5)/28)*.85,x=cx+Math.cos(a)*w/2*r,z=cz+Math.sin(a)*d/2*r;
      const y=hillSurfaceHeight(x,z)+.23+.48*(1-r*r);
      const flower=solid(group,new THREE.IcosahedronGeometry(.15+(i%3)*.015,0),['#b9a3aa','#d0b79e','#d9d5ba'][i%3],'model-flower',x,y,z,false);flower.scale.y=.6;
    }
    pack(group);
  });
  registerObjectType('villa_garden',object=>{
    if(object.formal)return formalGarden(object);
    const [cx,,cz]=object.position,[w,,d]=object.size,group=new THREE.Group();group.name=object.id+'-garden';scene.add(group);
    const bricks=[],shrubs=[],blooms=[],leaves=[],flowers=[],hedge=[],soil=[],rings=12,n=96;
    const radius=a=>object.shape==='organic'?1+.12*Math.sin(a*3)+.06*Math.cos(a*2):['rectangle','ribbon'].includes(object.shape)?1/Math.max(Math.abs(Math.cos(a)),Math.abs(Math.sin(a))):1;
    for(let j=0;j<=rings;j++)for(let i=0;i<=n;i++) {
      const a=i/n*Math.PI*2,r=j/rings,x=cx+Math.cos(a)*w/2*r*radius(a),z=cz+Math.sin(a)*d/2*r*radius(a);
      soil.push(x,hillSurfaceHeight(x,z)+.13+.1*(1-r*r),z);
    }
    const indices=[];for(let j=0;j<rings;j++)for(let i=0;i<n;i++){const a=j*(n+1)+i,b=a+n+1;indices.push(a,b+1,b,a,a+1,b+1);}
    const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(soil,3));geometry.setIndex(indices);geometry.computeVertexNormals();
    solid(group,geometry,'#827d63','garden-soil',0,0,0,false);
    const rectangular=['rectangle','ribbon'].includes(object.shape);
    const edgeAt=(t,scale=1)=>{
      if(!rectangular) {const a=t*Math.PI*2;return [cx+Math.cos(a)*w/2*radius(a)*scale,cz+Math.sin(a)*d/2*radius(a)*scale];}
      let distance=(t%1)*2*(w+d);const corners=[[-w/2,-d/2],[w/2,-d/2],[w/2,d/2],[-w/2,d/2]];
      for(let i=0;i<4;i++) {
        const a=corners[i],b=corners[(i+1)%4],length=i%2?d:w;
        if(distance<=length)return [cx+(a[0]+(b[0]-a[0])*distance/length)*scale,cz+(a[1]+(b[1]-a[1])*distance/length)*scale];
        distance-=length;
      }
    };
    const count=Math.ceil((rectangular?2*(w+d):Math.PI*(w+d)/2)/.40);
    for(let i=0;i<count;i++) {
      const [x,z]=edgeAt(i/count),[nx,nz]=edgeAt(i/count+.00001),tangent=Math.atan2(nx-x,nz-z);
      bricks.push({position:[x,hillSurfaceHeight(x,z)+.23,z],scale:[.28,.25,.43],rotation:[0,tangent,0],color:i%3?'#9c6956':'#b38369'});
    }
    if(object.hedge)for(let i=0;i<count;i++) {
      const [x,z]=edgeAt(i/count,.86);
      hedge.push({position:[x,hillSurfaceHeight(x,z)+.57,z],scale:[.42,.42,.42],color:i%3?'#73865e':'#82936d'});
    }
    for(let i=0;i<(object.shrubs||8);i++) {
      const a=i/(object.shrubs||8)*Math.PI*2,x=cx+Math.cos(a)*w*.35,z=cz+Math.sin(a)*d*.35;
      shrubs.push({position:[x,hillSurfaceHeight(x,z)+.65,z],scale:[.68,.55,.62],color:i%2?'#6c8058':'#7c8e66'});
    }
    for(let i=0;i<(object.hydrangeas||12);i++) {
      const a=i*2.39996,r=.78*Math.sqrt((i+.5)/(object.hydrangeas||12)),x=cx+Math.cos(a)*w/2*r,z=cz+Math.sin(a)*d/2*r,y=hillSurfaceHeight(x,z)+.62;
      leaves.push({position:[x,y-.17,z],scale:[.60,.34,.51],color:'#788e64'});
      for(let j=0;j<12;j++) {
        const b=j*2.39996,rr=Math.sqrt((j+.5)/12)*.4;
        blooms.push({position:[x+Math.cos(b)*rr,y+.19+.20*(1-rr),z+Math.sin(b)*rr],scale:[.14,.105,.14],color:['#a7b8c9','#bdc9cf','#e0dfce'][i%3]});
      }
    }
    for(let i=0;i<Math.ceil(w*d*1.5);i++) {
      const a=i*2.39996,r=Math.sqrt((i+.5)/Math.ceil(w*d*1.5))*.90*(rectangular?radius(a):1),x=cx+Math.cos(a)*w/2*r,z=cz+Math.sin(a)*d/2*r;
      flowers.push({position:[x,hillSurfaceHeight(x,z)+.32,z],scale:[.075,.08,.075],color:['#b39cab','#d4c9b2','#a98590'][i%3]});
    }
    instances(group,'garden-brick-border',new THREE.BoxGeometry(1,1,1),bricks,'#ffffff');
    instances(group,'garden-clipped-shrubs',new THREE.SphereGeometry(1,10,6),shrubs,'#ffffff');
    instances(group,'garden-hydrangea-leaves',new THREE.IcosahedronGeometry(1,0),leaves,'#ffffff');
    instances(group,'garden-hydrangea-petals',new THREE.IcosahedronGeometry(1,0),blooms,'#ffffff');
    instances(group,'garden-small-flowers',new THREE.IcosahedronGeometry(1,0),flowers,'#ffffff');
    if(hedge.length)instances(group,'garden-clipped-hedge',new THREE.SphereGeometry(1,8,5),hedge,'#ffffff');
  });
  function formalGarden(object) {
    const [cx,,cz]=object.position,[w,,d]=object.size,group=new THREE.Group();group.name=object.id+'-garden';scene.add(group);
    const rectangular=object.shape==='rectangle',hedges=[],flowers=[],rim=[],n=128,outline=[];
    for(let i=0;i<n;i++) {
      const a=i/n*Math.PI*2,c=Math.cos(a),s=Math.sin(a),power=rectangular?.18:.65;
      outline.push([cx+Math.sign(c)*Math.abs(c)**power*w/2,cz+Math.sign(s)*Math.abs(s)**power*d/2]);
    }
    if(object.shape==='capsule') {
      const width=Math.max(w,d),depth=Math.min(w,d),r=depth/2,s=new THREE.Shape();
      s.moveTo(-width/2+r,-r);s.lineTo(width/2-r,-r);s.absarc(width/2-r,0,r,-Math.PI/2,Math.PI/2,false);
      s.lineTo(-width/2+r,r);s.absarc(-width/2+r,0,r,Math.PI/2,Math.PI*1.5,false);s.closePath();
      outline.splice(0,outline.length,...s.getSpacedPoints(n).slice(0,-1).map(p=>w>=d?[cx+p.x,cz+p.y]:[cx-p.y,cz+p.x]));
    }
    const shape=new THREE.Shape(outline.map(([x,z])=>new THREE.Vector2(x,-z))),soil=new THREE.ShapeGeometry(shape);soil.rotateX(-Math.PI/2);
    const p=soil.attributes.position;for(let i=0;i<p.count;i++)p.setY(i,hillSurfaceHeight(p.getX(i),p.getZ(i))+.12);soil.computeVertexNormals();
    solid(group,soil,'#9a9982','formal-garden-soil',0,0,0,false);
    const curve=new THREE.CatmullRomCurve3(outline.map(([x,z])=>new THREE.Vector3(x,0,z)),true,'centripetal');
    const count=Math.ceil(curve.getLength()/.4);
    for(let i=0;i<count;i++) {
      const p=curve.getPointAt(i/count),t=curve.getTangentAt(i/count),y=hillSurfaceHeight(p.x,p.z);
      rim.push({position:[p.x,y+.14,p.z],scale:[.15,.20,.43],rotation:[0,Math.atan2(t.x,t.z),0]});
      hedges.push({position:[cx+(p.x-cx)*.94,y+.34,cz+(p.z-cz)*.94],scale:[.52,.48,.52]});
    }
    const drift=object.planting?.layout==='drift',spacing=object.planting?.spacing||.72,leafMats=[];
    const rows=Math.max(1,Math.floor(d/spacing)),cols=Math.max(1,Math.floor(w/spacing));
    for(let iz=0;iz<rows;iz++)for(let ix=0;ix<cols;ix++) {
      const x=(ix+.5)/cols*2-1,z=(iz+.5)/rows*2-1;
      if(rectangular?Math.max(Math.abs(x),Math.abs(z))>.80:Math.abs(x)**3+Math.abs(z)**3>.67)continue;
      const px=cx+x*w/2+Math.sin(ix*12.7+iz*3.1)*(drift?spacing*.44:.17),pz=cz+z*d/2+Math.cos(ix*9.7+iz*7.3)*(drift?spacing*.44:.17);
      if(drift) {
        const a=ix*2.39996+iz*1.37,y=hillSurfaceHeight(px,pz);
        leafMats.push({position:[px,y+.24,pz],scale:[spacing*.70,.10,spacing*.64],rotation:[0,a,0],color:(ix+iz)%3?'#9da58a':'#aab096'});
        for(let k=0;k<2;k++) {
          const r=.12+.035*Math.sin(a+k*4),angle=a+k*2.4,size=.12+.035*Math.sin(ix*17.1+iz*9.2+k);
          flowers.push({position:[px+Math.cos(angle)*r,y+.36+.025*Math.cos(a+k),pz+Math.sin(angle)*r],scale:[size,.065,size],rotation:[0,angle,0],color:Math.sin(ix*.43+iz*.71)>.25?'#d2c5b6':object.flowerColor||'#af8c96'});
        }
        continue;
      }
      flowers.push({position:[px,hillSurfaceHeight(px,pz)+.33,pz],scale:[.24,.12,.24],color:(ix+iz)%3?object.flowerColor||'#af8c96':'#d2c5b6'});
    }
    instances(group,'formal-garden-edging',new THREE.BoxGeometry(1,1,1),rim,'#c9c4b2');
    instances(group,'formal-garden-hedge',new THREE.IcosahedronGeometry(1,1),hedges,'#839274');
    if(leafMats.length)instances(group,'formal-garden-leaf-mats',new THREE.IcosahedronGeometry(1,0),leafMats,'#ffffff');
    instances(group,'formal-garden-flowers',new THREE.IcosahedronGeometry(1,0),flowers,'#ffffff');
  }
  registerObjectType('villa_pergola',object=>{
    const [x,,z]=object.position,[w,h,d]=object.size,group=new THREE.Group();group.name=object.id+'-pergola';group.position.set(x,hillSurfaceHeight(x,z),z);group.rotation.y=object.rotation||0;scene.add(group);
    const foliage=[];
    for(let i=0;i<=Math.round(w/3);i++)for(const side of [-1,1]) {
      const px=-w/2+i*w/Math.round(w/3),pz=side*d/2;
      block(group,'pergola-stone-foot',px,.16,pz,.55,.32,.55,'#bbb8a5');
      block(group,'pergola-column',px,h/2,pz,.20,h,.20,'#c3bba4');
      for(let k=0;k<22;k++) {
        const a=k*2.4,py=.25+k*h/22;
        foliage.push({position:[px+Math.sin(a)*.14,py,pz+Math.cos(a)*.14],scale:[.17,.23,.035],rotation:[.2,a,.3]});
      }
    }
    for(const side of [-1,1])block(group,'pergola-beam',0,h,side*d/2,w+.7,.22,.25,'#9f9984');
    for(let px=-w/2;px<=w/2;px+=.55){block(group,'pergola-rafter',px,h+.16,0,.12,.17,d+.7,'#a8a08a');for(let k=0;k<15;k++)foliage.push({position:[px+Math.sin(k*7.7)*.20,h+.29-Math.sin(px*2+k)*.07,-d/2+k*d/14],scale:[.20,.24,.035],rotation:[Math.PI/2+.2,k*2.4,.1]});}
    instances(group,'pergola-climbing-leaves',ivyLeafGeometry(),foliage,'#8c9b7b');pack(group);
  });
  registerObjectType('villa_urns',object=>{
    const group=new THREE.Group();group.name=object.id+'-urns';scene.add(group);const blooms=[],crowns=[],trunks=[];
    for(const [x,z] of object.points) {
      const y=hillSurfaceHeight(x,z);
      block(group,'urn-plinth',x,y+.09,z,.78,.18,.78,'#e1dccc');
      solid(group,new THREE.CylinderGeometry(.25,.34,.68,16),'#e4dfd0','urn-pedestal',x,y+.48,z);
      solid(group,new THREE.CylinderGeometry(.60,.22,.43,20),'#e4dfd0','urn-bowl',x,y+1.01,z);
      for(let i=0;i<24;i++){const a=i*2.4,r=Math.sqrt((i+.5)/24)*.47;blooms.push({position:[x+Math.cos(a)*r,y+1.26+.17*(1-r),z+Math.sin(a)*r],scale:[.16,.13,.16],color:i%4?'#af91a2':'#889572'});}
      if(object.treeHeight) {
        const h=object.treeHeight;
        trunks.push({position:[x,y+1.22+h/2,z],scale:[.07,h,.07]});
        for(let i=0;i<7;i++){const a=i*2.4,r=i?.72:0;crowns.push({position:[x+Math.cos(a)*r,y+1.22+h-.13*(i%3),z+Math.sin(a)*r],scale:[.93,.46,.82],color:i%3?object.flowerColor||'#b09aa6':'#879778'});}
      }
    }
    if(crowns.length){instances(group,'urn-topiary-trunks',new THREE.CylinderGeometry(1,1,1,7),trunks,'#8b8067');instances(group,'urn-topiary-crowns',new THREE.IcosahedronGeometry(1,1),crowns,'#ffffff');}
    instances(group,'urn-muted-flowers',new THREE.IcosahedronGeometry(1,0),blooms,'#ffffff');pack(group);
  });
  registerObjectType('villa_sign',object=>{
    const [x,,z]=object.position,group=new THREE.Group();group.name=object.id+'-sign';group.position.set(x,hillSurfaceHeight(x,z),z);group.rotation.y=object.rotation||0;scene.add(group);
    const w=object.width||5.4;
    for(const side of [-1,1])block(group,'sign-stone-post',side*(w/2+.16),1.2,0,.32,2.4,.42,'#d5d0bd');
    block(group,'sign-stone-tablet',0,1.26,0,w,1.85,.30,'#dad4bf');
    const canvas=document.createElement('canvas');canvas.width=1024;canvas.height=384;const c=canvas.getContext('2d');
    c.fillStyle='#dad4bf';c.fillRect(0,0,1024,384);c.fillStyle='#716c5a';c.textAlign='center';
    object.lines.forEach((text,i)=>{c.font=i?'42px Arial':'bold 76px Arial';c.fillText(text,512,140+i*92);});
    const texture=new THREE.CanvasTexture(canvas);texture.colorSpace=THREE.SRGBColorSpace;
    const face=new THREE.Mesh(new THREE.PlaneGeometry(w-.25,1.65),new THREE.MeshBasicMaterial({map:texture}));face.position.set(0,1.26,.16);group.add(face);pack(group);
  });
  registerObjectType('villa_grove',object=>{
    const [cx,,cz]=object.position,group=new THREE.Group();group.name=object.id+'-grove';scene.add(group);
    const trunks=[],crowns=[],branches=[];
    if(object.species==='palm') {
      const fronds=[];
      for(const [dx,dz,height] of object.trees) {
        const x=cx+dx,z=cz+dz,y=hillSurfaceHeight(x,z);
        trunks.push({position:[x,y+height/2,z],scale:[.15,height,.15]});
        for(let i=0;i<9;i++)for(let k=0;k<5;k++) {
          const a=i*Math.PI*2/9,r=.3+k*.46;
          fronds.push({position:[x+Math.cos(a)*r,y+height+.45-r*r*.19,z+Math.sin(a)*r],scale:[.59,.06,.20],rotation:[0,-a,Math.atan(.38*r)],color:i%2?'#87967b':'#96a588'});
        }
      }
      instances(group,'grove-palm-trunks',new THREE.CylinderGeometry(.8,1,1,9),trunks,'#9d9278');
      instances(group,'grove-palm-fronds',new THREE.IcosahedronGeometry(1,0),fronds,'#ffffff');return;
    }
    for(const [i,[dx,dz,height]] of object.trees.entries()) {
      const x=cx+dx,z=cz+dz,y=hillSurfaceHeight(x,z);
      trunks.push({position:[x,y+height/2,z],scale:[.17,height,.17],color:'#8d8066'});
      for(let j=0;j<5;j++) {
        const a=j*2.39996+i,px=x+Math.cos(a)*(j?1.3:0),pz=z+Math.sin(a)*(j?1.3:0),py=y+height-j*.53;
        crowns.push({position:[px,py,pz],scale:[2.5-j*.15,.62,2.2-j*.13],rotation:[0,a,.08],color:['#7d8d70','#8b9c7d','#9baa89'][j%3]});
        branches.push({position:[(x+px)/2,py-.5,(z+pz)/2],scale:[1.8,.08,.08],rotation:[0,-a,0],color:'#8d8066'});
      }
    }
    instances(group,'grove-trunks',new THREE.CylinderGeometry(1,1,1,7),trunks,'#ffffff');
    instances(group,'grove-pine-crowns',new THREE.IcosahedronGeometry(1,1),crowns,'#ffffff');
    instances(group,'grove-branches',new THREE.BoxGeometry(1,1,1),branches,'#ffffff');
    if(object.understory) {
      const shrubs=[];
      for(const [i,[dx,dz]] of object.trees.entries())for(let k=0;k<7;k++) {
        const a=k*2.4+i,r=.8+(k%3)*.40,x=cx+dx+Math.cos(a)*r,z=cz+dz+Math.sin(a)*r;
        shrubs.push({position:[x,hillSurfaceHeight(x,z)+.30,z],scale:[.78,.42,.66],color:k%3?'#95a286':'#a6af92'});
      }
      instances(group,'grove-understory',new THREE.IcosahedronGeometry(1,1),shrubs,'#ffffff');
    }
  });
  registerObjectType('villa_furniture',object=>{
    const [cx,,cz]=object.position,group=new THREE.Group();group.name=object.id+'-furniture';scene.add(group);
    for(const [dx,dz,angle] of object.benches||[]) {
      const bench=new THREE.Group();bench.position.set(cx+dx,hillSurfaceHeight(cx+dx,cz+dz),cz+dz);bench.rotation.y=angle;group.add(bench);
      for(const x of [-.85,.85])block(bench,'garden-bench-leg',x,.35,0,.12,.70,.66,'#666e5d');
      for(const z of [-.25,0,.25])block(bench,'garden-bench-slat',0,.72,z,2.3,.10,.20,'#ab9274');
      for(const y of [1.02,1.25])block(bench,'garden-bench-back',0,y,-.34,2.3,.16,.10,'#ab9274');
    }
    for(const [dx,dz] of object.lamps||[]) {
      const x=cx+dx,z=cz+dz,y=hillSurfaceHeight(x,z);
      solid(group,new THREE.CylinderGeometry(.07,.10,3.1,8),'#626c59','garden-lamp-post',x,y+1.55,z,false);
      block(group,'garden-lamp-glass',x,y+3.18,z,.36,.48,.36,'#e6d8b8');
      solid(group,new THREE.ConeGeometry(.36,.23,4),'#626c59','garden-lamp-cap',x,y+3.54,z,false);
    }
    pack(group);
  });

  // New family members are opt-in; the approved legacy villa branches stay unchanged.
  function section(parent,name){const g=new THREE.Group();g.name=name;parent.add(g);return g;}
  function seeded(seed=1){let n=seed>>>0;return ()=>{n=(Math.imul(n,1664525)+1013904223)>>>0;return n/4294967296;};}
  function rootAt(object,suffix,grounded=false){
    const [x,y,z]=object.position||[0,0,0],g=new THREE.Group();g.name=object.id+suffix;
    g.position.set(x,grounded?hillSurfaceHeight(x,z)+y:y,z);g.rotation.y=object.rotation||0;scene.add(g);return g;
  }
  function shapeAt(outline){const s=new THREE.Shape();outline.forEach(([x,z],i)=>i?s.lineTo(x,-z):s.moveTo(x,-z));s.closePath();return s;}
  function plate(parent,name,outline,y,thickness,color){
    const g=new THREE.ExtrudeGeometry(shapeAt(outline),{depth:thickness,bevelEnabled:false});g.rotateX(-Math.PI/2);
    return solid(parent,g,color,name,0,y,0);
  }
  function walkable(part){part.updateWorldMatrix(true,false);walkableGeometries.push(part.geometry.clone().applyMatrix4(part.matrixWorld));}
  function boundsEnvelope(id,group){
    group.updateWorldMatrix(true,true);const b=new THREE.Box3().setFromObject(group),points=[];
    if(b.isEmpty())return;
    for(const x of [b.min.x,b.max.x])for(const y of [b.min.y,b.max.y])for(const z of [b.min.z,b.max.z])points.push(new THREE.Vector3(x,y,z));
    modelEnvelopes.set(id,points);
  }
  function label(parent,name,text,w,h,color='#e4ddc7',background='#414e43'){
    const c=document.createElement('canvas');c.width=1024;c.height=256;
    const ctx=c.getContext('2d');ctx.fillStyle=background;ctx.fillRect(0,0,1024,256);ctx.fillStyle=color;ctx.textAlign='center';ctx.textBaseline='middle';
    const lines=Array.isArray(text)?text:[text];lines.forEach((t,i)=>{ctx.font=`${i?'':'bold '} ${lines.length===1?94:64}px Arial`;ctx.fillText(t,512,256*(i+.5)/lines.length,940);});
    const texture=new THREE.CanvasTexture(c);texture.colorSpace=THREE.SRGBColorSpace;
    const p=new THREE.Mesh(new THREE.PlaneGeometry(w,h),new THREE.MeshBasicMaterial({map:texture}));p.name=name;parent.add(p);return p;
  }
  function masonry(parent,name,x,y,z,w,h,d,color='#939084'){
    const g=section(parent,name);block(g,'stone-core',x,y+h/2,z,w,h,d,color);
    const joints=[];
    for(let row=1;row<h/.38;row++){
      joints.push({position:[x,y+row*.38,z+d/2+.009],scale:[w,.018,.012]});
      for(let q=-w/2+(row%2?.36:.7);q<w/2;q+=.74)joints.push({position:[x+q,y+row*.38-.19,z+d/2+.012],scale:[.018,.36,.012]});
      joints.push({position:[x+w/2+.009,y+row*.38,z],scale:[.012,.018,d]});
      for(let q=-d/2+(row%2?.36:.7);q<d/2;q+=.74)joints.push({position:[x+w/2+.012,y+row*.38-.19,z+q],scale:[.012,.36,.018]});
    }
    if(joints.length)instances(g,'villa-stone-joints',new THREE.BoxGeometry(1,1,1),joints,'#b6b2a5');return g;
  }
  function steppingPath(parent,spec,floor){
    const length=spec.length??5,width=spec.width??1.15,gap=spec.gap??.25,step=spec.stepLength??.6;
    const stones=[],start=spec.start||[0,0],end=spec.end||[0,length],n=Math.max(1,Math.floor(Math.hypot(end[0]-start[0],end[1]-start[1])/(step+gap)));
    parent.updateWorldMatrix(true,false);
    for(let i=0;i<=n;i++){
      const t=i/n,x=THREE.MathUtils.lerp(start[0],end[0],t),z=THREE.MathUtils.lerp(start[1],end[1],t),world=parent.localToWorld(new THREE.Vector3(x,0,z)),y=hillSurfaceHeight(world.x,world.z)-floor+.1;
      stones.push({position:[x,y,z],scale:[width,.12,step],rotation:[0,Math.atan2(end[0]-start[0],end[1]-start[1]),0]});
    }
    const p=instances(parent,'villa-stepping-stones',new THREE.BoxGeometry(1,1,1),stones,spec.color||'#c5c2af');
    for(const e of stones){const g=new THREE.BoxGeometry(...e.scale);g.rotateY(e.rotation[1]);g.translate(...e.position);walkableGeometries.push(g.applyMatrix4(parent.matrixWorld));}return p;
  }
  function cottage(object){
    const [w,d]=object.footprint||[7.5,10],wh=object.wallHeight??2.7,rs=object.roof||{},over=rs.overhang??.38,rise=rs.rise??rs.height??(rs.pitch?Math.tan(rs.pitch*Math.PI/180)*(w/2+over):6.6);
    const root=rootAt(object,'-cottage'),samples=[];root.updateWorldMatrix(true,false);
    for(const x of [-w/2,w/2])for(const z of [-d/2,d/2]){const p=root.localToWorld(new THREE.Vector3(x,0,z));samples.push(hillSurfaceHeight(p.x,p.z));}
    const floor=Math.max(...samples)+.16+(object.position?.[1]||0),bottom=Math.min(...samples)-.15;root.position.y=floor;root.userData={floorY:floor,id:object.id};
    const white=object.wallColor||'#ece9de',dark=rs.color||'#6a716e',trim=object.trimColor||'#e4e0d1';
    masonry(root,'villa-cottage-foundation',0,bottom-floor,0,w+.15,floor-bottom,d+.15,object.stoneColor||'#9c998a');
    block(root,'cottage-walls',0,wh/2,0,w,wh,d,white);
    const shoulder=rise*over/(w/2+over);
    for(const side of [-1,1])block(root,'cottage-eave-infill',side*w/2,wh+shoulder/2,0,.10,shoulder,d,white);
    for(const z of [-d/2-.015,d/2+.015]){
      const s=new THREE.Shape();s.moveTo(-w/2,0);s.lineTo(w/2,0);s.lineTo(w/2,shoulder);s.lineTo(0,rise);s.lineTo(-w/2,shoulder);s.closePath();
      const p=solid(root,new THREE.ShapeGeometry(s),white,'cottage-gable',0,wh,z,false);p.material=p.material.clone();p.material.side=THREE.DoubleSide;
      for(const side of [-1,1])line(root,[side*w/2,wh+shoulder,z+.04],[0,wh+rise,z+.04],.12,trim);
      if(z>0){
        windowBay(root,0,1.45,z+.06,1.25,2.35,false);
        for(const side of [-1,1])windowBay(root,side*w*.22,wh+rise*.23,z+.06,.78,1.3,false);
        windowBay(root,0,wh+rise*.54,z+.06,.68,1.15,false);
        for(let y=wh+.35;y<wh+rise*.89;y+=.32){const span=Math.min(w,(w+2*over)*(1-(y-wh)/rise));line(root,[-span/2,y,z+.045],[span/2,y,z+.045],.018,'#c7c7ba');}
      }else windowBay(root,0,wh+rise*.3,z-.04,1.1,1.6,false,Math.PI);
    }
    for(const side of [-1,1])for(const z of [-d*.28,d*.28])windowBay(root,side*(w/2+.035),1.45,z,1.2,1.5,false,side*Math.PI/2);
    if(object.stoneWall!==false){const s=object.stoneWall||{},side=s.side??1;const g=masonry(root,'villa-cottage-stone',side*(w/2+.03),0,0,.12,wh,d,s.color||object.stoneColor);if(side<0)g.rotation.y=0;}
    const roofGroup=section(root,object.id+'-roof');roofGroup.position.y=wh;
    const verts=[],W=w/2+over,D=d/2+over;const tri=(a,b,c)=>verts.push(...a,...b,...c);
    for(const side of [-1,1]){const a=[side*W,0,-D],b=[side*W,0,D],c=[0,rise,D],e=[0,rise,-D];tri(a,b,c);tri(a,c,e);}
    const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(verts,3));g.computeVertexNormals();
    const roofPart=solid(roofGroup,g,dark,'villa-cottage-roof',0,0,0,false);roofPart.material=roofPart.material.clone();roofPart.material.side=THREE.DoubleSide;
    for(const z of [-D,D])for(const side of [-1,1])line(roofGroup,[side*W,-.04,z],[0,rise+.025,z],.14,trim);
    line(roofGroup,[0,rise+.04,-D],[0,rise+.04,D],.10,dark);
    const seams=[];for(const side of [-1,1])for(let y=.32;y<rise;y+=rs.courseSpacing??.42){const x=side*W*(1-y/rise);seams.push({position:[x,y+.012,0],scale:[.018,.018,D*2],color:'#91968b'});}
    instances(roofGroup,'villa-cottage-roof-courses',new THREE.BoxGeometry(1,1,1),seams,'#ffffff');
    roofRecords.push({group:roofGroup,parameters:{kind:'aframe',width:w,depth:d,rise,ridgeHeight:wh+rise},tiers:1,thickness:.16,ridgeOrnament:false});
    if(object.chimney!==false){
      const c=object.chimney||{},height=c.height??wh+rise+.65,x=c.x??w*.45,z=c.z??-d*.2,cw=c.width??.85,cd=c.depth??1;
      masonry(root,'villa-cottage-chimney',x,0,z,cw,height,cd,c.color||object.stoneColor);
      block(root,'cottage-chimney-cap',x,height+.08,z,cw+.28,.16,cd+.24,'#b7b4a5');block(root,'cottage-chimney-flue',x,height+.2,z,cw*.55,.12,cd*.55,'#586055');
    }
    if(object.path){const s=object.path;steppingPath(root,{...s,start:s.start||[0,d/2+.4],end:s.end||[0,d/2+.4+(s.length??5)]},floor);}
    if(object.sign){
      const s=object.sign,g=section(root,'villa-cottage-name'),x=s.x??w*.55,z=s.z??d/2+3;
      const p=root.localToWorld(new THREE.Vector3(x,0,z)),y=hillSurfaceHeight(p.x,p.z)-floor;
      g.position.set(x,y,z);g.rotation.y=s.rotation??-.2;
      for(const side of [-1,1])block(g,'cottage-sign-post',side*.65,.7,0,.11,1.4,.11,'#4c594d');
      block(g,'cottage-sign-board',0,1.05,0,1.5,.55,.10,'#414e43');const face=label(g,'cottage-sign-text',s.text||'VILLA',1.42,.48);face.position.set(0,1.05,.058);
    }
    pack(roofGroup);pack(root,[roofGroup]);boundsEnvelope(object.id,root);return root;
  }
  registerObjectType('villa_cottage',cottage);
  registerObjectType('villa_cluster',object=>{
    const rand=seeded(object.seed??1),area=object.area||[36,36],count=object.positions?.length??object.count??6,cols=Math.ceil(Math.sqrt(count)),rows=Math.ceil(count/cols),[cx,cy,cz]=object.position||[0,0,0],angle=object.rotation||0;
    for(let i=0;i<count;i++){
      const p=object.positions?.[i]||[(i%cols-(cols-1)/2)*area[0]/cols+(rand()-.5)*area[0]/cols*.24,(Math.floor(i/cols)-(rows-1)/2)*area[1]/rows+(rand()-.5)*area[1]/rows*.24,(rand()-.5)*.22];
      const x=cx+Math.cos(angle)*p[0]+Math.sin(angle)*p[1],z=cz-Math.sin(angle)*p[0]+Math.cos(angle)*p[1],id=object.ids?.[i]||`${object.id}-${String(i+1).padStart(2,'0')}`;
      const root=cottage({...object.cottage,id,position:[x,cy,z],rotation:angle+(p[2]??0),path:object.path===false?false:object.path||{},sign:object.sign===false?false:{...object.sign,text:object.names?.[i]||`${object.sign?.prefix||'VILLA'} ${String(i+1).padStart(2,'0')}`}});
      root.name='villa-cluster-member';root.userData.id=id;
    }
  });
  function hotel(object){
    const [w,d]=object.footprint||[32,18],level=object.storeyHeight??3.8,storeys=object.storeys??4,H=level*storeys;
    let outline=object.outline||[[-w/2,-d/2],[w/2,-d/2],[w/2,d/2],[-w/2,d/2]];
    if(outline.length>3&&outline[0].every((v,i)=>v===outline.at(-1)[i]))outline=outline.slice(0,-1);
    const root=rootAt(object,'-villa');root.updateWorldMatrix(true,false);
    const grounds=outline.map(([x,z])=>{const p=root.localToWorld(new THREE.Vector3(x,0,z));return hillSurfaceHeight(p.x,p.z);});
    const floor=Math.max(...grounds)+.18+(object.position?.[1]||0),bottom=Math.min(...grounds)-.12;root.position.y=floor;root.userData={floorY:floor};
    const white=object.wallColor||'#e9e6da',trim=object.trimColor||'#f0ecdf',rail=object.railColor||'#657065',front=section(root,'villa-front-layer');root.userData.frontLayer=front;
    const facade=object.facade||{},frontEdges=facade.frontEdges||[2],entryEdge=object.porch?.edge??frontEdges[0],entryT=object.porch?.at??.5,bayWidth=facade.bayWidth??3.4;
    const area=outline.reduce((s,a,i)=>{const b=outline[(i+1)%outline.length];return s+a[0]*b[1]-b[0]*a[1];},0);
    plate(root,'hotel-foundation',outline,bottom-floor,floor-bottom,'#c5c0b0');
    const roofGroup=section(root,object.id+'-roof');roofGroup.position.y=H;
    const pilasters=section(front,'villa-hotel-pilasters'),balconies=section(front,'villa-french-balconies'),awnings=section(front,'villa-red-awnings'),dormers=section(roofGroup,'villa-hotel-dormers'),rs=object.roof||{},rise=rs.rise??3.6,inset=rs.inset??1.7;
    // Offset each polygon edge inward, intersecting neighbours for a continuous mansard shoulder.
    const shifted=outline.map((a,i)=>{const b=outline[(i+1)%outline.length],dx=b[0]-a[0],dz=b[1]-a[1],l=Math.hypot(dx,dz),nx=(area>0?1:-1)*dz/l,nz=(area>0?-1:1)*dx/l;return {a:[a[0]-nx*inset,a[1]-nz*inset],v:[dx,dz]};});
    const inner=shifted.map((b,i)=>{const a=shifted[(i+outline.length-1)%outline.length],cross=a.v[0]*b.v[1]-a.v[1]*b.v[0];if(Math.abs(cross)<.0001)return b.a;const t=((b.a[0]-a.a[0])*b.v[1]-(b.a[1]-a.a[1])*b.v[0])/cross;return [a.a[0]+a.v[0]*t,a.a[1]+a.v[1]*t];});
    const slopes=[],seams=[];
    for(let i=0;i<outline.length;i++){
      const a=outline[i],b=outline[(i+1)%outline.length],aa=inner[i],bb=inner[(i+1)%outline.length],length=Math.hypot(b[0]-a[0],b[1]-a[1]),nx=(area>0?1:-1)*(b[1]-a[1])/length,nz=(area>0?-1:1)*(b[0]-a[0])/length,angle=Math.atan2(nx,nz);
      const edge=section(front,'hotel-facade-'+i);edge.position.set((a[0]+b[0])/2,0,(a[1]+b[1])/2);edge.rotation.y=angle;
      const isEntry=i===entryEdge,doorX=(area>0?.5-entryT:entryT-.5)*length,doorWidth=object.interior?.doorWidth??2.8,doorHeight=object.interior?.doorHeight??3;
      if(isEntry){
        for(const [lo,hi] of [[-length/2,doorX-doorWidth/2],[doorX+doorWidth/2,length/2]])block(edge,'hotel-wall',(lo+hi)/2,H/2,0,hi-lo,H,.28,white);
        block(edge,'hotel-door-lintel',doorX,(H+doorHeight)/2,0,doorWidth,H-doorHeight,.28,white);
        const door=section(edge,'villa-hotel-door');root.userData.interiorDoor=door;
        for(const side of [-1,1])windowBay(door,doorX+side*doorWidth/4,doorHeight/2,.02,doorWidth/2-.12,doorHeight-.12);
      }else block(edge,'hotel-wall',0,H/2,0,length+.12,H,.28,white);
      for(let s=0;s<=storeys;s++)for(const [dy,projection,height] of [[-.09,.12,.12],[.06,.22,.10]])block(edge,'hotel-cornice',0,s*level+dy,.10,length+.30,height,projection,trim);
      const n=Math.max(1,Math.round(length/bayWidth)),spacing=length/n;
      for(let k=0;k<n;k++){
        const x=(k+.5)*spacing-length/2,ww=facade.windowWidth??Math.min(1.8,spacing*.6),hh=facade.windowHeight??2.45;
        for(let s=0;s<storeys;s++){
          if(isEntry&&s===0&&Math.abs(x-doorX)<doorWidth/2+ww/2)continue;
          const y=s*level+level*.52;windowBay(edge,x,y,.19,ww,hh);
          block(edge,'hotel-window-crown',x,y+hh/2+.18,.30,ww+.35,.13,.38,trim);
          if(s>0&&facade.balconies!==false){
            const g=section(balconies,'french-balcony');g.position.copy(edge.position);g.rotation.copy(edge.rotation);
            block(g,'balcony-floor',x,s*level+.28,.53,ww+.45,.12,.72,trim);
            for(const yy of [s*level+.44,s*level+1.18])line(g,[x-ww/2-.12,yy,.87],[x+ww/2+.12,yy,.87],.035,rail);
            for(let q=-ww/2-.12;q<=ww/2+.13;q+=.19)line(g,[x+q,s*level+.44,.87],[x+q,s*level+1.18,.87],.025,rail);
            for(const side of [-1,1])line(g,[x+side*(ww/2+.12),s*level+1.18,.18],[x+side*(ww/2+.12),s*level+1.18,.87],.035,rail);
          }
          if(s===0&&frontEdges.includes(i)&&facade.awnings!==false){
            const g=section(awnings,'red-awning');g.position.copy(edge.position);g.rotation.copy(edge.rotation);
            const p=block(g,'awning-canvas',x,y+hh/2-.12,.82,ww+.45,.10,1.25,facade.awningColor||'#a46960');p.rotation.x=.18;
            block(g,'awning-valance',x,y+hh/2-.28,1.43,ww+.45,.26,.07,facade.awningColor||'#a46960');
          }
        }
      }
      if(facade.pilasters!==false)for(let k=0;k<=n;k++){
        const x=k*spacing-length/2;if(isEntry&&Math.abs(x-doorX)<doorWidth/2+.25)continue;
        const g=section(pilasters,'hotel-pilaster');g.position.copy(edge.position);g.rotation.copy(edge.rotation);
        block(g,'pilaster-shaft',x,H/2,.2,.25,H-.35,.27,trim);
        for(let s=0;s<storeys;s++){block(g,'pilaster-capital',x,(s+1)*level-.34,.27,.44,.22,.42,trim);for(let j=0;j<3;j++)block(g,'pilaster-flute',x+(j-1)*.065,s*level+level*.53,.35,.012,level-.95,.014,'#c8c7b8');}
      }
      slopes.push(a[0],0,a[1],b[0],0,b[1],bb[0],rise,bb[1],a[0],0,a[1],bb[0],rise,bb[1],aa[0],rise,aa[1]);
      for(let q=.4;q<length;q+=rs.seamSpacing??.7){const t=q/length;const lo=[THREE.MathUtils.lerp(a[0],b[0],t),.02,THREE.MathUtils.lerp(a[1],b[1],t)],hi=[THREE.MathUtils.lerp(aa[0],bb[0],t),rise+.02,THREE.MathUtils.lerp(aa[1],bb[1],t)];seams.push([lo,hi]);}
      if((rs.dormerEdges||frontEdges).includes(i)){
        const dn=rs.dormerCount??Math.max(1,Math.floor(length/(rs.dormerSpacing??4.7)));
        for(let k=0;k<dn;k++){
          const t=(k+.5)/dn,dg=section(dormers,'hotel-dormer'),dw=rs.dormerWidth??1.55,dh=rs.dormerHeight??1.8;dg.position.set(a[0]+(b[0]-a[0])*t-nx*.32,.62,a[1]+(b[1]-a[1])*t-nz*.32);dg.rotation.y=angle;
          block(dg,'dormer-stucco',0,dh/2,-.3,dw+.35,dh,.85,trim);windowBay(dg,0,dh/2,.19,dw,dh-.22);
          frontGable(dg,0,dh,.28,dw+.6,.62,1.5,rs.color||'#68716c',false,trim);
        }
      }
      if(isEntry){
        const ps=object.porch||{},pw=ps.width??7,pd=ps.depth??3.7,ph=ps.height??3.6,g=section(front,'villa-hotel-porch');g.position.copy(edge.position);g.rotation.copy(edge.rotation);
        block(g,'porch-entablature',doorX,ph,pd/2,pw,.30,pd,trim);block(g,'porch-cornice',doorX,ph+.23,pd/2,pw+.5,.18,pd+.25,trim);
        for(const side of [-1,1]){solid(g,new THREE.CylinderGeometry(.19,.24,ph,16),trim,'porch-column',doorX+side*(pw/2-.6),ph/2,pd-.45);for(const y of [.15,ph-.16])block(g,'porch-column-base',doorX+side*(pw/2-.6),y,pd-.45,.62,.20,.62,trim);}
        walkable(block(g,'porch-platform',doorX,-.05,pd/2,pw+.2,.12,pd+.1,'#d6d1c1'));
        for(let j=0;j<3;j++)block(g,'porch-step',doorX,-.09-j*.06,pd+.2+j*.26,pw+.4,.12,.32,'#c8c2b1');
        if(ps.text){const p=label(g,'hotel-porch-lettering',ps.text,pw*.78,.38,'#9d895c',trim);p.position.set(doorX,ph,pd/2+.01);p.rotation.x=-Math.PI/2;}
        boundsEnvelope(object.id+'-entrance',g);
      }
    }
    const rg=new THREE.BufferGeometry();rg.setAttribute('position',new THREE.Float32BufferAttribute(slopes,3));rg.computeVertexNormals();
    const rp=solid(roofGroup,rg,rs.color||'#68716c','villa-mansard-slopes',0,0,0,false);rp.material=rp.material.clone();rp.material.side=THREE.DoubleSide;
    plate(roofGroup,'mansard-flat-cap',inner,rise,.12,rs.color||'#68716c');for(const [a,b] of seams)line(roofGroup,a,b,.018,rs.seamColor||'#92998e');
    if(rs.capSeams!==false){
      const entries=[],xs=inner.map(p=>p[0]),pitch=Math.max(.2,rs.capSeamSpacing??1.1);
      for(let x=Math.min(...xs)+pitch/2;x<Math.max(...xs);x+=pitch){
        const crossings=[];for(let i=0;i<inner.length;i++){
          const a=inner[i],b=inner[(i+1)%inner.length];
          if((a[0]>x)!==(b[0]>x))crossings.push(a[1]+(b[1]-a[1])*(x-a[0])/(b[0]-a[0]));
        }
        crossings.sort((a,b)=>a-b);for(let i=0;i+1<crossings.length;i+=2){const lo=crossings[i]+.03,hi=crossings[i+1]-.03;if(hi>lo)entries.push({position:[x,rise+.132,(lo+hi)/2],scale:[.016,.012,hi-lo]});}
      }
      if(entries.length){const strokes=instances(roofGroup,'villa-mansard-cap-seams',new THREE.BoxGeometry(1,1,1),entries,rs.capSeamColor||'#81897f');strokes.castShadow=false;strokes.receiveShadow=false;}
    }
    roofRecords.push({group:roofGroup,parameters:{kind:'mansard',width:w,depth:d,ridgeHeight:H+rise,rise},tiers:1,thickness:.16,ridgeOrnament:false});
    const porch=front.getObjectByName('villa-hotel-porch');if(porch)pack(porch);
    pack(roofGroup);pack(front,[root.userData.interiorDoor,...(porch?[porch]:[])]);pack(root,[roofGroup,front]);
    if(object.interior)front.traverse(p=>{if(p.material)p.material=p.material.clone();});return root;
  }
  registerObjectType('villa_hotel',hotel);
  function water(object){
    const root=rootAt(object,'-water'),[w,d]=object.size||[24,18],outline=object.outline||Array.from({length:64},(_,i)=>{const a=i/64*Math.PI*2;return [Math.cos(a)*w/2,Math.sin(a)*d/2];});
    const surface=solid(root,new THREE.ShapeGeometry(shapeAt(outline)),object.color||'#a2b6ad','villa-water-surface',0,object.level??0,0,false);surface.rotation.x=-Math.PI/2;
    const shore=section(root,'villa-shoreline');shore.position.y=object.level??0;
    if(object.shoreline!==false)for(let i=0;i<outline.length;i++){
      const a=outline[i],b=outline[(i+1)%outline.length];line(shore,[a[0],.035,a[1]],[b[0],.035,b[1]],object.shoreWidth??.22,object.shoreColor||'#b5b5a0');
    }
    const inside=(x,z)=>{let hit=false;for(let i=0,j=outline.length-1;i<outline.length;j=i++){const a=outline[i],b=outline[j];if((a[1]>z)!==(b[1]>z)&&x<(b[0]-a[0])*(z-a[1])/(b[1]-a[1])+a[0])hit=!hit;}return hit;};
    const rand=seeded(object.seed??3),bounds=new THREE.Box2().setFromPoints(outline.map(p=>new THREE.Vector2(...p))),ripples=section(root,'villa-water-ripples');ripples.position.y=object.level??0;
    for(let i=0;i<(object.ripples??24);i++){
      const x=THREE.MathUtils.lerp(bounds.min.x,bounds.max.x,rand()),z=THREE.MathUtils.lerp(bounds.min.y,bounds.max.y,rand()),length=.8+rand()*2.8;
      if(inside(x-length/2,z)&&inside(x+length/2,z))line(ripples,[x-length/2,.025,z],[x+length/2,.025,z+.04],.018,object.rippleColor||'#c6d2c5');
    }
    pack(shore);pack(ripples);pack(root,[surface,shore,ripples]);return root;
  }
  registerObjectType('villa_water',water);
  function cafe(parent,tables,options={}){
    const root=section(parent,'villa-cafe-tables'),wood=options.furnitureColor||'#817967';
    for(const entry of tables){
      const [x,z,angle=0]=entry,g=section(root,'cafe-setting');g.position.set(x,options.floorY??0,z);g.rotation.y=angle;
      solid(g,new THREE.CylinderGeometry(.67,.67,.07,32),options.tableColor||'#d1c9b6','cafe-tabletop',0,.74,0,false);
      solid(g,new THREE.CylinderGeometry(.045,.09,.67,8),wood,'cafe-table-leg',0,.37,0,false);solid(g,new THREE.CylinderGeometry(.3,.35,.06,12),wood,'cafe-table-foot',0,.04,0,false);
      for(let k=0;k<(options.chairs??4);k++){
        const a=k*Math.PI*2/(options.chairs??4),chair=section(g,'cafe-chair');chair.position.set(Math.sin(a)*1.03,0,Math.cos(a)*1.03);chair.rotation.y=a+Math.PI;
        block(chair,'cafe-chair-seat',0,.44,0,.46,.06,.45,wood);block(chair,'cafe-chair-back',0,.7,-.21,.47,.44,.06,wood);
        for(const sx of [-1,1])for(const sz of [-1,1])block(chair,'cafe-chair-leg',sx*.18,.22,sz*.17,.035,.44,.035,wood);
      }
      if(options.umbrellas){
        const p=section(g,'villa-parasol'),r=options.umbrellaRadius??1.9,h=options.umbrellaHeight??2.8;
        solid(p,new THREE.CylinderGeometry(.034,.043,h,10),wood,'parasol-pole',0,h/2,0,false);
        const vertices=[];for(let k=0;k<8;k++){const a=k*Math.PI/4,b=(k+1)*Math.PI/4;vertices.push(0,h+.34,0,Math.cos(a)*r,h,Math.sin(a)*r,Math.cos(b)*r,h,Math.sin(b)*r);line(p,[0,h+.35,0],[Math.cos(a)*r,h,Math.sin(a)*r],.022,'#c3c2ae');}
        const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));geo.computeVertexNormals();const cap=solid(p,geo,options.umbrellaColor||'#e7e2cf','parasol-canopy',0,0,0,false);cap.material=cap.material.clone();cap.material.side=THREE.DoubleSide;
      }
    }return root;
  }
  registerObjectType('villa_terrace',object=>{
    const root=rootAt(object,'-terrace'),[w,d]=object.size||[16,10],h=object.thickness??.24;
    walkable(block(root,'terrace-deck',0,-h/2,0,w,h,d,object.color||'#b4a28b'));
    const piers=section(root,'villa-deck-piers');root.updateWorldMatrix(true,false);
    if(object.supports!==false){
      const nx=Math.max(1,Math.ceil(w/(object.supportSpacing??4))),nz=Math.max(1,Math.ceil(d/(object.supportSpacing??4)));
      for(let i=0;i<=nx;i++)for(let j=0;j<=nz;j++){
        const x=(-w/2+.35)+(w-.7)*i/nx,z=(-d/2+.35)+(d-.7)*j/nz,p=root.localToWorld(new THREE.Vector3(x,0,z)),bottom=hillSurfaceHeight(p.x,p.z)-root.position.y-.12,top=-h;
        if(top>bottom)block(piers,'terrace-support',x,(top+bottom)/2,z,.22,top-bottom,.22,object.supportColor||'#9f9d8d');
      }
    }
    for(let z=-d/2+.3;z<d/2;z+=object.plankWidth??.38)line(root,[-w/2,.012,z],[w/2,.012,z],.018,'#9e947f');
    cafe(root,object.tables||[[-4,-1],[0,-1],[4,-1]],{...object,umbrellas:object.umbrellas??true});
    if(object.rails)for(const side of [-1,1]){for(let x=-w/2;x<=w/2;x+=2)block(root,'terrace-rail-post',x,.5,side*d/2,.065,1,.065,'#767e6b');line(root,[-w/2,1,side*d/2],[w/2,1,side*d/2],.065,'#767e6b');}
    pack(piers);pack(root,[piers]);
  });
  registerObjectType('villa_pool',object=>{
    const root=rootAt(object,'-pool'),[w,d]=object.size||[18,9],deck=object.deck??2,depth=object.depth??.8,c=object.color||'#9bbab6';
    block(root,'pool-basin',0,-depth/2,0,w,depth,d,'#bac5b9');
    const water=section(root,'villa-pool-water');block(water,'pool-surface',0,.025,0,w-.25,.05,d-.25,c);
    const s=object.infinitySide??1;
    for(const side of [-1,1]){
      walkable(block(root,'pool-deck',side*(w/2+deck/2),-.08,0,deck,.16,d+deck*2,object.deckColor||'#b7a48c'));
      if(side!==s)walkable(block(root,'pool-deck',0,-.08,side*(d/2+deck/2),w,.16,deck,object.deckColor||'#b7a48c'));
      if(side!==s)block(root,'pool-coping',0,.075,side*d/2,w+.25,.15,.28,'#dbd8c6');
      block(root,'pool-coping',side*w/2,.075,0,.28,.15,d,'#dbd8c6');
    }
    const spill=section(root,'villa-pool-spill');block(spill,'pool-weir',0,-depth/2,s*(d/2+.02),w,depth,.08,'#b8cfca');block(root,'pool-overflow-trough',0,-depth-.05,s*(d/2+.2),w,.12,.48,'#8daba4');
    for(let x=-w/2-deck;x<w/2+deck;x+=.42)for(const side of [-1,1])if(side!==s)line(root,[x,.008,side*(d/2+.18)],[x,.008,side*(d/2+deck)],.016,'#9f937e');
    for(const side of [-1,1])for(let z=-d/2;z<d/2;z+=.42)line(root,[side*(w/2+.2),.008,z],[side*(w/2+deck),.008,z],.016,'#9f937e');
    pack(root);
  });
  function bonsai(parent,spec={}){
    const g=section(parent,'villa-bonsai');g.position.fromArray(spec.position||[0,0,0]);const h=spec.height??3.2,s=(spec.spread??3.4)/3.4,pr=spec.potRadius??.85;
    solid(g,new THREE.CylinderGeometry(pr,pr*.765,.65,24),spec.potColor||'#777e70','bonsai-pot',0,.325,0);solid(g,new THREE.CylinderGeometry(pr+.01,pr+.01,.06,32),'#b5b09b','bonsai-pot-rim',0,.67,0);
    line(g,[0,.64,0],[-.22*s,h*.54,0],.24,'#817863');line(g,[-.22*s,h*.54,0],[.2*s,h*.9,.08*s],.16,'#817863');
    const leaves=[];for(let i=0;i<11;i++){const a=i*2.4,r=i%3*.48*s,y=h*(.64+(i%4)*.1),x=Math.cos(a)*r,z=Math.sin(a)*r;line(g,[-.05*s,y-.3,0],[x,y,z],.065,'#817863');leaves.push({position:[x,y,z],scale:[.75*s,.28,.65*s],rotation:[0,a,0],color:['#6e8168','#839578','#929e7e'][i%3]});}
    instances(g,'bonsai-clouds',new THREE.IcosahedronGeometry(1,1),leaves,'#ffffff');return g;
  }
  registerObjectType('villa_court',object=>{
    const root=rootAt(object,'-court',true),[w,d]=object.size||[12,16],pitch=object.tileSize??1.1,tiles=[];
    walkable(block(root,'marble-substrate',0,.035,0,w,.07,d,'#a6a99e'));
    const nx=Math.ceil(w/pitch),nz=Math.ceil(d/pitch),dx=w/nx,dz=d/nz;
    for(let i=0;i<nx;i++)for(let j=0;j<nz;j++)tiles.push({position:[-w/2+(i+.5)*dx,.08,-d/2+(j+.5)*dz],scale:[dx-.018,.045,dz-.018],color:(i+j)%3?object.color||'#cfcec3':object.accentColor||'#aeb3aa'});
    instances(root,'villa-marble-tiles',new THREE.BoxGeometry(1,1,1),tiles,'#ffffff');
    cafe(root,object.tables||[[-3,3],[3,3]],{...object,floorY:.11,umbrellas:object.umbrellas??false});if(object.bonsai!==false)bonsai(root,object.bonsai||{});pack(root);
  });
  registerObjectType('villa_sign_wall',object=>{
    const root=rootAt(object,'-sign-wall',true),w=object.width??7,h=object.height??1.25,curve=object.curve??.85,depth=object.depth??.45,n=40,g=section(root,'villa-curved-stone-wall');
    for(let i=0;i<n;i++){
      const x=-w/2+(i+.5)*w/n,z=curve*(1-(2*x/w)**2),slope=-8*curve*x/(w*w),p=block(g,'curved-stone',x,h/2,z,w/n+.025,h,depth,object.color||'#d0cdbb');p.rotation.y=-Math.atan(slope);
      block(g,'stone-coping',x,h+.045,z,w/n+.035,.09,depth+.12,'#e1dcc8');
      for(let y=.3;y<h;y+=.3)block(g,'sign-stone-course',x,y,z+depth/2+.015,w/n+.025,.018,.018,'#b4b3a4');
    }
    if(object.crown!==false){
      const s=new THREE.Shape();s.moveTo(-w*.26,0);s.quadraticCurveTo(-w*.24,h*.8,0,h*.9);s.quadraticCurveTo(w*.24,h*.8,w*.26,0);s.closePath();
      solid(g,new THREE.ExtrudeGeometry(s,{depth:depth,bevelEnabled:false,curveSegments:32}),object.color||'#d0cdbb','sign-arched-crown',0,h*.7,curve-depth/2);
    }
    const face=label(g,'stone-sign-lettering',object.lines||['VILLA'],w*.69,h*.7,object.textColor||'#dbd5ba',object.tabletColor||'#566257');face.position.set(0,h*.82,curve+depth/2+.08);pack(root);
  });
  registerInteriorKit('villa_hotel_lounge',(building,{roof})=>{
    const shell=scene.getObjectByName(building.id+'-villa'),spec=building.interior,[w,H,d]=spec.size||[12,3.8,12],offset=spec.offset||[0,0,0],group=new THREE.Group();group.name=building.id+'-interior';group.position.copy(shell.position);group.rotation.y=shell.rotation.y+(spec.rotation||0);
    group.position.add(new THREE.Vector3(...offset).applyAxisAngle(new THREE.Vector3(0,1,0),shell.rotation.y));
    const cream=spec.wallColor||'#e7e0d0',wood=spec.timberColor||'#786b57',trim=spec.trimColor||'#f0e8d7',panels=section(group,'villa-cream-panels');
    block(panels,'lounge-back-wall',0,H/2,-d/2,w,H,.18,cream);
    for(const side of [-1,1])block(panels,'lounge-side-wall',side*w/2,H/2,0,.18,H,d,cream);
    const door=spec.doorWidth??2.8,dh=spec.doorHeight??3;
    for(const side of [-1,1])block(panels,'lounge-front-wall',side*(w+door)/4,H/2,d/2,(w-door)/2,H,.18,cream);
    block(panels,'lounge-door-head',0,(H+dh)/2,d/2,door,H-dh,.18,cream);
    for(const side of [-1,1])for(let z=-d/2+.6;z<d/2-.5;z+=1.8){
      for(const y of [.18,1.05,H-.3])block(panels,'cream-panel-rail',side*(w/2-.12),y,z,.07,.055,1.72,trim);
      for(const dz of [-.82,.82])block(panels,'cream-panel-stile',side*(w/2-.12),H/2,z+dz,.07,H-.45,.05,trim);
    }
    for(const side of [-1,1])for(const z of spec.windows||[-d*.28,d*.08]){
      const win=section(panels,'lounge-tall-window');win.position.set(side*(w/2-.15),H*.55,z);win.rotation.y=-side*Math.PI/2;windowBay(win,0,0,0,1.65,H*.67);
      for(const dz of [-1,1])for(let k=0;k<4;k++)solid(panels,new THREE.CylinderGeometry(.045,.065,H*.77,7),'#c6bdab','lounge-curtain',side*(w/2-.22)-side*k*.025,H*.5,z+dz*(.89+k*.055),false);
    }
    const floor=section(group,'villa-lounge-marble');block(floor,'lounge-floor',0,.025,0,w,.05,d,'#d6cfbe');
    const tiles=[];for(let x=-w/2+.5;x<w/2;x+=1)for(let z=-d/2+.5;z<d/2;z+=1)tiles.push({position:[x,.057,z],scale:[.991,.014,.991],color:(Math.round(x+z)%3)?'#d8d2c2':'#c9c5b8'});
    instances(floor,'lounge-marble-tiles',new THREE.BoxGeometry(1,1,1),tiles,'#ffffff');
    const seatings=section(group,'villa-lounge-seating');
    for(const setting of spec.seating||[{position:[-2.6,0,1],chairs:3},{position:[2.6,0,1],chairs:3}]){
      const g=section(seatings,'lounge-setting');g.position.fromArray(setting.position||[0,0,0]);
      const tr=setting.tableRadius??.6;
      solid(g,new THREE.CylinderGeometry(tr,tr,.075,48),wood,'lounge-round-table',0,.57,0,false);
      if((setting.tableStyle??'shelf')==='shelf'){
        solid(g,new THREE.CylinderGeometry(tr*.82,tr*.82,.045,40),wood,'lounge-table-shelf',0,.14,0,false);
        for(let k=0;k<4;k++){const a=Math.PI/4+k*Math.PI/2;solid(g,new THREE.CylinderGeometry(.028,.042,.52,10),wood,'lounge-table-leg',Math.sin(a)*tr*.72,.3,Math.cos(a)*tr*.72,false);}
      }else{
        solid(g,new THREE.CylinderGeometry(.055,.09,.5,10),wood,'lounge-table-pedestal',0,.3,0,false);
        solid(g,new THREE.CylinderGeometry(.32,.38,.05,16),wood,'lounge-table-foot',0,.07,0,false);
      }
      solid(g,new THREE.CylinderGeometry(.035,.07,.22,12),'#b9b79b','lounge-bud-vase',0,.73,0,false);solid(g,new THREE.IcosahedronGeometry(.09,1),'#ab7d79','lounge-single-flower',0,.92,0,false);
      const angles=setting.angles||Array.from({length:setting.chairs??3},(_,i)=>(i/(setting.chairs??3)*Math.PI*2)+.45);
      for(const a of angles){
        const chair=section(g,'hotel-armchair');chair.position.set(Math.sin(a)*1.12,.07,Math.cos(a)*1.12);chair.rotation.y=a+Math.PI;
        for(const x of [-.27,.27])for(const z of [-.24,.24])block(chair,'lounge-chair-leg',x,.18,z,.055,.36,.055,wood);
        block(chair,'lounge-chair-seat',0,.4,0,.67,.14,.62,spec.upholsteryColor||'#d9cfb8');
        block(chair,'lounge-chair-back-frame',0,.72,-.28,.73,.59,.10,wood);block(chair,'lounge-chair-back-cushion',0,.73,-.21,.61,.47,.09,spec.upholsteryColor||'#d9cfb8');
        for(const side of [-1,1]){block(chair,'lounge-chair-arm',side*.36,.62,0,.065,.065,.65,wood);block(chair,'lounge-chair-arm-post',side*.36,.46,.23,.05,.30,.05,wood);}
      }
      const rug=setting.rug||[3.6,3.3];block(g,'lounge-muted-rug',0,.083,0,rug[0],.025,rug[1],spec.rugColor||'#b29a8b');
      for(const inset of [.11,.19]){
        for(const z of [-rug[1]/2+inset,rug[1]/2-inset])line(g,[-rug[0]/2+inset,.10,z],[rug[0]/2-inset,.10,z],.018,'#d6c8af');
        for(const x of [-rug[0]/2+inset,rug[0]/2-inset])line(g,[x,.10,-rug[1]/2+inset],[x,.10,rug[1]/2-inset],.018,'#d6c8af');
      }
      if(setting.rugPattern!==false){
        const motifs=[];for(let x=-rug[0]/2+.35;x<rug[0]/2-.25;x+=.38)for(let z=-rug[1]/2+.35;z<rug[1]/2-.25;z+=.38){
          if(Math.abs(x)<tr+.13&&Math.abs(z)<tr+.13)continue;
          motifs.push({position:[x,.102,z],scale:[.055,.006,.095],rotation:[0,Math.PI/4,0],color:(Math.round(x/.38+z/.38)%2)?'#bba88f':'#ccb9a0'});
        }
        instances(g,'villa-rug-motifs',new THREE.BoxGeometry(1,1,1),motifs,'#ffffff');
      }
    }
    const bar=section(group,'villa-mirrored-bar'),bs=spec.bar||{};bar.position.fromArray(bs.position||[0,0,-d/2+.7]);const bw=bs.width??w*.62;
    block(bar,'bar-cabinet',0,.6,0,bw,1.2,.65,wood);block(bar,'bar-counter',0,1.25,.13,bw+.18,.1,.9,'#c4b89e');
    block(bar,'bar-mirror',0,2.4,-.29,bw,2,.035,'#b8c3b5');
    for(const x of [-bw/2,0,bw/2])block(bar,'bar-mirror-frame',x,2.4,-.23,.07,2.1,.07,'#9f9277');for(const y of [1.38,3.4])block(bar,'bar-mirror-rail',0,y,-.23,bw+.1,.07,.07,'#9f9277');
    for(let x=-bw/2+.3;x<bw/2;x+=.52){block(bar,'bar-front-panel',x,.63,.34,.42,.91,.025,'#94816a');solid(bar,new THREE.CylinderGeometry(.05,.065,.26,8),'#9baf97','bar-bottle',x,1.46,-.03,false);solid(bar,new THREE.CylinderGeometry(.06,.04,.11,10),'#ded7bc','bar-glass',x+.15,1.38,.26,false);}
    const piano=section(group,'villa-grand-piano'),ps=spec.piano||{};piano.position.fromArray(ps.position||[-w*.31,0,-d*.22]);piano.rotation.y=ps.rotation??.3;
    const black=ps.color||'#41443f',shape=new THREE.Shape();shape.moveTo(-.72,.63);shape.lineTo(.72,.63);shape.bezierCurveTo(.8,-.1,.74,-.7,.36,-1.18);shape.bezierCurveTo(-.02,-1.65,-.76,-1.3,-.73,-.6);shape.closePath();
    const pg=new THREE.ExtrudeGeometry(shape,{depth:.26,bevelEnabled:false,curveSegments:40});pg.rotateX(-Math.PI/2);solid(piano,pg,black,'grand-piano-body',0,.77,0);
    const lid=section(piano,'grand-piano-open-lid');lid.position.set(-.68,1.06,-.5);lid.rotation.z=ps.lidAngle??.5;
    const lg=new THREE.ShapeGeometry(shape);lg.rotateX(-Math.PI/2);const lp=solid(lid,lg,black,'grand-piano-lid',.68,0,.5);lp.material=lp.material.clone();lp.material.side=THREE.DoubleSide;
    line(piano,[.55,1.03,-.9],[.55,1.06+1.23*Math.sin(lid.rotation.z),-.9],.025,'#8f8c7c');
    for(const [x,z] of [[-.55,-.4],[.55,-.4],[.1,1.05]]){solid(piano,new THREE.CylinderGeometry(.04,.07,.75,10),black,'piano-leg',x,.42,z,false);solid(piano,new THREE.SphereGeometry(.055,8,6),'#9f977a','piano-caster',x,.07,z,false);}
    block(piano,'piano-key-bed',0,.8,-.76,1.38,.12,.35,black);
    for(let i=0;i<28;i++){const x=(i-13.5)*.045;block(piano,'piano-white-key',x,.88,-.81,.042,.045,.26,'#e7e2d1');if(![2,6].includes(i%7))block(piano,'piano-black-key',x+.024,.92,-.73,.024,.04,.15,black);}
    block(piano,'piano-bench',0,.47,-1.35,.8,.10,.42,black);for(const x of [-.32,.32])for(const z of [-1.5,-1.2])block(piano,'piano-bench-leg',x,.24,z,.04,.48,.04,black);
    const ceiling=new THREE.Group();ceiling.name='villa-hotel-ceiling';ceiling.position.set(offset[0],offset[1]+H-roof.position.y,offset[2]);ceiling.rotation.y=spec.rotation||0;
    block(ceiling,'sealed-cream-ceiling',0,.05,0,w+.25,.20,d+.25,cream);
    for(const side of [-1,1]){block(ceiling,'ceiling-coffer',side*(w/2-.3),-.14,0,.3,.23,d,trim);block(ceiling,'ceiling-coffer',0,-.14,side*(d/2-.3),w,.23,.3,trim);}
    for(let z=-d/2+1.5;z<d/2;z+=2.7)for(const x of [-w*.32,w*.32])solid(ceiling,new THREE.CylinderGeometry(.065,.065,.025,12),'#ded4b4','ceiling-downlight',x,-.072,z,false);
    for(const g of group.children)pack(g);pack(ceiling);return {group,ceiling,front:shell.userData.frontLayer,door:shell.userData.interiorDoor};
  });
})();
