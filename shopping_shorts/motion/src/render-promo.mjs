// 랜딩 프로모 영상 렌더 — price_compare(1280x640) · free_banner(1600x360).
//   node src/render-promo.mjs stills price_compare 20 120 230   → .render_tmp/tour_step1b_f<N>.png
//   node src/render-promo.mjs mp4 price_compare free_banner  → ../static/landing/<id>.mp4
// 재료: public/hero/*.jpg (free_banner 배경, gitignore) — hero_data.json 기준.
import {bundle} from '@remotion/bundler';
import {renderMedia, renderStill, selectComposition} from '@remotion/renderer';
import {spawnSync} from 'child_process';
import fs from 'fs';
import path from 'path';
import {fileURLToPath} from 'url';

const here = path.dirname(fileURLToPath(import.meta.url));
const tmpDir = path.join(here, '..', '.render_tmp');
fs.mkdirSync(tmpDir, {recursive: true});
const [, , mode, ...rest] = process.argv;
const compId = (id) => ({price_compare: 'PriceCompare', free_banner: 'FreeBanner', sq_4: 'SqRender', hook_wall: 'HookWall', trend: 'TrendBanner', easy60: 'Easy60'})[id];
const serveUrl = await bundle({entryPoint: path.join(here, 'index.ts'), publicDir: path.join(here, '..', 'public')});

if (mode === 'stills') {
  const [id, ...frames] = rest;
  const composition = await selectComposition({serveUrl, id: compId(id)});
  for (const f of frames.map(Number)) {
    const out = path.join(tmpDir, `${id}_f${String(f).padStart(3, '0')}.png`);
    await renderStill({composition, serveUrl, frame: f, output: out, imageFormat: 'png'});
    console.log('still', out);
  }
} else if (mode === 'mp4') {
  const outDir = path.join(here, '..', '..', 'static', 'landing');
  for (const id of rest) {
    const composition = await selectComposition({serveUrl, id: compId(id)});
    const raw = path.join(tmpDir, `${id}_raw.mp4`);
    await renderMedia({composition, serveUrl, codec: 'h264', imageFormat: 'jpeg', jpegQuality: 95, crf: 14, outputLocation: raw, muted: true});
    const mp4 = path.join(outDir, `${id}.mp4`);
    const r = spawnSync('ffmpeg', ['-y', '-v', 'error', '-i', raw, '-an', '-c:v', 'libx264', '-preset', 'slow', '-crf', '23',
      '-vf', 'scale=in_range=full:out_range=tv,format=yuv420p', '-color_range', 'tv', '-movflags', '+faststart', '-r', '30', mp4], {stdio: 'inherit'});
    if (r.status !== 0) throw new Error('ffmpeg 실패 ' + r.status);
    console.log('mp4', mp4, fs.statSync(mp4).size, 'bytes');
  }
} else {
  console.error('usage: node src/render-promo.mjs stills <id> <frames...> | mp4 <id...>');
  process.exit(1);
}
