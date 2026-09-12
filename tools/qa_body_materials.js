const fs=require('fs'),path=require('path'),puppeteer=require('puppeteer');
const root=path.resolve(__dirname,'..');
(async()=>{
 const browser=await puppeteer.launch({headless:true});const page=await browser.newPage();
 const errors=[],shots=[];page.on('pageerror',e=>errors.push(e.message));
 await page.setViewport({width:1920,height:1000});
 await page.goto('http://127.0.0.1:8767/out/scene-style-ui-showcase.html?qa=1&revision=52',{waitUntil:'networkidle0'});
 await page.evaluate(()=>document.fonts.ready);
 const rows=await page.evaluate(()=>window.PRECISION20.map(p=>({id:p.id,name:p.name,design:p.body.design_label})));
 for(let i=0;i<rows.length;i++){
  await page.click(`[data-p20="${i}"]`);await page.click('[data-frame="body"]');
  await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
  const findings=await page.evaluate(()=>{
   const p=document.querySelector('#a-live-preview'),b=p.getBoundingClientRect(),errors=[];
   if(![...p.querySelectorAll('.body-material')].some(e=>getComputedStyle(e).backgroundImage.includes('gradient')))errors.push('색효과 없음');
   for(const key of ['channel','bodyTitle','caption']){
    const el=p.querySelector(`.precision-text[data-edit-bind="${key}"]`);if(!el?.textContent.trim()){errors.push(`${key} 없음`);continue;}
    const range=document.createRange();range.selectNodeContents(el);const r=range.getBoundingClientRect();
    if(r.left<b.left-2||r.right>b.right+2||r.top<b.top-2||r.bottom>b.bottom+2)errors.push(`${key} 화면 초과`);
   }
   const media=p.querySelector('.precision-media').getBoundingClientRect();
   if(media.height<b.height*.4)errors.push('영상 영역 40% 미만');
   const textRects=['channel','bodyTitle','caption'].map(key=>{const el=p.querySelector(`.precision-text[data-edit-bind="${key}"]`);if(!el)return null;const r=document.createRange();r.selectNodeContents(el);return {key,rect:r.getBoundingClientRect()};}).filter(Boolean);
   for(let a=0;a<textRects.length;a++)for(let c=a+1;c<textRects.length;c++){
    const x=textRects[a],y=textRects[c];if(Math.min(x.rect.bottom,y.rect.bottom)-Math.max(x.rect.top,y.rect.top)>2&&Math.min(x.rect.right,y.rect.right)-Math.max(x.rect.left,y.rect.left)>2)errors.push(`${x.key}/${y.key} 겹침`);
   }
   return errors;
  });errors.push(...findings.map(e=>rows[i].id+': '+e));
  const buffer=await (await page.$('#a-live-preview')).screenshot();
  shots.push({...rows[i],data:buffer.toString('base64')});
  if(process.argv.includes('--thumbnails'))fs.writeFileSync(path.join(root,'out/assets/scene-style/thumbnails',`story-${rows[i].id}-body.png`),buffer);
  // 입력, 프레임 전환, 설정 저장에 실제 사용자 값을 넘긴다.
  const input=await page.$('.layout-a [data-bind="bodyTitle"]');
  await input.click({clickCount:3});await input.type('이렇게 편해지는 생활의 작은 발견');
  await page.click('[data-frame="hook"]');await page.click('[data-frame="body"]');
  const restored=await page.$eval('#a-live-preview .precision-text[data-edit-bind="bodyTitle"]',e=>e.textContent);
  if(!restored.includes('생활의 작은 발견'))errors.push(rows[i].id+': 입력 전환 유실');
 }
 await page.goto('http://127.0.0.1:8767/out/scene-style-ui-showcase.html?qa=1&preset=13&frame=body',{waitUntil:'networkidle0'});
 if(!await page.$('#a-live-preview.is-body'))errors.push('본문 직접 링크 실패');
 const before=await page.$eval('.body-material[data-edit-bind="caption"]',e=>parseFloat(e.style.top));
 await page.click('.layout-a [data-caption-position="-1"]');
 const after=await page.$eval('.body-material[data-edit-bind="caption"]',e=>parseFloat(e.style.top));
 if(Math.abs(before-after-6)>.01)errors.push('영상 위 자막 배경 이동 불일치');
 await page.click('.layout-a .secondary');
 const saved=await page.evaluate(()=>JSON.parse(localStorage.getItem('scene_style_preset')));
 if(saved.presetId!=='t13'||saved.frameKind!=='body')errors.push('현재 본문 설정 저장 실패');
 const contact=await browser.newPage();await contact.setViewport({width:1440,height:850});
 await contact.setContent(`<body style="margin:0;padding:16px;background:#1B222D;color:#fff;display:grid;grid-template-columns:repeat(5,1fr);gap:16px;font:14px sans-serif">${shots.map(p=>`<div><p>${p.id} ${p.name}<br><small>${p.design}</small></p><img width="265" src="data:image/png;base64,${p.data}"></div>`).join('')}</body>`);
 await contact.screenshot({path:path.join(process.env.TEMP,'body-designed-all.png'),fullPage:true});
 for(let i=0;i<shots.length;i+=4){
  await contact.setViewport({width:1340,height:650});
  await contact.setContent(`<body style="margin:0;padding:8px;background:#1B222D;color:white;display:flex;gap:12px;font:14px sans-serif">${shots.slice(i,i+4).map(p=>`<div><p>${p.id} ${p.design}</p><img width="320" src="data:image/png;base64,${p.data}"></div>`).join('')}</body>`);
  await contact.screenshot({path:path.join(process.env.TEMP,`body-designed-${i/4}.png`),fullPage:true});
 }
 await browser.close();console.log(JSON.stringify({count:rows.length,errors},null,2));process.exitCode=errors.length?1:0;
})().catch(e=>{console.error(e);process.exit(1)});
