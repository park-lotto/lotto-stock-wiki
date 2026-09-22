// 템플릿 칸의 **기본 화면**(아무것도 안 건드린 상태)을 통째로 찍는다 — 구조를 바꿔도 "같게 나오나"를 픽셀로 비교하기 위한 기준 사진.
//   실행: node tools/qa_default_shots.js <출력폴더> [url]     PRESETS="이븐쇼핑,활용정점." 로 일부만
//   비교: node tools/qa_pixel_diff.js <기준폴더> <새폴더>
const puppeteer=require('puppeteer'),fs=require('fs');
const out=process.argv[2],url=process.argv[3]||'http://127.0.0.1:8771/out/scene-style-ui-showcase.html';
if(!out){console.error('출력폴더를 주세요');process.exit(1);}
const only=(process.env.PRESETS||'').split(',').map(s=>s.trim()).filter(Boolean);
fs.mkdirSync(out,{recursive:true});
const wait=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
  const browser=await puppeteer.launch({headless:true});const page=await browser.newPage();
  await page.setViewport({width:1600,height:1100,deviceScaleFactor:2});await page.setCacheEnabled(false);
  const errors=[];page.on('pageerror',e=>errors.push(String(e).slice(0,140)));
  await page.goto(url,{waitUntil:'networkidle0'});await wait(900);
  // 움직임(훅 모션·자막 등장)이 끝난 뒤 찍는다 — 연속 두 장이 같아질 때까지 기다린다
  const settle=async clip=>{let prev='';for(let i=0;i<14;i++){const cur=await page.screenshot({clip,encoding:'base64'});if(cur===prev)return cur;prev=cur;await wait(350);}return prev;};
  let n=0;
  for(const mode of ['story','continuous']){
    await page.evaluate(m=>{const e=document.querySelector('[data-template-mode="'+m+'"]');if(e)e.click();},mode);await wait(450);
    const count=await page.$$eval('[data-p20]',e=>e.length);
    for(let i=0;i<count;i++){
      await page.evaluate(i=>{const e=document.querySelector('[data-p20="'+i+'"]');if(e)e.click();},i);await wait(320);
      const name=await page.evaluate(()=>{const e=document.querySelector('[data-stage-name]');return e?e.textContent.trim().slice(0,10):''});
      if(only.length&&!only.some(o=>name.startsWith(o)))continue;
      for(const sc of (mode==='story'?[0,1]:[0])){
        await page.evaluate(s=>{const e=document.querySelector('[data-scene-step="'+(s===0?-1:1)+'"]');if(e)e.click();},sc);await wait(600);
        const clip=await page.evaluate(()=>{const r=document.querySelector('#a-live-preview').getBoundingClientRect();return {x:r.left,y:r.top,width:r.width,height:r.height}});
        const b64=await settle(clip);
        fs.writeFileSync(out+'/'+mode+'_'+name.replace(/[\/\\.\s]+/g,'_')+'_'+(sc?'본문':'훅')+'.png',Buffer.from(b64,'base64'));n++;
      }
    }
  }
  console.log(JSON.stringify({찍은칸:n,페이지오류:[...new Set(errors)]}));
  await browser.close();
})().catch(e=>{console.error(String(e).slice(0,300));process.exit(1)});
