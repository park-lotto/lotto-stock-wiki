// 고정형 20종: 자막 기본 크기(템플릿 값의 82%)와 '자막 등장' 효과(스윽/확대 0.3초)가 자막 글자·가림막을 함께 움직이는지 검사(2026-09-18)
//   node tools/qa_continuous_caption_enter.js [url]
const puppeteer = require('puppeteer');
const url = process.argv[2] || 'http://127.0.0.1:8771/out/scene-style-ui-showcase.html?qa=1';
(async () => {
  const b = await puppeteer.launch({headless: true}); const p = await b.newPage(); await p.setViewport({width: 1920, height: 1100});
  await p.goto(url, {waitUntil: 'networkidle0'}); await p.click('[data-template-mode="continuous"]');
  const n = await p.$$eval('[data-p20]', e => e.length); let fail = 0; const sizes = [];
  for (let i = 0; i < n; i++) {
    await p.click(`[data-p20="${i}"]`);
    for (const bm of ['rise', 'grow']) {
      const r = await p.evaluate(async bm => {
        const wait = ms => new Promise(res => setTimeout(res, ms));
        document.querySelector(`[data-hook-band-motion="${bm}"]`).click(); await wait(60);
        const label = document.querySelector('.hook-band-motion > span')?.textContent;
        const pv = document.querySelector('#a-live-preview').getBoundingClientRect();
        const text = document.querySelector('.precision-text[data-edit-bind="caption"]'), mask = document.querySelector('.caption-mask');
        if (!text || !mask) return {err: '자막/가림막 없음', label};
        const at = t => { window.sceneStyle.captionEnterAt(t); const a = text.getBoundingClientRect(), m = mask.getBoundingClientRect();
          return {ty: a.top, my: m.top, tw: a.width, mw: m.width, op: +getComputedStyle(text).opacity, mop: +getComputedStyle(mask).opacity}; };
        const s = at(0), e = at(100000);
        return {label, font: +(parseFloat(getComputedStyle(text).fontSize) / pv.height * 100).toFixed(2),
          move: +(s.ty - e.ty).toFixed(1), maskMove: +(s.my - e.my).toFixed(1), tScale: +(e.tw / s.tw).toFixed(3), mScale: +(e.mw / s.mw).toFixed(3),
          op: [s.op, e.op, s.mop, e.mop].map(v => v.toFixed(2)).join('/')};
      }, bm);
      const ok = !r.err && r.label === '자막 등장' && (bm === 'rise'
        ? r.move > 10 && Math.abs(r.move - r.maskMove) <= 1 && r.op === '0.00/1.00/0.00/1.00'
        : Math.abs(r.tScale - 1 / .84) < .02 && Math.abs(r.tScale - r.mScale) < .01 && r.op === '1.00/1.00/1.00/1.00');
      if (!ok) { fail++; console.log('NG', i, bm, JSON.stringify(r)); }
      if (bm === 'rise') sizes.push(r.font);
    }
  }
  console.log('자막 글자 크기(화면 높이 %):', [...new Set(sizes)].join(', '));
  console.log(fail ? `실패 ${fail}건` : `전부 통과 (${n}종 × 스윽·확대)`);
  await b.close(); process.exit(fail ? 1 : 0);
})().catch(e => { console.error(e); process.exit(1); });
