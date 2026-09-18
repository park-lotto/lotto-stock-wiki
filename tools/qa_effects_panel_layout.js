// 효과 패널 배치 검사(2026-09-18): 모션 3개씩 2줄 / 흰 띠·속도 버튼 왼쪽 정렬 / 가림막은 흐림·그라데이션만, 조절은 투명도만 /
//   가림막 다음 스티커를 고르면 크기·회전이 다시 보인다
const puppeteer = require('puppeteer');
const url = process.argv[2] || 'http://127.0.0.1:8771/out/scene-style-ui-showcase.html';
(async () => {
  const b = await puppeteer.launch({headless: true}); const p = await b.newPage(); await p.setViewport({width: 1920, height: 1200});
  const errors = []; p.on('pageerror', e => errors.push(e.message));
  await p.goto(url, {waitUntil: 'networkidle0'});
  const r = await p.evaluate(async () => {
    const wait = ms => new Promise(res => setTimeout(res, ms));
    const rows = el => [...new Set([...el.querySelectorAll('button')].map(x => Math.round(x.getBoundingClientRect().top)))].length;
    const grid = document.querySelector('.hook-motion-grid');
    const perRow = [...grid.querySelectorAll('button')].filter(x => Math.round(x.getBoundingClientRect().top) === Math.round(grid.querySelector('button').getBoundingClientRect().top)).length;
    const leftGap = sel => { const row = document.querySelector(sel), lab = row.querySelector('span').getBoundingClientRect(), btn = row.querySelector('button').getBoundingClientRect(); return Math.round(btn.left - lab.right); };
    const out = {motionRows: rows(grid), motionPerRow: perRow, bandGap: leftGap('.hook-band-motion'), speedGap: leftGap('.hook-speed:not(.hook-band-motion)')};
    [...document.querySelectorAll('button')].find(x => x.textContent.trim() === '효과')?.click(); await wait(150);
    out.maskButtons = [...document.querySelectorAll('[data-add-mask]')].map(x => x.textContent);
    document.querySelector('[data-add-mask="blur"]').click(); await wait(100);
    out.maskControls = [...document.querySelectorAll('.dec-edit label')].filter(l => !l.hidden).map(l => l.firstChild.textContent.trim());
    document.querySelector('[data-add-emoji]').click(); await wait(100);
    out.emojiControls = [...document.querySelectorAll('.dec-edit label')].filter(l => !l.hidden).map(l => l.firstChild.textContent.trim());
    return out;
  });
  r.errors = errors; console.log(JSON.stringify(r));
  const ok = r.motionRows === 2 && r.motionPerRow === 3 && r.bandGap < 20 && r.speedGap < 20 && r.maskButtons.join() === '흐림,그라데이션'
    && r.maskControls.join() === '투명도' && r.emojiControls.includes('크기') && r.emojiControls.includes('회전') && !errors.length;
  console.log(ok ? '전부 통과' : '실패'); await b.close(); process.exit(ok ? 0 : 1);
})().catch(e => { console.error(e); process.exit(1); });
