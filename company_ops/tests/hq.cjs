// Browser proof for the isolated, read-only 3D preview.
const path=require('path'),assert=require('node:assert/strict'),fs=require('fs');
const puppeteer=require(require.resolve('puppeteer',{paths:[path.resolve(__dirname,'../../../..'),process.cwd()]}));
const base=process.env.COMPANY_OPS_URL;
if(base!=='http://127.0.0.1:8923')throw Error('전용 HQ 검토 서버 http://127.0.0.1:8923 필요');
const artifacts=path.resolve(__dirname,'../.artifacts');fs.mkdirSync(artifacts,{recursive:true});
const pause=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 const browser=await puppeteer.launch({executablePath:process.env.COMPANY_OPS_BROWSER||'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.setViewport({width:1600,height:1000});await page.goto(base+'/hq/');await page.waitForSelector('body[data-ready=true]');await pause(1200);
  const initial=await page.evaluate(()=>hqDiagnostics());assert.equal(initial.visibleFloors,5);assert.equal(initial.team,null);
  await page.screenshot({path:path.join(artifacts,'hq-overview.png')});
  await page.click('#floors [data-team="improve"]');await pause(1300);let d=await page.evaluate(()=>hqDiagnostics());assert.equal(d.team,'improve');assert.equal(d.visibleFloors,4);
  await page.screenshot({path:path.join(artifacts,'hq-department.png')});
  // Actual projected robot click, not calling scene functions.
  const point=d.workerPoints.find(w=>w.id==='improve-2');await page.mouse.click(point.x,point.y);await pause(1300);
  assert.equal((await page.evaluate(()=>hqDiagnostics())).worker,'improve-2');assert((await page.$eval('#panel',e=>e.textContent)).includes('실제 세션'));
  await page.screenshot({path:path.join(artifacts,'hq-worker.png')});
  await page.click('#home');await pause(1200);assert.equal((await page.evaluate(()=>hqDiagnostics())).visibleFloors,5);
  const before=await page.evaluate(()=>hqDiagnostics().camera);await page.mouse.move(700,450);await page.mouse.wheel({deltaY:-150});await pause(350);assert.notDeepEqual(await page.evaluate(()=>hqDiagnostics().camera),before);
  await page.mouse.move(700,450);await page.mouse.down();await page.mouse.move(810,450,{steps:12});await page.mouse.up();assert.equal((await page.evaluate(()=>hqDiagnostics())).team,null);
  await page.click('#orbit');const orbitBefore=await page.evaluate(()=>hqDiagnostics().camera);await page.mouse.move(700,450);await page.mouse.down();await page.mouse.move(800,480,{steps:10});await page.mouse.up();await pause(300);assert.notDeepEqual(await page.evaluate(()=>hqDiagnostics().camera),orbitBefore);assert.equal((await page.evaluate(()=>hqDiagnostics())).team,null);
  await page.emulateMediaFeatures([{name:'prefers-reduced-motion',value:'reduce'}]);await pause(60);assert((await page.evaluate(()=>hqDiagnostics())).reduced);
  await page.click('#home');await page.click('#floors [data-team="qa"]');assert.equal((await page.evaluate(()=>hqDiagnostics())).team,'qa');
  // Real saved record through the existing API. This writes only to the explicit test DB.
  if(process.env.COMPANY_OPS_E2E==='1'){
    const created=await page.evaluate(async()=>{const r=await fetch('/api/projects',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({company_id:'makers',team_id:'improve',owner:'검토 전용',title:'[3D 검토 시험] 저장 업무 연결 '+Date.now(),description:'화면 연결 시험이며 실업무/대표 지시가 아닙니다.'})});if(!r.ok)throw Error('fixture create');return r.json();});
    await page.reload();await page.waitForSelector('body[data-ready=true]');await page.click('#floors [data-team="improve"]');
    await page.click('[data-project="'+created.id+'"]');await page.waitForSelector('.event');assert((await page.$eval('#panel',e=>e.textContent)).includes(created.title));await page.screenshot({path:path.join(artifacts,'hq-saved-work.png')});
  }
  // Fail the data boundary: the view must not continue claiming a fresh connection.
  await page.setRequestInterception(true);let fail=false;page.on('request',r=>fail&&r.url().endsWith('/api/state')?r.respond({status:503,body:'unavailable'}):r.continue());fail=true;
  await page.waitForFunction(()=>document.querySelector('#connection').textContent.includes('조회 실패'),{timeout:14000});fail=false;await page.waitForFunction(()=>!document.querySelector('#connection').textContent.includes('조회 실패'),{timeout:14000});
  await page.setViewport({width:900,height:1100});await page.click('#home');await pause(500);assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:path.join(artifacts,'hq-tablet.png')});
  await page.setViewport({width:390,height:844,isMobile:true,hasTouch:true,deviceScaleFactor:1});await page.reload();await page.waitForSelector('body[data-ready=true]');await pause(500);assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:path.join(artifacts,'hq-mobile.png'),fullPage:true});
  const cdp=await page.createCDPSession();const touch=(type,points)=>cdp.send('Input.dispatchTouchEvent',{type,touchPoints:points});
  const mobileBefore=await page.evaluate(()=>hqDiagnostics().camera);
  await touch('touchStart',[{x:230,y:360,id:1}]);await touch('touchMove',[{x:280,y:390,id:1}]);await touch('touchEnd',[]);await pause(300);
  assert.notDeepEqual(await page.evaluate(()=>hqDiagnostics().camera),mobileBefore);assert.equal((await page.evaluate(()=>hqDiagnostics())).team,null);
  const pinchBefore=await page.evaluate(()=>hqDiagnostics().camera);
  await touch('touchStart',[{x:210,y:310,id:1},{x:290,y:390,id:2}]);await touch('touchMove',[{x:180,y:290,id:1},{x:320,y:420,id:2}]);await touch('touchEnd',[]);await pause(300);
  assert.notDeepEqual(await page.evaluate(()=>hqDiagnostics().camera),pinchBefore);assert.equal((await page.evaluate(()=>hqDiagnostics())).team,null);
  const floor=await page.$('#floors [data-team="improve"]');const box=await floor.boundingBox();await page.touchscreen.tap(box.x+box.width/2,box.y+box.height/2);await pause(300);assert.equal((await page.evaluate(()=>hqDiagnostics())).team,'improve');
  assert.deepEqual(errors,[]);console.log(JSON.stringify({result:'PASS',checks:['WebGL exterior','department','actual robot ray pick','home','wheel','drag no false selection','orbit','reduced motion','saved work and events','API failure and recovery','tablet overflow','mobile overflow','touch pan','pinch','touch selection'],initial:{drawCalls:initial.drawCalls,triangles:initial.triangles,frameMs:initial.frameMs}},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
