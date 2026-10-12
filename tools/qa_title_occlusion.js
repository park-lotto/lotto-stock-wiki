// 제목 첫 줄이 머리띠(surfaces·boxes·cleanup_regions·top_band에서 온 면)에 가려지는지 전수 검사(2026-09-22)
//   사장님 결정(09-22): 가려진 제목은 고친다 = 제목이 머리띠 아래로 내려와 글자가 다 보여야 한다.
//   ★판정은 '보이는 것' 기준: 데이터 상자가 아니라 **실제로 화면에 그려진 면**과 글자 잉크 상자를 견준다.
//     (09-21 사고: data-edit-bind 로 캡슐을 찾다 아무것도 못 재고 '전수 통과'를 믿었다)
//   실행: node tools/qa_title_occlusion.js [url]
//         SHOT=폴더 → 가려진 칸만 캡처   SCOPE=story|fixed|all(기본 story)
//   ★이 검사는 고치기 전 코드에서 실패해야 정상이다 — 먼저 그걸 확인하고 믿을 것.
const puppeteer = require('puppeteer'), fs = require('fs');
const url = process.argv[2] || 'http://127.0.0.1:8771/out/scene-style-ui-showcase.html';
const SHOT = process.env.SHOT || '', SCOPE = process.env.SCOPE || 'story';
if (SHOT) fs.mkdirSync(SHOT, { recursive: true });
const wait = ms => new Promise(r => setTimeout(r, ms));

(async () => {
  const browser = await puppeteer.launch({ headless: true });
  const page = await browser.newPage();
  await page.setViewport({ width: 1600, height: 1100, deviceScaleFactor: SHOT ? 2 : 1 });
  await page.setCacheEnabled(false);
  const errors = []; page.on('pageerror', e => errors.push(String(e).slice(0, 140)));
  await page.goto(url, { waitUntil: 'networkidle0' }); await wait(900);

  // 한 칸을 재는 함수 — 제목 글자마다 '위를 덮는 면'이 있는지 본다.
  const measure = () => page.evaluate(() => {
    const pv = document.querySelector('#a-live-preview');
    const P = pv.getBoundingClientRect();
    const pct = r => ({
      top: (r.top - P.top) / P.height * 100, bottom: (r.bottom - P.top) / P.height * 100,
      left: (r.left - P.left) / P.width * 100, right: (r.right - P.left) / P.width * 100,
    });
    // 글자의 실제 잉크 상자(요소 상자가 아니라 글자가 차지한 자리)
    const ink = e => { const g = document.createRange(); g.selectNodeContents(e); return pct(g.getBoundingClientRect()); };
    const zi = e => { const v = parseInt(getComputedStyle(e).zIndex, 10); return Number.isFinite(v) ? v : 0; };

    // 머리띠가 될 수 있는 '그려진 면' 전부 — 네 출처가 흩어져 있어 클래스로 싸잡는다.
    const surfaces = [...pv.querySelectorAll('.precision-patch, .body-material, .body-surface, .precision-surface, .top-band, .cleanup-patch')]
      .filter(e => { const r = e.getBoundingClientRect(); return r.width > 2 && r.height > 2 && getComputedStyle(e).visibility !== 'hidden' && +getComputedStyle(e).opacity > 0.15; })
      .map(e => ({ cls: e.className.toString().slice(0, 40), z: zi(e), ...pct(e.getBoundingClientRect()) }));

    const out = { titles: [], surfaces, cover: [] };
    for (const b of ['hook1', 'hook2', 'bodyTitle']) {
      const e = pv.querySelector('.precision-text[data-edit-bind="' + b + '"]');
      if (!e || e.hidden) continue;
      const r = e.getBoundingClientRect(); if (r.height < 1 || !e.textContent.trim()) continue;
      const box = ink(e), z = zi(e);
      out.titles.push({ bind: b, z, ...box });
      // 이 글자를 덮는 면: 세로로 겹치고, 가로로 겹치고, 글자보다 위에 그려진 것
      for (const s of surfaces) {
        const vOver = Math.min(s.bottom, box.bottom) - Math.max(s.top, box.top);
        const hOver = Math.min(s.right, box.right) - Math.max(s.left, box.left);
        if (vOver > 0.15 && hOver > 1 && s.z >= z) {
          const ratio = vOver / Math.max(0.01, box.bottom - box.top);
          out.cover.push({ bind: b, cls: s.cls, z: s.z, titleZ: z, vOver: +vOver.toFixed(2), ratio: +ratio.toFixed(3) });
        }
      }
    }
    return out;
  });

  const f = v => Math.round(v * 10) / 10;
  const bad = [], seen = [];
  const modes = SCOPE === 'all' ? ['story', 'fixed'] : [SCOPE];

  for (const mode of modes) {
    await page.evaluate(m => { const e = document.querySelector('[data-template-mode="' + m + '"]'); if (e) e.click(); }, mode);
    await wait(450);
    const n = await page.$$eval('[data-p20]', e => e.length);
    for (let i = 0; i < n; i++) {
      await page.evaluate(i => document.querySelector('[data-p20="' + i + '"]').click(), i);
      await wait(320);
      const name = await page.evaluate(() => document.querySelector('[data-stage-name]').textContent.trim().slice(0, 12));
      const scenes = mode === 'story' ? [0, 1] : [0];
      for (const sc of scenes) {
        await page.evaluate(s => { const e = document.querySelector('[data-scene-step="' + (s === 0 ? -1 : 1) + '"]'); if (e) e.click(); }, sc);
        await wait(1500);
        const r = await measure();
        const where = name + '/' + (mode === 'story' ? (sc ? '본문' : '훅') : '고정');
        seen.push(where);
        if (!r.titles.length) continue;
        // 가려짐 = 글자 높이의 8% 이상을 면이 덮는다
        const hits = r.cover.filter(c => c.ratio >= 0.08);
        if (hits.length) {
          const worst = hits.sort((a, b) => b.ratio - a.ratio)[0];
          bad.push(where + ' → ' + worst.bind + ' 가 ' + Math.round(worst.ratio * 100) + '% 가려짐 (' + worst.cls.trim() + ', z ' + worst.z + '≥' + worst.titleZ + ')');
          if (SHOT) {
            const c = await page.evaluate(() => { const q = document.querySelector('#a-live-preview').getBoundingClientRect(); return { x: q.left, y: Math.max(0, q.top), width: q.width, height: q.height * 0.62 }; });
            await page.screenshot({ path: SHOT + '/' + where.replace(/[\/\\.\s]+/g, '_') + '.png', clip: c });
          }
        }
      }
    }
  }

  console.log('검사한 칸: ' + seen.length);
  if (errors.length) console.log('페이지 오류 ' + errors.length + '건: ' + errors.slice(0, 3).join(' | '));
  if (bad.length) { console.log('가려진 칸 ' + bad.length + '개:'); bad.forEach(b => console.log('  NG ' + b)); }
  else console.log('가려진 칸 0개');
  await browser.close();
  process.exit(bad.length ? 1 : 0);
})().catch(e => { console.error(e); process.exit(1); });
