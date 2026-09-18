// 효과 탭 직접 편집 검사(2026-09-18): 편집 칸이 목록 바로 아래 / 회전 ±180 / 크기·회전 손잡이 끌기 / 배지 두 번 눌러 글자 고치기
//   node tools/qa_decoration_direct_edit.js [url]
const puppeteer = require('puppeteer');
const url = process.argv[2] || 'http://127.0.0.1:8771/out/scene-style-ui-showcase.html';
(async () => {
  const b = await puppeteer.launch({headless: true}); const p = await b.newPage(); await p.setViewport({width: 1920, height: 1200});
  const errors = []; p.on('pageerror', e => errors.push(e.message));
  await p.goto(url, {waitUntil: 'networkidle0'});
  await p.evaluate(() => [...document.querySelectorAll('button')].find(x => x.textContent.trim() === '효과')?.click());
  await new Promise(r => setTimeout(r, 200));
  const res = {};
  // 가림막 추가 → 편집 칸 위치·회전 범위
  await p.click('[data-add-mask="blur"]'); await new Promise(r => setTimeout(r, 100));
  res.edit = await p.evaluate(() => { const items = document.querySelector('.dec-items'), edit = document.querySelector('.dec-edit');
    return {nextToList: items.nextElementSibling === edit, visible: !edit.hidden, heightShown: !document.querySelector('[data-mask-height]').hidden,
            rotRange: [document.querySelector('[data-dec="rot"]').min, document.querySelector('[data-dec="rot"]').max]}; });
  const get = () => p.evaluate(() => { const m = window.sceneStyle.effect().masks; return m[m.length - 1]; });
  const handle = k => p.evaluate(k => { const r = document.querySelector(`[data-handle="${k}"]`).getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }, k);
  const before = await get();
  let [x, y] = await handle('resize'); await p.mouse.move(x, y); await p.mouse.down(); await p.mouse.move(x - 60, y + 40, {steps: 6}); await p.mouse.up();
  const resized = await get(); res.resize = {w: [before.w, +resized.w.toFixed(1)], h: [before.h, +resized.h.toFixed(1)]};
  [x, y] = await handle('rotate'); await p.mouse.move(x, y); await p.mouse.down(); await p.mouse.move(x + 120, y + 60, {steps: 6}); await p.mouse.up();
  res.rotate = (await get()).rot;
  // 배지 추가 → 두 번 눌러 글자 고치기
  await p.evaluate(() => { document.querySelector('[data-dec-kit="badge"]').click(); document.querySelector('[data-add-badge]').click(); }); await new Promise(r => setTimeout(r, 100));
  const badgeText0 = (await get()).text;
  const c = await p.evaluate(() => { const els = document.querySelectorAll('.scene-decoration'); const r = els[els.length - 1].getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; });
  // 사람이 두 번 누르는 것처럼 누름·뗌을 두 번(puppeteer clickCount:2는 누름이 한 번만 가서 검사가 틀린다)
  await p.mouse.move(c[0], c[1]); for (let k = 0; k < 2; k++) { await p.mouse.down(); await p.mouse.up(); await new Promise(r => setTimeout(r, 80)); }
  await p.keyboard.type('오늘만 특가'); await p.keyboard.press('Enter'); await new Promise(r => setTimeout(r, 150));
  res.badge = [badgeText0, (await get()).text];
  res.errors = errors;
  console.log(JSON.stringify(res, null, 1));
  const ok = res.edit.nextToList && res.edit.visible && !res.edit.heightShown &&   /* 가림막은 투명도만(09-18 사장님) */ res.edit.rotRange.join() === '-180,180'
    && res.resize.w[1] < res.resize.w[0] && res.resize.h[1] !== res.resize.h[0] && Math.abs(res.rotate) > 30 && res.badge[1] === '오늘만 특가' && !errors.length;
  console.log(ok ? '전부 통과' : '실패'); await b.close(); process.exit(ok ? 0 : 1);
})().catch(e => { console.error(e); process.exit(1); });
