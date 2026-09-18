// 썰쇼핑형 20종 훅: 흰 띠 보조제목이 있고, '흰 띠 스윽 올라오기'에서 글자와 상자가 함께 올라오는지 검사한다
// (2026-09-18). 모션마다 돌려 팝업·슬라이드·플래시가 흰 띠 글자를 덮어쓰는 회귀도 잡는다.
//   node tools/qa_story20_band_rise.js [url]
const puppeteer = require('puppeteer');
const url = process.argv[2] || 'http://127.0.0.1:8771/out/scene-style-ui-showcase.html?qa=1';
const MOTIONS = ['zoom-punch', 'pop', 'slide', 'flash', 'push-in', 'shake'];
(async () => {
  const browser = await puppeteer.launch({headless: true});
  const page = await browser.newPage();
  await page.setViewport({width: 1920, height: 1100});
  await page.goto(url, {waitUntil: 'networkidle0'});
  await page.click('[data-template-mode="story"]');
  const count = await page.$$eval('[data-p20]', els => els.length);
  let fail = 0;
  for (let i = 0; i < count; i++) {
    await page.click(`[data-p20="${i}"]`);
    for (const m of MOTIONS) {
      const r = await page.evaluate(async (m) => {
        const wait = ms => new Promise(res => setTimeout(res, ms));
        document.querySelector(`[data-hook-motion="${m}"]`).click();
        const rb = document.querySelector('[data-hook-band-rise]');
        if (!/켜짐/.test(rb.textContent)) rb.click();
        await wait(40);
        const layer = document.querySelector('.precision-edit-layer');
        const band = [...layer.querySelectorAll('.precision-text')].find(el => el.dataset.editBind === 'bodyTitle');
        if (!band) return {err: '흰 띠 글자 없음'};
        window.sceneStyle.motionAt(100000); await wait(20);
        const T = band.getBoundingClientRect();
        const box = [...layer.querySelectorAll('.precision-patch')].find(el => {
          const b = el.getBoundingClientRect();
          return b.width > 0 && b.top <= T.top + 2 && b.bottom >= T.bottom - 2 && b.height <= T.height * 2.2;
        });
        if (!box) return {err: '흰 띠 상자 없음'};
        const at = t => { window.sceneStyle.motionAt(t); return [band.getBoundingClientRect().top, box.getBoundingClientRect().top, +getComputedStyle(band).opacity, +getComputedStyle(box).opacity]; };
        const s = at(0), e = at(100000);
        // 천천히 확대는 화면 전체를 키워 높이가 다른 두 요소가 화면상 조금 다르게 움직인다 — 글자-상자 간격으로 본다
        //   (간격도 확대 배율만큼 커지므로 카메라 배율로 나눠 비교한다).
        const cam = document.querySelector('.scene-camera');
        const zoom = cam ? (new DOMMatrix(getComputedStyle(cam).transform).a || 1) : 1;
        const gapS = s[0] - s[1], gapE = (e[0] - e[1]) / zoom;
        return {textMove: Math.round(s[0] - e[0]), boxMove: Math.round(s[1] - e[1]), gapDrift: +(gapS - gapE).toFixed(1), zoom: +zoom.toFixed(3), op: [s[2], e[2], s[3], e[3]].map(v => v.toFixed(2)).join('/'),
                overflow: band.scrollWidth > band.clientWidth + 2, anims: band.getAnimations().length, name: document.querySelector(`[data-p20].active, [data-p20][aria-pressed="true"]`)?.textContent?.trim().slice(0, 12)};
      }, m);
      const ok = !r.err && r.textMove > 20 && Math.abs(r.gapDrift) <= 1.5 && r.op === '0.00/1.00/0.00/1.00' && !r.overflow;
      if (!ok) fail++;
      if (!ok) console.log(ok ? 'OK ' : 'NG ', String(i).padStart(2), m.padEnd(10), JSON.stringify(r));
    }
  }
  console.log(fail ? `실패 ${fail}건` : `전부 통과 (${count}종 × ${MOTIONS.length}모션)`);
  await browser.close();
  process.exit(fail ? 1 : 0);
})().catch(e => { console.error(e); process.exit(1); });
