import * as T from 'three';
import {buildStudio,studioWorkers,box,cyl,rod,panel,text,plant} from './studio-art.js';
import {atlas} from './atlas-data.js';

export const roomSpecs=[
 {id:'plan',title:'기획·리서치',subtitle:'01 / RESEARCH',x:-12,z:-10,color:'#64af9e',workers:studioWorkers},
 {id:'dev',title:'제품 개발',subtitle:'02 / DEVELOPMENT',x:12,z:-10,color:'#76aaca',workers:atlas.workers.slice(32,36)},
 {id:'qa',title:'독립 검수',subtitle:'03 / QUALITY',x:12,z:10,color:'#cd9a70',workers:atlas.workers.slice(136,140)},
];
function floorSign(root,label,x,z,width=8,bg='#e3e9dc'){
 panel(root,width,1.15,x,.1,z,(c,W,H)=>text(c,label,30,H*.7,72,'#315967',650),bg).rotation.x=-Math.PI/2;
}
export function buildCampus(scene){
 const root=new T.Group();scene.add(root);const picks=[];
 cyl(root,31,.7,0,-.6,0,'#b6c9ba');cyl(root,30.4,.13,0,-.18,0,'#e4e8d9');
 const ring=new T.Mesh(new T.RingGeometry(18,21,100),new T.MeshStandardMaterial({color:'#b9cfc5',side:T.DoubleSide}));ring.rotation.x=-Math.PI/2;ring.position.y=-.1;root.add(ring);
 cyl(root,7,.2,0,0,0,'#dac7a4');cyl(root,6.65,.15,0,.13,0,'#eff0e5');
 cyl(root,4.4,5.4,0,2.9,0,'#315a64');cyl(root,4.85,.3,0,5.7,0,'#d6e2d8');cyl(root,4.85,.3,0,3.1,0,'#d6e2d8');
 for(let i=0;i<20;i++){const a=i*Math.PI/10;rod(root,[Math.sin(a)*4.5,.4,Math.cos(a)*4.5],[Math.sin(a)*4.5,5.5,Math.cos(a)*4.5],.045,'#8aafa9');}
 panel(root,6,1.1,0,4.25,4.6,(c,W,H)=>text(c,'MAKERS LAB',36,H*.7,105,'#e8f4e5',700));
 floorSign(root,'본사 · 통합 관제',0,8,8);
 const specs=[{id:'shortem',x:-15,z:10,name:'SHORTEM MAKER',ko:'숏템메이커',color:'#6eb0a0'},{id:'stock',x:15,z:10,name:'STOCK BRAIN',ko:'스탁브레인',color:'#789cbf'}];
 for(const s of specs){const g=new T.Group();g.position.set(s.x,0,s.z);root.add(g);
  box(g,13,.45,10,0,0,0,'#c0cdc1',.3);box(g,11,4,7,0,2.2,0,'#eaece1',.2);
  box(g,10.5,2.9,.13,0,2.3,3.56,'#355864');for(let i=-4;i<=4;i+=2)box(g,.07,3,.15,i,2.3,3.68,'#bbd2cb');
  box(g,11.6,.4,7.6,0,4.4,0,s.color,.16);box(g,10.7,.15,6.8,0,4.68,0,'#d2dcc5',.1);
  for(const x of [-4.3,4.3])plant(g,x,-1.9,1.3);
  box(g,4.9,.9,.2,0,3.5,3.85,s.color,.06);panel(g,4.7,.72,0,3.5,3.965,(c,W,H)=>text(c,s.name,32,H*.7,77,'#f3f5ea',750),s.color);
  box(g,2,2.5,.2,0,1.4,3.85,'#183c48');box(g,2.8,.15,1.5,0,.25,4.2,'#eddfbd');
  for(const x of [-5.6,5.6]){rod(g,[x,.1,4.4],[x,2,4.4],.045,'#627e7d');cyl(g,.14,.15,x,2.05,4.4,'#ffe1a4');}
  floorSign(g,s.ko,0,6.2,9);
  const hit=new T.Mesh(new T.BoxGeometry(12,5,9),new T.MeshBasicMaterial({visible:false}));hit.position.y=2.5;hit.userData.building=s.id;g.add(hit);picks.push(hit);
 }
 for(let i=0;i<24;i++){const a=i*Math.PI/12,x=Math.sin(a)*27,z=Math.cos(a)*27;if(z>21)continue;plant(root,x,z,1.5+(i%3)*.25);}
 for(const x of [-15,15]){box(root,4,.04,8,x,-.05,18,'#d9ccb1',.2);}
 floorSign(root,'MAKERS LAB / PROGRAM UNIVERSE',0,25,17);
 floorSign(root,'확장 부지',-16,-17,8);floorSign(root,'확장 부지',16,-17,8);
 return {root,picks};
}
export function buildInterior(scene){
 const root=new T.Group();scene.add(root);const workers=[],picks=[];
 box(root,48,.25,39,0,-.6,0,'#b6c8c0',.4);
 box(root,3,.15,38,0,-.2,0,'#d2c1a2',.1);box(root,47,.15,4.5,0,-.2,0,'#d2c1a2',.1);
 for(const spec of roomSpecs){const room=buildStudio(root,{workers:spec.workers,title:spec.title,leaderSeat:true});room.root.position.set(spec.x,0,spec.z);root.updateMatrixWorld(true);
  room.workers.forEach(w=>{w.point=room.root.localToWorld(w.point);w.room=spec.id;workers.push(w);});picks.push(...room.picks);
  floorSign(root,spec.subtitle,spec.x,spec.z+8.2,10);
 }
 // A reserved bay is explicit: it contains no invented workers or running services.
 box(root,21,.3,15,-12,-.22,10,'#dce1d0',.12);
 floorSign(root,'04 / 다음 팀 확장 부지',-12,7.5,14);
 floorSign(root,'기존 방과 자리는 그대로 유지',-12,11,15,'#dce1d0');
 for(const x of [-21,-3])for(const z of [4,16])plant(root,x,z,1.4);
 box(root,5.5,2.3,.22,-12,1.1,3,'#a9beb4');panel(root,5.1,1.8,-12,1.2,3.13,(c,W,H)=>{text(c,'NEXT SPACE',40,100,68,'#244f5a',700);text(c,'2F · B1 / 설계 예정',40,205,47,'#527677');text(c,'이 검토본은 1층만 이동합니다',40,295,33,'#527677');},'#e7eadb');
 floorSign(root,'↑ 숏템메이커 1F / TEAM WORKSPACES',0,20.5,22);
 root.visible=false;return {root,workers,picks};
}
