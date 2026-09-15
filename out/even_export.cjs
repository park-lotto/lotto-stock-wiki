// 이븐쇼핑(t11) 템플릿 + 팝업 모션으로 최민식 영상 프레임을 뽑는다.
// 진짜 UI(precision20-ui.js)를 브라우저에서 실행해 캡처한다 — 재현이 아니다.
const fs = require('fs');
const path = require('path');
const puppeteer = require('puppeteer');

const WORK = 'C:/Users/CH/AppData/Local/Temp/claude/C--Users-CH-Desktop-------/95282895-130e-4adc-bf25-7509d17fd5dc/scratchpad/volcano-noejeongu';
const URL = 'http://127.0.0.1:8767/out/scene-style-ui-showcase.html';
const OUT = path.join(WORK, 'even_frames');

const HOOK1 = '최민식이 기억하는';
const HOOK2 = '80년대 출연료';
const BODYTITLE = '최민식 첫 출연료 150만원의 진실';
const CHANNEL = '디씨썰극장';

const POP_FPS = 30;          // 팝업 구간만 프레임 단위
const timing = JSON.parse(fs.readFileSync(path.join(WORK, 'timing.json'), 'utf8'));

(async () => {
  fs.rmSync(OUT, { recursive: true, force: true });
  fs.mkdirSync(OUT, { recursive: true });

  const browser = await puppeteer.launch({
    executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    headless: 'new', args: ['--hide-scrollbars'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 900, height: 1500, deviceScaleFactor: 1.5 });
  page.on('pageerror', e => console.log('PAGEERROR', String(e).slice(0, 140)));
  await page.goto(URL, { waitUntil: 'networkidle0', timeout: 120000 });

  // 1) 이븐쇼핑 + 팝업
  await page.evaluate(() => {
    const card = [...document.querySelectorAll('.preset-card')].find(c => /이븐쇼핑/.test(c.textContent));
    if (card) card.click();
    const pop = document.querySelector('[data-hook-motion="pop"]');
    if (pop) pop.click();
  });

  // 2) 문구 (실측: 채널=입력7, hook1=8, hook2=9, bodyTitle=10, 워터마크=21)
  await page.evaluate((h1, h2, bt, ch) => {
    const byVal = v => [...document.querySelectorAll('input,textarea')].find(i => i.value === v);
    const set = (el, v) => { if (!el) return; el.value = v;
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true })); };
    set(byVal('숏템메이커'), ch);
    set(byVal('건망증 환자를 살려낸'), h1);
    set(byVal('일본 천재의 발명품'), h2);
    set(byVal('건망증 환자를 살려낸 천재의 발명품?'), bt);
    set(byVal('@숏템메이커'), '@' + ch);
    // 브랜딩 저장값도 같이 (UI 가 localStorage 에서 되살린다)
    try { if (window.sceneStyle.branding) window.sceneStyle.branding({ channel: ch }); } catch (e) {}
  }, HOOK1, HOOK2, BODYTITLE, CHANNEL);
  await page.evaluate((h1,h2,bt,ch)=>{ window.__H1=h1; window.__H2=h2; window.__BT=bt; window.__CH=ch; },
    HOOK1, HOOK2, BODYTITLE, CHANNEL);
  await new Promise(r => setTimeout(r, 250));

  // 3) 카드만 남긴다 — 크기를 먼저 고정해야 형제 제거 후에도 무너지지 않는다
  await page.evaluate(() => {
    const el = document.querySelector('#a-live-preview');
    const r = el.getBoundingClientRect();           // UI 기본 크기 (글꼴 자동맞춤 기준)
    const w = Math.round(r.width), h = Math.round(r.height);
    // ★조상을 숨기면 flex 자식인 카드가 0x0 으로 무너진다 — body 직속으로 옮긴 뒤 숨긴다
    document.body.appendChild(el);
    [...document.body.children].forEach(n => { if (n !== el) n.style.display = 'none'; });
    document.body.style.cssText = 'margin:0;padding:0;background:#0b0b0b';
    document.documentElement.style.cssText = 'background:#0b0b0b';
    Object.assign(el.style, { position: 'absolute', left: '0px', top: '0px', margin: '0',
      width: w + 'px', height: h + 'px', display: 'block' });
    window.sceneStyle.refresh();     // ← 여기서만 한 번. 이후 apply() 에서는 부르지 않는다
    window.__card = el;
  });
  await new Promise(r => setTimeout(r, 150));
  const box = await page.evaluate(() => {
    const r = window.__card.getBoundingClientRect();
    return { w: Math.round(r.width), h: Math.round(r.height) };
  });
  const clip = { x: 0, y: 0, width: box.w, height: box.h };
  console.log('card', box);

  // ★page.screenshot() 은 셔터 순간 재렌더를 일으켜 팝업/사진을 리셋한다(실측).
  //   CDP Page.captureScreenshot 은 합성 프레임을 그대로 떠서 상태가 보존된다.
  const cdp = await page.target().createCDPSession();
  const shot = async (file) => {
    const r = await cdp.send('Page.captureScreenshot', {
      format: 'png', captureBeyondViewport: false,
      clip: { x: 0, y: 0, width: box.w, height: box.h, scale: 1.5 },
    });
    fs.writeFileSync(path.join(OUT, file), Buffer.from(r.data, 'base64'));
  };

  // ★refresh() 는 .precision-media 를 데모 사진으로 되돌린다 — 반드시 refresh 뒤에 사진을 넣는다
  // ★밈 컷은 img 가 없고 meme 경로를 갖는다 — `img || 1` 로 뭉개면 밈이 통째로 사라진다(2026-09-13 실사고)
  const srcFor = (g) => g.img
    ? `/out/assets/scene-style/cms/${String(g.img).padStart(2, '0')}.jpg`
    : `/out/assets/scene-style/pepe/${path.basename(g.meme)}`;

  // frame: 'hook' | 'body'  · caption: 본문 흰 띠에 들어갈 그 컷의 자막
  const apply = async (src, motionMs, frame, caption) => {
    await page.evaluate((s, ms, fr, cap) => {
      const el = window.__card;
      // 훅/본문 틀 전환 — 본문은 사진 영역이 더 크다(38% vs 30.9%)
      if (fr === 'body') window.sceneStyle.show(1);
      else window.sceneStyle.show(0);
      // 자막 주입 — ★훅의 흰 띠는 bodyTitle(입력10), 본문의 흰 띠는 caption(입력11) 이다
      // ★show() 로 틀을 바꾸면 입력값이 화면에 다시 반영돼야 하므로 매번 전부 다시 쓴다
      {
        const ins = [...document.querySelectorAll('input,textarea')];
        const put = (ix, v) => { const e = ins[ix]; if (!e || v == null) return;
          e.value = v;
          e.dispatchEvent(new Event('input', { bubbles: true }));
          e.dispatchEvent(new Event('change', { bubbles: true })); };
        put(7, window.__CH); put(8, window.__H1); put(9, window.__H2);
        put(10, window.__BT);                       // 훅 흰 띠 = bodyTitle
        if (fr === 'body' && cap != null) put(11, cap);   // 본문 흰 띠 = caption
      }
      el.querySelectorAll('.precision-media, .scene-lens').forEach(n => { n.src = s; });
      // ★훅 흰 띠 글자가 팝업 투명도에 걸려 사라지는 문제 — 캡처 직전 불투명 고정
      if (fr !== 'body') {
        const t = [...el.querySelectorAll('.precision-text')];
        const band = t[t.length - 1];
        if (band) { band.style.opacity = '1'; band.style.transform = 'none'; }
      }
      if (ms !== null && ms !== undefined) {
        // ★기존 애니가 남아 있으면 motionAt 이 새 값을 못 만든다 — 정리 후 다시 건다
        document.getAnimations().forEach(a => { try { a.cancel(); } catch (e) {} });
        window.sceneStyle.motionAt(ms);
      }
    }, src, motionMs, frame, caption);
    await page.waitForFunction((s) => {
      const el = document.querySelector('#a-live-preview');
      const m = el.querySelector('.precision-media');
      return m && m.src.includes(s) && m.complete && m.naturalWidth > 0;
    }, { timeout: 15000 }, src);
    await new Promise(r => setTimeout(r, 60));
  };

  const groups = timing.groups;
  const hookEnd = groups[3].t;
  const popDur = Math.round(520 * 0.72);   // 374ms
  const shots = [];

  // A) 훅 팝업 — 프레임 단위
  const popFrames = Math.ceil(popDur / 1000 * POP_FPS);
  for (let i = 0; i <= popFrames; i++) {
    const ms = Math.min(popDur, Math.round(i / POP_FPS * 1000));
    const file = `pop_${String(i).padStart(3, '0')}.png`;
    await apply(srcFor(groups[0]), ms, 'hook', BODYTITLE);
    await shot(file);
    shots.push({ file, dur: 1 / POP_FPS });
  }
  const popSpent = (popFrames + 1) / POP_FPS;

  // B) 훅 나머지 (팝업 끝난 상태 유지)
  const hookRest = Math.max(0, hookEnd - popSpent);
  if (hookRest > 0.02) {
    await apply(srcFor(groups[0]), popDur + 200, 'hook', BODYTITLE);
    const file = 'hook_hold.png';
    await shot(file);
    shots.push({ file, dur: hookRest });
  }

  // C) 본문 — 컷마다 1장
  for (const g of groups) {
    const st = g.t, en = g.t + g.d;
    if (en <= hookEnd) continue;
    const dur = en - Math.max(st, hookEnd);
    await apply(srcFor(g), popDur, 'body', g.text);
    const file = `cut_${String(g.i).padStart(2, '0')}.png`;
    await shot(file);
    shots.push({ file, dur });
    console.log('cut', g.i, g.img ? ('img'+g.img) : ('MEME '+path.basename(g.meme)), 'dur', dur.toFixed(2));
  }

  fs.writeFileSync(path.join(OUT, 'shots.json'), JSON.stringify({ box, shots }, null, 1));
  const totalDur = shots.reduce((a, s) => a + s.dur, 0);
  console.log('DONE shots', shots.length, 'total', totalDur.toFixed(2), 'vs timing', timing.total);
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
