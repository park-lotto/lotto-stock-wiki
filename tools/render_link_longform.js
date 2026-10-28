// 구매링크 롱폼 안내 항목(out/link-longform-stage.html)을 투명 PNG 프레임으로 찍는다(관제 133).
//   node tools/render_link_longform.js <request.json>   request = {items, output, frames:[프레임 번호…], fps}
//   프레임 f 의 시각 = f/fps 초 — 화면의 linkLongform.motionAt 이 움직임·시계를 그 시각에 못 박는다(편집 화면과 같은 그리기 코드).
const fs=require('fs'),path=require('path'),{pathToFileURL}=require('url'),puppeteer=require('puppeteer');
(async()=>{
  const request=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
  const browser=await puppeteer.launch({headless:true,args:process.env.SCENE_STYLE_NO_SANDBOX==='1'?['--no-sandbox']:[]});
  try{
    const page=await browser.newPage();await page.setViewport({width:1920,height:1080,deviceScaleFactor:1});
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto(pathToFileURL(path.resolve(__dirname,'../out/link-longform-stage.html')).href+'?qa=1',{waitUntil:'networkidle0'});
    await page.evaluate(async items=>{window.linkLongform.load(items);await document.fonts.ready},request.items);
    const fps=request.fps||30;
    for(const f of request.frames){
      await page.evaluate(t=>window.linkLongform.motionAt(t),f/fps*1000);
      await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
      // ★멈춘 움직임의 시각만 바꾸면 크로미움 화면 합성이 새 그림을 안 만든다 — 한 박자 늦은(직전 시각) 그림이 찍혔다(2026-10-06 실측:
      //   4.5초 프레임에 30:00). render_scene_style.js 와 같은 처방: 지금 계산된 모양을 요소에 직접 박고 움직임을 걷어낸 뒤 찍는다.
      //   다음 프레임은 motionAt 이 항목을 다시 그려(freeze 표시를 보고) 움직임을 되살린다.
      await page.evaluate(()=>window.linkLongform.freeze());
      await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
      await page.screenshot({path:path.join(request.output,String(f).padStart(5,'0')+'.png'),clip:{x:0,y:0,width:1920,height:1080},omitBackground:true});
    }
    if(errors.length)throw new Error(errors.join('\n'));
  }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
