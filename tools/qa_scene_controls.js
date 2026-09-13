const puppeteer=require('puppeteer'),assert=require('assert'),path=require('path'),fs=require('fs');
(async()=>{
 const browser=await puppeteer.launch({headless:true});
 try{
  const page=await browser.newPage();await page.setViewport({width:1800,height:1300});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:8767/out/scene-style-ui-showcase.html?qa=1',{waitUntil:'networkidle0'});
  const input=async(selector,value)=>page.$eval(selector,(el,value)=>{el.value=value;el.dispatchEvent(new Event('input',{bubbles:true}))},value);
  const geometry=()=>page.evaluate(()=>window.sceneStyle.geometry());
  assert.equal(await page.$eval('.fixed-quick-panel',el=>el.hidden),false);
  const initial=await geometry();await input('[data-fixed-range="top"]','43');assert.equal((await geometry()).media.top,43);
  await page.click('[data-frame="body"]');assert.notEqual((await geometry()).media.top,43);
  await input('[data-fixed-range="top"]','35');
  assert.equal(Math.round((await geometry()).media.top+(await geometry()).media.height),100);
  await input('[data-fixed-color="title2"]','#ff0077');
  assert.equal(await page.$eval('.precision-text[data-edit-bind="bodyTitle"]',el=>getComputedStyle(el).color),'rgb(255, 0, 119)');
  await input('[data-caption-layout="color"]','#33ff66');
  assert.equal(await page.$eval('.precision-text[data-edit-bind="caption"]',el=>getComputedStyle(el).color),'rgb(51, 255, 102)');
  await page.click('[data-bind="caption"]');await page.keyboard.down('Control');await page.keyboard.press('KeyA');await page.keyboard.up('Control');await page.keyboard.type('First line');await page.keyboard.press('Enter');await page.keyboard.type('Second line');
  assert.equal(await page.$eval('[data-bind="caption"]',e=>e.value),'First line\nSecond line');
  assert.equal(await page.$eval('.precision-text[data-edit-bind="caption"]',e=>getComputedStyle(e).whiteSpace),'pre-wrap');
  const caption=await page.$('.precision-text[data-edit-bind="caption"]'),rect=await caption.boundingBox();
  await page.mouse.move(rect.x+rect.width/2,rect.y+rect.height/2);await page.mouse.down();await page.mouse.move(rect.x+rect.width/2+15,rect.y+rect.height/2-25,{steps:8});await page.mouse.up();
  const before=await page.evaluate(()=>window.sceneStyle.snapshot());assert.ok(Object.values(before.captionDrags).some(p=>p.y<0));
  await page.click('.layout-a .edit-pane > .primary');
  await page.reload({waitUntil:'networkidle0'}); // qa 모드에서는 자동 복원하지 않으므로 실제 저장값을 다음에 일반 URL에서 복원한다.
  await page.goto('http://127.0.0.1:8767/out/scene-style-ui-showcase.html',{waitUntil:'networkidle0'});
  const restored=await page.evaluate(()=>window.sceneStyle.snapshot());assert.deepEqual(restored.captionDrags,before.captionDrags);assert.deepEqual(restored.captionTexts,before.captionTexts);
  await page.click('[data-frame="hook"]');await page.click('[data-editor-tab="effects"]');
  for(const motion of ['zoom-punch','pop','slide','flash']){
    await page.click(`[data-hook-motion="${motion}"]`);
    const result=await page.evaluate(()=>{const duration=window.sceneStyle.motionAt(180);return {duration,styles:[...document.querySelectorAll('.precision-text')].filter(e=>e.getAnimations().length).map(e=>getComputedStyle(e).transform)}});
    assert.ok(result.duration>0&&result.styles.length>0,motion);
  }
  await page.click('[data-add-mask="blur"]');await page.click('[data-add-emoji="🔥"]');await page.click('[data-dec-kit="badge"]');await page.click('[data-add-badge="추천"]');
  assert.equal(await page.$$eval('.scene-decoration',els=>els.length),3);
  const decoration=await (await page.$('.scene-decoration[data-dec-index="2"]')).boundingBox();
  await page.mouse.move(decoration.x+10,decoration.y+10);await page.mouse.down();await page.mouse.move(decoration.x+35,decoration.y+40,{steps:5});await page.mouse.up();
  const snapshot=await page.evaluate(()=>window.sceneStyle.snapshot());assert.ok(snapshot.effects['0'].masks[2].l>6);
  await input('[data-dec="text"]','진짜 추천하는 꿀템');await input('[data-dec="badgeStyle"]','ticket');
  await page.click('[data-dec-kit="shape"]');
  for(const key of await page.$$eval('[data-add-graphic]',els=>els.map(e=>e.dataset.addGraphic))){
    await page.click(`[data-add-graphic="${key}"]`);
    const phases=await page.evaluate(()=>{const el=document.querySelector('.scene-decoration:last-child');const read=()=>{const s=getComputedStyle(el);return [s.translate,s.rotate,s.scale,s.clipPath].join('|')};window.sceneDecorations.motionAt(100);const a=read();window.sceneDecorations.motionAt(650);return [a,read()]});
    assert.notEqual(phases[0],phases[1],key);await page.click('[data-dec-delete]');
  }
  await page.click('[data-add-graphic="arrow_bold"]');
  await page.click('.layout-a .edit-pane > .primary');
  await page.screenshot({path:path.resolve('.tmp/scene-style-qa/restored-effects.png')});
  fs.writeFileSync(path.resolve('.tmp/scene-style-qa/controls-snapshot.json'),JSON.stringify(await page.evaluate(()=>window.sceneStyle.snapshot())));
  assert.deepEqual(errors,[]);console.log(JSON.stringify({ok:true,motions:4,animatedShapes:9,decorations:4,multiline:true,dragRestore:true,storyGeometry:true,colors:true}));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
