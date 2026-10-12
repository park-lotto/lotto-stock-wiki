// 칸 구조 시범(이븐쇼핑)에서 '채널명 칸'을 **실제 마우스**(＋ 클릭·손잡이 드래그)로 움직이며 부품 위치·글자 크기를 적고 화면을 찍는다.
//   기대: 채널명 칸(구분선)만 늘고, 글자·☰·🔍는 칸 가운데에 같이, 제목·자막·영상은 늘어난 만큼 그대로 밀린다. 글자 크기 불변. 되돌리면 제자리.
//   실행: node tools/qa_channel_block_mouse.js <출력폴더> [본문|훅]
const puppeteer=require('puppeteer'),fs=require('fs');const out=process.argv[2]||'.tmp/blockmouse',kind=process.argv[3]||'본문';fs.mkdirSync(out,{recursive:true});
const wait=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{const b=await puppeteer.launch({headless:true});const p=await b.newPage();await p.setViewport({width:1700,height:1100,deviceScaleFactor:2});await p.setCacheEnabled(false);
const errs=[];p.on('pageerror',e=>errs.push(String(e).slice(0,140)));
await p.goto(process.env.URL||'http://127.0.0.1:8771/out/scene-style-ui-showcase.html',{waitUntil:'networkidle0'});await wait(900);
await p.click('[data-p20="0"]');await wait(400);await p.evaluate(s=>document.querySelector('[data-scene-step="'+(s?1:-1)+'"]').click(),kind==='본문');await wait(2500);
await p.evaluate(()=>document.querySelectorAll('details').forEach(d=>d.open=true));await wait(400);
const read=()=>p.evaluate(()=>{const pv=document.querySelector('#a-live-preview'),P=pv.getBoundingClientRect(),f=v=>Math.round(v*10)/10,span=e=>{if(!e)return null;const r=e.getBoundingClientRect();return f((r.top-P.top)/P.height*100)+'~'+f((r.bottom-P.top)/P.height*100)};
 const q=s=>pv.querySelector(s),txt=b=>q('.precision-text[data-edit-bind="'+b+'"]'),fs=e=>e?Math.round(parseFloat(getComputedStyle(e).fontSize)*10)/10:null;
 const line=[...pv.querySelectorAll('.precision-patch')].find(e=>{const r=e.getBoundingClientRect();return r.height<3&&r.width>P.width*.5&&r.top-P.top<P.height*.3});
 const row=document.querySelector('[data-fixed-size="channel"]');
 return {슬라이더:document.querySelector('[data-fixed-range="channel"]').value,표시:row.querySelector('output')?.textContent,구분선:span(line),채널명:span(txt('channel'))+' '+fs(txt('channel'))+'px',메뉴:span(q('.body-ornament-menu')),돋보기:span(q('.body-ornament-search')),
  제목:['hook1','hook2','bodyTitle'].filter(txt).map(k=>span(txt(k))+' '+fs(txt(k))+'px').join(' | '),자막칸:span(q('.caption-mask')),영상:span(q('.scene-media-clip'))}});
const shot=async n=>{const c=await p.evaluate(()=>{const r=document.querySelector('#a-live-preview').getBoundingClientRect();return {x:r.left,y:r.top,width:r.width,height:r.height*.6}});await p.screenshot({path:out+'/'+n+'.png',clip:c});};
const log=async n=>{await wait(1200);const r=await read();console.log(n.padEnd(14),JSON.stringify(r));await shot(kind+'_'+n);};
await log('0처음');
const plus=await p.$('[data-fixed-size="channel"] [data-fixed-step="1"]');await plus.evaluate(e=>e.scrollIntoView({block:'center'}));
for(let i=0;i<4;i++){await plus.click();await wait(350);}await log('1더하기4번');
const r=await p.$('[data-fixed-range="channel"]');let bx=await r.boundingBox();const at=v=>bx.x+bx.width*(v/20);
const cur=Number(await p.evaluate(()=>document.querySelector('[data-fixed-range="channel"]').value));
await p.mouse.move(at(cur),bx.y+bx.height/2);await p.mouse.down();await p.mouse.move(at(20)+4,bx.y+bx.height/2,{steps:14});await p.mouse.up();await log('2손잡이끝까지');
bx=await r.boundingBox();await p.mouse.move(at(20)-2,bx.y+bx.height/2);await p.mouse.down();await p.mouse.move(at(9),bx.y+bx.height/2,{steps:14});await p.mouse.up();await log('3손잡이처음값');
console.log('페이지오류',JSON.stringify(errs));await b.close();})().catch(e=>{console.error(String(e).slice(0,300));process.exit(1)});
