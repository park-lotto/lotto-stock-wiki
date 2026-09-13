const assert = require('node:assert/strict');
const puppeteer = require('puppeteer');
(async()=>{
 const browser=await puppeteer.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 try {
  const page=await browser.newPage();
  const errors=[];
  page.on('pageerror',e=>errors.push(String(e)));
  await page.setViewport({width:1440,height:1000});
  await page.goto('http://127.0.0.1:8931/hq-building/',{waitUntil:'networkidle0'});
  for(const name of ['day','night','entry','lobby','reference']){
   await page.click(`[data-view="${name}"]`);
   await page.waitForFunction(()=>document.querySelector('#view').complete&&document.querySelector('#view').naturalWidth>0);
   assert.equal(await page.$eval(`[data-view="${name}"]`,e=>e.getAttribute('aria-pressed')),'true');
  }
  await page.click('[data-view="day"]');
  await page.screenshot({path:'company_ops/.artifacts/hq-review-desktop.png',fullPage:true});
  await page.setViewport({width:390,height:844});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.screenshot({path:'company_ops/.artifacts/hq-review-mobile.png',fullPage:true});
  assert.deepEqual(errors,[]);
  console.log('HQ_REVIEW_BROWSER_VERIFIED: five images, tabs, mobile width, no page errors');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
