// Read-only browser checks against the explicitly selected review server.
const path=require('path'),assert=require('assert/strict');
const puppeteer=require(path.resolve(__dirname,'../../../../node_modules/puppeteer'));
if(!process.env.COMPANY_OPS_URL)throw Error('검토 서버 URL 필요');
(async()=>{const browser=await puppeteer.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});try{
const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.setViewport({width:1600,height:1100});await page.goto(process.env.COMPANY_OPS_URL+'/static/control.html');await page.waitForSelector('.project');
await page.screenshot({path:path.resolve(__dirname,'../.artifacts/control-overview.png'),fullPage:true});
const title=await page.$eval('.project h3',e=>e.textContent);await page.click('.project-footer button');await page.waitForSelector('.timeline time');assert((await page.$eval('#room-content',e=>e.textContent)).includes(title));assert((await page.$eval('#room-content',e=>e.textContent)).includes('컨펌'));await page.screenshot({path:path.resolve(__dirname,'../.artifacts/control-room.png'),fullPage:true});
await page.reload();await page.waitForSelector('.timeline time');assert((await page.$eval('#room-content h1',e=>e.textContent))===title);
await page.click('#back');await page.waitForFunction(()=>!document.querySelector('#overview').hidden);await page.click('#workers-mode');await page.waitForSelector('.worker-group');assert((await page.$eval('#project-grid',e=>e.textContent)).includes('독립 실행 워커 목록은 아직 미연결'));
await page.click('#projects-mode');await page.type('#search','no-matching-project-917');assert(await page.$('.empty'));await page.$eval('#search',e=>{e.value='';e.dispatchEvent(new Event('input'));});
await page.evaluate(()=>[...document.querySelectorAll('#companies button')].find(b=>b.textContent==='에이치엔엘글로벌').click());await page.waitForFunction(()=>document.querySelector('#project-grid').textContent.includes('현재 조건'));
await page.evaluate(()=>[...document.querySelectorAll('#companies button')].find(b=>b.textContent==='전체 회사').click());await page.waitForSelector('.project');
await page.setViewport({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.click('.project-footer button');await page.waitForSelector('.timeline time');assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
assert.deepEqual(errors,[]);console.log('PASS: 관제→상황실·재열기·역할별·검색·회사 필터·모바일·콘솔 오류 없음');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exit(1);});
