// 자막이 **본문 자리에 제대로** 들어갔나 — 장면 하나하나 눈으로 보는 대신 도구로 전수(2026-09-22).
//   사장님: "자막이 본문에 딱 배치가 안 되었었어. 그거 테스트 해봐."
//
//   재는 것(본문 장면 전부):
//     ①대본 줄이 자막으로 들어갔나(빠진 장면 수)     ②자막 글자가 자막칸(caption-mask) 안에 있나
//     ③자막이 제목·채널명과 겹치지 않나              ④자막이 화면 좌우를 넘지 않나
//     ⑤자막 내용이 그 장면의 대본과 같나(엉뚱한 줄이 붙지 않았나)
//   실행: node tools/qa_caption_placement_auto.js [url]    SHOT=폴더 → 문제 장면만 캡처
const puppeteer = require('puppeteer');
const fs = require('fs');
const url = process.argv[2] || 'http://127.0.0.1:8772/produce.html';
const SHOT = process.env.SHOT || '';
if (SHOT) fs.mkdirSync(SHOT, { recursive: true });
const wait = ms => new Promise(r => setTimeout(r, ms));

(async () => {
  const b = await puppeteer.launch({ headless: true });
  const p = await b.newPage(); await p.setViewport({ width: 1700, height: 1000, deviceScaleFactor: SHOT ? 2 : 1 });
  const errs = []; p.on('pageerror', e => errs.push(String(e).slice(0, 140)));
  await p.goto(url, { waitUntil: 'networkidle2', timeout: 120000 }); await wait(3000);

  // 장면꾸미기 단계로 간다 — ★상단 단계 아이콘은 `onclick="jump(5)"`다(실측 2026-09-22).
  //   글자로 찾으면 그 아래 라벨(.dkl)을 눌러 아무 일도 안 일어난다 — 검사가 조용히 헛돈다.
  let btn = null;
  for (let round = 0; round < 10 && !btn; round++) {
    await p.evaluate(() => {
      const t = document.querySelector('[onclick="jump(5)"]')
        || [...document.querySelectorAll('[onclick^="jump("]')]
             .find(e => /장면꾸미기/.test((e.textContent || '').trim()));
      if (t) t.click();
    });
    for (let i = 0; i < 6; i++) {
      await wait(2000);
      const cand = await p.$('[onclick="openSceneStyleEditor()"]');
      if (cand && await cand.evaluate(e => !!e.offsetParent)) { btn = cand; break; }
    }
  }
  if (!btn) {
    const where = await p.evaluate(() => (document.body.innerText.match(/\d+\s*·\s*[^\n]{2,20}/) || [''])[0]);
    console.log(JSON.stringify({ 오류: '편집 버튼이 안 보인다 — 이 작업은 장면꾸미기 단계까지 안 왔다', 지금단계: where }));
    await b.close(); process.exit(1);
  }
  await btn.evaluate(e => e.scrollIntoView({ block: 'center' })); await btn.click();
  await p.waitForSelector('dialog[open] iframe', { timeout: 40000 });
  const f = await (await p.$('dialog[open] iframe')).contentFrame();
  await f.waitForFunction(() => window.sceneStyle && document.querySelector('#a-live-preview'), { timeout: 60000 });
  await wait(3000);

  const report = await f.evaluate(async () => {
    const wait = ms => new Promise(r => setTimeout(r, ms));
    const pv = document.querySelector('#a-live-preview');
    const ctx = window.sceneStyle.context?.() || {};
    const scenes = ctx.scenes || [];
    const out = { 장면수: scenes.length, 본문장면: 0, 자막빈장면: [], 넘침: [], 겹침: [], 내용불일치: [] };

    for (let i = 0; i < scenes.length; i++) {
      const sc = scenes[i];
      if (sc.kind !== 'body') continue;
      out.본문장면++;
      const want = (sc.caption || '').trim();
      if (!want) {
        // ★말이 아직 시작 안 된 짧은 틈(비트 시작 전 0.1~0.3초)은 자막이 없는 게 정상이다.
        //   실측(2026-09-22 job 93de4727fc85): 비트1이 0.09초 뒤부터 말해 그 앞이 빈 장면이 된다.
        //   긴 무음(0.6초 넘음)만 "자막이 빠졌다"로 본다.
        const gap = (+sc.end) - (+sc.start);
        (gap > 0.6 ? out.자막빈장면 : (out.무음틈 ||= [])).push({ i, t: +(+sc.start).toFixed(2), 길이: +gap.toFixed(2) });
        continue;
      }

      window.sceneStyle.show(i); await wait(220);
      const cap = pv.querySelector('.precision-text[data-edit-bind="caption"]');
      if (!cap) { out.자막빈장면.push({ i, why: '화면에 자막 글자가 없다' }); continue; }

      const got = (cap.textContent || '').trim();
      if (got.replace(/\s+/g, '') !== want.replace(/\s+/g, '')) {
        out.내용불일치.push({ i, 대본: want.slice(0, 22), 화면: got.slice(0, 22) });
      }

      const g = document.createRange(); g.selectNodeContents(cap);
      const T = g.getBoundingClientRect(), P = pv.getBoundingClientRect();
      const pc = v => +(v / P.height * 100).toFixed(2);
      const pcx = v => +(v / P.width * 100).toFixed(2);

      // ② 자막칸 안에 있나
      const mask = pv.querySelector('.caption-mask');
      if (mask) {
        const M = mask.getBoundingClientRect();
        const up = pc(M.top - T.top), down = pc(T.bottom - M.bottom);
        if (up > 0.5 || down > 0.5) out.넘침.push({ i, 위로: up, 아래로: down, 글자: got.slice(0, 16) });
      }
      // ④ 좌우를 넘나
      const left = pcx(P.left - T.left), right = pcx(T.right - P.right);
      if (left > 0.3 || right > 0.3) out.넘침.push({ i, 왼쪽: left, 오른쪽: right, 글자: got.slice(0, 16) });

      // ③ 제목·채널명과 겹치나
      for (const bind of ['channel', 'bodyTitle', 'hook1', 'hook2']) {
        const other = pv.querySelector(`.precision-text[data-edit-bind="${bind}"]`);
        if (!other || other.hidden) continue;
        const r2 = document.createRange(); r2.selectNodeContents(other);
        const O = r2.getBoundingClientRect();
        if (O.height < 1) continue;
        const overlap = Math.min(O.bottom, T.bottom) - Math.max(O.top, T.top);
        const hOver = Math.min(O.right, T.right) - Math.max(O.left, T.left);
        if (overlap > 1 && hOver > 1) out.겹침.push({ i, 상대: bind, 겹친높이: pc(overlap) });
      }
    }
    return out;
  });

  const fails = [];
  if (report.자막빈장면.length) fails.push(`자막이 빈 본문 장면 ${report.자막빈장면.length}개`);
  if (report.넘침.length) fails.push(`자막이 칸을 넘음 ${report.넘침.length}건`);
  if (report.겹침.length) fails.push(`자막이 제목·채널명과 겹침 ${report.겹침.length}건`);
  if (report.내용불일치.length) fails.push(`대본과 화면 자막이 다름 ${report.내용불일치.length}건`);

  console.log(JSON.stringify({ ...report, 실패: fails, 페이지오류: errs.slice(0, 3) }, null, 1));
  await b.close();
  process.exit(fails.length ? 1 : 0);
})().catch(e => { console.error(String(e).slice(0, 400)); process.exit(1); });
