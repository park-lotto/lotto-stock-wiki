const pptr=require('puppeteer'),assert=require('assert');
(async()=>{const b=await pptr.launch({headless:true});try{
 const p=await b.newPage();await p.setViewport({width:1800,height:1400});const errors=[];p.on('pageerror',e=>errors.push(e.message));
 await p.goto('http://127.0.0.1:8767/out/scene-style-ui-showcase.html?qa=1',{waitUntil:'networkidle0'});
 await p.click('[data-frame="body"]');await p.click('[data-caption-placement="free"]');
 const drag=async()=>{const r=await(await p.$('.caption-mask')).boundingBox();await p.mouse.move(r.x+10,r.y+10);await p.mouse.down();await p.mouse.move(r.x+20,r.y+90,{steps:5});await p.mouse.up()};
 await drag();let s=await p.evaluate(()=>sceneStyle.snapshot());assert.equal(Object.keys(s.captionDrags).length,1);
 await p.click('[data-caption-scope="all"]');s=await p.evaluate(()=>sceneStyle.snapshot());assert.equal(Object.keys(s.captionDrags).length,12);assert.equal(new Set(Object.values(s.captionDrags).map(v=>JSON.stringify(v))).size,1);
 const other=s.captionDrags['t11:story:2:caption'];await drag();s=await p.evaluate(()=>sceneStyle.snapshot());assert.deepEqual(s.captionDrags['t11:story:2:caption'],other);assert.notDeepEqual(s.captionDrags['t11:story:1:caption'],other);
 await p.click('.layout-a .edit-pane > .primary');await p.goto('http://127.0.0.1:8767/out/scene-style-ui-showcase.html',{waitUntil:'networkidle0'});assert.deepEqual(await p.evaluate(()=>sceneStyle.snapshot().captionDrags),s.captionDrags);
 await p.screenshot({path:'.tmp/scene-style-qa/caption-scope-controls.png'});
 await p.evaluate(()=>{const s=sceneStyle.snapshot();sceneStyle.load({jobId:'qa',text:{},scenes:[{kind:'hook',beat_idx:0,caption:'first phrase'},{kind:'hook',beat_idx:0,caption:'second phrase'},{kind:'body',beat_idx:1,caption:'next paragraph'}]},s)});
 assert.equal(await p.$eval('.scene-line-editor',e=>!e.hidden),true);await p.$eval('.scene-line-editor',e=>e.open=true);assert.equal(await p.$$eval('[data-line-inputs] input',e=>e.length),2);
 await p.$eval('[data-line-inputs] input',e=>{e.focus();e.setSelectionRange(5,5)});await p.click('[data-lines-split]');assert.equal(await p.$$eval('[data-line-inputs] input',e=>e.length),3);await p.click('[data-lines-merge]');assert.equal(await p.$$eval('[data-line-inputs] input',e=>e.length),2);
 await p.screenshot({path:'.tmp/scene-style-qa/paragraph-lines-scope.png'});assert.deepEqual(errors,[]);console.log(JSON.stringify({ok:true,allScenes:12,isolatedMove:true,restore:true,hookParagraphVisible:true,splitMerge:true}));
}finally{await b.close()}})().catch(e=>{console.error(e);process.exit(1)});
