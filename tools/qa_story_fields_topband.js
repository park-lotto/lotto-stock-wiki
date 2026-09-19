// 썰쇼핑형 편집칸·상단/하단 칸 검사(2026-09-18):
//   ① 20종 훅 = 채널명·훅 제목 1·훅 제목 2·보조 제목 칸이 다 뜨고, 채널명 글자가 제목줄과 안 겹친다
//   ② 20종 본문 = 채널명·본문 제목·현재 장면 자막 칸이 다 뜬다
//   ③ 상단 제목칸을 키우고 줄여도 글자 크기는 그대로, 흰 띠 아래 빈틈 없음(흰 띠가 칸 바닥을 따라감)
//   ④ 하단 칸을 올리면 영상이 그만큼 위로 줄고 하단 띠가 생긴다
//   node tools/qa_story_fields_topband.js [url] [shotDir]
const puppeteer = require('puppeteer');
const url = process.argv[2] || 'http://127.0.0.1:8771/out/scene-style-ui-showcase.html';
const shots = process.argv[3];
(async () => {
  const b = await puppeteer.launch({headless: true}); const p = await b.newPage(); await p.setViewport({width: 1920, height: 1200});
  const errors = []; p.on('pageerror', e => errors.push(e.message));
  await p.goto(url, {waitUntil: 'networkidle0'});
  await p.click('[data-template-mode="story"]');
  const n = await p.$$eval('[data-p20]', els => els.length);
  let fail = 0;
  const kindBtn = k => p.evaluate(k => { const b = [...document.querySelectorAll('button')].find(x => x.textContent.trim() === (k === 'hook' ? '훅' : '본문') && x.offsetParent); b?.click(); }, k);
  for (let i = 0; i < n; i++) {
    await p.click(`[data-p20="${i}"]`);
    for (const k of ['hook', 'body']) {
      await kindBtn(k); await new Promise(r => setTimeout(r, 60));
      const r = await p.evaluate(() => {
        const vis = [...document.querySelectorAll('.layout-a [data-field-key]')].filter(f => !f.hidden).map(f => f.dataset.fieldKey);
        const L = document.querySelector('.precision-edit-layer');
        const t = b => [...L.querySelectorAll('.precision-text')].find(e => e.dataset.editBind === b);
        const rg = el => { if (!el) return null; const r = document.createRange(); r.selectNodeContents(el); return r.getBoundingClientRect(); };
        const c = rg(t('channel')), h = rg(t('hook1')) || rg(t('bodyTitle'));
        return {vis, channelShown: !!(c && c.width > 4), overlap: !!(c && h && c.bottom > h.top + 1)};
      });
      const need = k === 'hook' ? ['channel', 'hook1', 'hook2', 'bodyTitle'] : ['channel', 'bodyTitle', 'caption'];
      const ok = need.every(x => r.vis.includes(x)) && r.channelShown && !r.overlap;
      if (!ok) { fail++; console.log('NG', i, k, JSON.stringify(r)); }
    }
  }
  // ③④ 이븐쇼핑(0번) 훅에서 상단/하단 칸
  await p.click('[data-p20="0"]'); await kindBtn('hook'); await new Promise(r => setTimeout(r, 60));
  const measure = () => p.evaluate(() => {
    const L = document.querySelector('.precision-edit-layer'), P = document.querySelector('#a-live-preview').getBoundingClientRect();
    const t = b => [...L.querySelectorAll('.precision-text')].find(e => e.dataset.editBind === b);
    const band = t('bodyTitle').getBoundingClientRect(), media = document.querySelector('.scene-camera img, .scene-camera video, #a-live-preview img')?.getBoundingClientRect();
    const m = document.querySelector('[data-scene-media], .precision-media, .scene-media') || null;
    return {font: parseFloat(getComputedStyle(t('hook1')).fontSize), bandBottom: (band.bottom - P.top) / P.height * 100,
            mediaTop: window.sceneStyle.geometry().media.top, mediaH: window.sceneStyle.geometry().media.height,
            bottomBand: [...L.children].some(e => e.dataset.editBind === 'bottom-band' || (parseFloat(e.style.top) > 80 && parseFloat(e.style.height) > 5))};
  });
  const setRange = (key, v) => p.evaluate((key, v) => { const i = document.querySelector(`[data-fixed-range="${key}"]`); i.value = v; i.dispatchEvent(new Event('input', {bubbles: true})); }, key, v);
  const base = await measure();
  const res = {base};
  for (const v of [50, 20]) { await setRange('top', v); res['top' + v] = await measure(); if (shots) await (await p.$('#a-live-preview')).screenshot({path: `${shots}/top${v}.png`}); }
  await setRange('top', 30); await setRange('bottom', 15); res.bottom15 = await measure();
  if (shots) await (await p.$('#a-live-preview')).screenshot({path: `${shots}/bottom15.png`});
  console.log(JSON.stringify(res));
  for (const key of ['top50', 'top20']) {
    const m = res[key];
    if (Math.abs(m.font - base.font) > .01) { fail++; console.log('NG 글자크기 바뀜', key); }
    if (Math.abs((m.mediaTop - m.bandBottom) - (base.mediaTop - base.bandBottom)) > 1) { fail++; console.log('NG 흰 띠-영상 간격', key, m.bandBottom, m.mediaTop); }
  }
  if (!(res.bottom15.bottomBand && Math.abs(res.bottom15.mediaTop + res.bottom15.mediaH - 85) < .6)) { fail++; console.log('NG 하단칸'); }
  if (errors.length) { fail++; console.log('페이지 오류', errors); }
  console.log(fail ? `실패 ${fail}건` : `전부 통과 (${n}종 훅/본문 칸 + 상단·하단 칸)`);
  await b.close(); process.exit(fail ? 1 : 0);
})().catch(e => { console.error(e); process.exit(1); });
