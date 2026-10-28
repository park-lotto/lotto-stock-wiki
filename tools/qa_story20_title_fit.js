// 썰쇼핑형 20종 훅: 허용 최대 길이 제목(첫 줄 11자·둘째 줄 10자)이 화면 안에 들어가는지 검사(2026-09-18, 둘째 줄 잘림 실사고 뒤)
//   node tools/qa_story20_title_fit.js [url]
const puppeteer = require('puppeteer');
const url = process.argv[2] || 'http://127.0.0.1:8771/out/scene-style-ui-showcase.html?qa=1';
const H1 = '제조사도 몰랐던 반전', H2 = '기차 케이크 반전법';   // 11자 / 10자(공백 포함)
(async () => {
  const b = await puppeteer.launch({headless: true}); const p = await b.newPage(); await p.setViewport({width: 1920, height: 1100});
  await p.goto(url, {waitUntil: 'networkidle0'}); await p.click('[data-template-mode="story"]');
  const n = await p.$$eval('[data-p20]', e => e.length); let fail = 0;
  for (let i = 0; i < n; i++) {
    await p.click(`[data-p20="${i}"]`);
    const r = await p.evaluate(async (h1, h2) => {
      const set = (k, v) => { const el = document.querySelector(`.layout-a [data-bind="${k}"]`); if (el) { el.value = v; el.dispatchEvent(new Event('input', {bubbles: true})); } };
      set('hook1', h1); set('hook2', h2); await new Promise(r => setTimeout(r, 60));
      const pv = document.querySelector('#a-live-preview').getBoundingClientRect();
      return [...document.querySelectorAll('.precision-text')].filter(x => /^hook[12]$/.test(x.dataset.editBind)).map(x => {
        const rg = document.createRange(); rg.selectNodeContents(x); const q = rg.getBoundingClientRect();
        return {bind: x.dataset.editBind, l: Math.round(q.left - pv.left), r: Math.round(pv.right - q.right)};
      });
    }, H1, H2);
    const bad = r.filter(x => x.l < 0 || x.r < 0);
    if (bad.length) { fail++; console.log('NG', i, JSON.stringify(r)); }
  }
  console.log(fail ? `잘림 ${fail}종` : `전부 화면 안 (${n}종)`); await b.close(); process.exit(fail ? 1 : 0);
})().catch(e => { console.error(e); process.exit(1); });
