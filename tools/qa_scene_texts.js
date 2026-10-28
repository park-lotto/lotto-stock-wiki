// 관제 219 점검: [이 장면만]으로 고친 제목·채널명 글이 그 장면에만 들어가는가 — 편집 화면과 렌더 경로(load→show(i), 렌더·캡컷·썸네일 공용) 둘 다.
// 사용: node tools/qa_scene_texts.js [저장소 폴더(기본: 이 파일의 상위)]
//   옛 코드 폴더를 주면 실패해야 정상이다(검사가 무언가를 재고 있다는 증거).
const path=require('path'),{pathToFileURL}=require('url'),puppeteer=require('puppeteer');
const repo=path.resolve(process.argv[2]||path.join(__dirname,'..'));
const url=pathToFileURL(path.join(repo,'out/scene-style-ui-showcase.html')).href+'?qa=1';
const context={scenes:[{kind:'hook',caption:'훅 자막'},{kind:'body',caption:'본문 자막 1'},{kind:'body',caption:'본문 자막 2'}],text:{channel:'픽집',hook1:'훅 하나',hook2:'훅 둘',bodyTitle:'공통 제목'}};
(async()=>{
  const browser=await puppeteer.launch({headless:true});
  const fails=[];const ok=(c,m)=>{if(!c)fails.push(m);};const step=m=>process.env.QA_DEBUG&&console.log('…',m);
  try{
    const open=async()=>{const page=await browser.newPage();await page.setViewport({width:1920,height:1100});const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>{errors.push('알림창: '+d.message());d.dismiss().catch(()=>{});});await page.goto(url,{waitUntil:'load',timeout:60000});await page.waitForFunction(()=>window.sceneStyle&&window.sceneStyle.load,{timeout:60000});return {page,errors};};
    const layerText=(page,bind)=>page.evaluate(b=>document.querySelector(`.precision-text[data-edit-bind="${b}"]`)?.textContent||'',bind);
    // 입력칸에 손으로 친 것과 같은 순서(beforeinput → 값 → input)로 넣는다 — 칸이 화면에 숨어 있어도 같은 길을 탄다
    const typeInto=(page,sel,text)=>page.evaluate((s,t)=>{const el=document.querySelector(s);el.dispatchEvent(new InputEvent('beforeinput',{bubbles:true,inputType:'insertText',data:t}));el.value=t;el.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:t}));},sel,text);
    const frame=page=>page.evaluate(()=>new Promise(r=>setTimeout(r,120)));   // 뒤로 간 탭은 requestAnimationFrame 이 멈춘다(창 2개를 번갈아 쓴다)
    
    // ① 편집 화면: 본문 1번 장면에서 [이 장면만] → 보조제목 고치기
    const {page,errors}=await open();
    await page.evaluate(c=>window.sceneStyle.load(c,null),context);
    await page.evaluate(()=>window.sceneStyle.show(1));await frame(page);
    await page.evaluate(()=>document.querySelector('[data-edit-scope="one"]').click());
    const field='.layout-a [data-bind="bodyTitle"]';
    await typeInto(page,field,'1번 전용 제목');await frame(page);
    const snap=await page.evaluate(()=>window.sceneStyle.snapshot());
    ok(snap.text.bodyTitle==='공통 제목',`저장 공통 글이 바뀜: ${snap.text.bodyTitle}`);
    ok(snap.sceneTexts&&snap.sceneTexts['bodyTitle:1']==='1번 전용 제목',`장면별 글 저장 안 됨: ${JSON.stringify(snap.sceneTexts)}`);
    await page.evaluate(()=>window.sceneStyle.show(2));await frame(page);
    const editBody=await layerText(page,'bodyTitle');const boxBody=await page.evaluate(s=>document.querySelector(s).value,field);
    ok(editBody==='공통 제목'&&boxBody==='공통 제목',`편집 화면 2번 장면이 '공통 제목'이 아님: 그림=${editBody} 입력칸=${boxBody}`);
    await page.evaluate(()=>window.sceneStyle.show(1));await frame(page);
    ok(await page.evaluate(s=>document.querySelector(s).value,field)==='1번 전용 제목','1번으로 돌아오면 입력칸에 장면 글이 안 보임');
    // ② 렌더 경로: 저장값 그대로 새 페이지에 load → 장면마다 show(i) 해서 그려진 글
    const r=await open();
    await r.page.evaluate((c,s)=>window.sceneStyle.load(c,s),context,snap);
    const drawn=[];for(let i=0;i<3;i++){await r.page.evaluate(n=>window.sceneStyle.show(n),i);await frame(r.page);drawn.push(await layerText(r.page,'bodyTitle'));}
    ok(drawn[1]==='1번 전용 제목'&&drawn[2]==='공통 제목',`렌더 장면별 글 = ${JSON.stringify(drawn)}`);
    const again=await r.page.evaluate(()=>window.sceneStyle.snapshot());
    ok(again.text.bodyTitle==='공통 제목'&&again.sceneTexts?.['bodyTitle:1']==='1번 전용 제목','다시 저장하면 장면 글·공통 글이 섞임');
    // ③ [모든 장면]으로 고치면 그 칸의 장면별 글이 지워지고 전 장면이 같은 글
    await page.evaluate(()=>window.sceneStyle.show(2));await frame(page);
    await page.evaluate(()=>document.querySelector('[data-edit-scope="all"]').click());
    await typeInto(page,field,'새 공통');await frame(page);
    const snap2=await page.evaluate(()=>window.sceneStyle.snapshot());
    ok(snap2.text.bodyTitle==='새 공통'&&!snap2.sceneTexts,`모든 장면 수정 뒤 = ${snap2.text.bodyTitle} / ${JSON.stringify(snap2.sceneTexts)}`);
    // ④ 이 장면만 [처음으로]는 그 장면 글만 공통으로 되돌린다
    await page.evaluate(()=>window.sceneStyle.show(1));await frame(page);
    await page.evaluate(()=>document.querySelector('[data-edit-scope="one"]').click());
    await typeInto(page,field,'잠깐');if(process.env.QA_DEBUG)console.log('④ 입력 뒤',JSON.stringify(await page.evaluate(()=>{const x=window.sceneStyle.snapshot();return [x.text.bodyTitle,x.sceneTexts,document.querySelector('[data-edit-scope].active')?.dataset.editScope,document.querySelectorAll('.layout-a [data-field-key="bodyTitle"] [data-field-reset]').length]})));
    await page.evaluate(()=>document.querySelector('.layout-a [data-field-key="bodyTitle"] [data-field-reset]').click());await frame(page);
    const snap3=await page.evaluate(()=>window.sceneStyle.snapshot());
    ok(snap3.text.bodyTitle==='새 공통'&&!snap3.sceneTexts&&await page.evaluate(s=>document.querySelector(s).value,field)==='새 공통',`이 장면만 처음으로 = ${snap3.text.bodyTitle} / ${JSON.stringify(snap3.sceneTexts)}`);
    ok(!errors.length&&!r.errors.length,`페이지 오류: ${[...errors,...r.errors].join(' | ')}`);
  }finally{await browser.close();}
  console.log(fails.length?`실패 ${fails.length}\n- `+fails.join('\n- '):'통과 — 장면별 제목 글: 편집·렌더·재저장·모든장면·처음으로');
  process.exit(fails.length?1:0);
})();
