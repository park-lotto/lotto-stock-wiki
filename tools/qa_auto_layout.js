// 영상이 들어왔을 때 **자동 배치**가 제대로 되는지 실측(2026-09-22, 사장님 제보).
//   사장님: "영상이 들어오면 자동으로 훅이랑 본문이랑 배치가 되고 제목 소제목 들어가고
//            자막이 본문에 딱 배치가 안 되었었어."
//   재는 것(전부 고객 길 그대로 — MIX_JOB 주입·강제 펼침 없음):
//     ①장면이 훅/본문으로 갈렸나  ②제목(hook1·hook2)·소제목(supportTitle)·본문제목(bodyTitle)이 비었나
//     ③자막이 본문 장면마다 들어갔나(빈 자막 장면이 몇 개인가)  ④자막 글자가 자막칸 안에 있나
//   실행: node tools/qa_auto_layout.js [url]      기본 http://127.0.0.1:8772/produce.html
const puppeteer = require('puppeteer');
const url = process.argv[2] || 'http://127.0.0.1:8772/produce.html';
const wait = ms => new Promise(r => setTimeout(r, ms));

(async () => {
  const b = await puppeteer.launch({ headless: true });
  const p = await b.newPage(); await p.setViewport({ width: 1700, height: 1000 });
  const errs = []; p.on('pageerror', e => errs.push(String(e).slice(0, 140)));
  await p.goto(url, { waitUntil: 'networkidle2', timeout: 90000 }); await wait(2500);

  // 6단계 장면꾸미기로 이동 — 고객이 누르는 그 아이콘
  const moved = await p.evaluate(() => {
    const t = [...document.querySelectorAll('a,button,div,li')]
      .find(e => /장면꾸미기/.test((e.textContent || '').trim()) && e.getBoundingClientRect().height > 10 && e.getBoundingClientRect().height < 140);
    if (!t) return false; t.click(); return true;
  });
  if (!moved) { console.log(JSON.stringify({ 오류: '장면꾸미기 단계 버튼을 못 찾았다', errs })); await b.close(); process.exit(1); }
  await wait(3000);

  const btn = await p.$('[onclick="openSceneStyleEditor()"]');
  const vis = btn && await btn.evaluate(e => !!e.offsetParent);
  if (!vis) { console.log(JSON.stringify({ 오류: '편집 버튼이 안 보인다', errs })); await b.close(); process.exit(1); }
  await btn.evaluate(e => e.scrollIntoView({ block: 'center' })); await btn.click();
  await p.waitForSelector('dialog[open] iframe', { timeout: 30000 });
  const f = await (await p.$('dialog[open] iframe')).contentFrame();
  await f.waitForFunction(() => window.sceneStyle && document.querySelector('#a-live-preview'), { timeout: 60000 });
  await wait(3000);

  const r = await f.evaluate(async () => {
    const wait = ms => new Promise(r => setTimeout(r, ms));
    const ctx = window.sceneStyle.context?.() || null;
    const snap = window.sceneStyle.snapshot?.() || {};
    const scenes = (ctx && ctx.scenes) || [];
    const text = (ctx && ctx.text) || {};
    const out = {
      장면수: scenes.length,
      훅: scenes.filter(s => s.kind === 'hook').length,
      본문: scenes.filter(s => s.kind === 'body').length,
      제목: { hook1: text.hook1 || '', hook2: text.hook2 || '', 소제목: text.supportTitle || '', 본문제목: text.bodyTitle || '' },
      자막있는장면: scenes.filter(s => (s.caption || '').trim()).length,
      자막빈장면: scenes.filter(s => !(s.caption || '').trim()).length,
      presetId: snap.presetId, mode: snap.mode,
      샘플: scenes.slice(0, 6).map(s => ({ kind: s.kind, t: +(+s.start).toFixed(2), cap: (s.caption || '').slice(0, 20) })),
      자막넘침: [],
    };
    // 자막 글자가 자막칸(캡션 마스크) 안에 있는지 — 본문 장면을 돌며 실제로 본다
    const pv = document.querySelector('#a-live-preview');
    const bodyIdx = scenes.map((s, i) => [s, i]).filter(([s]) => s.kind === 'body' && (s.caption || '').trim()).map(([, i]) => i);
    for (const i of bodyIdx.slice(0, 14)) {
      window.sceneStyle.show(i); await wait(230);
      const cap = pv.querySelector('.precision-text[data-edit-bind="caption"]');
      const mask = pv.querySelector('.caption-mask');
      if (!cap || !mask) { out.자막넘침.push({ i, why: !cap ? '자막 글자 없음' : '자막칸 없음' }); continue; }
      const g = document.createRange(); g.selectNodeContents(cap);
      const t = g.getBoundingClientRect(), m = mask.getBoundingClientRect(), P = pv.getBoundingClientRect();
      const pc = v => +(v / P.height * 100).toFixed(2);
      const over = { 위: pc(m.top - t.top), 아래: pc(t.bottom - m.bottom) };
      if (over.위 > 0.4 || over.아래 > 0.4) out.자막넘침.push({ i, 글자: (cap.textContent || '').slice(0, 18), ...over });
    }
    return out;
  });

  console.log(JSON.stringify({ ...r, 페이지오류: errs.slice(0, 3) }, null, 1));
  await b.close();
})().catch(e => { console.error(String(e).slice(0, 400)); process.exit(1); });
