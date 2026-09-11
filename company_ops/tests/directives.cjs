const path=require('path'),fs=require('fs'),assert=require('assert/strict');
const {execFileSync}=require('child_process');
const puppeteer=require(path.resolve(__dirname,'../../../../node_modules/puppeteer'));
if(process.env.COMPANY_OPS_E2E!=='1'||!process.env.COMPANY_OPS_URL||!process.env.COMPANY_OPS_TEST_DB)throw Error('명시적 시험 서버·시험 DB·E2E 설정 필요');
const root=path.resolve(__dirname,'../..');
const db=path.resolve(process.env.COMPANY_OPS_TEST_DB);
assert(db.startsWith(path.resolve(__dirname,'../.artifacts')+path.sep),'시험 DB는 .artifacts 내부만 허용');
const file=path.resolve(__dirname,'../.artifacts/terminal-test-payload.json');
(async()=>{
const browser=await puppeteer.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
try{
const page=await browser.newPage();await page.setViewport({width:1600,height:1050});
const errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.goto(process.env.COMPANY_OPS_URL+'/static/directives.html');
await page.waitForFunction(()=>document.querySelector('#sync').textContent.includes('원장 조회'));
const title='[터미널 연결 시험] CS 분류 지시 '+new Date().toISOString();
const payload={project:{company_id:'makers',team_id:'cs',owner:'접수 연동 시험',title,description:'시험 지시: 문의 분류와 재현 절차를 준비합니다. 실제 모델 실행·고객 발송·배포는 하지 않습니다.'},receipt:{request_id:'test-'+Date.now(),session_ref:'자동검증용 터미널 세션',approval_ref:'시험 fixture · 실제 대표 컨펌 아님',approval_text:'연동 검증 전용 승인 예시입니다. 실업무 승인이 아닙니다.'}};
fs.writeFileSync(file,JSON.stringify(payload),'utf8');
const args=['-m','company_ops.terminal','--db',db,'--file',file,'--confirmed-by-user'];
const run=()=>JSON.parse(execFileSync('py',args,{cwd:root,env:{...process.env,PYTHONIOENCODING:'utf-8'},encoding:'utf8'}));
const first=run(),second=run();assert.equal(first.project_id,second.project_id);
await page.waitForFunction(t=>document.querySelector('#list').textContent.includes(t),{timeout:15000},title);
await page.evaluate(t=>[...document.querySelectorAll('.job')].find(e=>e.textContent.includes(t)).click(),title);
await page.waitForFunction(()=>document.querySelector('#detail').textContent.includes('터미널 컨펌 근거와 확정 지시 접수'));
assert.equal(await page.$$eval('.pipeline li',e=>e.length),8);
assert((await page.$eval('#detail',e=>e.textContent)).includes('실제 대표 컨펌 아님'));
const response=await page.evaluate(async()=>await(await fetch('/api/state')).json());
assert.equal(response.projects.filter(p=>p.id===first.project_id).length,1);
await page.screenshot({path:path.resolve(__dirname,'../.artifacts/terminal-workflow.png'),fullPage:true});
await page.evaluate(async id=>{
 let s=await(await fetch('/api/state')).json(),p=s.projects.find(x=>x.id===id);
 for(let i=0;i<2;i++){
  const r=await fetch('/api/projects/'+id+'/actions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'advance',version:p.version,note:'자동 검증용 원장 단계 이동 · 실제 AI 실행 아님'})});
  if(!r.ok)throw Error('시험 단계 저장 실패');p=await r.json();
 }
},first.project_id);
await page.waitForFunction(()=>document.querySelector('.pipeline .current strong')?.textContent==='워커 실행',{timeout:15000});
assert((await page.$eval('.pipeline .current',e=>e.textContent)).includes('실행 세션 미연결'));
await page.screenshot({path:path.resolve(__dirname,'../.artifacts/terminal-workflow-progress.png'),fullPage:true});
await page.reload();await page.waitForFunction(t=>document.querySelector('#list').textContent.includes(t),{},title);
await page.select('#company','hnl');assert(!(await page.$eval('#list',e=>e.textContent)).includes(title));
await page.setViewport({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
assert.deepEqual(errors,[]);console.log('PASS: 터미널 전달·중복 방지·5초 자동 반영·단계 변경 자동 반영·승인 출처·8단계·재열기·회사 분리·모바일');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
