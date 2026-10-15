// 편집 화면(장면꾸미기 UI 그대로, 숨김 없음)에서 칼카피 틀 설명서 스냅샷을 열어 미리보기 칸만 찍는다 — check_spec_downstream.py 가 부른다.
// 입력: render_scene_style.js 와 같은 요청 json({snapshot, context, output}). 출력: editor.png · editor-snapshot.json(편집기가 다시 저장하는 값)
const fs=require('fs'),path=require('path'),{pathToFileURL}=require('url'),puppeteer=require('puppeteer');
(async()=>{
  const request=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
  const browser=await puppeteer.launch({headless:true,args:process.env.SCENE_STYLE_NO_SANDBOX==='1'?['--no-sandbox']:[]});
  try{
    const page=await browser.newPage();await page.setViewport({width:1800,height:1100,deviceScaleFactor:2});
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto(pathToFileURL(path.resolve(__dirname,'../../out/scene-style-ui-showcase.html')).href+'?qa=1',{waitUntil:'networkidle0'});
    await page.evaluate(r=>window.sceneStyle.load(r.context,r.snapshot),request);
    await page.evaluate(async()=>{await document.fonts.ready;window.sceneStyle.refresh();});
    await page.evaluate(i=>window.sceneStyle.show(i),request.index||0);
    await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
    await new Promise(r=>setTimeout(r,900));   // 훅 등장 효과가 끝난 그림
    // 미리보기 칸의 테두리·둥근 모서리만 뺀다(화면 장식 — 안 빼면 테두리 선이 잉크로 잡힌다). 그림 자체는 그대로.
    await page.addStyleTag({content:'#a-live-preview{border:0!important;border-radius:0!important;box-shadow:none!important;outline:none!important}'});
    await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
    const el=await page.$('#a-live-preview');
    await el.screenshot({path:path.join(request.output,'editor.png')});
    const snap=await page.evaluate(()=>window.sceneStyle.snapshot());
    fs.writeFileSync(path.join(request.output,'editor-snapshot.json'),JSON.stringify(snap));
    if(errors.length)throw new Error(errors.join('\n'));
  }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
