const fs=require('fs'),path=require('path'),{pathToFileURL}=require('url'),puppeteer=require('puppeteer');
// Materialize the sampled animation state for Chromium's screenshot compositor.
const materialize=page=>page.evaluate(()=>{
  document.querySelectorAll('.scene-decoration,.precision-text,.precision-patch,.scene-brand-ink,.cap-u').forEach(el=>{
    const animations=el.getAnimations();if(!animations.length)return;
    const style=getComputedStyle(el),values={};
    for(const key of ['transform','translate','rotate','scale','opacity','filter','clipPath'])values[key]=style[key];
    animations.forEach(a=>a.cancel());Object.assign(el.style,values);
  });
});
const twoFrames=page=>page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
(async()=>{
  const request=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
  const browser=await puppeteer.launch({headless:true,args:process.env.SCENE_STYLE_NO_SANDBOX==='1'?['--no-sandbox']:[]});
  try{
    const page=await browser.newPage();await page.setViewport({width:1920,height:2200,deviceScaleFactor:1});
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto(pathToFileURL(path.resolve(__dirname,'../out/scene-style-ui-showcase.html')).href+'?qa=1',{waitUntil:'networkidle0'});
    await page.addStyleTag({content:`body *{visibility:hidden!important}#a-live-preview,#a-live-preview *{visibility:visible!important}#a-live-preview{position:fixed!important;left:0!important;top:0!important;width:1080px!important;height:1920px!important;max-width:none!important;max-height:none!important;border:0!important;border-radius:0!important;box-shadow:none!important;background:transparent!important;z-index:99999!important}.precision-base,.precision-media,.scene-media-clip,.precision-badge{display:none!important}html,body{background:transparent!important}`});
    await page.evaluate(r=>window.sceneStyle.load(r.context,r.snapshot),request);
    await page.addStyleTag({content:'.scene-decoration{outline:none!important}.scene-decoration-toolbar,.precision-source-cleanup{display:none!important}'});
    await page.evaluate(async()=>{await document.fonts.ready;window.sceneStyle.refresh();window.sceneStyleExporting=true});
    const layers=[];
    const only=Array.isArray(request.only)?new Set(request.only.map(Number)):null;   // 썸네일 핀: 한 장면만(2026-09-23)
    // 단어 강조(관제 102): 켜져 있으면 자막 있는 장면을 장면 끝까지 프레임 묶음으로 낸다. 그림은 단어가 바뀔 때만 달라지므로
    //   바뀐 프레임만 찍고 나머지는 앞 그림을 복사한다(찍기 1장 ≈ 0.26초, 복사는 거의 0).
    const wordFx=!!(request.snapshot.wordFx&&request.snapshot.wordFx.style);
    for(let index=0;index<request.context.scenes.length;index++){
      if(only&&!only.has(index)){layers.push(null);continue;}
      const g=await page.evaluate(i=>window.sceneStyle.show(i),index);
      await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
      const file=`scene-style-layer-${index}.png`;
      const CAMERA=['zoom-punch','push-in','shake'],isCamera=CAMERA.includes(request.snapshot.hookMotion);
      const duration=(request.snapshot.hookMotion&&!isCamera)||request.snapshot.hookBandMotion||request.snapshot.hookBandRise?await page.evaluate(()=>window.sceneStyle.motionAt(100000)):0;   // 흰 띠 스윽은 줌 펀치와 겹쳐도 프레임별로 찍는다
      // 고정형 자막 등장(0.3초): 훅뿐 아니라 자막이 바뀌는 모든 장면의 시작을 프레임별로 찍는다.
      const enter=(request.snapshot.mode==='continuous'&&request.snapshot.hookBandMotion)||request.snapshot.bodyCaptionMotion||request.snapshot.captionPack?await page.evaluate(()=>window.sceneStyle.captionEnterAt?.(100000)||0):0;
      const moving=await page.evaluate(()=>{const shape=window.sceneDecorations?.motionAt(0),brand=window.sceneBranding?.motionAt(0);return shape||brand||false});
      const words=wordFx?await page.evaluate(()=>window.sceneStyle.wordFxAt?.(0)??null):null;   // null = 이 장면엔 강조할 자막이 없다
      await page.screenshot({path:path.join(request.output,file),clip:{x:0,y:0,width:1080,height:1920},omitBackground:true});
      const scene=request.context.scenes[index],first=Math.round(scene.start*30),end=Math.round(scene.end*30);
      let animation=null,wordSpans=null;
      const hookCount=duration>first/30*1000&&g.kind==='hook'?Math.ceil(duration/1000*30)-first+1:0,enterCount=enter?Math.ceil(enter/1000*30)+1:0;
      if(!request.still&&(moving||hookCount||enterCount||words!==null)){   // still=정지 한 장만(썸네일 핀)
        const settle=Math.max(hookCount,enterCount);   // 이 프레임까지는 제목·자막 등장이 움직인다 → 매 프레임 찍는다
        const count=moving||words!==null?end-first:Math.min(end-first,settle);
        const pattern=`scene-style-motion-${index}-%04d.png`,frameFile=f=>pattern.replace('%04d',String(f).padStart(4,'0'));
        let lastWord=null,lastShot=-1;const wordAt=[];
        for(let f=0;f<count;f++){
          await page.evaluate(i=>window.sceneStyle.show(i),index);
          // 단어 상태를 먼저 묻는다 — 등장이 끝났고 단어도 안 바뀌었으면 앞 그림을 그대로 쓴다.
          const word=words!==null?await page.evaluate(t=>window.sceneStyle.wordFxAt(t),f/30*1000):null;
          // word = '단어 번호:배율'. 캡컷 구간은 단어가 바뀔 때만 끊는다('툭 커짐'은 같은 단어 안에서 배율만 바뀐다).
          const wordNo=word===null?null:Number(String(word).split(':')[0]);wordAt[f]=word;
          if(words!==null&&(!wordSpans||wordNo!==wordSpans[wordSpans.length-1].word)){(wordSpans=wordSpans||[]).push({frame:f,word:wordNo});}
          if(words!==null&&!moving&&f>settle&&word===lastWord&&lastShot>=0){
            fs.copyFileSync(path.join(request.output,frameFile(lastShot)),path.join(request.output,frameFile(f)));
            continue;
          }
          lastWord=word;
          await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
          await page.evaluate(({title,shape,brand,cap,word})=>{window.sceneStyle.motionAt(title);window.sceneDecorations?.motionAt(shape);window.sceneBranding?.motionAt(brand);if(cap!==null)window.sceneStyle.captionEnterAt?.(cap);if(word!==null)window.sceneStyle.wordFxAt(word)},{title:g.kind==='hook'?(first+f)/30*1000:100000,shape:f/30*1000,brand:(first+f)/30*1000,cap:enter?f/30*1000:null,word:words!==null?f/30*1000:null});   // 단어 상태는 찍기 직전에 한 번 더 못 박는다
          await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
          await materialize(page);
          await page.screenshot({path:path.join(request.output,frameFile(f)),clip:{x:0,y:0,width:1080,height:1920},omitBackground:true});
          lastShot=f;
        }
        animation={pattern,count};
        // 캡컷은 정지 그림 클립만 받는다 — 단어마다 그 단어의 마지막 프레임(등장이 끝난 그림)을 대표로 넘긴다(scene_style.overlay_spans).
        if(wordSpans)wordSpans=wordSpans.map((span,k)=>({frame:span.frame,word:span.word,file:frameFile((k+1<wordSpans.length?wordSpans[k+1].frame:count)-1)}));
        // 대표 그림이 자막 등장 도중이면(첫 단어가 짧거나 글자 단위 등장이 길 때) 캡컷엔 글자가 덜 나온 채 멈춰 보인다(관제 127 실측:
        //   글자 팝 튕김 첫 단어 잉크 44,444 / 정상 51,402). 그 단어는 '등장이 끝난 자막 + 그 단어 강조'를 따로 한 장 찍는다.
        //   그려지는 강조(밑줄·동그라미 등)가 그 단어 구간 안에 다 안 그려졌을 때(진행도 <1)도 같다 — 다 그려진 그림으로 찍는다.
        if(wordSpans)for(const span of wordSpans){
          const f=Number(span.file.match(/(\d{4})\.png$/)[1]),part=String(wordAt[f]??'').split(':')[2],partial=part!==undefined&&Number(part)<1;
          if(!(enterCount&&f<enterCount-1)&&!partial)continue;
          await page.evaluate(i=>window.sceneStyle.show(i),index);await twoFrames(page);
          await page.evaluate(({title,shape,brand,word})=>{window.sceneStyle.motionAt(title);window.sceneDecorations?.motionAt(shape);window.sceneBranding?.motionAt(brand);window.sceneStyle.captionEnterAt?.(100000);window.sceneStyle.wordFxAt(word);document.querySelectorAll('.precision-text[data-edit-bind="caption"]').forEach(el=>el.style.setProperty('--wfx-p','1'))},{title:g.kind==='hook'?(first+f)/30*1000:100000,shape:f/30*1000,brand:(first+f)/30*1000,word:f/30*1000});
          await twoFrames(page);await materialize(page);
          span.file=`scene-style-capcut-${index}-${String(f).padStart(4,'0')}.png`;
          await page.screenshot({path:path.join(request.output,span.file),clip:{x:0,y:0,width:1080,height:1920},omitBackground:true});
        }
      }
      const camera=isCamera?await page.evaluate(({first,end})=>Array.from({length:end-first},(_,f)=>window.sceneStyle.cameraAt((first+f)/30*1000)),{first,end}):null;
      layers.push({...g,file,animation,camera,...(wordSpans?{wordSpans}:{}),...(enter?{enterMs:enter}:{})});   // enterMs = 이 장면 자막 등장 길이(표식 — 자막팩 칸 판정 점검이 읽는다)
    }
    if(errors.length)throw new Error(errors.join('\n'));
    fs.writeFileSync(path.join(request.output,'scene-style-layers.json'),JSON.stringify(layers));
  }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
