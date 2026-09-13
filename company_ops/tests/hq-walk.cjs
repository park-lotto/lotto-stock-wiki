const assert=require('node:assert/strict');
const puppeteer=require('puppeteer');
(async()=>{
 const browser=await puppeteer.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.setViewport({width:1440,height:1000});
  const response=await page.goto('http://127.0.0.1:8931/hq-walk/',{waitUntil:'domcontentloaded',timeout:120000});
  assert.equal(response.status(),200);
  await page.waitForFunction(()=>document.body.dataset.ready==='true',{timeout:120000});
  let d=await page.evaluate(()=>window.hqWalkDiagnostics());assert(d.meshes>0);assert(d.triangles>1000);assert.equal(d.mode,'orbit');
  const before=d.camera;
  await page.mouse.move(800,500);await page.mouse.down();await page.mouse.move(1000,500,{steps:10});await page.mouse.up();
  d=await page.evaluate(()=>window.hqWalkDiagnostics());assert.notDeepEqual(d.camera,before);
  await page.screenshot({path:'company_ops/.artifacts/hq-walk-orbit.png'});
  // 위치 바로가기 option이 마크업 오타로 조용히 사라지면 select가 아무것도 못 고른다(2026-09-13 실사고).
  const options=await page.evaluate(()=>[...document.querySelectorAll('#place option')].map(o=>o.value).filter(Boolean));
  assert.deepEqual(options,['entrance','lobby','office','lounge','stairs','mezzanine','meeting','third'],'위치 바로가기 목록이 코드의 places와 어긋남');
  await page.select('#place','entrance');
  assert.equal((await page.evaluate(()=>window.hqWalkDiagnostics())).mode,'walk','위치 선택은 보행 모드로 전환해야 한다');
  d=await page.evaluate(()=>window.hqWalkDiagnostics());const start=d.feet;
  await page.keyboard.down('KeyW');await new Promise(r=>setTimeout(r,3000));await page.keyboard.up('KeyW');
  d=await page.evaluate(()=>window.hqWalkDiagnostics());assert(d.feet.z<start.z-2,'Walking must move camera');
  await page.screenshot({path:'company_ops/.artifacts/hq-walk-entry.png'});
  await page.select('#place','lobby');await page.keyboard.down('KeyW');await new Promise(r=>setTimeout(r,700));await page.keyboard.up('KeyW');
  await page.screenshot({path:'company_ops/.artifacts/hq-walk-lobby.png'});
  await page.select('#place','office');await page.screenshot({path:'company_ops/.artifacts/hq-walk-office.png'});
  await page.click('#night');assert((await page.evaluate(()=>window.hqWalkDiagnostics())).night);
  await page.click('#orbit');assert.equal((await page.evaluate(()=>window.hqWalkDiagnostics())).mode,'orbit');
  await page.screenshot({path:'company_ops/.artifacts/hq-walk-night.png'});
  await page.setViewport({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.screenshot({path:'company_ops/.artifacts/hq-walk-mobile.png'});
  assert.deepEqual(errors,[]);console.log('HQ_WALK_BROWSER_VERIFIED',JSON.stringify(await page.evaluate(()=>window.hqWalkDiagnostics())));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
