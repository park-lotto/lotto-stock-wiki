export const statusNames={running:'실행',waiting:'대기',blocked:'막힘'};
const specs=[
 ['plan','기획·리서치',32,0,0,'#a6a0f8',['요구사항 정리','콘텐츠 조사','사용 흐름 설계','정책 검토','자료 분석','실험 설계']],
 ['dev','제품 개발',56,28,0,'#69baf3',['편집기 개선','자막 정렬','템플릿 개발','렌더 최적화','검색 개선','작업 저장']],
 ['collect','수집·분석',48,56,0,'#64d6bd',['채널 수집','원문 정리','중복 제거','자료 분류','스케줄 점검','품질 분석']],
 ['qa','독립 검수',36,14,29,'#ddad74',['회귀 검수','오류 재현','결과물 비교','성능 검수','접근성 검수','복구 검수']],
 ['ops','서비스 운영',28,42,29,'#8ca9ee',['서비스 점검','고객 문의','실패 로그','배포 관찰','예약 실행','보고 취합']],
];
const teams=specs.map(([id,name,size,x,z,color,tasks])=>({id,name,size,x,z,color,tasks,width:24,height:Math.ceil(size/8)*3+5}));
const projects=teams.flatMap(t=>t.tasks.map((name,i)=>({id:`${t.id}-${i}`,name:t.id==='plan'&&i===0?'수집 안정화':name,team:t.id,description:'탐색 검토용 예시 프로젝트입니다. 실제 운영 과제가 아닙니다.'})));
let n=0;
const workers=teams.flatMap(t=>Array.from({length:t.size},(_,i)=>{
 const index=n++,id=`W-${String(index+1).padStart(3,'0')}`;
 return {id,name:`${t.name} ${String(i+1).padStart(2,'0')}`,team:t.id,project:i===0?'plan-0':`${t.id}-${i%6}`,task:t.tasks[i%6],role:i===0?'팀장':i%6===0?'책임 워커':'실행 워커',status:index%20<14?'running':index%20<19?'waiting':'blocked',x:t.x+2.2+(i%8)*2.8,z:t.z+4+Math.floor(i/8)*3,reason:index%20===19?'재현 자료가 없어 다음 작업을 진행할 수 없습니다.':index%20>=14?'선행 작업의 결과를 기다리고 있습니다.':'배정된 예시 작업을 수행하는 상태입니다.',reportTo:i===0?'대표':`${t.name} 팀장`,run:`demo-${id.toLowerCase()}`};
}));
export const atlas={mode:'example',teams,projects,workers};
export function counts(items){return items.reduce((c,w)=>{c.total++;c[w.status]++;return c;},{total:0,running:0,waiting:0,blocked:0});}
export function searchWorkers(query='',{team='',status='',project=''}={}){
 const q=query.trim().toLocaleLowerCase();
 return workers.filter(w=>(!team||w.team===team)&&(!status||w.status===status)&&(!project||w.project===project)&&(!q||[w.id,w.name,w.task,projects.find(p=>p.id===w.project).name].join(' ').toLocaleLowerCase().includes(q)));
}
