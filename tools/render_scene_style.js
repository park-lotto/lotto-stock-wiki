const fs=require('fs'),path=require('path'),{pathToFileURL}=require('url'),puppeteer=require('puppeteer');
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
    for(let index=0;index<request.context.scenes.length;index++){
      if(only&&!only.has(index)){layers.push(null);continue;}
      const g=await page.evaluate(i=>window.sceneStyle.show(i),index);
      await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
      const file=`scene-style-layer-${index}.png`;
      const CAMERA=['zoom-punch','push-in','shake'],isCamera=CAMERA.includes(request.snapshot.hookMotion);
      const duration=(request.snapshot.hookMotion&&!isCamera)||request.snapshot.hookBandMotion||request.snapshot.hookBandRise?await page.evaluate(()=>window.sceneStyle.motionAt(100000)):0;   // 흰 띠 스윽은 줌 펀치와 겹쳐도 프레임별로 찍는다
      // 고정형 자막 등장(0.3초): 훅뿐 아니라 자막이 바뀌는 모든 장면의 시작을 프레임별로 찍는다.
      const enter=(request.snapshot.mode==='continuous'&&request.snapshot.hookBandMotion)||request.snapshot.bodyCaptionMotion?await page.evaluate(()=>window.sceneStyle.captionEnterAt?.(100000)||0):0;
      const moving=await page.evaluate(()=>{const shape=window.sceneDecorations?.motionAt(0),brand=window.sceneBranding?.motionAt(0);return shape||brand||false});
      await page.screenshot({path:path.join(request.output,file),clip:{x:0,y:0,width:1080,height:1920},omitBackground:true});
      const scene=request.context.scenes[index],first=Math.round(scene.start*30),end=Math.round(scene.end*30);
      let animation=null;
      const hookCount=duration>first/30*1000&&g.kind==='hook'?Math.ceil(duration/1000*30)-first+1:0,enterCount=enter?Math.ceil(enter/1000*30)+1:0;
      if(!request.still&&(moving||hookCount||enterCount)){   // still=정지 한 장만(썸네일 핀)
        const count=moving?end-first:Math.min(end-first,Math.max(hookCount,enterCount));
        const pattern=`scene-style-motion-${index}-%04d.png`;
        for(let f=0;f<count;f++){
          await page.evaluate(i=>window.sceneStyle.show(i),index);
          await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
          await page.evaluate(({title,shape,brand,cap})=>{window.sceneStyle.motionAt(title);window.sceneDecorations?.motionAt(shape);window.sceneBranding?.motionAt(brand);if(cap!==null)window.sceneStyle.captionEnterAt?.(cap)},{title:g.kind==='hook'?(first+f)/30*1000:100000,shape:f/30*1000,brand:(first+f)/30*1000,cap:enter?f/30*1000:null});
          await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
          // Materialize the sampled animation state for Chromium's screenshot compositor.
          await page.evaluate(()=>{
            document.querySelectorAll('.scene-decoration,.precision-text,.precision-patch,.scene-brand-ink').forEach(el=>{
              const animations=el.getAnimations();if(!animations.length)return;
              const style=getComputedStyle(el),values={};
              for(const key of ['transform','translate','rotate','scale','opacity','filter','clipPath'])values[key]=style[key];
              animations.forEach(a=>a.cancel());Object.assign(el.style,values);
            });
          });
          await page.screenshot({path:path.join(request.output,pattern.replace('%04d',String(f).padStart(4,'0'))),clip:{x:0,y:0,width:1080,height:1920},omitBackground:true});
        }
        animation={pattern,count};
      }
      const camera=isCamera?await page.evaluate(({first,end})=>Array.from({length:end-first},(_,f)=>window.sceneStyle.cameraAt((first+f)/30*1000)),{first,end}):null;
      layers.push({...g,file,animation,camera});
    }
    if(errors.length)throw new Error(errors.join('\n'));
    fs.writeFileSync(path.join(request.output,'scene-style-layers.json'),JSON.stringify(layers));
  }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
