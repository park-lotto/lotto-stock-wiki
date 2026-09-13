const assert=require('node:assert/strict'),path=require('node:path');
const p=require(require.resolve('puppeteer',{paths:[path.resolve(__dirname,'../../../..')]}));
const pause=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{const b=await p.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--enable-unsafe-swiftshader']});try{
 const page=await b.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.setViewport({width:1650,height:1050});await page.goto('http://127.0.0.1:8931/campus/');await page.waitForSelector('body[data-ready=true]');await pause(1500);
 assert.equal(await page.evaluate(()=>campusDiagnostics().buildings),12);
 for(const view of ['front','left','rear','hq','shortem']){await page.click(`[data-view="${view}"]`);await pause(1250);await page.screenshot({path:path.resolve(__dirname,`../.artifacts/campus-a-${view}.png`)});}
 await page.click('[data-view="front"]');await pause(1200);const dayCamera=await page.evaluate(()=>campusDiagnostics().camera);await page.click('#night');await pause(800);
 assert.equal(await page.evaluate(()=>campusDiagnostics().night),true);const nightCamera=await page.evaluate(()=>campusDiagnostics().camera);assert(Math.hypot(...dayCamera.map((v,i)=>v-nightCamera[i]))<.001);
 await page.screenshot({path:path.resolve(__dirname,'../.artifacts/campus-a-night.png')});
 await page.click('#compare');assert(await page.$eval('#reference img',e=>e.complete&&e.naturalWidth>1000));await page.click('#close-reference');
 await page.mouse.move(900,600);await page.mouse.down();await page.mouse.move(1070,630,{steps:10});await page.mouse.up();await pause(500);assert.equal(await page.evaluate(()=>campusDiagnostics().view),'free');
 // Keep emulation mode unchanged: changing isMobile reloads the page and resets night.
 await page.setViewport({width:390,height:844});await pause(700);await page.click('[data-view="front"]');await pause(1200);assert.equal(await page.evaluate(()=>campusDiagnostics().night),true);assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:path.resolve(__dirname,'../.artifacts/campus-a-mobile.png')});
 assert.deepEqual(errors,[]);console.log('PASS A campus: 12 buildings, 5 views, day/night same camera, reference, orbit, mobile, no errors');console.log(await page.evaluate(()=>campusDiagnostics()));
}finally{await b.close();}})().catch(e=>{console.error(e);process.exitCode=1});
