import * as T from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {RoomEnvironment} from 'three/addons/environments/RoomEnvironment.js';
import {buildHeadquarters} from './architecture.js';

const $=s=>document.querySelector(s), panel=$('#panel'), canvas=$('#scene');
let state=null,hq=null,selectedTeam=null,selectedWorker=null,selectedProject=null,lastSuccess=null,polling=false;
let reduced=matchMedia('(prefers-reduced-motion: reduce)').matches, transition=null;
const scene=new T.Scene();scene.background=new T.Color('#8c9c8e');scene.fog=new T.Fog('#8c9c8e',70,170);
const renderer=new T.WebGLRenderer({canvas,antialias:true,alpha:false,powerPreference:'high-performance'});
renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));renderer.shadowMap.enabled=true;renderer.shadowMap.type=T.PCFSoftShadowMap;
renderer.toneMapping=T.ACESFilmicToneMapping;renderer.toneMappingExposure=.92;renderer.outputColorSpace=T.SRGBColorSpace;
const camera=new T.PerspectiveCamera(36,1,.1,200);
const controls=new OrbitControls(camera,canvas);controls.enableDamping=true;controls.dampingFactor=.085;controls.minDistance=3;controls.maxDistance=76;
controls.maxPolarAngle=Math.PI*.48;controls.minPolarAngle=.15;controls.mouseButtons.LEFT=T.MOUSE.PAN;controls.mouseButtons.RIGHT=T.MOUSE.ROTATE;
controls.touches.ONE=T.TOUCH.PAN;controls.touches.TWO=T.TOUCH.DOLLY_PAN;
controls.addEventListener('start',()=>{transition=null;});
const pmrem=new T.PMREMGenerator(renderer), environment=new RoomEnvironment();
scene.environment=pmrem.fromScene(environment,.04).texture;scene.environmentIntensity=.55;environment.dispose();pmrem.dispose();
scene.add(new T.HemisphereLight('#fff3d8','#688576',.85));
const sun=new T.DirectionalLight('#ffe4ba',2.6);sun.position.set(-13,26,17);sun.castShadow=true;
sun.shadow.mapSize.set(2048,2048);Object.assign(sun.shadow.camera,{left:-22,right:22,top:23,bottom:-15,near:1,far:80});sun.shadow.normalBias=.04;sun.shadow.bias=-.0002;scene.add(sun);
const fill=new T.DirectionalLight('#c7dfdc',.75);fill.position.set(16,15,-4);scene.add(fill);
const ground=new T.Mesh(new T.PlaneGeometry(220,220),new T.MeshStandardMaterial({color:'#8c9c8e',roughness:1}));ground.rotation.x=-Math.PI/2;ground.position.y=-1.13;ground.receiveShadow=true;scene.add(ground);
const viewport=()=>canvas.getBoundingClientRect();
function homeCamera(){const narrow=viewport().width<600;return {position:new T.Vector3(narrow?25:24,narrow?22:21,narrow?43:37),target:new T.Vector3(narrow?-.8:-1,6,0)};}
function moveCamera(position,target){
  if(reduced){camera.position.copy(position);controls.target.copy(target);controls.update();transition=null;return;}
  transition={start:performance.now(),from:camera.position.clone(),to:position,fromTarget:controls.target.clone(),toTarget:target};
}
function resize(){const r=viewport();renderer.setSize(r.width,r.height,false);camera.aspect=r.width/r.height;camera.updateProjectionMatrix();}
new ResizeObserver(resize).observe(canvas.parentElement);resize();
const initial=homeCamera();camera.position.copy(initial.position);controls.target.copy(initial.target);controls.update();
function el(tag,text,cls){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;}
function add(tag,text,cls){const e=el(tag,text,cls);panel.append(e);return e;}
function button(text,fn,cls){const b=el('button',text,cls);b.type='button';b.addEventListener('click',fn);return b;}
function teamOf(id){return state.teams.find(t=>t.id===id);}
function roleName(id){return state.roles.find(r=>r.id===id)?.name||id;}
function projectsFor(teamId,role=null){return state.projects.filter(p=>p.company_id==='makers'&&p.team_id===teamId&&(!role||p.current_assignee===role));}
function markSelection(){
  document.querySelectorAll('[data-team]').forEach(b=>{const yes=b.dataset.team===selectedTeam;b.classList.toggle('selected',yes);b.setAttribute('aria-pressed',String(yes));});
  hq.workers.forEach(w=>w.ring.visible=w===selectedWorker);
  $('#crumb').textContent=selectedTeam?`${teamOf(selectedTeam).name}${selectedWorker?' / '+selectedWorker.title:''}`:'외부 전경';
}
function selectTeam(id){
  selectedTeam=id;selectedWorker=null;selectedProject=null;
  const floor=hq.floors.find(f=>f.team.id===id);hq.floors.forEach(f=>f.group.visible=f.index<=floor.index);hq.roof.visible=false;
  const target=new T.Vector3(.3,floor.y+1,0);
  moveCamera(target.clone().add(new T.Vector3(7,6,viewport().width<600?18:14)),target);
  markSelection();renderPanel();
}
function selectWorker(w){
  if(selectedTeam!==w.teamId)selectTeam(w.teamId);
  selectedWorker=w;selectedProject=null;
  const target=w.point.clone().add(new T.Vector3(0,.9,0));
  moveCamera(target.clone().add(new T.Vector3(2.4,2.05,4.7)),target);markSelection();renderPanel();
}
function goHome(){if(!hq)return;selectedTeam=selectedWorker=selectedProject=null;hq.floors.forEach(f=>f.group.visible=true);hq.roof.visible=true;const h=homeCamera();moveCamera(h.position,h.target);markSelection();renderPanel();}
function heading(kicker,title,description){add('div',kicker,'panel-kicker');add('h2',title,'panel-title');add('p',description,'panel-description');}
function projectRows(projects){
  if(!projects.length){add('p','이 위치에 연결된 저장 업무가 없습니다.','note');return;}
  for(const p of projects){
    const b=button('',()=>showProject(p.id),'project-row');b.dataset.project=p.id;
    const wrap=el('span');wrap.append(el('b',p.title),el('small',`${p.blocked?'차단 · ':''}${state.stages.find(s=>s.id===p.stage)?.label||p.stage} · ${roleName(p.current_assignee||'미배정')}`));b.append(wrap);panel.append(b);
  }
}
function renderPanel(){
  panel.replaceChildren();if(!state)return;
  if(selectedWorker){renderWorker();return;}
  if(selectedTeam){
    const t=teamOf(selectedTeam);panel.append(button('← 사옥 전체',goHome,'back-link'));
    heading('DEPARTMENT',t.name,t.description+' · 로봇을 선택해 역할과 저장된 업무를 확인하세요.');
    add('div','좌석과 책임 역할','section-label');
    for(const w of hq.workers.filter(w=>w.teamId===selectedTeam&&w.assignedSeat)){
      const b=button('',()=>selectWorker(w),'worker-row');b.dataset.worker=`${w.teamId}-${w.index}`;
      b.append(el('span',undefined,'robot-icon'));const s=el('span');s.append(el('b',`${roleName(w.role)} · ${w.title}`),el('small',`${projectsFor(w.teamId,w.role).length}건 저장 배정 · 실행 미연결`));b.append(s);panel.append(b);
    }
    add('div','이 부서의 저장 업무','section-label');projectRows(projectsFor(selectedTeam));
    add('p','로봇과 좌석은 공간 배치 예시입니다. 실제 직원·세션 수를 뜻하지 않습니다.','note');return;
  }
  heading('MAKERS LAB / HEADQUARTERS','메이커스랩 사옥','브랜드를 만들고, 제품을 돌보고, 더 나은 결과를 만드는 사람들이 만나는 곳.');
  const card=add('div',undefined,'brand-card');card.append(el('small','첫 번째 브랜드'),el('h3',state.companies.find(c=>c.id==='makers').products[0].name),el('p','개발부터 고객 지원까지. 다섯 부서가 하나의 제품을 함께 운영합니다.'),el('span','제품 내부 공장 · 구조 설계 중','badge'));
  add('div','부서를 선택해 들어가세요','section-label');
  for(const f of [...hq.floors].reverse()){
    const b=button('',()=>selectTeam(f.team.id),'team-row');b.dataset.team=f.team.id;
    const dot=el('span',undefined,'team-dot');dot.style.setProperty('--accent',f.color);const text=el('span');text.append(el('b',f.team.name),el('small',f.team.description));b.append(dot,text,el('span',`${f.index+1}F`));panel.append(b);
  }
  add('p','공간·로봇은 디자인 제안입니다. 옆에서 조회하는 업무는 이 PC의 로컬 저장 기록이며, AI 자동 실행은 아직 연결되지 않았습니다.','note');
}
function renderWorker(){
  const w=selectedWorker;panel.append(button('← '+teamOf(w.teamId).name,()=>selectTeam(w.teamId),'back-link'));
  const p=add('div',undefined,'worker-portrait');p.append(el('span',undefined,'robot-icon'));const title=el('span');title.append(el('strong',roleName(w.role)),el('small',w.title+' · 배치 예시'));p.append(title);
  const dl=add('dl',undefined,'data-list');
  for(const [name,value] of [['소속',teamOf(w.teamId).name],['배정 역할',state.roles.find(r=>r.id===w.role)?.role||w.role],['실제 세션','미연결'],['현재 실행','관측하지 않음']])dl.append(el('dt',name),el('dd',value));
  add('div',w.assignedSeat?'이 역할의 저장 배정':'확장 좌석','section-label');
  if(w.assignedSeat)projectRows(projectsFor(w.teamId,w.role));else add('p','추가 워커가 배치될 공간을 검토하기 위한 좌석입니다. 업무와 연결되지 않았습니다.','note');
  const link=add('a','업무 원장 열기 ↗','primary-link');link.href='/static/control.html';link.target='_blank';link.rel='noopener';
  add('p','지시·중단은 실제 실행 연결 단계에서 제공됩니다. 현재 저장 원장의 차단 상태를 실행 중인 프로세스 중단으로 표시하지 않습니다.','note');
}
let eventRequest=0;
async function showProject(id){
  const p=state.projects.find(p=>p.id===id&&p.company_id==='makers');if(!p)return;
  selectedProject=id;const token=++eventRequest;panel.replaceChildren();panel.append(button('← 역할 / 부서로 돌아가기',()=>{selectedProject=null;renderPanel();},'back-link'));
  heading('SAVED WORK',p.title,p.description||'상세 지시가 등록되지 않았습니다.');
  const dl=add('dl',undefined,'data-list');for(const [k,v] of [['상태',p.blocked?'차단':state.stages.find(s=>s.id===p.stage)?.label],['책임자',p.owner],['담당 역할',roleName(p.current_assignee||'미배정')],['갱신',new Date(p.updated_at).toLocaleString('ko-KR')]])dl.append(el('dt',k),el('dd',v));
  add('div','저장된 사건 · 최신 50건','section-label');const events=add('div','조회 중…');
  try{const r=await fetch(`/api/projects/${encodeURIComponent(id)}/events?limit=50`,{signal:AbortSignal.timeout(8000)});if(!r.ok)throw Error();const items=await r.json();if(token!==eventRequest||selectedProject!==id)return;events.replaceChildren();if(!items.length)events.append(el('p','저장된 사건이 없습니다.','note'));for(const ev of items){const row=el('div',undefined,'event');row.append(el('small',new Date(ev.created_at).toLocaleString('ko-KR')),el('div',ev.message));if(ev.evidence)row.append(el('div','근거: '+ev.evidence));events.append(row);}}
  catch{if(token===eventRequest&&selectedProject===id)events.textContent='사건을 조회하지 못했습니다. 업무를 다시 선택해 주세요.';}
}
function createNavigation(){
  for(const f of [...hq.floors].reverse()){
    const b=button('',()=>selectTeam(f.team.id));b.dataset.team=f.team.id;b.append(el('b',`${f.index+1}F`),document.createTextNode(f.team.name));$('#floors').append(b);
    const mini=button('',()=>selectTeam(f.team.id));mini.dataset.team=f.team.id;mini.setAttribute('aria-label',f.team.name+' 진입');mini.title=f.team.name;$('#mini-floors').append(mini);
  }
}
async function refresh(){
  if(polling||document.hidden)return;polling=true;
  try{
    const res=await fetch('/api/state',{signal:AbortSignal.timeout(8000)});if(!res.ok)throw Error('state');const next=await res.json();
    if(!Array.isArray(next.teams)||!Array.isArray(next.projects)||!Array.isArray(next.companies))throw Error('shape');
    const changed=JSON.stringify(next)!==JSON.stringify(state);state=next;lastSuccess=new Date();
    $('#connection').textContent='로컬 기록 · '+lastSuccess.toLocaleTimeString('ko-KR');
    if(!hq){await document.fonts.ready;hq=buildHeadquarters(scene,state.teams,state.companies.find(c=>c.id==='makers'));createNavigation();renderPanel();$('#loading').hidden=true;document.body.dataset.ready='true';}
    else if(changed){if(selectedProject)await showProject(selectedProject);else renderPanel();}
  }catch{
    $('#connection').textContent='조회 실패'+(lastSuccess?' · 마지막 '+lastSuccess.toLocaleTimeString('ko-KR'):'');
    if(!hq){$('#loading').replaceChildren(document.createTextNode('업무 구조를 불러오지 못했습니다. '),button('다시 연결',refresh));}
  }finally{polling=false;}
}
$('#home').onclick=goHome;$('#reset').onclick=()=>selectedTeam?selectTeam(selectedTeam):goHome();
$('#pan').onclick=()=>setMode(false);$('#orbit').onclick=()=>setMode(true);
function setMode(orbit){controls.mouseButtons.LEFT=orbit?T.MOUSE.ROTATE:T.MOUSE.PAN;controls.touches.ONE=orbit?T.TOUCH.ROTATE:T.TOUCH.PAN;$('#pan').setAttribute('aria-pressed',String(!orbit));$('#orbit').setAttribute('aria-pressed',String(orbit));}
function zoom(f){const offset=camera.position.clone().sub(controls.target),length=T.MathUtils.clamp(offset.length()*f,controls.minDistance,controls.maxDistance);transition=null;camera.position.copy(controls.target).add(offset.setLength(length));controls.update();}
$('#zoom-in').onclick=()=>zoom(.8);$('#zoom-out').onclick=()=>zoom(1.25);
function updateMotion(){controls.enableDamping=!reduced;$('#motion').setAttribute('aria-pressed',String(reduced));if(reduced&&transition){camera.position.copy(transition.to);controls.target.copy(transition.toTarget);transition=null;controls.update();}}
$('#motion').onclick=()=>{reduced=!reduced;updateMotion();};updateMotion();
matchMedia('(prefers-reduced-motion: reduce)').addEventListener('change',e=>{reduced=e.matches;updateMotion();});
const pointers=new Set();let press=null,gesture=false;const ray=new T.Raycaster();
canvas.addEventListener('pointerdown',e=>{pointers.add(e.pointerId);if(pointers.size>1)gesture=true;if(pointers.size===1){press={x:e.clientX,y:e.clientY,id:e.pointerId,time:performance.now(),button:e.button};gesture=false;}});
canvas.addEventListener('pointermove',e=>{if(press&&Math.hypot(e.clientX-press.x,e.clientY-press.y)>7)gesture=true;});
canvas.addEventListener('pointercancel',e=>{pointers.delete(e.pointerId);press=null;gesture=true;});
canvas.addEventListener('pointerup',e=>{
  const pick=press&&press.id===e.pointerId&&!gesture&&press.button===0&&performance.now()-press.time<650;pointers.delete(e.pointerId);if(!pointers.size)press=null;
  if(!pick||!hq)return;const r=viewport();ray.setFromCamera(new T.Vector2((e.clientX-r.left)/r.width*2-1,-(e.clientY-r.top)/r.height*2+1),camera);
  const visible=o=>{while(o){if(!o.visible)return false;o=o.parent;}return true;};
  // Team entry takes priority at whole-building scale; individual bots only inside a department.
  const candidates=selectedTeam?hq.picks.filter(o=>visible(o)):[...hq.floors.map(f=>f.plane),...hq.picks.filter(p=>p.userData.kind==='team')];
  const hit=ray.intersectObjects(candidates,false)[0];if(!hit)return;const d=hit.object.userData;
  if(d.kind==='worker')selectWorker(d.worker);else selectTeam(d.teamId);
});
canvas.addEventListener('keydown',e=>{if(e.key==='Escape'){goHome();e.preventDefault();}if(e.key==='+'||e.key==='=')zoom(.85);if(e.key==='-')zoom(1.15);});
let previous=performance.now();const frameTimes=[];
renderer.setAnimationLoop(now=>{
  if(document.hidden)return;
  if(transition){const t=Math.min(1,(now-transition.start)/1050),s=t*t*(3-2*t);camera.position.lerpVectors(transition.from,transition.to,s);controls.target.lerpVectors(transition.fromTarget,transition.toTarget,s);if(t===1)transition=null;}
  controls.update();renderer.render(scene,camera);
  if(frameTimes.length>180)frameTimes.shift();frameTimes.push(now-previous);previous=now;
});
// Read-only diagnostics used by browser verification, no mutation or commands.
window.hqDiagnostics=()=>({ready:!!hq,team:selectedTeam,worker:selectedWorker?`${selectedWorker.teamId}-${selectedWorker.index}`:null,project:selectedProject,visibleFloors:hq?.floors.filter(f=>f.group.visible).length,drawCalls:renderer.info.render.calls,triangles:renderer.info.render.triangles,frameMs:frameTimes.reduce((a,b)=>a+b,0)/frameTimes.length,camera:camera.position.toArray(),target:controls.target.toArray(),reduced,workerPoints:hq?.workers.filter(w=>!selectedTeam||w.teamId===selectedTeam).map(w=>{const v=w.point.clone().add(new T.Vector3(0,1,0)).project(camera),r=viewport();return {id:`${w.teamId}-${w.index}`,x:r.left+(v.x+1)*r.width/2,y:r.top+(1-v.y)*r.height/2};})});
await refresh();setInterval(refresh,5000);document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
