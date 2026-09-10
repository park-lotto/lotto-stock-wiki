const puppeteer = require('puppeteer');

const url = process.argv[2] || 'http://127.0.0.1:8770/out/scene-style-ui-showcase.html?mode=continuous&qa=1';
(async () => {
  const browser = await puppeteer.launch({headless:true});
  const page = await browser.newPage();
  await page.setViewport({width:1920,height:1000});
  const runtimeErrors=[];page.on('pageerror',error=>runtimeErrors.push(String(error)));
  await page.goto(url,{waitUntil:'networkidle0'});
  const report=await page.evaluate(async()=>{
    const failures=[],rows=window.CONTINUOUS20,preview=document.querySelector('#a-live-preview');
    const wait=()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
    if(rows.length!==20)failures.push(`고정형 개수 ${rows.length}`);
    if(document.querySelectorAll('.fixed-card').length!==20)failures.push('고정형 카드 20개 미표시');
    if(!document.querySelector('.layout-a .seg')?.hidden)failures.push('고정형에서 훅/본문 토글 노출');
    for(let i=0;i<rows.length;i++){
      document.querySelector(`[data-p20="${i}"]`).click();await wait();
      const src=preview.querySelector('.precision-base').getAttribute('src');
      if(src!==rows[i].frame_image)failures.push(`${rows[i].name}: 고정 프레임 불일치`);
      const fixed=()=>[...preview.querySelectorAll('[data-edit-bind]:not([data-edit-bind="caption"])')].map(el=>{const r=el.getBoundingClientRect(),s=getComputedStyle(el);return [el.dataset.editBind,r.x,r.y,r.width,r.height,s.fontSize,s.color,s.backgroundColor].join('|')}).sort().join('\n');
      const before=fixed();
      for(const target of [1,5,11]){document.querySelector('[data-scene-current]').textContent=String(target);while(Number(document.querySelector('[data-scene-current]').textContent)<target)document.querySelector('[data-scene-step="1"]').click();await wait();if(fixed()!==before)failures.push(`${rows[i].name}: 장면 이동 시 고정 디자인 변경`);}
      const field=document.querySelector('[data-field-key="hook1"]'),text=field?.querySelector('.precision-text');
      const y0=preview.querySelector('[data-edit-bind="hook1"]')?.getBoundingClientRect().y;
      field?.querySelector('[data-position-step="-1"]')?.click();await wait();
      const y1=preview.querySelector('[data-edit-bind="hook1"]')?.getBoundingClientRect().y;
      if(!(y1<y0))failures.push(`${rows[i].name}: 제목 위 이동 실패`);
      if([...preview.querySelectorAll('[data-edit-bind]')].some(el=>{const a=el.getBoundingClientRect(),b=preview.getBoundingClientRect();return a.left<b.left-3||a.right>b.right+3||el.scrollWidth>el.clientWidth+2}))failures.push(`${rows[i].name}: 글자 넘침`);
    }
    document.querySelector('.layout-a .secondary').click();
    if(!localStorage.getItem('scene_style_preset'))failures.push('현재 설정 저장 실패');
    return {count:rows.length,failures};
  });
  report.runtimeErrors=runtimeErrors;console.log(JSON.stringify(report,null,2));await browser.close();
  process.exit(report.failures.length||runtimeErrors.length?1:0);
})().catch(error=>{console.error(error);process.exit(1)});
