const puppeteer = require('puppeteer');
const path = require('path');

(async()=>{
  const browser=await puppeteer.launch({headless:true});
  const page=await browser.newPage();
  await page.setViewport({width:1920,height:1000});
  const failures=[],shots=[];
  page.on('pageerror',e=>failures.push(String(e)));
  await page.goto('http://127.0.0.1:8770/out/scene-style-ui-showcase.html?qa=1&revision=51',{waitUntil:'networkidle0'});
  const settle=()=>page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
  for(const mode of ['story','continuous']){
    await page.click(`[data-template-mode="${mode}"]`);
    const rows=await page.evaluate(mode=>(mode==='story'?window.PRECISION20:window.CONTINUOUS20).map(p=>({id:p.id,name:p.name})),mode);
    for(const kind of ['hook','body']){
      for(let i=0;i<rows.length;i++){
        await page.click(`[data-p20="${i}"]`);
        if(mode==='story')await page.click(`[data-frame="${kind}"]`);
        else await page.evaluate(kind=>{
          const wanted=kind==='hook'?1:2;
          let current=Number(document.querySelector('[data-scene-current]').textContent);
          while(current!==wanted){document.querySelector(`[data-scene-step="${current>wanted?-1:1}"]`).click();current=Number(document.querySelector('[data-scene-current]').textContent);}
        },kind);
        await settle();await page.evaluate(()=>document.fonts.ready);
        const errors=await page.evaluate(kind=>{
          const p=document.querySelector('#a-live-preview'),bounds=p.getBoundingClientRect(),errors=[];
          const texts=[...p.querySelectorAll('.precision-text')];
          if(kind==='body'&&!texts.some(e=>e.dataset.editBind==='caption'&&e.textContent.trim()))errors.push('본문 자막 없음');
          for(const el of texts){const s=getComputedStyle(el),r=document.createRange();r.selectNodeContents(el);const b=r.getBoundingClientRect();
            if(b.left<bounds.left-2||b.right>bounds.right+2||b.top<bounds.top-2||b.bottom>bounds.bottom+2)errors.push(`${el.dataset.editBind} 글자 경계 초과`);
            if(s.textShadow!=='none'||parseFloat(s.webkitTextStrokeWidth)>1.21)errors.push('두꺼운 테두리/그림자');
            if(!document.fonts.check(`${s.fontWeight} 24px ${s.fontFamily.split(',')[0]}`,'한글제목'))errors.push('서체 미로드');
          }
          const media=p.querySelector('.precision-media').getBoundingClientRect();if(media.height<bounds.height*.35)errors.push('영상 영역 부족');
          return errors;
        },kind);
        failures.push(...errors.map(e=>`${mode}/${rows[i].id}/${kind}: ${e}`));
        const buffer=await (await page.$('#a-live-preview')).screenshot();
        shots.push({label:`${mode} · ${rows[i].name} · ${kind}`,data:buffer.toString('base64')});
      }
    }
  }
  const contact=await browser.newPage();await contact.setViewport({width:1320,height:620});
  for(let i=0;i<shots.length;i+=4){
    await contact.setContent(`<html><body style="margin:0;background:#19212c;color:white;display:flex;gap:10px;padding:5px;font:14px sans-serif">${shots.slice(i,i+4).map(s=>`<div><p>${s.label}</p><img width="320" src="data:image/png;base64,${s.data}"></div>`).join('')}</body></html>`);
    await contact.screenshot({path:path.join(process.env.TEMP,`typography-audit-${String(i/4).padStart(2,'0')}.png`)});
  }
  console.log(JSON.stringify({screens:shots.length,contactSheets:shots.length/4,failures},null,2));
  await browser.close();process.exit(failures.length?1:0);
})().catch(e=>{console.error(e);process.exit(1)});
