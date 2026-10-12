// 템플릿 머리띠(채널명 줄) 구간 재기 — 2026-09-19 사장님 "캡슐·아이콘·글자가 같이 움직이게".
//   편집기에서 쓰는 원본 그림을 캔버스로 읽어, 위에서부터 '같은 색이 이어지는 띠'가 끝나는 줄을 찾는다.
//   결과: out/scene-header-bands.json  {"<preset>:<hook|body|frame>": {"y0":0,"y1":56,"color":"#1b1b1b"}}
//   실행: node tools/measure_header_bands.js [url]
const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');
const url = process.argv[2] || 'http://127.0.0.1:8771/out/scene-style-ui-showcase.html';

(async () => {
  const browser = await puppeteer.launch({headless: true});
  const page = await browser.newPage();
  await page.setViewport({width: 1600, height: 1100});
  const errors = [];
  page.on('pageerror', e => errors.push(String(e).slice(0, 120)));
  await page.goto(url, {waitUntil: 'networkidle0'});
  await new Promise(r => setTimeout(r, 900));

  const result = {};
  for (const mode of ['story', 'continuous']) {
    await page.evaluate(m => document.querySelector(`[data-template-mode="${m}"]`)?.click(), mode);
    await new Promise(r => setTimeout(r, 500));
    const count = await page.$$eval('[data-p20]', els => els.length);
    for (let i = 0; i < count; i++) {
      await page.evaluate(i => document.querySelector(`[data-p20="${i}"]`)?.click(), i);
      await new Promise(r => setTimeout(r, 320));
      const scenes = mode === 'story' ? [0, 1] : [0];
      for (const scene of scenes) {
        await page.evaluate(s => document.querySelector(`[data-scene-step="${s === 0 ? -1 : 1}"]`)?.click(), scene);
        await new Promise(r => setTimeout(r, 360));
        const info = await page.evaluate(async () => {
          const api = window.sceneStyle;
          const snap = api?.snapshot?.();
          const base = document.querySelector('.precision-base');
          if (!base?.src || !base.naturalWidth) return null;
          const canvas = document.createElement('canvas');
          canvas.width = base.naturalWidth; canvas.height = base.naturalHeight;
          const ctx = canvas.getContext('2d', {willReadFrequently: true});
          ctx.drawImage(base, 0, 0);
          const {width: W, height: H} = canvas;
          const rowAt = y => ctx.getImageData(0, y, W, 1).data;
          const avg = data => { let r = 0, g = 0, b = 0; for (let x = 0; x < data.length; x += 4) { r += data[x]; g += data[x + 1]; b += data[x + 2]; } const n = data.length / 4; return [r / n, g / n, b / n]; };
          const dist = (a, b) => Math.abs(a[0] - b[0]) + Math.abs(a[1] - b[1]) + Math.abs(a[2] - b[2]);
          // 맨 윗줄 색을 머리띠 색으로 보고, 그 색에서 크게 벗어나는 첫 줄을 머리띠 끝으로 본다.
          const top = avg(rowAt(1));
          let end = 0;
          for (let y = 2; y < Math.floor(H * 0.45); y++) {
            if (dist(avg(rowAt(y)), top) > 42) { end = y; break; }
          }
          // 글자·아이콘이 섞인 줄에서 일찍 끊기지 않게, 끊긴 뒤에도 같은 색이 다시 이어지면 계속 내려간다.
          if (end) {
            for (let y = end; y < Math.floor(H * 0.45); y++) {
              if (dist(avg(rowAt(y)), top) <= 42) end = y + 1; else if (y - end > Math.round(H * 0.02)) break;
            }
          }
          const hex = c => '#' + c.map(v => Math.round(v).toString(16).padStart(2, '0')).join('');
          // 채널명 줄(데이터)보다 짧게 잡히면 그 줄을 덮도록 늘린다 — 색만 보면 글자·아이콘에서 일찍 끊긴다.
          const rowsData = (window.PRECISION20 || []).concat(window.CONTINUOUS20 || []);
          const preset = rowsData.find(r => r.id === snap?.presetId);
          const frame = preset ? (preset.frame || (snap?.frameKind === 'body' ? preset.body : preset.hook)) : null;
          const chBox = frame?.channel_box || (frame?.channel_boxes || [])[0];
          const chLine = (frame?.lines || []).find(l => l.bind === 'channel');
          const chBottom = chBox ? (chBox.y + chBox.height) : (chLine ? chLine.y1 : 0);
          const scale = frame?.height ? H / frame.height : 1;
          const need = chBottom ? Math.round(chBottom * scale) + Math.round(H * 0.012) : 0;
          const y1 = Math.max(end, need);
          return {presetId: snap?.presetId || null, frameKind: snap?.frameKind || null, W, H, y0: 0, y1, color: hex(top), src: base.src.split('/').pop(), 색으로잰값: end, 채널줄: need};
        });
        if (!info || !info.presetId) continue;
        const key = `${info.presetId}:${info.frameKind || 'frame'}`;
        result[key] = {y0: info.y0, y1: info.y1, color: info.color, w: info.W, h: info.H, image: info.src, 색으로잰값: info.색으로잰값, 채널줄: info.채널줄};
      }
    }
  }
  const out = path.join(__dirname, '..', 'out', 'scene-header-bands.json');
  fs.writeFileSync(out, JSON.stringify(result, null, 1), 'utf8');
  const rows = Object.entries(result);
  console.log(JSON.stringify({잰것: rows.length, 예시: rows.slice(0, 6).map(([k, v]) => `${k} 머리띠 0~${v.y1}px (전체 ${v.h}px, ${(v.y1 / v.h * 100).toFixed(1)}%) ${v.color}`), 오류: errors}, null, 1));
  console.log('저장:', out);
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
