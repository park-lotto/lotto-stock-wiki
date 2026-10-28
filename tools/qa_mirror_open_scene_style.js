// 서버 실제 job(로컬 미러 8772)에서 고객 길 그대로 장면꾸미기 편집기를 연다 — MIX_JOB 강제 주입·단계 억지 펼침 없음.
//   선행: py tools/mirror_live_job.py <job_id> → py tools/serve_local_mirror.py
//   실행: node tools/qa_mirror_open_scene_style.js [캡처경로]
const puppeteer=require('puppeteer');
const shot=process.argv[2]||'.tmp/local-mirror/editor.png';
(async()=>{
  const b=await puppeteer.launch({headless:true});const p=await b.newPage();await p.setViewport({width:1700,height:1000});
  const errs=[];p.on('pageerror',e=>errs.push(String(e).slice(0,160)));
  await p.goto('http://127.0.0.1:8772/produce.html',{waitUntil:'networkidle2',timeout:90000});
  await new Promise(r=>setTimeout(r,1500));
  const job=await p.evaluate(()=>typeof MIX_JOB!=='undefined'?MIX_JOB:null);
  const btn=await p.$('[onclick="openSceneStyleEditor()"]');
  const visible=btn&&await btn.evaluate(e=>!!e.offsetParent);
  if(!visible){console.log(JSON.stringify({job,오류:'편집 버튼이 화면에 안 보인다',errs}));await b.close();process.exit(1);}
  await btn.evaluate(e=>e.scrollIntoView({block:'center'}));await btn.click();
  await p.waitForSelector('dialog[open] iframe',{timeout:30000});
  const f=await (await p.$('dialog[open] iframe')).contentFrame();
  await f.waitForFunction(()=>window.sceneStyle&&document.querySelector('#a-live-preview'),{timeout:60000});
  await new Promise(r=>setTimeout(r,2500));
  const info=await f.evaluate(()=>{const s=window.sceneStyle.snapshot?.()||{};
    return {src:location.pathname+location.search.slice(0,60),연결:document.querySelector('[data-connection-status]')?.textContent?.trim().slice(0,60),
      preset:s.presetId,mode:s.mode,frameKind:s.frameKind,
      ui버전:[...document.scripts].map(x=>x.src).filter(x=>/precision20-ui/.test(x)).map(x=>x.split('/').pop())[0],
      채널칸:!!document.querySelector('[data-field-key="channel"]'),채널명:document.querySelector('.precision-text[data-edit-bind="channel"]')?.textContent?.trim()||null,
      자막:document.querySelector('.precision-text[data-edit-bind="caption"]')?.textContent?.trim().slice(0,30)||null};});
  await p.screenshot({path:shot});
  console.log(JSON.stringify({job,info,errs},null,1));await b.close();
})().catch(e=>{console.error(String(e).slice(0,300));process.exit(1)});
