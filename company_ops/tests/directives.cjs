const path = require('path');
const assert = require('assert/strict');
const puppeteer = require(path.resolve(__dirname, '../../../../node_modules/puppeteer'));
if(process.env.COMPANY_OPS_E2E !== '1' || !process.env.COMPANY_OPS_URL) throw Error('전용 검토 서버와 E2E 승인이 필요합니다.');
(async()=>{
 const browser=await puppeteer.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 try{
 const page=await browser.newPage();await page.setViewport({width:1440,height:1000});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(process.env.COMPANY_OPS_URL+'/static/directives.html');
 await page.waitForFunction(()=>!document.querySelector('#submit').disabled);
 await page.select('#team','improve');
 const title='[접수 검증] 대표 지시 저장 '+new Date().toISOString();
 await page.type('#title',title);await page.type('#description','대표 지시를 제품개선팀에 배정하고 접수 이력을 확인합니다. AI 실행·고객 발송·배포는 하지 않습니다.');
 await page.click('#submit');await page.waitForFunction(()=>document.querySelector('#message').textContent.includes('접수 저장 완료'));
 await page.waitForFunction(()=>document.querySelector('#detail').textContent.includes('접수 업무 배정'));
 assert((await page.$eval('#detail',e=>e.textContent)).includes('Claude'));
 await page.reload();await page.waitForFunction(t=>document.querySelector('#list').textContent.includes(t),{},title);
 await page.evaluate(t=>[...document.querySelectorAll('.job')].find(e=>e.textContent.includes(t)).click(),title);
 await page.waitForFunction(()=>document.querySelector('#detail').textContent.includes('접수 업무 배정'));
 await page.screenshot({path:path.resolve(__dirname,'../.artifacts/directives-desktop.png'),fullPage:true});
 await page.select('#company','hnl');assert(!(await page.$eval('#list',e=>e.textContent)).includes(title));
 await page.setViewport({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 assert.deepEqual(errors,[]);console.log('PASS: 실제 접수·Claude 배정·이력·새로고침 보존·회사 분리·모바일 폭');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
