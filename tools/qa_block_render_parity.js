// '채널명 칸' 슬라이더가 **최종 렌더(MP4가 쓰는 PNG 레이어)**에도 화면과 똑같이 반영되는지 검사(2026-09-22).
//   왜: 편집기 화면이 맞아도 렌더가 다르면 고객이 보는 영상은 틀린다. 둘 다 precision20-ui.js가 그리지만
//       렌더는 snapshot을 sceneStyle.load()로 주입하는 **다른 경로**라 값이 안 실려 가면 조용히 기본값으로 나온다.
//   방법: ①편집기에서 슬라이더를 움직여 스냅샷을 뽑고 화면 좌표를 잰다
//         ②같은 스냅샷을 render_scene_style.js와 같은 방식(load+qa=1)으로 새 페이지에 주입해 좌표를 다시 잰다
//         ③두 좌표가 같아야 통과(0.4% 이내)
//   실행: node tools/qa_block_render_parity.js [url]     ONLY=템플릿이름 일부 → 그 칸만
//   ★이 검사는 값이 안 실려 가면 실패해야 정상이다(그걸 먼저 확인하고 믿을 것).
const puppeteer = require('puppeteer'), path = require('path'), { pathToFileURL } = require('url');
const url = process.argv[2] || 'http://127.0.0.1:8771/out/scene-style-ui-showcase.html';
const ONLY = process.env.ONLY || '';
const wait = ms => new Promise(r => setTimeout(r, ms));

// 화면에서 '칸 구조가 어디까지인지'를 재는 자 — 편집기·렌더 양쪽에서 똑같이 쓴다.
const PROBE = () => {
  const pv = document.querySelector('#a-live-preview'), P = pv.getBoundingClientRect();
  const pct = r => ({ t: +((r.top - P.top) / P.height * 100).toFixed(2), b: +((r.bottom - P.top) / P.height * 100).toFixed(2) });
  const ink = e => { const g = document.createRange(); g.selectNodeContents(e); return pct(g.getBoundingClientRect()); };
  const out = { texts: {}, icons: [], media: null, caption: null };
  for (const b of ['channel', 'hook1', 'hook2', 'bodyTitle', 'caption']) {
    const e = pv.querySelector('.precision-text[data-edit-bind="' + b + '"]');
    if (e && !e.hidden && e.getBoundingClientRect().height > 1) out.texts[b] = { ...ink(e), font: +parseFloat(getComputedStyle(e).fontSize).toFixed(2) };
  }
  pv.querySelectorAll('.body-ornament').forEach(e => { const r = e.getBoundingClientRect(); if (r.height > 1) out.icons.push(pct(r)); });
  const m = pv.querySelector('.scene-media-clip'), cm = pv.querySelector('.caption-mask');
  out.media = m ? pct(m.getBoundingClientRect()).t : null;
  out.caption = cm ? pct(cm.getBoundingClientRect()).t : null;
  return out;
};

(async () => {
  const browser = await puppeteer.launch({ headless: true });
  const edit = await browser.newPage();
  await edit.setViewport({ width: 1600, height: 1100 }); await edit.setCacheEnabled(false);
  const errs = []; edit.on('pageerror', e => errs.push(String(e).slice(0, 120)));
  await edit.goto(url, { waitUntil: 'networkidle0' }); await wait(900);
  await edit.evaluate(() => document.querySelector('[data-template-mode="story"]').click()); await wait(450);

  // 렌더와 같은 조건의 페이지(파일 URL + ?qa=1) — render_scene_style.js:8 과 같게 연다.
  const rend = await browser.newPage();
  await rend.setViewport({ width: 1600, height: 1100 }); await rend.setCacheEnabled(false);
  const rerrs = []; rend.on('pageerror', e => rerrs.push(String(e).slice(0, 120)));
  await rend.goto(pathToFileURL(path.resolve(__dirname, '../out/scene-style-ui-showcase.html')).href + '?qa=1', { waitUntil: 'networkidle0' });
  await wait(700);

  const setRange = async v => {
    await edit.evaluate(v => {
      const r = document.querySelector('[data-fixed-range="channel"]');
      r.value = String(v); r.dispatchEvent(new Event('input', { bubbles: true })); r.dispatchEvent(new Event('change', { bubbles: true }));
    }, v);
    let prev = ''; for (let i = 0; i < 12; i++) { await wait(220); const cur = JSON.stringify(await edit.evaluate(PROBE)); if (cur === prev) break; prev = cur; }
  };
  const near = (a, b, t) => a != null && b != null && Math.abs(a - b) <= t;
  const f = v => Math.round(v * 100) / 100;

  const fails = []; let checked = 0;
  const n = await edit.$$eval('[data-p20]', e => e.length);
  for (let i = 0; i < n; i++) {
    await edit.evaluate(i => document.querySelector('[data-p20="' + i + '"]').click(), i); await wait(320);
    const name = await edit.evaluate(() => document.querySelector('[data-stage-name]').textContent.trim().slice(0, 12));
    if (ONLY && !name.includes(ONLY)) continue;
    for (const sc of [0, 1]) {
      await edit.evaluate(s => document.querySelector('[data-scene-step="' + (s === 0 ? -1 : 1) + '"]').click(), sc); await wait(1500);
      await edit.evaluate(() => document.querySelectorAll('details').forEach(d => d.open = true));
      const where = name + '/' + (sc ? '본문' : '훅');
      const base = await edit.evaluate(() => { const r = document.querySelector('[data-fixed-range="channel"]'); return r && r.offsetParent ? Number(r.value) : null; });
      if (base == null) continue;

      for (const v of [base, 20]) {                       // 처음 값 / 최대
        await setRange(v);
        const screen = await edit.evaluate(PROBE);
        const snap = await edit.evaluate(() => window.sceneStyle.snapshot());
        const ctx = await edit.evaluate(() => window.sceneStyle.context ? window.sceneStyle.context() : (window.__lastContext || null));
        if (!snap) { fails.push(where + ' → 스냅샷이 안 나온다'); continue; }
        // 렌더와 같은 주입 경로
        const ok = await rend.evaluate((s, c) => { try { window.sceneStyle.load(c, s); window.sceneStyle.refresh(); return true; } catch (e) { return String(e).slice(0, 100); } }, snap, ctx);
        if (ok !== true) { fails.push(where + ' v' + v + ' → load 실패: ' + ok); continue; }
        await rend.evaluate(i => window.sceneStyle.show(i), snap.sceneIndex ?? sc);
        await wait(420);
        const shot = await rend.evaluate(PROBE);
        checked++;
        // 대조: 채널명·제목·아이콘·영상 시작이 화면과 같은 자리인가
        for (const b of Object.keys(screen.texts)) {
          const A = screen.texts[b], B = shot.texts[b];
          if (!B) { fails.push(where + ' v' + v + ' → 렌더에 ' + b + ' 없음'); continue; }
          if (!near(A.t, B.t, 0.4)) fails.push(where + ' v' + v + ': ' + b + ' 위치가 화면 ' + f(A.t) + '% ≠ 렌더 ' + f(B.t) + '%');
          if (!near(A.font, B.font, 0.6)) fails.push(where + ' v' + v + ': ' + b + ' 글자 크기 화면 ' + A.font + ' ≠ 렌더 ' + B.font + 'px');
        }
        // 훅엔 자막칸이 없다(null) — 한쪽만 없을 때만 어긋남으로 본다.
        const pair = (a, b, label) => {
          if (a == null && b == null) return;
          if (a == null || b == null) { fails.push(where + ' v' + v + ': ' + label + ' 한쪽만 있다 — 화면 ' + (a == null ? '없음' : f(a) + '%') + ' / 렌더 ' + (b == null ? '없음' : f(b) + '%')); return; }
          if (!near(a, b, 0.4)) fails.push(where + ' v' + v + ': ' + label + ' 화면 ' + f(a) + '% ≠ 렌더 ' + f(b) + '%');
        };
        pair(screen.media, shot.media, '영상 시작');
        pair(screen.caption, shot.caption, '자막칸');
        screen.icons.forEach((ic, k) => { const s = shot.icons[k]; if (!s || !near(ic.t, s.t, 0.4)) fails.push(where + ' v' + v + ': 아이콘' + (k + 1) + ' 화면 ' + f(ic.t) + '% ≠ 렌더 ' + (s ? f(s.t) + '%' : '없음')); });
      }
      await setRange(base);
    }
  }
  console.log('대조한 상태: ' + checked + '개');
  if (errs.length) console.log('편집기 오류 ' + errs.length + ': ' + errs.slice(0, 2).join(' | '));
  if (rerrs.length) console.log('렌더쪽 오류 ' + rerrs.length + ': ' + rerrs.slice(0, 2).join(' | '));
  if (fails.length) { console.log('어긋남 ' + fails.length + '건:'); fails.slice(0, 40).forEach(x => console.log('  NG ' + x)); }
  else console.log('화면 = 렌더, 어긋남 0건');
  await browser.close();
  process.exit(fails.length ? 1 : 0);
})().catch(e => { console.error(e); process.exit(1); });
