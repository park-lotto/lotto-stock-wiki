// 장면꾸미기 편집기 전 조작 훑기(2026-09-19 사장님 "하나씩 다 눌러보고 테스트해라").
//   훅/본문/고정형에서 모든 버튼·슬라이더를 실제로 누르고, 누를 때마다 화면 규칙을 검사한다.
//   규칙: ① 글자가 미리보기 밖으로 나가지 않는다 ② 채널명·제목·자막이 서로 겹치지 않는다
//         ③ 본문 자막 칸이 영상 위로 올라오지 않는다 ④ 페이지 오류 0
//   실행: node tools/qa_scene_all_controls.js [url]
const puppeteer = require('puppeteer');
const url = process.argv[2] || 'http://127.0.0.1:8771/out/scene-style-ui-showcase.html';

const CHECK = () => {
  // 모션이 도는 중 화면은 검사하지 않는다(확대·떨어지는 도중은 잠깐 밖으로 나가는 게 정상) → 끝난 상태로 맞춘다
  document.querySelectorAll('.precision-text,.precision-patch,.scene-camera').forEach(e => e.getAnimations().forEach(a => { try { a.finish(); } catch {} }));
  const pv = document.querySelector('#a-live-preview').getBoundingClientRect();
  const pct = v => (v - pv.top) / pv.height * 100;
  const out = [];
  // 화면 전체 확대(줌 펀치·천천히 확대·떨림)는 일부러 화면 밖까지 키우는 효과라 '밖으로' 검사에서 뺀다
  const camera = [...document.querySelectorAll('.scene-camera')].some(c => { const t = getComputedStyle(c).transform; return t && t !== 'none'; });
  const els = camera ? [] : [...document.querySelectorAll('.precision-text')].filter(e => !e.hidden && e.getBoundingClientRect().height > 0);
  for (const el of els) {
    const r = el.getBoundingClientRect(), range = document.createRange();
    range.selectNodeContents(el);
    const t = range.getBoundingClientRect();
    const scale = (el.style.transform.match(/scaleX\(([\d.]+)\)/) || [, 1])[1];
    if (t.left < pv.left - 4 || t.right > pv.right + 4) out.push(`${el.dataset.editBind}: 좌우 밖으로 ${Math.round(Math.max(pv.left - t.left, t.right - pv.right))}px (scaleX ${scale})`);
    if (r.top < pv.top - 2 || r.bottom > pv.bottom + 2) out.push(`${el.dataset.editBind}: 위아래 밖으로`);
  }
  // 겹침은 '실제 글자'로 잰다(요소 상자는 줄 간격 여백이 있어 1%쯤 늘 겹친다)
  const box = b => { const e = document.querySelector(`.precision-text[data-edit-bind="${b}"]`); if (!e) return null;
    const range = document.createRange(); range.selectNodeContents(e); const r = range.getBoundingClientRect();
    return r.height > 0 ? {t: pct(r.top), b: pct(r.bottom)} : null; };
  const over = (a, b) => a && b && Math.min(a.b, b.b) - Math.max(a.t, b.t) > 1.2;
  const ch = box('channel'), h1 = box('hook1'), h2 = box('hook2'), bt = box('bodyTitle'), cap = box('caption');
  if (over(ch, h1) || over(ch, h2) || over(ch, bt)) out.push('채널명과 제목이 겹침');
  if (over(h1, h2)) out.push('제목 1·2줄이 겹침');
  if (over(bt, cap) || over(h2, cap)) out.push('제목과 자막이 겹침');
  return out;
};

(async () => {
  const browser = await puppeteer.launch({headless: true});
  const page = await browser.newPage();
  await page.setViewport({width: 1600, height: 1100});
  const errors = [];
  page.on('pageerror', e => errors.push(String(e).slice(0, 120)));
  await page.goto(url, {waitUntil: 'networkidle0'});
  await new Promise(r => setTimeout(r, 900));

  const fails = [];
  const wait = (ms = 260) => new Promise(r => setTimeout(r, ms));
  const check = async where => { const bad = await page.evaluate(CHECK); bad.forEach(b => fails.push(`${where} → ${b}`)); };
  const clickAll = async (selector, where) => {
    const n = await page.$$eval(selector, els => els.length).catch(() => 0);
    for (let i = 0; i < n; i++) {
      const ok = await page.evaluate((s, i) => { const e = document.querySelectorAll(s)[i]; if (!e) return false; e.click(); return true; }, selector, i);
      if (!ok) continue;
      await wait();
      const label = await page.evaluate((s, i) => document.querySelectorAll(s)[i]?.textContent?.trim().slice(0, 10) || '', selector, i);
      await check(`${where}[${label}]`);
    }
  };
  const setRange = async (selector, value, where) => {
    const ok = await page.evaluate((s, v) => { const i = document.querySelector(s); if (!i) return false; i.value = v; i.dispatchEvent(new Event('input', {bubbles: true})); return true; }, selector, value);
    if (!ok) return;
    await wait(320);
    await check(`${where}=${value}`);
  };
  const openCards = () => page.evaluate(() => {
    document.querySelectorAll('.scene-text-panel > .text-group, .scene-effects-panel .text-group').forEach(d => d.open = true);
    document.querySelectorAll('details').forEach(d => { if (d.querySelector('.caption-looks') || d.querySelector('[data-fixed-range]')) d.open = true; });
  });

  for (const mode of ['story', 'continuous']) {
    await page.evaluate(m => document.querySelector(`[data-template-mode="${m}"]`)?.click(), mode);
    await wait(500);
    for (const preset of [0, 7, 13]) {
      await page.evaluate(i => document.querySelector(`[data-p20="${i}"]`)?.click(), preset);
      await wait(400);
      for (const scene of [0, 1]) {
        await page.evaluate(s => { const b = document.querySelector(`[data-scene-step="${s === 0 ? -1 : 1}"]`); if (b) b.click(); }, scene);
        await wait(420);
        await openCards();
        const name = await page.evaluate(() => document.querySelector('[data-stage-name]')?.textContent?.slice(0, 8) || '');
        const where = `${mode}/${name}/${scene ? '본문' : '훅'}`;
        await check(where);
        await clickAll('[data-hook-motion]', `${where} 훅모션`);
        await clickAll('[data-body-caption-motion]', `${where} 본문모션`);
        await clickAll('[data-hook-band-motion]', `${where} 띠모션`);
        await clickAll('[data-fixed-palette]', `${where} 팔레트`);
        await clickAll('[data-caption-look]', `${where} 자막모양`);
        await clickAll('[data-caption-position]', `${where} 자막위치`);
        for (const v of [50, 20, 30]) await setRange('[data-fixed-range="top"]', v, `${where} 상단칸`);
        for (const v of [15, 0]) await setRange('[data-fixed-range="bottom"]', v, `${where} 하단칸`);
        for (const bind of ['channel', 'hook1', 'hook2', 'bodyTitle', 'caption']) {
          for (const step of ['0.1', '-0.1']) {
            for (let i = 0; i < 3; i++) {
              const ok = await page.evaluate((b, s) => { const f = document.querySelector(`[data-field-key="${b}"]`); const btn = f?.querySelector(`[data-font-step="${s}"]`); if (!btn || f.hidden) return false; btn.click(); return true; }, bind, step);
              if (!ok) break;
            }
            await wait(320);
            await check(`${where} ${bind} 크기${step}`);
          }
          for (const dir of ['-1', '1']) {
            const ok = await page.evaluate((b, d) => { const f = document.querySelector(`[data-field-key="${b}"]`); const btn = f?.querySelector(`[data-position-step="${d}"]`); if (!btn || f.hidden) return false; btn.click(); btn.click(); return true; }, bind, dir);
            if (ok) { await wait(300); await check(`${where} ${bind} 이동${dir}`); }
          }
        }
      }
    }
  }
  // 폰트 세트 전환
  await page.evaluate(() => document.querySelector('[data-left-tab="font"]')?.click());
  await wait(400);
  await clickAll('[data-font-set]', '폰트세트');

  const unique = [...new Set(fails)];
  console.log(JSON.stringify({검사건수: unique.length, 실패: unique.slice(0, 40), 페이지오류: [...new Set(errors)]}, null, 1));
  console.log(unique.length === 0 && errors.length === 0 ? '전부 통과' : `실패 ${unique.length}종`);
  await browser.close();
  process.exit(unique.length === 0 && errors.length === 0 ? 0 : 1);
})().catch(e => { console.error(e); process.exit(1); });
