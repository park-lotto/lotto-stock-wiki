const fs=require('fs');
const WB=__dirname+'/';
const SP=__dirname;  // funcs.js/presets.json 은 test_extract.py 로 먼저 만든다
const LAYOUTS=JSON.parse(fs.readFileSync(WB+'channel_layouts.json','utf8'));
const PRESETS=JSON.parse(fs.readFileSync(SP+'/presets.json','utf8'));
const DOM={hcText:'',channel:'숏템메이커',title:''};
global.document={getElementById:()=>({textContent:'',value:'',classList:{add(){},remove(){},toggle(){}},style:{}}),querySelectorAll:()=>[]};
global.$=s=>{const k=s.replace('#','');return{get value(){return DOM[k]||'';},set value(v){DOM[k]=v;}};};
let BODY_BACKUP=null, part='hook';
const HC_DEFAULT={size:90,x:50}, BASE={}, DEF={};
const SPECS={hook:{},body:{}}; let SPEC=SPECS.hook;
let hint={textContent:''};
function syncUI(){} function render(){} function hcFit(){} function fitOne(){} function capSwitchTo(){} function syncFromSpec(){}
eval(fs.readFileSync(SP+'/funcs.js','utf8'));
function go(p){part=p;SPEC=SPECS[p];}

let fail=0;
function chk(name,cond,got){ console.log((cond?'  PASS  ':'  FAIL  ')+name+(cond?'':'   -> '+JSON.stringify(got))); if(!cond)fail++; }

console.log('=== T1. 본문 대제목을 고친 뒤 후킹을 고쳐도 본문은 그대로 ===');
applyLayout('sul_salrim');
go('body'); setBig('text','내가 적은 본문 제목');
go('hook'); setBig('text','찌든때 3초 컷\n하나면 끝나요');
chk('본문 대제목 유지', SPECS.body.title==='내가 적은 본문 제목', SPECS.body.title);

console.log('=== T2. 본문을 고친 뒤 다른 카드로 갈아타도 본문은 그대로 ===');
applyLayout('sul_lucky');
chk('본문 대제목 유지', SPECS.body.title==='내가 적은 본문 제목', SPECS.body.title);

console.log('=== T3. 본문 크기/색도 후킹과 따로 ===');
applyLayout('sul_salrim');
go('body'); bumpBig(-10); const bs=SPECS.body.title_size;
go('hook'); bumpBig(+20);
chk('본문 크기 유지', SPECS.body.title_size===bs, {body:SPECS.body.title_size,hook:(SPECS.hook.hc||{}).size});

console.log('=== T4. 본문 소제목(조회수)도 따로 ===');
applyLayout('sul_salrim');
go('body'); setSub('text','389,282');
go('hook'); setSub('text','조회수 1111');
chk('본문 조회수 유지', SPECS.body.views==='389,282', SPECS.body.views);

console.log('=== T5. 안 만진 본문은 카드 문구로 채워짐 (완성형 유지) ===');
SPECS.hook={};SPECS.body={};part='hook';SPEC=SPECS.hook;
applyLayout('sul_bangkkul');
chk('본문 자동 채움', !!SPECS.body.title && SPECS.body.title.length>3, SPECS.body.title);

console.log('=== T6. body_keep_hc 3채널은 예외(지금대로 같이 감) ===');
SPECS.hook={};SPECS.body={};part='hook';SPEC=SPECS.hook;
applyLayout('sul_dalrae');
go('hook'); setBig('text','달래샵 헤드라인 수정');
chk('달래샵은 본문도 따라감', ((SPECS.body.hc||{}).text)==='달래샵 헤드라인 수정', (SPECS.body.hc||{}).text);


console.log('=== T7. 카드 클릭 시 후킹과 본문은 서로 다른 모양이어야 (원본 실측) ===');
{const strip=o=>{const x=JSON.parse(JSON.stringify(o));delete x.hc;delete x._bandLock;return JSON.stringify(x);};
 let bad=[];
 for(const id of Object.keys(LAYOUTS)){
   if(id==='_meta')continue;
   SPECS.hook={};SPECS.body={};part='hook';SPEC=SPECS.hook;
   applyLayout(id);
   if(strip(SPECS.hook)===strip(SPECS.body)) bad.push(id);
 }
 chk('후킹==본문인 채널 없음(sul_core 제외)', bad.filter(x=>x!=='sul_core').length===0, bad);}

console.log('');
console.log(fail===0?'ALL PASS':(fail+' FAILED'));
process.exit(fail?1:0);
