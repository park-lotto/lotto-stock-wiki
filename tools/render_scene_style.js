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
    await page.addStyleTag({content:'.scene-decoration{outline:none!important}'});
    await page.evaluate(async()=>{await document.fonts.ready;window.sceneStyle.refresh()});
    const layers=[];
    for(let index=0;index<request.context.scenes.length;index++){
      const g=await page.evaluate(i=>window.sceneStyle.show(i),index);
      await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
      const file=`scene-style-layer-${index}.png`;
      const duration=request.snapshot.hookMotion?await page.evaluate(()=>window.sceneStyle.motionAt(100000)):0;
      const moving=await page.evaluate(()=>window.sceneDecorations?.motionAt(0)||false);
      await (await page.$('#a-live-preview')).screenshot({path:path.join(request.output,file),omitBackground:true});
      const scene=request.context.scenes[index],first=Math.round(scene.start*30),end=Math.round(scene.end*30);
      let animation=null;
      if(moving||(duration>first/30*1000&&g.kind==='hook')){
        const count=moving?end-first:Math.min(end-first,Math.ceil(duration/1000*30)-first+1);
        const pattern=`scene-style-motion-${index}-%04d.png`;
        for(let f=0;f<count;f++){
          await page.evaluate(({title,shape})=>{window.sceneStyle.motionAt(title);window.sceneDecorations?.motionAt(shape)},{title:g.kind==='hook'?(first+f)/30*1000:100000,shape:f/30*1000});
          await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
          await (await page.$('#a-live-preview')).screenshot({path:path.join(request.output,pattern.replace('%04d',String(f).padStart(4,'0'))),omitBackground:true});
        }
        animation={pattern,count};
      }
      layers.push({...g,file,animation});
    }
    if(errors.length)throw new Error(errors.join('\n'));
    fs.writeFileSync(path.join(request.output,'scene-style-layers.json'),JSON.stringify(layers));
  }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
