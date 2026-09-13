import * as T from 'three';
import {RoundedBoxGeometry} from 'three/addons/geometries/RoundedBoxGeometry.js';
import {atlas} from './atlas-data.js';

const ids=['W-001','W-002','W-003','W-004','W-007','W-015','W-016','W-020'];
export const studioWorkers=ids.map(id=>atlas.workers.find(w=>w.id===id));
const mats=new Map(),geos=new Map();
function mat(color,roughness=.55,metalness=.05){const key=[color,roughness,metalness].join();if(!mats.has(key))mats.set(key,new T.MeshStandardMaterial({color,roughness,metalness}));return mats.get(key);}
function geo(key,make){if(!geos.has(key))geos.set(key,make());return geos.get(key);}
function mesh(parent,geometry,material,x,y,z){const m=new T.Mesh(geometry,typeof material==='string'?mat(material):material);m.position.set(x,y,z);m.castShadow=true;m.receiveShadow=true;parent.add(m);return m;}
function box(p,w,h,d,x,y,z,c,r=.04){return mesh(p,geo(['b',w,h,d,r].join(),()=>new RoundedBoxGeometry(w,h,d,3,Math.min(r,w/2,h/2,d/2))),c,x,y,z);}
function ball(p,r,x,y,z,c){return mesh(p,geo('s'+r,()=>new T.SphereGeometry(r,24,16)),c,x,y,z);}
function cyl(p,r,h,x,y,z,c,r2=r){return mesh(p,geo(['c',r,h,r2].join(),()=>new T.CylinderGeometry(r,r2,h,24)),c,x,y,z);}
function rod(p,a,b,r,c){const from=new T.Vector3(...a),to=new T.Vector3(...b),m=cyl(p,r,from.distanceTo(to),0,0,0,c);m.position.copy(from).add(to).multiplyScalar(.5);m.quaternion.setFromUnitVectors(new T.Vector3(0,1,0),to.sub(from).normalize());return m;}
function texture(w,h,paint){const c=document.createElement('canvas');c.width=w;c.height=h;paint(c.getContext('2d'),w,h);const t=new T.CanvasTexture(c);t.colorSpace=T.SRGBColorSpace;t.anisotropy=4;return t;}
function panel(p,w,h,x,y,z,paint,bg='#173343'){
 const tex=texture(1024,Math.round(1024*h/w),(c,W,H)=>{c.fillStyle=bg;c.fillRect(0,0,W,H);paint(c,W,H);});
 return mesh(p,new T.PlaneGeometry(w,h),new T.MeshBasicMaterial({map:tex,toneMapped:false}),x,y,z);
}
const palette=['#5bada3','#e0a379','#7baec7','#a393c5','#5c9285','#c39e65','#839caf','#d48d73'];
function text(c,str,x,y,size,color='#e0e9eb',weight=500){c.fillStyle=color;c.font=`${weight} ${size}px "Segoe UI","Malgun Gothic",sans-serif`;c.fillText(str,x,y);}
function plant(p,x,z,size=1){const g=new T.Group();g.position.set(x,0,z);g.scale.setScalar(size);p.add(g);cyl(g,.27,.48,0,.24,0,'#e8decd',.21);cyl(g,.245,.025,0,.49,0,'#625744');for(let i=0;i<7;i++){const a=i*2.4,h=.65+(i%3)*.24;rod(g,[0,.45,0],[Math.cos(a)*.22,h,Math.sin(a)*.22],.018,'#527e59');const l=ball(g,.18,Math.cos(a)*.25,h,Math.sin(a)*.25,i%2?'#689570':'#88a779');l.scale.set(.62,2.2,.85);l.rotation.z=Math.sin(a)*.5;}}
function screen(p,w,accent){
 box(p,1.38,.86,.10,0,1.53,-.45,'#253c48',.07);cyl(p,.045,.4,0,1,-.48,'#7b8b8b');box(p,.54,.05,.32,0,.87,-.42,'#859899');
 panel(p,1.25,.72,0,1.53,-.392,(c,W,H)=>{
  c.fillStyle='#203c4c';c.fillRect(0,0,W,72);text(c,w.id+' / '+w.task,36,48,29,'#e4eeed',650);
  c.fillStyle=accent;c.fillRect(30,103,7,H-133);text(c,'WORKSPACE · DESIGN SAMPLE',56,132,19,'#84a6ad');
  if(w.status==='blocked'){text(c,'REVIEW REQUIRED',60,218,34,'#f7ba83',600);text(c,'재현 자료를 기다리는 중',60,278,29);for(let i=0;i<3;i++){c.fillStyle='#405461';c.fillRect(60,330+i*34,400-i*55,9);}}
  else {const rows=['const task = await collect(source);','validate(task.evidence);','review({ scope: "quality" });','await report.submit(result);'];rows.forEach((s,i)=>{text(c,String(i+1).padStart(2,'0'),56,194+i*51,20,'#65828e');text(c,s,107,194+i*51,23,i%2?'#a5c7e3':'#a5d7c1');});c.fillStyle='#294e56';c.fillRect(55,H-88,W-110,42);text(c,w.status==='waiting'?'WAITING · 선행 작업 대기':'EXAMPLE · 작업 화면 미리보기',76,H-59,22,'#9dd8be');}
 });
 // Portrait-side reference display, intentionally legible only at close range.
 const tablet=new T.Group();tablet.position.set(1.03,1.36,-.26);tablet.rotation.y=-.25;p.add(tablet);box(tablet,.47,.7,.055,0,0,0,'#667d87',.04);panel(tablet,.39,.6,0,0,.03,(c,W,H)=>{text(c,'BRIEF',70,125,60,'#98d8c7',700);for(let i=0;i<9;i++){c.fillStyle=i%3===0?'#81b9b4':'#435e6b';c.fillRect(65,210+i*92,650-i%3*130,30);}});
}
function keyboard(p){
 box(p,.92,.04,.37,0,.892,.24,'#647f85',.035);
 const m=new T.InstancedMesh(geo('key',()=>new RoundedBoxGeometry(.065,.023,.06,1,.008)),mat('#eef0e8'),40),o=new T.Object3D();
 for(let i=0;i<40;i++){o.position.set(-.36+(i%10)*.08,.922,.12+Math.floor(i/10)*.075);o.updateMatrix();m.setMatrixAt(i,o.matrix);}m.castShadow=true;p.add(m);box(p,.2,.035,.3,.68,.91,.23,'#e4e8e0',.07);
}
function robot(p,w,accent){
 const g=new T.Group();g.position.set(0,0,.88);p.add(g);
 // Compact shell with separated neck, joints, feet and replaceable chest panel.
 const body=box(g,.62,.66,.48,0,.92,0,accent,.17);box(g,.44,.28,.045,0,.94,.251,'#dce6df',.07);
 panel(g,.3,.11,0,1,.278,(c,W,H)=>text(c,w.id,45,H*.72,160,'#315367',700),'#e3e9de');
 for(const x of [-.16,.16]){rod(g,[x,.64,0],[x,.34,.2],.10,'#647c83');box(g,.25,.17,.38,x,.27,.24,'#eef0e7',.07);box(g,.25,.045,.39,x,.2,.24,'#617881',.02);}
 cyl(g,.14,.16,0,1.3,0,'#69818a');const head=new T.Group();head.position.set(0,1.65,0);g.add(head);
 box(head,.94,.67,.68,0,0,0,'#f0f0e6',.21);box(head,.80,.45,.12,0,-.02,.303,'#173845',.16);
 const faceMat=new T.MeshStandardMaterial({color:'#203e4e',roughness:.13,metalness:.35});box(head,.72,.36,.04,0,-.02,.372,faceMat,.12);
 const eye=new T.MeshBasicMaterial({color:w.status==='blocked'?'#ffd098':'#96f5e1'}),eyes=[];
 for(const x of [-.19,.19]){const e=box(head,.12,w.status==='waiting'?.055:.15,.025,x,.03,.4,eye,.045);if(w.status==='blocked')e.rotation.z=x<0?-.18:.18;eyes.push(e);}
 box(head,.13,.025,.02,0,-.14,.402,eye,.01);
 for(const x of [-.49,.49]){const ear=cyl(head,.13,.09,x,0,0,'#84999c');ear.rotation.z=Math.PI/2;const pin=cyl(head,.07,.1,x,0,0,accent);pin.rotation.z=Math.PI/2;}
 rod(head,[.28,.30,-.06],[.32,.56,-.06],.023,'#6f8689');const beacon=ball(head,.065,.32,.59,-.06,new T.MeshBasicMaterial({color:w.status==='blocked'?'#efad69':w.status==='waiting'?'#adc2d4':'#60dcb7'}));
 // Arms have shoulder/elbow joints, forearm casings and mitten hands.
 const hands=[];for(const sign of [-1,1]){
  const shoulder=[sign*.4,1.12,0],elbow=[sign*.56,.92,.01],hand=w.status==='waiting'?[sign*.25,.91,.31]:w.status==='blocked'?[sign*.27,1.03,.45]:[sign*.28,.94,-.53];
  ball(g,.13,...shoulder,'#dde5dd');rod(g,shoulder,elbow,.085,accent);ball(g,.085,...elbow,'#54717b');rod(g,elbow,hand,.08,'#e9ece2');hands.push(box(g,.18,.1,.19,...hand,'#e9ece2',.055));
 }
 if(w.status==='blocked'){const tab=box(g,.58,.36,.045,0,1,.46,'#304e5b',.035);tab.rotation.x=-.3;panel(g,.47,.25,0,1,.49,(c,W,H)=>{text(c,'!',W*.43,H*.64,220,'#f8c78d',700);});}
 // Chair and caster base.
 box(g,.63,.10,.54,0,.54,-.03,'#607c83',.09);box(g,.65,.6,.12,0,.93,-.31,'#698890',.09);cyl(g,.045,.4,0,.26,-.03,'#819293');
 for(let i=0;i<5;i++){const a=i*Math.PI*2/5;rod(g,[0,.1,0],[Math.cos(a)*.39,.1,Math.sin(a)*.39],.035,'#87989a');const wheel=cyl(g,.065,.08,Math.cos(a)*.39,.08,Math.sin(a)*.39,'#4b626d');wheel.rotation.z=Math.PI/2;}
 return {group:g,head,eyes,hands,beacon,body};
}
function desk(p,w,accent,index){
 box(p,3.25,.12,1.56,0,.80,0,'#b99876',.10);box(p,3.23,.05,1.54,0,.884,0,'#f0eee4',.08);
 for(const x of [-1.30,1.30]){box(p,.075,.73,1.22,x,.40,0,'#a5b5b3',.025);box(p,.46,.045,1.32,x,.055,0,'#95a6a5',.02);}
 box(p,.40,.53,.95,-1.14,.48,0,'#d2dbd4',.04);for(const y of [.36,.55,.71])box(p,.26,.018,.03,-1.14,y,.49,'#849897',.005);
 screen(p,w,accent);keyboard(p);
 const pad=box(p,.52,.02,.56,-.97,.923,.12,accent,.025);pad.rotation.y=-.15;
 for(let i=0;i<3;i++){const paper=box(p,.41,.01,.46,-.95,.94+i*.012,.10,'#faf5df',.005);paper.rotation.y=-.15+i*.04;}
 const mug=cyl(p,.105,.2,1.33,1.01,.25,index%2?'#d7a47c':'#81b3a2');cyl(p,.086,.008,1.33,1.115,.25,'#755a42');const handle=mesh(p,new T.TorusGeometry(.08,.025,8,16),'#d9dccc',1.45,1.02,.25);
 rod(p,[-1.38,.9,-.5],[-1.38,1.55,-.5],.025,'#637d83');rod(p,[-1.38,1.55,-.5],[-1.08,1.72,-.28],.025,'#637d83');const lamp=box(p,.42,.06,.19,-1.08,1.7,-.28,'#d8dfd4',.03);lamp.rotation.z=-.15;box(p,.32,.012,.12,-1.08,1.663,-.28,new T.MeshBasicMaterial({color:'#ffe3ad'}),.015);
 // Back acoustic divider and individual station plate.
 box(p,3.15,.26,.065,0,1.02,-.76,'#b8cbc4',.045);panel(p,.7,.18,-1.08,1.025,-.72,(c,W,H)=>text(c,w.id,60,H*.73,115,'#294e58',700),'#e8ede4');
}
export {box,cyl,rod,panel,text,plant};
export function buildStudio(scene,options={}){
 const roomWorkers=options.workers||studioWorkers,title=options.title||'기획 · 리서치 스튜디오';
 const root=new T.Group();scene.add(root);const workers=[],picks=[];
 const floorTex=texture(512,512,(c,W,H)=>{c.fillStyle='#ebe8dc';c.fillRect(0,0,W,H);let s=1234;const rand=()=>{s=(s*1664525+1013904223)>>>0;return s/4294967296;};for(let i=0;i<2200;i++){c.fillStyle=['#cecbbf','#dcd9cb','#f4f1e7'][i%3];c.fillRect(rand()*W,rand()*H,1+rand()*2,1+rand()*2);}});floorTex.wrapS=floorTex.wrapT=T.RepeatWrapping;floorTex.repeat.set(6,5);
 box(root,21,.4,15,0,-.26,0,'#9daba7',.20);box(root,20.8,.15,14.8,0,-.03,0,new T.MeshStandardMaterial({map:floorTex,roughness:.85}),.12);
 // Four warm quiet pods, rather than endless identical rows.
 for(const x of [-4.4,4.4])for(const z of [-2.8,3])box(root,8.25,.025,4.1,x,.065,z+.45,(x+z)>0?'#cbded6':'#d8dfd5',.22);
 box(root,20.8,2.9,.18,0,1.38,-7.1,'#dfe5dc',.07);
 for(let i=0;i<16;i++)box(root,.055,2.85,.06,-9.5+i*.25,1.4,-6.98,'#b8a183',.01);
 // Back identity panel and practical task board.
 panel(root,4.6,1.3,-5.8,1.9,-6.88,(c,W,H)=>{text(c,'MAKERS LAB',35,85,58,'#315765',700);text(c,title,35,157,36,'#617a7b');text(c,'작은 생각을 실제 작업으로.',35,226,25,'#83938b');},'#dfe5dc');
 box(root,5.9,1.9,.10,1.7,1.65,-6.91,'#9baea8',.06);
 panel(root,5.65,1.66,1.7,1.65,-6.848,(c,W,H)=>{text(c,'TEAM WORKBOARD',30,52,27,'#45656d',700);const cols=['조사','설계','리뷰'];for(let i=0;i<3;i++){text(c,cols[i],35+i*335,106,30,'#3d606a',600);for(let j=0;j<2;j++){c.fillStyle=['#c4dfd3','#ead4b5','#d1daeb'][i];c.fillRect(30+i*335,132+j*75,295,61);text(c,[['자료 수집','요구사항 정리'],['사용 흐름','실험 설계'],['근거 확인','팀장 보고']][i][j],46+i*335,170+j*75,24,'#48606a');}}},'#f1efe5');
 box(root,3.1,.73,1.0,7.6,.40,-6.25,'#bd9d78',.08);box(root,3.2,.07,1.1,7.6,.80,-6.25,'#eee9dd',.035);
 for(let i=0;i<5;i++)box(root,.12,.29,.37,6.5+i*.15,.98,-6.3,['#5b8d8b','#b88d72','#95aabb'][i%3],.01);
 plant(root,8.8,-6.25,.65);plant(root,-9.2,5.8,1.6);plant(root,9.3,5.8,1.7);plant(root,-9.2,-5.5,1.5);
 for(const x of [-9.7,9.7]){box(root,.06,.025,11,x,.075,0,new T.MeshBasicMaterial({color:'#d7b77d'}),.01);}
 for(let i=0;i<roomWorkers.length;i++){
  const w=roomWorkers[i],accent=palette[i%palette.length],station=new T.Group();station.position.set(-6.6+(i%4)*4.4,0,i<4?-2.8:3);root.add(station);
  if(options.leaderSeat&&w.role==='팀장'){
   station.position.set(-6.6,0,-4.6);
   box(root,4.1,.04,4.0,-6.6,.07,-4.15,'#dac49d',.15);
   box(root,.09,1.0,3.8,-4.48,.55,-4.15,'#aec5bb');
   panel(root,2.3,.42,-6.6,.11,-2.2,(c,W,H)=>text(c,'TEAM LEAD / 팀장',30,H*.72,58,'#735e3e',700),'#efe3c9').rotation.x=-Math.PI/2;
  }
  desk(station,w,accent,i);const bot=robot(station,w,accent);bot.head.rotation.y=(i%2?-.12:.12);
  const hit=mesh(station,new T.BoxGeometry(1.45,2.55,1.75),new T.MeshBasicMaterial({visible:false}),0,1.12,.7);hit.userData.workerId=w.id;picks.push(hit);
  const ring=mesh(station,new T.RingGeometry(.8,.85,64),new T.MeshBasicMaterial({color:'#479d94',side:T.DoubleSide}),0,.095,.88);ring.rotation.x=-Math.PI/2;ring.visible=false;
  workers.push({...bot,data:w,station,ring,accent,point:new T.Vector3(station.position.x,1.4,station.position.z+.88)});
 }
 // Wayfinding at the entrance, with no invented operational claims.
 panel(root,4.8,.45,0,.05,6.8,(c,W,H)=>text(c,'01 / RESEARCH STUDIO',30,H*.72,52,'#537479',650),'#e5e4d7').rotation.x=-Math.PI/2;
 return {root,workers,picks};
}
