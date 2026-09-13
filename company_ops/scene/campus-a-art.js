import * as T from 'three';
import {panel,text} from './studio-art.js';
import {aBuildings} from './campus-a-layout.js';

export function buildACampus(scene){
 const root=new T.Group();scene.add(root);const solid=[],windows=[],lit=[],trees=[],lights=[];
 const palette={stone:'#d9cdb4',trim:'#efe3ce',bronze:'#978360',paving:'#c3c2ac',grass:'#58764a'};
 const mat=(color,roughness=.7,metalness=.05)=>new T.MeshStandardMaterial({color,roughness,metalness});
 const warm=new T.MeshStandardMaterial({color:'#305563',emissive:'#ffd19a',emissiveIntensity:.025,roughness:.38,metalness:.12});
 const glass=new T.MeshPhysicalMaterial({color:'#6e9eaa',transparent:true,opacity:.22,roughness:.12,metalness:.3,depthWrite:false,side:T.DoubleSide});
 const water=mat('#247589',.12,.55);
 function box(w,h,d,x,y,z,color=palette.stone,angle=0,list=solid){list.push({w,h,d,x,y,z,color,angle});}
 function tree(x,z,size=1,y=0,flower=false){trees.push({x,z,size,y,flower});}
 function mesh(geometry,material,x,y,z){const m=new T.Mesh(geometry,material);m.position.set(x,y,z);m.castShadow=true;m.receiveShadow=true;root.add(m);return m;}
 function cylinder(r,h,x,y,z,color){return mesh(new T.CylinderGeometry(r,r,h,64),mat(color),x,y,z);}
 // Paths and waterways are independent editable objects, with geometric depth.
 box(160,.5,136,0,-.55,0,'#627e50');
 box(16,.12,116,0,-.2,4,palette.paving);
 box(133,.13,9,0,-.18,-18,palette.paving);box(133,.13,8,0,-.18,36,palette.paving);
 const waterPoints=[[-22,-43],[-19,-23],[-24,-6],[-19,9],[-24,24],[-19,40]];
 function ribbon(points,width,y,material){const curve=new T.CatmullRomCurve3(points.map(([x,z])=>new T.Vector3(x,y,z))),verts=[],idx=[];for(let i=0;i<=100;i++){const p=curve.getPoint(i/100),t=curve.getTangent(i/100),n=new T.Vector3(-t.z,0,t.x).normalize().multiplyScalar(width/2);verts.push(p.x+n.x,y,p.z+n.z,p.x-n.x,y,p.z-n.z);if(i<100){const k=i*2;idx.push(k,k+2,k+1,k+1,k+2,k+3);}}const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(verts,3));g.setIndex(idx);g.computeVertexNormals();const m=new T.Mesh(g,material);m.receiveShadow=true;root.add(m);return m;}
 for(const sign of [-1,1]){const points=waterPoints.map(([x,z])=>[Math.abs(x)*sign,z]);ribbon(points,6,-.12,mat('#b1ae95'));ribbon(points,4.6,-.08,water);}
 // Formal pools before the project pavilion, clear central footpath.
 for(const x of [-7.1,7.1]){box(6.2,.12,15,x,-.15,38,palette.trim);box(5.5,.06,14,x,-.045,38,'#ffffff',0,windows);mesh(new T.BoxGeometry(5.5,.05,14),water,x,-.015,38);}
 for(const sign of [-1,1])for(const z of [-18,6,36]){
  box(9,.25,3.6,sign*22,.12,z,palette.trim);for(const edge of [-1,1]){box(9,.08,.08,sign*22,1.1,z+edge*1.8,palette.bronze);for(let j=0;j<6;j++)box(.07,.85,.07,sign*22-4+j*1.6,.65,z+edge*1.8,palette.bronze);}
 }
 function glow(x,z){const light=new T.PointLight('#ffd197',0,16,2);light.position.set(x,2.2,z);root.add(light);lights.push(light);}
 function lamp(x,z){box(.12,2.3,.12,x,1.0,z,'#4b5b54');box(.38,.15,.38,x,2.23,z,'#ffffff',0,lit);}
 // Layered office volumes: real floors, set-back inner partitions and furniture behind glazing.
 for(const b of aBuildings){const total=b.floors*3.65;
  box(b.w+1.2,.4,b.d+1.2,b.x,.03,b.z,palette.stone);
  for(let f=0;f<b.floors;f++){
   const y=.3+f*3.65;
   box(b.w,.24,b.d,b.x,y,b.z,palette.trim);
   box(b.w-1.2,2.95,.22,b.x,y+1.65,b.z-b.d/2+.7,'#857d68');
   box(.3,3.3,b.d-.8,b.x-b.w/2+.4,y+1.77,b.z,palette.stone);box(.3,3.3,b.d-.8,b.x+b.w/2-.4,y+1.77,b.z,palette.stone);
   for(let j=0;j<Math.floor(b.w/3);j++){
    const x=b.x-b.w/2+2+j*3;
    box(2.5,2.2,.06,x,y+1.8,b.z-b.d/2+.86,'#ffffff',0,lit);
    for(const dz of [-1.2,2.2]){box(1.7,.08,.7,x,y+.9,b.z+dz,'#a99b7e');box(.65,.48,.07,x,y+1.2,b.z+dz-.13,'#284a56');box(.36,.48,.38,x,y+.65,b.z+dz+.7,'#758c87');}
   }
   // Front and back glazing; solid columns are deliberately narrow.
   for(const sign of [-1,1]){
    const z=b.z+sign*b.d/2;
    for(let j=0;j<Math.floor(b.w/2.5);j++){
     const x=b.x-b.w/2+1.25+j*2.5;
     box(2.22,2.58,.035,x,y+1.75,z-sign*.12,j%4===0?'#75818a':'#ffffff',0,lit);
     box(1.3,.09,.09,x,y+.86,z+sign*.015,'#4a524c');
     box(.43,.35,.045,x,y+1.11,z+sign*.025,'#28434a');
    }
    box(b.w-.6,3.1,.03,b.x,y+1.7,z,'#ffffff',0,windows);
    for(let j=0;j<=Math.ceil(b.w/2.5);j++){const x=b.x-b.w/2+j*b.w/Math.ceil(b.w/2.5);box(.11,3.3,.17,x,y+1.8,z,palette.bronze);}
    box(b.w+.4,.13,.2,b.x,y+3.5,z,palette.trim);box(b.w-.5,.04,.05,b.x,y+3.32,z-sign*.13,'#ffffff',0,lit);
   }
   for(const sign of [-1,1]){box(.035,3.1,b.d-.7,b.x+sign*b.w/2,y+1.7,b.z,'#ffffff',0,windows);for(let j=0;j<6;j++)box(.14,3.3,.11,b.x+sign*b.w/2,y+1.8,b.z-b.d/2+j*b.d/5,palette.bronze);}
  }
  box(b.w+1,.42,b.d+1,b.x,total+.25,b.z,palette.trim);
  box(b.w-2,.2,b.d-2,b.x,total+.5,b.z,'#627d50');
  // Rooftop walk, service core, terraced planters and pergola.
  box(b.w-3,.08,1.6,b.x,total+.65,b.z+1,palette.paving);
  box(b.w*.32,1.8,b.d*.3,b.x,total+1.4,b.z-2,palette.stone);
  for(const sign of [-1,1]){box(.16,.75,b.d+.3,b.x+sign*b.w/2,total+.85,b.z,palette.stone);box(b.w+.3,.75,.16,b.x,total+.85,b.z+sign*b.d/2,palette.stone);}
  for(let j=0;j<5;j++){const x=b.x-b.w/2+2+j*(b.w-4)/4;tree(x,b.z+b.d/2-2,.5,total+.6);}
  for(const sign of [-1,1]){tree(b.x+sign*(b.w/2-2),b.z-b.d/2+2,.65,total+.6);}
  if(b.name){
   const signWidth=Math.min(13,b.w-3);
   box(signWidth,2.8,.4,b.x,total-1.5,b.z+b.d/2+.32,'#33464e');
   panel(root,signWidth-.5,2.1,b.x,total-1.5,b.z+b.d/2+.54,(c,W,H)=>text(c,b.name,55,H*.7,Math.min(170,1050/b.name.length),'#f4e9d3',650),'#33464e');
   box(5,.22,3,b.x,3.3,b.z+b.d/2+1.5,palette.stone);for(const x of [-2.5,2.5])box(.18,3.2,.18,b.x+x,1.6,b.z+b.d/2+2.6,palette.bronze);
   glow(b.x,b.z+b.d/2+3);
  }
 }
 // Raised headquarters crown and side terraces distinguish the parent company.
 box(15,2.7,9,0,16.3,-36,palette.stone);box(15.7,.25,9.7,0,17.85,-36,palette.trim);
 for(const x of [-6,0,6])tree(x,-36,.65,18);box(12,.08,3,0,17.99,-34,'#627e50');
 // Plaza sculpture, not a fake telemetry display.
 cylinder(4,.3,0,.1,-7,palette.trim);cylinder(3.5,.12,0,.32,-7,'#376f7a');
 const sculpture=mesh(new T.TorusKnotGeometry(1.1,.12,72,10),mat('#b7a06c',.2,.8),0,2.1,-7);sculpture.rotation.z=.3;
 // Gate is open; the avenue is kept clear for future walk mode.
 box(120,.12,7,0,-.2,65,'#58696a');for(let i=-14;i<=14;i++)box(1.8,.015,.1,i*4,.0,65,'#d8d3b9');
 for(const x of [-8,8])box(2.5,4.7,2,x,2.15,55,palette.stone);box(20,1.15,2.2,0,4.6,55,palette.stone);
 panel(root,12,.8,0,4.6,56.13,(c,W,H)=>text(c,'MAKERS LAB',50,H*.74,100,'#33464e',700),'#d9cdb4');
 glow(-7,54);glow(7,54);
 for(const sign of [-1,1]){
  box(39,.1,20,sign*40,-.24,45,'#6e8753');
  for(const z of [34,56])box(41,.3,.6,sign*40,-.05,z,palette.stone);
  for(let i=0;i<12;i++){const z=-42+i*8;tree(sign*13.5,z,.85);lamp(sign*10.3,z);}
  for(let i=0;i<15;i++){const z=-43+i*7;tree(sign*68,z,1.1+(i%3)*.15);lamp(sign*62,z);}
  for(let i=0;i<10;i++){const x=sign*(19+i*5);tree(x,59,1.0);lamp(x,57);}
  for(const z of [-21,9,30])for(const x of [28,58])tree(sign*x,z,1.2,0,z===30);
 }
 let seed=471;const rand=()=>{seed=(seed*1664525+1013904223)>>>0;return seed/4294967296;};
 for(let i=0;i<200;i++){const x=(rand()-.5)*175,z=-56-rand()*20;tree(x,z,1+rand()*1.2);}
 // Variation inside lawns, avoiding building footprints and the central avenue.
 for(let i=0;i<110;i++){const x=(rand()-.5)*140,z=(rand()-.5)*96;if(Math.abs(x)<15||aBuildings.some(b=>Math.abs(x-b.x)<b.w/2+4&&Math.abs(z-b.z)<b.d/2+4)||Math.abs(Math.abs(x)-22)<5)continue;tree(x,z,.6+rand()*.8,0,i%13===0);}
 function instance(geometry,entries,material){const m=new T.InstancedMesh(geometry,material,entries.length),o=new T.Object3D();entries.forEach((e,i)=>{o.position.set(e.x,e.y,e.z);o.scale.set(e.w,e.h,e.d);o.rotation.set(0,e.angle||0,0);o.updateMatrix();m.setMatrixAt(i,o.matrix);m.setColorAt(i,new T.Color(e.color));});m.castShadow=true;m.receiveShadow=true;root.add(m);return m;}
 instance(new T.BoxGeometry(1,1,1),solid,mat('#ffffff'));
 const glassMesh=instance(new T.BoxGeometry(1,1,1),windows,glass);glassMesh.castShadow=false;
 instance(new T.BoxGeometry(1,1,1),lit,warm);
 const trunks=[],leaves=[];for(const t of trees){trunks.push({x:t.x,y:t.y+t.size,z:t.z,w:.15*t.size,h:2*t.size,d:.15*t.size,color:'#6c6449'});for(let j=0;j<9;j++){const a=j*2.4,r=j%3*.36*t.size;leaves.push({x:t.x+Math.sin(a)*r,y:t.y+(1.8+(j%4)*.22)*t.size,z:t.z+Math.cos(a)*r,w:.64*t.size,h:.8*t.size,d:.64*t.size,color:t.flower?['#dcbbba','#e6c8bf','#cda8ac'][j%3]:['#36563b','#507344','#6f8950','#416740'][j%4]});}}
 instance(new T.CylinderGeometry(1,1,1,6),trunks,mat('#ffffff'));instance(new T.IcosahedronGeometry(1,1),leaves,mat('#ffffff'));
 return {root,warm,water,buildingCount:aBuildings.length,treeCount:trees.length,setNight(on){warm.emissiveIntensity=on?1.25:.025;warm.color.set(on?'#d2ac77':'#305563');lights.forEach(l=>l.intensity=on?45:0);glass.opacity=on?.08:.16;}};
}
