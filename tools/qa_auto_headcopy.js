// 장면꾸미기를 열었을 때 **제목·소제목이 자동으로 들어가 있나**(2026-09-22 사장님).
//   사장님: "그냥 자동화가 되는 과정이야 눌러야 되는 거 없이 처음에 배치까지 잘 되야 하는 거야."
//
//   지금 구조(고치기 전): produce가 진입하며 제목 후보를 자동으로 뽑아 window._hcCopies에 담지만,
//   새 편집기는 STATE.headcopy만 보고 연다(scene-style-produce.js:122) → 사장님이 카드를 고르기
//   전에는 빈 채로 열리고, 서버가 대비책으로 **첫 나레이션**을 제목에 넣는다("아니 텀블러이 / 있다고?").
//   옛 꾸미기(produce.html frPick)는 이미 `hcText.value || _hcFirstCopy()`로 1번을 자동으로 쓴다
//   — 같은 판단이 두 군데서 다른 0순위-B 상태다.
//
//   재는 것: ①후보가 자동으로 뽑혔나 ②편집기 제목이 후보에서 왔나(나레이션 베낌이 아닌가)
//            ③소제목이 찼나 ④자막이 본문 장면에 들어갔나
//   실행: node tools/qa_auto_headcopy.js [url]     기본 http://127.0.0.1:8772/produce.html
//         JOB=<job_id> → 그 작업을 골라서 연다(미러에 여러 건이 쌓이면 제작소가 최신 것을 연다.
//                        ★안 고르면 '다른 대본으로 시험했다'고 착각한다 — 2026-09-22 실제로 겪음)
//   ★고치기 전 코드에서 ②③이 실패해야 정상이다 — 그걸 먼저 확인하고 이 검사를 믿을 것.
const puppeteer = require('puppeteer');
const url = process.argv[2] || 'http://127.0.0.1:8772/produce.html';
const WANT_JOB = process.env.JOB || '';
const wait = ms => new Promise(r => setTimeout(r, ms));

(async () => {
  const b = await puppeteer.launch({ headless: true });
  const p = await b.newPage(); await p.setViewport({ width: 1700, height: 1000 });
  const errs = []; p.on('pageerror', e => errs.push(String(e).slice(0, 140)));
  await p.goto(url, { waitUntil: 'networkidle2', timeout: 120000 });
  await wait(3000);

  // 원하는 작업 고르기 — 미러에 여러 건이 쌓이면 제작소는 **최신 것**을 자동으로 연다.
  //   ★왼쪽 목록은 job_id가 아니라 **작업 id(data-wid)**로 찍혀 있다. JOB에는 둘 중 아무거나 준다.
  if (WANT_JOB) {
    const picked = await p.evaluate(async (want) => {
      const wait = ms => new Promise(r => setTimeout(r, ms));
      for (const row of document.querySelectorAll('.ss-work[data-wid]')) {
        if (row.dataset.wid === want) { row.click(); await wait(2500); return row.dataset.wid; }
      }
      // job_id로 줬으면 작업 id를 모르므로, 목록을 순서대로 열어 MIX_JOB이 맞는 것을 찾는다.
      return null;
    }, WANT_JOB);
    if (!picked) {
      const wids = await p.$$eval('.ss-work[data-wid]', els => els.map(e => e.dataset.wid));
      for (const wid of wids) {
        await p.evaluate(w => document.querySelector(`.ss-work[data-wid="${w}"]`).click(), wid);
        await wait(3500);
        const now = await p.evaluate(() => (typeof MIX_JOB !== 'undefined' ? MIX_JOB : null));
        if (now === WANT_JOB) break;
      }
    }
    await wait(3000);
    const now = await p.evaluate(() => (typeof MIX_JOB !== 'undefined' ? MIX_JOB : null));
    if (now !== WANT_JOB && picked !== WANT_JOB) {
      console.log(JSON.stringify({ 오류: `요청한 작업(${WANT_JOB})을 못 열었다 — 지금 열린 것은 ${now}` }));
      await b.close(); process.exit(1);
    }
  }

  // 제목 후보는 6단계 진입 때 자동으로 뽑힌다(produce.html: loadHeadcopySuggest(false)).
  // AI 호출이라 시간이 걸린다 — 최대 90초 기다린다.
  // ★상단 단계 아이콘은 `onclick="jump(5)"`다(실측 2026-09-22). 글자로 찾으면 그 아래
  //   라벨(.dkl)을 눌러 아무 일도 안 일어나고 검사가 조용히 헛돈다.
  const moved = await p.evaluate(() => {
    const t = document.querySelector('[onclick="jump(5)"]')
      || [...document.querySelectorAll('[onclick^="jump("]')]
           .find(e => /장면꾸미기/.test((e.textContent || '').trim()));
    if (!t) return false; t.click(); return true;
  });
  if (!moved) { console.log(JSON.stringify({ 오류: '장면꾸미기 단계를 못 찾았다', errs })); await b.close(); process.exit(1); }

  let copies = [];
  for (let i = 0; i < 45; i++) {
    await wait(2000);
    copies = await p.evaluate(() => (window._hcCopies || []).map(c => ({
      text: c.text || '', subline: c.subline || '', why: (c.why || '').slice(0, 40) })));
    if (copies.length) break;
  }

  const btn = await p.$('[onclick="openSceneStyleEditor()"]');
  const vis = btn && await btn.evaluate(e => !!e.offsetParent);
  if (!vis) { console.log(JSON.stringify({ 후보수: copies.length, 오류: '편집 버튼이 안 보인다', errs })); await b.close(); process.exit(1); }
  await btn.evaluate(e => e.scrollIntoView({ block: 'center' })); await btn.click();
  await p.waitForSelector('dialog[open] iframe', { timeout: 40000 });
  const f = await (await p.$('dialog[open] iframe')).contentFrame();
  await f.waitForFunction(() => window.sceneStyle && document.querySelector('#a-live-preview'), { timeout: 60000 });
  await wait(3000);

  const view = await f.evaluate(() => {
    const ctx = window.sceneStyle.context?.() || {};
    const t = ctx.text || {}, scenes = ctx.scenes || [];
    return {
      제목1: t.hook1 || '', 제목2: t.hook2 || '', 소제목: t.supportTitle || '', 본문제목: t.bodyTitle || '',
      첫나레이션: (scenes.find(s => (s.caption || '').trim()) || {}).caption || '',
      장면수: scenes.length,
      자막있는장면: scenes.filter(s => (s.caption || '').trim()).length,
      본문장면: scenes.filter(s => s.kind === 'body').length,
      본문자막: scenes.filter(s => s.kind === 'body' && (s.caption || '').trim()).length,
    };
  });

  const norm = s => String(s || '').replace(/\s+/g, '');
  const title = norm(view.제목1 + view.제목2);
  const fromNarration = !!title && norm(view.첫나레이션).startsWith(title.slice(0, Math.min(8, title.length)));
  const fromCopies = copies.some(c => norm(c.text) === title);

  // 계약(template_copy.EVEN_SHOPPING) — 화면이 실제로 담는 길이. 넘으면 양끝이 잘린다.
  const MAX1 = 11, MAX2 = 10, MAX_SUB = 22;
  const fails = [];
  if (!copies.length) fails.push('제목 후보가 자동으로 안 뽑혔다(AI 호출 실패 또는 미실행)');
  if (!title) fails.push('제목이 비어 있다');
  else if (fromNarration && !fromCopies) fails.push('제목이 후보가 아니라 **첫 나레이션**에서 왔다 — 자동 배선이 끊겨 있다');
  if (view.제목1.length > MAX1) fails.push(`제목 첫 줄 ${view.제목1.length}자 > 계약 ${MAX1}`);
  if (view.제목2.length > MAX2) fails.push(`제목 둘째 줄 ${view.제목2.length}자 > 계약 ${MAX2}`);
  if (!norm(view.소제목)) fails.push('소제목(흰 띠)이 비어 있다');
  else if (view.소제목.length > MAX_SUB) {
    // ★뿌리(2026-09-22 실측): AI에게 준 한도가 canary off면 32자(_LEGACY_SUBLINE_LEN)인데
    //   화면 계약은 22자다 — 같은 값이 두 군데서 다르다(0순위-B). 사장님 결정 대기.
    fails.push(`소제목 ${view.소제목.length}자 > 계약 ${MAX_SUB} (AI 한도는 canary off라 32자 — 두 값이 어긋남)`);
  }
  if (view.본문장면 && view.본문자막 === 0) fails.push('본문 장면에 자막이 하나도 없다');

  const openedJob = await p.evaluate(() => (typeof MIX_JOB !== 'undefined' ? MIX_JOB : null));
  console.log(JSON.stringify({
    작업: openedJob,
    후보수: copies.length,
    후보1: copies[0] || null,
    편집기: view,
    판정: { 제목이후보에서왔나: fromCopies, 제목이나레이션베낌인가: fromNarration },
    실패: fails,
    페이지오류: errs.slice(0, 3),
  }, null, 1));
  await b.close();
  process.exit(fails.length ? 1 : 0);
})().catch(e => { console.error(String(e).slice(0, 400)); process.exit(1); });
