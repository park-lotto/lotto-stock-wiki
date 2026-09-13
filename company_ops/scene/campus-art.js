import * as T from 'three';
import {panel,text} from './studio-art.js';
import {buildings,waterRings} from './campus-layout.js';

// Curved buildings are true volumetric sectors, visible from every direction.
function sectorGeometry(inner,outer,start,end,height){
 const shape=new T.Shape(),steps=Math.max(12,Math.ceil((end-start)*32));
 for(let i=0;i<=steps;i++){const a=start+(end-start)*i/steps,x=Math.sin(a)*outer,y=-Math.cos(a)*outer;i?shape.lineTo(x,y):shape.moveTo(x,y);}
 for(let i=steps;i>=0;i--){const a=start+(end-start)*i/steps;shape.lineTo(Math.sin(a)*inner,-Math.cos(a)*inner);}shape.closePath();
 const geometry=new T.ExtrudeGeometry(shape,{depth:height,bevelEnabled:false,steps:1});geometry.rotateX(-Math.PI/2);return geometry;
}
export function buildGardenCampus(scene){
 const root=new T.Group();scene.add(root);const materials=new Map(),blocks=[],trees=[],lamps=[];
 const material=(color,roughness=.65,metalness=.05)=>{const key=[color,roughness,metalness].join();if(!materials.has(key))materials.set(key,new T.MeshStandardMaterial({color,roughness,metalness}));return materials.get(key);};
 const stone=material('#ddd8c6'),trim=material('#f0ebdb'),glass=material('#365d65',.19,.5),water=material('#397b8e',.16,.6),road=material('#707b7c'),soil=material('#587b54');
 const warm=new T.MeshStandardMaterial({color:'#f3dba2',emissive:'#ffd68a',emissiveIntensity:.22,roughness:.4});
 function sector(inner,outer,start,end,y,height,mat){const m=new T.Mesh(sectorGeometry(inner,outer,start,end,height),mat);m.position.y=y;m.castShadow=true;m.receiveShadow=true;root.add(m);return m;}
 const ring=(inner,outer,y,height,mat)=>sector(inner,outer,0,Math.PI*2,y,height,mat);
 function block(w,h,d,x,y,z,color,angle=0){blocks.push({w,h,d,x,y,z,color,angle});}
 function tree(x,z,size=1,y=0){trees.push({x,z,size,y});}
 function polar(radius,angle){return {x:Math.sin(angle)*radius,z:Math.cos(angle)*radius};}
 function pole(x,z,y=0){block(.12,3.1,.12,x,y+1.55,z,'#546260');block(.8,.14,.25,x,y+3.1,z,'#f2dbac');lamps.push(new T.Vector3(x,y+3.1,z));}
 // Large continuous terrain, not a small display plinth.
 block(210,.7,210,0,-.65,0,'#718965');
 ring(.01,17.7,-.12,.2,stone);
 for(const [inner,outer]of waterRings){ring(inner-.45,outer+.45,-.38,.16,stone);ring(inner,outer,-.08,.05,water);ring(inner-.12,inner,.03,.18,trim);ring(outer,outer+.12,.03,.18,trim);}
 for(const [inner,outer]of [[24.4,28.8],[45.3,49.1],[66.5,71]]){
  ring(inner-.5,outer+.5,-.12,.15,stone);ring(inner,outer,.04,.06,road);
  for(let i=0;i<120;i++){const a=i*Math.PI/60;sector((inner+outer)/2-.045,(inner+outer)/2+.045,a,a+.022,.105,.012,trim);}
 }
 // Bridges align with the main avenue and four spoke routes.
 for(const angle of [0,Math.PI,Math.PI/3,-Math.PI/3,2*Math.PI/3,-2*Math.PI/3]){
  for(const [inner,outer]of waterRings){const r=(inner+outer)/2,p=polar(r,angle),length=outer-inner+2.2;
   block(3.7,.32,length,p.x,.2,p.z,'#c7c5b8',angle);
   for(const side of [-1,1]){const dx=Math.cos(angle)*side*1.9,dz=-Math.sin(angle)*side*1.9;block(.08,.08,length,p.x+dx,1.25,p.z+dz,'#d6d8c9',angle);for(let j=0;j<4;j++){const k=-length/2+j*length/3;block(.07,1,.07,p.x+dx+Math.sin(angle)*k,.75,p.z+dz+Math.cos(angle)*k,'#b9c7c0');}}
  }
 }
 // Headquarters: three glazed levels, deep terraces, rooftop gardens.
 ring(.01,14.3,.1,.55,trim);
 for(let floor=0;floor<3;floor++){
  const radius=12.7-floor*1.5,y=.65+floor*4;
  ring(.01,radius,y,3.55,glass);ring(.01,radius+.8,y+3.55,.4,trim);
  for(let i=0;i<64;i++){const a=i*Math.PI/32,p=polar(radius+.03,a);block(.15,3.6,.15,p.x,y+1.8,p.z,'#d5d3c1',a);}
  ring(radius-.45,radius+.1,y+3.97,.1,soil);
  for(let i=0;i<18;i++){const p=polar(radius-.15,i*Math.PI/9);tree(p.x,p.z,.4,y+4.05);}
 }
 ring(.01,5.7,12.7,.5,stone);ring(3.6,5.2,13.2,1,glass);ring(3.4,5.5,14.2,.25,trim);
 block(7.2,11,.55,0,6.7,12.5,'#263d47');
 panel(root,6.7,8.6,0,7.1,12.79,(c,W,H)=>{text(c,'M',W*.28,H*.29,380,'#edf2e6',750);text(c,'메이커스랩',W*.08,H*.56,145,'#e5eadc',650);text(c,'MAKERS LAB',W*.1,H*.69,90,'#c2d3ce',600);text(c,'통합 관제 · 본사',W*.1,H*.82,70,'#afc9c7');},'#263d47');
 // Program wings. Each curved volume gets full facade detail on both radial faces.
 for(const b of buildings){
  const a0=b.angle-b.span/2,a1=b.angle+b.span/2,inner=b.radius-b.depth/2,outer=b.radius+b.depth/2;
  sector(inner-.5,outer+.5,a0-.018,a1+.018,.0,.35,stone);
  for(let f=0;f<b.floors;f++){
   const y=.35+f*3.4,inset=f===b.floors-1?.7:0;
   sector(inner+inset,outer-inset,a0,a1,y,3.05,glass);
   sector(inner-.25,outer+.25,a0-.008,a1+.008,y+3.05,.35,trim);
   for(const radius of [inner+inset,outer-inset])for(let j=0;j<=12;j++){
    const a=a0+(a1-a0)*j/12,p=polar(radius,a);block(.13,3.05,.13,p.x,y+1.52,p.z,'#dfddca',a);
    if(j%3===0){const q=polar(radius+(radius>b.radius?.06:-.06),a);block(.07,2.65,.07,q.x,y+1.5,q.z,'#e4cb96');}
   }
   // Warm facade strips articulate the floor rather than invented activity lights.
   sector(inner-.07,inner+.03,a0,a1,y+.18,.06,warm);
  }
  const roof=.35+b.floors*3.4;
  sector(inner+.65,outer-.65,a0+.025,a1-.025,roof,.12,soil);
  sector(inner+.3,inner+.45,a0,a1,roof,.65,trim);sector(outer-.45,outer-.3,a0,a1,roof,.65,trim);
  for(let j=0;j<5;j++){const a=a0+.045+(a1-a0-.09)*j/4,p=polar(b.radius,a);tree(p.x,p.z,.65,roof+.15);}
  const end=polar(b.radius,b.angle),cap=polar(b.radius,a1);
  block(.35,b.floors*3.4, b.depth,cap.x,b.floors*1.7+.35,cap.z,'#c9c7b7',a1);
  const front=polar(inner-.2,b.angle);block(2,2.7,.15,front.x,1.7,front.z,'#243f48',b.angle);
  for(const da of [-.08,.08]){const p=polar(inner-1,b.angle+da);pole(p.x,p.z);}
  // A small rooftop service core, not another program/company.
  block(2.4,1.2,1.8,end.x,roof+.65,end.z,'#c5c7b7',b.angle);
 }
 // Broad front entry axis, gate and forecourt fountain.
 block(8,.13,31,0,.05,80,'#747f7e');
 for(const x of [-5.5,5.5])block(2,.12,35,x,.02,80,'#c7c6b5');
 for(let i=0;i<9;i++)block(.1,.015,1.8,0,.13,69+i*3,'#dddccd');
 block(18,.15,6,0,.06,69,'#d6d2c1');
 for(const x of [-6,6])block(2,4.5,1.4,x,2.4,69,'#d8d4c3');
 block(14,1.25,1.4,0,4.7,69,'#d8d4c3');block(8,1.1,.1,0,4.7,69.76,'#3c535b');
 panel(root,7.4,.95,0,4.7,69.82,(c,W,H)=>text(c,'MAKERS LAB',35,H*.73,110,'#e7ecdf',650),'#3c535b');
 for(const x of [-8,8])pole(x,66);
 const fountain=new T.Group();fountain.position.z=33;root.add(fountain);
 const basin=new T.Mesh(new T.CylinderGeometry(5.8,5.8,.35,64),stone);basin.position.y=.1;fountain.add(basin);
 const surface=new T.Mesh(new T.CylinderGeometry(5.35,5.35,.08,64),water);surface.position.y=.3;fountain.add(surface);
 const centerpiece=new T.Mesh(new T.TorusGeometry(1.8,.12,8,48),trim);centerpiece.rotation.x=Math.PI/2;centerpiece.position.y=.6;fountain.add(centerpiece);
 for(const sign of [-1,1])for(let j=0;j<11;j++){tree(sign*7.5,22+j*6,1.05);pole(sign*5.8,23+j*6);}
 // Radial avenues and landscaped setbacks keep all ground footprints distinct.
 for(const radius of [16.3,23.8,29.5,39,44.7,59.8,65.7,72.4])for(let i=0;i<90;i++){
  const a=i*Math.PI/45,p=polar(radius,a);if(Math.abs(p.x)<9)continue;
  tree(p.x,p.z,.65+(i%4)*.12);if(i%6===0)pole(p.x+.8,p.z);
 }
 // Distant woodland and outlined plots convey continued land, not a floating toy.
 let seed=431;const random=()=>{seed=(seed*1664525+1013904223)>>>0;return seed/4294967296;};
 for(let i=0;i<310;i++){const a=random()*Math.PI*2,r=78+random()*19,p=polar(r,a);if(p.z>68&&Math.abs(p.x)<15)continue;tree(p.x,p.z,1.1+random());}
 for(const x of [-83,83])for(const z of [-48,-15,18]){
  block(16,.08,23,x,-.2,z,'#81907b');for(const dx of [-8,8])block(.12,.03,23,x+dx,-.14,z,'#d3d4ba');for(const dz of [-11.5,11.5])block(16,.03,.12,x,-.14,z+dz,'#d3d4ba');
 }
 // Repeated parts share geometry and draw calls, instead of thousands of individual meshes.
 function instance(geometry,entries,mat){const mesh=new T.InstancedMesh(geometry,mat,entries.length),o=new T.Object3D();entries.forEach((e,i)=>{o.position.set(e.x,e.y,e.z);o.scale.set(e.w,e.h,e.d);o.rotation.set(0,e.angle||0,0);o.updateMatrix();mesh.setMatrixAt(i,o.matrix);mesh.setColorAt(i,new T.Color(e.color));});mesh.castShadow=true;mesh.receiveShadow=true;root.add(mesh);return mesh;}
 instance(new T.BoxGeometry(1,1,1),blocks,material('#ffffff'));
 const trunks=[],foliage=[];
 trees.forEach((t,i)=>{trunks.push({x:t.x,y:t.y+.8*t.size,z:t.z,w:.16*t.size,h:1.6*t.size,d:.16*t.size,color:'#746b4e'});for(let j=0;j<3;j++)foliage.push({x:t.x+Math.sin(j*2.1+i)*.35*t.size,y:t.y+(1.65+j*.36)*t.size,z:t.z+Math.cos(j*2.1+i)*.3*t.size,w:(1.05-j*.14)*t.size,h:(1.1-j*.1)*t.size,d:(1.05-j*.14)*t.size,color:['#4b754a','#668350','#82945d','#3e6747'][i%4]});});
 instance(new T.CylinderGeometry(1,1,1,6),trunks,material('#ffffff'));
 instance(new T.IcosahedronGeometry(1,1),foliage,material('#ffffff'));
 return {root,warm,water,buildingCount:buildings.length,treeCount:trees.length};
}
