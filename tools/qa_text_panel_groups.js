// 문구/텍스트 탭 접이식 카드 검사(2026-09-18): 안내 상자 숨김 / 카드 4개(훅 모션 효과·빠른 조절·제목·자막) 기본 접힘 /
//   훅 화면에선 자막 카드 숨김·본문에선 보임 / 카드 안 칸이 그대로 동작(제목 입력이 미리보기에 반영) / 감시 무한 반복 없음
const puppeteer = require('puppeteer');
const url = process.argv[2] || 'http://127.0.0.1:8771/out/scene-style-ui-showcase.html';
(async () => {
  const b = await puppeteer.launch({headless: true}); const p = await b.newPage(); await p.setViewport({width: 1920, height: 1200});
  const errors = []; p.on('pageerror', e => errors.push(e.message));
  await p.goto(url, {waitUntil: 'networkidle0'}); await new Promise(r => setTimeout(r, 400));
  const snap = () => p.evaluate(() => ({
    note: getComputedStyle(document.querySelector('.scene-text-panel > .ai-card')).display,
    cards: [...document.querySelectorAll('.scene-text-panel > .text-group')].map(g => ({t: g.querySelector('b').textContent, open: g.open, hidden: g.hidden, hint: g.querySelector('small').textContent, h: Math.round(g.getBoundingClientRect().height)})),
    loose: [...document.querySelector('.scene-text-panel').children].filter(c => !c.classList.contains('text-group') && !c.classList.contains('ai-card') && !c.hidden && c.getBoundingClientRect().height > 0).map(c => c.className)}));
  const hook = await snap();
  // 제목 카드를 펼쳐 입력 → 미리보기 반영
  await p.evaluate(() => { document.querySelector('.text-group[data-group="title"]').open = true; const i = document.querySelector('[data-bind="hook1"]'); i.value = '카드 안 입력 확인'; i.dispatchEvent(new Event('input', {bubbles: true})); });
  await new Promise(r => setTimeout(r, 200));
  const typed = await p.evaluate(() => [...document.querySelectorAll('.precision-text')].some(e => e.textContent.includes('카드 안 입력 확인')));
  await p.evaluate(() => document.querySelector('[data-scene-step="1"]').click()); await new Promise(r => setTimeout(r, 400));
  const body = await snap();
  // 무한 반복 검사: 1초 동안 감시 콜백이 폭주하면 메인 스레드가 막힌다 → 타이머 지연으로 잰다
  const lag = await p.evaluate(() => new Promise(res => { const t0 = performance.now(); setTimeout(() => res(Math.round(performance.now() - t0 - 300)), 300); }));
  console.log(JSON.stringify({hook, body, typed, lag, errors}, null, 1));
  const titles = hook.cards.map(c => c.t).join();
  const ok = hook.note === 'none' && titles === '훅 모션 효과,빠른 조절,제목,자막' && hook.cards.every(c => !c.open)
    && hook.cards.find(c => c.t === '자막').hidden === true && body.cards.find(c => c.t === '자막').hidden === false
    && !hook.loose.length && !body.loose.length && typed && lag < 150 && !errors.length;
  console.log(ok ? '전부 통과' : '실패'); await b.close(); process.exit(ok ? 0 : 1);
})().catch(e => { console.error(e); process.exit(1); });
