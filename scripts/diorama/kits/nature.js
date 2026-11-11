// Nature family. Metres, local +z is the front of a cliff; rotations are degrees.
(()=>{
  const C={rock:'#9b9685',seam:'#797b6a',moss:'#929f80',water:'#a4b0a0',foam:'#e1e6dc',path:'#d3cec0',edge:'#aaa892',wood:'#95826c',rail:'#7e8879',leaf:'#92a284',trunk:'#837867',tent:'#b7ae91'};
  const landscapes=new Map();
  function root(o){const g=new THREE.Group();g.name=o.id+'-nature';g.position.set(...(o.position||[0,0,0]));if(o.baseY)g.position.y+=o.baseY;g.rotation.y=(o.rotation||0)*Math.PI/180;scene.add(g);return g;}
  function add(g,geometry,color,name){const m=new THREE.Mesh(geometry,material(color));m.name=name||'';m.castShadow=true;m.receiveShadow=true;g.add(m);return m;}
  function block(g,p,s,c,name){const m=add(g,new THREE.BoxGeometry(...s),c,name);m.position.set(...p);return m;}
  function line(g,vertices,c,name,opacity=.5){const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));const m=new THREE.LineSegments(geo,new THREE.LineBasicMaterial({color:c,transparent:true,opacity}));m.name=name;g.add(m);return m;}
  function random(seed=1){let n=seed;return ()=>{n=(Math.imul(n,1664525)+1013904223)>>>0;return n/4294967296;};}
  function instances(g,geo,items,c,name){
    if(!items.length)return;
    const m=new THREE.InstancedMesh(geo,material(c),items.length),d=new THREE.Object3D();m.name=name;m.castShadow=true;m.receiveShadow=true;g.add(m);
    items.forEach((p,i)=>{d.position.set(...p.p);d.scale.set(...(p.s||[1,1,1]));d.rotation.set(...(p.r||[0,0,0]),p.order||'XYZ');d.updateMatrix();m.setMatrixAt(i,d.matrix);if(p.c)m.setColorAt(i,new THREE.Color(p.c));});
    m.computeBoundingBox();m.computeBoundingSphere();m.instanceMatrix.needsUpdate=true;
    if(currentEnvelope){g.updateMatrixWorld(true);geo.computeBoundingBox();const b=geo.boundingBox,t=new THREE.Matrix4();for(let i=0;i<items.length;i++){m.getMatrixAt(i,t);for(const x of [b.min.x,b.max.x])for(const y of [b.min.y,b.max.y])for(const z of [b.min.z,b.max.z])currentEnvelope.push(new THREE.Vector3(x,y,z).applyMatrix4(t).applyMatrix4(m.matrixWorld));}}
    return m;
  }
  function rodItems(items,a,b,r){const u=new THREE.Vector3(...a),v=new THREE.Vector3(...b),d=v.clone().sub(u),q=new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0,1,0),d.clone().normalize()),e=new THREE.Euler().setFromQuaternion(q);items.push({p:u.add(v).multiplyScalar(.5).toArray(),s:[r,d.length(),r],r:[e.x,e.y,e.z]});}
  function paved(m){m.userData.paving=true;m.updateWorldMatrix(true,false);let geo=m.geometry.index?m.geometry.toNonIndexed():m.geometry.clone();for(const key of Object.keys(geo.attributes))if(!['position','normal'].includes(key))geo.deleteAttribute(key);walkableGeometries.push(geo.applyMatrix4(m.matrixWorld));return m;}
  function slab(corners,thickness){
    const v=[],top=corners.map(p=>[p[0],p[1]+thickness,p[2]]),quad=(a,b,c,d)=>v.push(...a,...b,...c,...a,...c,...d);
    quad(...top);quad(corners[3],corners[2],corners[1],corners[0]);for(let i=0;i<4;i++){const j=(i+1)%4;quad(corners[i],corners[j],top[j],top[i]);}
    const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(v,3));geo.computeVertexNormals();return geo;
  }
  function compact(g){
    const groups=new Map();for(const m of g.children){if(!m.isMesh||m.isInstancedMesh||m.name||m.userData.paving)continue;const key=m.material.color.getHexString();if(!groups.has(key))groups.set(key,[]);groups.get(key).push(m);}
    for(const parts of groups.values()){if(parts.length<2)continue;const geos=parts.map(m=>{m.updateMatrix();return (m.geometry.index?m.geometry.toNonIndexed():m.geometry.clone()).applyMatrix4(m.matrix);});const m=add(g,mergeGeometries(geos),parts[0].material.color);parts.forEach(p=>{g.remove(p);p.geometry.dispose();});geos.forEach(p=>p.dispose());m.castShadow=true;}
  }
  function register(type,builder){registerObjectType(type,o=>{const g=builder(o);compact(g);});}
  register('nature_terrain',terrain);
  function terrain(o){
    const g=root(o),[w,h,d]=o.size||[28,8,12],section=o.section||[[-d/2,0],[-d/2,h],[d/2,h*.94],[d*.05,h*.22],[-d*.1,0]],jag=o.jaggedness??.32,n=o.segments??28,vertices=[],rand=random(o.seed??1),jitter=Array.from({length:n+1},()=>rand()-.5);
    const point=(i,j)=>{const [z,y,scale=1]=section[j];return [(-w/2+i*w/n)*scale,y===0?0:y+Math.sin(i*1.7)*jag*.22,z+jitter[i]*jag];};
    const tri=(a,b,c)=>vertices.push(...a,...b,...c);
    for(let i=0;i<n;i++)for(let j=0;j<section.length;j++){const k=(j+1)%section.length;tri(point(i,j),point(i+1,j),point(i+1,k));tri(point(i,j),point(i+1,k),point(i,k));}
    for(const i of [0,n])for(const indices of THREE.ShapeUtils.triangulateShape(section.map(([z,y])=>new THREE.Vector2(z,y)),[]))tri(...indices.map(j=>point(i,j)));
    const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));geo.computeVertexNormals();const rock=add(g,geo,o.color||C.rock,o.id+'-rock');rock.material.side=THREE.DoubleSide;
    const faceAt=y=>{const hits=[];for(let i=0;i<section.length;i++){const a=section[i],b=section[(i+1)%section.length];if(y>=Math.min(a[1],b[1])&&y<=Math.max(a[1],b[1])&&a[1]!==b[1]){const t=(y-a[1])/(b[1]-a[1]);hits.push([THREE.MathUtils.lerp(a[0],b[0],t),THREE.MathUtils.lerp(a[2]??1,b[2]??1,t)]);}}return hits.sort((a,b)=>b[0]-a[0])[0]||[0,1];};
    const faceZ=y=>faceAt(y)[0];
    const strata=[];for(let row=1;row<=(o.strata??12);row++){const y=h*row/((o.strata??12)+1),[front,scale]=faceAt(y);for(let i=0;i<n;i++){const x=-w/2+i*w/n,z=front+.025;strata.push(x*scale,y+Math.sin(i*1.7)*jag*.22,z+jitter[i]*jag,(x+w/n)*scale,y+Math.sin((i+1)*1.7)*jag*.22,z+jitter[i+1]*jag);}}
    line(g,strata,o.seamColor||C.seam,o.id+'-strata',.34);
    const stones=[];for(let i=0;i<(o.boulders??12);i++){const x=(rand()-.5)*w,s=.45+rand()*.8;stones.push({p:[x,s*.7*.850650808,faceZ(.2)+.2+rand()],s:[s,s*.7,s*.75],r:[0,rand()*6,0]});}instances(g,new THREE.IcosahedronGeometry(1,0),stones,o.boulderColor||o.color||C.rock,o.id+'-boulders');
    if(o.moss!==false){
      const patches=[],top=section.reduce((a,b)=>b[1]>a[1]?b:a),scale=top[2]??1,localRock=new THREE.Mesh(geo,rock.material),ray=new THREE.Raycaster(new THREE.Vector3(),new THREE.Vector3(0,-1,0)),maxZ=Math.max(...section.map(p=>p[0]));
      for(let i=0;i<n;i++){
        const x=(-w/2+(i+rand())*w/n)*scale,z=top[0]+rand()*Math.min(2.5,Math.max(0,maxZ-top[0]));
        ray.ray.origin.set(x,top[1]+jag+10,z);const hit=ray.intersectObject(localRock)[0],sy=.1+rand()*.15,sx=w/n*(.4+rand()*.8)*scale,sz=.4+rand();
        if(hit)patches.push({p:[x,hit.point.y+sy,z],s:[sx,sy,sz]});
      }
      instances(g,new THREE.SphereGeometry(1,8,5),patches,o.mossColor||C.moss,o.id+'-moss');
    }
    return g;
  }
  register('nature_water',o=>{
    const g=root(o),[w,d]=o.size||[24,18],outline=o.outline||Array.from({length:48},(_,i)=>[Math.cos(i*Math.PI/24)*w/2,Math.sin(i*Math.PI/24)*d/2]),shape=new THREE.Shape();outline.forEach(([x,z],i)=>i?shape.lineTo(x,-z):shape.moveTo(x,-z));shape.closePath();
    const geo=new THREE.ShapeGeometry(shape);geo.rotateX(-Math.PI/2);const m=add(g,geo,o.color||C.water,o.id+'-surface');m.position.y=o.level??.035;m.castShadow=false;
    const within=(x,z)=>{let inside=false;for(let i=0,j=outline.length-1;i<outline.length;j=i++){const a=outline[i],b=outline[j];if((a[1]>z)!==(b[1]>z)&&x<(b[0]-a[0])*(z-a[1])/(b[1]-a[1])+a[0])inside=!inside;}return inside;};
    const ripples=[],rand=random(o.seed??3);for(let k=0;k<(o.ripples??22);k++){const radius=.4+rand()*w*.48,c=o.rippleCenter||[0,0],a=rand()*Math.PI*2,span=.4+rand();for(let j=0;j<20;j++){const t=a+j*span/20,t2=a+(j+1)*span/20,x=c[0]+Math.cos(t)*radius,z=c[1]+Math.sin(t)*radius*.38,x2=c[0]+Math.cos(t2)*radius,z2=c[1]+Math.sin(t2)*radius*.38;if(within(x,z)&&within(x2,z2)&&within((x+x2)/2,(z+z2)/2))ripples.push(x,(o.level??.035)+.009,z,x2,(o.level??.035)+.009,z2);}}
    line(g,ripples,o.rippleColor||C.foam,o.id+'-ripples',.28);return g;
  });
  register('nature_cascade',cascade);
  function cascade(o){
    if(o.tiers)return tieredCascade(o);
    const g=root(o),w=o.width??16,path=o.profile||[[0,8],[.5,7.6],[1.2,.035]],cols=o.ribbons??80,rows=o.segments??36,rand=random(o.seed??5),vertices=[],colours=[],streaks=[],base=o.spread??.05;
    const lengths=path.slice(1).map((b,i)=>Math.hypot(b[0]-path[i][0],b[1]-path[i][1])),total=lengths.reduce((a,b)=>a+b,0);
    const at=t=>{let s=t*total;for(let i=0;i<lengths.length;i++){if(s<=lengths[i]||i===lengths.length-1){const v=s/lengths[i];return [THREE.MathUtils.lerp(path[i][0],path[i+1][0],v),THREE.MathUtils.lerp(path[i][1],path[i+1][1],v)];}s-=lengths[i];}};
    const p=(u,t)=>{const [z,y]=at(t),x=(u-.5)*w*(1+t*base)+Math.sin(t*17+u*8)*(o.edgeWaviness??.16)*(2*u-1)**8;return [x,y+.045*Math.sin(u*41+t*9),z+.09*Math.sin(u*57+t*8)];};
    const source=new THREE.Color(o.color||'#c9d5ce'),foamColor=new THREE.Color(o.foamColor||C.foam);
    for(let i=0;i<cols;i++){const c=source.clone().lerp(foamColor,rand()*(o.flowVariation??.5));for(let j=0;j<rows;j++){const a=p(i/cols,j/rows),b=p((i+1)/cols,j/rows),cc=p((i+1)/cols,(j+1)/rows),d=p(i/cols,(j+1)/rows);vertices.push(...a,...b,...cc,...a,...cc,...d);for(let k=0;k<6;k++)colours.push(c.r,c.g,c.b);}}
    const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));geo.setAttribute('color',new THREE.Float32BufferAttribute(colours,3));geo.computeVertexNormals();const m=add(g,geo,'#ffffff',o.id+'-curtain');m.material=m.material.clone();m.material.vertexColors=true;m.material.side=THREE.DoubleSide;m.castShadow=false;
    for(let i=0;i<cols;i++){const u=(i+rand()*.7)/cols;let t=rand()*.08;while(t<.99){const end=Math.min(1,t+.025+rand()*.09),a=p(u,t),b=p(u,end);a[2]+=.03;b[2]+=.03;streaks.push(...a,...b);t=end+.005+rand()*.025;}}
    line(g,streaks,o.foamColor||C.foam,o.id+'-streams',.7);
    const foam=[],[z,y]=path.at(-1);for(let i=0;i<cols/2;i++)foam.push({p:[(rand()-.5)*w*(1+base),y+.025,z+rand()*.75],s:[.16+rand()*.3,.025,.13+rand()*.35]});instances(g,new THREE.SphereGeometry(1,8,4),foam,o.foamColor||C.foam,o.id+'-foam');return g;
  }
  function path(o){
    if(o.terrain){const points=drapePoints(o,o.points||[[-5,0,0],[5,0,0]]);return path({...o,terrain:undefined,points});}
    const g=root(o),points=o.points||[[-5,0,0],[5,0,0]],w=o.width??3.2,th=o.thickness??.1,joints=[],edges=[],rails=[],posts=[];
    for(let i=1;i<points.length;i++){
      const a=new THREE.Vector3(...points[i-1]),b=new THREE.Vector3(...points[i]),delta=b.clone().sub(a),length=Math.hypot(delta.x,delta.z),yaw=Math.atan2(delta.x,delta.z),mid=a.clone().add(b).multiplyScalar(.5);
      const sideVector=new THREE.Vector3(Math.cos(yaw)*w/2,0,-Math.sin(yaw)*w/2);
      const m=add(g,slab([a.clone().sub(sideVector).toArray(),b.clone().sub(sideVector).toArray(),b.clone().add(sideVector).toArray(),a.clone().add(sideVector).toArray()],th),o.color||C.path);paved(m);
      const steps=Math.max(1,Math.ceil(length/(o.jointSpacing??1.1)));
      for(let j=0;j<=steps;j++){const p=a.clone().lerp(b,j/steps);joints.push({p:[p.x,p.y+th+.006,p.z],s:[w-.16,.008,.018],r:[0,yaw,0]});}
      if(o.edges!==false)for(const side of [-1,1]){const p=mid.clone().add(new THREE.Vector3(Math.cos(yaw)*side*w/2,th+.015,-Math.sin(yaw)*side*w/2));edges.push({p:p.toArray(),s:[.09,.08,delta.length()],r:[-Math.atan2(delta.y,length),yaw,0],order:'YXZ'});}
      if(o.railHeight)for(const side of o.railSides||[-1,1]){
        const offset=new THREE.Vector3(Math.cos(yaw)*side*(w/2-.08),th,-Math.sin(yaw)*side*(w/2-.08));
        const count=Math.max(1,Math.ceil(length/(o.postSpacing??1.8)));
        for(let j=0;j<=count;j++){const p=a.clone().lerp(b,j/count).add(offset);posts.push({p:[p.x,p.y+o.railHeight/2,p.z],s:[.075,o.railHeight,.075]});}
        for(const level of [.48,1])rodItems(rails,a.clone().add(offset).add(new THREE.Vector3(0,o.railHeight*level,0)).toArray(),b.clone().add(offset).add(new THREE.Vector3(0,o.railHeight*level,0)).toArray(),.035);
      }
    }
    points.forEach((p,i)=>{
      const a=points[Math.max(0,i-1)],b=points[Math.min(points.length-1,i+1)],gradient=(u,v)=>{const dx=v[0]-u[0],dz=v[2]-u[2],s=(v[1]-u[1])/(dx*dx+dz*dz||1);return [dx*s,dz*s];};
      const ga=i?gradient(a,p):gradient(p,b),gb=i<points.length-1?gradient(p,b):ga;
      let geo;
      if(Math.hypot(ga[0]-gb[0],ga[1]-gb[1])<1e-9){geo=new THREE.CylinderGeometry(w/2,w/2,th,24);const v=geo.attributes.position;for(let j=0;j<v.count;j++)v.setY(j,v.getY(j)+v.getX(j)*ga[0]+v.getZ(j)*ga[1]);}
      else {
        // The lower envelope never lifts a cap above either incident paved slab.
        // Split the fan on the plane intersection so each triangle stays planar.
        const split=Math.atan2(-(ga[0]-gb[0]),ga[1]-gb[1]),tau=Math.PI*2,angles=[...Array.from({length:24},(_,j)=>j*tau/24),((split%tau)+tau)%tau,(((split+Math.PI)%tau)+tau)%tau].sort((a,b)=>a-b),v=[];
        const at=t=>{const x=Math.cos(t)*w/2,z=Math.sin(t)*w/2;return [x,Math.min(x*ga[0]+z*ga[1],x*gb[0]+z*gb[1])-th/2,z];},up=a=>[a[0],a[1]+th,a[2]];
        for(let j=0;j<angles.length;j++){const a=at(angles[j]),b=at(angles[(j+1)%angles.length]);v.push(0,th/2,0,...up(b),...up(a),0,-th/2,0,...a,...b,...a,...up(a),...up(b),...a,...up(b),...b);}
        geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(v,3));
      }
      geo.computeVertexNormals();const m=add(g,geo,o.color||C.path);m.position.set(p[0],p[1]+th/2,p[2]);paved(m);
    });
    instances(g,new THREE.BoxGeometry(1,1,1),joints,o.jointColor||'#b7b5a6',o.id+'-joints');instances(g,new THREE.BoxGeometry(1,1,1),edges,o.edgeColor||C.edge,o.id+'-edges');instances(g,new THREE.BoxGeometry(1,1,1),posts,o.railColor||C.rail,o.id+'-posts');instances(g,new THREE.CylinderGeometry(1,1,1,7),rails,o.railColor||C.rail,o.id+'-rails');return g;
  }
  register('nature_path',o=>!o.pattern||o.pattern==='paved'?path(o):spacedPath(o));
  function platform(o,bridge){
    const g=root(o),[w,d]=o.size||(bridge?[2.8,14]:[7,5]),height=o.height??(bridge?1.3:.3),foot=o.footY??0,th=o.thickness??.14,sag=bridge?(o.sag??.45):0,plank=o.plankWidth??.28,count=Math.ceil(d/plank),parts=[],posts=[],ropes=[],rail=o.railHeight??1.05;
    const y=z=>height-sag*(1-(2*z/d)**2);
    // Continuous backing sits below the boards: no coplanar faces or route gaps.
    const supportDrop=th*.12,v=[];for(let i=0;i<count;i++){const z=-d/2+i*d/count,z2=-d/2+(i+1)*d/count;v.push(-w/2,y(z)-supportDrop,z,-w/2,y(z2)-supportDrop,z2,w/2,y(z2)-supportDrop,z2,-w/2,y(z)-supportDrop,z,w/2,y(z2)-supportDrop,z2,w/2,y(z)-supportDrop,z);parts.push({p:[0,(y(z)+y(z2))/2-th/2,(z+z2)/2],s:[w,th,Math.hypot(d/count,y(z2)-y(z))-.015],r:[-Math.atan2(y(z2)-y(z),z2-z),0,0]});}
    const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(v,3));geo.computeVertexNormals();const surface=paved(add(g,geo,o.color||C.wood,o.id+'-decking'));surface.material.side=THREE.DoubleSide;
    instances(g,new THREE.BoxGeometry(1,1,1),parts,o.color||C.wood,o.id+'-planks');
    const num=Math.max(1,Math.ceil(d/(o.postSpacing??2.5)));
    for(const side of [-1,1]){
      for(let i=0;i<=num;i++){const z=-d/2+i*d/num,top=y(z);if(o.rails!==false)posts.push({p:[side*w/2,top+rail/2,z],s:[.09,rail,.09]});if(!bridge||i===0||i===num){const h=Math.max(.05,top-th-foot);posts.push({p:[side*(w/2-.15),foot+h/2,z],s:[.17,h,.17]});}}
      if(o.rails!==false)for(const level of [rail*.48,rail])for(let i=0;i<40;i++){const z=-d/2+i*d/40,z2=z+d/40;rodItems(ropes,[side*w/2,y(z)+level,z],[side*w/2,y(z2)+level,z2],o.ropeRadius??.028);}
    }
    instances(g,new THREE.BoxGeometry(1,1,1),posts,o.railColor||C.rail,o.id+'-posts');instances(g,new THREE.CylinderGeometry(1,1,1,6),ropes,o.railColor||C.rail,o.id+'-rails');return g;
  }
  register('nature_bridge',o=>platform(o,true));register('nature_deck',o=>platform(o,false));
  register('nature_tent',o=>{
    if(o.style&&o.style!=='a_frame')return campTent(o);
    const g=root(o),[w,h,d]=o.size||[3,2.1,3.6],base=o.baseHeight??.12;
    block(g,[0,base/2,0],[w+.4,base,d+.4],o.floorColor||C.wood);
    const shape=new THREE.Shape();shape.moveTo(-w/2,base);shape.lineTo(w/2,base);shape.lineTo(0,h+base);shape.closePath();const geo=new THREE.ExtrudeGeometry(shape,{depth:d,bevelEnabled:false});geo.translate(0,0,-d/2);add(g,geo,o.color||C.tent,o.id+'-canvas');
    const door=new THREE.Shape();door.moveTo(-w*.25,base+.01);door.lineTo(w*.25,base+.01);door.lineTo(0,h*.78);door.closePath();const flap=add(g,new THREE.ShapeGeometry(door),o.doorColor||'#626d60',o.id+'-door');flap.position.z=d/2+.012;
    const ropes=[];for(const side of [-1,1])for(const end of [-1,1])rodItems(ropes,[side*w/2,base+.12,end*d/2],[side*(w/2+(o.guySpread??.8)),.025,end*(d/2+.5)],.015);instances(g,new THREE.CylinderGeometry(1,1,1,5),ropes,o.ropeColor||C.rail,o.id+'-guys');return g;
  });
  register('nature_grove',o=>{
    if(o.density!==undefined||o.kind==='kesiya'||o.terrain)return forest(o);
    const g=root(o),[w,d]=o.size||[12,8],rand=random(o.seed??7),trees=o.trees||[[-3,0,7],[2,-1,8],[4,2,6]],trunks=[],crowns=[],shrubs=[],flowers=[],mats=[],palette=o.flowerColors?.length?o.flowerColors:['#b7ad8e','#c3b7b5','#d4d7c5'];
    const excluded=(x,z)=>(o.exclude||[]).some(([cx,cz,sw,sd])=>Math.abs(x-cx)<sw/2&&Math.abs(z-cz)<sd/2);
    const floor=(x,z)=>(o.slope?.[0]??0)*x+(o.slope?.[1]??0)*z;
    if(o.ground!==false){const corners=[[-w/2,-d/2],[-w/2,d/2],[w/2,d/2],[w/2,-d/2]].map(([x,z])=>[x,floor(x,z),z]);add(g,slab(corners,.04),o.groundColor||'#b4bda5',o.id+'-ground');}
    for(const [x,z,h=7,base=0] of trees){const y=floor(x,z)+base,pine=o.kind==='pine'||o.kind!=='broadleaf'&&rand()>.5;trunks.push({p:[x,y+h*.45,z],s:[.105,h*.9,.105]});const radius=(o.crownScale??1)*(pine?h*.17:h*.26);for(let j=0;j<(pine?7:5);j++){const a=j*2.4,r=radius*(pine?.48:.45),cy=y+h*(pine?.67+j*.042:.82+(j%3)*.065);crowns.push({p:[x+Math.cos(a)*r,cy,z+Math.sin(a)*r],s:[radius*(.72+rand()*.2),radius*(pine?.17:.45),radius*(.7+rand()*.25)]});}mats.push({p:[x,y+.12,z],s:[radius*.62,.12,radius*.6]});}
    for(let i=0;i<(o.shrubs??70);i++){const x=(rand()-.5)*w,z=(rand()-.5)*d;if(excluded(x,z))continue;const s=(o.shrubScale??.55)*(.6+rand()*.8),y=floor(x,z);shrubs.push({p:[x,y+s*.65,z],s:[s,s*.65,s*.8]});if(rand()<(o.flowers??.18))for(let j=0;j<4;j++)flowers.push({p:[x+(rand()-.5)*s,y+s*1.21,z+(rand()-.5)*s],s:[.07,.05,.07],c:palette[flowers.length%palette.length]});}
    instances(g,new THREE.CylinderGeometry(1,1,1,7),trunks,o.trunkColor||C.trunk,o.id+'-trunks');instances(g,new THREE.SphereGeometry(1,9,6),crowns,o.leafColor||C.leaf,o.id+'-crowns');instances(g,new THREE.SphereGeometry(1,8,5),[...shrubs,...mats],o.shrubColor||C.moss,o.id+'-understory');instances(g,new THREE.IcosahedronGeometry(1,0),flowers,'#ffffff',o.id+'-flowers');return g;
  });

  // Camping additions are opt-in. The original waterfall and default tent/path
  // builders above retain their geometry, material ownership and random sequence.
  function surface(g,vertices,color,name){
    const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));geo.computeVertexNormals();
    const m=add(g,geo,color,name);m.material=m.material.clone();m.material.side=THREE.DoubleSide;return m;
  }
  function outline(o,w,d){return o.outline||[[-w/2,-d/2],[w/2,-d/2],[w/2,d/2],[-w/2,d/2]];}
  function inside(x,z,polygon){let yes=false;for(let i=0,j=polygon.length-1;i<polygon.length;j=i++){const a=polygon[i],b=polygon[j];if((a[1]>z)!==(b[1]>z)&&x<(b[0]-a[0])*(z-a[1])/(b[1]-a[1])+a[0])yes=!yes;}return yes;}
  function patch(g,polygon,floor,color,name){
    const tris=THREE.ShapeUtils.triangulateShape(polygon.map(([x,z])=>new THREE.Vector2(x,z)),[]),v=[];
    for(const t of tris)for(const i of [t[0],t[2],t[1]]){const [x,z]=polygon[i];v.push(x,floor(x,z),z);}
    return surface(g,v,color,name);
  }
  function rods(g,items,color,name,radiusSegments=7){return instances(g,new THREE.CylinderGeometry(1,1,1,radiusSegments),items,color,name);}
  function spacedPath(o){
    if(o.terrain)return spacedPath({...o,terrain:undefined,points:drapePoints(o,o.points||[[-5,0,0],[5,0,0]])});
    if(!['stepping','boardwalk'].includes(o.pattern))throw new Error('Unknown nature_path pattern: '+o.pattern);
    const start=walkableGeometries.length,g=path({...o,edges:false,jointSpacing:1e6}),geos=[],remove=[];
    // Reuse the exact sloping slabs and grade-change caps from the paved path.
    // Its invisible support is for the guided route only, not a visible ribbon.
    for(const m of g.children)if(m.userData.paving){m.updateMatrix();const geo=(m.geometry.index?m.geometry.toNonIndexed():m.geometry.clone()).applyMatrix4(m.matrix);for(const key of Object.keys(geo.attributes))if(!['position','normal'].includes(key))geo.deleteAttribute(key);geos.push(geo);remove.push(m);}
    walkableGeometries.splice(start);
    const support=add(g,mergeGeometries(geos),o.color||C.path,o.id+'-route-support');support.material=support.material.clone();support.material.visible=false;support.castShadow=false;support.receiveShadow=false;paved(support);
    geos.forEach(geo=>geo.dispose());remove.forEach(m=>{g.remove(m);m.geometry.dispose();});
    const joint=g.getObjectByName(o.id+'-joints');if(joint){g.remove(joint);joint.geometry.dispose();}
    const points=o.points||[[-5,0,0],[5,0,0]],parts=[],w=o.width??3.2,th=o.thickness??.1,rand=random(o.seed??17),stepping=o.pattern==='stepping';
    for(let i=1;i<points.length;i++){
      const a=new THREE.Vector3(...points[i-1]),b=new THREE.Vector3(...points[i]),delta=b.clone().sub(a),length=Math.hypot(delta.x,delta.z),yaw=Math.atan2(delta.x,delta.z),pitch=-Math.atan2(delta.y,length);
      if(length<1e-6)continue;
      const pitchLength=stepping?(o.stepLength??.65)+(o.stepGap??.22):(o.plankWidth??.24),count=Math.max(1,Math.ceil(length/pitchLength));
      for(let j=0;j<count;j++){
        const p=a.clone().lerp(b,(j+.5)/count),shift=stepping?(rand()-.5)*(o.stagger??.12):0;
        p.x+=Math.cos(yaw)*shift;p.z-=Math.sin(yaw)*shift;p.y+=th/2;
        parts.push({p:p.toArray(),s:stepping?[(o.stoneWidth??Math.min(.8,w*.88))/2,th,Math.max(.08,length/count-(o.stepGap??.22))/2]:[w,th,Math.max(.04,length/count-.013)],r:[pitch,yaw+(stepping?(rand()-.5)*.12:0),0],order:'YXZ'});
      }
    }
    instances(g,stepping?new THREE.CylinderGeometry(1,1,1,7):new THREE.BoxGeometry(1,1,1),parts,o.color||(stepping?C.path:C.wood),o.id+'-'+o.pattern);return g;
  }

  function campTent(o){
    const style=o.style;if(!['safari','bell','glass_a_frame','dome'].includes(style))throw new Error('Unknown nature_tent style: '+style);
    const g=root(o),[w,h,d]=o.size||[4.5,3,4.8],base=o.baseHeight??.12,wall=Math.min(h*.85,o.wallHeight??(style==='safari'?h*.6:.5)),color=o.color||C.tent,roofColor=o.roofColor||'#697163',frameColor=o.frameColor||C.wood,ropes=[],frame=[],seams=[],v=[];
    const tri=(a,b,c)=>v.push(...a,...b,...c),quad=(a,b,c,d)=>{tri(a,b,c);tri(a,c,d);},seam=(a,b)=>seams.push(...a,...b);
    block(g,[0,base/2,0],[w+.32,base,d+.32],o.floorColor||C.wood,o.id+'-floor');
    if(style==='safari'){
      const over=o.roofOverhang??.35,porch=o.porchDepth??.55,z=d/2;
      quad([-w/2,base,-z],[w/2,base,-z],[w/2,base+wall,-z],[-w/2,base+wall,-z]);
      for(const side of [-1,1]){
        const x=side*w/2;quad([x,base,-z],[x,base,z],[x,base+wall,z],[x,base+wall,-z]);
        // Narrow front curtains flank an actual open entrance.
        const inner=side*w*(o.openWidth??.46)/2;
        quad([x,base,z],[inner,base,z],[inner,base+wall,z],[x,base+wall,z]);
        tri([x,base+wall,z],[inner,base+wall,z],[0,base+h,z]);
        for(const zz of [-z,z+porch])rodItems(frame,[x,base,zz],[x,base+wall,zz],.035);
        rodItems(frame,[x,base+wall,z+porch],[0,base+h,z+porch],.04);
        for(const zz of [-z,z])rodItems(ropes,[x,base+wall,zz],[side*(w/2+(o.guySpread??.65)),.02,zz+Math.sign(zz)*.4],.012);
      }
      surface(g,v,color,o.id+'-'+style+'-shell');
      const roof=[];for(const s of [-1,1])roof.push(0,base+h+.045,-z-over,s*(w/2+over),base+wall-.12,-z-over,s*(w/2+over),base+wall-.12,z+porch+over,0,base+h+.045,-z-over,s*(w/2+over),base+wall-.12,z+porch+over,0,base+h+.045,z+porch+over);
      surface(g,roof,roofColor,o.id+'-roof');
      const windows=[];for(const s of [-1,1]){
        const x=s*(w/2+.009),cy=base+wall*.57,ww=d*.34,wh=wall*.38;
        windows.push({p:[x,cy,-d*.06],s:[.018,wh,ww]});
        for(const y of [cy-wh/2,cy+wh/2])seam([x,y,-d*.06-ww/2],[x,y,-d*.06+ww/2]);
        for(const z of [-d*.06-ww/2,-d*.06+ww/2])seam([x,cy-wh/2,z],[x,cy+wh/2,z]);
        for(let j=1;j<5;j++)seam([s*(w/2+over)*j/5,base+h+.055+(wall-.12-h)*j/5,-d/2-over],[s*(w/2+over)*j/5,base+h+.055+(wall-.12-h)*j/5,d/2+porch+over]);
        seam([s*w/2,base+.12,-d/2],[s*w/2,base+.12,d/2]);
      }
      instances(g,new THREE.BoxGeometry(1,1,1),windows,o.doorColor||'#7c8271',o.id+'-windows');
    }else if(style==='bell'){
      const n=o.segments??40,rx=w/2,rz=d/2,doorHalf=.24;
      for(let i=0;i<n;i++){
        const a=i*2*Math.PI/n,b=(i+1)*2*Math.PI/n,pa=[Math.sin(a)*rx,base+wall,Math.cos(a)*rz],pb=[Math.sin(b)*rx,base+wall,Math.cos(b)*rz];
        tri([0,base+h,0],pa,pb);
        if(Math.cos((a+b)/2)<Math.cos(doorHalf))quad([pa[0],base,pa[2]],[pb[0],base,pb[2]],pb,pa);
        if(i%4===0){seam([0,base+h+.009,0],[pa[0]*1.003,pa[1]+.008,pa[2]*1.003]);rodItems(ropes,pa,[Math.sin(a)*(rx+(o.guySpread??.65)),.02,Math.cos(a)*(rz+(o.guySpread??.65))],.012);}
      }
      surface(g,v,color,o.id+'-'+style+'-shell');
      const pole=block(g,[0,base+h/2,0],[.055,h,.055],frameColor,o.id+'-center-pole');pole.castShadow=false;
      // The entrance ridge is a separate canvas porch, not another full A-frame.
      const dz=rz+.35,dh=Math.min(h*.63,1.85),dw=w*.29;
      surface(g,[-dw/2,base,rz,0,base+dh,dz,-dw/2,base,rz+.6,0,base+dh,dz,dw/2,base,rz,dw/2,base,rz+.6],color,o.id+'-entrance');
      const door=new THREE.Shape();door.moveTo(-dw*.42,base);door.lineTo(dw*.42,base);door.lineTo(0,base+dh*.95);door.closePath();const m=add(g,new THREE.ShapeGeometry(door),o.doorColor||'#777d6a',o.id+'-door');m.position.z=rz+.025;
      rodItems(frame,[0,base,dz],[0,base+dh,dz],.025);
    }else if(style==='glass_a_frame'){
      for(const side of [-1,1])quad([side*w/2,base,-d/2],[side*w/2,base,d/2],[0,base+h,d/2],[0,base+h,-d/2]);
      tri([-w/2,base,-d/2],[0,base+h,-d/2],[w/2,base,-d/2]);surface(g,v,roofColor,o.id+'-'+style+'-shell');
      surface(g,[-w/2,base+.02,d/2+.012,w/2,base+.02,d/2+.012,0,base+h-.025,d/2+.012],o.glassColor||'#a6b4ad',o.id+'-glazing');
      for(const z of [-d/2,d/2+.04])for(const side of [-1,1])rodItems(frame,[side*w/2,base,z],[0,base+h,z],o.frameRadius??.045);
      const doorW=o.doorWidth??Math.min(1.05,w*.3),doorH=Math.min(2.05,h*.68),z=d/2+.055;
      for(const x of [-doorW/2,doorW/2]){rodItems(frame,[x,base,z],[x,base+doorH,z],.028);rodItems(frame,[x,base+doorH,z],[x,base+h*(1-2*Math.abs(x)/w),z],.022);}
      rodItems(frame,[-doorW/2,base+doorH,z],[doorW/2,base+doorH,z],.025);rodItems(frame,[-w/2,base,z],[w/2,base,z],.035);
      for(const s of [-1,1])for(let j=1;j<5;j++)seam([s*w*j/10,base+h*(1-j/5)+.015,-d/2],[s*w*j/10,base+h*(1-j/5)+.015,d/2]);
      seam([-w/2,base,d/2+.065],[0,base+h,d/2+.065]);seam([w/2,base,d/2+.065],[0,base+h,d/2+.065]);
    }else{
      const geo=new THREE.SphereGeometry(1,32,16,0,Math.PI*2,0,Math.PI/2);geo.scale(w/2,h,d/2);geo.translate(0,base,0);add(g,geo,color,o.id+'-'+style+'-shell');
      const ribs=[];for(const a of [0,Math.PI/2])for(let j=0;j<32;j++){
        const at=t=>[Math.cos(t)*Math.cos(a)*(w/2+.012),base+Math.sin(t)*(h+.012),Math.cos(t)*Math.sin(a)*(d/2+.012)];rodItems(ribs,at(j*Math.PI/32),at((j+1)*Math.PI/32),.018);
      }
      rods(g,ribs,frameColor,o.id+'-ribs');
      const door=[],doorPoint=(u,t)=>{const x=u*w*.2,y=base+.03+t*h*.63*Math.sqrt(Math.max(0,1-u*u));return [x,y,d/2*Math.sqrt(Math.max(0,1-(x/(w/2))**2-((y-base)/h)**2))+.016];};
      for(let i=0;i<24;i++)for(let j=0;j<12;j++){const a=doorPoint(-1+i/12,j/12),b=doorPoint(-1+(i+1)/12,j/12),c=doorPoint(-1+(i+1)/12,(j+1)/12),e=doorPoint(-1+i/12,(j+1)/12);door.push(...a,...b,...c,...a,...c,...e);}
      surface(g,door,o.doorColor||'#757d6b',o.id+'-door');
      for(let i=0;i<24;i++)seam(doorPoint(-1+i/12,1),doorPoint(-1+(i+1)/12,1));
      for(let j=0;j<24;j++){const a=j*Math.PI/12,b=(j+1)*Math.PI/12;seam([Math.cos(a)*w*.49,base+.14,Math.sin(a)*d*.49],[Math.cos(b)*w*.49,base+.14,Math.sin(b)*d*.49]);}
    }
    rods(g,frame,frameColor,o.id+'-frame');rods(g,ropes,o.ropeColor||C.rail,o.id+'-guys',5);line(g,seams,o.seamColor||'#8d927e',o.id+'-seams',.5);return g;
  }

  register('nature_canopy',o=>{
    const g=root(o),[w,h,d]=o.size||[8,4.2,6],peaks=o.peaks||[[0,0,h]],edge=o.edgeHeight??2.1,sag=o.edgeSag??.5,n=o.segments??16,v=[],seams=[],poles=[],ropes=[];
    const sorted=[...peaks].sort((a,b)=>a[0]-b[0]);
    for(let k=0;k<sorted.length;k++){
      const [px,pz,py]=sorted[k],left=k?(sorted[k-1][0]+px)/2:-w/2,right=k<sorted.length-1?(sorted[k+1][0]+px)/2:w/2;
      const corners=[[left,-d/2],[right,-d/2],[right,d/2],[left,d/2]];
      for(let side=0;side<4;side++)for(let j=0;j<n;j++){
        const a=corners[side],b=corners[(side+1)%4],at=(t,r)=>{const x=THREE.MathUtils.lerp(a[0],b[0],t),z=THREE.MathUtils.lerp(a[1],b[1],t),ey=edge-sag*Math.sin(t*Math.PI);return [THREE.MathUtils.lerp(px,x,r),THREE.MathUtils.lerp(py,ey,r)-(o.curvature??.42)*Math.sin(Math.PI*r),THREE.MathUtils.lerp(pz,z,r)];};
        for(let row=0;row<8;row++){const p=at(j/n,row/8),q=at((j+1)/n,row/8),r=at((j+1)/n,(row+1)/8),s=at(j/n,(row+1)/8);v.push(...p,...q,...r,...p,...r,...s);}
        seams.push(...at(j/n,1),...at((j+1)/n,1));
      }
      rodItems(poles,[px,0,pz],[px,py+.06,pz],.035);
    }
    for(const x of [-w/2,w/2])for(const z of [-d/2,d/2]){rodItems(poles,[x,0,z],[x,edge+.04,z],.025);rodItems(ropes,[x,edge,z],[x+Math.sign(x)*(o.guySpread??.8),.02,z+Math.sign(z)*(o.guySpread??.8)],.01);}
    surface(g,v,o.color||'#dfdfd0',o.id+'-membrane');rods(g,poles,o.poleColor||C.wood,o.id+'-poles');rods(g,ropes,o.ropeColor||C.rail,o.id+'-guys',5);line(g,seams,o.seamColor||'#b3b7a6',o.id+'-edges',.6);return g;
  });

  function offsetPoints(points,distance){return points.map((p,i)=>{const a=points[Math.max(0,i-1)],b=points[Math.min(points.length-1,i+1)],dx=b[0]-a[0],dz=b[2]-a[2],len=Math.hypot(dx,dz)||1;return [p[0]+dz/len*distance,p[1],p[2]-dx/len*distance];});}
  function ribbon(g,points,width,color,name,lift=0){
    const left=offsetPoints(points,-width/2),right=offsetPoints(points,width/2),v=[];
    for(let i=1;i<points.length;i++){const p=[left[i-1],left[i],right[i],right[i-1]].map(p=>[p[0],p[1]+lift,p[2]]);v.push(...p[0],...p[1],...p[2],...p[0],...p[2],...p[3]);}
    return surface(g,v,color,name);
  }
  register('nature_stream',o=>{
    const g=root(o),points=o.points||[[0,0,-8],[0,0,0],[1,0,8]],w=o.width??3.5,bank=o.bankWidth??.85,rand=random(o.seed??11),stones=[],flows=[],walkPoints=o.boardwalk?offsetPoints(points,(o.boardwalk.side??1)*(w/2+(o.boardwalk.gap??.35)+(o.boardwalk.width??1.8)/2)):null;
    ribbon(g,points,w+2*bank,o.bankColor||'#b4b39d',o.id+'-bed',.015);ribbon(g,points,w,o.color||C.water,o.id+'-water',o.level??.04);
    const lengths=points.slice(1).map((p,i)=>Math.hypot(p[0]-points[i][0],p[2]-points[i][2])),total=lengths.reduce((a,b)=>a+b,0);
    const sample=t=>{let distance=t*total;for(let i=0;i<lengths.length;i++){if(distance<=lengths[i]||i===lengths.length-1){const a=new THREE.Vector3(...points[i]),b=new THREE.Vector3(...points[i+1]),delta=b.clone().sub(a),p=a.lerp(b,distance/(lengths[i]||1)),side=new THREE.Vector3(delta.z,0,-delta.x).normalize();return {p,side,tangent:delta.normalize()};}distance-=lengths[i];}};
    const clearsWalk=(p,radius)=>!(o.excludePolygons||[]).some(poly=>inside(p.x,p.z,poly)||poly.some((a,i)=>{const b=poly[(i+1)%poly.length],dx=b[0]-a[0],dz=b[1]-a[1],t=THREE.MathUtils.clamp(((p.x-a[0])*dx+(p.z-a[1])*dz)/(dx*dx+dz*dz||1),0,1);return Math.hypot(p.x-a[0]-t*dx,p.z-a[1]-t*dz)<radius;}))&&(!walkPoints||walkPoints.slice(1).every((b,i)=>{const a=walkPoints[i],dx=b[0]-a[0],dz=b[2]-a[2],t=THREE.MathUtils.clamp(((p.x-a[0])*dx+(p.z-a[2])*dz)/(dx*dx+dz*dz||1),0,1);return Math.hypot(p.x-a[0]-t*dx,p.z-a[2]-t*dz)>radius+(o.boardwalk.width??1.8)/2+.1;}));
    const stoneCount=o.boulders??42;for(let tries=0;stones.length<stoneCount&&tries<stoneCount*50;tries++){const {p,side}=sample(rand()),bankStone=rand()<.6,lateral=bankStone?(rand()<.5?-1:1)*(w/2+rand()*bank*.7):(rand()-.5)*w*.8,s=(o.boulderScale??.65)*(.55+rand()*.95),sy=s*(.45+rand()*.3),sz=s*(.65+rand()*.4),yaw=rand()*6;p.addScaledVector(side,lateral);if(!clearsWalk(p,Math.max(s,sz)))continue;stones.push({p:[p.x,p.y+sy*.850650808-.035,p.z],s:[s,sy,sz],r:[0,yaw,0]});}
    for(let i=0;i<(o.flowLines??65);i++){const t=rand(),{p,side,tangent}=sample(t),q=p.clone().addScaledVector(tangent,.15+rand()*.6);p.addScaledVector(side,(rand()-.5)*w*.7);q.addScaledVector(side,(rand()-.5)*.08);q.x+=p.x-sample(t).p.x;q.z+=p.z-sample(t).p.z;flows.push(p.x,p.y+(o.level??.04)+.013,p.z,q.x,q.y+(o.level??.04)+.013,q.z);}
    instances(g,new THREE.IcosahedronGeometry(1,1),stones,o.boulderColor||'#a19f8e',o.id+'-boulders');line(g,flows,o.foamColor||C.foam,o.id+'-flow',.5);
    if(o.rapids)streamRapids(g,o,points,sample);
    if(o.boardwalk){const b=o.boardwalk,walk=spacedPath({id:o.id+'-boardwalk',position:o.position,baseY:o.baseY,rotation:o.rotation,pattern:'boardwalk',points:walkPoints.map(p=>[p[0],p[1]+(b.height??.18),p[2]]),width:b.width??1.8,thickness:b.thickness??.12,plankWidth:b.plankWidth??.24,color:b.color||C.wood,railHeight:b.railHeight,railSides:b.railSides||[b.side===-1?1:-1],railColor:b.railColor||C.rail});walk.position.set(0,0,0);walk.rotation.set(0,0,0);g.add(walk);}
    return g;
  });

  // Landscape additions are opt-in; old builders keep their random sequence.
  function terrainFor(id){const t=landscapes.get(id);if(!t)throw new Error('Build nature_hills before terrain consumer: '+id);return t;}
  function terrainFloor(g,id,x,z){
    const t=terrainFor(id);g.updateWorldMatrix(true,false);t.updateWorldMatrix(true,false);
    const p=t.worldToLocal(g.localToWorld(new THREE.Vector3(x,0,z)));
    return t.localToWorld(new THREE.Vector3(p.x,t.userData.heightAt(p.x,p.z),p.z)).y-g.position.y;
  }
  function drapePoints(o,points){
    const g=new THREE.Group();g.position.set(...(o.position||[0,0,0]));g.position.y+=o.baseY??0;g.rotation.y=(o.rotation||0)*Math.PI/180;
    const out=[];for(let i=1;i<points.length;i++){
      const a=new THREE.Vector3(...points[i-1]),b=new THREE.Vector3(...points[i]),n=Math.max(1,Math.ceil(a.distanceTo(b)/(o.sampleSpacing??.75)));
      for(let j=i===1?0:1;j<=n;j++){const p=a.clone().lerp(b,j/n);out.push([p.x,terrainFloor(g,o.terrain,p.x,p.z)+p.y+(o.heightOffset??.04),p.z]);}
    }return out;
  }
  function localPlatform(g,o){
    g.updateWorldMatrix(true,false);const p=g.localToWorld(new THREE.Vector3(...(o.position||[0,0,0])));
    const child=platform({...o,position:p.toArray(),rotation:(o.rotation??0)+g.rotation.y*180/Math.PI},false);g.attach(child);return child;
  }
  function polygonOffset(poly,distance){
    const area=poly.reduce((s,p,i)=>{const q=poly[(i+1)%poly.length];return s+p[0]*q[1]-q[0]*p[1];},0),sign=area>0?1:-1;
    return poly.map((p,i)=>{const a=poly[(i+poly.length-1)%poly.length],b=poly[(i+1)%poly.length],normal=(u,v)=>{const dx=v[0]-u[0],dz=v[1]-u[1],len=Math.hypot(dx,dz)||1;return [sign*dz/len,-sign*dx/len];},n=normal(a,p),m=normal(p,b),den=Math.max(.5,1+n[0]*m[0]+n[1]*m[1]);return [p[0]+distance*(n[0]+m[0])/den,p[1]+distance*(n[1]+m[1])/den];});
  }
  function lakeShape(poly,holes=[]){
    const shape=new THREE.Shape(poly.map(([x,z])=>new THREE.Vector2(x,-z)));
    for(const p of holes)shape.holes.push(new THREE.Path(p.map(([x,z])=>new THREE.Vector2(x,-z))));
    const geo=new THREE.ShapeGeometry(shape);geo.rotateX(-Math.PI/2);return geo;
  }
  register('nature_lake',o=>{
    const g=root(o),[w,d]=o.size||[70,45],raw=o.outline||Array.from({length:16},(_,i)=>[Math.cos(i*Math.PI/8)*w/2,Math.sin(i*Math.PI/8)*d/2]);
    if(!(w>0&&d>0)||raw.length<3)throw new Error('nature_lake needs positive size and a shoreline polygon');
    const poly=o.smooth===false?raw:new THREE.CatmullRomCurve3(raw.map(([x,z])=>new THREE.Vector3(x,0,z)),true,'centripetal').getSpacedPoints(o.segments??128).slice(0,-1).map(p=>[p.x,p.z]);
    const shore=o.shoreWidth??1.5,level=o.level??.06,islands=(o.islands||[]).map(a=>({...a,outline:(a.outline||Array.from({length:24},(_,i)=>[Math.cos(i*Math.PI/12)*(a.size?.[0]??6)/2,Math.sin(i*Math.PI/12)*(a.size?.[1]??4)/2])).map(([x,z])=>[x+(a.position?.[0]??0),z+(a.position?.[1]??0)])}));
    const water=add(g,lakeShape(poly,islands.map(a=>a.outline)),o.color||'#8faaa2',o.id+'-water');water.position.y=level;water.castShadow=false;
    if(shore>0){const bank=add(g,lakeShape(polygonOffset(poly,shore),[poly]),o.shoreColor||'#b7b6a0',o.id+'-shore');bank.position.y=level+.012;const shallow=add(g,lakeShape(poly,[polygonOffset(poly,-Math.min(shore,w*.04,d*.04))]),o.shallowColor||'#b1bfb0',o.id+'-shallows');shallow.position.y=level+.008;shallow.castShadow=false;}
    for(let i=0;i<islands.length;i++){const a=islands[i],y=level+(a.height??.35);patch(g,a.outline,()=>y,a.color||'#a5b298',o.id+'-island-'+i);const sides=[];a.outline.forEach(([x,z],j)=>{const [xx,zz]=a.outline[(j+1)%a.outline.length];sides.push(x,level,z,xx,level,zz,xx,y,zz,x,level,z,xx,y,zz,x,y,z);});surface(g,sides,a.shoreColor||o.shoreColor||'#b7b6a0',o.id+'-island-bank-'+i);}
    const rand=random(o.seed??31),fringe=[],reeds=[],ripples=[],fringeRing=polygonOffset(poly,shore*.65);
    for(let i=0;i<(o.fringe??180);i++){const index=Math.floor(rand()*poly.length),a=fringeRing[index],b=fringeRing[(index+1)%poly.length],t=rand(),x=THREE.MathUtils.lerp(a[0],b[0],t),z=THREE.MathUtils.lerp(a[1],b[1],t),h=(o.fringeHeight??.55)*(.65+rand()*.6);fringe.push({p:[x,level+h/2,z],s:[h*.24,h,h*.24],r:[0,rand()*6,0]});if(rand()<(o.reeds??.3))rodItems(reeds,[x,level,z],[x+.08,level+h*1.5,z],.018);}
    for(let i=0;i<(o.ripples??45);i++){const x=(rand()-.5)*w,z=(rand()-.5)*d,len=1+rand()*w*.055;if(inside(x-len/2,z,poly)&&inside(x+len/2,z,poly)&&!islands.some(a=>inside(x,z,a.outline)))ripples.push(x-len/2,level+.018,z,x+len/2,level+.018,z+.035);}
    instances(g,new THREE.ConeGeometry(1,1,5),fringe,o.fringeColor||'#919f7e',o.id+'-fringe');rods(g,reeds,o.reedColor||'#9e9b78',o.id+'-reeds',5);line(g,ripples,o.rippleColor||C.foam,o.id+'-ripples',.3);
    if(o.jetty)localPlatform(g,{id:o.id+'-jetty',size:[2.4,8],height:level+.35,footY:level-.2,...o.jetty});return g;
  });
  register('nature_hills',o=>{
    const g=root(o),[w,d]=o.size||[70,45],nx=o.segments?.[0]??72,nz=o.segments?.[1]??52,bottom=o.bottom??0,datum=o.height??0,terrace=o.terraceHeight??0;
    if(!(w>0&&d>0&&Number.isInteger(nx)&&nx>=2&&Number.isInteger(nz)&&nz>=2))throw new Error('nature_hills needs positive size and at least two segments per axis');
    const masses=o.masses??[{center:[-w*.22,-d*.14],size:[w*.65,12,d*.9]},{center:[w*.22,0],size:[w*.75,9,d]}],profile=o.profile?[...o.profile].sort((a,b)=>a[0]-b[0]):null;
    const analytical=(x,z)=>{
      const profileZ=z+(o.profileBend??0)*Math.cos(x/w*Math.PI)**2;
      let y=datum;
      if(profile){y+=profileZ<=profile[0][0]?profile[0][1]:profile.at(-1)[1];for(let i=1;i<profile.length;i++)if(profileZ>=profile[i-1][0]&&profileZ<profile[i][0]){let t=(profileZ-profile[i-1][0])/(profile[i][0]-profile[i-1][0]);if(o.profileSmooth!==false)t=t*t*(3-2*t);y=datum+THREE.MathUtils.lerp(profile[i-1][1],profile[i][1],t);break;}}
      for(const m of [...masses,...(o.peak?[{power:.65,...o.peak}]:[])]){const [mw,mh,md]=m.size,[cx,cz]=m.center||[0,0],r=Math.hypot((x-cx)*2/mw,(z-cz)*2/md);if(r<1)y+=mh*Math.pow((1+Math.cos(Math.PI*r))/2,m.power??1.35);}
      if(terrace>0){const n=y/terrace,base=Math.floor(n),f=n-base;y=(base+THREE.MathUtils.smoothstep(f,.68,1))*terrace;}
      const fade=o.edgeFalloff||[0,0];if(fade[0]>0)y=bottom+(y-bottom)*THREE.MathUtils.smoothstep(w/2-Math.abs(x),0,fade[0]);if(fade[1]>0)y=bottom+(y-bottom)*THREE.MathUtils.smoothstep(d/2-Math.abs(z),0,fade[1]);return y;
    };
    const heights=[],v=[],idx=[],colors=[],low=new THREE.Color(o.color||'#a7b397'),high=new THREE.Color(o.highColor||'#91a185'),heightRange=Math.max(1,...masses.map(m=>m.size[1]),o.peak?.size[1]??0);
    for(let j=0;j<=nz;j++)for(let i=0;i<=nx;i++){const x=(i/nx-.5)*w,z=(j/nz-.5)*d,y=analytical(x,z);if(!Number.isFinite(y)||y<bottom)throw new Error('nature_hills surface must be finite and above bottom');heights.push(y);v.push(x,y,z);const c=low.clone().lerp(high,THREE.MathUtils.clamp((y-datum)/heightRange,0,1));colors.push(c.r,c.g,c.b);}
    for(let j=0;j<nz;j++)for(let i=0;i<nx;i++){const a=j*(nx+1)+i,b=a+1,c=a+nx+1,e=c+1;idx.push(a,c,e,a,e,b);}
    const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(v,3));geo.setAttribute('color',new THREE.Float32BufferAttribute(colors,3));geo.setIndex(idx);geo.computeVertexNormals();
    const mesh=add(g,geo,'#ffffff',o.id+'-land');mesh.material=mesh.material.clone();mesh.material.vertexColors=true;
    // Match the rendered triangles, including their diagonal, not the analytic curve.
    g.userData.heightAt=(x,z)=>{if(Math.abs(x)>w/2+1e-7||Math.abs(z)>d/2+1e-7)throw new Error('Point outside nature_hills '+o.id+': '+[x,z]);const gx=THREE.MathUtils.clamp((x/w+.5)*nx,0,nx),gz=THREE.MathUtils.clamp((z/d+.5)*nz,0,nz),i=Math.min(nx-1,Math.floor(gx)),j=Math.min(nz-1,Math.floor(gz)),u=gx-i,t=gz-j,a=j*(nx+1)+i,h=heights[a],e=heights[a+nx+2];return t>=u?h*(1-t)+heights[a+nx+1]*(t-u)+e*u:h*(1-u)+e*t+heights[a+1]*(u-t);};
    landscapes.set(o.id,g);
    const perimeter=[];for(let i=0;i<=nx;i++)perimeter.push(i);for(let j=1;j<=nz;j++)perimeter.push(j*(nx+1)+nx);for(let i=nx-1;i>=0;i--)perimeter.push(nz*(nx+1)+i);for(let j=nz-1;j>0;j--)perimeter.push(j*(nx+1));
    const sides=[];perimeter.forEach((a,k)=>{const b=perimeter[(k+1)%perimeter.length],p=v.slice(a*3,a*3+3),q=v.slice(b*3,b*3+3);sides.push(...p,...q,q[0],bottom,q[2],...p,q[0],bottom,q[2],p[0],bottom,p[2]);});surface(g,sides,o.sideColor||'#ada991',o.id+'-earth');patch(g,[[-w/2,-d/2],[w/2,-d/2],[w/2,d/2],[-w/2,d/2]],()=>bottom,o.sideColor||'#ada991',o.id+'-bottom');
    const contours=[],bands=[];const interval=o.contourSpacing??3;
    if(interval>0)for(let j=0;j<nz;j++)for(let i=0;i<nx;i++){
      const a=j*(nx+1)+i;for(const tri of [[a,a+nx+1,a+nx+2],[a,a+nx+2,a+1]]){
        const ys=tri.map(k=>heights[k]),min=Math.min(...ys),max=Math.max(...ys);
        for(let y=Math.ceil(min/interval)*interval;y<max;y+=interval){const hits=[];for(let k=0;k<3;k++){const p=tri[k],q=tri[(k+1)%3];if((heights[p]<=y&&heights[q]>y)||(heights[q]<=y&&heights[p]>y)){const t=(y-heights[p])/(heights[q]-heights[p]);hits.push([THREE.MathUtils.lerp(v[p*3],v[q*3],t),y+.018,THREE.MathUtils.lerp(v[p*3+2],v[q*3+2],t)]);}}if(hits.length===2){contours.push(...hits[0],...hits[1]);if(o.bands)rodItems(bands,hits[0].map((p,k)=>k===1?p+.04:p),hits[1].map((p,k)=>k===1?p+.04:p),o.bandRadius??.16);}}
      }
    }
    line(g,contours,o.contourColor||'#89977f',o.id+'-contours',.22);rods(g,bands,o.bandColor||'#859777',o.id+'-terrace-bands',6);
    if(o.greenhouses)greenhouses(g,o.greenhouses,o.id);return g;
  });
  function greenhouses(g,o,id){
    if(o.blocks){o.blocks.forEach((block,i)=>greenhouses(g,{...o,...block,blocks:undefined},id+'-block-'+i));return;}
    const roofs=[],walls=[],seams=[],rows=o.rows??9,cols=o.columns??10,[sw,sh,sd]=o.roofSize||[3,.7,7],spacing=o.spacing||[sw+.6,sd+1],center=o.position||[0,0],yaw=(o.rotation??0)*Math.PI/180;
    const transform=(x,z)=>[center[0]+Math.cos(yaw)*x+Math.sin(yaw)*z,center[1]-Math.sin(yaw)*x+Math.cos(yaw)*z];
    for(let j=0;j<rows;j++)for(let i=0;i<cols;i++){const [x,z]=transform((i-(cols-1)/2)*spacing[0],(j-(rows-1)/2)*spacing[1]);if(o.outline&&!inside(x,z,o.outline)||(o.excludePolygons||[]).some(p=>inside(x,z,p)))continue;
      const corners=[[-sw/2,-sd/2],[-sw/2,sd/2],[sw/2,-sd/2],[sw/2,sd/2]].map(([dx,dz])=>[x+Math.cos(yaw)*dx+Math.sin(yaw)*dz,z-Math.sin(yaw)*dx+Math.cos(yaw)*dz]);
      let y;try{y=Math.max(...corners.map(([x,z])=>g.userData.heightAt(x,z)));}catch{continue;}
      const wall=o.wallHeight??.45;walls.push({p:[x,y+wall/2,z],s:[sw,wall,sd],r:[0,yaw,0]});roofs.push({p:[x,y+wall,z],s:[sw,sh,sd],r:[0,yaw,0]});
      const pt=(dx,dy,dz)=>[x+Math.cos(yaw)*dx+Math.sin(yaw)*dz,y+wall+dy,z-Math.sin(yaw)*dx+Math.cos(yaw)*dz];seams.push(...pt(0,sh+.012,-sd/2),...pt(0,sh+.012,sd/2));for(const s of [-1,1])for(const end of [-1,1])seams.push(...pt(s*sw/2,.012,end*sd/2),...pt(0,sh+.012,end*sd/2));
    }
    const roofGeo=new THREE.BufferGeometry();roofGeo.setAttribute('position',new THREE.Float32BufferAttribute([-.5,0,-.5,0,1,-.5,0,1,.5,-.5,0,-.5,0,1,.5,-.5,0,.5,0,1,-.5,.5,0,-.5,.5,0,.5,0,1,-.5,.5,0,.5,0,1,.5,-.5,0,-.5,.5,0,-.5,0,1,-.5,-.5,0,.5,0,1,.5,.5,0,.5],3));
    const positions=roofGeo.attributes.position;for(let i=0;i<positions.count;i+=3){const a=new THREE.Vector3().fromBufferAttribute(positions,i+1),b=new THREE.Vector3().fromBufferAttribute(positions,i+2);positions.setXYZ(i+1,b.x,b.y,b.z);positions.setXYZ(i+2,a.x,a.y,a.z);}roofGeo.computeVertexNormals();
    instances(g,new THREE.BoxGeometry(1,1,1),walls,o.wallColor||'#c8cbc0',id+'-greenhouse-walls');instances(g,roofGeo,roofs,o.color||'#deded2',id+'-greenhouse-roofs');line(g,seams,o.frameColor||'#a6ad9e',id+'-greenhouse-seams',.42);
  }
  function forest(o){
    const g=root(o),[w,d]=o.size||[40,30],rand=random(o.seed??7),density=o.density??.12,count=Math.min(6000,Math.ceil(w*d*density)),trunks=[],crowns=[],under=[],pine=o.kind!=='broadleaf',excluded=(x,z)=>(o.exclude||[]).some(([cx,cz,sw,sd])=>Math.abs(x-cx)<sw/2&&Math.abs(z-cz)<sd/2)||(o.excludePolygons||[]).some(p=>inside(x,z,p))||o.outline&&!inside(x,z,o.outline),floor=(x,z)=>o.terrain?terrainFloor(g,o.terrain,x,z):(o.slope?.[0]??0)*x+(o.slope?.[1]??0)*z;
    if(!(w>0&&d>0&&density>=0))throw new Error('nature_grove needs positive size and nonnegative density');
    const generated=[],cols=Math.max(1,Math.ceil(Math.sqrt(count*w/d))),rows=Math.max(1,Math.ceil(count/cols));
    if(!o.trees)for(let j=0;j<rows;j++)for(let i=0;i<cols;i++){if(j*cols+i>=count)continue;const x=((i+.15+rand()*.7)/cols-.5)*w,z=((j+.15+rand()*.7)/rows-.5)*d,edge=Math.min(w/2-Math.abs(x),d/2-Math.abs(z));if(rand()>THREE.MathUtils.smoothstep(edge,0,o.edgeFalloff??2)||excluded(x,z))continue;const range=o.treeHeight||[9,14];generated.push([x,z,THREE.MathUtils.lerp(...range,rand())]);}
    for(const [x,z,h=11,base=0] of o.trees||generated){if(excluded(x,z))continue;const y=floor(x,z)+base,r=h*(pine?.145:.24)*(o.crownScale??1);trunks.push({p:[x,y+h*.48,z],s:[o.trunkRadius??.11,h*.96,o.trunkRadius??.11]});
      for(let j=0;j<(pine?6:7);j++){const a=j*2.399+rand()*.22,rr=r*(pine?.5:.45),s=.78+rand()*.2;crowns.push({p:[x+Math.cos(a)*rr,y+h*(pine?.73+j*.043:.72+j*.034),z+Math.sin(a)*rr],s:[r*s,r*(pine?.18:.4),r*s*.9]});}
    }
    for(let i=0;i<(o.shrubs??Math.ceil(w*d*.3));i++){const x=(rand()-.5)*w,z=(rand()-.5)*d;if(excluded(x,z))continue;const s=(o.shrubScale??.5)*(.65+rand()*.6);under.push({p:[x,floor(x,z)+s*.35,z],s:[s,s*.35,s*.8]});}
    if(o.ground!==false&&!o.terrain)patch(g,outline(o,w,d),(x,z)=>floor(x,z)+.015,o.groundColor||'#a7b397',o.id+'-ground');
    rods(g,trunks,o.trunkColor||C.trunk,o.id+'-trunks');instances(g,new THREE.SphereGeometry(1,8,5),crowns,o.leafColor||'#889d80',o.id+'-crowns');instances(g,new THREE.SphereGeometry(1,7,4),under,o.shrubColor||'#9aaa8c',o.id+'-understory');return g;
  }
  function tieredCascade(o){
    if(!o.tiers.length)throw new Error('nature_cascade tiers must not be empty');const g=root(o);
    for(let i=0;i<o.tiers.length;i++){
      const t=o.tiers[i],w=t.width??o.width??16,z=t.z??i*4,top=t.top??(o.tiers.length-i)*2.4,bottom=t.bottom??top-2.4,run=t.run??1.1,pool=t.poolDepth??2.8;
      if(!(top>bottom&&top>(o.footY??0)&&run>0&&pool>0))throw new Error('nature_cascade tier top must exceed bottom and footY, with positive run/poolDepth');
      g.updateWorldMatrix(true,false);const rockPoint=g.localToWorld(new THREE.Vector3(t.x??0,0,z-.08));
      const rock=terrain({id:o.id+'-ledge-'+i,position:rockPoint.toArray(),rotation:o.rotation??0,size:[w+(o.rockMargin??2)*2,top,run+pool],section:[[-run-pool,o.footY??0],[-run-pool,top-.12,1],[0,top,.96],[.06,bottom+.15,.93],[0,o.footY??0]],jaggedness:.16,segments:24,strata:Math.max(3,Math.ceil((top-(o.footY??0))*1.4)),boulders:0,moss:false,color:o.rockColor||C.rock,seamColor:o.seamColor||C.seam,seed:(o.seed??5)+i});g.attach(rock);rock.name=o.id+'-ledge-'+i;
      const p=g.localToWorld(new THREE.Vector3(t.x??0,0,z+.09));const child=cascade({...o,tiers:undefined,id:o.id+'-tier-'+i,position:p.toArray(),baseY:0,rotation:(o.rotation??0),width:w,profile:[[0,top+.05],[run*.25,top],[run,bottom+.06]],ribbons:o.ribbons??48,segments:o.segments??20,seed:(o.seed??5)+i});g.attach(child);
      const water=add(g,lakeShape([[(t.x??0)-w/2,z+run],[(t.x??0)+w/2,z+run],[(t.x??0)+w*.55,z+run+pool],[(t.x??0)-w*.55,z+run+pool]]),o.poolColor||C.water,o.id+'-pool-'+i);water.position.y=bottom+.06;water.castShadow=false;
      rock.userData.tier=i;
    }return g;
  }
  register('nature_line',o=>{
    const g=root(o),coaster=o.kind==='coaster';if(o.kind&&!['cable','coaster'].includes(o.kind))throw new Error('Unknown nature_line kind');
    if(o.points&&(o.points.length<2||o.points.every(p=>p.every((v,k)=>v===o.points[0][k]))))throw new Error('nature_line needs distinct profile points');
    const points=o.terrain?drapePoints(o,o.points||[[-20,0,0],[20,0,0]]):o.points||[[-20,0,0],[0,4,0],[20,8,0]],height=o.height??(coaster?1.2:8),profile=points.map(([x,y,z])=>new THREE.Vector3(x,y+height,z)),curve=new THREE.CatmullRomCurve3(profile,false,'centripetal'),length=curve.getLength(),samples=curve.getSpacedPoints(Math.max(40,Math.ceil(length/.6))),posts=[],cables=[],frames=[],cabins=[],glass=[],wheels=[],station=[],seams=[];
    const at=t=>curve.getPointAt(t),towers=o.towers??Math.max(2,Math.ceil(length/18)+1),foot=t=>{const p=at(t);return o.terrain?terrainFloor(g,o.terrain,p.x,p.z):p.y-height;};
    if(!(Number.isInteger(towers)&&towers>=2))throw new Error('nature_line requires at least two towers');
    const sagAt=t=>{const s=t*(towers-1)%1;return 4*(o.sag??.8)*s*(1-s);};
    for(let i=0;i<towers;i++){const t=i/(towers-1),p=at(t),y=foot(t),tan=curve.getTangentAt(t),side=new THREE.Vector3(tan.z,0,-tan.x).normalize().multiplyScalar(1.3);rodItems(posts,[p.x,y,p.z],[p.x,p.y,p.z],o.postRadius??(coaster?.07:.16));if(!coaster)rodItems(frames,p.clone().sub(side).toArray(),p.clone().add(side).toArray(),.085);}
    for(let i=1;i<samples.length;i++){const a=samples[i-1],b=samples[i];for(const side of [-1,1]){const tangent=b.clone().sub(a).normalize(),offset=new THREE.Vector3(tangent.z,0,-tangent.x).multiplyScalar(side*(o.gauge??(coaster?.7:1.8))/2),p=a.clone().add(offset),q=b.clone().add(offset);if(!coaster){p.y-=sagAt((i-1)/(samples.length-1));q.y-=sagAt(i/(samples.length-1));}rodItems(cables,p.toArray(),q.toArray(),o.lineRadius??(coaster?.035:.022));if(coaster&&side===1&&i%3===0)rodItems(frames,a.clone().sub(offset).toArray(),a.clone().add(offset).toArray(),.026);}}
    for(let i=0;i<(o.vehicles??7);i++){const t=(i+.5)/(o.vehicles??7),p=at(t),tan=curve.getTangentAt(t),yaw=Math.atan2(tan.x,tan.z);if(!coaster){p.add(new THREE.Vector3(tan.z,0,-tan.x).multiplyScalar((i%2?1:-1)*(o.gauge??1.8)/2));p.y-=sagAt(t);const vs=o.vehicleScale??1;if(!(vs>0))throw new RangeError('nature_line: vehicleScale must be positive');rodItems(frames,p.toArray(),[p.x,p.y-.7*vs,p.z],.025*vs);cabins.push({p:[p.x,p.y-1.55*vs,p.z],s:[1.2*vs,1.35*vs,1.35*vs],r:[0,yaw,0]});glass.push({p:[p.x,p.y-1.35*vs,p.z],s:[1.23*vs,.62*vs,1.38*vs],r:[0,yaw,0]});}else{cabins.push({p:[p.x,p.y+.2,p.z],s:[.7,.3,1.15],r:[0,yaw,0]});glass.push({p:[p.x-tan.x*.35,p.y+.52,p.z-tan.z*.35],s:[.65,.45,.15],r:[0,yaw,0]});wheels.push({p:[p.x,p.y+.035,p.z],s:[.8,.12,.65],r:[0,yaw,0]});}}
    if(o.stations!==false)for(const t of [0,1]){const p=at(t),y=foot(t),size=o.stationSize||[5,o.stationHeight??(coaster?3:height+1),4],h=size[1];station.push({p:[p.x,y+h/2,p.z],s:size});seams.push(p.x-size[0]/2,y+h+.02,p.z,p.x+size[0]/2,y+h+.02,p.z);}
    rods(g,posts,o.postColor||'#8b9283',o.id+'-towers');rods(g,cables,o.lineColor||'#737d70',o.id+'-'+(coaster?'rails':'cables'),6);rods(g,frames,o.frameColor||'#899181',o.id+'-frames',6);instances(g,new THREE.BoxGeometry(1,1,1),cabins,o.vehicleColor||'#b6a08b',o.id+'-vehicles');instances(g,new THREE.BoxGeometry(1,1,1),glass,o.glassColor||'#a1b2a8',o.id+'-windows');instances(g,new THREE.BoxGeometry(1,1,1),wheels,o.lineColor||'#737d70',o.id+'-bogies');instances(g,new THREE.BoxGeometry(1,1,1),station,o.stationColor||'#bcb9a7',o.id+'-stations');line(g,seams,o.frameColor||'#899181',o.id+'-station-seams',.4);return g;
  });
  function streamRapids(g,o,points,sample){
    const rand=random((o.seed??11)+113),foam=[],streaks=[],r=o.rapids,count=r.count??24,w=o.width??3.5,level=o.level??.04;
    const footprint=[...offsetPoints(points,-w/2),...offsetPoints(points,w/2).reverse()].map(p=>[p[0],p[2]]),within=(p,margin=0)=>[[margin,0],[-margin,0],[0,margin],[0,-margin]].every(([x,z])=>inside(p.x+x,p.z+z,footprint));
    const wake=(p,side,tangent,scale)=>{for(let j=0;j<5;j++){const t=j/4,q=p.clone().addScaledVector(tangent,.2+t*scale*1.7).addScaledVector(side,Math.sin(t*4+j)*scale*.18),radius=scale*(.28+.2*t);if(within(q,radius))foam.push({p:[q.x,q.y+level+.028,q.z],s:[radius,.018,scale*.16],r:[0,Math.atan2(tangent.x,tangent.z),0]});}};
    for(let i=0;i<count;i++){const {p,side,tangent}=sample((i+.25+rand()*.5)/count);p.addScaledVector(side,(rand()-.5)*w*.7);const scale=(r.scale??.65)*(.7+rand()*.5);wake(p,side,tangent,scale);for(let j=0;j<3;j++){const a=p.clone().addScaledVector(side,(j-1)*scale*.4),b=a.clone().addScaledVector(tangent,scale*1.5);if(within(a)&&within(b))streaks.push(a.x,a.y+level+.04,a.z,b.x,b.y+level+.04,b.z);}}
    instances(g,new THREE.SphereGeometry(1,7,4),foam,o.foamColor||C.foam,o.id+'-rapids');line(g,streaks,o.foamColor||C.foam,o.id+'-rapid-lines',.7);
  }

  register('nature_lights',o=>{
    const g=root(o),points=o.points||[[-4,0,0],[4,0,0]],height=o.height??3.4,sag=o.sag??.45,spacing=o.bulbSpacing??.75,posts=[],wires=[],bulbs=[],sockets=[],seen=new Set();
    for(const p of points){const key=p.join(',');if(seen.has(key))continue;seen.add(key);rodItems(posts,p,[p[0],p[1]+height+.06,p[2]],o.postRadius??.04);}
    for(let i=1;i<points.length;i++){
      const a=new THREE.Vector3(...points[i-1]),b=new THREE.Vector3(...points[i]),length=a.distanceTo(b),count=Math.max(1,Math.ceil(length/spacing)),at=t=>a.clone().lerp(b,t).add(new THREE.Vector3(0,height-4*sag*t*(1-t),0));
      for(let j=0;j<count*3;j++)rodItems(wires,at(j/(count*3)).toArray(),at((j+1)/(count*3)).toArray(),o.wireRadius??.009);
      for(let j=0;j<=count;j++){const p=at(j/count);sockets.push({p:[p.x,p.y-.035,p.z],s:[.025,.07,.025]});bulbs.push({p:[p.x,p.y-.115,p.z],s:[o.bulbRadius??.07,(o.bulbRadius??.07)*1.2,o.bulbRadius??.07]});}
    }
    rods(g,posts,o.postColor||C.wood,o.id+'-posts');rods(g,wires,o.wireColor||'#707969',o.id+'-wire',5);instances(g,new THREE.BoxGeometry(1,1,1),sockets,o.wireColor||'#707969',o.id+'-sockets');const m=instances(g,new THREE.SphereGeometry(1,7,5),bulbs,o.bulbColor||'#e4dcc3',o.id+'-bulbs');if(m){m.material=m.material.clone();m.material.emissive.set(o.bulbColor||'#e4dcc3');m.material.emissiveIntensity=o.glow??.12;}return g;
  });

  function timberTable(g,{size=[2.4,.75,.85],kind='picnic_table',color=C.wood,seatColor=color},at=[0,0,0],rotation=0){
    const parts=[],[w,h,d]=size,angle=rotation*Math.PI/180,put=(p,s,c=color)=>{const x=p[0]*Math.cos(angle)+p[2]*Math.sin(angle),z=-p[0]*Math.sin(angle)+p[2]*Math.cos(angle);parts.push({p:[at[0]+x,at[1]+p[1],at[2]+z],s,r:[0,angle,0],c});};
    const seat=kind==='bench';put([0,h-.045,0],[w,.09,d]);
    for(const x of [-w*.35,w*.35])for(const z of [-d*.32,d*.32])put([x,(h-.09)/2,z],[.075,h-.09,.075]);
    if(!seat)for(const x of [-w*.35,w*.35])put([x,h*.5,0],[.075,.075,d*.82]);
    if(kind==='picnic_table')for(const s of [-1,1]){put([0,.43,s*(d/2+.28)],[w,.09,.32],seatColor);for(const x of [-w*.35,w*.35])put([x,.195,s*(d/2+.28)],[.08,.39,.08]);}
    return parts;
  }
  register('nature_furniture',o=>{
    const g=root(o),kind=o.kind||'picnic_table',color=o.color||C.wood;
    if(kind==='log_seat'){
      const [length,height,depth]=o.size||[1.8,.42,.42],logs=[{p:[0,height/2,0],s:[height/2,length,depth/2],r:[0,0,Math.PI/2]}];
      rods(g,logs,color,o.id+'-log',12);for(const x of [-length/2-.004,length/2+.004]){const m=add(g,new THREE.CircleGeometry(depth/2,12),o.endColor||'#b4a58b');m.rotation.y=Math.PI/2;m.scale.y=height/depth;m.position.set(x,height/2,0);m.material=m.material.clone();m.material.side=THREE.DoubleSide;}
    }else if(kind==='folding_chair'){
      const [w,h,d]=o.size||[.6,.85,.6],legs=[],fabric=[];for(const x of [-w/2,w/2]){rodItems(legs,[x,.02,-d/2],[x,.48,d/2],.018);rodItems(legs,[x,.02,d/2],[x,.48,-d/2],.018);rodItems(legs,[x,.42,-d/2],[x,h,-d/2-.07],.018);}
      fabric.push({p:[0,.44,0],s:[w,.035,d]},{p:[0,(h+.45)/2,-d/2-.04],s:[w,h-.45,.035]});instances(g,new THREE.BoxGeometry(1,1,1),fabric,o.fabricColor||'#adb096',o.id+'-canvas');rods(g,legs,o.frameColor||'#7b8375',o.id+'-frame');
    }else{
      if(!['picnic_table','table','bench'].includes(kind))throw new Error('Unknown nature_furniture kind: '+kind);
      instances(g,new THREE.BoxGeometry(1,1,1),timberTable(g,{...o,size:o.size||(kind==='bench'?[2,.43,.35]:[2.4,.75,.85]),kind,color}),'#ffffff',o.id+'-timber');
    }
    return g;
  });
  register('nature_firepit',o=>{
    const g=root(o),radius=o.radius??.85,count=o.stones??18,ring=[],logs=[],seats=[],ends=[],rand=random(o.seed??5),[sw,sh,sd]=o.stoneSize||[.37,.28,.32];
    const ash=add(g,new THREE.CylinderGeometry(radius*.91,radius*.91,.035,32),o.ashColor||'#828474',o.id+'-ash');ash.position.y=.02;
    for(let i=0;i<count;i++){const a=i*Math.PI*2/count,s=.86+rand()*.25;ring.push({p:[Math.sin(a)*radius,sh*.425*s,Math.cos(a)*radius],s:[sw*s/2,sh*s/2,sd*s/2],r:[0,a,0]});}
    instances(g,new THREE.IcosahedronGeometry(1,0),ring,o.stoneColor||'#a3a18f',o.id+'-ring');
    for(const a of [.3,2.5,4.4])rodItems(logs,[-Math.cos(a)*radius*.65,.09,-Math.sin(a)*radius*.65],[Math.cos(a)*radius*.65,.15,Math.sin(a)*radius*.65],.075);
    rods(g,logs,o.logColor||'#7e806b',o.id+'-logs',9);
    for(const [angle,distance,length] of o.seats||[[0,2.2,1.8],[120,2.2,1.8],[240,2.2,1.8]]){const a=angle*Math.PI/180,x=Math.sin(a)*distance,z=Math.cos(a)*distance,h=o.seatHeight??.42;seats.push({p:[x,h/2,z],s:[h/2,length,h/2],r:[0,a,Math.PI/2],order:'YXZ'});for(const s of [-1,1])ends.push({p:[x+s*Math.cos(a)*(length/2+.004),h/2,z-s*Math.sin(a)*(length/2+.004)],s:[h*.46,.012,h*.46],r:[0,a,Math.PI/2],order:'YXZ'});}
    rods(g,seats,o.seatColor||C.wood,o.id+'-seats',12);rods(g,ends,o.endColor||'#b8aa90',o.id+'-endgrain',12);return g;
  });

  register('nature_pavilion',o=>{
    const [w,h,d]=o.size||[8,3.2,7],deck=o.deckHeight??.3,g=platform({...o,size:[w,d],height:deck,rails:o.rails??true,railHeight:o.railHeight??.9},false),posts=[],beams=[],grid=[],tables=[],roof=o.roof||'net',top=deck+h;
    for(const x of [-w/2,w/2])for(const z of [-d/2,d/2])rodItems(posts,[x,deck,z],[x,top,z],o.postRadius??.065);
    for(const z of [-d/2,d/2])rodItems(beams,[-w/2,top,z],[w/2,top,z],.045);for(const x of [-w/2,w/2])rodItems(beams,[x,top,-d/2],[x,top,d/2],.045);
    const m=surface(g,[-w/2,top,-d/2,-w/2,top,d/2,w/2,top,d/2,-w/2,top,-d/2,w/2,top,d/2,w/2,top,-d/2],o.roofColor||'#a7ae9b',o.id+'-'+roof);
    if(roof==='net'){m.material.transparent=true;m.material.opacity=o.netOpacity??.32;m.material.depthWrite=false;m.castShadow=false;const spacing=o.netSpacing??.22;for(let x=-w/2;x<=w/2;x+=spacing)grid.push(x,top+.006,-d/2,x,top+.006,d/2);for(let z=-d/2;z<=d/2;z+=spacing)grid.push(-w/2,top+.008,z,w/2,top+.008,z);line(g,grid,o.netColor||'#7f8978',o.id+'-net-grid',.34);}else if(roof!=='shade')throw new Error('Unknown nature_pavilion roof: '+roof);
    for(const [x,z] of o.tables||[[-2,0],[2,0]])tables.push(...timberTable(g,{kind:'picnic_table',size:o.tableSize||[4.6,.75,.9],color:o.tableColor||C.wood},[x,deck,z],o.tableRotation??90));
    rods(g,posts,o.frameColor||C.wood,o.id+'-columns');rods(g,beams,o.frameColor||C.wood,o.id+'-beams');instances(g,new THREE.BoxGeometry(1,1,1),tables,'#ffffff',o.id+'-tables');return g;
  });

  register('nature_gravel',o=>{
    const g=root(o),[w,d]=o.size||[8,6],polygon=outline(o,w,d),top=o.thickness??.055,rand=random(o.seed??19),grains=[],xs=polygon.map(p=>p[0]),zs=polygon.map(p=>p[1]),minX=Math.min(...xs),maxX=Math.max(...xs),minZ=Math.min(...zs),maxZ=Math.max(...zs);
    paved(patch(g,polygon,()=>top,o.color||'#bdb8a6',o.id+'-ground'));
    const count=o.granules??240;for(let i=0,tries=0;i<count&&tries<count*20;tries++){const x=minX+rand()*(maxX-minX),z=minZ+rand()*(maxZ-minZ);if(!inside(x,z,polygon))continue;const s=(o.grainSize??.045)*(.6+rand()*.7);grains.push({p:[x,top+s*.22,z],s:[s,s*.24,s*.7],r:[0,rand()*6,0],c:i%3===0?(o.lightColor||'#cecaba'):(o.grainColor||'#aba996')});i++;}
    instances(g,new THREE.IcosahedronGeometry(1,0),grains,'#ffffff',o.id+'-grains');return g;
  });

  register('nature_terrace',o=>{
    const g=root(o),[w,d]=o.size||[12,7],polygon=outline(o,w,d),h=o.height??.65,slope=o.slope||[0,0],floor=(x,z)=>h+x*slope[0]+z*slope[1],bottom=Math.min(-.05,...polygon.map(([x,z])=>floor(x,z)-.06)),v=[],lip=[];
    patch(g,polygon,floor,o.color||'#b1bc9d',o.id+'-lawn');
    for(let i=0;i<polygon.length;i++){const [x,z]=polygon[i],[xx,zz]=polygon[(i+1)%polygon.length],a=[x,floor(x,z),z],b=[xx,floor(xx,zz),zz],c=[xx,bottom,zz],d=[x,bottom,z];v.push(...a,...b,...c,...a,...c,...d);lip.push(...[x,a[1]+.008,z],...[xx,b[1]+.008,zz]);}
    surface(g,v,o.retainingColor||'#a5a58e',o.id+'-retaining');line(g,lip,o.edgeColor||'#969e83',o.id+'-lip',.4);return g;
  });
  register('nature_flowerbed',o=>{
    const g=root(o),[w,d]=o.size||[6,2],rand=random(o.seed??23),count=o.count??100,kind=o.kind||'mixed',slope=o.slope||[0,0],floor=(x,z)=>x*slope[0]+z*slope[1],stems=[],leaves=[],petals=[],centres=[],palette=o.flowerColors?.length?o.flowerColors:['#e3e1d4','#cbb4bd'],exclude=o.exclude||[];
    if(o.ground!==false)patch(g,outline(o,w,d),(x,z)=>floor(x,z)+.018,o.groundColor||'#a3af8f',o.id+'-ground');
    for(let i=0;i<count;i++){
      const columns=Math.max(1,Math.round(Math.sqrt(count*w/d))),rows=Math.ceil(count/columns),x=(-.5+((i%columns)+.15+rand()*.7)/columns)*w,z=(-.5+(Math.floor(i/columns)+.15+rand()*.7)/rows)*d;
      if(exclude.some(([cx,cz,sw,sd])=>Math.abs(x-cx)<sw/2&&Math.abs(z-cz)<sd/2)||o.outline&&!inside(x,z,o.outline))continue;
      const y=floor(x,z),height=(o.height??.5)*(.65+rand()*.55),cosmos=kind==='cosmos'||kind==='mixed'&&i%3===0,r=(o.flowerRadius??.12)*(cosmos?1.1:1),color=cosmos?palette[Math.min(1,palette.length-1)]:palette[0];
      rodItems(stems,[x,y,z],[x,y+height,z],.009);leaves.push({p:[x,y+.13,z],s:[.14,.1,.13]});
      const petalsCount=cosmos?8:7;for(let j=0;j<petalsCount;j++){const a=j*Math.PI*2/petalsCount;petals.push({p:[x+Math.cos(a)*r*.65,y+height,z+Math.sin(a)*r*.65],s:[r*.66,.017,r*.3],r:[0,-a,0],c:color});}
      centres.push({p:[x,y+height+.012,z],s:[r*.27,.025,r*.27]});
    }
    rods(g,stems,o.stemColor||'#859573',o.id+'-stems',5);instances(g,new THREE.SphereGeometry(1,6,4),leaves,o.leafColor||'#97a583',o.id+'-leaves');instances(g,new THREE.SphereGeometry(1,6,3),petals,'#ffffff',o.id+'-petals');instances(g,new THREE.SphereGeometry(1,6,3),centres,o.centerColor||'#b8aa7d',o.id+'-centres');return g;
  });
})();
