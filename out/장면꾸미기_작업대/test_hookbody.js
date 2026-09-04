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



console.log('=== T8. 「같게」로 본문이 헤드카피 구조가 돼도 편집칸/그림이 안 어긋난다 ===');
{SPECS.hook={};SPECS.body={};part='hook';SPEC=SPECS.hook;
 applyLayout('sul_gongami');
 go('hook'); setBig('text','샤넬도 예상 못한'+String.fromCharCode(10)+'일본의 천재적 발상');
 if(!SPECS.body._sameBackup){const bk=JSON.parse(JSON.stringify(SPECS.body));delete bk._sameBackup;
   SPECS.body=JSON.parse(JSON.stringify(SPECS.hook));SPECS.body._sameBackup=bk;SPECS.body._touched=true;}
 go('body');
 const shown=_isBody()?(SPEC.title||''):((SPEC.hc||{}).text||'');
 const drawn=((SPEC.hc||{}).text||'').trim()?((SPEC.hc||{}).text):(SPEC.title||'');
 chk('편집칸 == 그림', shown.trim()===drawn.trim(), {pan:shown,drawn:drawn});
 const before=(SPEC.hc||{}).size;
 bumpBig(4);
 const after=(SPEC.hc||{}).size;
 chk('크기 +4 가 실제 그려지는 글에 먹는다', after===before+4, {before:before,after:after,title_size:SPEC.title_size});}

console.log('=== T9. 카드를 고르면 채널명도 그 채널 것으로 바뀐다 ===');
{ // 완성형 클릭 1번 = 띠에 뜨는 이름도 그 채널이어야 한다
  DOM.channel='살림킹왕짱';           // 앞서 다른 채널을 보던 상태
  applyLayout('sul_bangkkul');       // 방구석꿀템으로 갈아탄다
  const want=LAYOUTS['sul_bangkkul'].name;
  chk('후킹 채널명이 그 채널 것', SPECS.hook.channel===want, {got:SPECS.hook.channel,want:want});
  chk('본문 채널명이 그 채널 것', SPECS.body.channel===want, {got:SPECS.body.channel,want:want});
  chk('채널명 입력칸도 같이 바뀐다', DOM.channel===want, {got:DOM.channel,want:want});
  // 사장님이 직접 고쳐 쓴 이름은 카드를 갈아타도 지켜져야 한다(내 채널명으로 쓰는 경우)
  if(typeof setCh==='function'){
    setCh('내 채널');
    applyLayout('sul_lucky');
    chk('내가 적은 채널명은 카드 전환에도 유지', SPECS.hook.channel==='내 채널', SPECS.hook.channel);
  } else chk('setCh 가 있다(직접 고친 이름 지키기)', false, 'setCh 없음');
}

console.log('=== T10. 저장값(DEF)이 있어도 채널명은 그 채널 것 ===');
{ // ★DEF 분기는 조기 return 이라 여기까지 안 고치면 저장된 채널에서만 조용히 실패한다
  //   (실측 2026-09-04: 노드는 DEF={} 로 돌아 통과했는데 브라우저 28채널 전부 안 바뀌었다)
  _chanReset(); DOM.channel='살림킹왕짱';
  DEF['sul_gongami']={hook:{preset:'sul_gongami',channel:'살림킹왕짱',hc:{text:'옛 글',size:70}},
                      body:{preset:'sul_gongami',channel:'살림킹왕짱',title:'옛 본문',hc:{text:''}}};
  applyLayout('sul_gongami');
  const want=LAYOUTS['sul_gongami'].name;
  chk('저장값으로 열어도 후킹 채널명이 그 채널 것', SPECS.hook.channel===want, {got:SPECS.hook.channel,want:want});
  chk('저장값으로 열어도 본문 채널명이 그 채널 것', SPECS.body.channel===want, {got:SPECS.body.channel,want:want});
  chk('저장값으로 열어도 입력칸이 바뀐다', DOM.channel===want, {got:DOM.channel,want:want});
  delete DEF['sul_gongami'];
}

console.log('');
console.log(fail===0?'ALL PASS':(fail+' FAILED'));
process.exit(fail?1:0);
