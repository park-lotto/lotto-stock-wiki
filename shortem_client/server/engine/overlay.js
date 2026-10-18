// 자막·제목·틀 그림(투명 PNG) 찍기 — 설치팩 chrome-headless-shell(고정 경로)을 puppeteer-core 로.
//   글꼴은 캐시 파일을 요청 가로채기로 넣는다(파일을 작업 폴더에 복사하지 않음 · 네트워크 0).
//   장면마다: 등장 효과 구간은 1/30초마다, 낱말 강조가 바뀌는 시각마다, 그 뒤 정지 한 장.
import fs from 'node:fs';
import path from 'node:path';
import puppeteer from 'puppeteer-core';
import { toolPath } from '../tools_paths.js';
import { PAGE_JS, PAGE_CSS } from './overlay_page.js';

const MOTIONS = JSON.parse(fs.readFileSync(new URL('./caption_motions.json', import.meta.url), 'utf8'));
const FPS = 30;
const fontMime = f => (/\.otf$/i.test(f) ? 'font/otf' : /\.woff2$/i.test(f) ? 'font/woff2' : /\.woff$/i.test(f) ? 'font/woff' : 'font/ttf');

export async function launch() {
  return puppeteer.launch({ executablePath: toolPath('chrome'), headless: 'shell', args: ['--no-first-run', '--disable-gpu', '--font-render-hinting=none', '--hide-scrollbars', '--mute-audio'], defaultViewport: null });
}

// fonts = {family: {file, ext}} · scenes = timeline 장면(+off 꼬리) · 반환 {shots:[{file,dur}], metrics:[…], fonts:{family:loaded}}
export async function renderOverlays({ spec, scenes, title, fonts, outDir, browser: ext, onProgress }) {
  fs.mkdirSync(outDir, { recursive: true });
  const browser = ext || await launch();
  const famList = Object.keys(fonts);
  try {
    const page = await browser.newPage();
    await page.setViewport({ width: spec.W, height: spec.H, deviceScaleFactor: 1 });
    await page.setRequestInterception(true);
    page.on('request', req => {
      const u = req.url();
      const m = u.match(/^https:\/\/shortem\.local\/font\/(\d+)$/);
      if (m && famList[+m[1]]) {
        const f = fonts[famList[+m[1]]];
        try { return req.respond({ status: 200, headers: { 'Access-Control-Allow-Origin': '*', 'Content-Type': fontMime('x.' + (f.ext || 'ttf')) }, body: fs.readFileSync(f.file) }); } catch { return req.abort(); }
      }
      if (u.startsWith('data:') || u === 'about:blank') return req.continue();
      return req.abort();   // 그 밖 네트워크는 전부 막는다
    });
    const errors = [];
    page.on('pageerror', e => errors.push(String(e.message || e)));
    const faces = famList.map((fam, i) => `@font-face{font-family:"${fam.replace(/"/g, '')}";src:url("https://shortem.local/font/${i}") format("${{ otf: 'opentype', ttf: 'truetype', woff2: 'woff2', woff: 'woff' }[fonts[fam].ext] || 'truetype'}");font-weight:400;font-display:block}`).join('\n');
    const data = { W: spec.W, H: spec.H, frames: spec.frames, scenes, title, motions: MOTIONS.motions, wordFx: MOTIONS.word_fx, fonts: famList };
    const html = `<!doctype html><html><head><meta charset="utf-8"><style>:root{--W:${spec.W}px;--H:${spec.H}px}${faces}\n${PAGE_CSS}</style></head><body><div id="stage"></div>
<script>window.__DATA__=${JSON.stringify(data).replace(/</g, '\\u003c')};</script><script>${PAGE_JS}</script></body></html>`;
    await page.setContent(html, { waitUntil: 'load' });
    const loaded = await page.evaluate(() => window.R.fontsReady());
    const shots = [], metrics = [];
    const shoot = async (i, t, n) => {
      const m = await page.evaluate((i, t) => window.R.show(i, t), i, t);
      await page.evaluate(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))));
      const file = path.join(outDir, `s${String(i).padStart(3, '0')}_${String(n).padStart(3, '0')}.png`);
      await page.screenshot({ path: file, clip: { x: 0, y: 0, width: spec.W, height: spec.H }, omitBackground: true });
      return { m, file };
    };
    for (let i = 0; i < scenes.length; i++) {
      const s = scenes[i];
      const durMs = Math.max(1, (s.t1 - s.t0) * 1000);
      // 시각 목록: 0, 등장 구간 1/30초마다, 낱말 바뀜, 그리고 정지(장면 끝까지)
      const first = await page.evaluate((i, t) => window.R.show(i, t), i, 0);
      const times = new Set([0]);
      const titleLeft = first.titleEnterMs ? first.titleEnterMs - s.t0 * 1000 : 0;
      const animMs = Math.min(durMs, Math.max(first.enterMs || 0, titleLeft > 0 ? titleLeft : 0));
      for (let t = 1000 / FPS; t < animMs; t += 1000 / FPS) times.add(Math.round(t * 1000) / 1000);
      if (animMs > 0 && animMs < durMs) times.add(animMs);
      if (s.words && s.words.length > 1 && !s.off) for (const w of s.words) { const t = (w.t0 - s.t0) * 1000; if (t > 0 && t < durMs) times.add(Math.round(t)); }
      const list = [...times].sort((a, b) => a - b);
      let n = 0, lastM = null;
      for (let k = 0; k < list.length; k++) {
        const t = list[k], next = k + 1 < list.length ? list[k + 1] : durMs;
        const { m, file } = await shoot(i, t, n++);
        shots.push({ file, dur: (next - t) / 1000 });
        lastM = m;
      }
      metrics.push({ scene: i, ...lastM });
      if (onProgress) onProgress(i + 1, scenes.length);
    }
    await page.close();
    if (errors.length) { const e = new Error('그리기 중 오류'); e.detail = errors.join('\n').slice(0, 1500); throw e; }
    return { shots, metrics, fonts: loaded };
  } finally {
    if (!ext) await browser.close();
  }
}

// ffconcat 목록(그림·길이). 마지막 그림은 한 번 더(concat 규칙)
export function writeConcat(shots, file) {
  const esc = p => p.replace(/\\/g, '/').replace(/'/g, "'\\''");
  const lines = ['ffconcat version 1.0'];
  for (const s of shots) { lines.push(`file '${esc(s.file)}'`); lines.push(`duration ${Math.max(0.001, s.dur).toFixed(4)}`); }
  if (shots.length) lines.push(`file '${esc(shots[shots.length - 1].file)}'`);
  fs.writeFileSync(file, lines.join('\n') + '\n');
  return file;
}
