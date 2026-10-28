// 고정형 20종 자막칸 디자인(6종 순환) 캡처·대비 검사(2026-09-18). 결과 시트: %TEMP%/continuous20_caption_look.png
//   node tools/qa_continuous_caption_look.js [url]
const puppeteer = require('puppeteer'), path = require('path');
const url = process.argv[2] || 'http://127.0.0.1:8771/out/scene-style-ui-showcase.html?qa=1';
(async () => {
  const b = await puppeteer.launch({headless: true}); const p = await b.newPage(); await p.setViewport({width: 1920, height: 1100});
  await p.goto(url, {waitUntil: 'networkidle0'}); await p.click('[data-template-mode="continuous"]');
  const n = await p.$$eval('[data-p20]', e => e.length); const shots = []; let fail = 0;
  for (let i = 0; i < n; i++) {
    await p.click(`[data-p20="${i}"]`); await p.evaluate(() => document.querySelector('[data-scene-step="1"]')?.click()); await new Promise(r => setTimeout(r, 120));
    const r = await p.evaluate(() => {
      const m = document.querySelector('.caption-mask'), t = document.querySelector('.precision-text[data-edit-bind="caption"]');
      const rg = document.createRange(); rg.selectNodeContents(t); const q = rg.getBoundingClientRect(), mb = m.getBoundingClientRect();
      return {bg: getComputedStyle(m).backgroundImage.slice(0, 40), color: getComputedStyle(t).color, inside: q.left >= mb.left - 1 && q.right <= mb.right + 1 && q.top >= mb.top - 2 && q.bottom <= mb.bottom + 2};
    });
    if (!r.inside) { fail++; console.log('NG 글자가 칸 밖', i, JSON.stringify(r)); }
    const file = path.join(process.env.TEMP, `caplook-${String(i).padStart(2, '0')}.png`);
    const el = await p.$('#a-live-preview'); const box = await el.boundingBox();
    await p.screenshot({path: file, clip: {x: box.x, y: box.y, width: box.width, height: box.height * .45}}); shots.push(file);
  }
  console.log(fail ? `실패 ${fail}건` : `전부 통과 (${n}종, 글자가 칸 안)`); console.log(JSON.stringify(shots.slice(0, 1)));
  await b.close(); process.exit(fail ? 1 : 0);
})().catch(e => { console.error(e); process.exit(1); });
