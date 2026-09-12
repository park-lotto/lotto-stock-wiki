import {atlas,searchWorkers,counts,statusNames} from './atlas-data.js';
import {createAtlas} from './atlas-scene.js';
const $=s=>document.querySelector(s),teamOf=id=>atlas.teams.find(t=>t.id===id),projectOf=id=>atlas.projects.find(p=>p.id===id);
function node(tag,text,cls){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;}
function button(text,fn,id,cls){const e=node('button',text,cls);e.type='button';if(id)e.id=id;e.onclick=fn;return e;}
function badge(w){return node('span',statusNames[w.status],`state ${w.status}`);}
let selected=null,project=null,visible=new Set(atlas.workers.map(w=>w.id));
const workerLabels=atlas.workers.map(w=>{const e=node('div',undefined,'worker-label');e.append(node('strong',w.id),node('small',w.task));$('#labels').append(e);return e;});
const teamLabels=atlas.teams.map(t=>{const e=node('div',undefined,'team-label'),c=counts(atlas.workers.filter(w=>w.team===t.id));e.style.setProperty('--accent',t.color);e.append(node('b',t.name),node('small',`배치 ${c.total} · 실행 ${c.running} · 대기 ${c.waiting} · 막힘 ${c.blocked}`));$('#labels').append(e);return e;});
let world;
const mini=$('#minimap'),ctx=mini.getContext('2d');
function frame({project:pos,zoom,target}){
 $('#zoom').textContent=Math.round(zoom/1.4*100)+'%';
 atlas.teams.forEach((t,i)=>{const p=pos(t.x+t.width/2,t.z+1,0),e=teamLabels[i];e.style.left=p.x+'px';e.style.top=p.y+'px';e.hidden=!p.visible;});
 atlas.workers.forEach((w,i)=>{const e=workerLabels[i],p=pos(w.x,w.z+.8,0);e.hidden=!p.visible||zoom<1.15&&selected?.id!==w.id;if(!e.hidden){e.style.left=p.x+'px';e.style.top=p.y+'px';e.classList.toggle('selected',selected?.id===w.id);e.classList.toggle('dim',!visible.has(w.id));e.lastChild.hidden=zoom<2.5&&selected?.id!==w.id;}});
 ctx.clearRect(0,0,180,120);for(const t of atlas.teams){ctx.fillStyle='#25384d';ctx.fillRect(t.x*2+7,t.z*2+5,t.width*2,t.height*2);}
 for(const w of atlas.workers){ctx.fillStyle=selected?.id===w.id?'#fff':!visible.has(w.id)?'#334257':w.status==='blocked'?'#eeae67':'#79abbc';ctx.fillRect(w.x*2+6,w.z*2+4,2,2);}
 ctx.strokeStyle='#b7eafa';ctx.strokeRect(target.x*2+7-18/zoom,target.z*2+5-12/zoom,36/zoom,24/zoom);
}
try{world=createAtlas($('#scene'),selectWorker,frame);}catch(error){const e=node('div','3D 화면을 시작하지 못했습니다. WebGL 사용 가능 여부를 확인해 주세요. '+error.message,'load-error');$('main').append(e);throw error;}
const totals=counts(atlas.workers);for(const k of ['total','running','waiting','blocked'])$('#'+k).textContent=totals[k];$('#project-count').textContent=atlas.projects.length;
for(const t of atlas.teams){const o=node('option',`${t.name} · ${t.size}`);o.value=t.id;$('#team').append(o);}
function updateSearch(){
 project=null;selected=null;$('#detail').hidden=true;$('#log-pane').hidden=true;world.route([]);
 const found=searchWorkers($('#search').value,{team:$('#team').value,status:$('#status').value});visible=new Set(found.map(w=>w.id));world.highlight([...visible]);$('#matches').textContent=found.length;
 const frag=document.createDocumentFragment();for(const w of found){const b=button('',()=>selectWorker(w),null,'result');b.dataset.result=w.id;const top=node('span');top.append(node('b',w.id+' · '+w.task),badge(w));b.append(top,node('small',`${teamOf(w.team).name} / ${projectOf(w.project).name}`));frag.append(b);}if(!found.length)frag.append(node('p','일치하는 업무가 없습니다. 검색어나 필터를 바꿔보세요.','empty'));$('#results').replaceChildren(frag);
}
function panelHeader(kicker,title){const p=$('#detail');p.replaceChildren();p.hidden=false;const h=node('div',undefined,'section-head');h.append(node('span',kicker,'kicker'),button('×',closeDetail,'close-detail'));p.append(h,node('h2',title));return p;}
function closeDetail(){updateSearch();}
function selectWorker(w){
 $('#log-pane').hidden=true;
 selected=w;project=null;visible.add(w.id);world.highlight([...visible],w.id);world.route([]);world.focus(w.x,w.z+(innerWidth<700?7:0),3.8);
 if(innerWidth<700)$('#finder').hidden=true;
 const t=teamOf(w.team),p=panelHeader('예시 워커 · '+w.role,w.id);p.append(badge(w),node('p',w.task));
 const dl=node('dl',undefined,'detail-grid');for(const [label,value] of [['위치',`숏템메이커 / ${t.name}`],['프로젝트',projectOf(w.project).name],['보고 대상',w.reportTo],['실행 ID',w.run]])dl.append(node('dt',label),node('dd',value));p.append(dl,node('p',w.reason,w.status==='blocked'?'reason':''));
 const actions=node('div',undefined,'actions');actions.append(button('프로젝트 함께 보기',()=>selectProject(w.project),'follow-project','primary'),button('예시 로그',()=>showLogs(w),'logs'));p.append(actions,node('p','실제 실행기 미연결 · 지시·중단은 이 검토본에서 수행하지 않습니다.'));
 $('#notice').textContent=`${w.id} 선택 · ${t.name} · ${w.task} · ${statusNames[w.status]} (예시)`;
}
function selectProject(id){
 $('#log-pane').hidden=true;
 project=projectOf(id);selected=null;const ws=atlas.workers.filter(w=>w.project===id);visible=new Set(ws.map(w=>w.id));world.highlight([...visible]);world.route(ws);world.home();
 const p=panelHeader('예시 프로젝트 · 참여 위치 강조',project.name),c=counts(ws);p.append(node('p',`참여 ${c.total} · 실행 ${c.running} · 대기 ${c.waiting} · 막힘 ${c.blocked}`));
 for(const w of ws){const b=button('',()=>selectWorker(w),null,'result');b.append(node('b',`${w.id} · ${w.task}`),badge(w),node('small',teamOf(w.team).name));p.append(b);}p.append(node('p','선은 참여 워커를 잇는 예시 경로입니다. 실제 작업 의존 관계는 미연결입니다.'));
 $('#notice').textContent=`${project.name} · 관련 워커 ${ws.length}개 위치 강조 (예시)`;
}
function showLogs(w){$('#log-pane').hidden=false;$('#log-content').textContent=`[예시 기록 / 실제 터미널 아님]\n실행 ID: ${w.run}\n워커: ${w.id}\n업무: ${w.task}\n상태: ${statusNames[w.status]}\n보고: ${w.reportTo}\n사유: ${w.reason}\n\n외부 명령은 실행되지 않습니다. 실제 결과물 없음.`;}
function home(){closeDetail();$('#search').value='';$('#team').value='';$('#status').value='';updateSearch();world.home();$('#notice').textContent='검토용 고정 데이터 · 실제 명령과 중단은 연결하지 않았습니다.';}
$('#home').onclick=home;$('#search').oninput=updateSearch;$('#team').onchange=updateSearch;$('#status').onchange=updateSearch;
$('#open-search').onclick=()=>{$('#finder').hidden=!$('#finder').hidden;if(!$('#finder').hidden)$('#search').focus();};$('#close-search').onclick=()=>{$('#finder').hidden=true;};
$('#zoom-in').onclick=()=>world.zoomBy(1.3);$('#zoom-out').onclick=()=>world.zoomBy(1/1.3);$('#orbit').onclick=()=>{const b=$('#orbit'),on=b.getAttribute('aria-pressed')!=='true';b.setAttribute('aria-pressed',String(on));world.rotate(on);};
$('#close-logs').onclick=()=>{$('#log-pane').hidden=true;};
mini.onclick=e=>{const r=mini.getBoundingClientRect();world.focus(((e.clientX-r.left)*180/r.width-7)/2,((e.clientY-r.top)*120/r.height-5)/2,2.4);};
document.addEventListener('keydown',e=>{if(e.key==='Escape'){closeDetail();$('#finder').hidden=true;}if((e.ctrlKey||e.metaKey)&&e.key==='k'){e.preventDefault();$('#finder').hidden=false;$('#search').focus();}});
if(innerWidth<700)$('#finder').hidden=true;
updateSearch();window.atlasDiagnostics=()=>world.diagnostics();document.body.dataset.ready='true';
